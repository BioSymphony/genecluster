# plantiSMASH

**Status:** checked baseline 2.0.4.

plantiSMASH predicts candidate biosynthetic regions in plant genomes. Use a normal, non-editable source installation because its plugin discovery depends on the installed package layout.

## Installation contract

Use release 2.0.4 or an explicitly reviewed immutable commit. Record the source revision, environment lock, database state, and license terms. Do not describe local packaging iterations as upstream versions.

## Minimal pattern

```bash
plantismash \
  --output-dir <OUTPUT_DIR> \
  <PUBLIC_OR_SYNTHETIC_GENBANK>
```

Confirm current flags through the upstream help output.

## Output contract

Retain input accessions and hashes, exact revision, environment and database versions, command, region coordinates, compact call tables, warnings, and output hashes.

plantiSMASH calls are hypotheses. Compare them with gene annotation, domains, expression, synteny, and other callers before making pathway claims.

Source: [plantiSMASH releases](https://github.com/plantismash/plantismash/releases).
