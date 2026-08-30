# antiSMASH 8 public integration guide

**Status:** checked baseline 8.0.4 for bacterial and fungal BGC calling.

antiSMASH does not provide the current plant-specific route in this kit. Use plantiSMASH for plant-focused calling and treat cross-tool agreement as supporting evidence rather than a substitute for biological review.

## Input contract

Use a public or synthetic GenBank record with stable identifiers and appropriate feature annotations. Record the source accession, access date, input hash, taxon setting, antiSMASH version, database versions, and command.

## Container pattern

Prefer the official, immutable image digest or a reproducibly built image. Verify the image source and database setup before use.

```bash
antismash \
  --taxon <BACTERIA_OR_FUNGI> \
  --output-dir <OUTPUT_DIR> \
  <INPUT_GENBANK>
```

Choose options from the current [antiSMASH documentation](https://docs.antismash.secondarymetabolites.org/) rather than copying unreviewed historical flags.

## Output contract

Retain:

- the input accession and SHA-256;
- the exact antiSMASH and database versions;
- the full command and exit state;
- region identifiers and coordinates;
- compact JSON or tabular summaries;
- hashes of retained outputs;
- warnings and incomplete database states.

Raw inputs, large database payloads, provider logs, credentials, and provider response JSON stay outside this repository.

## Review limits

A predicted region is a computational BGC hypothesis. Review gene models, domain evidence, neighborhood context, assembly quality, and supporting literature before making pathway or functional claims.

Sources: [antiSMASH releases](https://github.com/antismash/antismash/releases), [documentation](https://docs.antismash.secondarymetabolites.org/), and [plantiSMASH](https://github.com/plantismash/plantismash).
