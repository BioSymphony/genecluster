# BioSymphony GeneCluster Public Mining

Status: draft v0
Last reviewed: 2026-04-29

BioSymphony GeneCluster turns a pathway, metabolite, enzyme family, or query set into a provider-neutral evidence dossier for candidate genes and genome neighborhoods. A campaign may be local-lite, local-full, RunPod, SSH/HPC, or cloud-VM backed. Heavy data stays outside the repo unless a user explicitly opts into a configured heavy workdir.

## Power Goal

Use this campaign when the user has only a few useful clues and wants a scientific lab crew to expand them into a defensible candidate map. Valid clue types include:

- one or more enzyme names, EC numbers, pathway steps, metabolites, domains, motifs, accessions, papers, raw pasted sequences, primer-derived fragments, or BLAST hits
- tidy public resources such as NCBI Gene/Protein/Nucleotide, SRA, TSA, WGS, RefSeq, GenBank, BLAST result pages, UniProt, InterPro/Pfam, or published supplemental FASTA/GFF tables
- messy resources such as mixed DNA/protein snippets, wrapped FASTA copied from papers, ambiguous base calls, partial ORFs, translated fragments, local lab notes, and unlabelled sequence files

The output is a candidate and context dossier that distinguishes homolog discovery, paralog/isoform cleanup, domain-function labeling, neighboring-gene evidence, and unvalidated pathway hypotheses.

## Campaign Template

Use a campaign-specific id:

`genecluster-<organism-or-project>-<pathway-or-goal>-v0`

Scientific target examples:

- candidate discovery for a pathway interval from step A to step Z
- missing enzyme search from sparse source-species canonical proteins
- domain-family survey with paralog and splice/isoform review
- transcriptome-only candidate dossier
- genome-anchored neighborhood capture around candidate anchors

Primary inputs should be recorded in `data-ledger.tsv` and `query-ledger.tsv`:

- target organism transcriptome/proteome/genome/GFF resources, accessions, or local heavy-workdir pointers
- source-species canonical protein accessions, public query FASTA, domains, motifs, or literature seeds
- optional outgroups or negative-control species for subtractive review
- approved databases/tools and their license/use modes

## Hard Execution Rules

- No raw FASTQ, SRA, BAM/CRAM/SAM, genome assemblies, BLAST databases, or large intermediate files are downloaded into this repo.
- Heavy sequence work runs in the selected provider or configured heavy workdir.
- RunPod is a well-supported provider path, but it is not required for public skill use.
- Public webservers are disabled unless the campaign manifest explicitly opts into them and the privacy/terms posture is reviewed.
- Local artifacts are limited to manifests, ledgers, validation summaries, small tables, compact HTML reports, and remote artifact pointers.

For other GeneCluster public-mining campaigns, record the selected search mode in provenance:

- `remote_container_blast`: BLAST+, DIAMOND, MMseqs2, HMMER, or ORF tools run in a controlled remote worker against downloaded public databases or campaign-specific FASTA files
- `local_lite_blast`: small FASTA checks, sequence normalization, and limited BLAST against existing local databases outside this repo
- `ncbi_remote_blast`: NCBI web/API BLAST for small public queries when rate limits, privacy, and terms are acceptable
- `manual_tidy_import`: curated import of NCBI/BLAST/UniProt/InterPro tables where full re-search is unnecessary

Never send private sequences or unpublished constructs to public web tools. When a query is messy or possibly private, normalize it locally or in the remote worker first and mark the privacy status before any remote public search.

## Execution Contract

Provider-neutral fields:

```json
{
  "execution": {
    "mode": "remote",
    "provider_class": "runpod_pod",
    "large_local_downloads": false,
    "remote_workdir": "/workspace/genecluster/runs/<run_id>",
    "remote_volume_mount": "/workspace",
    "artifact_policy": "summaries_only",
    "web_tool_policy": "container-only",
    "future_provider_classes": [
      "local_lite",
      "local_full",
      "ssh_hpc",
      "cloud_vm",
      "managed_workflow"
    ]
  }
}
```

Provider classes:

- `local_lite`: metadata, manifest validation, small FASTA checks, dossier rendering only
- `local_full`: explicit opt-in heavy local workdir outside the repo
- `runpod_pod`: supported heavy provider path using a mounted Network Volume
- `ssh_hpc`: external lab cluster or university server
- `cloud_vm`: generic cloud VM with attached storage
- `managed_workflow`: future managed workflow backend

Run scopes:

