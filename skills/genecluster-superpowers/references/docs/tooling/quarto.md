# Quarto

Use Quarto to render candidate tables, provenance, and figures as reports.
Install [Quarto 1.11.9](https://github.com/quarto-dev/quarto-cli/releases/tag/v1.11.9)
for new work. Quarto 1.11 includes the Deno certificate fix described in the
[release announcement](https://opensource.posit.co/blog/2026-11-02_quarto-1-11/).
Use the recorded version, such as 1.9.37, to reproduce an older report.

## Render A Report

From the report project directory, check the version and render HTML.

```bash
quarto --version
quarto render --to html
```

A macOS test of 1.11.9 rendered a synthetic HTML book with a data table and a
working CSV link. Check asset links and tables on your own report after an
upgrade.

## Render A Manuscript Bundle

Set JATS output and an explicit bundle name in the manuscript project.

```yaml
project:
  type: manuscript
manuscript:
  meca-bundle: bundle.zip
format:
  html: default
  jats: default
```

Run `quarto render` to produce the HTML article, JATS XML, and MECA archive.
With the default output directory, inspect `_manuscript/bundle.zip` and verify
that its manifest references the article and source files. See the
[manuscript documentation](https://quarto.org/docs/manuscripts/components.html#meca-bundle).

Retain the source `.qmd` files, `_quarto.yml`, version, command, and output
hashes. Keep rendered sites and large embedded data in ignored runtime storage.
