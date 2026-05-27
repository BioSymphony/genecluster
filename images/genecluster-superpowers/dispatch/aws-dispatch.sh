#!/usr/bin/env bash
# BioSymphony GeneCluster cloud dispatch template
#
# AWS EC2 dispatcher (mirrors the runpod-dispatch.sh contract).
#
# Architecture:
#   1. Upload boot script + a tiny user-data wrapper to S3:
#        s3://${BIOSYMPHONY_DISPATCH_BUCKET}/<tool>/<run-id>/boot.sh
#        s3://${BIOSYMPHONY_DISPATCH_BUCKET}/<tool>/<run-id>/user-data.sh
#   2. `aws ec2 run-instances` with --user-data fetching boot.sh from S3 and
#      executing it. EBS volume substitutes for RunPod's networkVolume.
#   3. Tag instance: tool=<tool>, biosymphony-run-id=<run_id>, project=biosymphony.
#   4. Boot script self-uploads STATUS sentinels back to S3 every 30s so
#      monitors poll s3:// URLs (parallel to RunPod's pod-proxy http server).
#   5. Self-terminate via `aws ec2 terminate-instances` from the boot script
#      using the instance's IAM role (see required policy below).
#
# Required IAM role attached to the instance profile (<DispatchRole>):
#   {
#     "Version": "2012-10-17",
#     "Statement": [
#       { "Effect": "Allow",
#         "Action": ["s3:GetObject","s3:PutObject","s3:ListBucket"],
#         "Resource": [
#           "arn:aws:s3:::<your-dispatch-bucket>",
#           "arn:aws:s3:::<your-dispatch-bucket>/*"
#         ]},
#       { "Effect": "Allow",
#         "Action": ["ec2:TerminateInstances","ec2:DescribeInstances"],
#         "Resource": "*",
#         "Condition": { "StringEquals": { "ec2:ResourceTag/project": "biosymphony" }}}
#     ]
#   }
#   The Condition restricts self-terminate to instances we tagged ourselves , 
#   protects sibling EC2 workloads in the same account.
#
# Suggested S3 layout (bucket: <your-dispatch-bucket>):
#   <tool>/<run-id>/boot.sh                          (uploaded by this script)
#   <tool>/<run-id>/user-data.sh                     (uploaded by this script)
#   <tool>/<run-id>/launch.json                      (uploaded by this script)
#   <tool>/<run-id>/status/STATUS                    (boot script -> here)
#   <tool>/<run-id>/status/SUCCESS                   (boot script -> here)
#   <tool>/<run-id>/status/FAILURE                   (boot script -> here)
#   <tool>/<run-id>/logs/boot.log                    (boot script -> here)
#   <tool>/<run-id>/artifacts/<tool>.summary.tsv     (final deliverables)
#
# Cost model (us-east-1, 2026-05 indicative on-demand):
#   m6a.large   (2 vCPU /  8 GB):  ~$0.086/h
#   m6a.xlarge  (4 vCPU / 16 GB):  ~$0.172/h
#   m6a.2xlarge (8 vCPU / 32 GB):  ~$0.346/h
#   g5.xlarge   (4 vCPU / 16 GB / 1xA10G): ~$1.006/h
#   gp3 EBS:    ~$0.08/GB-month
#   Spot is typically 30-70% cheaper but can be reclaimed mid-job.
#
# Args (parallel to runpod-dispatch.sh):
#   $1 TOOL_NAME
#   $2 IMAGE                ignored on AWS (instances run an AMI, not a
#                           container, by default). For container parity, the
#                           AMI's user-data wrapper does `docker run <IMAGE>`.
#                           Pass an empty string "" to run boot.sh on bare AMI.
#   $3 BOOT_SCRIPT_PATH
#   $4 MOUNT_PATH           default /workspace; mountpoint for the EBS volume
#
# Env (required):
#   AWS_PROFILE                       (or AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY)
#   BIOSYMPHONY_DISPATCH_BUCKET       e.g. <your-dispatch-bucket>
#
# Env (optional):
#   AWS_REGION              default us-east-1
#   RUN_ID                  default $(date -u +%Y%m%d-%H%M%S)
#   INSTANCE_TYPE           default m6a.large (CPU); set g5.xlarge for GPU
#   AMI_ID                  default = latest Amazon Linux 2023 in region;
#                           use Deep Learning AMI (Ubuntu) for GPU
#   USE_SPOT                default 0; set 1 to request spot
#   IAM_INSTANCE_PROFILE    default <DispatchRole>
#   EBS_GB                  default 100
#   KEY_NAME                optional; SSH keypair name (omit for SSM-only access)
#   SECURITY_GROUP_IDS      comma-separated; default = look up sg by tag
#                           Name=biosymphony-dispatch-sg
#   SUBNET_ID               default = first default-VPC subnet in region
#   POD_TIMEOUT_HOURS       informational; written into user-data banner
#   DISPATCH_OUT_DIR        default $(dirname BOOT_SCRIPT_PATH)/.aws-dispatch
#
# Outputs (DISPATCH_OUT_DIR):
#   <tool>-<run_id>-instance-id          single-line instance id
#   <tool>-<run_id>-launch.json          manifest with monitor S3 URLs
#   <tool>-<run_id>-run-instances.json   raw run-instances response
#
# TODO: support Capacity Reservations + Reserved Instances for predictable
# pricing on long-running campaigns. For now this template is on-demand or spot.

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
  AWS_PROFILE  (or AWS creds)
  BIOSYMPHONY_DISPATCH_BUCKET

