# BioSymphony GeneCluster: Cloud-Portable Dispatch Templates

**Scope:** one-line tool dispatch for the BioSymphony GeneCluster superpower
stack across RunPod, AWS, GCP, Vast.ai, and Lambda Labs. No laptop installs
required for any tool, the laptop only renders Quarto reports from derived
artifacts 

---

## Files in this directory

| File | Purpose |
| --- | --- |
| `runpod-dispatch.sh` | **Canonical** reference. Network-volume-backed pods on RunPod. |
| `aws-dispatch.sh` | EC2 spot/on-demand + EBS volume + S3 staging + S3 sentinels. |
| `gcp-dispatch.sh` | Compute Engine + persistent disk + GCS staging + GCS sentinels. |
| `vastai-dispatch.sh` | Vast.ai bid-search + ephemeral container + external staging. |
| `lambda-dispatch.sh` | Lambda Labs flat-rate GPU + SSH dispatch + external staging. |
| `README.md` | This file. |

All scripts share the same call signature:

```
<dispatcher>.sh <TOOL_NAME> [IMAGE] <BOOT_SCRIPT_PATH> [MOUNT_PATH=/workspace]
```

Boot scripts get these env vars in the pod/instance:

```
BIOSYMPHONY_TOOL_NAME e.g. cblaster
BIOSYMPHONY_RUN_ID e.g. <run-id>
BIOSYMPHONY_MOUNT_PATH e.g. /workspace
BIOSYMPHONY_WORKDIR e.g. /workspace/cblaster/<run-id>
```

Plus a Mozilla-UA download helper `biosymphony_helper.sh` source-able from
the workdir, exposing the function `biosymphony_download <name> <url> <sha256> <dest>`.

---

## One-line invocation per cloud

The example BIA-P450 case (Q002 CYP80B1 / Q005 CYP719A1 /
Q012 CYP80A1 berbamunine synthase on Stephania tetrandra), invoked via
`cblaster`:

### RunPod (canonical)

```
RUN_ID=<run-id> \
 ./runpod-dispatch.sh cblaster condaforge/mambaforge:latest \
 /path/to/cblaster-boot.sh /workspace
```

### AWS

```
RUN_ID=<run-id> \
BIOSYMPHONY_DISPATCH_BUCKET=<your-dispatch-bucket> \
AWS_PROFILE=default \
 ./aws-dispatch.sh cblaster "" \
 /path/to/cblaster-boot.sh /workspace
```

### GCP

```
RUN_ID=<run-id> \
GOOGLE_CLOUD_PROJECT=<your-gcp-project> \
BIOSYMPHONY_DISPATCH_BUCKET=<your-dispatch-bucket> \
 ./gcp-dispatch.sh cblaster "" \
 /path/to/cblaster-boot.sh /workspace
```

### Vast.ai (cheapest GPU)

```
RUN_ID=<run-id> \
USE_INTERRUPTIBLE=1 VAST_GPU=RTX_4090 VAST_MAX_HOURLY_USD=0.35 \
BIOSYMPHONY_STAGING_S3_PREFIX=s3://<your-dispatch-bucket> \
VASTAI_API_KEY=<from-secure-store> \
 ./vastai-dispatch.sh clean ghcr.io/<owner>/genecluster-superpowers:v0.1 \
 /path/to/clean-boot.sh /workspace
```

### Lambda Labs (simple GPU)

```
RUN_ID=<run-id> \
LAMBDA_API_KEY=<from-secure-store> \
LAMBDA_SSH_KEY_NAME=<lambda-ssh-key-name> \
LAMBDA_SSH_PRIVATE_KEY_PATH=<lambda-ssh-private-key-path> \
LAMBDA_INSTANCE_TYPE=gpu_1x_h100 \
BIOSYMPHONY_DISPATCH_BUCKET=<your-dispatch-bucket> \
 ./lambda-dispatch.sh prostt5 "" \
 /path/to/prostt5-boot.sh /workspace
```

---

## Decision tree: when to pick which cloud

```
Need durable network volume mounted across many short jobs?
 └─ YES → RunPod (persistent network volume preserved across pods)
 └─ NO ↓

Already have AWS account / VPC / S3 bucket / IAM roles?
 └─ YES → AWS (enterprise-friendly; spot for 30, 70% discount)
 └─ NO ↓

Already have GCP project / VPC / GCS bucket / SA?
 └─ YES → GCP (preemptible for 60, 91% discount; Filestore for shared FS)
 └─ NO ↓

GPU-heavy + cheapness > everything (research workloads, ESM, ProstT5, CLEAN)?
 └─ YES → Vast.ai (RTX 4090 spot $0.25, 0.50/h)

Want simplest GPU provisioning, willing to pay flat rates?
 └─ YES → Lambda Labs (gpu_1x_a10 $0.75/h, A100/H100 also available)
```

