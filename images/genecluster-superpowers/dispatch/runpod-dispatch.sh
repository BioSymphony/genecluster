#!/usr/bin/env bash
# BioSymphony GeneCluster cloud dispatch template
#
# RunPod dispatcher (canonical reference for the cloud-portable template family).
# All other cloud dispatchers (aws / gcp / vastai / lambda) mirror this contract.
#
# Behavior:
#   1. Encode <BOOT_SCRIPT_PATH> + the cloud-agnostic boot prelude as base64.
#   2. POST /v1/pods with networkVolumeId, dockerStartCmd, env vars, and
#      cpuFlavorIds widening for capacity.
#   3. Persist provider response files under ignored runtime dispatch state so
#      the operator-side monitor can pick up where this exits without staging
#      provider identifiers in source paths.
#   4. Exit. Polling, log-pulling, and self-stop are NOT this script's job , 
#      see operator-side monitors and the boot script's `.self_stop_status`
#      sentinel pattern.
#
# Lessons baked in (do not rip out):
#   * dockerStartCmd has a ~64 KB POST-body ceiling. Boot scripts >50 KB
#     should self-fetch their large payloads from S3/GCS/catbox; this
#     script's wrapper is intentionally tiny.
#   * No inline heredocs in dockerStartCmd.
#   * Network volumes attach in SECURE cloud only.
#     We widen via cpuFlavorIds (NOT via cloudType:COMMUNITY).
#   * Never pass RUNPOD_API_KEY into the pod. Boot scripts must rely on the
#     operator-side monitor or provider-native storage for cleanup and pulls.
#   * Boot scripts must `rm -f SUCCESS FAILURE *.summary.tsv` at the start
#     to avoid stale-sentinel false positives.
#   * mambaforge image has no curl/wget; downloads must use Python urllib
#     with a Mozilla User-Agent (feedback_mambaforge_image_lacks_curl_wget,
#).
#
# Args:
#   $1  TOOL_NAME             short identifier (alnum + dash); used in run-id
#                             and as a tag on the pod
#   $2  IMAGE                 container image (default: condaforge/mambaforge:latest)
#                            : pass the superpowers image once it's pushed
#   $3  BOOT_SCRIPT_PATH      absolute path to the bash boot script (this is
#                             the "real work" payload that the wrapper will exec)
#   $4  MOUNT_PATH            mount point for the network volume (default /workspace)
#
# Env (required):
#   RUNPOD_API_KEY                          (exported or sourced from RUNPOD_ENV_FILE)
#   GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID    e.g. <network-volume-id>
#   GENECLUSTER_RUNPOD_DATACENTER           e.g. US-KS-2
#
# Env (optional):
#   RUN_ID                  default: $(date -u +%Y%m%d-%H%M%S)
#   POD_NAME                default: <tool>-<run_id>
#   CONTAINER_DISK_GB       default: 60
#   GPU_TYPE_ID             if set, request a GPU pod (e.g. NVIDIA_GeForce_RTX_4090)
#   POD_TIMEOUT_HOURS       informational; written into the dockerStartCmd banner
#   RUNPOD_EXPOSE_HTTP      default: 0. Set to 1 only for deliberate short-lived
#                           summary pulls through the RunPod proxy.
#   SERVE_TTL_SECONDS       default: 14400 when RUNPOD_EXPOSE_HTTP=1
#   DISPATCH_OUT_DIR        default: <repo>/.runtime/provider-dispatch/runpod
#
# Outputs (written to DISPATCH_OUT_DIR):
#   <tool>-<run_id>-create-response.json   raw POST response
#   <tool>-<run_id>-pod-id                 pod ID alone (for monitors)
#   <tool>-<run_id>-launch.json            human-readable manifest
#
# Cost model (RunPod, 2026-05 indicative):
#   CPU 8-core 32 GB:    ~$0.30/h SECURE, ~$0.13/h COMMUNITY
#   GPU RTX 4090 24 GB:  ~$0.60/h SECURE, ~$0.34/h COMMUNITY
#   Network volume:      ~$0.07/GB-month
# Volumes pin you to SECURE; budget accordingly.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ----- args + env -------------------------------------------------------------

TOOL_NAME="${1:-}"
IMAGE="${2:-condaforge/mambaforge:latest}"
BOOT_SCRIPT_PATH="${3:-}"
MOUNT_PATH="${4:-/workspace}"

if [[ -z "$TOOL_NAME" || -z "$BOOT_SCRIPT_PATH" ]]; then
  cat >&2 <<USAGE
usage: $0 <tool_name> [image] <boot_script_path> [mount_path]

required env:
  RUNPOD_API_KEY
  GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID
  GENECLUSTER_RUNPOD_DATACENTER

