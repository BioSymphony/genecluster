---
name: biosymphony
description: Use when planning or executing BioSymphony GeneCluster campaigns to find biosynthetic gene clusters and assemble pathway support across genomes and transcriptomes. Applications include bioprospecting toward target molecules, pathway gap-filling, comparative atlas building, and novel-cluster discovery. The skill provides source/query ledgers, route scouting, candidate search, function scoring, claim checks, task contracts, check commands, and provenance.
---

# BioSymphony

BioSymphony GeneCluster turns "find this gene cluster" or "assemble this pathway" into comparative-genomics campaign contracts that bounded workers can execute and reviewers can inspect. It gives agents public source ledgers, query and control resolution, route cards, candidate search, function scoring, BGC calls, and claim-bounded pathway review packets.

## Operating model

Use the operator's existing orchestrator or tracker when the campaign needs
worker fan-out. That can be Symphony + Linear, another tracker, a `/goal` setup,
or a solo capable-agent pass for small work. Do not create a new daemon or
background service for v1.

BioSymphony is a control-plane skill kit for capable agents. Use it to get
campaign shapes, check commands, issue contracts, route cards, provider
handoffs, and review artifacts. Make ordinary orchestration decisions, write
small adapters when needed, and choose whether a tracker adds value. Escalate
to external compute only after the route, artifact contract, and claim ceiling
are clear.

Use BioSymphony as a local-first skill kit:

1. Classify the campaign by local capability tier.
2. Write tracker-neutral work units as scientific contracts.
3. Check each contract before dispatch.
4. Run only active waves through the selected orchestrator.
5. Require figure manifests for review artifacts.
6. Preserve provenance in campaign artifacts and tracker comments.

If an agent can choose the next bounded worker, adapt a ledger, or write a
small adapter, let it do so. Keep the durable result in the campaign artifacts.

## Stage 0: Campaign data preflight

Every campaign must begin with a Stage 0 preflight. Do not start a
`genecluster_*` maturity step until the preflight produces a valid
`campaign-launch-readiness.json` produced by `genecluster_campaign_preflight.py`.

The preflight answers five operator-facing questions before any compute spend:

| Pillar | What it surfaces | Where it comes from |
|---|---|---|
| **Data** | assembly state, RNA-Seq breadth, and annotation status for the target and its comparators | NCBI Datasets v2, SRA `esearch`, and the NGDC GWH fallback |
| **Inputs** | seed protein query set (UniProt anchors + controls) | KEGG REST + `data/pathway-species-catalog.tsv` + optional user TSV |
| **Relevance** | pathway overlap across related and convergent producers | NCBI E-utilities taxonomy walk |
| **Novelty** | existing publications mapping pathway-to-species; reviewable novelty windows | catalog `key_publication_pmid` + multi-pass literature check |
| **Importance** | composite comparative-value ranking for sequencing-priority decisions | deterministic score: annotation + tissue breadth + recency + catalog comparative_value |

### Two operating modes

**Mode A: user-supplied comparators and queries.** If you know which comparator
species and seed proteins to use, pass them explicitly:

```bash
python3 scripts/genecluster_campaign_preflight.py \
  --target "Coptis chinensis" \
  --pathway BIA \
  --campaign-id coptis-bia-example \
  --out-dir .runtime/<campaign-id>-preflight \
  --comparative-species "Berberis vulgaris,Eschscholzia californica,Argemone mexicana" \
  --seed-queries-tsv .runtime/<campaign-id>-preflight/operator-seed-queries.tsv
```

The preflight cross-checks every comparator against `data/pathway-species-catalog.tsv`
and validates the seed-queries TSV (required columns, positive/negative controls,
duplicate `query_id`s, missing UniProt anchors).

**Mode B: automatic discovery.** If you do not supply comparators, the preflight
runs `genecluster_species_scout.py` to:

1. Select cataloged producers of the target pathway.
2. Search the NCBI taxonomy from genus to family for related species with a public genome.
3. Query NCBI Datasets v2, SRA `esearch`, and the NGDC GWH plants index for each candidate.
4. Resolve the pathway against KEGG and create a placeholder seed-query set.

