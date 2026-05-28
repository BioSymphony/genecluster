# Neocloud GPU/CPU Providers: Bioinformatics Reference Notes

**Status:** Forward-research. We do **not** have credentials for any of the providers below as of 2026-05-11. This document compares them against our validated RunPod recipe (`docs/biosymphony-antismash-cookbook.md`) so a future operator can dispatch a working pod on any of them inside one hour.

**Reference baseline (RunPod, as of 2026-05):** `cpu5c` (4 vCPU, 16 GB RAM) at ~$0.14/hr; `cpu5g` (4 vCPU, 32 GB) at ~$0.18/hr; H100 PCIe ~$2.59/hr (Community), $2.39/hr (SECURE); A100 80GB ~$1.89/hr; network volume $0.07/GB-mo (<1 TB), $0.05/GB-mo (≥1 TB). Validated tools: antiSMASH 8, DeepBGC, ESM-C (Synthyra), MMseqs2, Foldseek+ProstT5, CLEAN, P450Rdb.

---

## TL;DR: Provider comparison table

All pricing per-hour, on-demand, single-GPU, as of **2026-05**. Marketplace prices fluctuate within the day on Vast.ai and Cudo.

| Provider | H100 80GB | A100 80GB | RTX 4090 | CPU-only | Persistent vol | Custom Docker | Self-stop API | Recommended for |
|---|---|---|---|---|---|---|---|---|
| **RunPod** (baseline) | $2.39, $2.69 | $1.89 | $0.34 | $0.14, $0.18/hr (cpu5c-g) | $0.07/GB-mo | Yes (`dockerStartCmd`) | Yes (`/v1/pods/{id}/stop`) | One-shot bio pipelines, antiSMASH/DeepBGC, < 4h workloads |
| **Vast.ai** | $1.23, $1.87 (marketplace low) | ~$1.50, $2.00 | $0.29, $0.35 (spot $0.25) | Limited. most hosts are GPU-first | Per-host, ~$0.10, $0.20/GB-mo | Yes (GHCR/DH/ECR), `--onstart-cmd` 16 KB | Yes (DELETE `/api/v0/instances/{id}/`) | Cheapest GPU inference, interruptible bulk runs, marketplace flexibility |
| **Lambda Labs** | $3.29 (PCIe) / $4.09, $4.29 (SXM) | $2.79 (SXM) | not offered | not offered | NFS, free for now (region-locked) | **Limited**, image at launch only, not arbitrary Docker entrypoint; Docker is pre-installed on the host | Yes (REST `/instance-operations/terminate`) | H100/H200/B200 jobs that want simplicity + no egress fees |
| **CoreWeave** | $6.16 (normalized from $49.24 8-GPU node) | $2.70 (norm.) | not offered | $0.07, $0.10/core-hr (component-billed) | $0.015, $0.07/GB-mo (4 tiers) | Yes (K8s-native, OCI) | K8s `kubectl delete pod` | Multi-node H100/H200 training, InfiniBand clusters, S3-compatible storage |
| **Cudo Compute** | $1.38, $2.47 (commit $1.79) | $0.78, $1.50 | available | Yes (VM-style) | Yes | Yes (PyTorch images standard) | Yes | Cheap GPU with commit, less mature API |
| **Hyperstack** | $2.40 (SXM) / $1.90 (PCIe spot $1.52) | $1.60 (SXM) / $1.35 (PCIe; spot $1.08) | not offered (RTX A6000 $0.50, RTX Pro 6000 SE $1.80) | $0.35, $3.74/hr by core count | $0.10/TB-hr (~$0.07/GB-mo) | Yes (cloud-init `user_data`) | Yes (REST `DELETE /core/virtual-machines/{id}`) | UK/EU jurisdiction, predictable enterprise pricing |
| **Crusoe Cloud** | $3.90 | $1.65 (PCIe) / $1.95 (SXM) | not offered | $0.04/vCPU-hr (general); $0.09/vCPU-hr (storage-opt) | $0.08/GiB-mo | Yes. Custom images + CCR; `startup_script` field at create | Yes (REST PATCH action=STOP) | Carbon-aware shops, AMD MI300X access ($3.45), cheap CPU |

**Provider-of-choice cheat sheet:**
- **Cheapest GPU inference, one-shot:** Vast.ai marketplace H100 ≈ $1.23, $1.65/hr if reliability score ≥ 90 %.
- **Multi-node H100/H200 training:** CoreWeave (InfiniBand) or Lambda 1-Click Clusters.
- **Carbon-aware / AMD GPUs:** Crusoe Cloud.
- **UK/EU data residency:** Hyperstack.
- **What we already use:** RunPod. keep using for < 4h pipelines unless capacity outages force a pivot.

