# GeneCluster Live Run Checklist

Status: pre-execution checklist v1
Last reviewed: 2026-04-30

Use this before launching a real provider-backed GeneCluster run. The public
default is provider-neutral: start with `smoke` or `candidate_search`, then
escalate to `full_public_mining` only after target materialization, target
search, and claim gates are proven. Private/example campaigns may define
campaign-specific one-day aliases, but public skill instructions should not
depend on them.

## Hard Blockers

Clear these before `--execution-ready` should pass.

1. Build or select a pinned runner image.
   - Required form: `registry/name@sha256:<digest>` or equivalent digest-pinned
     image.
   - Must include BLAST+, `update_blastdb.pl`, DIAMOND, MMseqs2, HMMER,
     miniprot, SRA Toolkit, NCBI Datasets, minimap2, Nextflow, Python 3, and
     SQLite support.
   - Must include OpenJDK 17+ so the Nextflow installer/runtime works.
   - First-boot `mamba install` is a development/emergency fallback, not the
     normal launch path.
   - For standard full/candidate runs, first-boot package installation is a
     blocker. Use a baked image. Emergency boot installs require an explicit
     degraded runbook, `--allow-first-boot-install`, generous container disk,
     persistent logs, and an independent watcher.
   - If the image lives in GHCR, GitLab registry, ECR/GAR/ACR, Quay, or another
     auth-sensitive registry, configure RunPod container registry auth before
     launch. Set only the auth record id in
     `GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID` or
     `RUNPOD_CONTAINER_REGISTRY_AUTH_ID`.
   - If the image is public-pullable without auth, record that explicitly with
     `GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL=1` only after verifying the exact
     digest can be pulled by a clean environment.
   - Use at least the GeneCluster launcher default container disk (`80 GB`) for
     standard runs. Smaller disks are smoke/debug only and require
     `--allow-small-container-disk`.

2. Set provider credentials from a secure local secret store.
   - `RUNPOD_API_KEY`
   - `GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID`
   - `GENECLUSTER_RUNPOD_DATACENTER`
   - Optional for faster/cleaner NCBI EFetch: `NCBI_API_KEY`

3. Resolve high-confidence seed blockers.
   - Update `query-ledger.tsv` with public protein accessions, provider-side
     query FASTA pointers, or explicit context-only downgrades.
   - Do not let unresolved high-confidence canonical seeds silently become
     broad-family/domain-only searches.

4. Verify provider storage.
   - Network volume mounted at `/workspace`.
   - `/workspace/genecluster/{db-cache,search-cache,runs,nextflow-cache,sra-cache,scratch}`
     is writable.
   - `search_result_cache` is present in `cache-ledger.tsv`.
   - Do not use `s3://`, `gs://`, `r2://`, `b2://`, or `az://` as executable
     DB/cache/work paths; those are backup targets until an object-store
     adapter exists.

5. Stage only candidate-search high-ROI databases first.
   - `blast_swissprot`
   - `diamond_swissprot`
   - `mmseqs_uniprotkb`
   - `mmseqs_pfam`
   - `hmmer_pfam`
   - `custom_pathway_seed_db` when the campaign defines one

6. Verify the provider lifecycle and summary transport contract.
   - `provider/runpod-pod.json` has `pod_lifecycle_policy.operator_side_cleanup_required: true`.
   - `pod_lifecycle_policy.provider_api_key_inside_pod` is `false`.
   - The Docker start command uses `provider/runpod-docker-start.sh` or an
     equivalent wrapper that writes status and idles for operator cleanup.
   - Pod monitoring checks `runtime` and `runtime.uptimeInSeconds`, not only
     `desiredStatus`.
   - Summary retrieval is configured through RunPod S3 / a configured summary
     endpoint, or a deliberate short-lived HTTP pull-pod fallback.

7. Verify the biological route, not just the runner flags.
   - Run `genecluster_route_audit.py --launch-manifest <bundle>/launch-manifest.json`.
   - If transcriptome evidence exists and the campaign wants a full scientific
     route, `genecluster_route_audit.py --require-transcript-first` must pass.
   - If the strict audit fails, the launch may still be a candidate-smoke or
     rescue run, but it is not a transcript-first full discovery run.
   - Direct genome `tblastn` is rescue/support evidence when transcript data is
     available; transcript/ORF/protein candidates come first, then genome
     anchoring.

