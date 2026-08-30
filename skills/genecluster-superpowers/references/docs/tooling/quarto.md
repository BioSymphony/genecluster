# Quarto

**Status:** checked baseline 1.9.37; current stable upstream 1.10.18 as of 2026-08-30.

Quarto renders a versioned report project to HTML, PDF, Word, and manuscript-oriented formats. GeneCluster can use it as a report layer for tables, provenance, methods, and figures.

## Baseline policy

The repository retains 1.9.37 as its documented baseline until the report fixture is checked against 1.10.18. Quarto 1.11 is prerelease and is not a public baseline here.

Install Quarto from the official [download page](https://quarto.org/docs/download/) and verify the version:

```bash
quarto --version
quarto render
```

## Manuscript and MECA output

MECA is configured in a Quarto manuscript project; it is not a `--to meca` command-line format. Configure JATS or `manuscript.meca-bundle: true` in the project, then run `quarto render`. See the official [manuscript components](https://quarto.org/docs/manuscripts/components.html) documentation.

## Output contract

Retain the source `.qmd` files, `_quarto.yml`, Quarto version, render command, and hashes of published outputs. Generated sites and large embedded data belong in ignored runtime storage unless they are intentionally reviewed release artifacts.