- `smoke`: metadata/query resolution and validation only
- `candidate_search`: remote or configured-workdir candidate search and small dossier
- `genome_context`: review candidate coordinates, genome/GFF suitability, and anchor-centered neighborhood summaries
- `coexpression`: add expression and coexpression evidence for candidate prioritization without making physical-cluster claims
- `synteny`: add orthology and conserved-neighborhood evidence for reviewed genome-localized candidates
- `full_public_mining`: candidate search plus genome context, coexpression, synteny, and public-data claim audit
- `next_experiment_design`: convert reviewed public-data gaps into sequencing, metabolomics, and biochemical-validation options
- campaign-specific aliases may exist in private or example campaigns, but public workflows should use the generic scopes above.

The dry-run issue generator supports all of these planning scopes:

```bash
python3 skills/biosymphony/scripts/genecluster_issue_dry_run.py \
  --campaign <campaign-dir>/campaign-manifest.json \
  --run-scope full_public_mining \
  --out dry-run/genecluster-full-public-mining
```

Provider-neutral scope rules:

- `smoke` and `candidate_search` create concrete launch-bundle review issues for most campaigns.
- `genome_context`, `coexpression`, `synteny`, `full_public_mining`, and `next_experiment_design` are planning/review scopes unless a provider adapter produces the requested small artifacts.
- Scope-specific issues must still include Agent Role, Artifact Contract, Review Gate, Handoff Notes, Claim Boundary, and exact Validation Commands.
- A provider class can be `local_lite`, `local_full`, `runpod_pod`, `ssh_hpc`, `cloud_vm`, or `managed_workflow`; generated issues should preserve provider-specific gaps as review notes rather than hard-coding secrets or account details.

## Clue Intake and Normalization

Every campaign starts with a `clue-ledger` section in the manifest or notes. For each clue, record source, privacy status, molecule type, organism, expected enzyme/pathway role, and whether it is raw, curated, or inferred.

Normalize inputs before search:

- split mixed pasted content into individual records with stable `query_id` values
- detect nucleotide versus protein sequence and keep the original raw text as an external artifact pointer when needed
- translate nucleotide fragments in all plausible frames when ORFs are partial or strand is unknown
- trim adapters/vector/low-complexity regions only when the command and thresholds are recorded
- map NCBI/BLAST identifiers to current accession/version pairs
- preserve aliases from papers, enzyme names, and BLAST descriptions without treating them as validated function

When only a few clues are available, expand seeds in this order: known characterized enzymes, close orthologs from related taxa, HMM/domain models, curated pathway-family proteins, then broad family searches with stricter review flags.

## Evidence Classes

Every candidate hit should be assigned one or more evidence classes:

- `transcript_hit`
- `protein_hit`
- `domain_hit`
- `genome_localized`
- `neighborhood_supported`
- `coexpression_supported`
- `review_required`

Physical gene-cluster claims require genome coordinates. Transcriptome-only evidence can nominate candidate genes, but cannot prove clustering.

## Homolog Search and Cleanup

Required search lanes should be selected by the data available:

- protein queries against predicted proteins with BLASTP/DIAMOND for close homologs
- nucleotide or transcript queries with BLASTN/TBLASTN for raw assemblies, TSA, contigs, or genome scaffolds
- translated nucleotide searches with BLASTX/TBLASTN when molecule type is uncertain
- profile searches with HMMER/Pfam/InterProScan for remote homologs and domain-family membership
- reciprocal best-hit or orthogroup checks for candidate orthology when reference proteomes exist

Deduplicate before ranking:

- collapse exact duplicate sequences and redundant accessions
- group isoforms by transcript/gene model when GFF or transcript metadata exists
- group likely paralogs, homeologs, alleles, and assembly duplicates by sequence identity, coverage, genomic locus, and expression/sample support
- retain distinct paralogs when they differ by domain architecture, active-site residues, genome neighborhood, expression pattern, or literature support
- flag splice variants and partial transcripts separately from full-length protein-coding candidates

Candidate rows should include `dedupe_group`, `representative_id`, `isoform_status`, `splice_variant_status`, `paralog_status`, `partial_status`, and a short `dedupe_rationale`.

## Genome Neighborhoods and Domain Labels

When genome or GFF resources exist, capture neighboring genes around each anchor candidate rather than only the hit gene:

