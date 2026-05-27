# GeneCluster Prep ROI Triage

Status: run-prep guidance v1
Last reviewed: 2026-04-29

This note separates preparation that materially improves the first real
provider-backed run from impressive but burdensome work that should stay
optional until the candidate signal justifies it.

## High-ROI Prep Before The First Real Run

These items reduce wasted RunPod time, bad claims, and reruns.

1. Scope-gated DB/cache staging
   - Candidate-search must not wait for `nr`, `nt`, UniRef, InterProScan, or
     full plantiSMASH resources.
   - Required first-pass resources are curated/high-signal: SwissProt BLAST,
     SwissProt DIAMOND, UniProtKB/MMseqs where feasible, Pfam/HMMER, Pfam
     MMseqs, and the custom public MIA seed DB.
   - The first full campaign should be timeboxed and candidate-first. It should
     enable candidate-search resources plus high-ROI/small-to-medium
     full-context resources. Large medium-ROI and huge resources remain gated
     under later full-context, `optional_max`, or `deferred_review` lanes.
   - Use `db-bootstrap-plan.json` plus provider-side
     `genecluster_db_bootstrap.py` to create cache directories and verify or
     build only approved custom provider-side databases. Huge public DBs remain
     fail-closed until explicitly preloaded.
   - Required enabled DBs are all-or-fail for candidate search. A partial
     result set is not accepted as successful if a required search database is
     missing.

2. Provider-side metadata and query resolution
   - Resolve public query accessions and write query FASTA under the provider
     run inputs.
   - Record accession drift, exact resolved accessions, sequence checksums,
     and source citations before search starts.
   - Keep the local repo to ledgers and summaries only.
   - Treat unresolved high-confidence public seed proteins as execution
     blockers until they are resolved or explicitly marked context-only.
   - Keep unresolved medium-confidence comparator seeds as warnings so they do
     not block a first signal-generating run.
   - Use `query-resolution-plan.json` plus the provider runner's
     `--resolve-queries` flag for public protein accessions; never paste
     unpublished/private sequences into the repo.
   - Use `reference-import-plan.json` plus provider-side
     `genecluster_reference_import.py` to prefer existing public
     genome/protein/GFF resources before raw SRA import or assembly.
   - Heavy genome/protein/GFF downloads require explicit provider-side opt-in;
     default reference import writes a plan and blocker instead of fetching.

3. Cache/tool preflight
   - Verify write access, free space, DB presence, and tool versions before any
     biological run.
   - Fail before large fetches if the image, volume, or databases are not ready.

4. Candidate-first search
   - Run local/provider BLAST/DIAMOND/MMseqs/HMMER against staged DBs.
   - Export compact `candidate_hits.tsv`, `evidence.jsonl`,
     `claim-audit.jsonl`, `provenance.jsonl`, `versions.json`, and
     `licenses.tsv`.
   - Do not assemble transcriptomes until candidate search or metadata shows it
     is necessary.

5. Claim/audit gates
   - Transcriptome-only evidence supports candidate genes, not physical
     clusters.
   - Broad CYP/OMT/reductase hits support family-level hypotheses, not product
     chemistry.
   - Physical cluster claims require genome coordinates plus neighboring-gene
     evidence.

6. Resume-safe workflow layout
   - Keep Nextflow cache and work directories under `/workspace/genecluster`.
   - Always use `-resume` for workflow lanes.
   - Preserve both the task cache and work directory for reruns.

7. Decoy controls for broad families
   - Generate `decoy-plan.json` from the query ledger before search.
   - Broad CYP, OMT, reductase, GH1, transporter, and TF-like seeds must carry
     explicit negative-control/family-decoy expectations.
   - Decoy hits should lower confidence or trigger review; they should never
     become product-chemistry support by themselves.