**Rule of thumb for BioSymphony:**

- **CPU-only tools** (cblaster, clinker, JCVI MCScan, MMseqs2, plantiSMASH,
 P450Rdb): RunPod canonical. AWS spot if existing customer.
- **GPU tools** (CLEAN ESM-1b, HIT-EC, ProstT5, Foldseek+ProstT5, transformers):
 RunPod canonical with GPU. Vast.ai for cost-sensitive bulk. Lambda for
 one-off prototyping (no spot bidding overhead).
- **Long-running / multi-tool campaigns**: RunPod (volume preserved). Avoid
 Vast.ai/Lambda, every instance is fresh disk.

---

## Cost comparison table

Indicative on-demand rates as of 2026-05; spot/interruptible discount in
parens. Prices in USD.

| Resource | RunPod | AWS (us-east-1) | GCP (us-central1) | Vast.ai | Lambda |
| --- | --- | --- | --- | --- | --- |
| **CPU 4-core 16 GB** | $0.18/h SECURE | $0.17/h (spot ~$0.06) | $0.13/h (spot ~$0.04) | n/a (GPU-only) | n/a |
| **CPU 8-core 32 GB** | $0.30/h SECURE | $0.35/h (spot ~$0.12) | $0.39/h (spot ~$0.04) | n/a | n/a |
| **GPU RTX 4090 24 GB** | $0.60/h SECURE | n/a | n/a | $0.25, 0.50/h | n/a |
| **GPU A10 / L4 24 GB** | $0.40/h SECURE | $1.00/h (g5.xlarge) | $0.71/h (g2-standard-4) | $0.40/h | $0.75/h |
| **GPU A100 40 GB** | $1.10/h SECURE | $4.10/h (p4d slice) | $3.67/h (a2) | $0.60, 1.20/h | $1.10/h |
| **GPU H100 80 GB** | $2.49/h SECURE | $5.50/h (p5) | $11.00/h (a3) | $1.50, 2.50/h | $2.49/h |
| **Network volume / persistent disk** | $0.07/GB-mo | $0.08/GB-mo (gp3) | $0.10/GB-mo (pd-balanced) | n/a (ephemeral) | n/a (ephemeral) |
| **Shared FS (NFS-style)** | n/a (volume = block) | EFS $0.30/GB-mo | Filestore $0.20/GB-mo | n/a | n/a |
| **Object storage egress to inspect artifacts** | free via pod proxy | $0.09/GB-out | $0.12/GB-out | manual scp/rsync | manual scp/rsync |

**Cost insight:**

- For a typical 4-hour BIA-P450 cblaster run: RunPod $1.20, AWS spot $0.48,
 GCP spot $0.16, Vast.ai $1.40 (no need; CPU-only).
- For an 8-hour CLEAN ESM-1b enrichment: RunPod GPU $4.80, Vast.ai spot
 $2.00, Lambda flat $6.00.
- Volume-month for 100 GB shared corpus: RunPod $7, AWS gp3 $8, GCP $10.
 (Vast.ai/Lambda need re-stage every run.)

---

## Required env vars per cloud

### RunPod

| Var | Required | Default |
| --- | --- | --- |
| `RUNPOD_API_KEY` | yes | exported in the shell or sourced from an untracked secure env file |
| `GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID` | yes | `<network-volume-id>` |
| `GENECLUSTER_RUNPOD_DATACENTER` | yes | `US-KS-2` |
| `RUN_ID` | no | auto |
| `CONTAINER_DISK_GB` | no | 60 |
| `GPU_TYPE_ID` | no | (CPU pod if unset) |

### AWS