- record scaffold/contig, strand, coordinates, neighboring gene IDs, distances, orientation, and annotation source
- default to an anchor-centered window and record the exact window rule, for example `10 genes each side` or `100 kb each side`
- label neighbors by proposed domain/function using InterPro/Pfam/HMMER/BLAST evidence, not just product names copied from annotations
- distinguish biosynthetic enzyme candidates, transporters, regulators, tailoring enzymes, housekeeping genes, transposons, and low-confidence hypothetical proteins
- generate a compact neighborhood visualization table or SVG/HTML panel with anchors, neighbors, orientation arrows, domain labels, and evidence badges

Neighbor labels are proposed functions until supported by curated annotation or experiment. The dossier must separate `proposed_domain_function`, `annotation_source`, and `validated_function`.

## Required Ledgers

`data-ledger.tsv` must include:

- `dataset_id`
- `accession`
- `run_id`
- `data_role`
- `sample_type`
- `organism`
- `bioproject`
- `technology`
- `expected_size`
- `source_url`
- `remote_path`
- `checksum_status`

`query-ledger.tsv` must include:

- `query_id`
- `query_name`
- `source_organism`
- `sequence_source`
- `enzyme_class`
- `pathway_role`
- `confidence`
- `citation`

`resource-ledger.tsv` must include:

- `resource`
- `resource_type`
- `version`
- `license_class`
- `use_mode`
- `citation`

## Query Seed Strategy

Build seed sets from the pathway and question, not from a hard-coded organism.
Good public seeds usually come from:

- characterized enzymes for the exact pathway step
- close orthologs from related taxa
- branch-point enzymes that distinguish competing pathway routes
- HMM/domain models for remote homolog discovery
- transporters and regulators only as context unless the project specifically
  asks for transport or regulation
- negative-control or outgroup proteins for broad enzyme families

For monoterpene indole alkaloid campaigns, a reusable seed library might include
strictosidine-entry enzymes, branch-point reductases, CYP hydroxylase families,
aromatic methyltransferases, MATE/ABC/NPF transporters, and jasmonate/MIA
transcription-factor context. Treat this as an example library, not the public
default. If a native enzyme for a specific step is unresolved in the target
organism, record that caveat in `pathway-steps.tsv` and keep product-completion
claims review-gated.

## Candidate Search Milestone

The first readiness milestone is complete when:

- the campaign manifest passes GeneCluster preflight
- public accession metadata is represented in `data-ledger.tsv`
- public/literature query seeds are represented in `query-ledger.tsv`
- resources and licenses are represented in `resource-ledger.tsv`
- a remote candidate-search run can write small summaries only
- the dossier contains `candidate_hits.tsv`, `evidence.jsonl`, `provenance.jsonl`, `licenses.tsv`, `versions.json`, and `export.xlsx`
- candidate records separate candidate genes, genome-localized candidates, and cluster/neighborhood-supported candidates
- the dossier records search mode, BLAST/profile-search commands or imported result provenance, and database versions
- homologs are deduplicated into representative candidates with paralog/isoform/splice-variant flags
- candidate domains and active-site/motif notes are summarized without converting them into validated functions
- available genome neighborhoods are captured with neighboring genes, proposed labels, and exact coordinate/window rules
- `claim-ledger.md` separates hypotheses, evidence-supported claims, rejected candidates, and experimentally validated claims

## Review Flags

Flag candidates for review when:

- the hit is a broad CYP/OMT/reductase family member with weak pathway specificity
- transcript evidence is incomplete or likely chimeric
- the apparent hit may be a paralog, allele, or tetraploid homeolog
- genome coordinates are unavailable
- a physical cluster claim is inferred from transcript-only data
- product-level chemistry would require LC-MS/MS or functional assay confirmation
- BLAST descriptions imply a function that is not supported by domain architecture, active-site residues, orthology, or literature
- a candidate is only one splice isoform among conflicting transcript models
- a high-scoring hit is probably an annotation-propagation artifact, pseudogene, contaminant, or assembly duplicate
- a public result was imported from a BLAST/NCBI table without rerunning against a versioned database

## Claim Ledger Rules

Use four claim levels:

- `hypothesis`: plausible candidate or neighborhood inferred from sequence/context evidence
- `evidence_supported`: supported by reproducible search, domain, orthology, expression, or genome-neighborhood evidence
- `validated_elsewhere`: function validated in another organism or accession, with citation and transfer caveat
- `validated_in_target`: direct biochemical, genetic, metabolomic, or expression validation in the target organism/material

Do not write "encodes", "produces", "catalyzes", or "cluster for" unless the claim level supports that wording. Prefer "candidate", "putative", "homolog", "domain-supported", "neighborhood-supported", or "hypothesized" for unvalidated records.
