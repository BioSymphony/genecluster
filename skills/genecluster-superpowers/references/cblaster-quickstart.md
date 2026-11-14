# cblaster + clinker quickstart

The local wrapper passed a two-cluster synthetic fixture with cblaster 1.4.0, clinker 0.0.32, and DIAMOND 2.2.5 on macOS ARM64.

The local cblaster route needs a protein query FASTA and genomic coordinates. Provide an annotated GenBank/EMBL file, or a GFF/GTF with its matching FASTA, to build the local database. A prepared database is also accepted when both `<prefix>.dmnd` and `<prefix>.sqlite3` exist.

```bash
python3 -m pip install "cblaster==1.4.0" "clinker==0.0.32"
cblaster config --email "${ENTREZ_EMAIL}"

bash skills/genecluster-superpowers/scripts/run-cblaster.sh \
  --organism <ORGANISM_LABEL> \
  --query <QUERY_FASTA> \
  --genbank <ANNOTATED_GENBANK_OR_GFF> \
  --out-dir .runtime/cblaster/<ORGANISM_LABEL>
```

Install DIAMOND separately and set `ENTREZ_EMAIL` before running setup. For a prepared database, replace `--genbank <ANNOTATED_GENBANK_OR_GFF>` with `--database <DB_PREFIX_OR_DMND>`. The wrapper runs the following steps.

1. `cblaster makedb <ANNOTATED_GENOME> --name <DB_PREFIX>` when a database must be built.
2. `cblaster search --session_file search-session.json` to save a JSON search session.
3. `cblaster extract_clusters search-session.json --output clusters --format genbank`.
4. `clinker clusters/*.gbk --plot clinker.html`.

Use a fresh or empty output directory for each run. Prepared databases may be reused from outside it. [Full output contract and version notes](docs/tooling/cblaster-clinker.md)