---

## 1. Vast.ai: marketplace GPU, the obvious RunPod substitute

**Why first:** Vast.ai is the closest functional analog to RunPod and pricing is consistently 30, 50 % cheaper for H100/A100. The marketplace model (independent hosts bidding) means a given GPU price can range from $1.50/hr to $4.00/hr on the same platform; you pick by filtering on reliability score and DLPerf.

### API and CLI

`vastai` CLI (PyPI: `pip install vastai`) plus full Python SDK (`pip install vastai-sdk`). REST API at `https://console.vast.ai/api/v0/` with Bearer-token auth.

Auth:
```bash
vastai set api-key YOUR_KEY    # CLI persists to ~/.config/vastai/
# Or for REST:
curl -H "Authorization: Bearer $VAST_API_KEY" https://console.vast.ai/api/v0/instances/
```

Search for offers (live marketplace query):
```bash
vastai search offers 'gpu_name=H100 num_gpus=1 verified=true \
  reliability>=0.95 direct_port_count>=1 rentable=true' \
  -o 'dph_total-'   # sort by price ascending
```

`reliability>=0.95` is the production threshold to use, the marketplace default UI hides anything < 0.90. For bioinformatics where a 4-hour run wasted is real money, we want **≥ 0.97**.

### Custom Docker image (GHCR / Docker Hub / ECR)

Vast.ai supports custom images from any public registry. For private GHCR we'd add registry credentials via the template settings.

```bash
vastai create instance OFFER_ID \
  --image ghcr.io/<org>/genecluster-runner:latest \
  --disk 50 \
  --onstart-cmd "bash /workspace/boot.sh" \
  --ssh --direct
```

**Critical gotcha:** `--onstart-cmd` is capped at **16 KB**. Same shape as RunPod's `dockerStartCmd` 64 KB limit, but tighter. The base64+gzip + curl-fetch pattern from applies here harder. for any non-trivial boot, stage the script as part of the image or curl it from catbox.moe inside a tiny launcher.

### Persistent storage

Per-host, no managed network volume. Each instance has a disk that survives `stop` (`vastai stop instance ID`) but disk charges continue while stopped. `vastai destroy instance ID` is irreversible, wipes the disk.

Pricing varies per host. Typical: $0.10, $0.20/GB-mo for stopped, lower for running. There's no Vast.ai-managed "network volume" equivalent to RunPod's; if you need a 50 GB reference DB shared across many one-shot runs, build it into the Docker image or pull from S3-compat object storage on each boot.

### Spot / interruptible

Lowest-cost tier. Bid-based: set a max hourly price, the highest active bid on a given machine keeps its instance running, others are paused. Pausing is abrupt, your boot script must be idempotent and checkpoint to disk regularly.

**Use spot for:** stateless GPU inference (Foldseek+ProstT5, ESMplusplus_small) where a paused run can resume from a sentinel.
**Don't use spot for:** antiSMASH/DeepBGC pipelines that need 5, 25 minutes uninterrupted of orderly DB initialization.

### Reliability score, DLPerf, capacity

The reliability score is a 0, 1 number from rolling host uptime data. Hide-below threshold default is 0.90; production threshold should be **0.95+** with a hard floor of 0.97 for jobs > 1 hour. DLPerf is Vast.ai's synthetic GPU benchmark per $; useful to compare A100 vs H100 cost-efficiency for our actual workload.

**No equivalent of RunPod's "container never started" failure mode** because instances boot from raw images directly on bare-metal hosts (not via the registry-stall path RunPod has). The main failure modes are (a) preemption on spot, (b) host going offline mid-run (rare on reliability-95+), (c) `--onstart-cmd` 16 KB overflow.

### Self-stop

```bash
# Inside the pod or from operator:
curl -X DELETE \
  -H "Authorization: Bearer $VAST_API_KEY" \
  https://console.vast.ai/api/v0/instances/${INSTANCE_ID}/
# Or:
vastai destroy instance $INSTANCE_ID
```

Unlike RunPod, the API key is **not** silently injected into the pod env, so the failure mode does not apply. You can self-stop cleanly from inside the container.

### Compliance

SOC 2 Type II certified (under NDA, contact sales for the report). HIPAA-supported workloads on the "Secure Cloud" tier, datacenter partners hold HIPAA / HITRUST / GDPR. For clinical genomics, use Secure Cloud only; the open marketplace is consumer-grade GPUs in random datacenters.

### Concrete quick-start: Foldseek + ProstT5 on Vast.ai

(Substitute for our RunPod recipe at `.runtime/bia-trio-launch/staging/p41-esmcpp-trio-boot-v2.sh`.)

