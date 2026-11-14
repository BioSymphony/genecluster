# plantiSMASH

**Status:** checked baseline 2.0.4.

plantiSMASH predicts candidate biosynthetic regions in plant genomes. Use a normal, non-editable source installation because its plugin discovery depends on the installed package layout.

## Installation contract

Use release 2.0.4 or an explicitly reviewed immutable commit. Record the source revision, environment lock, database state, and license terms. Do not describe local packaging iterations as upstream versions.

## Minimal pattern

```bash
plantismash --taxon plants --genefinding none \
  --outputfolder <OUTPUT_DIR> \
  <PUBLIC_OR_SYNTHETIC_GENBANK>
```

For FASTA plus GFF3, pass the genome FASTA as the positional input and the matching annotation with `--gff3`. Verify the reference IDs and CDS phase convention before running. [plantiSMASH 2.0.4 CLI source](https://github.com/plantismash/plantismash/blob/plantismash-2.0.4/run_antismash.py)

## Output contract

Retain input accessions and hashes, exact revision, environment and database versions, command, region coordinates, compact call tables, warnings, and output hashes.

plantiSMASH calls are hypotheses. Compare them with gene annotation, domains, expression, synteny, and other callers before making pathway claims.

[plantiSMASH 2.0.4 release](https://github.com/plantismash/plantismash/releases/tag/plantismash-2.0.4)
