# plantiSMASH quickstart

**Status:** checked baseline 2.0.4.

Use release 2.0.4 or a reviewed immutable commit. Install it normally rather than in editable mode so plugin discovery uses the installed package layout.

```bash
plantismash \
  --output-dir .runtime/plantismash/<RUN_ID> \
  <PUBLIC_OR_SYNTHETIC_GENBANK>
```

Check current flags through `plantismash --help`. Record the input accession and hash, exact revision, environment and database versions, command, region coordinates, warnings, and output hashes.

Treat predicted regions as hypotheses. Compare them with annotation, domain, expression, synteny, and independent caller evidence.

See the [per-tool guide](docs/tooling/plantismash.md).
