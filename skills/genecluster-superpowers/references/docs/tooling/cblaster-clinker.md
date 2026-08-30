# cblaster and clinker

**Status:** available upstream; public end-to-end wrapper fixture planned.

cblaster searches for co-located homologs by remote NCBI search or local DIAMOND search. clinker compares GenBank cluster records and produces an interactive HTML plot.

Current public releases reviewed on 2026-08-30 are cblaster 1.4.2 and clinker 0.0.32.

## Install

```bash
python3 -m pip install "cblaster>=1.4.0" "clinker>=0.0.32"
cblaster --version
clinker --version
```

These are minimum versions, not exact pins.

## Minimal pattern

```bash
cblaster search \
  --query_file <QUERY_FASTA> \
  --mode remote \
  --output <OUTPUT_DIR>/clusters.csv \
  --plot <OUTPUT_DIR>/clusters.html

clinker <CLUSTER_GENBANK_FILES> --plot <OUTPUT_DIR>/clinker.html
```

The current clinker CLI does not document `--output_html` or `--output_svg`. Export a static image through a separately documented browser or rendering step when needed.

## Output contract

Keep the query ledger, search mode, database and access date, cblaster and clinker versions, GenBank inputs, tabular results, HTML plot, and hashes. Local search requires prepared genome records; remote search depends on the current upstream service and database behavior.

Sources: [cblaster documentation](https://cblaster.readthedocs.io/), [cblaster on PyPI](https://pypi.org/project/cblaster/), and [clinker](https://github.com/gamcil/clinker).
