# GeneCluster Transcriptome-Only Campaign

Status: draft v0
Last reviewed: 2026-04-29

Use this campaign when transcriptomes exist but no suitable genome/GFF exists for physical cluster calls.

## Power Goal

Use this campaign to turn a few pathway clues, raw sequences, NCBI/TSA records, public BLAST hits, or transcriptome assemblies into a deduplicated list of candidate transcripts and predicted proteins. It is optimized for homolog discovery, splice/isoform review, expression support, and proposed domain-function labeling when genome neighborhoods are unavailable.

## Claim Boundary

Allowed claims:

- candidate transcript/protein families
- expression-supported pathway modules
- isoform and tissue/sample support
- domain/pathway/orthology evidence

Forbidden claims:

- physical gene clusters
- genomic neighborhood support
- synteny support

Transcriptome-only dossiers may say "candidate homolog", "domain-supported transcript", or "expression-supported pathway member". They must not say a candidate is physically clustered or that a transcript has a validated biochemical function unless that validation comes from an explicit experiment or citation.

## Input Handling

Accept both tidy and messy inputs:

- tidy resources: NCBI TSA/EST/SRA metadata, public transcript FASTA, protein FASTA, BLAST result exports, UniProt/InterPro/Pfam records, and published supplemental tables
- messy resources: raw pasted DNA/protein sequence, mixed FASTA/non-FASTA text, ambiguous bases, partial ORFs, redundant isoform files, and fragmentary BLAST descriptions

Before search:

- assign every clue a stable `query_id`
- detect nucleotide versus protein sequence and translate uncertain nucleotide fragments in plausible frames
- retain the original clue text as provenance, but search only normalized FASTA or curated accession/version identifiers
- mark private, unpublished, or uncertain-origin sequences so they are not sent to public web BLAST

## Search Options

Select and record one or more reproducible search lanes:

- local or remote BLASTP/DIAMOND against predicted transcriptome proteins
- TBLASTN/BLASTN against transcript contigs when ORFs are not available
- BLASTX for nucleotide fragments of unknown frame
- HMMER/Pfam/InterProScan for domain-family searches and remote homologs
- manual import of small NCBI/BLAST tables when the table is treated as evidence input rather than a rerun search

For public NCBI remote BLAST, record query accessions, program, database, date, filters, max targets, and job/result identifiers. For local or remote-container BLAST, record command, database path or accession snapshot, database date, e-value, identity, coverage, and filtering thresholds.

## Isoform, Splice Variant, and Paralog Cleanup

Deduplicate before ranking:

- collapse exact duplicate transcript/protein sequences
- group transcript isoforms by assembler gene ID, ORF overlap, reciprocal best hits, or annotation metadata
- flag likely splice variants when exon structure, ORF length, domain architecture, UTR differences, or transcript IDs support an isoform relationship
- flag likely paralogs/homeologs when sequences are similar but biologically distinct candidates remain plausible
- retain multiple representatives when they differ in catalytic residues, domain architecture, expression pattern, tissue support, or literature-linked pathway role

`candidate_hits.tsv` should include `dedupe_group`, `representative_id`, `isoform_status`, `splice_variant_status`, `paralog_status`, `orf_status`, and `dedupe_rationale`.

## Domain and Function Labels

Every candidate should have a proposed label derived from evidence rather than copied blindly from the top BLAST description:

- `proposed_domain_function`: concise family or domain-level role
- `domain_evidence`: Pfam/InterPro/HMMER/BLAST evidence used for the label
- `active_site_or_motif_notes`: conserved residues, motif presence/absence, or reason not checked
- `validated_function`: only filled when direct target-organism validation or cited validation in another organism exists

Visual outputs should be compact transcript/protein schematics or tables showing ORF length, domain boxes, motif notes, isoform grouping, and evidence badges. They should not include genome-neighborhood arrows unless genome coordinates are later added by a separate genome-context campaign.

## Waves

1. Question contract and query seed ledger
2. Public/private data ledger and license review
3. Clue normalization from raw sequence, accessions, and BLAST/NCBI resources
4. Remote transcriptome import or assembly
5. ORF prediction and protein/domain annotation
6. Local/remote BLAST, translated search, and profile-search lanes
7. Isoform, splice-variant, paralog, and duplicate cleanup
8. Expression and coexpression evidence
9. Evidence ranking, domain-function labels, and reviewer caveats
10. Transcriptome-only dossier export

## Required Dossier Artifacts

- `data-ledger.tsv`
- `query-ledger.tsv`
- `candidate_hits.tsv`
- `candidate-ranking.tsv`
- `evidence.jsonl`
- `provenance.jsonl`
- `isoform-groups.tsv`
- `domain-labels.tsv`
- `claim-ledger.md`

Every candidate must include a caveat that transcriptome-only evidence cannot establish physical clustering.

## Review Flags

Flag candidates when:

- the transcript is partial, chimeric, low coverage, or assembled from a single sample
- a top hit is a broad enzyme family member rather than a close pathway ortholog
- splice variants conflict on catalytic domains or active-site motifs
- paralogs cannot be separated cleanly from alleles/homeologs
- expression support is absent, tissue-mismatched, or driven by one outlier sample
- an imported BLAST/NCBI description implies a function not supported by domain architecture or curated literature
