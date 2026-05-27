# GeneCluster Provider Data Materialization

Status: public-skill rulebook
Last reviewed: 2026-04-30

GeneCluster should be remote-heavy and local-light. Large public genomes,
SRA/ENA reads, FASTQ, BAM, indexes, assemblies, and database caches belong in
the selected provider workdir or cache volume. The local repo should receive
only compact review artifacts unless the operator explicitly requests more.

RunPod is the blessed internal provider today, but these rules apply to
`runpod_pod`, `local_full`, `ssh_hpc`, and `cloud_vm`.

## Default Policy

- Do not download raw biological data into the repo.
- Do not commit raw FASTQ, BAM/CRAM/SAM, genome FASTA, large assemblies, BLAST
  DBs, HMM indexes, or provider caches.
- Provider-side large downloads require explicit permission such as
  `--allow-provider-large-downloads` or `--allow-large-downloads`.
- Provider paths must be outside the repo, for example:
  `/workspace/genecluster/runs/<run_id>` on RunPod.
- Local pullback defaults to summaries, ledgers, small tables, reports,
  provenance, and claim audit.

## Materialization Sequence

For public SRA/genome inputs, the provider stage should follow this order:

1. Resolve user-supplied accessions.
   - BioProject, SRS/SRX/ERX/DRX, or run IDs are all acceptable intake values.
   - Resolve them to concrete SRR/ERR/DRR run accessions before conversion.
   - Write `resolved-accessions.tsv`.
   - Skill helper:
     `python3 skills/biosymphony/scripts/genecluster_sra_runinfo.py --data-ledger <campaign-dir>/data-ledger.tsv --out-dir .runtime/<bundle>/sra-runinfo`

2. Resolve read layout.
   - Record `LibraryLayout`, platform, read length when available, spots, bases,
     and expected file naming.
   - Write `sra-layout.tsv`.
   - Branch downstream commands from this ledger:
     - `SINGLE`: use single-read aligner flags such as HISAT2 `-U`.
     - `PAIRED`: require both mate files and use paired flags such as `-1/-2`.
     - mixed/unclear: stop or enter an explicitly labeled degraded branch.

3. Fetch provider-side sequence data.
   - Use `datasets download genome accession <GCA/GCF> --include ...` for
     public genome packages.
   - Use `prefetch` for SRA staging.
   - Use `fasterq-dump` on the discovered run accession directory or `.sra`
     artifact, not on a guessed SRX/SRS/BioProject path.
   - Write command logs and `download-manifest.tsv`.

4. Validate materialized files.
   - Non-empty genome/protein/GFF/FASTQ files.
   - Expected mate count for the recorded layout.
   - Checksums or size/status when available.
   - Write `materialized-targets.tsv`.

5. Build target artifacts under provider storage.
   - Transcript/protein/genome FASTA, ORFs, BLAST/DIAMOND/MMseqs indexes,
     splice-aware coordinate maps, or other run-specific indexes.
   - Write `target-db-indexes.tsv` and `target-db-build-summary.json`.

6. Search only after target materialization validates.
   - Candidate search cannot silently fall back to SwissProt/reference-only
     hits if target materialization failed.
   - `candidate-search-summary.json` must distinguish target-organism searches
     from reference/control searches.

7. Validate declared stage outputs.
   - A done marker is not enough. The primary expected outputs from the stage
     contract must exist and be non-empty before downstream workers consume
     them.
   - Skill helper:
     `python3 skills/biosymphony/scripts/genecluster_stage_contract.py --stage-contract .runtime/<bundle>/stage-contract.json --artifact-root .runtime/<bundle>-summary --check-expected-outputs`

## Local Pullback Boundary

Default small artifacts:

- `run_summary.json`
- `stage-progress.jsonl`
- `resolved-accessions.tsv`
- `sra-layout.tsv`
- `materialized-targets.tsv`
- `target-db-indexes.tsv`
- `candidate_hits.tsv`
- top hits per query
- anchor/neighborhood summaries
- claim audit
- provenance and versions
- HTML/Markdown/Excel/CSV reports

Optional local review artifacts for private runs:

- compact predicted proteome FASTA
- compact GFF/GTF needed for review
- small query FASTA

Never pull by default:

- raw FASTQ
- raw SRA cache
- BAM/CRAM/SAM
- HISAT2/STAR/minimap2 indexes
- BLAST/DIAMOND/MMseqs DBs
- Pfam/HMMER pressed DBs
- Nextflow work dirs
- provider scratch/cache dirs

## Why This Is Practical

The first full GeneCluster provider run showed that public raw data acquisition
was straightforward once the wrapper assumptions were corrected:

- NCBI Datasets genome fetch completed quickly.
- `prefetch` plus `fasterq-dump` handled public SRA reads reliably after SRX to
  SRR resolution.
- The provider volume preserved completed stages across failed pod attempts.
- Local review stayed small: compact tables, reports, proteome, and transcript
  annotations were tens of MB, not hundreds of GB.

The expensive failures were not NCBI downloads. They were preventable contract
bugs:

- passing an SRX path to `fasterq-dump` after `prefetch` created an SRR folder
- assuming paired-end reads when run metadata said single-end
- missing helper tools in the container
- treating warning-only tool checks as acceptable
- running unbounded context annotation without a fanout gate

## Acceptance Criteria

A provider-side data materialization stage is acceptable only when:

- `resolved-accessions.tsv` maps every broad accession to concrete run IDs or
  records a blocker.
- `sra-layout.tsv` records layout and downstream branch.
- `download-manifest.tsv` or equivalent records commands, provider paths, and
  sizes/status.
- `materialized-targets.tsv` records non-empty provider-side targets.
- Stage done markers are written only after validation.
- The local pullback excludes raw/heavy artifacts unless the operator explicitly
  requested them outside the repo.
- The final summary separates:
  - data fetched
  - target materialized
  - target indexed
  - target searched
  - context lanes completed/deferred

## Common Closeout Language

Use precise wording:

- "Provider data materialization succeeded; raw files remain on provider
  volume."
- "Target-organism search succeeded; local pullback contains summary artifacts
  only."
- "Context lane deferred by budget; target candidate evidence remains valid at
  candidate-search maturity."

Avoid vague wording:

- "Downloaded locally"
- "Pipeline succeeded" when only data fetch or only candidate search succeeded
- "Cluster found" without coordinate/neighborhood evidence
- "No large files" if compact derived FASTA/GTF were pulled back; instead say
  "no raw/heavy provider artifacts were pulled back"
