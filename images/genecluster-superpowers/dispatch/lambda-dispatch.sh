#!/usr/bin/env bash
# BioSymphony GeneCluster cloud dispatch template
#
# Lambda Labs Cloud dispatcher (simple GPU; parallel to runpod-dispatch.sh).
#
# Architecture:
#   1. Stage boot.sh + helper.sh to a public-readable URL or S3 bucket.
#      Lambda has no Docker container option: instances are bare Ubuntu VMs
#      with PyTorch/CUDA pre-installed (Deep Learning Stack).
#   2. POST to https://cloud.lambdalabs.com/api/v1/instance-operations/launch
#      with SSH key id + region + instance type. There's no native onstart
#      script, so the dispatcher writes boot.sh into ~/cloud-init.sh after
#      first SSH (auto-handled by Lambda's first-boot hook), or: preferred , 
#      the dispatcher uploads boot.sh and triggers it via SSH.
#   3. SSH to the new instance, copy boot.sh, exec it as a detached process.
#   4. Boot script self-uploads STATUS sentinels to S3 / GCS / external URL.
#   5. Termination is operator-side. Do not pass the Lambda API key into the
#      instance or write it into launch manifests.
#
# Tradeoffs vs RunPod / AWS / GCP / vast.ai:
#   + Simplest pricing and provisioning of any GPU cloud (flat hourly rate,
#     no spot bidding, no offer search).
#   + Pre-installed CUDA + PyTorch + JupyterLab on every instance.
#   - No Docker support natively: pip install your tools, or `apt install
#     docker.io` first thing in boot.sh.
#   - No durable persistent disk; every instance is fresh. Pre-stage to S3.
#   - Capacity is tight; high-end H100s often unavailable.
#   - SSH key must be pre-registered with Lambda (no inline keypair creation).
#
# Args (parallel to runpod-dispatch.sh):
#   $1 TOOL_NAME
#   $2 IMAGE                Lambda has no container concept. Pass empty
#                           string or for documentation: the container we
#                           would run if Lambda supported docker (boot.sh
#                           must apt-install docker if container is needed).
#   $3 BOOT_SCRIPT_PATH
#   $4 MOUNT_PATH           default /workspace
#
# Env (required):
#   LAMBDA_API_KEY                              cloud.lambdalabs.com -> API
#   LAMBDA_SSH_KEY_NAME                         pre-registered key name in Lambda
#   LAMBDA_SSH_PRIVATE_KEY_PATH                 local path to matching private key
#   BIOSYMPHONY_DISPATCH_BUCKET (S3) OR
#     BIOSYMPHONY_STAGING_URL_BASE              external URL host
#
# Env (optional):
#   LAMBDA_INSTANCE_TYPE      default 'gpu_1x_a10'   (cheapest GPU)
#                                                    options: gpu_1x_a10,
#                                                    gpu_1x_a100, gpu_1x_h100,
#                                                    gpu_8x_a100_80gb_sxm4
#   LAMBDA_REGION             default 'us-east-1'    auto-fallback to any
#   RUN_ID                    default $(date -u +%Y%m%d-%H%M%S)
#   POD_TIMEOUT_HOURS         informational
#   DISPATCH_OUT_DIR          default <repo>/.runtime/provider-dispatch/lambda
#   AWS_REGION                default us-east-1 (S3 staging)
#
# Outputs (DISPATCH_OUT_DIR):
#   <tool>-<run_id>-instance-id          single-line Lambda instance id
#   <tool>-<run_id>-launch.json          manifest with monitor URL
#   <tool>-<run_id>-launch-response.json raw API JSON
#
# Cost model (Lambda Labs, 2026-05 indicative: flat on-demand only):
#   gpu_1x_a10  (1xA10 24 GB):           $0.75/h
#   gpu_1x_a100 (1xA100 40 GB):          $1.10/h
#   gpu_1x_h100 (1xH100 80 GB SXM5):     $2.49/h
#   gpu_8x_h100 (8xH100 80 GB SXM5):     $19.88/h
# No spot/preemptible market.
#
# TODO: support Lambda's filesystems API (https://docs.lambdalabs.com/...
# /file-systems/) for durable cross-instance state: currently each instance
# gets fresh local SSD only.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ----- args + env -------------------------------------------------------------

TOOL_NAME="${1:-}"
IMAGE="${2:-}"
BOOT_SCRIPT_PATH="${3:-}"
MOUNT_PATH="${4:-/workspace}"

