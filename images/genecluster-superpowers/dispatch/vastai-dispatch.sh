#!/usr/bin/env bash
# BioSymphony GeneCluster cloud dispatch template
#
# Vast.ai dispatcher (cheapest GPU; parallel to runpod-dispatch.sh).
#
# Architecture:
#   1. Auto-install vastai-cli if missing.
#   2. Stage boot.sh + helper.sh to a public-readable URL (S3 with public-read,
#      GCS public-object, or catbox.moe). Vast.ai instances are bare Docker
#      containers without volume parity to RunPod's networkVolume: pre-staging
#      to a remote URL is the canonical pattern (instances are ephemeral).
#   3. `vastai search offers` to find a host matching constraints.
#   4. `vastai create instance` with --onstart-cmd that fetches boot.sh from
#      the staging URL and execs it.
#   5. Boot script self-uploads sentinels back to the same staging URL OR to
#      a separate user-controlled S3 prefix (recommended for production).
#   6. Self-destroy via vast.ai REST API (token from `vastai set api-key`)
#     : call `DELETE /api/v0/instances/<id>/`.
#
# Tradeoffs vs RunPod / AWS / GCP:
#   + Cheapest GPU on the market (RTX 3090/4090 hosts often $0.20-0.40/h spot).
#   + No cloud account required if you're paying per-instance.
#   - No durable volume; every instance is fresh disk. Pre-stage everything.
#   - Hosts vary in network bandwidth: verify with `vastai search` filters.
#   - Limited regional control; the "datacenter" is whichever host bid the offer.
#
# Args (parallel to runpod-dispatch.sh):
#   $1 TOOL_NAME
#   $2 IMAGE              container image; vast.ai requires a Docker image
#                         (no bare-OS path). Default: condaforge/mambaforge:latest
#                         For the superpowers image: ghcr.io/<owner>/genecluster-superpowers:v0.1
#   $3 BOOT_SCRIPT_PATH
#   $4 MOUNT_PATH         default /workspace
#
# Env (required):
#   VASTAI_API_KEY                    (or run `vastai set api-key <key>`)
#   BIOSYMPHONY_STAGING_URL_BASE      e.g. https://files.catbox.moe or
#                                     https://your-s3.s3.amazonaws.com/...
#                                     OR set BIOSYMPHONY_STAGING_S3_PREFIX
#                                     for AWS S3 staging
#
# Env (optional):
#   VAST_GPU                  default 'RTX_4090' : vast.ai gpu name
#   VAST_DLPERF_MIN           default 30         : DLPerf threshold filter
#   VAST_INET_DOWN_MIN        default 100        : Mbps; reject slow hosts
#   VAST_DISK_GB              default 60         : host disk request
#   VAST_RAM_GB_MIN           default 16         : host RAM minimum
#   VAST_CPU_CORES_MIN        default 4
#   VAST_MAX_HOURLY_USD       default 0.50       : bid ceiling
#   USE_INTERRUPTIBLE         default 0          : set 1 for spot-style hosts
#   POD_TIMEOUT_HOURS         informational
#   RUN_ID                    default $(date -u +%Y%m%d-%H%M%S)
#   DISPATCH_OUT_DIR          default $(dirname BOOT_SCRIPT_PATH)/.vastai-dispatch
#
# Outputs (DISPATCH_OUT_DIR):
#   <tool>-<run_id>-instance-id            single-line vast.ai instance id
#   <tool>-<run_id>-launch.json            manifest with monitor URL
#   <tool>-<run_id>-create-response.json   raw vastai create JSON
#
# Self-destroy command (operator-side; mirror of RunPod stop):
#   vastai destroy instance <instance_id>
#
# Cost model (vast.ai, 2026-05 indicative):
#   RTX 3090 24 GB: $0.10, 0.30/h
#   RTX 4090 24 GB: $0.25, 0.50/h
#   A100 80 GB:     $0.60, 1.20/h
#   H100 80 GB:     $1.50, 2.50/h
# Interruptible (spot-equivalent) often 30, 50% cheaper than on-demand.
#
# TODO: support upload of boot script directly to vast.ai's instance
# filesystem via SSH once the instance is up: current pattern requires
# external staging URL.

set -euo pipefail

# ----- args + env -------------------------------------------------------------

TOOL_NAME="${1:-}"
IMAGE="${2:-condaforge/mambaforge:latest}"
BOOT_SCRIPT_PATH="${3:-}"
MOUNT_PATH="${4:-/workspace}"