Resolve the placeholder queries to UniProt anchors before launch.

### Required artifacts

After a successful preflight, the campaign directory must contain:

```
.runtime/<campaign-id>-preflight/
├── campaign-launch-readiness.json     # downstream contract (preflight_status: ready)
├── campaign-preflight-summary.md      # top-level 5-pillar report
├── species_scout.tsv                  # candidate-by-candidate scout output
├── species_scout.json                 # structured findings
├── relevance-novelty-summary.md       # human report (Data / Inputs / Relevance / Novelty / Importance)
└── seed-query-candidates.tsv          # if KEGG resolved or operator-supplied
```

If `preflight_status != "ready"`, stop the campaign.

### Enriching the catalog

After a campaign, update `data/pathway-species-catalog.tsv` with supported
findings. Add new species, update `key_publication_pmid`, refine
`comparative_value` from concrete synteny or cluster results, and set
`last_audit_date`. Cite the evidence for each change.

See `references/docs/biosymphony-campaign-preflight-runbook.md` for the full operator runbook.

## Required checks

Before making local capability claims, run:

```bash
python3 scripts/capability_probe.py --json
```

Before packaging or reviewing the public BioSymphony skill, run the public skill
check:

```bash
python3 scripts/biosymphony_public_skill_audit.py \
  --skill-root skills/biosymphony
```

Before dispatching a Linear issue body to Symphony, check it:

```bash
python3 scripts/preflight_check.py path/to/issue.md
```

Before dispatching a rendered worker prompt, provider payload, or snapshot-based
handoff, run the orchestration preflight:

```bash
python3 scripts/symphony_orchestration_preflight.py \
  --rendered-prompt path/to/rendered-prompt.md

python3 scripts/symphony_orchestration_preflight.py \
  --provider-payload path/to/provider-payload.json

python3 scripts/symphony_orchestration_preflight.py \
  --git-ref <reviewed-git-ref> \
  --required-path .runtime/<bundle>/launch-manifest.json
```

Rendered prompts must contain a non-empty issue body. Keep provider payloads
under the configured byte limit. Confirm that the worker can access each
required script and bundle. Stop if the system silently selects a different
worker, team, or provider mode. Mark any recovery from missing prompt, body, or
provider state as degraded in the closeout.

Before accepting a figure dossier, check its manifest:

```bash
python3 scripts/figure_manifest_check.py figure-dossier/figure_manifest.json
```

Before dispatching or accepting a GeneCluster campaign prep artifact, check
the user/campaign-specific ledgers:

```bash
python3 scripts/genecluster_preflight.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --project-goals <campaign-dir>/project-goals.yaml \
  --pathway-steps <campaign-dir>/pathway-steps.tsv \
  --data-ledger <campaign-dir>/data-ledger.tsv \
  --query-ledger <campaign-dir>/query-ledger.tsv \
  --resource-ledger <campaign-dir>/resource-ledger.tsv \
  --database-ledger <campaign-dir>/database-ledger.tsv \
  --cache-ledger <campaign-dir>/cache-ledger.tsv
```

Provider launch bundles also include `artifact_pull.yaml`, a summary-only pull
contract that controls which returned files may be copied back locally:

```bash
python3 scripts/genecluster_preflight.py \
  --artifact-pull-manifest <bundle-dir>/artifact_pull.yaml
```

The pull manifest must stay `pull_summaries_only`, require post-pull checksums,
exclude raw/heavy outputs, and keep local destinations under `.runtime` unless
the operator explicitly reviews a different summary location.
`--launch-manifest` checking follows and hashes this pointer when present, so
launch bundles fail preflight if the return-artifact policy drifts.

Before planning or dispatching a GeneCluster Atlas campaign, run the source
scout, then the route scout. The source scout is deterministic and registry-only:

```bash
python3 scripts/genecluster_source_scout.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --query-registry references/genecluster-query-registry.tsv \
  --out-dir .runtime/genecluster-source-scout \
  --json

python3 scripts/genecluster_preflight.py \
  --query-registry references/genecluster-query-registry.tsv \
  --required-claims references/required-claims.tsv \
  --source-ledger .runtime/genecluster-source-scout/source-ledger.tsv
```

