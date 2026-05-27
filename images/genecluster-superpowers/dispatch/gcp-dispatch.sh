#!/usr/bin/env bash
# BioSymphony GeneCluster cloud dispatch template
#
# GCP Compute Engine dispatcher (mirrors the runpod-dispatch.sh contract).
#
# Architecture:
#   1. Upload boot script + helper to GCS:
#        gs://${BIOSYMPHONY_DISPATCH_BUCKET}/<tool>/<run-id>/boot.sh
#        gs://${BIOSYMPHONY_DISPATCH_BUCKET}/<tool>/<run-id>/helper.sh
#   2. `gcloud compute instances create` with --metadata-from-file
#      startup-script=<wrapper>. Wrapper fetches boot.sh from GCS and execs.
#      Persistent disk substitutes for RunPod's networkVolume; for shared
#      multi-instance state, swap to Filestore (mount NFS).
#   3. Tag instance with labels: tool=<tool>, biosymphony-run-id=<run_id>, project=biosymphony.
#   4. Boot script self-uploads STATUS sentinels back to GCS every 30s.
#   5. Self-delete via `gcloud compute instances delete` from boot script
#      using the attached service account (see required roles below).
#
# Required service account roles (attached to instance via --service-account):
#   roles/storage.objectAdmin                    (read boot, write status/artifacts)
#   roles/compute.instanceAdmin.v1               (self-delete)
# Recommended: create dedicated SA `biosymphony-dispatch@<project>.iam.gserviceaccount.com`
# and grant only `storage.objectAdmin` on the bucket + `compute.instanceAdmin`
# scoped via instance label condition on `project=biosymphony`.
#
# Filestore alternative (for genuine networkVolume parity):
#   --metadata=filestore-target=<nfs-ip>:/<share> and the wrapper mounts it.
#   Filestore is ~$0.20/GB-month: pricier than persistent disk but mountable
#   from many instances simultaneously, like RunPod's networkVolume.
#
# Cost model (us-central1, 2026-05 indicative on-demand):
#   e2-standard-2  (2 vCPU /  8 GB):  ~$0.067/h
#   e2-standard-4  (4 vCPU / 16 GB):  ~$0.134/h
#   n2-standard-8  (8 vCPU / 32 GB):  ~$0.388/h
#   g2-standard-4  (4 vCPU / 16 GB / 1xL4): ~$0.71/h
#   pd-balanced disk: ~$0.10/GB-month
#   Filestore (BASIC_HDD, 1 TiB minimum): ~$0.20/GB-month
#   Spot (preemptible) is typically 60-91% cheaper.
#
# Args (parallel to runpod-dispatch.sh):
#   $1 TOOL_NAME
#   $2 IMAGE                container image (Container-Optimized OS path) or
#                           empty string to run boot.sh on a stock GCE image.
#   $3 BOOT_SCRIPT_PATH
#   $4 MOUNT_PATH           default /workspace
#
# Env (required):
#   GOOGLE_CLOUD_PROJECT or CLOUDSDK_CORE_PROJECT
#   BIOSYMPHONY_DISPATCH_BUCKET
#
# Env (optional):
#   GCP_REGION              default us-central1
#   GCP_ZONE                default us-central1-a
#   RUN_ID                  default $(date -u +%Y%m%d-%H%M%S)
#   MACHINE_TYPE            default e2-standard-2 (CPU); set g2-standard-4 GPU
#   IMAGE_FAMILY            default debian-12 (latest LTS); use cos-stable
#                           for container-on-COS path, deeplearning-platform
#                           images for GPU
#   IMAGE_PROJECT           default debian-cloud
#   USE_SPOT                default 0; set 1 for preemptible
#   DISK_GB                 default 100
#   SERVICE_ACCOUNT         default biosymphony-dispatch@<project>.iam.gserviceaccount.com
#   NETWORK                 default 'default'
#   POD_TIMEOUT_HOURS       informational
#   DISPATCH_OUT_DIR        default $(dirname BOOT_SCRIPT_PATH)/.gcp-dispatch
#
# Outputs (DISPATCH_OUT_DIR):
#   <tool>-<run_id>-instance-name        single-line VM name
#   <tool>-<run_id>-launch.json          manifest with monitor GCS URLs
#   <tool>-<run_id>-create-response.json raw create response
#
# TODO: support GKE Autopilot for tool-as-job-with-PV pattern; this template
# is plain Compute Engine VM.

set -euo pipefail

# ----- args + env -------------------------------------------------------------