8. Verify orchestration plumbing before dispatch or launch.
   - Rendered prompts must have a non-empty issue body; empty `<issue_body>` is
     a hard stop.
   - Provider payloads must pass byte-size preflight before any RunPod REST
     call; do not treat misleading capacity errors as capacity until payload,
     image, credentials, registry auth, and volume checks pass.
   - A pod whose `desiredStatus` is `RUNNING` but whose `runtime` remains null
     is not running user code. Stop it and diagnose image pull, registry auth,
     capacity, and volume attach before relaunching.
   - Snapshot/branch checks must prove the bundle and scripts are present in
     the exact Git ref cloned by the worker/pod.
   - Any worker recovery from missing prompt/body/bundle/provider state must be
     marked degraded in closeout, even if the worker recovers successfully.

9. Verify stage-level observability before long runs.
   - `stage-contract.json` must validate before dispatch.
   - `stage-contract.json` must include fail-closed `required_tools` proofs
     for exact stage executables, not only package names. For example, a
     transcript-first lane that calls TransDecoder must prove both
     `TransDecoder.LongOrfs` and `TransDecoder.Predict` are callable on the
     provider before the ORF stage starts.
   - Warning-only tool checks are not acceptable for live runs. If an executable
     is missing from `PATH`, the wrapper may discover an installed provider path
     and export it, but it must then re-prove the command or exit before burning
     time on downstream biological stages.
   - Every long-running provider command must write `stage-progress.jsonl`
     records with `started`, periodic `heartbeat` or stage output growth, and
     a terminal status.
   - A watcher issue/worker is recommended for runs longer than two hours. It
     should poll every 10-15 minutes and check provider runtime, stage progress,
     current logs, and summary artifacts before assuming capacity or scheduler
     failure.
   - Restart timing is only a triage signal. Do not claim the failing stage from
     elapsed time alone; confirm against `stage-progress.jsonl`, per-stage logs,
     and output markers before patching or reporting root cause.
   - Partial completion is acceptable only when the final dossier names the
     failed/skipped stage, records a resume command, and downgrades claims.

10. Estimate context-lane fanout before launch.
   - Candidate search and cluster/context annotation are separate maturity
     levels. A run can produce useful real target hits while still deferring
     exhaustive neighborhood/domain annotation.
   - Before window, domain, coexpression, synteny, or graph/pangenome lanes,
     estimate cardinality: queries, candidate hits, deduplicated anchors,
     windows, proteins per window, database profiles, and expected runtime.
   - If cardinality exceeds the runtime budget, activate a bounded branch:
     top-N hits per query, deduplicated anchors, smaller curated HMM/DB set,
     representative windows, or explicit `deferred_by_budget` rows.
   - Prefer "annotate once, join many": scan the target proteome/transcriptome
     once for Pfam/CDD/domain calls and join those calls into windows instead
     of scanning each window independently against the full DB.

## Preflight Sequence

For provider-side raw genome/SRA acquisition, also follow
`genecluster-provider-data-materialization.md`. In short: resolve accessions,
resolve read layout, fetch raw data only on the provider, validate
materialized target artifacts, build target indexes, then search. Local pullback
should stay to compact summaries and review artifacts unless the operator
explicitly requests otherwise outside the repo.

Generate and validate the bundle locally:

```bash
python3 skills/biosymphony/scripts/genecluster_launch_bundle.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --provider-class runpod_pod \
  --run-scope full_public_mining \
  --run-id genecluster-full-public-mining-runpod-prep \
  --image <digest-pinned-image> \
  --allow-provider-large-downloads \
  --out .runtime/genecluster-launch-full-public-mining

python3 skills/biosymphony/scripts/genecluster_preflight.py \
  --launch-manifest .runtime/genecluster-launch-full-public-mining/launch-manifest.json \
  --execution-ready

python3 skills/biosymphony/scripts/genecluster_route_audit.py \
  --launch-manifest .runtime/genecluster-launch-full-public-mining/launch-manifest.json

python3 skills/biosymphony/scripts/symphony_orchestration_preflight.py \
  --git-ref <private-run-branch> \
  --required-path .runtime/genecluster-launch-full-public-mining/launch-manifest.json

python3 skills/biosymphony/scripts/genecluster_stage_contract.py \
  --stage-contract .runtime/genecluster-launch-full-public-mining/stage-contract.json
```

Run provider preflight before candidate search:

```bash
python3 remote/genecluster_remote_runner.py \
  --launch-manifest launch-manifest.json \
  --max-runtime-hours 24 \
  --toolcheck \
  --db-bootstrap \
  --data-materialization \
  --target-db-build \
  --cache-preflight \
  --reference-import \
  --query-preflight \
  --resolve-queries \
  --decoy-preflight
```

During launch, watch the provider state:

