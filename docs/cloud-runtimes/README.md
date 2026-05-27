# Cloud-runtime reference docs for BioSymphony bio-tools

**Last updated:** 2026-05-11 (forward-research, no validated dispatches yet on any of these clouds).
**Canonical compute platform today:** RunPod. The docs in this directory describe how to port if a use case emerges that RunPod can't serve.

## Doc index

| Doc | Scope |
|---|---|
| [`aws-bio-tools.md`](aws-bio-tools.md) | AWS EC2 / S3 / EBS / Batch / HealthOmics, 5,991 words |
| [`gcp-bio-tools.md`](gcp-bio-tools.md) | GCP Compute Engine / GCS / PD / Batch (Cloud Life Sciences deprecated 2025-07), 5,728 words |
| [`neocloud-bio-tools.md`](neocloud-bio-tools.md) | Vast.ai, Lambda Labs, CoreWeave, Cudo, Hyperstack, Crusoe, 4,813 words |
| Reference (RunPod canonical): [`../biosymphony-antismash-cookbook.md`](../biosymphony-antismash-cookbook.md) | Validated end-to-end recipe, the pattern all three docs above translate from |

## TL;DR: RunPod stays default

| Dimension | RunPod | AWS on-demand | GCP on-demand | Vast.ai bid | Lambda fixed |
|---|---|---|---|---|---|
| 4-vCPU 32-GB CPU pod | $0.184/hr (cpu5g) | ~$0.68/hr (c6i.4xlarge) | ~$0.42/hr (c2-standard-4 + RAM) | ~$0.10, 0.20/hr | n/a (no CPU) |
| A100 80GB | $1.89/hr | $3.67/hr ($1.10 spot) | $3.67/hr ($1.10 spot) | $0.80, 1.40/hr | $1.29/hr |
| H100 80GB | $2.79/hr | $7.20/hr ($3.00 spot) | ~$11/hr ($3 spot) | $2.00, 2.40/hr | $2.49/hr |
| Persistent vol | $0.10/GB-mo | $0.08/GB-mo (EBS gp3) | $0.10/GB-mo (PD-bal) | $0.02, 0.10/GB-mo | included w/ NFS |
| Boot-payload limit | 64 KB (gz+b64) | 16 KB (use S3 fetch) | unlimited (gs:// startup-script-url) | 16 KB | SSH-driven |
| SOC 2 / HIPAA | SOC 2 Type II (2024) | SOC 2 / HIPAA / ISO | SOC 2 / HIPAA / ISO | ⚠️ marketplace, no | SOC 2 Type II |

RunPod's price advantage holds for both CPU and GPU vs hyperscaler on-demand. Vast.ai marketplace bids can undercut RunPod on GPU but with reliability-score discipline (≥0.97).

## Decision tree

```
Want to port a workload?
│
├── Is the workload bandwidth-bound on NCBI / SRA?  (download dominates compute)
│     └─ YES → GCP (`gs://sra-pub-run-*`) or AWS (`s3://ncbi-sra-pub-run-*`)
│              Same-region pulls are free + ~50× faster than RunPod's 1, 4 MB/s
│
├── Need multi-node InfiniBand training?  (rare for our work)
│     └─ YES → CoreWeave (only neocloud with InfiniBand at scale)
│
├── Large persistent reference dataset, infrequent compute?
│     └─ YES → S3 / GCS storage ($0.023/GB-mo) + RunPod compute pulls per-job
│              4, 5× cheaper than keeping a RunPod network volume hot
│
├── Need auditable infra (SOC 2 / HIPAA, clinical PHI, regulated data)?
│     └─ YES → AWS or GCP (NOT Vast.ai marketplace)
│              RunPod has SOC 2 Type II as of 2024, fine for most cases
│
├── Need a managed AlphaFold / ESMFold pipeline?
│     └─ YES → AWS HealthOmics Ready2Run (only those two are managed)
│
├── Big GPU job, looking to undercut RunPod on price?
│     └─ Spot A100 → AWS or GCP at ~$1.10/hr (vs RunPod $1.89/hr)
│        Vast.ai bid → $0.80, 1.40/hr (with reliability ≥0.97)
│        Lambda fixed → $1.29/hr (simplest API; no CPU-only support)
│
└── Otherwise → STAY ON RUNPOD
      Validated recipes ship for RunPod; CPU is 3, 5× cheaper; on-demand GPU is 3, 10× cheaper.
```

## Architectural deltas to remember when porting

These are the patterns that change when you leave RunPod. Each is documented in detail in the per-cloud doc.

1. **Boot payload size**, RunPod's `dockerStartCmd` is 64 KB. AWS UserData is 16 KB (use `s3://` fetch). GCP startup-script via `gs://` is unlimited. Vast.ai `--onstart-cmd` is 16 KB.
2. **Self-stop API**, RunPod has a clean `POST /v1/pods/<id>/stop`. AWS uses `aws ec2 stop-instances` (needs IAM permission); GCP uses `gcloud compute instances stop` (needs SA permission). All three clouds also support instance-side `shutdown -h +<min>` as a fallback.
3. **Stale credential injection**, RunPod injects a stale `RUNPOD_API_KEY` into the pod env (per). AWS / GCP avoid this entirely via instance profiles + IMDSv2 / metadata-server. Lambda doesn't inject anything. **This category of footgun disappears on hyperscalers.**
4. **Public artifact-pull URL**, RunPod gives us free `*.proxy.runpod.net` URLs for pod-side HTTP servers. **No other cloud here offers this.** Move to SSH-based artifact pulls or stand up your own ingress.
5. **Persistent volume model**, RunPod network volumes are SECURE-only (per). AWS EBS attaches anywhere within an AZ; GCP PD attaches within a zone; Lambda's NFS is region-locked. None of the others have RunPod's specific SECURE-vs-COMMUNITY split.
6. **Image-pull stalls**, RunPod stalls on large GHCR images (>5 GB),. ECR + AWS, Artifact Registry + GCP, and CoreWeave handle large images cleanly. Vast.ai inherits RunPod-like risk because the marketplace hosts run Docker via various backends.
7. **NCBI bandwidth**, 1, 4 MB/s on RunPod GPU pods,. AWS / GCP get free same-region Open Data mirrors at 100+ MB/s.

## Open follow-ups (none blocking)

- **Benchmark Foldseek end-to-end on Vast.ai vs RunPod** for cost parity. The neocloud doc projects $0.10/hr CPU and $0.80/hr A100, but no real workload has been timed yet.
- **Validate GCP free same-region SRA download** for one of our prefetch-heavy campaigns (e.g., a Houttuynia re-run) to confirm the 50× bandwidth improvement projection.
- **Confirm Crusoe CPU pricing amortizes** for our short (<2 h) pipelines. The $0.04/vCPU-hr rate is appealing but boot/teardown overhead may swamp it.
- **Vast.ai reliability-score floor**, pick a concrete threshold (≥0.97 is the doc's recommendation) and write it into any future dispatch wrapper.

## Memory cross-references that apply to all three clouds

These RunPod-flavored memories carry forward as design constraints regardless of target cloud:
