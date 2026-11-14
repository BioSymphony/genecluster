# plantiSMASH quickstart

**Status:** checked baseline 2.0.4.

Use release 2.0.4 or a reviewed immutable commit. Install it normally rather than in editable mode so plugin discovery uses the installed package layout.

```bash
plantismash --taxon plants --genefinding none \
  --outputfolder .runtime/plantismash/<RUN_ID> \
  <PUBLIC_OR_SYNTHETIC_GENBANK>
```

For FASTA input, pass the genome FASTA and add `--gff3` with its matching annotation. Record the input accessions and hashes, exact revision, database versions, command, region coordinates, and output hashes.

Treat predicted regions as hypotheses. Compare them with annotation, domain, expression, synteny, and independent caller evidence.

See the [per-tool guide](docs/tooling/plantismash.md).
