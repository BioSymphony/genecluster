# GeneCluster Genome-Context Campaign

Status: draft v0
Last reviewed: 2026-04-29

Use this campaign when an annotated genome or assembly/GFF can support physical genome-context analysis.

## Power Goal

Use this campaign to move from homolog candidates to genome-localized hypotheses: find homologs from sparse input clues, anchor them to assemblies/GFFs, capture neighboring genes, label proposed domain functions, deduplicate paralogs and isoforms, and visualize candidate neighborhoods without confusing context evidence for validated pathway chemistry.

## Claim Boundary

Allowed claims:

- genome-localized candidate genes
- local gene neighborhoods around anchors
- physical cluster hypotheses
- synteny-supported or lineage-expanded neighborhoods
- plant BGC caller support when rules/databases are recorded

Forbidden claims:

- product-level pathway completion without biochemical validation
- physical clusters from transcriptome-only evidence
- cluster boundaries without boundary evidence

Genome context can support "candidate neighborhood" or "physical cluster hypothesis" language when coordinates are reproducible. It does not validate enzyme activity, metabolite production, or final pathway completion.

## Input Handling

Required genome resources:

- assembly FASTA or public accession/version
- GFF/GTF and, when available, CDS/protein FASTA from the same annotation release
- source metadata, license, organism/tissue/cultivar notes, and checksum or accession provenance

Optional clue resources:

- raw or tidy query sequences, enzyme names, motifs, EC numbers, NCBI/BLAST exports, UniProt/InterPro/Pfam records, transcriptome candidates, and literature seed proteins

Before anchoring, normalize identifiers across GFF, protein FASTA, CDS FASTA, transcript FASTA, and BLAST tables. Record any identifier repair rules in provenance rather than silently editing IDs.

## Search and Anchoring Options

Select lanes by resource quality:

- BLASTP/DIAMOND from protein seeds to predicted proteins for annotated genomes
- TBLASTN from protein seeds to assembly scaffolds when annotation is incomplete
- BLASTN/TBLASTX from transcript candidates to genome/CDS resources
- HMMER/Pfam/InterProScan to label domains and remote family members
- reciprocal search or orthogroup checks to distinguish close orthologs from broad paralog families
- miniprot protein-to-genome anchoring when GFF/protein identifiers fail or annotation is fragmented

Search may run in a remote container or a configured local workdir outside this repo. Provider-local BLAST/DIAMOND/MMseqs/HMMER is the default; public webserver uploads and NCBI remote BLAST batch execution are not part of the v1 approved workflow. The dossier must record command provenance, database/accession versions, thresholds, and privacy decisions.

## Neighborhood Capture

For each anchor candidate, capture an explicit genome window:

- anchor gene ID, transcript/protein IDs, scaffold/contig, strand, start, end, and annotation source
- neighboring gene IDs, coordinates, strand, distance from anchor, orientation, and product/domain labels
- the exact window rule, for example `10 genes each side`, `100 kb each side`, or a boundary rule justified by synteny/expression/BGC caller support
- missing-neighbor notes for contig edges, annotation gaps, fragmented assemblies, or low-confidence gene models

Neighborhood tables should preserve raw annotation labels and proposed labels separately. Raw product names from GFFs are evidence inputs, not validated functions.

## Visualization and Labels

Produce a compact visualization for each priority locus:

- anchor and neighbor arrows with strand/orientation
- domain or pathway-role labels derived from Pfam/InterPro/HMMER/BLAST/curated literature
- evidence badges for `protein_hit`, `domain_hit`, `transcript_supported`, `neighborhood_supported`, `synteny_supported`, and `review_required`
- clear marking for transposons, repeat proteins, hypothetical proteins, fragmented genes, and boundary uncertainty

Use "proposed" labels unless direct validation exists. Separate `proposed_domain_function`, `annotation_source`, `validated_function`, and `claim_level` in exported tables.

## Paralogs, Isoforms, and Splice Variants

Genome-context ranking must not collapse biologically meaningful duplicates too early:

- group isoforms by gene model and mark the representative transcript/protein used for anchoring
- check splice variants for domain loss, active-site changes, frame issues, and tissue-specific transcript evidence when RNA-seq/Iso-Seq is available
- group likely paralogs/homeologs by sequence similarity, gene-tree/orthogroup evidence, synteny, and locus proximity
- keep tandem duplicates and local paralog expansions visible in neighborhood diagrams
- flag assembly duplicates, haplotigs, allelic copies, and pseudogenes separately from functional paralog hypotheses

`cluster_neighborhoods.tsv` should include `dedupe_group`, `representative_id`, `isoform_status`, `splice_variant_status`, `paralog_status`, and `locus_confidence`.

## Waves

1. Question contract and cluster definition
2. Genome/protein/GFF metadata freeze and identifier normalization
3. Clue normalization from raw sequence, accessions, BLAST/NCBI resources, and transcriptome candidates
4. Query/domain candidate search
5. Transcript/protein-to-genome anchoring
6. Isoform, splice-variant, paralog, and locus cleanup
7. Neighborhood extraction and anchor-centered tables
8. Neighborhood visualization and proposed domain-function labels
9. plantiSMASH / PlantClusterFinder / PhytoClust evidence lanes when available
10. Orthology and synteny review
11. Evidence ranking and cluster claim audit
12. Genome-context dossier export

## Required Dossier Artifacts

- `data-ledger.tsv`
- `query-ledger.tsv`
- `cluster_neighborhoods.tsv`
- `candidate-ranking.tsv`
- `orthology_links.tsv`
- `anchor_ladder.tsv`
- `reciprocal_hits.tsv`
- `domain-labels.tsv`
- `neighborhood_hypotheses.tsv`
- `pathway_completeness.tsv`
- `neighborhood-visualization.html` or equivalent compact SVG/HTML panels
- `evidence.jsonl`
- `provenance.jsonl`
- `claim-ledger.md`
- `dossier_index.json`

Every physical-cluster claim must cite genome coordinates and the exact command/database that produced them.

## Review Flags

Flag claims when:

- the candidate sits on a short contig, contig edge, haplotig, or suspect duplicate scaffold
- neighboring genes are inferred from inconsistent assembly and annotation releases
- cluster boundaries depend on arbitrary distance without synteny, coexpression, BGC caller, or functional-category support
- BLAST/domain labels are too broad to assign pathway role
- tandem duplicates cannot be resolved as paralogs, alleles, assembly duplicates, or pseudogenes
- splice variants change the domain model used to make the neighborhood claim
- product-level claims are being inferred from gene order rather than biochemical validation