example (CPU on-demand):
  RUN_ID=<run-id> \\
  BIOSYMPHONY_DISPATCH_BUCKET=<your-dispatch-bucket> \\
  $0 cblaster "" /path/to/cblaster-boot.sh /workspace

example (GPU spot, container):
  USE_SPOT=1 INSTANCE_TYPE=g5.xlarge AMI_ID=ami-deep-learning-... \\
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

: "${BIOSYMPHONY_DISPATCH_BUCKET:?BIOSYMPHONY_DISPATCH_BUCKET required (e.g. <your-dispatch-bucket>)}"
command -v aws >/dev/null 2>&1 || { echo "FATAL: aws CLI not found"; exit 67; }

AWS_REGION="${AWS_REGION:-us-east-1}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d-%H%M%S)}"
INSTANCE_TYPE="${INSTANCE_TYPE:-m6a.large}"
USE_SPOT="${USE_SPOT:-0}"
IAM_INSTANCE_PROFILE="${IAM_INSTANCE_PROFILE:-<DispatchRole>}"
EBS_GB="${EBS_GB:-100}"
POD_TIMEOUT_HOURS="${POD_TIMEOUT_HOURS:-4}"
DISPATCH_OUT_DIR="${DISPATCH_OUT_DIR:-$(dirname "$BOOT_SCRIPT_PATH")/.aws-dispatch}"
mkdir -p "$DISPATCH_OUT_DIR"