if [[ -z "$TOOL_NAME" || -z "$BOOT_SCRIPT_PATH" ]]; then
  cat >&2 <<USAGE
usage: $0 <tool_name> [image_doc_only] <boot_script_path> [mount_path]

required env:
  LAMBDA_API_KEY
  LAMBDA_SSH_KEY_NAME              (pre-registered with Lambda)
  LAMBDA_SSH_PRIVATE_KEY_PATH      (local path)
  BIOSYMPHONY_DISPATCH_BUCKET (for S3 staging) OR BIOSYMPHONY_STAGING_URL_BASE

example (single A10):
  LAMBDA_INSTANCE_TYPE=gpu_1x_a10 \\
  RUN_ID=<run-id> \\
  $0 clean "" /path/to/clean-boot.sh /workspace

example (H100):
  LAMBDA_INSTANCE_TYPE=gpu_1x_h100 \\
  RUN_ID=<run-id> \\
  $0 prostt5 "" /path/to/prostt5-boot.sh /workspace
USAGE
  exit 64
fi

if [[ ! -f "$BOOT_SCRIPT_PATH" ]]; then
  echo "FATAL: boot script not found: $BOOT_SCRIPT_PATH" >&2
  exit 66
fi

: "${LAMBDA_API_KEY:?LAMBDA_API_KEY required}"
: "${LAMBDA_SSH_KEY_NAME:?LAMBDA_SSH_KEY_NAME required (pre-registered key name)}"
: "${LAMBDA_SSH_PRIVATE_KEY_PATH:?LAMBDA_SSH_PRIVATE_KEY_PATH required}"

if [[ ! -f "$LAMBDA_SSH_PRIVATE_KEY_PATH" ]]; then
  echo "FATAL: SSH private key not found: $LAMBDA_SSH_PRIVATE_KEY_PATH" >&2
  exit 67
fi

LAMBDA_INSTANCE_TYPE="${LAMBDA_INSTANCE_TYPE:-gpu_1x_a10}"
LAMBDA_REGION="${LAMBDA_REGION:-us-east-1}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
POD_TIMEOUT_HOURS="${POD_TIMEOUT_HOURS:-4}"
DISPATCH_OUT_DIR="${DISPATCH_OUT_DIR:-${SCRIPT_DIR}/../../../.runtime/provider-dispatch/lambda}"
mkdir -p "$DISPATCH_OUT_DIR"
AWS_REGION="${AWS_REGION:-us-east-1}"

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

# ----- Stage boot script ------------------------------------------------------
HELPER_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-helper.sh"
printf '%s\n' "$DOWNLOAD_HELPER" > "$HELPER_FILE"

if [[ -n "${BIOSYMPHONY_DISPATCH_BUCKET:-}" ]]; then
  command -v aws >/dev/null 2>&1 || { echo "FATAL: aws CLI required for S3 staging"; exit 67; }
  S3_PREFIX="s3://${BIOSYMPHONY_DISPATCH_BUCKET}/${TOOL_NAME}/${RUN_ID}"
  aws s3 cp "$BOOT_SCRIPT_PATH" "$S3_PREFIX/boot.sh"   --region "$AWS_REGION" --quiet
  aws s3 cp "$HELPER_FILE"      "$S3_PREFIX/helper.sh" --region "$AWS_REGION" --quiet
  BOOT_URL="$(aws s3 presign "$S3_PREFIX/boot.sh"   --region "$AWS_REGION" --expires-in 43200)"
  HELPER_URL="$(aws s3 presign "$S3_PREFIX/helper.sh" --region "$AWS_REGION" --expires-in 43200)"
  STATUS_PUSH_PREFIX="$S3_PREFIX/status"
  STATUS_PUSH_MODE="s3"
elif [[ -n "${BIOSYMPHONY_STAGING_URL_BASE:-}" ]]; then
  BOOT_URL="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/boot.sh"
  HELPER_URL="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/helper.sh"
  STATUS_PUSH_PREFIX="${BIOSYMPHONY_STAGING_URL_BASE%/}/${TOOL_NAME}/${RUN_ID}/status"
  STATUS_PUSH_MODE="manual"
  echo "WARN: manual staging, upload boot.sh + helper.sh to:"
  echo "  $BOOT_URL"
  echo "  $HELPER_URL"