```bash
# Pseudocode: use RunPod MCP, runpodctl, or REST depending on available tooling.
# Do not treat desiredStatus=RUNNING as sufficient.
check pod.desiredStatus
check pod.runtime != null
check pod.runtime.uptimeInSeconds increases between polls
```

If `runtime` remains null after the payload timeout, stop the pod and diagnose
capacity/provisioning before retrying. If the runner exits, make sure the pod
is stopped by the operator-side monitor before it repeatedly restarts the same
`dockerStartCmd`.

Only then run candidate search:

```bash
python3 remote/genecluster_remote_runner.py \
  --launch-manifest launch-manifest.json \
  --max-runtime-hours 24 \
  --candidate-search
```

Only after the candidate table and public reference import are reviewed, run the
coordinate context lanes:

```bash
python3 remote/genecluster_remote_runner.py \
  --launch-manifest launch-manifest.json \
  --max-runtime-hours 24 \
  --anchor-map \
  --neighborhood-extract
```

For the first full campaign, run the same launch manifest with all planned
24-hour stages and keep `--max-runtime-hours 24`:

```bash
python3 remote/genecluster_remote_runner.py \
  --launch-manifest launch-manifest.json \
  --max-runtime-hours 24 \
  --toolcheck \
  --db-bootstrap \
  --data-materialization \
  --target-db-build \
  --cache-preflight \
  --reference-import \
  --query-preflight \
  --resolve-queries \
  --decoy-preflight \
  --candidate-search \
  --anchor-map \
  --neighborhood-extract \
  --pathway-completeness
```

For a later reviewed open-ended escalation that intentionally stages large
required DBs on the provider volume, add `--allow-large-downloads` to the DB
bootstrap/full runner command. Do not use that flag for a first full-context
campaign unless the volume/cache has already been prepared.

## Review Gates Before Full Context

Do not run full-context lanes until these are reviewed:

- `genecluster_input_audit.py --require-known-data` has been run on the launch
  bundle. Workers must summarize existing `data-ledger.tsv` and
  `query-ledger.tsv` entries before asking the operator questions, and may ask
  only generated `intake_interview.questions` whose answers are not already in
  the ledgers/plans. Use `--interview-mode quick` for blockers only,
  `standard` for normal confirmation, `strict` before high-risk heavy claims,
  and `skip` only when the user explicitly says to use defaults.
- The exact launch bundle path exists in the private Git ref the RunPod pod will
  clone. `genecluster_runpod_rest_launch.py` checks this by default; do not pass
  `--skip-git-ref-check` unless another bundle delivery path is already proven.
- `genecluster_contract_self_check.py --require-real-target-search` passes on
  the returned summary directory before a worker posts success.
- `genecluster_stage_contract.py --progress-jsonl <summary>/stage-progress.jsonl
  --require-terminal` passes. If a stage failed or was skipped, the closeout is
  `partial` unless the failure is explicitly outside the selected scope.
- `genecluster_route_audit.py --require-transcript-first` passes before a
  worker describes the run as transcript-first/full-scientific-ready. If it
  fails, report the run as target-nucleotide `tblastn` smoke/rescue readiness
  or implement the missing transcriptome/ORF/proteome/map-to-genome stages.
- `candidate-search-summary.json` reports `real_target_search_ok: true`,
  `target_commands_completed >= 1`, `mock_tools: false`, and nonzero
  `target_candidate_rows`.
- `data-materialization-summary.json` reports `ok: true` for at least one
  transcript/protein/genome target source or an existing target FASTA/protein/GFF
  input is documented. `dry_run: true` or `mock_tools: true` is a hard stop.
- `materialized-targets.tsv` or an existing target-source ledger proves where
  the target-organism search DB came from.
- `target-db-indexes.tsv` has built/present `target_*` indexes. `mocked`
  indexes and reference DBs such as SwissProt/Pfam do not satisfy target-search
  readiness.
- `candidate_hits.tsv` has candidate rows, not only broad-family noise.
- Raw tool output is not enough for downstream synthesis. Live promotion should
  use normalized hit ledgers with headers, stable IDs, provenance, and evidence
  class labels. Known/native positive controls, cross-species homologs,
  broad-family/domain-only hits, decoys, and new candidate hypotheses should be
  distinguishable.
- `candidate_hits.tsv` rows used for target claims have `target_db_id` starting
  with `target_` and `dataset_id` from the target data ledger; rows with
  `provider_search` or `mock_provider_summary` are never deliverable evidence.
- `run_summary.json` has `candidate_search_ok: true`,
  `real_target_search_ok: true`, and `heavy_execution_performed: true`;
  required enabled DBs cannot be missing or failed even if another database
  produced hits.
