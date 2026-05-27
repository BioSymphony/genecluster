# Capability Stack

BioSymphony GeneCluster is the control plane that lets your agent find biosynthetic gene clusters and assemble pathway evidence across genomes and transcriptomes. It decides which evidence route is defensible, prepares run contracts, validates outputs, and turns tool results into a reviewable evidence package. The same artifact contracts work whether a solo agent is running on a laptop or a multi-agent Linear DAG is fanning out across cloud GPUs.

## Campaign Brain

- `genecluster_campaign_preflight.py` ranks data readiness, relevance, novelty, and seed-query maturity.
- `genecluster_species_scout.py` searches for plausible comparator species across NCBI, SRA, NGDC/GWH, KEGG hints, and local catalog memory.
- `genecluster_source_scout.py` turns source availability into route-readable ledgers.
- `genecluster_annotation_scout.py` chooses annotation-direct, transcript-first, genome-context, synteny, transcriptome-only, rescue, or next-experiment-design routes.
- `genecluster_preflight.py` validates manifests, ledgers, launch bundles, route claims, and generated artifacts.

## Evidence Lanes

- Candidate search: BLAST-style anchors, MMseqs2 iterative search, Foldseek/ProstT5 structural similarity.
- Genome context: GFF/proteome parsing, neighborhood extraction, Pfam and SwissProt annotation, coordinate-aware cluster windows.
- BGC callers: plantiSMASH, antiSMASH, DeepBGC, MIBiG cross-reference, and cblaster/clinker re-entry recipes.
- Comparative genomics: JCVI MCScan, synteny/dotplot outputs, OrthoFinder/GENESPACE-style normalized contracts.
- Enzyme/function: P450Rdb, KEGG/KAAS, EnzymeMap, DiffPaSS, DeepEC/ECPred, HIT-EC/CLEAN re-entry paths.
- Reporting: Quarto books, Cytoscape.js pathway viewers, igv-reports, pyGenomeTracks, workbook postprocessing.

## Execution Lanes

- Local contracts for cheap validation and dry runs.
- Docker build contexts for GeneCluster runner images.
- Cloud-portable dispatch templates for RunPod, AWS, GCP, Vast.ai, and Lambda Labs.
- Provider handoff manifests that keep heavy compute outside source control while preserving versions, hashes, and expected outputs.

## Atlas Outputs

A mature run should produce:

- `source-ledger.tsv`
- `query-resolution-ledger.tsv`
- `route-decision.json`
- `cluster_calls.tsv`
- `bgc_consensus.tsv`
- `protein_function_votes.tsv`
- `protein_function_jury.tsv`
- `comparative_atlas/`
- `review_surface_manifest.json`
- `claim-ledger.tsv`
- Quarto HTML/PDF review surfaces

## Tooling Inventory

The current inventory is in [biosymphony-tooling-status.md](biosymphony-tooling-status.md): 25 validated tools, 3 parked tools with re-entry recipes, 8 shelved-but-testable tools, and 2 gated tools with alternatives.

Use [skills/genecluster-superpowers/SKILL.md](../skills/genecluster-superpowers/SKILL.md) when extending the atlas with a new tool so the work starts from the existing validation record instead of re-running discovery.
