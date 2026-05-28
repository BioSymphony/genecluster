# GeneCluster Next-Experiment Design Campaign

Status: draft v0
Last reviewed: 2026-04-29

Use this campaign after public-data mining to design new RNA-seq, DNA-seq, metabolomics, or enzyme-validation experiments from evidence gaps.

## Power Goal

Use this campaign to convert a GeneCluster evidence dossier into the next experiment that can resolve uncertainty. It should start from the same user power goals as mining campaigns: a few clues, messy raw sequences, tidy NCBI/BLAST resources, candidate homologs, possible neighboring genes, proposed domain functions, paralog/isoform ambiguity, splice variants, and a claim ledger that separates hypotheses from validated claims.

## Inputs

- GeneCluster dossier
- accepted/rejected candidate list
- unresolved claim list
- available tissues, cultivars, treatments, and assay constraints
- `candidate_hits.tsv`, `cluster_neighborhoods.tsv`, `domain-labels.tsv`, `isoform-groups.tsv`, and `claim-ledger.md` when present
- raw clue ledger or notes describing messy pasted sequence, public accessions, NCBI/BLAST imports, and search modes already used

## Gap Triage

Classify each unresolved item before proposing new work:

- homolog discovery gap: too few seed clues, weak BLAST/profile support, missing related-taxon references, or no reciprocal/orthogroup check
- search-mode gap: public BLAST import needs rerun in a versioned local/remote workflow, or local/remote search lacked database/version provenance
- genome-context gap: candidate lacks coordinates, neighboring genes, boundary evidence, or assembly/GFF consistency
- domain-function gap: candidate has only product-description labels and needs Pfam/InterPro/HMMER/motif or active-site review
- dedupe gap: paralogs, homeologs, alleles, assembly duplicates, or isoforms are not resolved
- splice-variant gap: transcript variants disagree on ORF completeness, domain architecture, active-site residues, or expression support
- raw-data gap: messy sequences, private notes, or unlabelled files need normalization and privacy review before public tool use
- validation gap: hypothesis lacks biochemical, genetic, metabolomic, expression, or localization support

## Outputs

- sequencing scope with sample recommendations
- assay design and validation priorities
- candidate genes for cloning or expression
- metabolite standards and LC-MS/MS requirements
- vendor-ready scope and acceptance criteria
- updated claim ladder distinguishing `hypothesis`, `evidence_supported`, `validated_elsewhere`, and `validated_in_target`
- recommended search reruns, neighborhood visualizations, domain-label audits, and dedupe/splice checks before wet-lab spend

## Review Rules

- Do not recommend new sequencing until public data gaps are explicit.
- Separate candidate-discovery experiments from biochemical validation experiments.
- Flag controlled/private sequence or material handling requirements before any vendor-facing output.
- Do not treat a top BLAST hit, gene neighborhood, expression correlation, or domain label as biochemical validation.
- Prefer a cheap in silico cleanup wave before new assays when candidate ranking is blocked by paralogs, isoforms, splice variants, or missing database provenance.
- Keep private sequences out of public BLAST or public design tools unless the user explicitly clears the privacy status.

## Experiment Design Patterns

Use the smallest experiment that resolves the claim blocker:

- if homolog search is weak, design a remote/local BLAST, DIAMOND, MMseqs2, HMMER, reciprocal-hit, or orthogroup rerun with accession/versioned databases
- if genome neighborhoods are missing, design long-read genome sequencing, Hi-C scaffolding, targeted assembly polishing, GFF repair, or capture of anchor-centered neighboring genes
- if proposed domain functions are weak, design domain/motif review, protein modeling, active-site comparison, or targeted mutagenesis only after the sequence model is stable
- if paralogs or isoforms are unresolved, design Iso-Seq, targeted RT-PCR, variant-aware expression analysis, or locus-specific PCR before cloning
- if splice variants are central, design tissue/treatment-specific RNA-seq or RT-PCR that can distinguish ORF-complete and domain-disrupting isoforms
- if pathway product claims are unresolved, design enzyme-expression assays, substrate panels, metabolomics, coexpression perturbation, or isotope-feeding experiments
- if public-data provenance is weak, rerun tidy NCBI/BLAST imports through a versioned workflow before wet-lab follow-up

## Vendor-Ready Scope Requirements

Vendor-facing outputs should include:

- exact sample material, tissue, treatment, cultivar, replicate count, and privacy/material-handling notes
- target loci/transcripts/proteins with representative IDs and dedupe group IDs
- neighboring genes or coordinates when assays depend on genome context
- sequence artifacts to use, stored outside this repo when large or private
- acceptance criteria tied to claim movement, for example "resolve splice variant used for candidate C17OMT hypothesis" rather than "generate RNA-seq"
- decision rules for promoting, rejecting, or keeping each candidate as a hypothesis

## Claim Movement

Each proposed experiment should state the highest claim level it can support:

- BLAST/profile reruns can support `hypothesis` or `evidence_supported`
- neighborhood visualization and synteny can support a physical-cluster hypothesis, not product validation
- RNA-seq/Iso-Seq can support transcript presence, splice form, and expression evidence
- LC-MS/MS, enzyme assays, genetics, or isotope feeding are required for target-organism validation

Do not design an expensive validation experiment until the candidate sequence, isoform, and paralog identity are specific enough to make the result interpretable.