`source-ledger.tsv` rows include `source_record_type`, `source_provider`,
`source_accession`, `source_accession_kind`, `material_type`, and
`acquisition_policy` so mixed route/scout ledgers remain machine-auditable. The
source scout must stay `metadata_only_no_network_no_raw_download`.

When a campaign needs public read acquisition metadata, resolve SRA-style
accessions before materialization and check the normalized read contract:

```bash
python3 scripts/genecluster_sra_runinfo.py \
  --data-ledger <campaign-dir>/data-ledger.tsv \
  --out-dir .runtime/genecluster-sra-runinfo \
  --json

python3 scripts/genecluster_preflight.py \
  --read-accessions .runtime/genecluster-sra-runinfo/read-accessions.tsv
```

Then run the route scout and keep both outputs with the campaign packet:

```bash
python3 scripts/genecluster_annotation_scout.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --query-fasta <campaign-dir>/query-with-controls.faa \
  --source-ledger .runtime/genecluster-source-scout/source-ledger.tsv \
  --out-dir .runtime/genecluster-atlas/route-scout \
  --json
```

The query FASTA must include ACT2, GAPDH, and random-shuffle or negative
controls. The route card must record rejected routes and claim ceilings before
any worker wave starts.

Before accepting GeneCluster Atlas function-scoring, comparative, review, or
provider handoff artifacts, check the Atlas contracts:

```bash
python3 scripts/genecluster_atlas_contracts.py \
  --cluster-calls .runtime/genecluster-atlas/cluster_calls.tsv \
  --bgc-consensus .runtime/genecluster-atlas/bgc_consensus.tsv \
  --protein-function-votes .runtime/genecluster-atlas/protein_function_votes.tsv \
  --protein-function-jury .runtime/genecluster-atlas/protein_function_jury.tsv \
  --comparative-atlas .runtime/genecluster-atlas/comparative_atlas \
  --review-surface-manifest .runtime/genecluster-atlas/review_surface_manifest.json \
  --provider-handoff-manifest .runtime/genecluster-atlas/provider_handoff_manifest.json \
  --json
```

To normalize compact mocked or already-run lane outputs into Atlas contracts
without running external tools:

```bash
python3 scripts/genecluster_atlas_normalizers.py \
  all \
  --out-dir .runtime/genecluster-atlas
```

To build the first static summary-only review surface:

```bash
python3 scripts/genecluster_review_surface.py \
  --final-deliverable .runtime/<atlas>-final-deliverable \
  --out-dir .runtime/genecluster-atlas/review \
  --json
```

Full JBrowse/clinker browser packages are second-tier deliverables. The first
review surface should contain summary HTML, workbooks, claim ledgers, versions,
hashes, and caveats only.

To create a summary-only GeneCluster dossier skeleton from candidate hits:

```bash
python3 scripts/genecluster_dossier_skeleton.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --candidate-hits <campaign-dir>/fixtures/candidate_hits.tsv \
  --out .runtime/genecluster-dossier-smoke

python3 scripts/genecluster_preflight.py \
  --dossier-manifest .runtime/genecluster-dossier-smoke/dossier-manifest.json
```

The skeleton emits `dossier-manifest.json`, `datapackage.json`, and
`ro-crate-metadata.json`. These are summary/provenance sidecars only; raw
FASTA/GFF/FASTQ/BAM/database artifacts must remain provider-side or in approved
remote storage.

To intake a public or synthetic spreadsheet-style request without fetching data:

```bash
python3 scripts/genecluster_excel_intake.py \
  --workbook "<PUBLIC_OR_SYNTHETIC_WORKBOOK>.xlsx" \
  --out .runtime/genecluster-example-intake \
  --campaign-id genecluster-example-v0
```

Before declaring a GeneCluster prep repo clean, scan for local raw/heavy sequence artifacts:

```bash
python3 scripts/genecluster_preflight.py \
  --repo-root . \
  --scan-local-artifacts
```

To prepare execution without launching compute, generate provider-neutral launch bundles:

