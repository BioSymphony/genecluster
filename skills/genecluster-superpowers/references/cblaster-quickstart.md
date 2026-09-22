# cblaster + clinker quickstart

**Status:** wrapper contract only; no live search or biological validation is claimed.

The local cblaster route needs a protein query FASTA and genomic coordinates. Provide an annotated GenBank/EMBL file, or a GFF/GTF with its matching FASTA, to build the local database. A prepared database is also accepted when both `<prefix>.dmnd` and `<prefix>.sqlite3` exist.

```bash
python3 -m pip install "cblaster>=1.4.0" "clinker>=0.0.32"

bash skills/genecluster-superpowers/scripts/run-cblaster.sh \
  --organism <ORGANISM_LABEL> \
  --query <QUERY_FASTA> \
  --genbank <ANNOTATED_GENBANK_OR_GFF> \
  --out-dir .runtime/cblaster/<ORGANISM_LABEL>
```

For a prepared database, replace `--genbank <ANNOTATED_GENBANK_OR_GFF>` with `--database <DB_PREFIX_OR_DMND>`. The wrapper uses the current cblaster contract:

1. `cblaster makedb <ANNOTATED_GENOME> --name <DB_PREFIX>` when a database must be built;
2. `cblaster search --session_file search-session.json` to save a JSON search session;
3. `cblaster extract_clusters search-session.json --output clusters --format genbank`;
4. `clinker clusters/*.gbk --plot clinker.html`.

The summary TSV is an inspection artifact, not an extraction session. Use a fresh or empty output directory for each run; prepared databases may be reused from outside it. Missing query files, annotated inputs, prepared database pairs, GFF companion FASTA files, unsafe organism labels, or invalid numeric limits fail before a search. See [`docs/tooling/cblaster-clinker.md`](docs/tooling/cblaster-clinker.md) for the full output contract and upstream sources.
