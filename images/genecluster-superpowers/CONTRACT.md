# Per-tool dispatch contract

**Status:** dispatch contract for tools running via the cloud-portable templates under `dispatch/`.
**Applies to:** every tool dispatched via the cloud-portable templates under `dispatch/`. The same contract holds whether the pod runs on RunPod, AWS, GCP, Vast.ai, or Lambda . the only difference is cloud-native artifact storage (volume / S3 / GCS / instance disk).

This contract is the source of truth for boot-script authoring, monitor-script polling, and worker-side artifact pulls. Each per-tool boot under `images/genecluster-superpowers/scripts/<tool>-boot.sh` MUST satisfy every clause below.

---

## 1. Sentinel paths

Every tool writes sentinels under `<MOUNT>/superpowers/<TOOL>/`. The `<MOUNT>` is `/workspace` on RunPod, an EBS volume mount on AWS, a Filestore mount on GCP, and a similar host volume on Vast.ai / Lambda.

| File | Required | Format | Purpose |
|---|---|---|---|
| `STATUS` | ✅ | `phase=<name> ts=<unix>` (single line, atomically rewritten each phase) | Monitor polls; reflects current pipeline stage. |
| `SUCCESS` | ✅ on success | `complete\n` (any non-empty content) | Created **only** after every expected output exists + tool exit code = 0. |
| `FAILURE` | ✅ on failure | tail of `/tmp/dmesg`, `ls -la`, last 100 lines of relevant `*.log` | Created on cleanup_on_failure path. |
| `<tool>-summary.tsv` | ✅ on success | TSV per output schema (see §3) | The headline derived deliverable. |
| `tools.txt` | ✅ | one line per binary used, format `<bin>: <which-output-or-MISSING>` | Verifies every required binary is on PATH. |
| `inventory.txt` | optional | per-stage size/count totals | For no-growth detector; helps post-hoc forensics. |
| `.self_stop_status` | ✅ if pod self-stops | HTTP code from stop call | Captures whether pod's own self-stop curl returned 200. |

### Sentinel hygiene

- **Stale-sentinel cleanup at boot start**:
 ```bash
 rm -f SUCCESS FAILURE *.summary.tsv hits.tsv # whatever previous run might have left
 rm -rf result/ tmp/
 ```
- **Atomic STATUS writes:** always `echo "phase=X ts=$(date -u +%s)" > STATUS` (overwrite, not append). Never write partial lines.
- **SUCCESS is not just `mkdir`:** verify tool's exit code AND that expected output files exist + non-empty before creating SUCCESS.

## 2. Cleanup pattern

Provider cleanup must be explicit and auditable. Do not pass long-lived provider API keys into pods or write them into launch manifests.

- RunPod cleanup is operator-side: the caller uses `RUNPOD_API_KEY` outside the pod after pulling summary artifacts.
- AWS/GCP cleanup should use instance profiles or attached service accounts, not static keys in user data.
- Vast.ai/Lambda cleanup should be operator-side unless short-lived scoped credentials are available outside source control.

Required status pattern:

```bash
cat > .self_stop_status <<'EOF'
self_stop_attempted=false
self_stop_blocker=operator_side_cleanup_required
EOF
```

For RunPod, boot scripts should default to `sleep <IDLE_SECONDS> && exit` with a short `IDLE_SECONDS` so the operator has time to pull summary artifacts before cleanup. Keep provider IDs and response payloads in ignored runtime dispatch state.

For AWS/GCP, provider-native instance identities can perform stop/terminate when scoped narrowly. For other providers, prefer operator-side cleanup.

## 3. Output TSV schema

Every tool's `<tool>-summary.tsv` MUST conform to the canonical schema (extra columns OK, missing columns forbidden):

| Column | Type | Description |
|---|---|---|
| `query_id` | str | One of {Q002, Q005, Q012, …}. |
| `target` | str | The protein/cluster/feature ID returned by the tool. |
| `evidence_kind` | str | One of {`sequence_blast`, `sequence_profile`, `structure_fold`, `cluster_homology`, `synteny_anchor`, `motif_cluster`, `ec_call`, `ko_assignment`, `bgc_match`, `reaction_template`, `coevolution`, `embedding_neighbor`, `signal_peptide`}. |
| `score` | float | Tool's primary score (e.g., bitscore, evalue, identity, fold-prob, EC-confidence). Higher = better. |
| `top_metadata_json` | str | JSON-encoded blob of tool-specific extras (top 3 fields the tool emits). |

