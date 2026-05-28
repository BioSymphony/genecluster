# GeneCluster Cross-Species Discovery Engine

Status: implemented contract v1
Last reviewed: 2026-04-30

## Core Pattern

GeneCluster’s default discovery shape is:

`canonical genes/proteins from species A` -> `search species B datasets` -> `reciprocal/orthology scoring` -> `genome anchoring` -> `neighborhood capture` -> `pathway completeness + reviewable evidence package`.

This is intentionally broader than any one demo. It supports missing-gene searches, paralog-heavy families, transcriptome-only organisms, fragmented genomes, multi-target comparisons, BGC-like neighborhoods, non-plant metabolism, and private/provider-local datasets.

## Required Ledgers And Plans

Launch bundles carry these cross-species contracts:

- `target-db-plan.json`: target species resources and provider-only index targets
- `orthology-anchor-plan.json`: A-to-B search directions and anchor confidence ladder
- `reciprocal-search-plan.json`: forward and reverse search policy
- `pathway-completeness-plan.json`: per-step evidence matrix policy
- `campaign-prompt.md`: durable handoff prompt for a Codex/Symphony execution worker

Raw SRA rows are not treated as indexable FASTA resources. They are marked `target_raw_sequence_source` with `provider_materialization_required`; only materialized transcript/protein/genome/GFF resources receive BLAST/DIAMOND/MMseqs/miniprot index targets.

## Search Directions

Every candidate record should preserve:

- `canonical_A_to_target_B`
- `target_B_to_canonical_A`
- `domain_to_target_B`
- `target_B_to_reference_db`

The candidate table records `source_species`, `target_species`, `target_db_id`, `search_direction`, `reciprocal_rank`, `reciprocal_best_hit`, `anchor_method`, `anchor_confidence`, and `coordinate_confidence`.

## Anchor Confidence Ladder

Use the strongest available anchor:

- `exact_gff_id`
- `reciprocal_best_hit`
- `transcript_to_genome`
- `protein_to_genome`
- `domain_only`
- `unanchored`

`miniprot` is the default provider-side fallback for protein-to-genome anchoring when GFF/protein identifiers fail. Domain-only and unanchored rows must remain claim-limited.

## Claim Rules

- Transcript-only evidence cannot prove a physical cluster.
- Broad CYP/OMT/reductase/domain-family hits cannot prove product chemistry.
- Cluster claims require coordinates and neighborhood evidence.
- 24-hour runs must finish a complete dossier with `deferred_by_budget` rows instead of silently omitting slow lanes.

## Summary Outputs

Provider workers should return only small outputs:

- `target-db-build-summary.json`
- `target-db-ledger.resolved.tsv`
- `target-db-indexes.tsv`
- `candidate_hits.tsv`
- `orthology_links.tsv`
- `anchor_ladder.tsv`
- `reciprocal_hits.tsv`
- `candidate_anchors.tsv`
- `cluster_neighborhoods.tsv`
- `neighbor_annotations.tsv`
- `domain_labels.tsv`
- `neighborhood_hypotheses.tsv`
- `pathway_completeness.tsv`
- `claim-audit.jsonl`
- `evidence.jsonl`
- `provenance.jsonl`
- `versions.json`
- `dossier-manifest.json`

Large sequence files, raw search outputs, indexes, caches, assemblies, and workflow directories stay provider-side.