TOOL_NAME="${1:-}"
IMAGE="${2:-}"
BOOT_SCRIPT_PATH="${3:-}"
MOUNT_PATH="${4:-/workspace}"

if [[ -z "$TOOL_NAME" || -z "$BOOT_SCRIPT_PATH" ]]; then
  cat >&2 <<USAGE
usage: $0 <tool_name> [container_image_or_empty] <boot_script_path> [mount_path]

required env:
  GOOGLE_CLOUD_PROJECT  (or CLOUDSDK_CORE_PROJECT)
  BIOSYMPHONY_DISPATCH_BUCKET

example (CPU on-demand):
  RUN_ID=<run-id> \\
  GOOGLE_CLOUD_PROJECT=biosymphony-prod \\
  BIOSYMPHONY_DISPATCH_BUCKET=<your-dispatch-bucket> \\
  $0 cblaster "" /path/to/cblaster-boot.sh /workspace

example (GPU spot, container):
  USE_SPOT=1 MACHINE_TYPE=g2-standard-4 \\
  IMAGE_FAMILY=common-cu123-debian-11-py310 IMAGE_PROJECT=deeplearning-platform-release \\
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

# Resolve project
GCP_PROJECT="${GOOGLE_CLOUD_PROJECT:-${CLOUDSDK_CORE_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}}"
: "${GCP_PROJECT:?GOOGLE_CLOUD_PROJECT or gcloud config project required}"

: "${BIOSYMPHONY_DISPATCH_BUCKET:?BIOSYMPHONY_DISPATCH_BUCKET required}"
command -v gcloud  >/dev/null 2>&1 || { echo "FATAL: gcloud CLI not found"; exit 67; }
command -v gsutil  >/dev/null 2>&1 || { echo "FATAL: gsutil not found"; exit 67; }

GCP_REGION="${GCP_REGION:-us-central1}"
GCP_ZONE="${GCP_ZONE:-us-central1-a}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-2}"
IMAGE_FAMILY="${IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${IMAGE_PROJECT:-debian-cloud}"
USE_SPOT="${USE_SPOT:-0}"
DISK_GB="${DISK_GB:-100}"
NETWORK="${NETWORK:-default}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-biosymphony-dispatch@${GCP_PROJECT}.iam.gserviceaccount.com}"
POD_TIMEOUT_HOURS="${POD_TIMEOUT_HOURS:-4}"
DISPATCH_OUT_DIR="${DISPATCH_OUT_DIR:-$(dirname "$BOOT_SCRIPT_PATH")/.gcp-dispatch}"
mkdir -p "$DISPATCH_OUT_DIR"