- `decoy-preflight.json` has no missing negative controls.
- `claim-audit.jsonl` has no unsupported cluster/product claims.
- `resolved-references.tsv` identifies a viable public genome/protein/GFF
  source before coordinate claims are promoted.
- `candidate_anchors.tsv` has anchored rows before neighborhood or cluster
  evidence is treated as more than a planned lane.
- `run-economics.json` still keeps `optional_max` databases deferred unless
  candidate evidence is ambiguous.
- A genome/GFF/protein reference is viable before plantiSMASH, synteny, or
  neighboring-gene visualization is treated as more than a planned lane.
- `toolcheck.json` shows real provider tool paths and versions, including
  Nextflow and `update_blastdb.pl`; mock paths are not acceptable for live
  promotion.
- `stage-contract.json` and provider boot logs prove exact stage commands are
  callable. A package manager saying `transdecoder` or another multi-script
  package is installed is not enough if `TransDecoder.LongOrfs` and
  `TransDecoder.Predict` are absent from `PATH`.
- `db-bootstrap-summary.json` fails closed when required DBs are missing. A run
  with all required DBs marked `blocked_preload_required` is not successful just
  because the bootstrap script itself completed.
- A partial run must still produce a closeout summary even when a late context
  lane fails. The summary should name completed stages, missing stages, validated
  artifacts, missing artifacts, claim downgrades, and the next resume command.

The current today-ready target-search path for transcript-like SRA is SRA
Toolkit -> FASTQ -> provider target FASTA -> BLAST nucleotide DB -> `tblastn`
with canonical protein seeds. That is candidate-smoke/rescue evidence, not the
preferred full scientific route when transcript data exists. The preferred route
is transcriptome curation/import/assembly -> ORF/protein prediction -> protein
candidate search -> splice-aware transcript-to-genome anchoring -> neighborhood
capture. Until those stages are wired and the strict route audit passes, do not
call a run "full transcript-first discovery."

For SRA Toolkit stages, record the accession ladder explicitly. User inputs may
be BioProject, SRS/SRX/ERX/DRX experiment accessions, or SRR/ERR/DRR run
accessions. `prefetch` may accept the broader accession, but `fasterq-dump`
must be pointed at the concrete downloaded `.sra` artifact or resolved run
directory, not a guessed SRX path. A live SRA stage is not acceptable until it
has written:

- `resolved-accessions.tsv` or equivalent with input accession -> run accession
  mapping.
- `sra-layout.tsv` or equivalent with each run accession, `LibraryLayout`, read
  lengths when available, and whether the downstream branch is single-end,
  paired-end, or mixed/degraded.
- a command log showing `prefetch` and `fasterq-dump` inputs separately.
- non-empty FASTQ outputs.
- a non-empty target FASTA or transcript/protein artifact consumed by the
  target DB builder.

Alignment/assembly branches must consume that layout metadata. A single-end run
should not fail because `*_2.fastq` is absent; a paired-end run should fail
closed if only one mate is present unless the campaign explicitly declares a
single-end rescue/degraded branch. For HISAT2, use `-U` for single-end and
`-1/-2` for paired-end. Equivalent branching is required for STAR, minimap2
short-read modes, Trinity/rnaSPAdes, and quantification tools.

## Summary Retrieval And Cleanup

Prefer RunPod S3 / network-volume object access for summary pullback:

```bash
aws s3 cp \
  --endpoint-url "https://s3api-${GENECLUSTER_RUNPOD_DATACENTER}.runpod.io" \
  "s3://<volume-or-bucket>/genecluster/runs/<run_id>/summary/" \
  .runtime/<run_id>-summary/ \
  --recursive \
  --exclude "*" \
  --include "*.json" --include "*.jsonl" --include "*.tsv" --include "*.xlsx" --include "*.html"
```

Use the short-lived HTTP pull pod only when S3/volume object access is not set
up. Stop the main pod until summaries validate; delete pods only after
`dossier-manifest.json`, `run_summary.json`, `versions.json`, artifact
boundaries, and cleanup decisions are reviewed. The network volume persists
independently of pod deletion.

## Optional Escalations

Escalate only after candidate review:

- Add RefSeq plant proteins and plant TrEMBL if curated DBs miss expected
  homologs.
- Add CDD/RPS-BLAST when spreadsheet-compatible CDD reporting is needed.
- Add MIBiG 4.0 proteins and plantiSMASH 2.0 once genome coordinates are
  available.
- Add InterProScan after the candidate set is small enough to annotate cheaply.
- Add `nr`, `nt`, or UniRef only if the curated/plant-biased search is
  inconclusive.