```bash
python3 scripts/genecluster_launch_bundle.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --provider-class <local_lite|local_full|runpod_pod|ssh_hpc|cloud_vm> \
  --run-scope candidate_search \
  --run-id genecluster-candidate-search-prep \
  --out .runtime/genecluster-launch-candidate-search

python3 scripts/genecluster_preflight.py \
  --launch-manifest .runtime/genecluster-launch-candidate-search/launch-manifest.json
```

Before handing a long provider run to Symphony or another worker, validate the
stage contract. This catches untested shell pipelines that are launchable but
lack stage outputs, checkpoint markers, timeout budgets, or watcher rules:

```bash
python3 scripts/genecluster_stage_contract.py \
  --stage-contract .runtime/<bundle>/stage-contract.json
```

After a provider run or summary pullback, check declared primary outputs
rather than trusting done markers alone:

```bash
python3 scripts/genecluster_stage_contract.py \
  --stage-contract .runtime/<bundle>/stage-contract.json \
  --artifact-root .runtime/<bundle>-summary \
  --check-expected-outputs
```

For a real provider-only SRA run, regenerate with
`--allow-provider-large-downloads`; execution-ready checking now fails if
transcript-like SRA materialization is planned but the runner command lacks
`--allow-large-downloads`.

To require actual launch readiness after RunPod env vars, volume metadata, and an image digest are set:

```bash
python3 scripts/genecluster_preflight.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --execution-ready
```

Before asking the operator for missing GeneCluster data links, query lists, or
resource slots, check the bundle inputs first:

```bash
python3 scripts/genecluster_input_audit.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --require-known-data \
  --interview-mode standard \
  --markdown-out .runtime/<bundle>/input-audit.md
```

If the input report lists accessions or source URLs, do not ask the operator to provide
those same links again. Ask only generated `intake_interview.questions` whose
answers are not already present in the ledgers or plans.

GeneCluster interview modes:

- `quick`: ask only blocking questions.
- `standard`: confirm blockers plus high-risk route/claim decisions.
- `strict`: require resolution before heavy execution claims.
- `skip`: ask nothing; record assumptions and proceed only within claim limits.

If the user says "skip and go", "use defaults", "assume defaults", or "no
interview", rerun with `--interview-mode skip` and use the generated assumptions
as the campaign record. Do not use skip mode to bypass execution-ready, route,
or real-target-search checks.

For live RunPod launches, use the generated `provider/runpod-docker-start.sh`
or an equivalent status-and-idle wrapper, and monitor `runtime.uptimeInSeconds`
rather than only `desiredStatus`. Keep long-lived provider API keys
operator-side. Prefer RunPod S3 / configured summary endpoints for summary
retrieval; short-lived HTTP pull pods are fallback only.

Treat provider lifecycle status and scientific workload status as separate
signals. A pipeline can finish and write valid summary artifacts while the
operator-side monitor still needs to stop the pod before the idle window closes.
Watchers must poll both pod actuality (`runtime.uptimeInSeconds`, restart
pattern, terminal state) and provider artifacts (`.dockerstart_status`, `run_summary.json`,
`stage-progress.jsonl`, expected outputs). If artifacts prove `pipeline_exit=0`
but the pod keeps restarting, stop the pod, mark lifecycle cleanup as degraded,
and continue with artifact checks instead of waiting indefinitely.

For SRA-backed GeneCluster stages, never assume the accession in the intake
ledger is the path to pass to `fasterq-dump`. Resolve experiment/sample/project
accessions to concrete run accessions and, after `prefetch`, discover the
downloaded `.sra` artifact or SRR/ERR/DRR run directory before conversion. A
pipeline that calls `fasterq-dump /.../SRX...` after `prefetch SRX...` is not
execution-ready; it must prove a non-empty FASTQ and materialized target FASTA
before candidate search.

Use the resolver before writing or dispatching an SRA-backed pipeline:

```bash
python3 scripts/genecluster_sra_runinfo.py \
  --data-ledger <campaign-dir>/data-ledger.tsv \
  --out-dir .runtime/<bundle>/sra-runinfo
```

Also resolve and record `LibraryLayout` before alignment or assembly. Single-end
SRA runs must use single-read branches such as HISAT2 `-U` and must not require
`*_2.fastq`; paired-end runs must prove both mates exist and use paired-read
branches such as `-1/-2`. Do not infer layout from file-name hopes or from the
fact that the sequencer was Illumina.