if [[ ! "$TOOL_NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo "FATAL: TOOL_NAME must be alnum/_/-: $TOOL_NAME" >&2
  exit 64
fi

# ----- Mozilla-UA download helper (for boot scripts; mirrors runpod) ----------
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

# ----- AMI default ------------------------------------------------------------
# Resolve latest Amazon Linux 2023 if AMI_ID not provided.
if [[ -z "${AMI_ID:-}" ]]; then
  AMI_ID="$(aws ssm get-parameter \
    --region "$AWS_REGION" \
    --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
    --query 'Parameter.Value' --output text 2>/dev/null || true)"
  if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
    echo "WARN: could not resolve default AL2023 AMI; set AMI_ID explicitly." >&2
    # Fallback to a hardcoded recent us-east-1 AL2023; user should override.
    AMI_ID="ami-0c1ac8a41498c1a9c"  # TODO: refresh hardcoded fallback periodically
  fi
fi

# ----- Subnet + SG defaults ---------------------------------------------------
if [[ -z "${SUBNET_ID:-}" ]]; then
  SUBNET_ID="$(aws ec2 describe-subnets \
    --region "$AWS_REGION" \
    --filters Name=default-for-az,Values=true \
    --query 'Subnets[0].SubnetId' --output text 2>/dev/null || true)"
  if [[ -z "$SUBNET_ID" || "$SUBNET_ID" == "None" ]]; then
    echo "FATAL: could not resolve default subnet; set SUBNET_ID." >&2
    exit 73
  fi
fi

if [[ -z "${SECURITY_GROUP_IDS:-}" ]]; then
  SECURITY_GROUP_IDS="$(aws ec2 describe-security-groups \
    --region "$AWS_REGION" \
    --filters Name=tag:Name,Values=biosymphony-dispatch-sg \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
  if [[ -z "$SECURITY_GROUP_IDS" || "$SECURITY_GROUP_IDS" == "None" ]]; then
    echo "WARN: no biosymphony-dispatch-sg found; falling back to default SG."
    SECURITY_GROUP_IDS="$(aws ec2 describe-security-groups \
      --region "$AWS_REGION" \
      --filters Name=group-name,Values=default \
      --query 'SecurityGroups[0].GroupId' --output text)"
  fi
fi

# ----- S3 staging -------------------------------------------------------------
S3_PREFIX="s3://${BIOSYMPHONY_DISPATCH_BUCKET}/${TOOL_NAME}/${RUN_ID}"

# Check bucket reachable
aws s3 ls "s3://${BIOSYMPHONY_DISPATCH_BUCKET}" >/dev/null 2>&1 \
  || { echo "FATAL: bucket s3://${BIOSYMPHONY_DISPATCH_BUCKET} not reachable. Create it: aws s3 mb s3://${BIOSYMPHONY_DISPATCH_BUCKET} --region $AWS_REGION" >&2; exit 74; }

# Prepend the helper to the boot script so it's source-able from boot.sh.
HELPER_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-helper.sh"
printf '%s\n' "$DOWNLOAD_HELPER" > "$HELPER_FILE"

aws s3 cp "$BOOT_SCRIPT_PATH" "$S3_PREFIX/boot.sh"      --region "$AWS_REGION" >/dev/null
aws s3 cp "$HELPER_FILE"      "$S3_PREFIX/helper.sh"    --region "$AWS_REGION" >/dev/null

# ----- user-data wrapper ------------------------------------------------------
# Tiny shell that:
#   - mounts EBS volume at MOUNT_PATH
#   - pulls boot.sh + helper.sh from S3
#   - if IMAGE given: docker run <IMAGE> bash boot.sh
#   - else:           bash boot.sh on bare AMI
#   - posts STATUS sentinels to S3 every 30s in a sidecar loop
#   - self-terminates after boot.sh exits + 30 min idle for operator pull
#
# user-data has a 16 KB limit on EC2 (gzipped 10 KB).

USER_DATA_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-user-data.sh"

cat > "$USER_DATA_FILE" <<USERDATA
#!/usr/bin/env bash
# BioSymphony GeneCluster AWS user-data wrapper: generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# tool=${TOOL_NAME} run_id=${RUN_ID} timeout=${POD_TIMEOUT_HOURS}h
set -uo pipefail

TOOL='${TOOL_NAME}'
RUN_ID='${RUN_ID}'
MOUNT='${MOUNT_PATH}'
S3_PREFIX='${S3_PREFIX}'
IMAGE='${IMAGE}'
WORKDIR="\${MOUNT}/\${TOOL}/\${RUN_ID}"

mkdir -p "\$MOUNT"
# Mount the largest unmounted block device at MOUNT (covers gp3 EBS attachment)
DEV=\$(lsblk -ndo NAME,MOUNTPOINT | awk '\$2=="" {print "/dev/"\$1}' | sort | tail -1)
if [[ -n "\$DEV" ]]; then
  if ! blkid "\$DEV" >/dev/null 2>&1; then
    mkfs.xfs -f "\$DEV" || mkfs.ext4 -F "\$DEV"
  fi
  mount "\$DEV" "\$MOUNT" || true
fi

mkdir -p "\$WORKDIR/logs"
cd "\$WORKDIR"
rm -f SUCCESS FAILURE STATUS *.summary.tsv 2>/dev/null || true

# Stream STATUS to S3 every 30s as a sidecar (parallel to RunPod http.server).
(
  while true; do
    if [[ -f STATUS  ]]; then aws s3 cp STATUS  "\$S3_PREFIX/status/STATUS"  --region '${AWS_REGION}' --quiet 2>/dev/null || true; fi
    if [[ -f SUCCESS ]]; then aws s3 cp SUCCESS "\$S3_PREFIX/status/SUCCESS" --region '${AWS_REGION}' --quiet 2>/dev/null || true; fi
    if [[ -f FAILURE ]]; then aws s3 cp FAILURE "\$S3_PREFIX/status/FAILURE" --region '${AWS_REGION}' --quiet 2>/dev/null || true; fi
    sleep 30
  done
) &
SIDECAR_PID=\$!

# Pull boot.sh + helper.sh from S3
aws s3 cp "\$S3_PREFIX/boot.sh"   ./boot.sh   --region '${AWS_REGION}'
aws s3 cp "\$S3_PREFIX/helper.sh" ./biosymphony_helper.sh --region '${AWS_REGION}'
chmod +x boot.sh

export BIOSYMPHONY_TOOL_NAME="\$TOOL"
export BIOSYMPHONY_RUN_ID="\$RUN_ID"
export BIOSYMPHONY_MOUNT_PATH="\$MOUNT"
export BIOSYMPHONY_WORKDIR="\$WORKDIR"
export BIOSYMPHONY_S3_PREFIX="\$S3_PREFIX"

if [[ -n "\$IMAGE" ]]; then
  # Container path: requires docker on AMI (Deep Learning AMIs ship with it;
  # AL2023 needs `dnf install -y docker && systemctl start docker`).
  command -v docker >/dev/null 2>&1 || { dnf install -y docker || amazon-linux-extras install -y docker; systemctl start docker; }
  docker pull "\$IMAGE"
  docker run --rm \\
    -v "\$WORKDIR":/work \\
    -e BIOSYMPHONY_TOOL_NAME -e BIOSYMPHONY_RUN_ID -e BIOSYMPHONY_MOUNT_PATH -e BIOSYMPHONY_WORKDIR -e BIOSYMPHONY_S3_PREFIX \\
    -w /work \\
    "\$IMAGE" \\
    bash boot.sh > logs/boot.log 2>&1
  RC=\$?
else
  bash boot.sh > logs/boot.log 2>&1
  RC=\$?
fi

# Final flush of artifacts + logs to S3
aws s3 cp logs/boot.log     "\$S3_PREFIX/logs/boot.log"     --region '${AWS_REGION}' --quiet 2>/dev/null || true
aws s3 sync . "\$S3_PREFIX/artifacts/" --region '${AWS_REGION}' --exclude "logs/*" --exclude "boot.sh" --exclude "biosymphony_helper.sh" --quiet 2>/dev/null || true
echo "{\"stage\":\"complete\",\"boot_rc\":\$RC,\"ts\":\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > .self_stop_status
aws s3 cp .self_stop_status "\$S3_PREFIX/status/.self_stop_status" --region '${AWS_REGION}' --quiet 2>/dev/null || true

# Idle window for operator inspection, then self-terminate.
sleep \$((${POD_TIMEOUT_HOURS} * 3600))
TOKEN=\$(curl -sS -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
IID=\$(curl -sS -H "X-aws-ec2-metadata-token: \$TOKEN" http://169.254.169.254/latest/meta-data/instance-id)
aws ec2 terminate-instances --region '${AWS_REGION}' --instance-ids "\$IID"
USERDATA

USERDATA_BYTES="$(wc -c < "$USER_DATA_FILE")"
if (( USERDATA_BYTES > 14000 )); then
  cat >&2 <<MSG
WARN: user-data is ${USERDATA_BYTES} bytes; EC2 limit is 16 KB raw / 64 KB base64
encoded. Move logic into boot.sh on S3 if you exceed 14 KB.
MSG
fi

# Stage user-data and boot to S3 for retrieval/audit
aws s3 cp "$USER_DATA_FILE" "$S3_PREFIX/user-data.sh" --region "$AWS_REGION" >/dev/null

# ----- run-instances ----------------------------------------------------------

INSTANCE_TAGS="ResourceType=instance,Tags=[{Key=Name,Value=${TOOL_NAME}-${RUN_ID}},{Key=tool,Value=${TOOL_NAME}},{Key=biosymphony-run-id,Value=${RUN_ID}},{Key=project,Value=biosymphony}]"
VOLUME_TAGS="ResourceType=volume,Tags=[{Key=Name,Value=${TOOL_NAME}-${RUN_ID}-vol},{Key=project,Value=biosymphony}]"

BLOCK_DEVICE_MAPPING="DeviceName=/dev/sdf,Ebs={VolumeSize=${EBS_GB},VolumeType=gp3,DeleteOnTermination=true}"

EXTRA_ARGS=()
if [[ -n "${KEY_NAME:-}" ]]; then
  EXTRA_ARGS+=(--key-name "$KEY_NAME")
fi

if [[ "$USE_SPOT" == "1" ]]; then
  EXTRA_ARGS+=(--instance-market-options 'MarketType=spot,SpotOptions={SpotInstanceType=one-time,InstanceInterruptionBehavior=terminate}')
fi

RESP_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-run-instances.json"

set +e
aws ec2 run-instances \
  --region "$AWS_REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --subnet-id "$SUBNET_ID" \
  --security-group-ids "$SECURITY_GROUP_IDS" \
  --iam-instance-profile "Name=$IAM_INSTANCE_PROFILE" \
  --block-device-mappings "$BLOCK_DEVICE_MAPPING" \
  --tag-specifications "$INSTANCE_TAGS" "$VOLUME_TAGS" \
  --user-data file://"$USER_DATA_FILE" \
  "${EXTRA_ARGS[@]}" \
  > "$RESP_FILE"
RC=$?
set -e

if (( RC != 0 )); then
  echo "FATAL: aws ec2 run-instances exited $RC; see $RESP_FILE" >&2
  cat "$RESP_FILE" >&2 || true
  exit 75
fi

INSTANCE_ID="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['Instances'][0]['InstanceId'])" "$RESP_FILE")"
echo "$INSTANCE_ID" > "$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-instance-id"

MANIFEST_FILE="$DISPATCH_OUT_DIR/${TOOL_NAME}-${RUN_ID}-launch.json"
python3 - <<PY > "$MANIFEST_FILE"
import json, os
print(json.dumps({
  "cloud": "aws",
  "tool_name": "$TOOL_NAME",
  "run_id": "$RUN_ID",
  "instance_id": "$INSTANCE_ID",
  "instance_type": "$INSTANCE_TYPE",
  "ami_id": "$AMI_ID",
  "region": "$AWS_REGION",
  "subnet_id": "$SUBNET_ID",
  "image": "$IMAGE",
  "mount_path": "$MOUNT_PATH",
  "use_spot": int("$USE_SPOT"),
  "ebs_gb": int("$EBS_GB"),
  "s3_prefix": "$S3_PREFIX",
  "monitor_status_url":  "$S3_PREFIX/status/STATUS",
  "monitor_success_url": "$S3_PREFIX/status/SUCCESS",
  "monitor_failure_url": "$S3_PREFIX/status/FAILURE",
  "monitor_logs_url":    "$S3_PREFIX/logs/boot.log",
  "stop_command":       "aws ec2 stop-instances --region $AWS_REGION --instance-ids $INSTANCE_ID",
  "terminate_command":  "aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID",
}, indent=2))
PY

aws s3 cp "$MANIFEST_FILE" "$S3_PREFIX/launch.json" --region "$AWS_REGION" --quiet 2>/dev/null || true

cat <<DONE
[aws-dispatch] OK
  tool          = $TOOL_NAME
  run_id        = $RUN_ID
  instance_id   = $INSTANCE_ID
  instance_type = $INSTANCE_TYPE
  ami_id        = $AMI_ID
  region        = $AWS_REGION
  s3_prefix     = $S3_PREFIX
  manifest      = $MANIFEST_FILE

Monitor (sentinels via S3):
  aws s3 cp $S3_PREFIX/status/STATUS - --region $AWS_REGION
  aws s3 ls $S3_PREFIX/status/  --region $AWS_REGION

Tail logs:
  aws s3 cp $S3_PREFIX/logs/boot.log - --region $AWS_REGION | tail -50

Stop (preserves instance + EBS, cheap to resume):
  aws ec2 stop-instances --region $AWS_REGION --instance-ids $INSTANCE_ID

Terminate (destroys instance; EBS DeleteOnTermination=true wipes volume):
  aws ec2 terminate-instances --region $AWS_REGION --instance-ids $INSTANCE_ID
DONE