if [[ -z "$TOOL_NAME" || -z "$BOOT_SCRIPT_PATH" ]]; then
  cat >&2 <<USAGE
usage: $0 <tool_name> [image] <boot_script_path> [mount_path]

required env:
  VASTAI_API_KEY                    (or run `vastai set api-key <key>` once)
  BIOSYMPHONY_STAGING_URL_BASE      OR  BIOSYMPHONY_STAGING_S3_PREFIX

example (cheap RTX 4090 spot):
  VAST_GPU=RTX_4090 USE_INTERRUPTIBLE=1 VAST_MAX_HOURLY_USD=0.35 \\
  BIOSYMPHONY_STAGING_S3_PREFIX=s3://<your-dispatch-bucket> \\
  RUN_ID=<run-id> \\
  $0 clean ghcr.io/<owner>/genecluster-superpowers:v0.1 \\
     /path/to/clean-boot.sh /workspace
USAGE
  exit 64
fi

if [[ ! -f "$BOOT_SCRIPT_PATH" ]]; then
  echo "FATAL: boot script not found: $BOOT_SCRIPT_PATH" >&2
  exit 66
fi

# Auto-install vastai-cli if missing
if ! command -v vastai >/dev/null 2>&1; then
  echo "[vastai-dispatch] installing vastai-cli (one-time)" >&2
  pip install --user vastai-cli >&2 \
    || { echo "FATAL: pip install vastai-cli failed; install manually" >&2; exit 67; }
  hash -r
fi

# Persist API key if env-passed
if [[ -n "${VASTAI_API_KEY:-}" ]]; then
  vastai set api-key "$VASTAI_API_KEY" >/dev/null 2>&1 || true
fi

RUN_ID="${RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
VAST_GPU="${VAST_GPU:-RTX_4090}"
VAST_DLPERF_MIN="${VAST_DLPERF_MIN:-30}"
VAST_INET_DOWN_MIN="${VAST_INET_DOWN_MIN:-100}"
VAST_DISK_GB="${VAST_DISK_GB:-60}"
VAST_RAM_GB_MIN="${VAST_RAM_GB_MIN:-16}"
VAST_CPU_CORES_MIN="${VAST_CPU_CORES_MIN:-4}"
VAST_MAX_HOURLY_USD="${VAST_MAX_HOURLY_USD:-0.50}"
USE_INTERRUPTIBLE="${USE_INTERRUPTIBLE:-0}"
POD_TIMEOUT_HOURS="${POD_TIMEOUT_HOURS:-4}"
DISPATCH_OUT_DIR="${DISPATCH_OUT_DIR:-$(dirname "$BOOT_SCRIPT_PATH")/.vastai-dispatch}"
mkdir -p "$DISPATCH_OUT_DIR"

