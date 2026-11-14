# InterProScan And Pfam

Use HMMER against a pinned Pfam-A library for Pfam signatures. Use InterProScan
when you need signatures from multiple member databases and their InterPro
mappings. Both take protein FASTA. Preserve the query IDs so you can join domain
calls to sequence-search results.

## Choose A Version

- For InterProScan 6, use the [6.0.3.0 Nextflow release](https://github.com/ebi-pf-team/interproscan6/releases/tag/6.0.3.0)
  with Nextflow 25.10.4 or later and a supported container runtime. Pin the
  workflow and the InterPro data release separately. See the
  [workflow options](https://interproscan6.readthedocs.io/stable/options/).
- To reproduce a v5 analysis, use its recorded application and database
  versions. [5.78-109.0](https://interproscan-docs.readthedocs.io/en/v5/ReleaseNotes.html)
  is the final v5 release and includes Pfam 38.2.
- For a standalone Pfam search, record the archive version and hash.
  [Pfam 39.0](https://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam39.0/)
  expands the signature library. Compare domain counts and accession coverage
  before combining results from different releases.

## Handoff To A Candidate Table

Record protein ID, signature accession, source database and release, residue
start and end, and the native score or E-value. Preserve proteins with zero
reported matches when joining results. Use [documented output formats](https://github.com/ebi-pf-team/interproscan6/blob/6.0.3.0/docs/output.md)
to review parser assumptions before switching to v6. A domain match supports
annotation at the signature's scope. Assign substrate or pathway evidence
separately.

For a local-only InterProScan 6 search, pass `--no-matches-api`.

For public accessions, use the [InterPro API](https://interpro-documentation.readthedocs.io/en/latest/api.html).
Record the InterPro release and annotate InterPro-N predictions separately
from member-database signatures. The [November resource paper](https://doi.org/10.1093/nar/gkag1114)
also describes accession lookup through the hosted InterPro MCP service.