For provider-side raw data acquisition, follow
`references/genecluster-provider-data-materialization.md`. The intended pattern
is remote-heavy and local-light: raw reads, BAMs, indexes, DBs, work dirs, and
scratch stay on the provider volume; local pullback defaults to compact
summaries, ledgers, candidate tables, reports, provenance, versions, and claim
checks. Compact derived FASTA/GTF artifacts may be pulled back for private review
only when useful, but raw/heavy artifacts should not be copied into the repo.

When reporting RunPod outcomes, separate first-attempt orchestration status from
final workload status. "Success" means declared artifacts were fetched,
checked, hashed, and cleanup was verified. A DNS/API failure, duplicate-guard
block, boot crash, or retry belongs in the outcome as a degraded/retried
orchestration event even when the final pod workload succeeds. A failed
operator-side cleanup after `pipeline_exit=0` is a degraded lifecycle event,
and must be reported with the cleanup
action taken.

For private or auth-sensitive runner images, digest pinning is necessary but not
sufficient. Configure RunPod container registry auth with
`GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID` or
`RUNPOD_CONTAINER_REGISTRY_AUTH_ID`, or explicitly assert a proven public-pull
image with `GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL=1`. A pod with
`desiredStatus=RUNNING` and null `runtime` is a failed start, not progress.
Standard GeneCluster launches require baked images; package installs inside
`dockerStartCmd` are rejected unless explicitly marked as emergency/debug with
`--allow-first-boot-install`.

When a finite RunPod pod uses an embedded `dockerStartCmd` wrapper, build it
with the generic gzip/base64 helper and keep the generated script below the
local byte ceiling before any paid API call:

```bash
python3 scripts/build_runpod_dockerstart.py \
  --template pipeline/<wave>/dockerstart.sh.template \
  --pipeline pipeline/<wave>/run.sh \
  --input QUERY_FASTA=path/to/query-sequences.faa \
  --out pipeline/<wave>/dockerstart.built.sh \
  --manifest-out pipeline/<wave>/dockerstart.manifest.json
```

If the RunPod MCP create-pod tool cannot express `networkVolumeId` or
`dockerStartCmd`, use the REST launcher after sourcing local secrets:

```bash
# Optional: source a local secure env file outside the repo.
# source /path/to/secure/runpod.env
python3 scripts/genecluster_runpod_rest_launch.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --git-ref <reviewed-git-ref> \
  --bundle-path .runtime/<bundle> \
  --pod-id-out .runtime/<bundle>/runpod-main-pod-id.txt \
  --dry-run
```

Remove `--dry-run` only after the bundle path is present in the Git ref the pod
will clone. The launcher intentionally fails if the bundle is not in that ref.

To dry-run the provider runner locally without biological downloads or live tools:

```bash
python3 .runtime/<bundle>/remote/genecluster_remote_runner.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --out .runtime/genecluster-runner-mock-summary \
  --max-runtime-hours 24 \
  --toolcheck \
  --db-bootstrap \
  --data-materialization \
  --target-db-build \
  --workflow-classes \
  --cache-preflight \
  --reference-import \
  --query-preflight \
  --decoy-preflight \
  --candidate-search \
  --anchor-map \
  --orthology-anchor \
  --neighborhood-extract \
  --neighborhood-score \
  --pathway-completeness \
  --mock-tools
```

Before any worker posts a final success claim for a real target-organism search,
run the stage/progress and contract self-checks:

```bash
python3 scripts/genecluster_stage_contract.py \
  --stage-contract .runtime/<bundle>/stage-contract.json \
  --progress-jsonl .runtime/<run_id>-summary/stage-progress.jsonl \
  --require-terminal
```

```bash
python3 scripts/genecluster_contract_self_check.py \
  --summary-dir .runtime/<run_id>-summary \
  --require-real-target-search
```

This must fail if `candidate_hits.tsv` is populated from reference/mocked
databases while target-species materialization or target DB build failed. For a
real target-organism success claim, `candidate-search-summary.json` must report
`real_target_search_ok: true`, at least one completed target command, and
nonzero target candidate rows; mock/dry-run summaries are hard failures.