A summary TSV without these columns is a contract violation; CONTRACT-conformant downstream pulls (xlsx merger, Quarto dashboard) reject it.

## 4. Summary egress rule

Default to provider storage, SSH, S3/GCS, or operator-side tools. If a RunPod HTTP proxy is necessary, expose it deliberately, serve only the run summary directory, and keep the TTL short.

```bash
if [ "${RUNPOD_EXPOSE_HTTP:-0}" = "1" ]; then
 python3 -m http.server 8000 --directory "$WORK" > "$WORK/http.log" 2>&1 &
fi
```

Never serve the provider mount root when raw/heavy data or credentials may be present.

## 5. Cache-bust on monitor URLs


```bash
# Operator-side monitor: every poll URL appends ?cb=$RANDOM:
curl -s "https://<pod>-8000.proxy.runpod.net/STATUS?cb=$RANDOM"
curl -s "https://<pod>-8000.proxy.runpod.net/SUCCESS?cb=$RANDOM" -o /dev/null -w '%{http_code}'
```

Without `?cb=$RANDOM`, polls return cached responses for several minutes. "Stuck pipeline" is most likely "stuck cache."

## 6. Pre-flight smoke pod


```bash
# Cents not dollars: always smoke before a real run:
mamba install -y -c bioconda <tool>
command -v <tool> # exits 0 if installed, 1 if missing
<tool> --version # exits 0 with version string
```

A 2-min smoke pod that checks every binary the boot script uses is mandatory before running the full pipeline. Skip = $$ in crash-loop billing.

## 7. No inline heredocs in dockerStartCmd


- 36 KB wrappers with base64-decode-via-heredoc patterns silently crash-loop within 60-90s.
- Use **curl-fetch + sha256-verify** pattern (catbox.moe upload + Mozilla UA download from inside pod).
- For tiny payloads (<10 KB), `printf '%s' '<base64>' | base64 -d > script.sh` is OK; for anything larger, stage to volume FIRST via separate dispatch.

## 8. Mozilla User-Agent for catbox / NGDC / external HTTP


```python
# In every boot script that fetches via Python:
import urllib.request
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
with urllib.request.urlopen(req, timeout=300) as r, open(dest, 'wb') as f:
 while True:
 chunk = r.read(65536)
 if not chunk: break
 f.write(chunk)
```

`mambaforge` ships only python+conda; **no curl, no wget**. The UA workaround is required for catbox.moe specifically and recommended elsewhere.

## 9. Restart-count thresholds


- **1 restart** = noise (network blip, image pull retry).
- **2 restarts** = suspect; investigate logs but don't act yet.
- **3+ restarts** = stop the pod, halt loop, alert.

Numbers defined BEFORE the first signal so alarming wording can't drive reflexive action.

## 10. No-growth detector


```bash
# Each heartbeat: HEAD critical path file sizes; alert after 3 consecutive 0-growth heartbeats.
# Anti-pattern: monitoring only "new events" goes silent during a hang.
```

Monitor scripts under `dispatch/monitors/` MUST implement no-growth alongside state-change detection.

## 11. Stage-skip cache must verify outputs


```bash
# WRONG: pipe with || true / && cascade: set -e gets suppressed
if "$@" | tee log; then mark_complete; fi

# CORRECT: explicit exit-code capture + output verification
"$@"
RC=$?
if [ "$RC" = "0" ] && [ -s expected_output.tsv ]; then mark_complete; fi
```

`outcome=success` ≠ scientific success. Verify expected output files exist before writing the SUCCESS sentinel.

## 12. Pre-clean third-party FASTAs


- Third-party reference FASTAs (P450Rdb, MIBiG cluster GBKs, etc.) often contain stray characters (`/`, control chars).
- Default: 1-line Python pre-clean strips non-AA chars before `diamond makedb` / `makeblastdb`.
- Always sanity-check `awk '/^>/{c++; next}{l+=length($0)} END{print c " seqs, " l " aa"}'` after cleaning.

## 13. Verify upstream URLs before Dockerfile authorship


