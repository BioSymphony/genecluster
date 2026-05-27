# GCP for BioSymphony GeneCluster: engineering notes

**Status:** Forward research, not yet validated. We have **no GCP credentials**. This doc exists so the next operator can dispatch a working pod within one hour, not so we can claim we've used GCP.

**Reference recipe to translate:** [`docs/biosymphony-antismash-cookbook.md`](../biosymphony-antismash-cookbook.md) (validated on RunPod cpu5g, antiSMASH 8 on *B. subtilis* 168, 5 min 17 s wall, ~$0.017).

**Validated RunPod tools we'd port:** antiSMASH 8, DeepBGC, ESM-C via Synthyra/ESMplusplus_small, MMseqs2, Foldseek + ProstT5, CLEAN, P450Rdb.

All prices in this doc are **as of 2026-05-11**, region `us-central1` unless noted, on-demand. GCP changes prices on the order of months; re-verify before relying on any number.

---

## TL;DR: when to (and not to) port from RunPod to GCP

**Use GCP over RunPod when:**

- You need a managed batch service (Cloud Batch) instead of hand-rolled pod dispatch + monitor. RunPod has no native job queue.
- You need NFS shared between many concurrent workers, Filestore is a one-call provision; RunPod network volumes are single-pod-attach.
- The data lives in GCS already (NCBI SRA mirror, public genomics datasets) and you want zero-egress same-region access.
- You need >256 vCPU in one VM, or multi-node MPI, RunPod tops out at pod-flavor sizes; GCE goes to `c2-standard-60` / `m3-ultramem-128`.
- Compliance: HIPAA-eligible service list, VPC-SC, CMEK. RunPod doesn't have BAA coverage.
- Spot A100/H100 capacity, GCP Spot discounts on accelerators are 60-91 %, often deeper than RunPod's COMMUNITY tier when COMMUNITY is full.

**Stay on RunPod when:**