Before choosing a biological execution route, run the route check:

```bash
python3 scripts/genecluster_route_audit.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json
```

If transcriptome support is declared and the campaign is trying to make a
full scientific route claim, the strict check must pass:

```bash
python3 scripts/genecluster_route_audit.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --require-transcript-first
```

When transcript support exists, transcript/ORF/protein candidate discovery is
the primary route. Direct genome `tblastn` is rescue/support unless no
transcriptome route is available. A bundle may be technically RunPod-launchable
for target nucleotide `tblastn` while still failing strict transcript-first
scientific readiness; do not collapse those into the same claim.

To check claim boundaries for a candidate table:

```bash
python3 scripts/genecluster_claim_audit.py \
  --candidate-hits <summary-dir>/candidate_hits.tsv \
  --out .runtime/genecluster-claim-audit.jsonl \
  --claim-ledger .runtime/genecluster-claim-ledger.md \
  --campaign-id <campaign-id>
```

To prepare Symphony/Linear planning issues without dispatching workers:

```bash
python3 scripts/genecluster_issue_dry_run.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --run-scope full_public_mining \
  --out .runtime/genecluster-linear-full-public-mining
```

## Reference map

- Capability tiers: `references/capability-matrix.md`
- Linear issue contract: `references/contract-template.md`
- Figure manifest schema: `references/figure-manifest.schema.json`
- GeneCluster public mining campaign: `references/campaigns/genecluster-public-mining.md`
- GeneCluster transcriptome-only campaign: `references/campaigns/genecluster-transcriptome-only.md`
- GeneCluster genome-context campaign: `references/campaigns/genecluster-genome-context.md`
- GeneCluster next-experiment campaign: `references/campaigns/genecluster-next-experiment-design.md`
- GeneCluster Linear issue extension: `references/genecluster-linear-issue-template.md`
- GeneCluster resource registry: `references/genecluster-resource-registry.md`
- GeneCluster remote execution: `references/genecluster-runpod-execution.md`
- GeneCluster provider data materialization: `references/genecluster-provider-data-materialization.md`
- GeneCluster cross-species discovery engine: `references/genecluster-cross-species-discovery.md`
- GeneCluster prep ROI triage: `references/genecluster-prep-roi.md`
- GeneCluster live run checklist: `references/genecluster-live-run-checklist.md`
- Claim pressure-test pattern: `references/claim-pressure-test-pattern.md`
- Public skill export policy: `PUBLIC_EXPORT.md`
- Sibling campaign pattern (variant-effect atlas): `references/campaigns/mechanistic-variant-atlas.md`
- GeneCluster example data: use operator-supplied public fixtures or synthetic fixtures from the active checkout.
- Variant-atlas example data: use operator-supplied public fixtures or synthetic fixtures from the active checkout.

Read only the relevant reference for the current task.

## Campaign policy

The main campaign family finds biosynthetic gene clusters and assembles pathway
support across genomes and transcriptomes. Use it to find a cluster, assemble
pathway support, investigate a pathway gap, or compare cluster topology. The
route specifications are under `references/campaigns/`. Use public or synthetic
fixtures for worked examples.

The same contract loop (source ledgers, query and control resolution, route cards with claim ceilings, candidate search, function scoring, claim checks, review packet) also hosts related campaign patterns:

- **Mechanistic Variant Atlas** (`references/campaigns/mechanistic-variant-atlas.md`). Use when the request is "explain why these variants produce this phenotype" or "check these structural-mechanism claims." Exercises content-dependent branching, multi-claim ledger, and claim-boundary checks on a variant x metric matrix rather than a genome x cluster matrix.

Tier B/C/D campaigns are experimental or remote until the capability probe proves the required tools exist.

## GeneCluster policy

GeneCluster uses BioSymphony as the control plane and the selected compute lane
as the execution plane. Keep the skill provider-neutral. The `local_lite`,
`local_full`, `runpod_pod`, `ssh_hpc`, and `cloud_vm` lanes use the same manifest
and artifact contracts. The RunPod adapter currently has the most complete
lifecycle, data-materialization, summary-sync, and self-check support. Use
another heavy lane only when it provides equivalent storage, tools, and summary
sync.