if [[ ! "$TOOL_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "FATAL: TOOL_NAME must be alnum/_/-: $TOOL_NAME" >&2
  exit 64
fi

# GCE instance names: lowercase, alnum/dash, max 63 chars.
INSTANCE_NAME="${TOOL_NAME//_/-}-${RUN_ID//_/-}"
INSTANCE_NAME="$(echo "$INSTANCE_NAME" | tr '[:upper:]' '[:lower:]' | cut -c1-63)"

# ----- Mozilla-UA download helper (same contract as RunPod) -------------------
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

# ----- GCS staging ------------------------------------------------------------
GCS_PREFIX="gs://${BIOSYMPHONY_DISPATCH_BUCKET}/${TOOL_NAME}/${RUN_ID}"

# Verify bucket reachable
gsutil ls "gs://${BIOSYMPHONY_DISPATCH_BUCKET}" >/dev/null 2>&1 \
  || { echo "FATAL: gs://${BIOSYMPHONY_DISPATCH_BUCKET} not reachable. Create it: gsutil mb -p $GCP_PROJECT -l $GCP_REGION gs://${BIOSYMPHONY_DISPATCH_BUCKET}" >&2; exit 74; }

HELPER_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-helper.sh"
printf '%s\n' "$DOWNLOAD_HELPER" > "$HELPER_FILE"

gsutil -q cp "$BOOT_SCRIPT_PATH" "$GCS_PREFIX/boot.sh"
gsutil -q cp "$HELPER_FILE"      "$GCS_PREFIX/helper.sh"

# ----- startup-script wrapper -------------------------------------------------
# GCE startup-script size limit is 256 KB raw: much more generous than EC2's
# 16 KB user-data, so we don't need to be as aggressive about offloading logic.
# But for parity with RunPod/AWS we keep this wrapper tiny and the real work
# in boot.sh on GCS.

WRAPPER_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-startup-script.sh"

cat > "$WRAPPER_FILE" <<WRAPPER
#!/usr/bin/env bash
# BioSymphony GeneCluster GCP startup-script: generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# tool=${TOOL_NAME} run_id=${RUN_ID} timeout=${POD_TIMEOUT_HOURS}h
set -uo pipefail

TOOL='${TOOL_NAME}'
RUN_ID='${RUN_ID}'
MOUNT='${MOUNT_PATH}'
GCS_PREFIX='${GCS_PREFIX}'
IMAGE='${IMAGE}'
WORKDIR="\${MOUNT}/\${TOOL}/\${RUN_ID}"

# Install gsutil if missing (Debian images ship gcloud SDK in /snap or via apt).
command -v gsutil >/dev/null 2>&1 || {
  curl -sS https://sdk.cloud.google.com | bash >/tmp/gcloud-install.log 2>&1
  source /root/google-cloud-sdk/path.bash.inc 2>/dev/null || true
}

mkdir -p "\$MOUNT"
# Mount the additional persistent disk attached at /dev/sdb (--create-disk=device-name=workspace)
DEV=/dev/disk/by-id/google-workspace
if [[ -b "\$DEV" ]]; then
  if ! blkid "\$DEV" >/dev/null 2>&1; then
    mkfs.ext4 -F "\$DEV"
  fi
  mount "\$DEV" "\$MOUNT" || true
fi

mkdir -p "\$WORKDIR/logs"
cd "\$WORKDIR"
rm -f SUCCESS FAILURE STATUS *.summary.tsv 2>/dev/null || true

# Sidecar: stream STATUS to GCS every 30s.
(
  while true; do
    if [[ -f STATUS  ]]; then gsutil -q cp STATUS  "\$GCS_PREFIX/status/STATUS"  2>/dev/null || true; fi
    if [[ -f SUCCESS ]]; then gsutil -q cp SUCCESS "\$GCS_PREFIX/status/SUCCESS" 2>/dev/null || true; fi
    if [[ -f FAILURE ]]; then gsutil -q cp FAILURE "\$GCS_PREFIX/status/FAILURE" 2>/dev/null || true; fi
    sleep 30
  done
) &
SIDECAR_PID=\$!

gsutil -q cp "\$GCS_PREFIX/boot.sh"   ./boot.sh
gsutil -q cp "\$GCS_PREFIX/helper.sh" ./biosymphony_helper.sh
chmod +x boot.sh

export BIOSYMPHONY_TOOL_NAME="\$TOOL"
export BIOSYMPHONY_RUN_ID="\$RUN_ID"
export BIOSYMPHONY_MOUNT_PATH="\$MOUNT"
export BIOSYMPHONY_WORKDIR="\$WORKDIR"
export BIOSYMPHONY_GCS_PREFIX="\$GCS_PREFIX"

if [[ -n "\$IMAGE" ]]; then
  command -v docker >/dev/null 2>&1 || {
    apt-get update && apt-get install -y docker.io || true
    systemctl start docker || true
  }
  docker pull "\$IMAGE"
  docker run --rm \\
    -v "\$WORKDIR":/work \\
    -e BIOSYMPHONY_TOOL_NAME -e BIOSYMPHONY_RUN_ID -e BIOSYMPHONY_MOUNT_PATH -e BIOSYMPHONY_WORKDIR -e BIOSYMPHONY_GCS_PREFIX \\
    -w /work \\
    "\$IMAGE" \\
    bash boot.sh > logs/boot.log 2>&1
  RC=\$?
else
  bash boot.sh > logs/boot.log 2>&1
  RC=\$?
fi

# Final flush
gsutil -q cp logs/boot.log "\$GCS_PREFIX/logs/boot.log" 2>/dev/null || true
gsutil -q -m rsync -r -x '^(boot\.sh|biosymphony_helper\.sh)\$' . "\$GCS_PREFIX/artifacts/" 2>/dev/null || true
echo "{\"stage\":\"complete\",\"boot_rc\":\$RC,\"ts\":\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > .self_stop_status
gsutil -q cp .self_stop_status "\$GCS_PREFIX/status/.self_stop_status" 2>/dev/null || true

# Idle window for operator inspection, then self-delete.
sleep \$((${POD_TIMEOUT_HOURS} * 3600))
NAME=\$(curl -sS -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
ZONE=\$(curl -sS -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | sed 's|.*/||')
gcloud compute instances delete "\$NAME" --zone "\$ZONE" --quiet
WRAPPER

# Stage wrapper to GCS for audit
gsutil -q cp "$WRAPPER_FILE" "$GCS_PREFIX/startup-script.sh"

# ----- gcloud compute instances create ----------------------------------------

EXTRA_ARGS=()

if [[ "$USE_SPOT" == "1" ]]; then
  EXTRA_ARGS+=(--provisioning-model=SPOT --instance-termination-action=DELETE)
fi

# GPU detection: if MACHINE_TYPE starts with g2/n1+nvidia/a2/a3, attach accelerators.
case "$MACHINE_TYPE" in
  g2-*) EXTRA_ARGS+=(--accelerator="count=1,type=nvidia-l4") ;;
  a2-* | a3-*) : ;;  # GPU baked into accelerator-optimized machine families
  n1-*) : ;;          # User must pass --accelerator manually if needed; TODO