```bash
# 1) Find cheapest H100 with reliability ≥ 0.97
vastai search offers 'gpu_name=H100 num_gpus=1 reliability>=0.97 \
  inet_down>=200 cuda_max_good>=12.4 rentable=true' \
  -o 'dph_total-' | head -5
# Note the OFFER_ID and dph_total (dollars per hour)

# 2) Boot
# Keep provider API keys operator-side; do not pass stop keys into the instance.
vastai create instance $OFFER_ID \
  --image condaforge/mambaforge:latest \
  --disk 60 \
  --onstart-cmd "curl -sSL https://litterbox.catbox.moe/<your_boot>.sh | bash" \
  --ssh --direct

# 3) Get instance_id from response, monitor
INSTANCE_ID=<from above>
vastai show instance $INSTANCE_ID

# 4) Pull artifacts when SUCCESS sentinel appears
vastai copy $INSTANCE_ID:/workspace/results/ ./results/

# 5) Destroy (or have the boot script self-destroy)
vastai destroy instance $INSTANCE_ID
```

**Cost validation, illustrative:** Foldseek+ProstT5 inference for 500 queries on RunPod takes ~25 min on an A100; we'd expect ~20 min on a Vast.ai H100 @ $1.65/hr = **$0.55**. RunPod equivalent was ~$0.79 (A100 PCIe, SECURE). The savings are real, the operational hassle (manual reliability filtering, no managed volume) is the cost.

---

## 2. Lambda Labs Cloud: fixed-price simplicity, H100/H200/B200 focused

**Why it matters:** Lambda is the closest thing to a "boring" GPU cloud. fixed pricing, simple REST API, no marketplace mechanics, no surprise capacity outages. Trade-off: the cheapest H100 is ~2× Vast.ai's spot price, and the deployment model is more "rent a VM, run your own Docker" than "give us a Docker image, we'll run it."

### API and pricing (May 2026)

| Instance | GPU | RAM | Price |
|---|---|---|---|
| `gpu_1x_h100_pcie` | H100 80GB PCIe | 200 GB | **$3.29/hr** |
| `gpu_1x_h100_sxm5` | H100 80GB SXM | 225 GB | **$3.29/hr** (note 1) |
| `gpu_8x_h100_sxm5` | 8× H100 80GB SXM | 1.8 TB | $25.00, $32.00/hr |
| `gpu_1x_a100` | A100 40GB | 200 GB | $1.29, $1.99/hr |
| `gpu_1x_a100_sxm` | A100 80GB SXM | 200 GB | $2.79/hr |
| `gpu_1x_a6000` | RTX A6000 48GB | 100 GB | $1.09/hr |
| `gpu_1x_quadro_rtx_6000` | Quadro RTX 6000 24GB | 100 GB | $0.69/hr |

Note 1: SXM nodes are sold as 8-GPU clusters normally. Per-GPU prices vary $2.99, $4.29 depending on configuration as of 2026-05.

No RTX 4090, no L40S, no CPU-only instances. **Lambda is GPU-only.** If your bio workload is CPU (antiSMASH, MMseqs2 small), Lambda is the wrong platform. stay on RunPod cpu5c.

### REST API

Base: `https://cloud.lambda.ai/api/v1/`, Basic auth with API key as username, blank password (or Bearer in some endpoints; current docs at `https://docs-api.lambda.ai/api/cloud`).

Launch:
```bash
curl -u "$LAMBDA_API_KEY:" -X POST \
  https://cloud.lambda.ai/api/v1/instance-operations/launch \
  -H "Content-Type: application/json" \
  -d '{
    "region_name": "us-west-1",
    "instance_type_name": "gpu_1x_h100_pcie",
    "ssh_key_names": ["my_key"],
    "file_system_names": ["bio-refs-100gb"],
    "name": "antismash-run-1",
    "user_data": "#!/bin/bash\ndocker run --gpus all ghcr.io/<org>/bio:latest bash /boot.sh"
  }'
```

Terminate:
```bash
curl -u "$LAMBDA_API_KEY:" -X POST \
  https://cloud.lambda.ai/api/v1/instance-operations/terminate \
  -H "Content-Type: application/json" \
  -d '{ "instance_ids": ["<id>"] }'
```

**Rate limits:** Not formally documented as of 2026-05. Anecdotally users report soft-limited at a handful of launches per minute; for our workload (1, 5 pods at a time) we will never hit it. If automating a swarm of 50+ launches, paginate and retry on 429.

### Image deployment: important difference vs RunPod