- You want **lowest-cost CPU** for opportunistic <1 h jobs. RunPod cpu5g (4 vCPU / 32 GB) at $0.184/hr undercuts GCP c2-standard-4 (~$0.21/hr on-demand, ~$0.14/hr Spot) and there is no GCP minimum charge, but RunPod billing is per-second from container-start whereas GCE bills from VM creation (boot ~30-45 s of paid time you can't run anything in).
- You're already paying the iteration cost of the RunPod boot pattern (base64+gzip `dockerStartCmd`, proxy file pull, self-stop) and don't want to retool. None of the GCP analogs are turn-key drop-ins.
- You need RunPod-specific networking (`*-8000.proxy.runpod.net` over HTTPS without DNS / certs / firewall). GCE requires either a public IP + open firewall rule, IAP tunnel, or a load balancer, non-trivial for one-shot pods.
- The pipeline lives in a single ~20 GB container with `dockerStartCmd` as the only orchestration. RunPod's stateless-pod model maps to a single GCE VM only if you also write the auto-shutdown plumbing.
- You can't predict capacity needs week-to-week and don't want sustained-use discount commitments. Both clouds have on-demand; RunPod just doesn't tempt you with CUDs.

---

## Quick-start: antiSMASH 8 on a c2-standard-16 (GCE): mirror of RunPod test4b

This recipe ports `.runtime/<superpowers-launch>/staging/test4b-antismash8-mambaforge-boot.sh` to GCP. Wall time estimate: 6-8 min (slightly higher than RunPod's 5:17 because we don't have the `condaforge/mambaforge` cache in a regional cache.)

```bash
# Variables
PROJECT=biosymphony-dev # gcloud config set project biosymphony-dev
ZONE=us-central1-a # us-east1 if you want NCBI SRA in-region
INSTANCE=antismash8-bsub-demo
BUCKET=biosymphony-boot-scripts # GCS bucket for startup-script-url

# 1. One-time bucket setup (idempotent)
gcloud storage buckets create gs://$BUCKET --location=us-central1 --uniform-bucket-level-access

# 2. Upload boot script to GCS (the analog of RunPod's gzip+b64 dockerStartCmd)
gcloud storage cp ./antismash8-boot.sh gs://$BUCKET/antismash8-boot.sh

# 3. Launch VM with startup-script-url (no 256 KB limit; script can be MB-scale)
gcloud compute instances create $INSTANCE \
 --zone=$ZONE \
 --machine-type=c2-standard-16 \
 --image-family=debian-12 \
 --image-project=debian-cloud \
 --boot-disk-size=50GB \
 --boot-disk-type=pd-balanced \
 --scopes=https://www.googleapis.com/auth/cloud-platform \
 --metadata=startup-script-url=gs://$BUCKET/antismash8-boot.sh,shutdown-after-minutes=120 \
 --provisioning-model=SPOT \
 --instance-termination-action=DELETE \
 --max-run-duration=4h

# 4. Tail boot log (analog of RunPod proxy STATUS poll)
gcloud compute instances get-serial-port-output $INSTANCE --zone=$ZONE | tail -80

# 5. Pull results from GCS (boot script uploads to gs://$BUCKET/results/<instance>/)
gcloud storage cp -r gs://$BUCKET/results/$INSTANCE/ ./antismash-results/

# 6. Delete (if --instance-termination-action wasn't set or you want to be sure)
gcloud compute instances delete $INSTANCE --zone=$ZONE --quiet
```

The boot script (`antismash8-boot.sh`) lives at the bottom of this doc, it's a self-contained port of the RunPod boot pattern.

Cost estimate for this run (Spot pricing):

| Item | Quantity | Rate | Cost |
|---|---|---|---|
| c2-standard-16 Spot (us-central1) | 0.13 hr (8 min) | ~$0.21/hr | $0.027 |
| pd-balanced 50 GB | 0.13 hr | $0.00014/GB-hr | $0.001 |
| GCS Standard storage (boot script + results, ~30 MB) | 1 month | $0.020/GB-mo | $0.001 |
| GCS Class A operations (uploads) | ~10 | $5/1e6 | negligible |
| Egress to laptop (results.tar.gz, 22 MB) | 0.022 GB | $0.12/GB | $0.003 |
| **Total** | | | **~$0.03** |

That's roughly 2x RunPod's $0.017, Spot mostly closes the gap, but GCE has unavoidable boot-time billing and a thin egress charge for pulling results to your laptop.

---

## RunPod → GCP translation table

| Concept | RunPod | GCP analog | Notes |
|---|---|---|---|
| One-shot compute | POST `/v1/pods` with `cpuFlavorIds`, `dockerStartCmd` | `gcloud compute instances create --machine-type --metadata startup-script-url=...` | GCE has no pod abstraction. VM + startup script + auto-stop = a "pod". |
| Pod flavor ID | `cpu5g`, `cpu3c`, etc. | `c2-standard-N`, `n2-standard-N`, `e2-standard-N` | GCP is explicit; RunPod is implicit. See machine-type cheat sheet. |
| Compute type confusion | `computeType: "GPU"` (default!) bills 5-10× | Machine family is in the name (`a2-`, `g2-`, `n2-`) | GCE can't accidentally pick GPU. |
| Container disk | `containerDiskInGb: 30` | `--boot-disk-size=30GB` | GCE boot disks are separately billable (~$0.04-0.17/GB-mo). |
| Network volume | `networkVolumeId` (SECURE-only) | `gcloud compute disks create --type=pd-ssd` + `--disk=` flag (single-VM) or Filestore for multi-VM NFS | GCP persistent disks are single-attach RW like RunPod volumes; Filestore = multi-attach NFS, no RunPod analog. |
| Multi-DC scheduling | `dataCenterIds: ["US-KS-2","EU-RO-1",...]` | Regional MIG (`--zones=us-central1-a,us-central1-b,us-central1-c`) | MIGs auto-fall-back across zones in one region; for cross-region you script it. |
| Boot payload | `dockerStartCmd` (64 KB POST limit; we use gzip+b64) | `--metadata=startup-script=` (256 KB limit) **or** `--metadata=startup-script-url=gs://...` (no size limit) | GCS-backed startup-script-url is the production path; embeds badly into one-shot CI. |
| Self-stop | POST to RunPod stop endpoint with API key | `gcloud compute instances stop $NAME` from inside via SA, or `shutdown -h +5`, or `--max-run-duration=4h` | `--max-run-duration` is the cleanest equivalent of "deadman timer", added at create time, can't be forgotten. |
| Image pull | RunPod pulls from registry on pod start; GHCR stalls common for >5 GB | GCE pulls when `cos-cloud` family or via `docker pull` in startup script; Artifact Registry images cached at zone level | Use Artifact Registry in same region as VMs, pulls cross-region cost egress. |
| Proxy file access | `https://${POD_ID}-8000.proxy.runpod.net/` | None native. Use external IP + firewall rule, IAP tunnel, or upload to GCS | The cleanest port is "boot script uploads artifacts to GCS, you pull from GCS". |
| Active monitor | `curl proxy/STATUS?cb=$RANDOM` loop | `gcloud compute instances get-serial-port-output` polling, or Cloud Logging filter + sink | Cloud Logging is more durable than serial output for long runs. |
| Capacity outage | Single SECURE DC out → widen `dataCenterIds` | Single zone out → regional MIG or retry with `--zones=` list | MIGs handle this declaratively. For ad-hoc, script `--zones` rotation. |
| Cost surprise | Forgetting `computeType: "CPU"` → 5-10× | Forgetting `--provisioning-model=SPOT` → 3-5× on accelerators | Both clouds have one big lever you can forget. |
| Stale apikey injection | RunPod injects stale `RUNPOD_API_KEY` in pod env | GCE metadata service `metadata.google.internal/computeMetadata/v1/`, never put SA JSON keys in user data | Use attached service account + scopes, not key files. |
| Heredoc pitfall | `python3 - <<EOF` collides with stdin pipe | Same risk in startup scripts (run via cloud-init) | Keep startup scripts file-sourced; avoid inline heredocs. |
| 502 from proxy during long stages | `http.server` not started yet | Cloud Logging stream is always live; no analog problem | Win for GCP, one less footgun. |
| Stale sentinel pattern | `rm -f SUCCESS FAILURE` at boot | Same, `rm -f /var/log/biosymphony-status/*` first | Pattern ports identically. |

---

## Machine-type cheat sheet (us-central1, on-demand, 2026-05-11)

Pricing is **approximate**; verify with [`gcloud compute machine-types list`](https://cloud.google.com/compute/vm-instance-pricing) before billing-sensitive work.

### General-purpose

| Family | When to use | Example | vCPU / RAM | On-demand | Spot | RunPod cross-ref |
|---|---|---|---|---|---|---|
| **e2-standard** | Cheap, bursty, small jobs (boot pods, monitors) | `e2-standard-4` | 4 / 16 GB | ~$0.13/hr | ~$0.04/hr | cpu3c-ish |
| **n2-standard** | Workhorse general-purpose (Intel Cascade/Ice Lake) | `n2-standard-8` | 8 / 32 GB | ~$0.39/hr | ~$0.10/hr | cpu5g equivalent |
| **n2d-standard** | AMD EPYC Milan; same RAM, ~10 % cheaper than n2 | `n2d-standard-16` | 16 / 64 GB | ~$0.68/hr | ~$0.17/hr | No clean match |
| **t2d-standard** | AMD Tau, throughput-tuned, x86 | `t2d-standard-32` | 32 / 128 GB | ~$1.24/hr | ~$0.31/hr | No match |
| **t2a-standard** | ARM Neoverse N1; cheapest per-vCPU, but **most bioconda packages lack ARM builds** | `t2a-standard-16` | 16 / 64 GB | ~$0.59/hr | ~$0.15/hr | No match; risky for bio |

### Compute-optimized (CPU-bound: BLAST, HMMER, alignment, antiSMASH)

| Family | When to use | Example | vCPU / RAM | On-demand | Spot | RunPod cross-ref |
|---|---|---|---|---|---|---|
| **c2-standard** | Intel Cascade Lake, 3.9 GHz turbo, 4 GB/vCPU | `c2-standard-16` | 16 / 64 GB | ~$0.84/hr | ~$0.21/hr | Faster per-core than cpu5g |
| **c3-standard** | Intel Sapphire Rapids, newer, supports Hyperdisk | `c3-standard-22` | 22 / 88 GB | ~$1.10/hr | ~$0.30/hr | No match; best single-thread |

c2 is the **default port target** for antiSMASH 8 / BLAST / HMMER pipelines. It costs roughly 2× cpu5g for 2× the cores at higher clock; worth it for CPU-bound stages.

### Memory-optimized (assembly, large genome indexing)

| Family | When to use | Example | vCPU / RAM | On-demand | Spot | Note |
|---|---|---|---|---|---|---|
| **m1-megamem** | 14-24 GB/vCPU, up to 1.4 TB | `m1-ultramem-40` | 40 / 961 GB | ~$5.40/hr | n/a | No RunPod analog |
| **m3-megamem** | Latest, Intel Ice Lake, up to 3.9 TB | `m3-ultramem-128` | 128 / 3904 GB | ~$24/hr | n/a | For *de novo* mammal-scale assembly |

If you needed *Stephania* chr-scale assembly RAM, this is the only ladder. RunPod has nothing comparable.

### GPU (Foldseek ProstT5, ESM, CLEAN, AlphaFold)

| Family | GPU | vCPU / RAM | On-demand | Spot | RunPod cross-ref | Verdict |
|---|---|---|---|---|---|---|
| **n1 + T4** | 1× T4 16 GB | configurable | ~$0.35/hr GPU + ~$0.04/vCPU | ~$0.10/hr GPU | RunPod T4: ~$0.30/hr | Cheapest inference GPU. Good for ProstT5 / CLEAN. |
| **g2-standard** | 1× L4 24 GB | 4-96 / 16-432 GB | ~$0.71/hr + base | ~$0.20/hr GPU | RunPod L4: ~$0.40/hr | **Best price/perf for inference** in 2026; supports fp8. |
| **a2-highgpu-1g** | 1× A100 40 GB | 12 / 85 GB | ~$3.67/hr | ~$1.10/hr (70 % off) | RunPod A100 80GB: $1.89/hr | Spot A100 is competitive; on-demand isn't. |
| **a2-ultragpu-1g** | 1× A100 80 GB | 12 / 170 GB | ~$5.07/hr | ~$1.50/hr | RunPod A100 80GB: $1.89/hr | Spot is the only competitive option. |
| **a3-highgpu-1g** | 1× H100 80 GB | 26 / 234 GB | ~$10.60/hr | ~$3.00/hr | RunPod H100: $2.49-3.50/hr | Spot is the only competitive option; H100 capacity is the gating factor. |

Notes:
- Spot pricing on GPUs in GCP has been **60-91 % off** since 2024 ([Spot VMs pricing](https://cloud.google.com/spot-vms/pricing)).
- **30-second termination notice** on Spot. must handle SIGTERM and checkpoint or run idempotent.
- A100 80GB on GCP costs **2.7× RunPod** on-demand. Spot A100 is the only competitive shape for one-shot.

---

## Storage decision tree

Match storage to data lifecycle, not just size.

```
Is the data ephemeral (deleted at pod end)?
 YES → boot disk (pd-balanced 50-100 GB). $0.10/GB-mo prorated.
 NO ↓

Does it need multi-writer NFS semantics?
 YES → Filestore Basic HDD ($0.20/GB-mo, min 1 TB) or Filestore Zonal SSD ($0.30/GB-mo, min 2.5 TB)
 , only choice for >1 VM concurrent writes.
 NO ↓

Does it need block-device semantics (mount as /mnt/x, random IO)?
 YES → Persistent Disk
 - pd-standard: HDD-backed, $0.040/GB-mo, slow IO. For archival mounts.
 - pd-balanced: SSD-backed, $0.10/GB-mo, 3000 baseline IOPS. **DEFAULT.**
 - pd-ssd: $0.17/GB-mo, 30 IOPS/GB. For sustained 30k+ IOPS.
 - pd-extreme: $0.125/GB-mo + $0.065/IOPS-mo, provisioned to 160k IOPS. For Foldseek databases hot-path.
 - Hyperdisk Balanced (c3+): $0.10/GB + IOPS/throughput separately. For fine-grained perf tuning.
 NO ↓

Object store (GCS):
 - Standard: $0.020/GB-mo, no min duration. **Default for results, archives, NCBI mirrors.**
 - Nearline: $0.010/GB-mo, 30-day min, $0.01/GB retrieval. For monthly access.
 - Coldline: $0.004/GB-mo, 90-day min, $0.02/GB retrieval. For yearly access.
 - Archive: $0.0012/GB-mo, 365-day min, $0.05/GB retrieval. For "delete-or-never-read".
```

Rule of thumb for our pipelines:

- **Boot disk = pd-balanced 50 GB.** Mambaforge + bioconda envs fit; raw data shouldn't.
- **Raw / intermediate data = pd-ssd disk attached only for the run.** Detach + delete after. Or skip the disk and stage to/from GCS at start/end of pipeline.
- **Reference DBs = pd-extreme or Hyperdisk** if same DB is used >2× / week (Pfam-A, BFD, MMseqs2 UniRef). Sized at the data's footprint, not a 2× safety margin.
- **Final artifacts = GCS Standard,** organized by `gs://biosymphony-results/<campaign>/<pod-id>/`.

### NCBI SRA on GCS

NCBI mirrors public SRA data to GCS. From [NCBI SRA Cloud docs](https://www.ncbi.nlm.nih.gov/sra/docs/SRA-Google-Cloud/):

- Free access in any **US region**, specifically **us-east1** is recommended.
- Bucket paths observed: `gs://sra-pub-src-N/` (source submissions, BAM/CRAM/FASTQ), `gs://sra-pub-run-N/` (run files), where N is a sharding integer.
- SRA Toolkit `prefetch` and `fasterq-dump` 2.10.2+ have native GCS support. Set `vdb-config` to use cloud credentials.
- Same-region GCE → GCS reads are free (egress not billed). Cross-region or to-internet pulls cost $0.12/GB.

**RunPod cross-ref:** Memory documents 1-4 MB/s sustained from RunPod GPU pods. On a GCE VM in us-east1, intra-region GCS pulls have been measured at 100+ MB/s. **a ~50× speedup** for the SRA download phase, just from co-location. This alone is a strong argument for GCP on SRA-heavy campaigns.

---

## Self-stop / kill-switch patterns

Three concrete patterns, ordered by simplicity.

### Pattern 1: `--max-run-duration` (deadman timer, simplest)

```bash
gcloud compute instances create $NAME \
 --max-run-duration=4h \
 --instance-termination-action=DELETE \
 ...
```

Set at create time, fires regardless of what the boot script does. Equivalent to `at now + 4 hours; gcloud compute instances delete`. **The recommended default.** Stops a runaway from billing through the weekend.

### Pattern 2: instance-side shutdown via metadata or success signal

In the boot script, after `SUCCESS` is written:

```bash
# Self-stop using the attached service account (no API key needed).
# Requires the VM to have the compute.instances.stop or compute.instances.delete permission.
TOKEN=$(curl -s -H "Metadata-Flavor: Google" \
 "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" | \
 python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

NAME=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
ZONE=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{print $NF}')
PROJECT=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)

# Stop (preserves disk): for hibernate-like behavior, analog of RunPod stop
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
 "https://compute.googleapis.com/compute/v1/projects/$PROJECT/zones/$ZONE/instances/$NAME/stop"

# Or delete (destroys instance and any --instance-termination-action=DELETE marked disks)
# curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
# "https://compute.googleapis.com/compute/v1/projects/$PROJECT/zones/$ZONE/instances/$NAME"
```

**Critical:** the metadata service replaces RunPod's stale-API-key footgun cleanly. The token is short-lived and scoped to the VM's attached service account. Never put a service account JSON key in user data. equivalent to RunPod's "don't echo $RUNPOD_API_KEY into the pod" rule.

For idle-detection (CPU < threshold for N minutes), use `top`/`ps` polling in the boot script before issuing the stop API call. [Reference impl by Justin Shenk](https://gist.github.com/justinshenk/312b5e0ab7acc3b116f7bf3b6d888fa4).

### Pattern 3: Cloud Scheduler + Cloud Function (external)

For "stop everything tagged `biosymphony-campaign-id=X` every night at 02:00":

```bash
# 1. Cloud Function (Python) that lists & stops instances by label
gcloud functions deploy stop-by-label \
 --runtime=python311 --trigger-http --entry-point=stop_by_label

# 2. Cloud Scheduler cron entry
gcloud scheduler jobs create http stop-biosymphony-nightly \
 --schedule="0 2 * * *" \
 --uri=https://us-central1-$PROJECT.cloudfunctions.net/stop-by-label \
 --message-body='{"label": "biosymphony-campaign-id"}' \
 --oidc-service-account-email=stopper-sa@$PROJECT.iam.gserviceaccount.com
```

Use this for **enforcement** ("everything in dev project shuts down nightly") rather than per-pod self-stop. Equivalent to a cron-driven RunPod GraphQL stop loop.

### Pattern 4: Cloud Monitoring alert + Cloud Function (idle detection at scale)

For "stop any VM whose CPU has been <5 % for 30 min":

```
Cloud Monitoring → metric: compute.googleapis.com/instance/cpu/utilization
 → alert if mean < 0.05 over 30 min
 → notification channel: Pub/Sub topic
 → Cloud Function subscribes to Pub/Sub, calls instances.stop
```

Heavyweight. Use only when running >10 ad-hoc VMs and you can't trust each to self-stop. Equivalent of RunPod monitor pod for `cpu=0%` stalls.

---

## Boot payload: GCE startup script via `metadata.startup-script` or `startup-script-url`

| Constraint | RunPod `dockerStartCmd` | GCE `metadata.startup-script` | GCE `startup-script-url` |
|---|---|---|---|
| Size limit | ~64 KB POST body | 256 KB metadata value | None (sourced from GCS) |
| Encoding pattern | gzip + base64 | Plain bash | Plain bash |
| Stored in repo | dispatch script embeds | inline in `gcloud` command | upload to GCS |
| Modify after VM up | No (recreate) | Yes (add-metadata + reboot) | Yes (re-upload to GCS, recreate VM) |
| Boot logs | RunPod proxy STATUS file | `gcloud compute instances get-serial-port-output` or Cloud Logging | Same as above |

**Recommendation:** Use `startup-script-url=gs://<bucket>/boot.sh` for any script >10 KB. The gzip+b64 dance we use on RunPod is unnecessary on GCP and adds debugging friction.

If you must inline, use:

```bash
gcloud compute instances create $NAME \
 --metadata-from-file=startup-script=./boot.sh \
 ...
```

`--metadata-from-file` reads from disk and submits as inline metadata, same 256 KB limit, but no shell escaping pain.

---

## Image strategy: Artifact Registry vs Docker Hub

| Decision | Recommendation |
|---|---|
| Public images you already use (`condaforge/mambaforge`, `antismash/standalone-lite`) | Pull directly from Docker Hub. GCE has unmetered Docker Hub pull as of 2026. **No analog to RunPod's GHCR-stall pattern observed,** but `gcloud auth configure-docker` is still recommended to use Artifact Registry's caching for repeat pulls. |
| Your own custom images (e.g., `ghcr.io/biosymphony/genecluster-runner`) | Push to **Artifact Registry in the same region as your VMs**. `gcloud auth configure-docker us-central1-docker.pkg.dev`. Cross-region pulls cost egress. |
| Image pull authentication | Default GCE service account has `roles/artifactregistry.reader` if granted on the project. Or attach a custom SA with `--scopes=https://www.googleapis.com/auth/cloud-platform`. **Never put SA JSON keys in startup-script.** |

GCE-managed `cos-cloud/cos-stable` images come with `docker` pre-installed, equivalent to a "container OS" pod base. Trade-off: no apt, so anything outside the container has to come in via the container image. Debian 12 + manual `apt-get install docker.io` in startup script is the more flexible path; COS is the more secure path.

For our pipelines, **Debian 12 is the default**, boot scripts install mambaforge directly and don't go through Docker.

---

## Bandwidth profile

| Path | RunPod observed | GCP expected |
|---|---|---|
| NCBI FTP (eutils, prefetch) | 1-4 MB/s sustained | 5-20 MB/s sustained (region-dependent; better from us-east1) |
| NCBI SRA via `prefetch` | 1-4 MB/s | 100+ MB/s **when reading from `gs://sra-pub-run-N/` in same region** |
| Catbox / catbox.litterbox | RunPod often blocked | Should work from GCE; not validated |
| NGDC GWH (Plants index) | 1-10 MB/s, occasional 50-100 MB/s | Same expected; no GCP-specific advantage |
| Intra-cloud (GCS in same region) | n/a | 100+ MB/s sustained; **free** |
| Inter-zone (same region) | n/a | 100+ MB/s; **$0.01/GB** |
| Inter-region | n/a | $0.02-0.12/GB depending on continent |
| Internet egress (results pull to laptop) | Free (via proxy) | $0.12/GB first 1 TB, $0.08/GB next |

**Implication for SRA-heavy campaigns:** Each 3 GB SRA file at 1-4 MB/s on RunPod is 15-30 min. On GCE us-east1 from `gs://sra-pub-run-*`, the same file is 30-60 s. A 4-dataset RNA-Seq campaign drops from 2.5-3 h of downloads to ~5 min. **Strongest single argument for porting bandwidth-sensitive campaigns to GCP.**

---

## Capacity recovery: multi-zone MIG + Spot fallback

RunPod's playbook: widen `dataCenterIds` from one DC to a list of four. GCP analog is more declarative.

```bash
# Create instance template (the "pod spec" of GCE)
gcloud compute instance-templates create antismash-template \
 --machine-type=c2-standard-16 \
 --image-family=debian-12 --image-project=debian-cloud \
 --provisioning-model=SPOT \
 --instance-termination-action=DELETE \
 --max-run-duration=4h \
 --metadata-from-file=startup-script=./antismash-boot.sh

# Create regional MIG across all 4 us-central1 zones, target size 1
gcloud compute instance-groups managed create antismash-mig \
 --region=us-central1 \
 --zones=us-central1-a,us-central1-b,us-central1-c,us-central1-f \
 --base-instance-name=antismash \
 --template=antismash-template \
 --size=1 \
 --target-distribution-shape=BALANCED
```

If `us-central1-a` is out of c2-standard-16 Spot capacity, the MIG retries `us-central1-b`, etc. If all 4 zones are out, the MIG returns errors but **does not block**, you can layer on a Pub/Sub trigger to retry hourly.

**Spot eviction:** 30-second `TERM` signal. Handle in the boot script:

```bash
# In boot script
trap 'echo "Spot eviction, uploading state to GCS"; gcloud storage cp /tmp/state gs://$BUCKET/state-checkpoint/; exit 0' TERM
```

For pipelines that take >30 min and can't checkpoint, **use on-demand, not Spot.** antiSMASH 8 fits the Spot envelope (5-15 min). AlphaFold 3 inference does not.

---

## Managed services for bio

### Cloud Batch (the successor to Cloud Life Sciences API)

**Cloud Life Sciences API was deprecated 2023-07-17 and shut down 2025-07-08.** All new bio workflows on GCP should use **Cloud Batch**. ([Migration guide](https://cloud.google.com/batch/docs/migrate-to-batch-from-cloud-life-sciences), [Snakemake issue #2360](https://github.com/snakemake/snakemake/issues/2360))

Submitting a single-task antiSMASH job to Cloud Batch:

```bash
gcloud batch jobs submit antismash-bsub-batch \
 --location=us-central1 \
 --config=- <<'EOF'
{
 "taskGroups": [{
 "taskSpec": {
 "runnables": [{
 "container": {
 "imageUri": "condaforge/mambaforge:latest",
 "entrypoint": "/bin/bash",
 "commands": ["-c", "curl -sS https://storage.googleapis.com/biosymphony-boot-scripts/antismash8-boot.sh | bash"]
 }
 }],
 "computeResource": {"cpuMilli": 16000, "memoryMib": 65536},
 "maxRunDuration": "3600s"
 },
 "taskCount": 1
 }],
 "allocationPolicy": {
 "instances": [{
 "policy": {
 "machineType": "c2-standard-16",
 "provisioningModel": "SPOT"
 }
 }]
 },
 "logsPolicy": {"destination": "CLOUD_LOGGING"}
}
EOF
```

Cloud Batch **vs** rolling-your-own MIG:

- **Use Cloud Batch when:** you're submitting many jobs and want a queue, retry policy, log aggregation, deps between jobs. It's a real job system.
- **Use MIG + startup-script when:** you want one VM doing one thing, with full control of the boot script. Simpler mental model; closer to RunPod.

For BioSymphony GeneCluster specifically: each "campaign dispatch" is a single one-shot pod. **Start with MIG + startup script.** Move to Cloud Batch if you scale to >10 parallel campaigns.

### Nextflow on Cloud Batch

[`nextflow.config`](https://nextflow.io/docs/latest/google.html) with the `google-batch` executor, minimal example:

```groovy
process { executor = 'google-batch' }
google {
 project = 'biosymphony-dev'
 location = 'us-central1'
 batch.spot = true
}
```

`nextflow run nextflow-io/rnaseq-nf -profile google-batch` ports any nf-core pipeline to Cloud Batch with no per-step Dockerfile changes. **This is the main reason teams pick GCP over RunPod for production bio workflows**, nf-core has first-class GCP support, RunPod has none.

### Vertex AI for protein language models

- **AlphaFold 2:** Google ships the [vertex-ai-alphafold-inference-pipeline](https://github.com/GoogleCloudPlatform/vertex-ai-alphafold-inference-pipeline) repo. Vertex AI Pipeline JSON + an AlphaFold Portal that's user-friendly. Splits CPU preprocessing from GPU inference automatically. Mature as of 2024.
- **AlphaFold 3:** No official Vertex AI deployment as of 2026-05. EBI's hosted version is the recommended endpoint for casual use; for batch on GCP, self-host on an `a2-ultragpu-1g` (A100 80 GB).
- **ESM-2, ESM-C:** No prebuilt Vertex AI container. Same pattern as our RunPod recipe. pull `Synthyra/ESMplusplus_small` from HF, use `a2-` or `g2-` machine. Vertex AI Workbench can run the notebook variant for interactive use.
- **AlphaGenome:** Released January 2026 ([DeepMind blog](https://deepmind.google/blog/alphagenome-ai-for-better-understanding-the-genome/), open source weights). Python SDK at [google-deepmind/alphagenome](https://github.com/google-deepmind/alphagenome). 1 Mb DNA → regulatory predictions. Worth integrating for any cis-regulatory analysis; runs on a single A100.

### GKE Autopilot

Skip for our use case. Autopilot is for long-running services; our pods are one-shot batch. Cloud Batch is the right primitive.

### Cloud Workstations

For interactive R / Jupyter on a persistent home directory (the `~/.runtime/` analog), Cloud Workstations gives you a managed dev VM with auto-stop and persistent PD. Cost: ~$0.10-0.50/hr depending on machine. **Use case:** Quarto rendering, exploratory analysis. Not a replacement for batch dispatch.

---

## Sustained-use and committed-use discounts

| Discount | Triggers | Effective rate |
|---|---|---|
| **Sustained-use discount (SUD)** | Automatic. Discounts at 25/50/75/100 % of the month threshold. | Up to **30 %** off after running 100 % of the month. |
| **Committed-use discount (CUD), 1-year** | Sign up; commit to spend or specific machine type. | Up to **57 %** off for general compute, **70 %** off for memory-optimized. |
| **CUD, 3-year** | Same. | Up to **70 %** off. |
| **Spot/preemptible** | `--provisioning-model=SPOT`. | **60-91 %** off list. 30 s eviction notice. |

For our usage pattern (intermittent one-shot pods), **Spot + on-demand for non-preemptible** is the only relevant lever. SUD applies but we don't hit the thresholds. CUDs don't make sense until we're running >1 VM continuously for a quarter.

**As of 2026-01-21**, Google migrated billing from credit-based to direct-discount CUD presentation, but the percentages didn't change. Old proposals citing "CUD credits" will show on bills as direct discounts now.

---

## Gotcha translation table: RunPod memories → GCP analogs

| RunPod memory | GCP analog | Mitigation |
|---|---|---|
| (64 KB POST) | 256 KB metadata limit; use startup-script-url for larger | Use `gs://` URLs; no gzip+b64 needed |
| | Same risk in startup scripts | Don't pipe stdin to a script that reads stdin via heredoc |
| | GCE has `status` field that's truthful | `gcloud compute instances describe --format='value(status)'` is authoritative |
| | Artifact Registry IAM via attached SA | Attach SA with `roles/artifactregistry.reader`; never use SA JSON keys |
| | Same pattern, 2-min smoke instance first | Use `e2-medium` Spot for $0.005/hr smoke tests |
| | MIG `restartPolicy` thresholds | Set `maxRetryCount` on instance template |
| | Same pattern; not GCP-specific | Verify output file exists, not exit code alone |
| | GCS pulls cost egress | Tag artifacts by importance; only pull summaries to laptop |
| | Same, capture HTTP status from stop API | Write `.self_stop_status` sentinel before `instances.stop` call |
| | GCE `stop` (preserves disk) vs `delete` (destroys boot disk if not `--keep-disks`) | Use `stop` for hibernate; `delete` only if you've copied artifacts off |
| | GCE labels (`--labels=campaign=demo3`) | Always filter `gcloud compute instances delete` by label |
| | Single-zone capacity outage | Regional MIG across all zones; auto-retry |
| | GCE `pendingOperations` field; serial console output | Check serial port output at 60 s; if blank, the image pull or boot failed |
| | GCE has only one status surface (REST + gcloud agree) | No gotcha here |
| | Same principle applies to GCP-specific notes | Embed GCP gotchas in issue bodies |
| | Not cloud-specific | Same `git add -f` fix |
| | GCE metadata server provides fresh tokens | Use metadata server, never stash credentials in env or files |
| | Cloud Batch handles this natively | Use Cloud Batch for >10 min jobs; submit + exit + receive completion via Pub/Sub |
| | startup-script-url, no size limit | Upload bundle to GCS, reference by URL |
| Ephemeral upload services may change availability | GCS signed URLs replace catbox/file.io | `gcloud storage sign-url` for unauth pulls |
| | Same, install nextflow in container | `mamba install nextflow>=24` |
| | GCE us-east1 + `gs://sra-pub-run-*` | ~50× speedup; **the big win** |
| | Same anti-pattern applies | Layer on Cloud Monitoring no-progress alert |
| | Cloud Logging is always live | One less gotcha on GCP |
| | Same, not cloud-specific | Same fix |
| | GCE PD attaches in any zone, no SECURE/COMMUNITY split | One less footgun |
| | Use file-based startup scripts | Same lesson, easier on GCP |
| | Same, image is the same image | Install curl in startup script, or use Debian 12 host |
| | Not GCP-specific | Same fix: custom UA |
| | Same pattern in startup script | `rm -f $WORKDIR/SUCCESS $WORKDIR/FAILURE` at boot |
| | Machine type implicit (a2- vs c2-) | Less risk; can't be wrong by silence |
| | Zone outage handled by regional MIG | Declarative recovery |
| | Less common on Docker Hub-hosted images; verify in Artifact Registry | Use mambaforge as the base, install at boot |
| | Cloud Logging streams in real time | No cache-busting needed |
| | `--boot-disk-size` is independent of machine type | No coupling |

---

## Sample startup-script: antiSMASH 8 boot (GCE port of test4b)

Save as `antismash8-boot.sh`, upload to `gs://biosymphony-boot-scripts/`, reference as `--metadata=startup-script-url=gs://biosymphony-boot-scripts/antismash8-boot.sh`. This is a direct port of `.runtime/<superpowers-launch>/staging/test4b-antismash8-mambaforge-boot.sh` to GCE conventions.

```bash
#!/bin/bash
# antiSMASH 8 boot script for GCE: port of RunPod test4b
set -euo pipefail

WORKDIR=/var/biosymphony
RESULTS_BUCKET=${RESULTS_BUCKET:-biosymphony-results}
GENOME_URL=${GENOME_URL:-https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_000964.3&rettype=gbwithparts&retmode=text}
ANTISMASH_TAXON=${ANTISMASH_TAXON:-bacteria}

mkdir -p "$WORKDIR" && cd "$WORKDIR"
# Reset sentinels (memory:)
rm -f SUCCESS FAILURE STATUS

write_status() {
 echo "$(date -u +%FT%TZ) | phase=$1" | tee -a STATUS
 # Stream to Cloud Logging
 logger -t biosymphony "phase=$1"
}

trap 'write_status "FAILED: $?"; touch FAILURE; sync; gcloud storage cp -r "$WORKDIR" gs://$RESULTS_BUCKET/$(hostname)/ || true' ERR

# 1. Install mambaforge if not on COS
write_status "install_mambaforge"
if ! command -v mamba >/dev/null 2>&1; then
 curl -L -o /tmp/Mambaforge.sh "https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-Linux-x86_64.sh"
 bash /tmp/Mambaforge.sh -b -p /opt/mambaforge
 export PATH=/opt/mambaforge/bin:$PATH
 echo 'export PATH=/opt/mambaforge/bin:$PATH' >> /etc/profile.d/mambaforge.sh
fi
export PATH=/opt/mambaforge/bin:$PATH

# 2. Install antiSMASH
write_status "install_antismash"
mamba install -n base -c bioconda -c conda-forge -y antismash hmmer prodigal blast

# 3. Download antiSMASH DBs
write_status "db_download"
DB_DIR=$WORKDIR/antismash-dbs-v8
mkdir -p "$DB_DIR"
if [ ! -d "$DB_DIR/pfam" ] || [ ! -d "$DB_DIR/clusterblast" ]; then
 download-antismash-databases --database-dir "$DB_DIR"
fi

# 4. Fetch genome (mambaforge image lacks curl by default: debian-12 host has it)
write_status "fetch_genome"
curl -sS -A "Mozilla/5.0 biosymphony/1.0" -o genome.gbk "$GENOME_URL"
test -s genome.gbk

# 5. Run antiSMASH
write_status "run_antismash"
mkdir -p results
antismash \
 --taxon "$ANTISMASH_TAXON" \
 --cpus "$(nproc)" \
 --output-dir results \
 --databases "$DB_DIR" \
 genome.gbk

# 6. Verify and package
write_status "verify"
test -f results/*.json
test -f results/index.html
ls -lah results/

write_status "archive"
tar -czf results.tar.gz results/
cp results/*.json regions.json || true

# 7. Upload to GCS (analog of RunPod proxy artifact pull)
write_status "upload_to_gcs"
gcloud storage cp results.tar.gz "gs://$RESULTS_BUCKET/$(hostname)/results.tar.gz"
gcloud storage cp regions.json "gs://$RESULTS_BUCKET/$(hostname)/regions.json" || true
gcloud storage cp STATUS "gs://$RESULTS_BUCKET/$(hostname)/STATUS"

# 8. Sentinel + self-stop
write_status "complete"
touch SUCCESS
gcloud storage cp SUCCESS "gs://$RESULTS_BUCKET/$(hostname)/SUCCESS"

write_status "self_stop"
# Use attached service account (no API key needed)
TOKEN=$(curl -sS -H "Metadata-Flavor: Google" \
 http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token \
 | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
NAME=$(curl -sS -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/name)
ZONE=$(curl -sS -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/zone | awk -F/ '{print $NF}')
PROJECT=$(curl -sS -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)

# Capture status code BEFORE writing sentinel (memory:)
HTTP_CODE=$(curl -sS -o /tmp/stop-resp.json -w '%{http_code}' \
 -X POST -H "Authorization: Bearer $TOKEN" \
 "https://compute.googleapis.com/compute/v1/projects/$PROJECT/zones/$ZONE/instances/$NAME/stop")
echo "self_stop_http=$HTTP_CODE" > .self_stop_status
gcloud storage cp .self_stop_status "gs://$RESULTS_BUCKET/$(hostname)/.self_stop_status" || true
```

**IAM prereqs:**
- VM service account needs `roles/compute.instanceAdmin.v1` on the project (to call `instances.stop` on itself).
- VM service account needs `roles/storage.objectCreator` on `$RESULTS_BUCKET`.
- Or, simpler: VM service account = Compute Engine default + grant the above two roles.

**Verification:** After `gcloud compute instances create ...`, poll the GCS bucket:

```bash
RESULTS_BUCKET=biosymphony-results
NAME=antismash8-bsub-demo
while ! gcloud storage ls "gs://$RESULTS_BUCKET/$NAME/SUCCESS" >/dev/null 2>&1; do
 sleep 30
 echo "$(date) | latest STATUS:"
 gcloud storage cat "gs://$RESULTS_BUCKET/$NAME/STATUS" 2>/dev/null | tail -3
done
gcloud storage cp -r "gs://$RESULTS_BUCKET/$NAME/" ./antismash-results/
```

---

## Authoritative URLs

| Topic | URL |
|---|---|
| VM instance pricing | https://cloud.google.com/compute/vm-instance-pricing |
| GPU pricing | https://cloud.google.com/compute/gpus-pricing |
| Spot VMs pricing | https://cloud.google.com/spot-vms/pricing |
| Disk and image pricing | https://cloud.google.com/compute/disks-image-pricing |
| Machine families guide | https://cloud.google.com/compute/docs/machine-resource |
| Startup scripts | https://cloud.google.com/compute/docs/instances/startup-scripts/linux |
| `gcloud compute instances create` | https://cloud.google.com/sdk/gcloud/reference/compute/instances/create |
| Instance metadata server | https://cloud.google.com/compute/docs/metadata/overview |
| Artifact Registry auth | https://cloud.google.com/artifact-registry/docs/docker/authentication |
| Container-Optimized OS | https://cloud.google.com/container-optimized-os/docs |
| Cloud Batch overview | https://cloud.google.com/batch/docs |
| Migrate from Cloud Life Sciences | https://cloud.google.com/batch/docs/migrate-to-batch-from-cloud-life-sciences |
| Cloud Life Sciences deprecation announcement | https://cloud.google.com/life-sciences/docs/release-notes (returns 404, service offline since 2025-07-08) |
| Nextflow on Google Cloud | https://nextflow.io/docs/latest/google.html |
| Nextflow on Cloud Batch (official) | https://cloud.google.com/batch/docs/nextflow |
| Regional MIGs | https://cloud.google.com/compute/docs/instance-groups/regional-migs |
| Sustained-use discounts | https://cloud.google.com/compute/docs/sustained-use-discounts |
| Committed-use discounts | https://cloud.google.com/compute/docs/instances/committed-use-discounts-overview |
| Cloud Storage pricing | https://cloud.google.com/storage/pricing |
| Filestore overview | https://cloud.google.com/filestore/docs/overview |
| Hyperdisk overview | https://cloud.google.com/compute/docs/disks/hyperdisks |
| NCBI SRA on Google Cloud | https://www.ncbi.nlm.nih.gov/sra/docs/SRA-Google-Cloud/ |
| NCBI SRA in the cloud (overview) | https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/ |
| AlphaFold on Vertex AI repo | https://github.com/GoogleCloudPlatform/vertex-ai-alphafold-inference-pipeline |
| AlphaGenome (DeepMind) | https://deepmind.google/blog/alphagenome-ai-for-better-understanding-the-genome/ |
| AlphaGenome Python SDK | https://github.com/google-deepmind/alphagenome |
| dsub (DataBiosphere; Cloud Life Sciences successor for many users) | https://github.com/DataBiosphere/dsub |
| Cloud Workstations | https://cloud.google.com/workstations |

---

## Open questions / next steps

1. **GCS SRA bucket numbering.** NCBI docs mention "any US region" works but don't enumerate `gs://sra-pub-run-N` shards. The sharding scheme is `[0-9]` or similar; first real run should `gcloud storage ls gs://sra-pub-run-1/` etc. to map.
2. **Mambaforge image cold-pull from Docker Hub**, is it cached anywhere in GCE us-central1? RunPod stalls on >5 GB images; we expect Docker Hub on GCE to be reliable but should validate with a 60 s smoke before betting an 8 h pipeline.
3. **Verify Spot eviction frequency for c2-standard-16 in us-central1.** GCP's Spot pricing is dynamic; antiSMASH 8 fits in 10 min but if Spot evicts within 5 min we're worse off than on-demand. Need 5-10 runs of empirical data.
4. **Cloud Batch vs MIG for our scale.** Likely MIG + startup-script is the right starting point. the operational mental model maps to RunPod 1:1. Pivot to Cloud Batch if we go to a many-genome demo (>10 parallel).
5. **HIPAA path.** None of the current BioSymphony GeneCluster campaigns process human data; this is a "when needed" question, not "now."
6. **AlphaFold 3 on GCE A100 80GB.** No official Vertex AI integration as of 2026-05. If we need batch AlphaFold 3, the recipe is: a2-ultragpu-1g Spot + DeepMind's official Docker image + GCS for inputs/outputs. Estimate $1.50 + ~10 min per protein for small targets; ~30 min for large.
