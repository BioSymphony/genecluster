# AWS EC2 + S3 for BioSymphony Bio-Tool Workloads: Reference Notes

**Status:** forward-research, **not** validated on real runs. No AWS credentials in the repo.
**Audience:** an operator who knows our RunPod cookbook (`biosymphony-antismash-cookbook.md`) and wants the cheapest path to "dispatch a working pod on AWS in under an hour."
**Pricing baseline:** 2026-05 published rates in `us-east-1` (N. Virginia). Verify on the AWS console before any real dispatch; AWS adjusts rates frequently and the search results below already show movement of ±20-45% on GPU instances inside the past 12 months.

If you've just opened this doc cold, read `docs/biosymphony-antismash-cookbook.md` first, every section here is a translation of a pattern from that doc. If a pattern below feels arbitrary, the rationale lives in the cookbook or in `MEMORY.md`.

---

## 1. RunPod → AWS pattern-translation summary

| RunPod pattern | AWS analog | Notes |
|---|---|---|
| `POST /v1/pods` with `imageName` + `dockerStartCmd` | `aws ec2 run-instances` with AMI + UserData **OR** EC2 Launch Template | Launch Template lets you version configs (Spot fallback, multi-AZ); RunInstances is fine for one-shots. |
| `cpuFlavorIds: [cpu5c, cpu5g, ...]` | `--instance-type c6i.4xlarge` (or via Mixed Instances Policy in Auto Scaling) | Single field, no "flavor pool". To get pool-like behavior use an Auto Scaling group MIP or AWS Batch compute environment. |
| `containerDiskInGb: 30` | `BlockDeviceMapping` → EBS gp3 volume | EBS is per-volume billed; reuse across runs via AMI snapshots. |
| RunPod Network Volume (~$0.10/GB-month, SECURE-only) | **EBS gp3** (per-AZ, $0.08/GB-mo) OR **EFS Standard** ($0.30/GB-mo, multi-AZ, NFS) OR **S3** ($0.023/GB-mo) | See §4 decision tree. |
| `POST /v1/pods/<id>/stop` (self-stop from inside container) | `aws ec2 stop-instances --instance-ids $(curl -s 169.254.169.254/latest/meta-data/instance-id)` with IMDSv2 token | Needs an IAM instance profile with `ec2:StopInstances` (scoped to self via tag/ARN). Alternative: `sudo shutdown -h now` if the instance is configured to stop (not terminate) on OS shutdown via `InstanceInitiatedShutdownBehavior=stop`. |
| `dockerStartCmd` 64 KB POST limit (we gzip+b64) | **UserData 16 KB limit** (base64-encoded), enforced server-side | Tighter than RunPod. Pattern: tiny UserData fetches the real script from S3. See §6. |
| Provider stop key passed at create | IAM role + IMDSv2, **never** ship `AWS_ACCESS_KEY_ID` in UserData | See MEMORY: -> AWS equivalent is "stale credentials shipped to the instance"; instance profiles avoid this category entirely. |
| `cloudType: "SECURE"` + `dataCenterIds: [...]` widening | Multi-AZ Auto Scaling group or AWS Batch compute env (built-in) | AWS doesn't have a "SECURE" vs "COMMUNITY" split; AZ diversification + Spot fallback gives equivalent capacity recovery. |
| `computeType: "CPU"` (must be explicit, else GPU billing) | **Just pick the right instance family** (`c6i.*` = CPU, `g5.*`/`p4d.*`/`p5.*` = GPU). No silent billing mode. | The closest AWS footgun is "I asked for `g5.xlarge` for a CPU job and burned A10G rates"; it's user error, not a hidden default. |
| `condaforge/mambaforge:latest` default (RunPod stalls on >5 GB GHCR) | Standard AMI (`Amazon Linux 2023` or `Ubuntu 22.04 LTS`) + Docker daemon, **OR** ECR pulls | EC2 has no analog stall. it boots the kernel, not the container. Container is `docker run` after boot. ECR public BioContainers gallery is being deprecated; use [Seqera Containers](https://seqera.io/containers/) or sync to a private ECR. |
| Boot phase via `phase=…` in `STATUS` file + `python3 -m http.server` proxy poll | CloudWatch Logs (push) **or** the same `python3 -m http.server` pattern + a public IP / SSM Session Manager | CloudWatch Logs is the "right" answer for production; the http-server hack still works in dev and avoids IAM friction for a one-shot. |
| RunPod proxy GET caches (`?cb=$RANDOM`) | S3 GET is not cached by AWS infra | If you proxy via CloudFront or use the http-server pattern, cache-bust applies. Direct S3 GETs are fine. |
| ~1-4 MB/s from NCBI on GPU pods | **Same external bandwidth ceiling**, but free same-region pull from public-data S3 buckets (NCBI SRA, BLAST DBs, UniProt, etc.) | Big win: pre-staged Open Data mirrors run at multi-Gbps in-region. §3 lists the relevant buckets. |
| `runtime.uptimeInSeconds=-1` stall pattern | "Instance status check failed" / `InsufficientInstanceCapacity` errors | AWS surfaces failures more explicitly; multi-AZ launch templates self-recover. |

---

## 2. Quick-start: antiSMASH 8 on a `c6i.4xlarge` (mirror of `test4b`)

This block dispatches the same workload as our validated RunPod run (B. subtilis 168 → mambaforge → bioconda antismash → 15 regions in ~5 min). Total cost on AWS ≈ **$0.08-0.12** at on-demand `c6i.4xlarge` ($0.68/hr × 0.1 hr) plus negligible S3/EBS. Spot would cut compute ~70%.

### One-time setup (run on your laptop, ~10 min)

```bash
# 1) Pick a region. us-east-1 is the cheapest and the SRA/BLAST mirrors live there.
export AWS_REGION=us-east-1

# 2) Create an S3 bucket for boot scripts + results.
aws s3 mb s3://biosymphony-runs --region $AWS_REGION

# 3) Create the IAM role + instance profile so the instance can:
# - pull from public S3 buckets (no-sign-request works too)
# - write results to s3://biosymphony-runs/
# - stop itself via ec2:StopInstances
cat > trust.json <<'EOF'
{ "Version": "2012-10-17", "Statement": [
 {"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}
]}
EOF
aws iam create-role --role-name BioSymphonyWorker --assume-role-policy-document file://trust.json

cat > policy.json <<'EOF'
{ "Version": "2012-10-17", "Statement": [
 {"Effect":"Allow","Action":["s3:GetObject","s3:ListBucket"],"Resource":"*"},
 {"Effect":"Allow","Action":["s3:PutObject","s3:PutObjectAcl"],"Resource":"arn:aws:s3:::biosymphony-runs/*"},
 {"Effect":"Allow","Action":"ec2:StopInstances","Resource":"*",
 "Condition":{"StringEquals":{"ec2:ResourceTag/biosymphony":"worker"}}}
]}
EOF
aws iam put-role-policy --role-name BioSymphonyWorker \
 --policy-name BioSymphonyWorker --policy-document file://policy.json
aws iam create-instance-profile --instance-profile-name BioSymphonyWorker
aws iam add-role-to-instance-profile \
 --instance-profile-name BioSymphonyWorker --role-name BioSymphonyWorker

# 4) Create a security group that allows only your IP for SSH (optional debug access).
MY_IP=$(curl -s https://checkip.amazonaws.com)/32
aws ec2 create-security-group --group-name biosymphony-sg --description "BioSymphony workers"
aws ec2 authorize-security-group-ingress --group-name biosymphony-sg \
 --protocol tcp --port 22 --cidr $MY_IP

# 5) Upload your full boot script to S3 (no 16 KB UserData limit there).
aws s3 cp boot-antismash8.sh s3://biosymphony-runs/boot/boot-antismash8.sh
```

### Per-run dispatch (mirrors managed worker step)

```bash
# UserData stays tiny (<1 KB): fetch+exec the real boot from S3.
cat > userdata.sh <<'EOF'
#!/bin/bash
exec > /var/log/biosymphony-boot.log 2>&1
set -x
# IMDSv2 token (mandatory for new Amazon Linux AMIs)
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
 -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
REGION=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/placement/region)
# Install docker + awscli on Amazon Linux 2023
dnf install -y docker awscli
systemctl start docker
aws s3 cp s3://biosymphony-runs/boot/boot-antismash8.sh /root/boot.sh --region $REGION
chmod +x /root/boot.sh
bash /root/boot.sh
EOF

# Encode (base64) and dispatch: AMI is the latest AL2023 x86_64.
AMI=$(aws ssm get-parameter \
 --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
 --query 'Parameter.Value' --output text)

aws ec2 run-instances \
 --image-id "$AMI" \
 --instance-type c6i.4xlarge \
 --iam-instance-profile Name=BioSymphonyWorker \
 --security-groups biosymphony-sg \
 --user-data file://userdata.sh \
 --block-device-mappings 'DeviceName=/dev/xvda,Ebs={VolumeSize=50,VolumeType=gp3,DeleteOnTermination=true}' \
 --instance-initiated-shutdown-behavior stop \
 --tag-specifications 'ResourceType=instance,Tags=[
 {Key=biosymphony,Value=worker},
 {Key=Name,Value=antismash8-bsub168}]' \
 --query 'Instances[0].InstanceId' --output text
```

The instance comes up in ~30 s; the boot script handles `dnf install docker → docker run mambaforge → mamba install antismash → antismash …`. Results land in `s3://biosymphony-runs/<run-id>/`. The instance self-stops via the IAM-scoped `ec2:StopInstances` call at the end of the boot script. Per-run cost: ~$0.10 on-demand, ~$0.03 if you swap `run-instances` for a Spot fleet request.

### Pull results

```bash
aws s3 sync s3://biosymphony-runs/antismash8-bsub168/ ./results/
```

A full reference boot script is in §10.

---

## 3. NCBI / public-data mirrors on AWS: the big bandwidth win

The single biggest reason to consider AWS over RunPod is **free same-region pulls from Open Data S3 buckets**. RunPod GPU pods regularly hit a 1-4 MB/s ceiling pulling raw FASTQ from `ftp.ncbi.nlm.nih.gov`; from a `us-east-1` EC2 instance, the SRA/BLAST mirrors deliver multi-Gbps off S3 with zero egress charge.

| Dataset | S3 URI | Region | Egress policy | Notes |
|---|---|---|---|---|
| NCBI SRA (raw reads) | `s3://sra-pub-run-odp/` (and partner buckets) | `us-east-1` | Free worldwide for SRA Open Data | `vdb-dump`/`fasterq-dump` directly against S3; see [SRA AWS docs](https://www.ncbi.nlm.nih.gov/sra/docs/sra-aws-download/). |
| NCBI BLAST DBs (nr, nt, swissprot, refseq_*) | `s3://ncbi-blast-databases/` | `us-east-1` | Unauth public; free same-region | Directory rotates; check `s3://ncbi-blast-databases/latest-dir` for the current snapshot prefix. ([registry page](https://registry.opendata.aws/ncbi-blast-databases/)) |
| UniProt RDF | `s3://aws-open-data-uniprot-rdf/` | `us-east-1` | Free same-region | New release every ~2 months; pick latest dated prefix. ([registry page](https://registry.opendata.aws/uniprot/)) |
| Kraken2 NCBI RefSeq | `s3://genome-idx/` (Kraken indexes), various sponsored buckets | `us-east-1` | Free same-region | Pre-built indexes; saves the 5-10 min build. |
| OpenProteinSet (HHblits/JackHMMER MSAs for PDB chains + UniClust30 clusters) | `s3://openfold/` | `us-east-1` | Free worldwide | 140k PDB chains + 16M UniClust30 MSAs, enormous time-saver for AlphaFold-style runs. |
| gnomAD | `s3://gnomad-public/` | `us-east-1` | Free worldwide | Population variant frequencies. |
| 1000 Genomes | `s3://1000genomes/` | `us-east-1` | Free worldwide | Long-running mirror, used heavily by Broad-style pipelines. |
| Human Pangenome Reference (HPRC R2) | `s3://human-pangenomics/` | `us-east-1` | Free worldwide | High-quality phased assemblies, 200+ individuals. |
| AWS Registry of Open Data (master index, bioinformatics tag) | https://registry.opendata.aws/tag/bioinformatics/ |, | varies per dataset | Browse before assuming you need to download from upstream. |

**Pattern:** instead of `urllib.request.urlretrieve("https://ftp.ncbi.nlm.nih.gov/...")`, do `aws s3 cp s3://ncbi-blast-databases/<dir>/swissprot.* . --no-sign-request`. Inside `us-east-1` the throughput is essentially network-card-limited (Gbps). Cross-region S3 GETs into a different AWS region incur **no inter-region fee** for Open Data buckets (per registry policy), but check each dataset's "free egress" column in its registry YAML.

> Sanity check: AWS gives **100 GB/month of internet egress free** aggregated across services. That's enough for results upload from a few dozen runs. Beyond 100 GB it's $0.09/GB tiering down to $0.05/GB beyond 150 TB.

---

## 4. Storage decision tree (RunPod Network Volume → AWS)

| Data type | Lifetime | Sharing | Right answer | Reason |
|---|---|---|---|---|
| Raw FASTQ pulled fresh from SRA | Disposable, per-run | None | **Skip**, read from `s3://sra-pub-run-odp/` directly | No reason to copy data already in S3. `fasterq-dump --threads 8` against the S3 mirror beats most local I/O. |
| Reference DB you'll reuse (Pfam, SwissProt BLAST, antiSMASH DBs, ProstT5 weights) | Months | Multiple instances, possibly parallel | **EBS gp3 snapshot** (per-AZ) **or** S3 + on-boot rsync | If single-instance/serial: snapshot a fully-loaded gp3, restore on each new instance ($0.08/GB-mo). If parallel: keep the canonical copy in S3, sync into local NVMe at boot. Avoid EFS unless multiple instances genuinely need concurrent writes. |
| Intermediate alignments (BAM, SAM, k-mer indexes) during a single pipeline run | <24 h | Pipeline-local | **Instance store (NVMe)** on i4i / r6id / c6id, or large gp3 | NVMe is free (bundled in instance hourly), 60-75% lower latency than gp3, dies on stop. Perfect for scratch. |
| Final results (HTML reports, JSON, FASTA, tarballs) | Forever | Cross-team | **S3 Standard** | $0.023/GB-mo, 100 GB egress free/mo. Lifecycle policy → Intelligent-Tiering / IA after 30 days if you forget about it. |
| Cold archives (raw seq for paper repro 2-5 yr from now) | Years | Rarely accessed | **S3 Glacier Deep Archive** | $0.00099/GB-mo ($1.01/TB-mo). Restore takes 12 h but you'll never pull it. |
| Shared scratch across an MPI HPC cluster | Days, parallel writes | Many instances at once | **EFS Elastic Throughput** or **FSx for Lustre** | EFS Standard $0.30/GB-mo (elastic tier. only pay for what you use); FSx for Lustre when you need scratch at >GB/s sustained. Both pricier than EBS but multi-instance. |

**Default pick for our pattern:** results in S3, reference DBs as a gp3 snapshot (or fresh download per-run if <5 GB, the antiSMASH-DB case), scratch on the root gp3. EFS only enters when ParallelCluster does.

### EBS gp3 vs io2 cheat
- **gp3**: $0.08/GB-mo + first 3,000 IOPS + 125 MB/s free; +$0.005/IOPS-mo and +$40.96/MBps-mo beyond. Use for almost everything.
- **io2**: $0.125/GB-mo + $0.065/IOPS-mo. Only worth it for sub-ms latency or >256k IOPS. Not relevant to our pipelines.

---

## 5. Instance-type cheat sheet (with RunPod cross-reference)

Pricing is **on-demand `us-east-1`, as of 2026-05**. Always re-check on the [EC2 pricing page](https://aws.amazon.com/ec2/pricing/on-demand/) before committing. there was a 44% reduction on P5 in June 2025 and a 15% H200 hike later in the year.

### CPU (the bulk of our workloads)

| AWS instance | vCPU / RAM | $/hr on-demand | $/hr Spot (~typical) | RunPod analog | When to pick it |
|---|---|---|---|---|---|
| `c6i.large` | 2 / 4 GiB | $0.085 | ~$0.026 | cpu3c | Tiny smoke/staging pods. |
| `c6i.xlarge` | 4 / 8 GiB | $0.17 | ~$0.05 | cpu5c | Same compute footprint as our test4b cpu5c (8 GiB though, vs cpu5c's 16 GiB). Use c6i.2xlarge for parity. |
| `c6i.2xlarge` | 8 / 16 GiB | $0.34 | ~$0.10 | cpu5g (32 GiB has more RAM) | DeepBGC, MMseqs2 typical runs. |
| **`c6i.4xlarge`** | **16 / 32 GiB** | **$0.68** | ~$0.20 | cpu5g (32 GiB) at $0.184/hr | **Default for antiSMASH 8 / cblaster / clinker.** Matches our validated cpu5g profile. |
| `c6i.8xlarge` | 32 / 64 GiB | $1.36 | ~$0.40 | cpu7c (64 GiB) at ~$0.38/hr | Larger assemblies, JCVI MCScan with big synteny inputs. |
| `c7i.4xlarge` | 16 / 32 GiB | $0.714 | ~$0.21 |, | Ice Lake successor; ~5% faster wall, +5% price. Marginal. |
| `c7g.4xlarge` (Graviton) | 16 / 32 GiB | $0.578 | ~$0.17 |, | **15-25% cheaper than c6i** if your tools have ARM64 bioconda builds. see Graviton note below. |
| `c8g.4xlarge` (Graviton4) | 16 / 32 GiB | ~$0.65 | ~$0.20 |, | Newest Graviton; same caveat. |

### Memory-optimized (genome assembly, large index builds)

| AWS instance | vCPU / RAM | $/hr | Use case |
|---|---|---|---|
| `r6i.2xlarge` | 8 / 64 GiB | $0.504 | Genome assemblers (SPAdes, MaSuRCA), large HMMER scans. |
| `r6i.4xlarge` | 16 / 128 GiB | $1.008 | k-mer-heavy assembly; 128 GiB is the sweet spot. |
| `r6i.8xlarge` | 32 / 256 GiB | $2.016 | Plant genome assembly, multi-sample joint-calling. |
| `x2idn.16xlarge` | 64 / 1024 GiB | ~$6.67 | Only when 1 TB RAM is genuinely the bottleneck (rare, Trinity on poorly assembled transcriptomes). |

### GPU (model inference: ESM-C, ProstT5, AlphaFold)

| AWS instance | GPU | vCPU / RAM | $/hr on-demand (2026-05) | RunPod analog | Use case |
|---|---|---|---|---|---|
| `g5.xlarge` | 1× A10G 24 GB | 4 / 16 GiB | **$1.006** | RTX 4090 24 GB ≈ $0.34/hr. **3× cheaper on RunPod for the same VRAM tier** | Single ESM-C/ESMplusplus inference, ProstT5 embeddings on a few thousand sequences. |
| `g5.2xlarge` | 1× A10G 24 GB | 8 / 32 GiB | $1.212 | RTX 4090 | More CPU pre/post-processing alongside the GPU. |
| `g5.12xlarge` | 4× A10G 24 GB | 48 / 192 GiB | $5.672 | 4× RTX 4090 | Batched embedding jobs. |
| `p4d.24xlarge` | 8× A100 40 GB | 96 / 1152 GiB | **$21.96** (was $32.77, -33% in 2025) | A100-80GB at $1.89/hr. **~10× cheaper on RunPod per-A100-hour**, but RunPod is 80 GB vs AWS's 40 GB | Large AlphaFold runs, HHblits on big DBs. |
| `p5.48xlarge` | 8× H100 80 GB | 192 / 2 TB | ~$33-55/hr (post-2025 cut, region-dependent) | H100 80 GB community ≈ $2.39-2.99/hr, **same 10× delta** | Foundation-model fine-tuning; bigger than we need for inference. |
| `p5e.48xlarge` | 8× H200 141 GB | 192 / 2 TB | ~$39.80/accelerator-hour (Capacity Blocks; up ~15% in 2025) | H200 not yet routinely on RunPod | Frontier MSA + folding combined; **almost certainly overkill** for plant-secondary-metabolism tooling. |

**GPU bottom line:** AWS GPU on-demand is **3-10× the price of RunPod community GPUs**. Only consider AWS GPU if (a) you need free same-region pulls from a giant reference DB that lives in `us-east-1` Open Data (rare for inference), (b) you need committed Capacity Block scheduling that RunPod can't promise (real for >24 h sustained training, not for the atlas jobs), or (c) RunPod GPU capacity is genuinely unavailable. **Default GPU choice stays RunPod.**

### Storage-optimized (large local NVMe)

| AWS instance | NVMe | vCPU / RAM | $/hr | When |
|---|---|---|---|---|
| `i4i.2xlarge` | 1× 1875 GB NVMe | 8 / 64 GiB | ~$0.69 | Very fast scratch for index builds (MMseqs2 createindex, RocksDB-style); 60-75% lower I/O latency than gp3. |
| `i4i.4xlarge` | 1× 3750 GB NVMe | 16 / 128 GiB | ~$1.37 | Same use cases at bigger scale. |

### Graviton (ARM64) compatibility note

Bioconda gained official `linux-aarch64` channel support in **July 2024**. As of 2026-05, [nf-core's Arm pipelines effort](https://nf-co.re/blog/2026/arm-pipelines) reports comparable wall-clock vs `c7a` x86 with **20-25% cost savings** on a `c8g`. Catch: not every bioconda recipe has been rebuilt for `aarch64` yet. Before picking Graviton for a tool, verify the channel: `mamba search -c bioconda --platform linux-aarch64 <tool>`. Likely-working: BLAST+, HMMER, Prodigal, MMseqs2, samtools, bcftools, the core bioconda spine. Likely-broken on ARM today: tools with old PyTorch pins (CLEAN), tools with x86-only binary forks (some folding stacks). When in doubt, smoke-test on `c8g.xlarge` ($0.14/hr) for 5 min before committing the run.

---

## 6. Boot payload: the 16 KB UserData limit and the S3-fetch pattern

EC2 enforces a hard **16 KB UserData ceiling** (`InvalidUserData.MalformedFileSize` if you exceed it; the AWS SDK actually allows you to push up to 21847 raw bytes which is the same number after base64 encoding). Our RunPod cookbook uses `dockerStartCmd` with a base64+gzip-embedded boot script that runs ~10 KB raw. we'd squeak in under EC2's limit, but the cleaner pattern (and the one every AWS reference doc uses) is:

```
┌─────────────────┐
│ UserData (16KB) │ shebang + IMDSv2 token + dnf install + aws s3 cp boot.sh + exec
└────────┬────────┘
 │ pulls real boot
 ▼
┌──────────────────────────────────────────┐
│ s3://biosymphony-runs/boot/boot.sh │ full pipeline (no size limit)
└──────────────────────────────────────────┘
```

The instance profile attached at launch lets `aws s3 cp` authenticate without credentials in UserData. This replaces provider-key env-var patterns and avoids the stale-credential footgun because IMDSv2 hands the role to the SDK at runtime.

**IMDSv2 is mandatory on new AMIs.** Token-fetch then header-attach:
```bash
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
 -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/instance-id
```

The boot script can use the AWS CLI directly, it inherits the instance role via IMDSv2 automatically.

---

## 7. Self-stop / kill-switch patterns

RunPod has one mechanism (`POST /v1/pods/<id>/stop` with the API key). AWS has three, each with different blast radius:

### Pattern A: in-script `shutdown -h` with `InstanceInitiatedShutdownBehavior=stop`

Cheapest, no IAM required.

```bash
# At create time:
aws ec2 run-instances ... --instance-initiated-shutdown-behavior stop

# At end of boot.sh:
echo "Run complete, stopping in 60 s..."
sleep 60 # buffer for log flush
shutdown -h +0 # OS halt → EC2 stops the instance (does NOT terminate)
```

**Trade-off:** the instance stays in `stopped` state and you keep paying for the EBS volume (~$0.08/GB-mo for gp3). For a 50 GB root volume that's $4/mo idle. fine for hours, expensive for months. Use Pattern B if you want full cleanup.

### Pattern B: in-script `aws ec2 stop-instances` (preferred for our pattern)

Requires the IAM policy from §2. The instance stops itself via the API call.

```bash
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
 -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/placement/region)

aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
```

Same effect as Pattern A but cleaner separation: the script reports its own decision, you can swap `stop-instances` → `terminate-instances` to also reclaim the EBS volume.

### Pattern C: CloudWatch idle-CPU alarm (operator-side safety net)

For runs you orphan (boot.sh crashed before reaching its self-stop branch, monitor disconnected, etc.):

```bash
# CPU < 5% for 3 consecutive 5-minute periods (=15 min) → stop the instance
aws cloudwatch put-metric-alarm \
 --alarm-name "biosymphony-idle-stop-$INSTANCE_ID" \
 --metric-name CPUUtilization --namespace AWS/EC2 \
 --dimensions Name=InstanceId,Value=$INSTANCE_ID \
 --statistic Average --period 300 --threshold 5 \
 --comparison-operator LessThanThreshold --evaluation-periods 3 \
 --alarm-actions "arn:aws:swf:$REGION:$ACCT:action/actions/AWS_EC2.InstanceId.Stop/1.0"
```

**Use Pattern B as the primary self-stop and Pattern C as a backstop** (set on create-instance, scoped via tag). Pattern A is fine for personal-laptop-style throwaway dispatches.

> Anti-pattern memo: keep the heartbeat as `STATUS` files in S3 with a `LastWriteTime` test, not just `desiredStatus`. Same lesson as, a stuck process can hold an instance "Running" indefinitely; the auto-stop alarm catches it.

---

## 8. Container deployment paths

| Path | When it wins | When it doesn't |
|---|---|---|
| **EC2 + Docker (this doc's default)** | Single-shot pods, hand-controlled boot, RunPod-shaped workflows | Multi-stage pipelines with branching, retries, hundreds of parallel tasks |
| **ECS Fargate** | Serverless containers, no EC2 management, can pull from ECR/public Docker | 30-min image-pull stall potential for >5 GB images; vCPU/RAM granularity differs from EC2 |
| **AWS Batch** | Hundreds-thousands of independent jobs (per-sample variant calling, batch antiSMASH over many genomes), Spot-aware retries | Single-pod runs (overhead of compute env setup), interactive debugging (job runs detached) |
| **AWS HealthOmics** | Pre-baked nf-core workflows, WDL/Nextflow pipelines, compliance/HIPAA needs | Custom or non-standard tools (no Ready2Run for antiSMASH/cblaster), per-run cost not visible upfront (estimated post-hoc) |
| **AWS ParallelCluster** | True HPC (MPI, tightly coupled, large shared filesystem) | Pleasingly-parallel workloads. Batch beats it |

**Recommendation for BioSymphony:** stay on **EC2 + Docker** as the default for parity with the RunPod cookbook. Move to **AWS Batch** when we run the same pipeline across ≥20 inputs in one campaign. Move to **AWS HealthOmics** only if we adopt a HealthOmics-Ready2Run pipeline (currently no overlap. none of antiSMASH / cblaster / DeepBGC / MMseqs2 / Foldseek / ProstT5 / CLEAN / P450Rdb are Ready2Run as of 2026-05). AlphaFold/ESMFold *are* Ready2Run via Google DeepMind / Meta publishing, so if we ever fold structures inside the atlas pipeline that's the right entry point.

### HealthOmics Ready2Run inventory (as of 2026-05, [docs link](https://docs.aws.amazon.com/omics/latest/dev/workflows-r2r-table.html))

| Workflow | Publisher | Relevant to us? |
|---|---|---|
| AlphaFold (601-1200 res) | Google DeepMind | **Yes** if we move structural prediction into the atlas |
| AlphaFold (≤600 res) | Google DeepMind | **Yes**, covers most enzymes |
| ESMFold (≤800 res) | Meta Research | **Yes**, fast first-pass alternative to AlphaFold |
| Bases2Fastq (2x75/2x150/2x300) | Element Biosciences | No (we don't run Element AVITI BCL conversion) |
| GATK-BP fq2bam / fq2vcf / Somatic WES | Broad Institute | No (we're not variant-calling humans) |
| NVIDIA Parabricks (BAM2FQ2BAM, FQ2BAM, DeepVariant, HaplotypeCaller, Mutect2) | NVIDIA | No (same, not our pipeline) |
| nf-core scRNAseq (KallistoBUStools, Salmon Alevin-fry, STARsolo) | NF-Core | No (not our use case, but model for "bring your own nf-core pipeline") |
| Sentieon Germline/Somatic/LongRead | Sentieon (subscription) | No |
| Ultima Genomics DeepVariant | Ultima Genomics | No |

So: HealthOmics gives us a clean managed path for **AlphaFold / ESMFold only** today. Everything else stays on plain EC2 or AWS Batch.

---

## 9. Cost comparison: RunPod vs AWS for our typical pods

**Caveat:** AWS prices below are on-demand `us-east-1` 2026-05. Spot saves ~70% but adds interruption risk; pre-empted runs that have to restart can erase the savings if your work isn't checkpointable. For our pattern (5-60 min self-contained pods writing results to S3) Spot is reasonable but not free of risk.

| Workload (validated on RunPod) | RunPod actual | AWS equivalent | AWS on-demand | AWS Spot (typical) | Notes |
|---|---|---|---|---|---|
| antiSMASH 8, B. subtilis 168 (5:17 wall) | cpu5g 4vCPU/32GB @ $0.184/hr = **$0.017** | c6i.4xlarge 16vCPU/32GB | $0.060 (~$0.68/hr × 0.088 hr) | ~$0.018 | AWS on-demand 3.5× more; Spot near-parity. |
| DeepBGC, public plant chromosome panel (~25 min) | cpu5g @ $0.184/hr = **$0.077** | c6i.4xlarge | $0.283 | ~$0.085 | Same ratio. |
| MMseqs2 search, 10k queries vs SwissProt (30 min) | cpu7c 16vCPU/64GB @ $0.38/hr = **$0.19** | c6i.8xlarge | $0.68 | ~$0.20 | Same ratio. |
| ESM-C inference, 1k proteins, ~10 min | RTX 4090 community @ $0.34/hr = **$0.057** | g5.xlarge (A10G 24GB) | $0.17 | ~$0.05 | RunPod 3× cheaper on GPU even at on-demand parity. |
| AlphaFold, 1 sequence ≤600 res (7.5 h via HealthOmics) | A100 community @ $1.89/hr = **$14.18** | HealthOmics Ready2Run | ~$15-25 (estimate, run-based) | n/a | HealthOmics packages compute+storage+overhead. Variable. |
| Storage, keeping atlas results around for 6 months (100 GB) | Network volume @ $10/mo = **$60** | S3 Standard | $13.80 | $13.80 | **AWS wins** for long-term storage by ~4-5×. |
| Egress, pulling 500 GB results to laptop once | Free | 500 GB out at $0.09/GB after 100 GB free | **$36** | $36 | **RunPod wins**. AWS egress is the dominant cost for "ship the whole atlas home" patterns. |

**Bottom line:** RunPod is the right tool when (a) GPU is involved or (b) you don't need same-region SRA/BLAST mirrors. **AWS gets cheaper only when you stay inside AWS**, pipelines that write to S3, do downstream Athena/Quicksight on S3, and never pull the data home. For the atlas workflow (laptop renders Quarto from derived artifacts), egress to laptop would dominate AWS-side costs.

---

## 10. Sample boot script (parity with `test4b-antismash8-mambaforge-boot.sh`)

This is the file you'd `aws s3 cp` to `s3://biosymphony-runs/boot/boot-antismash8.sh` in §2's setup. Key diffs vs the RunPod version:

- `aws s3 cp` for everything (results upload + optional reference DB pull)
- IMDSv2 token fetch for instance-id + region
- `aws ec2 stop-instances` instead of `POST /v1/pods/<id>/stop`
- Status writes go to `s3://biosymphony-runs/<run-id>/STATUS` (no `python3 -m http.server`, let CloudWatch + S3 polling handle it)

```bash
#!/bin/bash
# /root/boot.sh: runs on the instance after UserData kicks it off.
# Mirrors the RunPod test4b mambaforge antiSMASH 8 demo on AWS EC2.

set -uo pipefail
RUN_ID="antismash8-bsub168-$(date -u +%Y%m%dT%H%M%SZ)"
WORK=/mnt/work
mkdir -p "$WORK" && cd "$WORK"

# ── 0. Identity + AWS context via IMDSv2 ────────────────────────
TOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" \
 -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
INSTANCE_ID=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -sH "X-aws-ec2-metadata-token: $TOKEN" \
 http://169.254.169.254/latest/meta-data/placement/region)
BUCKET=biosymphony-runs
S3PREFIX="s3://$BUCKET/$RUN_ID"

status() {
 echo "phase=$1 ts=$(date -u +%s)" > /tmp/STATUS
 aws s3 cp /tmp/STATUS "$S3PREFIX/STATUS" --region "$REGION" --quiet || true
}

fail() {
 status "verify_failed reason=$1"
 aws s3 cp /var/log/biosymphony-boot.log "$S3PREFIX/boot.log" \
 --region "$REGION" --quiet || true
 echo "FAILURE: $1" > /tmp/FAILURE
 aws s3 cp /tmp/FAILURE "$S3PREFIX/FAILURE" --region "$REGION" --quiet || true
 sleep 60
 aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID" || true
 exit 1
}

status "started"

# ── 1. Pull mambaforge container ────────────────────────────────
status "docker_pull"
docker pull condaforge/mambaforge:latest

# ── 2. Install antiSMASH 8 inside the container ─────────────────
status "install_antismash"
docker run --rm -d --name as8 -v "$WORK":/workspace \
 condaforge/mambaforge:latest sleep infinity
docker exec as8 mamba install -n base -c bioconda -c conda-forge \
 -y antismash hmmer prodigal blast > install.log 2>&1 \
 || fail "mamba_install_failed"

# ── 3. Download antiSMASH DBs ────────────────────────────────────
status "db_download"
docker exec as8 mkdir -p /workspace/antismash-dbs-v8
docker exec as8 download-antismash-databases \
 --database-dir /workspace/antismash-dbs-v8 \
 > db-download.log 2>&1 || fail "db_download_failed"

# ── 4. Fetch B. subtilis 168 genome from NCBI ───────────────────
status "fetch_genome"
docker exec as8 python3 -c '
import urllib.request, os
url=("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
 "?db=nuccore&id=NC_000964.3&rettype=gbwithparts&retmode=text")
req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 BioSymphony"})
data=urllib.request.urlopen(req, timeout=180).read()
open("/workspace/bsubtilis168.gbk","wb").write(data)
print(f"fetched {os.path.getsize(\"/workspace/bsubtilis168.gbk\")} bytes")
' > fetch.log 2>&1 || fail "fetch_genome_failed"

# ── 5. Run antiSMASH 8 ───────────────────────────────────────────
status "run_antismash"
NCPU=$(nproc)
docker exec as8 antismash \
 --taxon bacteria --cpus "$NCPU" \
 --output-dir /workspace/results-bsub168 \
 --databases /workspace/antismash-dbs-v8 \
 --genefinding-tool none \
 --cb-general --cb-knownclusters --cb-subclusters \
 --asf --pfam2go --rre --tfbs \
 --html-description "BioSymphony AWS antiSMASH 8 demo" \
 /workspace/bsubtilis168.gbk > antismash.log 2>&1 || fail "antismash_run_failed"

# ── 6. Archive + upload ──────────────────────────────────────────
status "archive"
tar -czf results.tar.gz -C results-bsub168 . || fail "tar_failed"
aws s3 cp results.tar.gz "$S3PREFIX/results.tar.gz" --region "$REGION"
aws s3 cp results-bsub168/ "$S3PREFIX/results/" --recursive --region "$REGION"

# ── 7. Mark success + self-stop ──────────────────────────────────
status "ready_for_pull"
echo "complete" > /tmp/SUCCESS
aws s3 cp /tmp/SUCCESS "$S3PREFIX/SUCCESS" --region "$REGION"

status "self_stop"
sleep 60
aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
```

---

## 11. Gotcha translation table (RunPod memory entries → AWS analog)

These cross-reference generalized lessons from prior provider-backed validation runs. The whole point of this doc is to bake equivalents in upfront so a future operator does not burn capacity rediscovering them.

| RunPod memory | AWS analog | Prevention |
|---|---|---|
|, pod's `RUNPOD_API_KEY` env diverges from what you passed | "Don't put `AKID/Secret` in UserData" | IAM **instance profile** + IMDSv2. Never embed long-lived credentials. |
|, `dockerStartCmd` >~64 KB silently fails | UserData hard cap **16 KB** (tighter) | Tiny UserData → fetch real boot from S3. §6 pattern. |
|, >5 GB GHCR images stall | ECR/Docker Hub pulls don't stall, but cold-pull a 5 GB image is still 30-60 s on a fresh instance | Pre-bake a custom AMI with the image already pulled (`docker pull` in user-data, then `aws ec2 create-image`). For one-shots, accept the wait. |
| | Amazon Linux 2023 ships `curl`/`wget`; Ubuntu does too | No issue at the host layer. If you're still using mambaforge inside Docker, same workaround applies (Python urllib). |
| | NCBI/UniProt may also throttle default UAs | Set `User-Agent: Mozilla/5.0 BioSymphony` on every external fetch. Same rule as RunPod. |
|, `*.proxy.runpod.net` caches GET | S3 GETs are not cached by AWS infra | No `?cb=$RANDOM` needed for direct S3 polling. If you front S3 with CloudFront, cache-bust applies. |
|, silent GPU billing | "I picked a `g5` for a CPU job" | User error, instance type is explicit. The closest gotcha is **Spot interrupt mid-pipeline**; mitigate with checkpoints or use On-Demand for runs <60 min. |
|, volumes locked to SECURE cloud | EBS is per-AZ (not multi-AZ); EFS is regional | Pick storage shape to match your access pattern, not "secure tier". |
|, "no instances available" outages | `InsufficientInstanceCapacity` errors | Use a Launch Template with **multi-AZ Auto Scaling Group + Mixed Instances Policy** for capacity diversification. AWS Batch does this for you. |
|, runtime=null stall | Less common, but **instance status check failed** ≈ same. | Hard timeout: if no `STATUS` file appears in S3 within 5 min, `terminate-instances` and re-dispatch. |
| | Same lesson | Check `aws ec2 stop-instances` exit code; write `.self_stop_status` sentinel to S3 BEFORE calling. |
|, don't bulk-delete pods | Don't bulk-terminate by region | Use tag filter: `aws ec2 describe-instances --filters Name=tag:biosymphony,Values=worker`. Never run `terminate-instances` on raw IDs from `describe-instances` output without a tag filter. |
| | Same lesson | Sync only derived artifacts (`results-summary.json`, `regions.json`, `index.html`) from S3 to laptop; leave raw `results.tar.gz` in S3. Egress charges apply. |
| | Same lesson | CloudWatch idle-CPU alarm + S3 `STATUS` file `LastModified` poll. State="running" ≠ progress. |
| | Same lesson | Verify expected output files exist in S3 (HEAD request) before writing SUCCESS sentinel. |
| | Same lesson | Boot script must `aws s3 rm $S3PREFIX/SUCCESS $S3PREFIX/FAILURE 2>/dev/null` at start. |

---

## 12. When to use AWS over RunPod

1. **Free same-region pulls from Open Data S3 mirrors** (SRA, BLAST DBs, UniProt, OpenProteinSet, gnomAD). kills RunPod's 1-4 MB/s NCBI ceiling stone dead.
2. **Long-lived storage of results** that downstream AWS services (Athena, QuickSight, SageMaker, Glue) consume. staying in-cloud avoids egress.
3. **HIPAA/compliance**-bound runs (HealthOmics is HIPAA-eligible; RunPod is not).
4. **Spot-tolerant high-throughput batches** (1000+ AWS Batch jobs in parallel, each <30 min, checkpointable). Spot pricing at ~$0.05/hr per `c6i.xlarge`-class node hits scale RunPod can't.
5. **AlphaFold/ESMFold pipelines**, HealthOmics Ready2Run packages handle DB management + GPU scheduling + per-sample billing transparently. We'd spend 1-2 days replicating this on RunPod.
6. **ParallelCluster / MPI workloads**, RunPod doesn't have a real multi-node coordinator; AWS does.

## 13. When NOT to use AWS over RunPod

1. **GPU inference under a few hours**, RunPod is 3-10× cheaper per GPU-hour, full stop. Don't pay g5/p4d on-demand rates for ESM-C / ProstT5 / DeepBGC unless RunPod GPU capacity is genuinely unavailable.
2. **One-shot pods where you'll pull all results back to laptop**, AWS egress past 100 GB/mo gets expensive fast ($0.09/GB tiering to $0.05/GB above 150 TB). RunPod's network volumes have no egress charge to RunPod-proxy clients.
3. **Quick prototypes / smoke tests**, the IAM-role + Launch Template + S3 bucket setup adds 1-2 hours of friction vs RunPod's 5-min dispatch. Worth it for production, overhead for "does this tool even work."
4. **Iterating on Dockerfile contents**, RunPod's `dockerStartCmd` pattern lets you rerun a tweaked boot script in 30 s. AWS needs UserData re-upload + new instance launch. Not a blocker, but a friction tax.
5. **No-AWS-credentials operator**, onboarding new account takes a day for IAM/billing/budgets. RunPod is "API key, go." Stay on RunPod until the team has a real AWS account ready.

---

## 14. Authoritative URLs

- [Amazon EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [Amazon EC2 Spot Instances](https://aws.amazon.com/ec2/spot/)
- [Vantage EC2 Instance Comparison](https://instances.vantage.sh/), best cross-reference for vCPU/RAM/price by region
- [Amazon EBS Pricing](https://aws.amazon.com/ebs/pricing/), gp3, io2, snapshots
- [Amazon EFS Pricing](https://aws.amazon.com/efs/pricing/), Standard, IA, Archive, Elastic Throughput
- [Amazon S3 Pricing](https://aws.amazon.com/s3/pricing/), Standard, Intelligent-Tiering, Glacier tiers, request costs
- [AWS Data Transfer Pricing](https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer), internet egress tiers, inter-region, intra-AZ
- [EC2 UserData docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html), 16 KB limit, cloud-init behavior
- [EC2 IMDSv2 docs](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html)
- [EC2 Launch Templates](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-launch-templates.html)
- [CloudWatch alarm actions (stop/terminate)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/UsingAlarmActions.html)
- [AWS HealthOmics overview](https://aws.amazon.com/healthomics/) and [Ready2Run workflows table](https://docs.aws.amazon.com/omics/latest/dev/workflows-r2r-table.html)
- [AWS Batch user guide](https://docs.aws.amazon.com/batch/latest/userguide/), for many-job dispatch
- [AWS ParallelCluster docs](https://docs.aws.amazon.com/parallelcluster/latest/ug/what-is-aws-parallelcluster.html), MPI / HPC scheduler
- [Registry of Open Data on AWS, bioinformatics tag](https://registry.opendata.aws/tag/bioinformatics/)
- [NCBI SRA on AWS](https://www.ncbi.nlm.nih.gov/sra/docs/sra-aws-download/) and [registry entry](https://registry.opendata.aws/ncbi-sra/)
- [NCBI BLAST DBs on AWS](https://registry.opendata.aws/ncbi-blast-databases/), `s3://ncbi-blast-databases/`
- [UniProt on AWS](https://registry.opendata.aws/uniprot/), `s3://aws-open-data-uniprot-rdf/`
- [OpenProteinSet on AWS](https://registry.opendata.aws/openfold/), `s3://openfold/` (HHblits/JackHMMER MSAs for 140k PDB chains + 16M UniClust30 clusters)
- [nf-core on Arm (2026)](https://nf-co.re/blog/2026/arm-pipelines), Graviton compatibility and benchmarks
- [BioContainers in ECR Public Gallery](https://gallery.ecr.aws/biocontainers/), note: being deprecated in favor of Seqera Containers
- [Seqera Containers](https://seqera.io/containers/), modern replacement for BioContainers
- [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/)
- [Choosing between AWS Batch or ParallelCluster (AWS HPC Blog)](https://aws.amazon.com/blogs/hpc/choosing-between-batch-or-parallelcluster-for-hpc/)

---

## 15. Open questions for a future operator

These are things this doc cannot answer without actually running AWS jobs:

1. **Real same-region throughput from `s3://ncbi-blast-databases/`**, registry says it's `us-east-1` public. We've assumed Gbps; need to benchmark a 50 GB `nr` pull from a `c6i.4xlarge` and measure wall time. Suspect 5-10 min based on AWS's S3-EC2 in-region typical numbers, but worth confirming.
2. **Actual Spot interrupt rate on `c6i.4xlarge`** vs `c7g.4xlarge` in `us-east-1` for sub-2-hour bio runs in mid-2026. Quoted average <5% is across-the-board; specific instance + AZ + time-of-day matter. Use the [Spot Instance Advisor](https://aws.amazon.com/ec2/spot/instance-advisor/) to check current frequency.
3. **HealthOmics actual per-run cost** for AlphaFold ≤600 res. docs say "based on requested compute + filesystem" with a 1-hour minimum billing increment. Need a real run on a representative input (the GitHub example workflows are starting points) to validate the $15-25 estimate.
4. **Whether the AWS HealthOmics Nextflow runtime can host `antismash/standalone-lite:8.0.4`** as a private workflow with reasonable cost. If it can, that's a much smoother managed path than EC2-on-Docker.
5. **AMI pre-baking strategy**: does it pay off vs cold pull? For a `c6i.4xlarge` with a 30-min antiSMASH run, the 1-min docker pull is 2% of wall time. For a 5-min run it's 20%. Pre-baking via `aws ec2 create-image` after a single warm-up run is cheap and worth doing once we run frequently.
6. **Cross-region cost** of writing results back to `us-west-2` if our team's downstream tooling lives there. Inter-region S3 transfer is $0.02/GB. for 500 GB of results that's $10 per run, which can dominate.
7. **Whether ECR Public BioContainers replacement (Seqera Containers) has a working antiSMASH 8 / DeepBGC image** as of 2026-05. Worth verifying before we plan a fully containerized AWS Batch dispatch.

---

*Document drafted 2026-05-11 as forward-research; no AWS validation runs have occurred.*
*Update protocol: when an AWS run actually fires, add a "Validated" subsection mirroring the antiSMASH cookbook's format (redacted provider ID, region, wall, cost, observed gotchas).*
