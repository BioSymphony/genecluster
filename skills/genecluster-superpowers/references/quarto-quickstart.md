# Quarto Quickstart

Use [Quarto 1.11.9](https://github.com/quarto-dev/quarto-cli/releases/tag/v1.11.9)
for new work. To reproduce an earlier report, use its recorded version.

From the report directory, run:

```bash
quarto --version
quarto render --to html
```

Use `quarto render --to pdf` after configuring a PDF engine. For MECA, configure
JATS and a bundle filename in the [Quarto guide](docs/tooling/quarto.md) and
run `quarto render`. Check that the rendered report links to the expected
tables and that any MECA archive contains its manifest.