esac

CREATE_RESP="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-create-response.json"

set +e
gcloud compute instances create "$INSTANCE_NAME" \
  --project="$GCP_PROJECT" \
  --zone="$GCP_ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --network="$NETWORK" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --boot-disk-size=50GB \
  --create-disk="name=${INSTANCE_NAME}-workspace,size=${DISK_GB}GB,type=pd-balanced,device-name=workspace,auto-delete=yes" \
  --service-account="$SERVICE_ACCOUNT" \
  --scopes="https://www.googleapis.com/auth/cloud-platform" \
  --labels="tool=${TOOL_NAME//_/-},biosymphony-run-id=${RUN_ID//_/-},project=biosymphony" \
  --metadata-from-file="startup-script=$WRAPPER_FILE" \
  --format=json \
  "${EXTRA_ARGS[@]}" \
  > "$CREATE_RESP"
RC=$?
set -e

if (( RC != 0 )); then
  echo "FATAL: gcloud compute instances create exited $RC; see $CREATE_RESP" >&2
  cat "$CREATE_RESP" >&2 || true
  exit 75
fi

echo "$INSTANCE_NAME" > "$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-instance-name"

MANIFEST_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch.json"
python3 - <<PY > "$MANIFEST_FILE"
import json
print(json.dumps({
  "cloud": "gcp",
  "tool_name": "$TOOL_NAME",
  "run_id": "$RUN_ID",
  "instance_name": "$INSTANCE_NAME",
  "machine_type": "$MACHINE_TYPE",
  "image_family": "$IMAGE_FAMILY",
  "project": "$GCP_PROJECT",
  "zone": "$GCP_ZONE",
  "image": "$IMAGE",
  "mount_path": "$MOUNT_PATH",
  "use_spot": int("$USE_SPOT"),
  "disk_gb": int("$DISK_GB"),
  "gcs_prefix": "$GCS_PREFIX",
  "monitor_status_url":  "$GCS_PREFIX/status/STATUS",
  "monitor_success_url": "$GCS_PREFIX/status/SUCCESS",
  "monitor_failure_url": "$GCS_PREFIX/status/FAILURE",
  "monitor_logs_url":    "$GCS_PREFIX/logs/boot.log",
  "stop_command":   "gcloud compute instances stop $INSTANCE_NAME --zone $GCP_ZONE --project $GCP_PROJECT",
  "delete_command": "gcloud compute instances delete $INSTANCE_NAME --zone $GCP_ZONE --project $GCP_PROJECT --quiet",
}, indent=2))
PY

gsutil -q cp "$MANIFEST_FILE" "$GCS_PREFIX/launch.json" 2>/dev/null || true

cat <<DONE
[gcp-dispatch] OK
  tool          = $TOOL_NAME
  run_id        = $RUN_ID
  instance_name = $INSTANCE_NAME
  machine_type  = $MACHINE_TYPE
  image_family  = $IMAGE_FAMILY
  project       = $GCP_PROJECT
  zone          = $GCP_ZONE
  gcs_prefix    = $GCS_PREFIX
  manifest      = $MANIFEST_FILE

Monitor (sentinels via GCS):
  gsutil cat $GCS_PREFIX/status/STATUS
  gsutil ls  $GCS_PREFIX/status/

Tail logs:
  gsutil cat $GCS_PREFIX/logs/boot.log | tail -50

Stop (preserves disk; cheap to resume):
  gcloud compute instances stop $INSTANCE_NAME --zone $GCP_ZONE --project $GCP_PROJECT

Delete (destroys instance + workspace disk if auto-delete=yes):
  gcloud compute instances delete $INSTANCE_NAME --zone $GCP_ZONE --project $GCP_PROJECT --quiet
DONE