- For multi-tool images, dispatch ~$0.10 sub-agent to confirm canonical repo URL + install method + version pin + license BEFORE writing Dockerfile RUN directives.
- Saves wasted GHA build cycles on URL drift / deprecated installers / wrong forks.

## 14. License compliance

| Tool | License | Distribution constraint |
|---|---|---|
| plantiSMASH 2.0 | AGPL-3.0+ | Atlas-internal + static-Quarto + manuscript citation FINE; hosting a service downstream triggers source-publication requirement. |
| CLEAN | Apache-2.0 with research-use-only PDF | Atlas-internal use FINE; commercial hosting needs review. |
| All other tested tools | MIT/BSD/GPL/CC-BY | No additional constraints beyond Apache/MIT terms. |

Flag for license-review time: plantiSMASH AGPL implications.

---

## Appendix A: Cloud-specific deviations

The contract clauses above hold uniformly. The only cloud-native variations:

| Aspect | RunPod | AWS | GCP | Vast.ai | Lambda |
|---|---|---|---|---|---|
| Mount point | `/workspace` | `/mnt/efs` (EFS) or `/data` (EBS) | `/mnt/filestore` | `/workspace` | `/workspace` |
| Sentinel pull URL | `https://<pod-id>-8000.proxy.runpod.net/<file>` | `https://<bucket>.s3.<region>.amazonaws.com/<run>/<file>` | `https://storage.googleapis.com/<bucket>/<run>/<file>` | direct SSH or `vastai exec instance` | direct SSH |
| Self-stop | worker-side `POST /v1/pods/<id>/stop` | self via IAM role `aws ec2 terminate-instances` | self via SA `gcloud compute instances delete` | self via API `vastai destroy` | self via API `DELETE /instances` |
| Cache-bust | `?cb=$RANDOM` (proxy caches) | not needed (S3 has no proxy cache) | not needed | n/a | n/a |
| Volume cost / month | included in pod-hours | EBS ~$0.10/GB-month | Filestore ~$0.20/GB-month | host-disk only | host-disk only |
| GPU pricing tier | $0.40-$1.50/h | $1.00-$3.00/h | $0.80-$2.50/h | $0.20-$0.80/h | $0.50-$1.50/h |
| CPU pricing tier | $0.05-$0.30/h | $0.05-$0.20/h | $0.04-$0.20/h | $0.05-$0.30/h | n/a |

## Appendix B: Boot-script skeleton

The reference skeleton lives at `images/genecluster-superpowers/scripts/_boot-skeleton.sh`. Per-tool boots inherit it via `source` or copy-modify.

```bash
#!/bin/bash
# Boot skeleton: implements every CONTRACT clause.

set -uo pipefail

TOOL="${TOOL_NAME:?TOOL_NAME env var must be set}"
MOUNT="${MOUNT_PATH:-/workspace}"
WORK="$MOUNT/superpowers/$TOOL"
mkdir -p "$WORK"
cd "$WORK"

# §1 stale sentinel cleanup
rm -f SUCCESS FAILURE *.summary.tsv

# §4 optional summary HTTP
if [ "${RUNPOD_EXPOSE_HTTP:-0}" = "1" ]; then
 python3 -m http.server 8000 --directory "$WORK" > http.log 2>&1 &
 HTTP_PID=$!
 sleep 2
fi
echo "phase=started ts=$(date -u +%s)" > STATUS

cleanup_on_failure() {
 echo "phase=verify_failed ts=$(date -u +%s)" > STATUS
 ls -la > FAILURE 2>&1
 cat *.log 2>/dev/null | tail -50 >> FAILURE
 echo "Idling 5 min for operator inspection..."
 sleep 300
 exit 1
}

# … tool-specific install + work …

# §1 verify expected outputs before SUCCESS
ALL_OK=1
[ -s "$TOOL-summary.tsv" ] || ALL_OK=0
[ "$RC" = "0" ] || ALL_OK=0

if [ "$ALL_OK" = "1" ]; then
 echo "phase=success ts=$(date -u +%s)" > STATUS
 echo "complete" > SUCCESS
 ls -lh > ls-output.txt
 sleep "${IDLE_SECONDS:-1800}"
else
 cleanup_on_failure
fi
```
