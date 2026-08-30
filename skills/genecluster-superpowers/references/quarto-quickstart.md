# Quarto quickstart

**Status:** checked baseline 1.9.37; current stable upstream 1.10.18 as of 2026-08-30.

Install Quarto from the official [download page](https://quarto.org/docs/download/) or your trusted package manager. The repository keeps 1.9.37 as its report baseline until 1.10.18 passes the public fixture.

## Render

```bash
cd .runtime/<REPORT_PROJECT>
quarto --version
quarto render
quarto render --to html
quarto render --to pdf
```

For MECA output, configure a Quarto manuscript project with JATS or `manuscript.meca-bundle: true`, then run `quarto render`. MECA is not a `--to` format. See [manuscript components](https://quarto.org/docs/manuscripts/components.html).

Keep generated sites and large embedded data in ignored runtime storage unless they are reviewed release artifacts.