else
  echo "FATAL: set BIOSYMPHONY_DISPATCH_BUCKET (S3) or BIOSYMPHONY_STAGING_URL_BASE (manual)" >&2
  exit 64
fi

# ----- Lambda Labs API: launch instance ---------------------------------------

PAYLOAD_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-payload.json"

python3 - <<PY > "$PAYLOAD_FILE"
import json, os
print(json.dumps({
  "region_name": os.environ["LAMBDA_REGION"],
  "instance_type_name": os.environ["LAMBDA_INSTANCE_TYPE"],
  "ssh_key_names": [os.environ["LAMBDA_SSH_KEY_NAME"]],
  "name": f"{os.environ['TOOL_NAME']}-{os.environ['RUN_ID']}",
  "quantity": 1,
}, indent=2))
PY

export LAMBDA_REGION LAMBDA_INSTANCE_TYPE LAMBDA_SSH_KEY_NAME TOOL_NAME RUN_ID

LAUNCH_RESP="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch-response.json"
LAMBDA_AUTH_HEADER=$(printf '%s:' "$LAMBDA_API_KEY" | base64 | tr -d '\n')

set +e
HTTP_CODE=$(curl -sS \
  -o "$LAUNCH_RESP" -w "%{http_code}" \
  -X POST "https://cloud.lambdalabs.com/api/v1/instance-operations/launch" \
  -H "Authorization: Basic $LAMBDA_AUTH_HEADER" \
  -H "Content-Type: application/json" \
  --data-binary @"$PAYLOAD_FILE")
CURL_RC=$?
set -e

if (( CURL_RC != 0 )); then
  echo "FATAL: curl exited $CURL_RC posting to Lambda" >&2
  exit 70
fi

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "FATAL: Lambda launch returned HTTP $HTTP_CODE" >&2
  cat "$LAUNCH_RESP" >&2 || true
  echo "" >&2
  echo "Common causes:" >&2
  echo "  - $LAMBDA_INSTANCE_TYPE not available in $LAMBDA_REGION (capacity)" >&2
  echo "  - SSH key '$LAMBDA_SSH_KEY_NAME' not registered" >&2
  echo "  - billing not configured" >&2
  exit 71
fi

INSTANCE_ID="$(python3 -c "
import json,sys
d = json.load(open(sys.argv[1]))
ids = d.get('data', {}).get('instance_ids') or d.get('instance_ids') or []
if not ids:
    sys.exit(1)
print(ids[0])
" "$LAUNCH_RESP")"

if [[ -z "$INSTANCE_ID" ]]; then
  echo "FATAL: could not parse Lambda instance id from response" >&2
  cat "$LAUNCH_RESP" >&2 || true
  exit 72
fi

echo "$INSTANCE_ID" > "$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-instance-id"

echo "[lambda-dispatch] launched instance_id=$INSTANCE_ID; polling for IP..."