Lambda launches **VMs with Lambda Stack pre-installed (Ubuntu 22.04 + CUDA + PyTorch + Docker + NVIDIA Container Toolkit)**. You do **not** point Lambda at a Docker image. You SSH in (or hand cloud-init `user_data`) and run `docker run` yourself.

This is structurally different from our RunPod / Vast.ai flow:
- RunPod: "Here's my Docker image + start command, RunPod runs the container as the pod root process."
- Lambda: "Here's a GPU VM, you run whatever you want, including docker if you want."

For our existing bundles this means **the boot script lives in `user_data`** and does:

```bash
#!/bin/bash
docker pull ghcr.io/<org>/genecluster-runner:latest
docker run --gpus all --rm \
  -v /lambda/nfs/persistent-storage:/refs \
  -v /home/ubuntu/work:/work \
  ghcr.io/<org>/genecluster-runner:latest \
  bash /work/boot.sh
# Self-terminate
curl -u "$LAMBDA_API_KEY:" -X POST \
  https://cloud.lambda.ai/api/v1/instance-operations/terminate \
  -d '{"instance_ids":["'$(curl -s http://169.254.169.254/latest/meta-data/instance-id)'"]}'
```

### Persistent file system (the killer feature)

Lambda's persistent filesystems are **NFS, free as of 2026-05** (pricing TBD per the docs. "see billing page"; community reports it remains free at small scales). Created in the Lambda Console or via API. Mounted at `/lambda/nfs/persistent-storage` automatically.

**Region constraint** is the gotcha: filesystem and instance must be in the same region. You **cannot** attach to a running instance. must specify `file_system_names` at launch time.

Capacity: Up to 8 EB per filesystem, 24 filesystems per account (Texas region limited to 10 TB).

For our biology workloads, this is the single best feature on Lambda: stage a 100 GB reference DB once, mount free into every subsequent H100 run. No equivalent on Vast.ai. RunPod network volumes ($0.07/GB-mo for 1 TB = $70/mo) would be free here.

### What Lambda is bad at

- **No CPU-only instances**, wrong tool for antiSMASH/MMseqs2 small jobs.
- **Capacity scarcity** on H100/H200 in popular regions during US business hours. The `instance-types` endpoint will report `instances_in_capacity = false` and the launch fails. Workaround: poll multiple regions, or accept H100-PCIe at higher cost when SXM is unavailable.
- **No `--cpus` / sub-GPU fractional billing**, you pay for the whole node.
- **NFS is region-locked**, can't move a populated filesystem between us-west-1 and us-east-1.

### Compliance

SOC 2 Type II + ISO 27001. Lambda publishes its compliance reports more openly than Vast.ai.

---

## 3. CoreWeave: Kubernetes-native, enterprise, multi-node training

**Skip for one-shot bio runs.** CoreWeave is built around running large training clusters on InfiniBand-connected H100/H200 nodes. The pricing model bills GPU + CPU + RAM + storage as **separate line items**, so a "$4.76/hr H100 PCIe" advertised rate becomes ~$6/hr after you provision the matching CPU and RAM. They publicly state 8-GPU HGX H100 nodes at $49.24/hr ($6.16/hr/GPU normalized). On-demand single-GPU rentals do exist on "CoreWeave Classic" but the platform is optimized for committed multi-month contracts that can be 60 % cheaper.

### When CoreWeave is the answer

- You need a **multi-node H100/H200 cluster with InfiniBand** for distributed training of an ESM-3 size model or AlphaFold-3 retraining run.
- You have a **6-figure annual GPU budget** and want reserved capacity that won't get bumped by a marketplace.
- You need **S3-compatible object storage** in the same datacenter as your compute, with no egress fees and managed VAST Data backend. Endpoint: `https://cwobject.com`.
- You're running production AI inference workloads with **SOC 2 / HIPAA / ISO 27001** all in scope, on certified hardware.

### When CoreWeave is NOT the answer

- Anything < 8 GPUs.
- Anything < 1 week wall time.
- You don't want to deal with `kubectl` and PVCs.

### Quickstart pointers (if it ever becomes relevant)