| Var | Required | Default |
| --- | --- | --- |
| `AWS_PROFILE` (or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`) | yes |, |
| `BIOSYMPHONY_DISPATCH_BUCKET` | yes |, |
| `AWS_REGION` | no | `us-east-1` |
| `INSTANCE_TYPE` | no | `m6a.large` |
| `AMI_ID` | no | latest AL2023 via SSM |
| `IAM_INSTANCE_PROFILE` | no | `<DispatchRole>` |
| `EBS_GB` | no | 100 |
| `USE_SPOT` | no | 0 |

Required IAM role policy is documented in the script header.

### GCP

| Var | Required | Default |
| --- | --- | --- |
| `GOOGLE_CLOUD_PROJECT` (or `gcloud config project`) | yes |, |
| `BIOSYMPHONY_DISPATCH_BUCKET` | yes |, |
| `GCP_REGION` | no | `us-central1` |
| `GCP_ZONE` | no | `us-central1-a` |
| `MACHINE_TYPE` | no | `e2-standard-2` |
| `IMAGE_FAMILY` / `IMAGE_PROJECT` | no | `debian-12` / `debian-cloud` |
| `SERVICE_ACCOUNT` | no | `biosymphony-dispatch@<project>.iam.gserviceaccount.com` |
| `DISK_GB` | no | 100 |
| `USE_SPOT` | no | 0 |

Required SA roles: `roles/storage.objectAdmin`, `roles/compute.instanceAdmin.v1`.

### Vast.ai

| Var | Required | Default |
| --- | --- | --- |
| `VASTAI_API_KEY` | yes |, |
| `BIOSYMPHONY_STAGING_S3_PREFIX` (auto S3) **or** `BIOSYMPHONY_STAGING_URL_BASE` (manual) | yes | . |
| `VAST_GPU` | no | `RTX_4090` |
| `VAST_MAX_HOURLY_USD` | no | 0.50 |
| `USE_INTERRUPTIBLE` | no | 0 |

`vastai-cli` auto-installs via `pip install --user vastai-cli` if missing.

### Lambda Labs

| Var | Required | Default |
| --- | --- | --- |
| `LAMBDA_API_KEY` | yes |, |
| `LAMBDA_SSH_KEY_NAME` (pre-registered) | yes |, |
| `LAMBDA_SSH_PRIVATE_KEY_PATH` | yes |, |
| `BIOSYMPHONY_DISPATCH_BUCKET` (S3) **or** `BIOSYMPHONY_STAGING_URL_BASE` | yes | . |
| `LAMBDA_INSTANCE_TYPE` | no | `gpu_1x_a10` |
| `LAMBDA_REGION` | no | `us-east-1` |

---

## Sentinel-pull pattern per cloud

All boot scripts write the canonical sentinels (`STATUS`, `SUCCESS`, `FAILURE`,
`<tool>.summary.tsv`, `.self_stop_status`) into the workdir
`<MOUNT_PATH>/<TOOL>/<RUN_ID>/`. The dispatchers wire up cloud-specific egress:

| Cloud | Sentinel egress | Cache-bust required? | Operator pull command |
| --- | --- | --- | --- |
| **RunPod** | provider storage by default; optional short-lived summary HTTP only when `RUNPOD_EXPOSE_HTTP=1` | yes when HTTP proxy is enabled | `curl -sS "https://${POD}-8000.proxy.runpod.net/STATUS?cb=$RANDOM"` |
| **AWS** | sidecar `aws s3 cp` every 30 s to `s3://<bucket>/<tool>/<run_id>/status/` | no (S3 strong consistency since 2020) | `aws s3 cp s3://<bucket>/<tool>/<run_id>/status/STATUS -` |
| **GCP** | sidecar `gsutil cp` every 30 s to `gs://<bucket>/<tool>/<run_id>/status/` | no | `gsutil cat gs://<bucket>/<tool>/<run_id>/status/STATUS` |
| **Vast.ai** | depends on staging mode: S3 sidecar (preferred) or manual `curl POST` to external endpoint | depends on backend | `aws s3 cp <s3-prefix>/status/STATUS -` or `vastai logs <id>` |
| **Lambda** | over SSH, `cat <MOUNT_PATH>/<tool>/<run_id>/STATUS` | n/a | `ssh -i <key> ubuntu@<ip> "cat <MOUNT_PATH>/<tool>/<run_id>/STATUS"` |

**Monitor heartbeat pattern (cloud-agnostic):**

```bash
while :; do
 STATUS=$(<cloud-specific pull>)
 echo "[$(date -u +%H:%M:%S)] STATUS=$STATUS"
 case "$STATUS" in
 *success*|*complete*) break ;;
 *failed*|*FATAL*) break ;;
 esac
 # No-progress detector (per)
 HEAD_BYTES=$(<cloud-specific HEAD on STATUS file>)
 if [[ "$HEAD_BYTES" == "$LAST_BYTES" ]]; then
 NO_GROWTH=$((NO_GROWTH+1))
 if (( NO_GROWTH >= 3 )); then
 echo "ALERT: no growth in 3 heartbeats; investigating"
 break
 fi
 else
 NO_GROWTH=0
 fi
 LAST_BYTES="$HEAD_BYTES"
 sleep 60
done
```

---

## Lessons baked into all 5 templates (feedback memory references)

These show up as comment-tags in each script's header so future fixers can
trace back to the originating debugging session:

- **64 KB POST-body / user-data ceiling** . wrappers stay tiny; large payloads
 go through staging URL.
 (,
)
- **No inline heredocs in pod startup commands** . all wrappers use
 base64-encoded payloads or external staging URLs.
- **mambaforge has no curl/wget** . Mozilla-UA Python urllib helper is
 baked in (`biosymphony_download` function in every dispatcher).
 (,
)
- **HTTP proxy is opt-in** . serve only a summary workdir, never a provider
 mount root, and prefer provider storage or SSH when available.

- **Stale sentinel cleanup at boot start** . `rm -f SUCCESS FAILURE STATUS
 *.summary.tsv` before any work.

- **RunPod injects stale `RUNPOD_API_KEY`** . do not pass provider API keys
 into pods. Cleanup is owned by the operator-side monitor.

- **`.self_stop_status` sentinel BEFORE the actual API call** . captures
 intent so monitors can detect stop intent independent of API success.

- **Volumes are SECURE-only on RunPod** . capacity widening via
 `cpuFlavorIds`, never `cloudType: COMMUNITY`.

- **Cache-bust monitor URLs on RunPod** . `?cb=$RANDOM` mandatory.

- **Stop ≠ Delete on RunPod** . stop preserves volume; delete destroys
 container disk. Default to stop.

- **TOOL_NAME prefix in resource names** . never bulk-delete; filter by
 prefix.

---

## Open issues / TODOs across templates

- **AWS:** hardcoded AMI fallback (line in `aws-dispatch.sh` near `AMI_ID=`)
 needs periodic refresh; SSM lookup is the primary path.
- **GCP:** GPU machine-type → accelerator mapping is partial . `n1-*` users
 must pass `--accelerator` manually. `g2-*` and `a2-*`/`a3-*` are auto-handled.
- **Vast.ai:** native API has no "stop / hibernate" . only destroy. Templates
 reflect this; for long-running campaigns prefer RunPod or AWS-with-EBS-stop.
- **Lambda Labs:** no spot market; flat hourly rate. No persistent state across
 instances (filesystems API not yet integrated; TODO in `lambda-dispatch.sh`).
- **Cross-cloud:** no GKE Autopilot / EKS / ECS templates . Compute Engine and
 EC2 only. Container orchestration on cloud-native services would be a v2.
- **Cross-cloud:** the boot script contract is a one-way emit (writes
 STATUS/SUCCESS/FAILURE); no two-way command channel from monitor → pod.
 For interactive debugging, SSH or `runpodctl exec` directly.

---

## Adding a new cloud

The template contract is:

1. Read `BOOT_SCRIPT_PATH`, ship it to the cloud (image-bundled, S3-staged,
 or POST-body).
2. Spin up an instance/container with `MOUNT_PATH` mounted somewhere
 (network volume, EBS, persistent disk, ephemeral SSD).
3. Set canonical env: `BIOSYMPHONY_TOOL_NAME`, `BIOSYMPHONY_RUN_ID`,
 `BIOSYMPHONY_MOUNT_PATH`, `BIOSYMPHONY_WORKDIR`.
4. Materialize `biosymphony_helper.sh` with the Mozilla-UA download function
 in the workdir.
5. Sidecar streams `STATUS`/`SUCCESS`/`FAILURE` somewhere monitorable (proxy
 HTTP, S3, GCS, SSH-cat).
6. Idle window for operator pull, then operator-side cleanup or provider-native self-stop when scoped credentials are available.
7. Emit `<tool>-<run_id>-launch.json` manifest with: cloud, instance id,
 monitor URL, stop command. Manifest schema is the same across clouds.

Manifest schema (consumed by operator-side monitors):

```json
{
 "cloud": "runpod|aws|gcp|vastai|lambda",
 "tool_name": "<TOOL_NAME>",
 "run_id": "<RUN_ID>",
 "<id_field>": "<pod_id|instance_id|instance_name>",
 "image": "<container image or empty>",
 "mount_path": "/workspace",
 "monitor_status_url":"<pull URL or s3:// or gs:// or 'ssh ...'>",
 "stop_command": "<text command>",
 "...": "<cloud-specific extras>"
}
```