example:
  RUN_ID=<run-id> \\
  $0 cblaster condaforge/mambaforge:latest \\
     /path/to/cblaster-boot.sh /workspace
USAGE
  exit 64
fi

if [[ ! -f "$BOOT_SCRIPT_PATH" ]]; then
  echo "FATAL: boot script not found: $BOOT_SCRIPT_PATH" >&2
  exit 66
fi

# Pull RunPod creds from an explicit untracked env file if not already exported.
if [[ -z "${RUNPOD_API_KEY:-}" && -n "${RUNPOD_ENV_FILE:-}" && -f "$RUNPOD_ENV_FILE" ]]; then
  # shellcheck disable=SC1091
  source "$RUNPOD_ENV_FILE"
fi

: "${RUNPOD_API_KEY:?RUNPOD_API_KEY required (export or source via RUNPOD_ENV_FILE)}"
: "${GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID:?network volume id required}"
: "${GENECLUSTER_RUNPOD_DATACENTER:?datacenter required (e.g. US-KS-2)}"

RUN_ID="${RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
POD_NAME="${POD_NAME:-${TOOL_NAME}-${RUN_ID}}"
CONTAINER_DISK_GB="${CONTAINER_DISK_GB:-60}"
POD_TIMEOUT_HOURS="${POD_TIMEOUT_HOURS:-4}"
RUNPOD_EXPOSE_HTTP="${RUNPOD_EXPOSE_HTTP:-0}"
SERVE_TTL_SECONDS="${SERVE_TTL_SECONDS:-14400}"
DISPATCH_OUT_DIR="${DISPATCH_OUT_DIR:-${SCRIPT_DIR}/../../../.runtime/provider-dispatch/runpod}"
mkdir -p "$DISPATCH_OUT_DIR"