For non-public campaigns, do not launch remote compute or fetch raw biological data unless the user explicitly asks for execution. Prep-only work may create manifests, ledgers, review skeletons, launch bundles, and Linear issue drafts under ignored local folders such as `.runtime/`.

Expect sparse clues and inconsistent biological inputs. Plan for homolog search,
domain and function labels, deduplication, paralog and isoform review, and
neighbor capture. Add coexpression and synteny only when the available data
supports them. State the claim level for every result.

Never infer scientific completion from runner flags alone. A final plan/comment
must explicitly prove the current maturity level:

- `L0_control_plane_ready`: manifests and plans exist only **AND** Stage 0 preflight has been run. `.runtime/<campaign-id>-preflight/campaign-launch-readiness.json` exists with `preflight_status == "ready"` (see Stage 0 section above)
- `L1_provider_tool_ready`: provider image/toolcheck/lifecycle pass
- `L2_provider_db_ready`: required reference/domain DBs are present
- `L3_target_materialized_ready`: target species FASTA/protein/transcript/genome inputs and target indexes exist
- `L4_raw_sra_pipeline_ready`: SRA reads were fetched/converted and either materialized into searchable target sequences or explicitly assembled/imported
- `L5_claim_audited_dossier_ready`: legacy maturity id for a checked review packet; target candidate hits, anchors/neighborhoods where supported, provenance, versions, and claim checks pass

For transcript-like public SRA inputs, the documented path can materialize
provider-side target nucleotide FASTA and BLAST DBs, then run protein queries
with `tblastn`. De novo transcriptome assembly and physical cluster claims are
separate escalation lanes, not implied by `--allow-large-downloads`.

The default GeneCluster discovery pattern is cross-species and support-checked:
canonical genes/proteins from source species A -> target species B search -> reciprocal/orthology scoring -> genome anchoring -> neighborhood capture -> pathway completeness matrix. The A-to-B ladder must preserve search direction, target DB identity, reciprocal rank/status, anchor method, anchor confidence, and coordinate confidence. Protein-to-genome fallback should use `miniprot` on the provider when GFF/protein IDs do not anchor cleanly.

Run scopes:

- `smoke`: metadata, ledgers, provenance, and review-packet wiring
- `candidate_search`: homolog/domain search, deduplication, ranking, and candidate support
- `genome_context`: coordinate anchoring, neighboring genes, and cluster claim gates
- `coexpression`: expression/module support without cluster overclaims
- `synteny`: orthology, paralogy, and conserved-neighborhood support
- `full_public_mining`: provider-neutral full public/approved-data mining
- `next_experiment_design`: convert open support gaps into assay/sequencing/metabolomics plans
Campaign-specific aliases can exist in non-public examples for backward
compatibility, but public skill behavior should default to generic scopes such
as `smoke`, `candidate_search`, `genome_context`, `coexpression`, `synteny`,
`full_public_mining`, and `next_experiment_design`.


**Freshness.** Scan recent literature when you define a target. Treat
preprint-only support at the `candidate` ceiling unless you also cite a
peer-reviewed source. If a campaign has been inactive for more than three
months, compare the `version` columns in `database-ledger.tsv` and
`resource-ledger.tsv` with current upstream releases. Record version drift in
the closeout.

## Closeout standard

Every worker should finish with:

- Commands run exactly as written.
- Artifact paths and hashes, when applicable.
- A summary of changed areas.
- Limits for predicted structures, affinity estimates, generated designs, and rendering assumptions.
- A tracker-neutral closeout artifact with the outcome, checks, artifacts, limits, and next action.
- An optional tracker comment that links to the closeout artifact without adding private content.
- A literature-scan summary and any tool or database version drift.

## Rendering defaults

- PyMOL: use the app path for local ray-rendered static panels.
- ChimeraX: default to GUI + REST for rendering on macOS.
- ChimeraX `--nogui`: use for analysis only.
- ChimeraX `--offscreen`: treat as `unstable_macos` until a smoke test proves it for the campaign.