if [[ ! "$TOOL_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "FATAL: TOOL_NAME must be alnum/_/-: $TOOL_NAME" >&2
  exit 64
fi

# ----- Mozilla-UA download helper ---------------------------------------------
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

# ----- Stage boot script to public-readable URL -------------------------------
# Two staging modes:
#   1. BIOSYMPHONY_STAGING_S3_PREFIX (preferred for production; AWS bucket)
#   2. BIOSYMPHONY_STAGING_URL_BASE  (manual upload mode; e.g. catbox)
#
# Mode 1 supports auto-staging here; mode 2 expects boot.sh already at
# ${BIOSYMPHONY_STAGING_URL_BASE}/<tool>/<run-id>/boot.sh.

HELPER_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-helper.sh"
printf '%s\n' "$DOWNLOAD_HELPER" > "$HELPER_FILE"

if [[ -n "${BIOSYMPHONY_STAGING_S3_PREFIX:-}" ]]; then
  command -v aws >/dev/null 2>&1 || { echo "FATAL: aws CLI required for S3 staging"; exit 67; }
  S3_PREFIX="${BIOSYMPHONY_STAGING_S3_PREFIX%/}/${TOOL_NAME}/${RUN_ID}"
  aws s3 cp "$BOOT_SCRIPT_PATH" "$S3_PREFIX/boot.sh"   --quiet
  aws s3 cp "$HELPER_FILE"      "$S3_PREFIX/helper.sh" --quiet
  # Generate a presigned URL valid for the pod lifetime (default 12 h).
  BOOT_URL="$(aws s3 presign "$S3_PREFIX/boot.sh"   --expires-in 43200)"
  HELPER_URL="$(aws s3 presign "$S3_PREFIX/helper.sh" --expires-in 43200)"
  STATUS_PUSH_PREFIX="$S3_PREFIX/status"
  STATUS_PUSH_MODE="s3"
elif [[ -n "${BIOSYMPHONY_STAGING_URL_BASE:-}" ]]; then
  BOOT_URL="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/boot.sh"
  HELPER_URL="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/helper.sh"
  STATUS_PUSH_PREFIX="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/status"
  STATUS_PUSH_MODE="manual"
  echo "WARN: BIOSYMPHONY_STAGING_URL_BASE mode, upload boot.sh + helper.sh to:"
  echo "  $BOOT_URL"
  echo "  $HELPER_URL"
  echo "before the instance boots."
else
  echo "FATAL: set BIOSYMPHONY_STAGING_S3_PREFIX (auto) or BIOSYMPHONY_STAGING_URL_BASE (manual)" >&2
  exit 64
fi

# ----- vastai search offers ---------------------------------------------------
# vastai search offers query language: AND-joined predicates separated by space.
# We sort by dollars-per-DLperf to find best $/perf hosts.

SEARCH_QUERY="gpu_name=$VAST_GPU dlperf>=$VAST_DLPERF_MIN inet_down>=$VAST_INET_DOWN_MIN cpu_cores>=$VAST_CPU_CORES_MIN cpu_ram>=$VAST_RAM_GB_MIN disk_space>=$VAST_DISK_GB"
if [[ "$USE_INTERRUPTIBLE" == "1" ]]; then
  SEARCH_QUERY="$SEARCH_QUERY rentable=true"
fi
# Bid ceiling
SEARCH_QUERY="$SEARCH_QUERY dph_total<=$VAST_MAX_HOURLY_USD"

echo "[vastai-dispatch] searching offers: $SEARCH_QUERY"
SEARCH_RESP="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-offers.json"

set +e
vastai search offers --raw "$SEARCH_QUERY" -o 'dph_total' > "$SEARCH_RESP"
RC=$?
set -e

if (( RC != 0 )); then
  echo "FATAL: vastai search offers failed; see $SEARCH_RESP" >&2
  exit 75
fi

OFFER_ID="$(python3 -c "
import json,sys
data = json.load(open(sys.argv[1]))
if isinstance(data, dict): data = data.get('offers', [])
if not data:
    sys.exit(2)
# Best by dollars/DLperf, then by inet_down
ranked = sorted(data, key=lambda o: (float(o.get('dph_total', 99))/max(float(o.get('dlperf',1)), 1), -float(o.get('inet_down',0))))
print(ranked[0]['id'])
" "$SEARCH_RESP" 2>/dev/null || true)"

if [[ -z "$OFFER_ID" ]]; then
  echo "FATAL: no vast.ai offers matched query: $SEARCH_QUERY" >&2
  exit 76
fi

echo "[vastai-dispatch] selected offer_id=$OFFER_ID"

# ----- onstart-cmd ------------------------------------------------------------
# vast.ai onstart-cmd is the bash payload; gets ~64 KB. Keep tiny: fetch
# boot.sh from staging URL.
#
# vast.ai instances start with the chosen Docker image's CMD; we override with
# --onstart-cmd which is appended to the entrypoint as a shell command.
#
# The instance does NOT have a generic "self-terminate" credential. To self-destroy,
# we pass VASTAI_API_KEY as an env var; boot script's last step is curl DELETE.

ONSTART_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-onstart.sh"

cat > "$ONSTART_FILE" <<ONSTART
#!/usr/bin/env bash
# BioSymphony GeneCluster vast.ai onstart: generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# tool=${TOOL_NAME} run_id=${RUN_ID} timeout=${POD_TIMEOUT_HOURS}h
set -uo pipefail

WORKDIR='${MOUNT_PATH%/}/${TOOL_NAME}/${RUN_ID}'
mkdir -p "\$WORKDIR/logs"
cd "\$WORKDIR"
rm -f SUCCESS FAILURE STATUS *.summary.tsv 2>/dev/null || true

# Fetch boot script + helper (Mozilla UA in case staging is catbox)
python3 -c "
import urllib.request, sys
for url, dest in [(sys.argv[1], 'boot.sh'), (sys.argv[2], 'biosymphony_helper.sh')]:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
        f.write(r.read())
" '${BOOT_URL}' '${HELPER_URL}' 2>>logs/fetch.log
chmod +x boot.sh

export BIOSYMPHONY_TOOL_NAME='${TOOL_NAME}'
export BIOSYMPHONY_RUN_ID='${RUN_ID}'
export BIOSYMPHONY_MOUNT_PATH='${MOUNT_PATH}'
export BIOSYMPHONY_WORKDIR="\$WORKDIR"

bash boot.sh > logs/boot.log 2>&1
RC=\$?
echo "{\"stage\":\"complete\",\"boot_rc\":\$RC,\"ts\":\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > .self_stop_status

# Idle for operator pull, then self-destroy via vast.ai API.
sleep \$((${POD_TIMEOUT_HOURS} * 3600))
INSTANCE_ID=\$(cat /vast.ai-instance-id 2>/dev/null || echo "\$VAST_CONTAINERLABEL")
if [[ -n "\${VASTAI_API_KEY:-}" && -n "\$INSTANCE_ID" ]]; then
  curl -sS -X DELETE -H "Authorization: Bearer \$VASTAI_API_KEY" \\
    "https://console.vast.ai/api/v0/instances/\$INSTANCE_ID/" || true
fi
ONSTART

# ----- vastai create instance -------------------------------------------------

CREATE_RESP="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-create-response.json"

# vastai create instance flags: --image, --disk, --label, --onstart, --env
ENV_FLAGS=(
  -e BIOSYMPHONY_TOOL_NAME="$TOOL_NAME"
  -e BIOSYMPHONY_RUN_ID="$RUN_ID"
  -e BIOSYMPHONY_MOUNT_PATH="$MOUNT_PATH"
  -e VASTAI_API_KEY="${VASTAI_API_KEY:-}"
)

set +e
vastai create instance "$OFFER_ID" \
  --image "$IMAGE" \
  --disk "$VAST_DISK_GB" \
  --label "${TOOL_NAME}-${RUN_ID}" \
  --onstart "$ONSTART_FILE" \
  --raw \
  "${ENV_FLAGS[@]}" \
  > "$CREATE_RESP"
RC=$?
set -e

if (( RC != 0 )); then
  echo "FATAL: vastai create instance exited $RC; see $CREATE_RESP" >&2
  cat "$CREATE_RESP" >&2 || true
  exit 77
fi

INSTANCE_ID="$(python3 -c "
import json,sys
d = json.load(open(sys.argv[1]))
print(d.get('new_contract') or d.get('id') or '')
" "$CREATE_RESP")"

if [[ -z "$INSTANCE_ID" ]]; then
  echo "FATAL: could not parse vast.ai instance id from response" >&2
  cat "$CREATE_RESP" >&2 || true
  exit 78
fi

echo "$INSTANCE_ID" > "$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-instance-id"

MANIFEST_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch.json"
python3 - <<PY > "$MANIFEST_FILE"
import json
print(json.dumps({
  "cloud": "vastai",
  "tool_name": "$TOOL_NAME",
  "run_id": "$RUN_ID",
  "instance_id": "$INSTANCE_ID",
  "offer_id": "$OFFER_ID",
  "image": "$IMAGE",
  "mount_path": "$MOUNT_PATH",
  "use_interruptible": int("$USE_INTERRUPTIBLE"),
  "max_hourly_usd": float("$VAST_MAX_HOURLY_USD"),
  "boot_url": "$BOOT_URL",
  "status_push_mode": "$STATUS_PUSH_MODE",
  "status_push_prefix": "$STATUS_PUSH_PREFIX",
  "monitor_command": "vastai logs $INSTANCE_ID",
  "destroy_command": "vastai destroy instance $INSTANCE_ID",
}, indent=2))
PY

cat <<DONE
[vastai-dispatch] OK
  tool        = $TOOL_NAME
  run_id      = $RUN_ID
  instance_id = $INSTANCE_ID
  offer_id    = $OFFER_ID
  image       = $IMAGE
  mount_path  = $MOUNT_PATH
  manifest    = $MANIFEST_FILE
  status_push = $STATUS_PUSH_MODE -> $STATUS_PUSH_PREFIX

Monitor (vast.ai logs streaming):
  vastai logs $INSTANCE_ID

Show instance status:
  vastai show instance $INSTANCE_ID

Destroy (no preserve, vast.ai has no native stop/hibernate):
  vastai destroy instance $INSTANCE_ID
DONE