# Sanity: alphanumeric + dash for TOOL_NAME (used in pod name + S3-style paths
# in parallel dispatchers).
if [[ ! "$TOOL_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "FATAL: TOOL_NAME must be alnum/_/-: $TOOL_NAME" >&2
  exit 64
fi

# ----- shared download helper (sourced by boot scripts) -----------------------
# Boot scripts can `source <(cat dispatch/runpod-dispatch.sh) || true` to no-op
# the dispatcher logic and just import the helper, but the canonical pattern is
# for the boot script to inline its own copy. This is the reference impl.
#
# Usage in a boot script:
#   biosymphony_download <name> <url> <sha256> <dest>
#
# Used inline below as a heredoc-free string fed into the wrapper.
read -r -d '' DOWNLOAD_HELPER <<'HELPER' || true
biosymphony_download() {
  local name="$1" url="$2" sha="$3" dest="$4"
  local actual i
  for i in 1 2 3; do
    if python3 -c "
import urllib.request, sys
req = urllib.request.Request(sys.argv[1], headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
with urllib.request.urlopen(req, timeout=300) as r, open(sys.argv[2], 'wb') as f:
    while True:
        chunk = r.read(65536)
        if not chunk:
            break
        f.write(chunk)
" "$url" "$dest" 2>>biosymphony-download-errors.log; then
      actual=$(sha256sum "$dest" | awk '{print $1}')
      if [ "$actual" = "$sha" ]; then
        echo "ok name=$name sha=$sha bytes=$(wc -c < "$dest")"
        return 0
      fi
      echo "sha_mismatch name=$name expected=$sha actual=$actual attempt=$i" >&2
    else
      echo "urllib_failed name=$name attempt=$i" >&2
    fi
    sleep 5
  done
  echo "FAIL name=$name after_3_retries" >&2
  return 1
}
HELPER

# ----- build dockerStartCmd ---------------------------------------------------
# Strategy:
#   1. base64-encode the boot script (no heredoc inside dockerStartCmd).
#   2. Wrapper: write boot script to /workspace/<run_id>/boot.sh, source the
#      Mozilla-UA download helper as a sibling file, exec boot.sh.
#   3. Always start http.server EARLY (before the boot script runs) so a
#      monitor can pull sentinels via the runpod proxy
#.
#
# The wrapper is intentionally tiny (<2 KB) so dockerStartCmd stays well under
# 64 KB even with a 30 KB boot script base64'd. Boot scripts >40 KB should
# self-fetch from catbox/S3 instead of being embedded.

BOOT_B64="$(base64 < "$BOOT_SCRIPT_PATH" | tr -d '\n')"
HELPER_B64="$(printf '%s' "$DOWNLOAD_HELPER" | base64 | tr -d '\n')"

WORKDIR="${MOUNT_PATH%/}/${TOOL_NAME}/${RUN_ID}"

# Wrapper: shell-quote-safe (no embedded EOF heredoc). Single double-quoted
# string with \$ for runtime expansion of pod-side env vars and ' for the
# pod's own quoting.
read -r -d '' DOCKER_START_CMD <<WRAPPER || true
bash -c "set -ux; mkdir -p '${WORKDIR}/logs'; cd '${WORKDIR}'; echo '[boot] BioSymphony GeneCluster cloud dispatch v1, tool=${TOOL_NAME} run_id=${RUN_ID} timeout=${POD_TIMEOUT_HOURS}h pod=\${RUNPOD_POD_ID:-unknown}' | tee logs/dispatch.log; rm -f SUCCESS FAILURE STATUS *.summary.tsv 2>/dev/null || true; if [ '${RUNPOD_EXPOSE_HTTP}' = '1' ]; then python3 -m http.server 8000 --directory '${WORKDIR}' > logs/http.log 2>&1 & echo \$! > logs/http.pid; sleep 2; else echo '[boot] http proxy disabled; use provider storage or operator-side tools for artifact pull' > logs/http.log; fi; printf '%s' '${HELPER_B64}' | base64 -d > biosymphony_helper.sh; chmod +x biosymphony_helper.sh; printf '%s' '${BOOT_B64}' | base64 -d > boot.sh; chmod +x boot.sh; export BIOSYMPHONY_TOOL_NAME='${TOOL_NAME}' BIOSYMPHONY_RUN_ID='${RUN_ID}' BIOSYMPHONY_MOUNT_PATH='${MOUNT_PATH}' BIOSYMPHONY_WORKDIR='${WORKDIR}'; cd '${WORKDIR}' && bash boot.sh > logs/boot.log 2>&1; RC=\$?; echo phase=boot_exit rc=\$RC ts=\$(date -u +%s) >> STATUS 2>/dev/null || true; echo \"{\\\"stage\\\":\\\"complete\\\",\\\"boot_rc\\\":\$RC,\\\"ts\\\":\\\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\\\"}\" > .self_stop_status; sleep '${SERVE_TTL_SECONDS}'"
WRAPPER

# Sanity: hard-fail if wrapper exceeds 60 KB (leave headroom under 64 KB POST limit).
WRAPPER_BYTES="${#DOCKER_START_CMD}"
if (( WRAPPER_BYTES > 60000 )); then
  cat >&2 <<MSG
FATAL: dockerStartCmd is ${WRAPPER_BYTES} bytes; >60 KB likely to silently fail.
Move boot script payload to catbox.moe / S3 / GCS and have the boot script
self-fetch + sha256-verify.
MSG
  exit 65
fi

# ----- build POST payload -----------------------------------------------------
# We widen capacity via cpuFlavorIds (compute pool union), NOT cloudType:COMMUNITY,
# because the volume only attaches in SECURE.
# Valid cpuFlavorIds enum (verified against the RunPod /v1/pods schema):
#   cpu3c, cpu3g, cpu3m   (3rd-gen compute / general / memory)
#   cpu5c, cpu5g, cpu5m   (5th-gen compute / general / memory)
# Default widens across both gens for compute + general flavors (typical
# bioinformatics workloads are CPU/memory-balanced; "m" memory-optimized
# carries premium for large-RAM tools like assemblies).
# TODO: if RunPod adds a wildcard later, replace the array.
CPU_FLAVORS_JSON='["cpu5c","cpu5g","cpu3c","cpu3g"]'

if [[ -n "${GPU_TYPE_ID:-}" ]]; then
  GPU_BLOCK=$(printf ',"gpuTypeIds":["%s"],"gpuCount":1' "$GPU_TYPE_ID")
  CPU_FLAVORS_JSON='[]'  # GPU pods use gpuTypeIds, not cpuFlavorIds
else
  GPU_BLOCK=""
fi

PAYLOAD_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-payload.json"

# Export so the python heredoc below can pick them up.
export TOOL_NAME RUN_ID POD_NAME IMAGE CONTAINER_DISK_GB MOUNT_PATH \
       GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID GENECLUSTER_RUNPOD_DATACENTER \
       CPU_FLAVORS_JSON RUNPOD_EXPOSE_HTTP
export GPU_TYPE_ID="${GPU_TYPE_ID:-}"
export DOCKER_START_CMD_PIPED="$DOCKER_START_CMD"

python3 - <<PY > "$PAYLOAD_FILE"
import json, os, sys

payload = {
    "name": os.environ["POD_NAME"],
    "imageName": os.environ["IMAGE"],
    "containerDiskInGb": int(os.environ["CONTAINER_DISK_GB"]),
    "cloudType": "SECURE",
    "networkVolumeId": os.environ["GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID"],
    "volumeMountPath": os.environ["MOUNT_PATH"],
    "dataCenterIds": [os.environ["GENECLUSTER_RUNPOD_DATACENTER"]],
    "dockerStartCmd": ["bash","-lc", os.environ["DOCKER_START_CMD_PIPED"]],
    "env": {
        "BIOSYMPHONY_TOOL_NAME":  os.environ["TOOL_NAME"],
        "BIOSYMPHONY_RUN_ID":     os.environ["RUN_ID"],
        "BIOSYMPHONY_MOUNT_PATH": os.environ["MOUNT_PATH"],
    },
}
if os.environ.get("RUNPOD_EXPOSE_HTTP") == "1":
    payload["ports"] = ["8000/http"]
cpu_flavors = json.loads(os.environ.get("CPU_FLAVORS_JSON","[]"))
if cpu_flavors:
    payload["cpuFlavorIds"] = cpu_flavors
gpu_type = os.environ.get("GPU_TYPE_ID","").strip()
if gpu_type:
    payload["gpuTypeIds"] = [gpu_type]
    payload["gpuCount"] = 1
json.dump(payload, sys.stdout, indent=2)
PY

# ----- POST -------------------------------------------------------------------

RESP_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-create-response.json"
HTTP_CODE_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-http-code"

set +e
HTTP_CODE=$(curl -sS \
  -o "$RESP_FILE" -w "%{http_code}" \
  -X POST "https://rest.runpod.io/v1/pods" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary @"$PAYLOAD_FILE")
CURL_RC=$?
set -e

echo "$HTTP_CODE" > "$HTTP_CODE_FILE"

if (( CURL_RC != 0 )); then
  echo "FATAL: curl exited $CURL_RC posting to RunPod" >&2
  exit 70
fi

if [[ "$HTTP_CODE" != "200" && "$HTTP_CODE" != "201" ]]; then
  echo "FATAL: RunPod create returned HTTP $HTTP_CODE" >&2
  echo "response saved to: $RESP_FILE" >&2
  cat "$RESP_FILE" >&2 || true
  exit 71
fi

# Extract pod id
POD_ID="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('id') or d.get('pod',{}).get('id') or '')" "$RESP_FILE" || true)"

if [[ -z "$POD_ID" ]]; then
  echo "FATAL: could not parse pod id from response" >&2
  cat "$RESP_FILE" >&2 || true
  exit 72
fi

echo "$POD_ID" > "$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-pod-id"

# Manifest for monitor consumption.
MANIFEST_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch.json"
export WORKDIR
python3 - <<PY > "$MANIFEST_FILE"
import json, os
print(json.dumps({
  "cloud": "runpod",
  "tool_name": os.environ["TOOL_NAME"],
  "run_id": os.environ["RUN_ID"],
  "pod_id": "$POD_ID",
  "pod_name": os.environ["POD_NAME"],
  "image": os.environ["IMAGE"],
  "mount_path": os.environ["MOUNT_PATH"],
  "workdir": os.environ.get("WORKDIR") or f"{os.environ['MOUNT_PATH'].rstrip('/')}/{os.environ['TOOL_NAME']}/{os.environ['RUN_ID']}",
  "datacenter": os.environ["GENECLUSTER_RUNPOD_DATACENTER"],
  "volume_id": os.environ["GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID"],
  "monitor_url_template": "https://{pod_id}-8000.proxy.runpod.net/STATUS?cb={rand} (only when RUNPOD_EXPOSE_HTTP=1)",
  "stop_url_template":    "POST https://rest.runpod.io/v1/pods/{pod_id}/stop  (operator-side; uses caller's RUNPOD_API_KEY)",
}, indent=2))
PY

cat <<DONE
[runpod-dispatch] OK
  tool       = $TOOL_NAME
  run_id     = $RUN_ID
  pod_id     = $POD_ID
  pod_name   = $POD_NAME
  image      = $IMAGE
  mount_path = $MOUNT_PATH
  workdir    = $WORKDIR
  manifest   = $MANIFEST_FILE
  response   = $RESP_FILE

Monitor (cache-busted;):
  curl -sS "https://${POD_ID}-8000.proxy.runpod.net/${TOOL_NAME}/${RUN_ID}/STATUS?cb=\$RANDOM"

Stop / hibernate (operator-side; preserves volume,):
  curl -sS -X POST -H "Authorization: Bearer \$RUNPOD_API_KEY" \\
    "https://rest.runpod.io/v1/pods/${POD_ID}/stop"

Delete (destroys container disk; volume preserved):
  curl -sS -X DELETE -H "Authorization: Bearer \$RUNPOD_API_KEY" \\
    "https://rest.runpod.io/v1/pods/${POD_ID}"
DONE
