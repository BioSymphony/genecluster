# cblaster and clinker

**Status:** wrapper contract tested with fake CLIs; no biological validation or live search is claimed.

cblaster finds co-located homologs. Its local route needs query protein FASTA plus either an annotated genome input or a prepared cblaster database. clinker compares the GenBank cluster files produced by cblaster.

## Install

```bash
python3 -m pip install "cblaster>=1.4.0" "clinker>=0.0.32"
cblaster --version
clinker --version
diamond version
```

Record the installed versions with the campaign artifacts. No installer or search is run by the public wrapper tests.

## Wrapper interface

Use a safe generic organism label and provide every biological input explicitly:

```bash
bash skills/genecluster-superpowers/scripts/run-cblaster.sh \
  --organism <ORGANISM_LABEL> \
  --query <QUERY_FASTA> \
  --genbank <ANNOTATED_GENBANK_OR_GFF> \
  --out-dir .runtime/cblaster/<ORGANISM_LABEL>
```

Instead of `--genbank`, pass `--database <DB_PREFIX_OR_DMND>` when both `<prefix>.dmnd` and `<prefix>.sqlite3` already exist. `--query-file`, `--genome`, and `--output-dir` remain accepted aliases. The wrapper accepts the positional shorthand `<label> <query.faa> <annotated-genome>`, but it has no proteome-only default.

GFF/GTF inputs require a matching nucleotide FASTA beside the annotation. A protein-only FASTA cannot supply the coordinates needed for cluster extraction.

Use a new or empty `--out-dir` for every invocation. The wrapper fails early when it finds prior entries there, so an annotated-genome run cannot reuse stale database or cluster outputs. `--database` permits reuse of a prepared database when it is kept outside the fresh output directory.

## Exact local chain

Build a database from annotated genome records:

```bash
cblaster makedb <ANNOTATED_GENBANK_OR_GFF> --name <DB_PREFIX>
```

Then save the search session as JSON and use that session for GenBank extraction:

```bash
cblaster search \
  --query_file <QUERY_FASTA> \
  --mode local \
  --database <DB_PREFIX>.dmnd \
  --gap 50000 \
  --min_hits 3 \
  --session_file <OUTPUT_DIR>/search-session.json \
  --output <OUTPUT_DIR>/clusters.tsv \
  --output_delimiter $'\t' \
  --plot <OUTPUT_DIR>/cblaster.html

cblaster extract_clusters <OUTPUT_DIR>/search-session.json \
  --output <OUTPUT_DIR>/clusters \
  --format genbank

clinker <OUTPUT_DIR>/clusters/*.gbk --plot <OUTPUT_DIR>/clinker.html
```

The summary TSV is for inspection; it is not an extraction session. `extract_clusters` consumes the cblaster JSON session and writes GenBank files. `clinker --plot <file.html>` creates portable HTML; SVG export is an interactive browser action, and `--output_html`/`--output_svg` are not current clinker flags.

If no clusters are extracted, the wrapper reports that clinker was skipped. It fails before tool calls when the query, annotated input, prepared database pair, organism label, GFF companion FASTA, numeric `--gap`/`--min-hits`, or fresh output directory is invalid.

Sources: [cblaster search guide](https://cblaster.readthedocs.io/en/latest/guide/search_module.html), [cblaster makedb guide](https://cblaster.readthedocs.io/en/latest/guide/makedb_module.html), [cblaster extract-clusters guide](https://cblaster.readthedocs.io/en/latest/guide/extract_clusters_module.html), [cblaster CLI source](https://github.com/gamcil/cblaster/blob/master/cblaster/parsers.py), and [clinker CLI](https://github.com/gamcil/clinker#usage).
