# GeneCluster Linear Issue Extension

Use this extension inside BioSymphony Linear issue contracts for GeneCluster work. It adds scientific claim boundaries, artifact contracts, agent handoffs, and review gates on top of the general `templates/linear-issue.md` structure.

## Required GeneCluster Sections

GeneCluster issues should include these sections in addition to the base Linear issue contract sections:

- `## Agent Role` - the bounded worker role for this issue, such as query curation, candidate discovery, genome-context review, coexpression review, synteny review, claim audit, or next-experiment design
- `## Evidence Class` - one or more controlled evidence classes from this reference
- `## Artifact Contract` - concrete expected output paths plus format, provenance, remote-only, and no-raw-data requirements
- `## Review Gate` - the human or reviewer-agent decision that must happen before downstream work can rely on the issue
- `## Handoff Notes` - what downstream agents may consume, what remains remote-only, and what caveats must be preserved
- `## Claim Boundary` - explicit allowed and forbidden claims
- `## Orchestration Guardrails` - prompt render, provider payload, snapshot/branch, no-silent-fallback, and route/payload checks required before dispatch or launch
- `## Resume / Recovery Contract` - checkpoint artifact, resume command, degraded recovery marker, and wakeup retry diagnostics

Keep `## Validation Commands` exact and runnable from the repo root. Do not leave placeholder text in commands.

If a worker has to recover from an empty prompt body, missing issue text,
missing bundle, wrong worker/team, oversized provider payload, or stale provider
error hypothesis, it must mark the issue as degraded in the closeout comment.
Recovery is useful, but silent recovery is not acceptable evidence that the
orchestration path is healthy.

## Supported Run Scopes

Use these scope names when drafting or dry-running GeneCluster issue sets:

- `smoke` - metadata, ledger, resource, launch-bundle, and provenance wiring only
- `candidate_search` - query/domain/homology candidate discovery plus candidate dossier review
- `genome_context` - candidate coordinate anchoring and neighborhood review
- `coexpression` - expression/module support for candidate prioritization
- `synteny` - orthology and conserved-neighborhood review for genome-localized candidates
- `full_public_mining` - candidate search, genome context, coexpression, synteny, and public claim audit
- `next_experiment_design` - experiment planning from reviewed public-data gaps

Private or example campaigns may define campaign-specific aliases for backward
compatibility. Public skill docs and issue templates should default to the
generic scope names above.

## Evidence Class

- `transcript_hit`
- `protein_hit`
- `domain_hit`
- `genome_localized`
- `neighborhood_supported`
- `coexpression_supported`
- `review_required`

## Artifact Contract

Expected outputs must list concrete paths. The contract details should say which artifacts are local summaries and which large artifacts remain in provider-managed storage.

Common output paths include:

- `data-ledger.tsv`
- `query-ledger.tsv`
- `resource-ledger.tsv`
- `candidate_hits.tsv`
- `cluster_neighborhoods.tsv`
- `candidate-ranking.tsv`
- `coexpression_edges.tsv`
- `synteny_blocks.tsv`
- `orthogroups.tsv`
- `evidence.jsonl`
- `provenance.jsonl`
- `versions.json`
- `licenses.tsv`
- `citations.bib`
- `claim-ledger.md`
- `next-experiment-brief.md`
- `dossier-manifest.json`

Artifact contracts must preserve these rules:

- raw sequence data, genome assemblies, BLAST/MMseqs databases, workflow workdirs, and indexes stay outside the repo
- returned local artifacts are small summaries, manifests, ledgers, reports, or spreadsheets
- every claim row links to evidence and provenance identifiers
- provider credentials are never recorded in issue bodies, ledgers, or dossiers

## Review Gate

Every GeneCluster issue should state the decision needed before downstream work can depend on it. Typical review gates:

- accept/reject metadata and license posture before provider upload
- accept/reject broad-family query seeds before candidate search
- accept/reject candidate rows before genome-context, coexpression, or synteny lanes
- accept/reject physical-cluster claims only when genome coordinates and boundary logic are present
- accept/reject next-experiment recommendations before vendor-facing or wet-lab planning

## Handoff Notes

Handoff notes should name the exact artifact fields downstream agents may consume. Prefer stable identifiers such as:

- `candidate_id`
- `query_id`
- `dataset_id`
- `evidence_ids`
- `neighborhood_cluster_id`
- `orthogroup_id`
- `synteny_block_id`
- `coexpression_module`

State any preserved caveats directly in the handoff notes, especially transcriptome-only limits, broad-family false-positive risk, incomplete genome coordinates, and unresolved product chemistry.

## Claim Boundary

Every GeneCluster issue should explicitly state:

- This issue may claim: `<allowed claim>`
- This issue must not claim: `<forbidden overclaim>`

Common forbidden overclaims:

- transcriptome-only evidence proves a physical gene cluster
- broad CYP/OMT/reductase homology proves product chemistry
- genome neighborhood implies pathway membership without supporting evidence
- candidate discovery is experimental validation