# Poll for IP: Lambda usually takes 1-3 min before SSH is reachable.
INSTANCE_IP=""
for i in $(seq 1 60); do
  set +e
  STATUS_RESP=$(curl -sS \
    -X GET "https://cloud.lambdalabs.com/api/v1/instances/${INSTANCE_ID}" \
    -H "Authorization: Basic $LAMBDA_AUTH_HEADER")
  set -e
  INSTANCE_IP=$(python3 -c "
import json,sys
d = json.loads(sys.argv[1])
print(d.get('data', {}).get('ip', '') or d.get('ip',''))
" "$STATUS_RESP" 2>/dev/null || true)
  if [[ -n "$INSTANCE_IP" && "$INSTANCE_IP" != "None" ]]; then
    break
  fi
  sleep 10
done

if [[ -z "$INSTANCE_IP" || "$INSTANCE_IP" == "None" ]]; then
  echo "WARN: instance launched but no IP yet after 10 min, operator must SSH manually" >&2
fi

# ----- SSH onstart payload ----------------------------------------------------
# Push boot.sh fetcher + executor as a one-liner over SSH.

SSH_CMD="set -uo pipefail
mkdir -p ${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}/logs
cd ${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}
rm -f SUCCESS FAILURE STATUS *.summary.tsv 2>/dev/null || true
python3 -c \"
import urllib.request, sys
for url, dest in [(sys.argv[1], 'boot.sh'), (sys.argv[2], 'biosymphony_helper.sh')]:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
        f.write(r.read())
\" '${BOOT_URL}' '${HELPER_URL}'
chmod +x boot.sh
	export BIOSYMPHONY_TOOL_NAME='${TOOL_NAME}' BIOSYMPHONY_RUN_ID='${RUN_ID}' BIOSYMPHONY_MOUNT_PATH='${MOUNT_PATH}' BIOSYMPHONY_WORKDIR='${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}' LAMBDA_INSTANCE_ID='${INSTANCE_ID}'
	nohup bash -c 'bash boot.sh > logs/boot.log 2>&1; RC=\$?; echo \"{\\\"stage\\\":\\\"complete\\\",\\\"boot_rc\\\":\$RC}\" > .self_stop_status; sleep ${POD_TIMEOUT_HOURS}h' >/dev/null 2>&1 &
disown
echo phase=launched ts=\$(date -u +%s) > STATUS"

if [[ -n "$INSTANCE_IP" && "$INSTANCE_IP" != "None" ]]; then
  echo "[lambda-dispatch] SSHing to ubuntu@$INSTANCE_IP to start boot.sh"
  set +e
  ssh -i "$LAMBDA_SSH_PRIVATE_KEY_PATH" \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=15 \
    -o BatchMode=yes \
    "ubuntu@$INSTANCE_IP" \
    "$SSH_CMD"
  SSH_RC=$?
  set -e
  if (( SSH_RC != 0 )); then
    echo "WARN: SSH dispatch failed (rc=$SSH_RC); operator must SSH and run boot manually." >&2
    echo "  ssh -i $LAMBDA_SSH_PRIVATE_KEY_PATH ubuntu@$INSTANCE_IP" >&2
  fi
else
  echo "WARN: skipping SSH dispatch, no IP yet."
fi

# ----- manifest ---------------------------------------------------------------
MANIFEST_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch.json"
python3 - <<PY > "$MANIFEST_FILE"
import json
print(json.dumps({
  "cloud": "lambda",
  "tool_name": "$TOOL_NAME",
  "run_id": "$RUN_ID",
  "instance_id": "$INSTANCE_ID",
  "instance_ip": "$INSTANCE_IP",
  "instance_type": "$LAMBDA_INSTANCE_TYPE",
  "region": "$LAMBDA_REGION",
  "image": "$IMAGE",
  "mount_path": "$MOUNT_PATH",
  "boot_url": "$BOOT_URL",
  "status_push_mode": "$STATUS_PUSH_MODE",
  "status_push_prefix": "$STATUS_PUSH_PREFIX",
  "ssh_command": "ssh -i <ssh-private-key> ubuntu@$INSTANCE_IP",
  "monitor_command": "ssh -i <ssh-private-key> ubuntu@$INSTANCE_IP cat ${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}/STATUS",
  "terminate_command": "operator-side: set LAMBDA_AUTH_HEADER from LAMBDA_API_KEY, then curl -sS -X POST -H 'Authorization: Basic $LAMBDA_AUTH_HEADER' -H 'Content-Type: application/json' -d '{\"instance_ids\":[\"$INSTANCE_ID\"]}' https://cloud.lambdalabs.com/api/v1/instance-operations/terminate",
}, indent=2))
PY

cat <<DONE
[lambda-dispatch] OK
  tool          = $TOOL_NAME
  run_id        = $RUN_ID
  instance_id   = $INSTANCE_ID
  instance_ip   = ${INSTANCE_IP:-pending}
  instance_type = $LAMBDA_INSTANCE_TYPE
  region        = $LAMBDA_REGION
  manifest      = $MANIFEST_FILE
  status_push   = $STATUS_PUSH_MODE -> $STATUS_PUSH_PREFIX

Monitor (over SSH):
  ssh -i $LAMBDA_SSH_PRIVATE_KEY_PATH ubuntu@${INSTANCE_IP:-PENDING} \\
    "cat ${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}/STATUS"

Tail logs:
  ssh -i $LAMBDA_SSH_PRIVATE_KEY_PATH ubuntu@${INSTANCE_IP:-PENDING} \\
    "tail -f ${MOUNT_PATH}/${TOOL_NAME}/${RUN_ID}/logs/boot.log"

Terminate (no preserve, Lambda has no stop/hibernate):
  curl -sS -X POST \\
    -H "Authorization: Basic $LAMBDA_AUTH_HEADER" \\
    -H 'Content-Type: application/json' \\
    -d '{"instance_ids":["$INSTANCE_ID"]}' \\
    https://cloud.lambdalabs.com/api/v1/instance-operations/terminate
DONE