- Onboarding: **self-service signup gives $50 in free credits** (2026); no minimum commitment for on-demand. Enterprise reserved contracts negotiated via sales (typically 6+ month).
- Storage: 4 tiers, hot $0.06/GB-mo, warm $0.03/GB-mo, cold $0.015/GB-mo, archive $0.0125/GB-mo; distributed file storage $0.07/GB-mo. No ingress/egress charges.
- Kubernetes: Bring-your-own manifests; storage class `shared-vast` for distributed file storage, `block-nvme-ord1` etc. for per-pod NVMe.
- Custom images: Yes, any OCI registry (GHCR, Docker Hub, internal Harbor).
- "Regions" become "Availability Zones", different names from AWS (don't paste `us-east-1` into the SDK).

---

## 4. Cudo Compute: marketplace-style, less mature, cheap commits

**Position:** Cheaper than RunPod for H100/A100 when you commit, on par with Vast.ai for short runs. Less mature API than RunPod, less community than Vast.ai. Worth keeping on the bench for cost validation but not the place to dispatch our first new campaign.

### Pricing (as of 2026-05)

| GPU | On-demand | Commit |
|---|---|---|
| H100 80GB | $1.38, $2.47/hr (varies by region/host) | $1.79/hr (3+ month) |
| A100 80GB | $0.78, $1.50/hr | (commit unlisted) |
| RTX 4090 | available, marketplace pricing |  |
| Commit discounts | up to 50% with 1/3/6/12/36-month commit |

CPU-only VMs available. Storage and S3-compatible object storage on the platform.

### Custom Docker support

PyTorch Docker images on NVIDIA Ampere supported as a standard pattern. Custom images from any public registry. CLI exists (`cudoctl`) but it's less complete than `vastai` or `runpodctl`. REST API is documented at the `Quote on request` level for some plans, **as of 2026-05 their public pricing page hides on-demand-without-commit numbers and requests quotes**, which is a warning sign for "self-service this thing in an hour from a script."

### When to try Cudo

- You have a 3+ month committed bioinformatics workload (e.g., monthly campaign cohorts) and the 50% commit discount on a fleet of A100s would actually save money.
- You hit a Vast.ai capacity outage on H100s and want a fallback marketplace.

### When to skip Cudo

- One-shot experimental runs, the friction to get a real on-demand price is higher than just using RunPod or Vast.ai.

---

## 5. Hyperstack: UK / EU-jurisdiction GPU, predictable enterprise pricing

**Position:** Fixed-price GPU cloud out of UK (parent: NexGen Cloud). Hyperstack is what you choose when your bio data needs to stay in EU/UK jurisdiction for GDPR or contractual reasons. Pricing is mid-tier. cheaper than Lambda, more expensive than Vast.ai marketplace, comparable to RunPod SECURE.

### Pricing (2026-05)

| GPU | On-demand | Spot |
|---|---|---|
| H100 80GB SXM | $2.40/hr | not offered |
| H100 80GB PCIe | (only listed as spot) | $1.52/hr |
| A100 80GB SXM | $1.60/hr | not offered |
| A100 80GB PCIe | $1.35/hr | $1.08/hr |
| RTX Pro 6000 SE | $1.80/hr |, |
| RTX A6000 48GB | $0.50/hr |, |
| L40 | $1.00/hr |, |
| CPU-only (4 vCPU) | $0.35/hr |, |
| CPU-only (32 vCPU) | $3.74/hr |, |
| Storage | ~$0.07/GB-mo (= $0.10/TB-hr) | |

Reserved discount ~15, 30%. No RTX 4090.

### API

REST at `https://infrahub-api.nexgencloud.com/v1/`. Bearer auth.

Sample VM create:
```bash
curl -X POST https://infrahub-api.nexgencloud.com/v1/core/virtual-machines \
  -H "api_key: $HYPERSTACK_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "antismash-1",
    "environment_name": "default-CANADA-1",
    "image_name": "Ubuntu Server 22.04 LTS",
    "key_name": "ssh-key-1",
    "flavor_name": "n1-A100x1",
    "user_data": "#cloud-config\nruncmd:\n  - docker run --gpus all ghcr.io/<org>/bio:latest bash /boot.sh"
  }'
```

`user_data` accepts cloud-init YAML, which is the cleanest way to dispatch a Docker container at boot. Comparable in spirit to RunPod's `dockerStartCmd` but you wrap your real boot in cloud-init.

Terminate via DELETE on the VM ID, same shape as Lambda/Crusoe.

### Custom images

Save snapshots of running VMs as custom images, redeploy. Pull from public registries via `docker pull` in user-data, same as Lambda. SDKs in Go and Python; Terraform provider exists.

### Regions

Norway (primary), Iceland, Canada (Montreal), and UK locations referenced. EU data residency is the headline.

### When to use Hyperstack

- Bio data with GDPR or UK NHS-adjacent contractual constraints.
- Predictable enterprise pricing without marketplace volatility.
- You want CPU-only and GPU options on the same platform with the same auth (Lambda doesn't do CPU).

### When not

- You want the cheapest H100 in absolute terms, Vast.ai wins.
- US-only data residency is fine and RunPod already works.

---

## 6. Crusoe Cloud: flare-gas-powered, AMD MI300X access, cheap CPU

**Position:** Climate-aligned datacenters in Iceland and Texas, powered by flare-gas-captured power. Crusoe is the only neocloud here that offers **AMD MI300X (192 GB)** at scale and at a reasonable price ($3.45/hr). relevant if you have a workload that maps better to ROCm than CUDA, but for our bio toolset, CUDA-only tools (CLEAN, ProstT5, ESM-C) tie us to NVIDIA.

### Pricing (2026-05)

| Resource | Price |
|---|---|
| H100 80GB | $3.90/GPU-hr |
| H200 141GB | $4.29/GPU-hr |
| A100 80GB SXM | $1.95/GPU-hr |
| A100 80GB PCIe | $1.65/GPU-hr |
| L40S | Contact sales |
| AMD MI300X 192GB | $3.45/GPU-hr |
| CPU (general-purpose) | $0.04/vCPU-hr |
| CPU (storage-optimized) | $0.09/vCPU-hr |
| Persistent disk | $0.08/GiB-mo |
| Egress | $0 (no egress fees) |

Per-minute billing on all resources. Spot pricing exists but "contact sales" for rates.

### API and CLI

Mature `crusoe` CLI (open-source at `github.com/crusoecloud/cli`). Bearer-token REST API at `https://api.crusoecloud.com/v1alpha5/` (the version moves; check the changelog).

Quick VM create with startup script:
```bash
crusoe compute vms create \
  --name antismash-1 \
  --type a100-80gb.1x \
  --image ubuntu-22.04 \
  --location us-southcentral1-a \
  --ssh-key "$(cat ~/.ssh/id_ed25519.pub)" \
  --startup-script ./boot.sh
```

Or via REST POST `/projects/{project_id}/compute/vms/instances` with body:
```json
{
  "name": "antismash-1",
  "type": "a100.1x",
  "image": "ubuntu:22.04",
  "location": "us-southcentral1-a",
  "ssh_public_key": "ssh-rsa AAAA...",
  "startup_script": "#!/bin/bash\ndocker run --gpus all ghcr.io/<org>/bio:latest bash /boot.sh"
}
```

Self-stop via REST PATCH on the VM with `{"action":"STOP"}`, or DELETE for full destruction. The CLI offers `crusoe compute vms stop|delete`.

### Custom Docker

Two paths:
1. **Crusoe Container Registry (CCR):** Push your image to `registry.<location>.ccr.crusoecloudcompute.com/<repo>.<first-8-of-project-id>`, then pull from VMs.
2. **External registries** (GHCR, Docker Hub): `docker pull` in your startup script. CCR is optional, not required.

### Custom OS images

You can snapshot a running VM and create a "custom image" usable for future launches, similar shape to Hyperstack. `crusoe compute images create` is the syntax.

### When to use Crusoe

- You want **cheap CPU instances at $0.04/vCPU-hr** with a real network volume. undercuts RunPod's cpu5c by 4×.
- You want **MI300X** for an ROCm-compatible workload (none in our current bio toolset. but worth flagging for future use).
- You care about renewable / flare-gas-aligned compute as a procurement criterion.

### When not

- H100 at $3.90/hr is more expensive than Vast.ai, RunPod, Hyperstack, and Cudo. Crusoe's value isn't H100 price-leadership.

---

## 7. Gotcha translation: RunPod memory entries → neocloud analogs

| RunPod gotcha (memory ID) | Vast.ai | Lambda | CoreWeave | Cudo | Hyperstack | Crusoe |
|---|---|---|---|---|---|---|
| `large_image_stall_pattern` (5+ GB image, runtime=null) | Less common, bare-metal pull; if host slow, low-reliability hosts can stall | Doesn't apply, you `docker pull` after VM boot, see exit code immediately | Doesn't apply, K8s pull errors surface in pod events | Similar marketplace risk on slow hosts | Doesn't apply, cloud-init shows pull failures | Doesn't apply, same as Lambda model |
| `mambaforge_image_lacks_curl_wget` | Same, image-side concern, not provider-specific | Same, but base AMI has curl, Docker is post-pull | Same | Same | Same | Same |
| `dockerstart_avoid_inline_heredocs` (64 KB limit) | Vast.ai `--onstart-cmd` is **16 KB** (tighter). same workaround | N/A (VM model, no size limit on user_data beyond cloud-init 16 KB) | N/A | Probably similar marketplace limit | cloud-init 16 KB practical | startup_script ~16 KB practical |
| `runpod_injects_stale_apikey` | Does NOT apply, Vast doesn't inject API key | Does NOT apply, Lambda uses instance metadata | N/A | N/A | N/A | N/A |
| `runpod_proxy_caches_get_responses` | N/A, no managed proxy; SSH or direct port | N/A, SSH only | N/A, your own ingress | N/A | N/A | N/A |
| `runpod_network_volumes_secure_only` | No managed volume product | NFS region-locked (analog) | PVC region-locked (analog) | Yes, with regional pinning | Yes, region-locked | Yes, region-locked |
| `runpod_us_ks_2_secure_volume_outage` (DC-specific stall) | Per-host outages; reliability filter dodges | Less common, fewer DCs, larger inventory | Multi-AZ failover possible | Marketplace can hide outages | Multi-region failover | Multi-region failover |
| `runpod_cpu_gpu_secure_capacity` | Filter by reliability + DLPerf | "capacity false" surfaces cleanly | Reserved tier avoids | Marketplace fluidity | Public pricing implies real capacity | Capacity public; per-minute |
| `runpod_gpu_pod_ncbi_bandwidth_slow` (1, 4 MB/s NCBI) | **Pre-flight check needed**, varies wildly by host inet_down. Filter `inet_down>=200` (Mbps). Hosts publishing 1 Gbps+ deliver real speed. | Lambda has no egress fees and uplinks are typically 10, 25 Gbps; NCBI bandwidth should be 10, 50 MB/s typical | N/A (cluster) | Per-host marketplace risk | Predictable EU bandwidth | Strong (10+ MB/s NCBI typical) |
| `pod_http_server_must_start_early` | Same pattern, start an HTTP server early for monitor pulls, or use SSH-based pull | Same | Same (K8s service) | Same | Same | Same |
| `monitor_must_detect_no_progress` | Same: poll critical-path file sizes via SSH, alert on 3 heartbeats without growth | Same | Same | Same | Same | Same |

**Net:** Most failure-mode gotchas in our RunPod memory either don't apply or have a clean analog. The biggest divergence is the **container model**:
- RunPod: container is the pod (`dockerStartCmd` runs as PID 1).
- Vast.ai: container is the instance, closest analog to RunPod.
- Lambda / Hyperstack / Crusoe / CoreWeave: instance is a VM; container is spawned by your `user_data` / `startup_script`, adds a layer but makes self-stop and debugging easier.

---

## 8. Decision tree

**"I have an H100 inference job for 2 hours (e.g., Foldseek+ProstT5 batch on 10 k queries)"**
→ **Vast.ai** marketplace, reliability ≥ 0.97, expect ~$3 total. Fallback: RunPod H100 SECURE if Vast capacity is tight.

**"I have an antiSMASH/DeepBGC CPU run for 5, 25 minutes"**
→ **RunPod cpu5c** (validated cookbook). Crusoe CPU at $0.04/vCPU-hr is the cheapest in absolute terms but adds an unvalidated path; don't pivot from RunPod here unless you have ≥ 100 runs to spread the setup cost over.

**"I have a 50 GB persistent reference DB and run 30 jobs/month against it"**
→ **Lambda Labs** (free NFS) for GPU jobs; **RunPod network volume** ($3.50/mo for 50 GB) for CPU jobs. Vast.ai isn't a good fit. no managed volume.

**"I need multi-node H100 InfiniBand for ESM-3 retraining"**
→ **CoreWeave** (or Lambda 1-Click Clusters). Talk to sales.

**"I need EU/UK data residency for a clinical genomics campaign"**
→ **Hyperstack** primarily, **Crusoe** Iceland as alternative.

**"I want the cheapest possible CPU pod for a 1-hour MMseqs2 search"**
→ **Crusoe** at $0.04/vCPU-hr × 4 vCPU × 1 hr = $0.16, OR **RunPod cpu5c** at $0.14/hr (validated). About a wash. stay on RunPod.

**"AMD MI300X for ROCm-compatible bio workload"**
→ **Crusoe** ($3.45/hr). only neocloud here that offers it.

---

## 9. When to use a neocloud over RunPod

1. **Cost arbitrage** on H100/A100 GPU work. Vast.ai marketplace is genuinely 30, 50 % cheaper for non-spot, and we should benchmark a small representative workload (Foldseek inference on 500 queries) on Vast.ai to validate end-to-end cost parity, including the operational overhead.
2. **Persistent reference DBs you re-use 10+ times**, Lambda NFS at $0/mo (or Crusoe $0.08/GiB-mo) beats RunPod network volume by a wide margin once amortized.
3. **EU/UK data residency**, RunPod's DCs are US-heavy. Hyperstack or Crusoe Iceland is the right answer.
4. **Multi-node InfiniBand training**, CoreWeave or Lambda Clusters; RunPod can't do this well.
5. **A given RunPod capacity outage is blocking work**, Vast.ai is the lowest-friction immediate failover.

## 10. When NOT to use a neocloud over RunPod

1. **Validated bio recipes already work on RunPod**, our antiSMASH/DeepBGC cookbook is debugged; moving it to Vast.ai means re-validating the boot sequence under their 16 KB onstart limit and their different proxy/SSH model. Total cost of validation is multiple hours of operator time; the per-run savings need to amortize against that.
2. **Short pipelines (< 30 min)**, the dispatch overhead is similar; the per-run cost difference is cents. Stay on what works.
3. **You need a managed HTTP proxy URL** (RunPod's `*.proxy.runpod.net`). Vast.ai and Lambda use SSH or open-port forwarding; you'd need to stand up your own ingress.
4. **You need `dockerStartCmd` to BE the pod** (rather than wrapping a VM that then runs Docker). Only Vast.ai matches RunPod's container-is-instance model; others require an extra layer.

---

## 11. Risk profile: neocloud vs hyperscaler / RunPod

| Risk | RunPod | Vast.ai | Lambda | CoreWeave | Cudo | Hyperstack | Crusoe |
|---|---|---|---|---|---|---|---|
| SOC 2 | Yes (Type II) | Yes (Type II, NDA) | Yes (Type II) | Yes (Type II) | (partial) | (in progress) | (partial) |
| HIPAA | Secure tier | Secure cloud | Available | Available | n/a | n/a | n/a |
| ISO 27001 | (partial) | Yes | Yes | Yes | n/a | n/a | n/a |
| Capacity for H100 | Frequent outages on US-KS-2 | Marketplace fluid | Often capacity-tight in popular regions | Reserved tier solves | Marketplace fluid | Stable EU | Stable |
| Public outage cadence | 1, 2x/quarter we've hit it | Per-host, not platform | 1, 2x/year publicized | Rare | Less publicized | Less data | Less data |
| Self-service signup | Yes | Yes | Yes | Yes ($50 credit) | Yes | Yes | Yes |
| Less mature than hyperscaler | Yes | Yes | Yes | Less so (PE-backed scale) | Yes | Yes | Yes |
| Marketplace = unknown hosts | No | **Yes** (DC-vetted on Secure Cloud) | No | No | Partial | No | No |

For **clinical genomics on patient data**, the right move is RunPod SECURE or Lambda or Hyperstack. anything with explicit HIPAA BAA available. Vast.ai marketplace open tier is **not** appropriate for PHI.

---

## 12. References

Pricing references (verify before any real run; marketplace prices are stale within 24 hours):
- [Vast.ai live pricing](https://vast.ai/pricing), marketplace, refresh always
- [Lambda Cloud pricing](https://lambda.ai/pricing)
- [CoreWeave pricing](https://www.coreweave.com/pricing)
- [Cudo Compute pricing](https://www.cudocompute.com/pricing)
- [Hyperstack GPU pricing](https://www.hyperstack.cloud/gpu-pricing)
- [Crusoe Cloud pricing](https://www.crusoe.ai/cloud/pricing)
- [RunPod pricing](https://www.runpod.io/pricing)
- [getdeploying.com H100 comparison](https://getdeploying.com/gpus/nvidia-h100), cross-provider table

API and CLI:
- [Vast CLI on GitHub](https://github.com/vast-ai/vast-cli) and [Python SDK on PyPI](https://pypi.org/project/vastai/)
- [Lambda Cloud API docs](https://docs.lambda.ai/api/cloud)
- [Lambda filesystems](https://docs.lambda.ai/public-cloud/filesystems/)
- [Crusoe CLI on GitHub](https://github.com/crusoecloud/cli) and [API reference](https://docs.crusoecloud.com/api/)
- [Hyperstack API reference](https://docs.hyperstack.cloud/docs/api-reference/)
- [CoreWeave object storage S3 compatibility](https://docs.coreweave.com/products/storage/object-storage/reference/object-storage-s3)

Compliance:
- [Vast.ai compliance](https://vast.ai/compliance)
- [Vast.ai SOC 2 Type II announcement](https://vast.ai/article/vast-soc2-typeII-certification)

Our existing RunPod baseline:
- `docs/biosymphony-antismash-cookbook.md`
- `docs/runpod-pipeline-dispatch-runbook.md`

---

**Next concrete step when this matters:** Pick one of {Vast.ai H100, Lambda H100 PCIe, Hyperstack H100 PCIe spot} and run an existing Foldseek+ProstT5 batch end-to-end. Measure: (a) dispatch-to-first-result wall time, (b) total cost, (c) any failure modes not in this doc. Update this file with the validated path. Until that validation exists, **RunPod remains the canonical bio runtime** and this doc is forward-research only.