8. Agent-queryable evidence summaries
   - Export compact TSV/JSONL plus `evidence.sqlite` so Symphony/Linear agents
     can query candidates, audit records, and evidence without reading raw
     BLAST output.
   - Keep database/raw search caches remote-only; sync only manifests and
     small structured summaries.
   - Include `candidate_anchors.tsv`, `cluster_neighborhoods.tsv`,
     `neighbor_annotations.tsv`, and `domain_labels.tsv` when coordinate
     evidence exists, so downstream agents can reason about anchors,
     methyltransferase-neighborhood hypotheses, paralogs, and claim gates.

9. Search-result cache
   - Cache raw search outputs on the provider by query FASTA hash, database id,
     database path, engine, and tool version placeholder.
   - This avoids repeating expensive homology searches while preserving enough
     provenance to invalidate stale cache entries later.

10. Run economics
   - Generate `run-economics.json` before launch.
   - Treat missing credentials, placeholder image, unresolved high-confidence
     seeds, missing search cache, and excessive low-ROI DB requirements as
     launch blockers or review warnings before paying for compute.

11. Anchor-first genome context
   - Map candidate IDs to GFF/GTF coordinates before running expensive BGC,
     synteny, or visualization lanes.
   - Extract a configurable wide neighborhood around anchors (`window_kb` and
     `window_genes`) and label neighbors with compact domain/product hints.
   - Treat wide-neighborhood hits as hypotheses until synteny, coexpression,
     phylogeny, or experimental evidence upgrades the claim.

## Medium-ROI Prep

Do after candidate-search is proven or when the full run is definitely viable.

- NCBI Datasets-based genome/protein/GFF import for chosen public assemblies.
- CDD/RPS-BLAST cross-checks for old spreadsheet-compatible domain reporting.
- MIBiG 4.0 protein DB for specialized-metabolism cluster comparison.
- plantiSMASH 2.0 only after genome/GFF viability is confirmed.
- JBrowse/clinker/pyGenomeViz dossier panels once coordinate evidence exists.
- Synteny/coexpression lanes only when there are enough reference genomes or
  samples to make the evidence meaningful.

## Low-ROI Or Burdensome Before First Signal

These remain useful later, but they should not block the first real run.

- Full `nr`, `nt`, UniRef, or all-of-TrEMBL staging before any candidate result.
- InterProScan full data cache before the candidate set is small enough to
  annotate cheaply.
- Whole-transcriptome de novo assembly as the first action when public
  protein/transcript/genome resources can be searched first.
- Plant BGC calling without a viable genome/GFF and anchor candidates.
- Cross-organism synteny and coexpression dashboards before candidate IDs are
  stable.
- Public webserver workflows for any private, unpublished, or collaborator
  restricted sequence.
- KEGG/BioCyc/BRENDA-derived bulk data unless licensing and redistribution
  terms are explicitly reviewed.

## Current Gate Mapping

Database ledgers use `run_gate`:

- `candidate_search`: required for first candidate-search and full runs.
- `full_public_mining` or campaign-specific full-context gates: required only
  once the full context lane is selected.
- campaign-specific timeboxed gates: used only when a private/example campaign
  defines a one-day profile and records the deferral policy.
- `optional_max`: maximum-tier assets that are useful but expensive.
- `deferred_review`: assets with heavier setup, licensing, or runtime burden.

`cache-preflight` and generated `search-plan.json` honor these gates. This is
intentional: the platform remains ambitious, but the first run should be fast
enough to learn something before paying for every maximum-tier resource.

## Sources To Recheck Before Live Run

- Selected provider storage and environment-variable docs.
- Nextflow stable cache/resume docs.
- NCBI Datasets CLI v2 docs for public genome/protein/GFF metadata.
- nf-core/fetchngs docs for SRA/ENA/GEO metadata and samplesheets.
- MMseqs2 latest user guide, including GPU search if a GPU image is selected.
- plantiSMASH 2.0 and MIBiG 4.0 release/version notes for full-context lanes.
