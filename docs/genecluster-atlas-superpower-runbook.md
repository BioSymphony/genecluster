# GeneCluster Atlas Superpower Runbook

## Purpose

GeneCluster Atlas turns a pathway/species question into a routed, evidence-checked campaign: scout public data availability, select the least-overclaiming route, run bounded worker waves, and return ledgers, evidence packages, and review surfaces.

## Public Defaults

- Optimize first for reproducible GeneCluster depth, not raw compute.
- Keep orchestration tracker-neutral: issue contracts can live in Linear, GitHub Issues, or another private tracker.
- Keep paid provider mutation outside the public repo. Public files should prepare manifests and validation contracts only.
- Pull back summaries, ledgers, reports, versions, hashes, claim checks, and review HTML only.
- Do not pull raw reads, full genomes, private sequences, heavy indexes, model weights, or database payloads into this repo.

## Source And Route Scout

Every GeneCluster campaign starts with registry-backed source scouting, then route selection:

```bash
python3 skills/biosymphony/scripts/genecluster_source_scout.py \
  --campaign path/to/campaign-manifest.json \
  --query-registry skills/biosymphony/references/genecluster-query-registry.tsv \
  --out-dir .runtime/genecluster-source-scout \
  --json

python3 skills/biosymphony/scripts/genecluster_preflight.py \
  --query-registry skills/biosymphony/references/genecluster-query-registry.tsv \
  --required-claims skills/biosymphony/references/required-claims.tsv \
  --source-ledger .runtime/genecluster-source-scout/source-ledger.tsv \
  --json
```

The scout writes:

- `source-ledger.tsv` - route-readable source rows plus query/source probe rows.
- `query-resolution-ledger.tsv` - per-query resolution status and claim ceiling.
- `source-scout-report.json` - probe order, counts, policy, and blockers.

After source scouting, run the route scout:

```bash
python3 skills/biosymphony/scripts/genecluster_annotation_scout.py \
  --campaign path/to/campaign-manifest.json \
  --query-fasta path/to/query-with-controls.faa \
  --source-ledger .runtime/genecluster-source-scout/source-ledger.tsv \
  --out-dir .runtime/genecluster-atlas/route-scout \
  --json

python3 skills/biosymphony/scripts/genecluster_preflight.py \
  --route-annotation-ledger .runtime/genecluster-atlas/route-scout/annotation-ledger.tsv \
  --json
```

The query FASTA should include positive controls such as ACT2/GAPDH and a negative random-shuffle control. The route card records the claim ceiling, blockers, source availability, controls, and rejected routes.

## Annotation-Direct Engine

The annotation-direct wrapper shape is:

```bash
python3 pipeline/genecluster_annotation_direct/run.py \
  --species coptis_chinensis \
  --proteome /opt/inputs/proteome.faa \
  --gff /opt/inputs/genomic.gff \
  --queries /opt/inputs/queries.faa \
  --pfam-hmm /opt/dbs/Pfam-A.hmm \
  --swissprot-dmnd /opt/dbs/swissprot.dmnd \
  --workdir /workspace/genecluster \
  --window-kb 50 \
  --threads 8
```

Expected summary outputs:

- `results.xlsx`
- `cluster_neighborhoods.tsv`
- `neighbor_pfam.tsv`
- `neighbor_swissprot.tsv`
- `controls-qc.json`
- `run-summary.json`
- `biology-interpretation.md`

## Atlas Ledgers

Validate comparative contracts before accepting outputs:

```bash
python3 skills/biosymphony/scripts/genecluster_atlas_contracts.py \
  --cluster-calls .runtime/genecluster-atlas/cluster_calls.tsv \
  --bgc-consensus .runtime/genecluster-atlas/bgc_consensus.tsv \
  --protein-function-votes .runtime/genecluster-atlas/protein_function_votes.tsv \
  --protein-function-jury .runtime/genecluster-atlas/protein_function_jury.tsv \
  --comparative-atlas .runtime/genecluster-atlas/comparative_atlas \
  --review-surface-manifest .runtime/genecluster-atlas/review_surface_manifest.json \
  --provider-handoff-manifest .runtime/genecluster-atlas/provider_handoff_manifest.json \
  --json
```

The validators reject missing IDs, unresolved claims, raw-heavy local artifacts, collapsed caller disagreement, collapsed protein-function contradictions, and literal secret values in provider handoffs.

## Provider Handoff

The public repo should prepare provider handoff manifests only. A trusted operator environment owns paid launch, monitoring, egress, hashing, cost capture, cleanup, and reconciliation.

Before any paid provider run:

- verify credentials from a secure store, not repo files
- confirm the image digest and license posture
- confirm required cache/database paths exist provider-side
- ensure output pull is summary-only
- ensure cleanup is operator-side or provider-native

Do not declare success until declared artifacts are fetched, validated, hashed, and provider cleanup is verified.

## Completion Definition

- A user can ask a GeneCluster question and receive a route card, issue DAG, validated handoff bundle, evidence-checked outputs, and review surface.
- At least one annotation-direct species remains reproducible from public fixtures or operator-supplied data.
- At least one comparative atlas dry run covers 3-4 species.
- Every accepted claim states evidence level and caveats.
