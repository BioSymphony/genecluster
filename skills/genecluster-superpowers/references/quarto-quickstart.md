# Quarto 1.9: quickstart

**Status:** ✅ **ADOPTED**, blessed canonical atlas-report path. Atlas project lives at `.runtime/<atlas>-quarto-preview/`. 
**Install:** `brew install quarto` (macOS, **interactive**, runs `sudo installer`, will prompt for password). Linux: `wget` the .deb, `sudo dpkg -i`. Or `pip install "quarto-cli==1.9.*"` cross-platform fallback. Auto-handled by `tools/recommended/install-cheap.sh`.

> **Install gotcha:** the macOS .pkg install is interactive. Claude/agent invocations can't drive it. The user must run `brew install quarto` or `sudo installer ...` themselves the first time.

## Sample run on atlas data

```bash
# 1. Render the existing atlas project to HTML
cd .runtime/<atlas>-quarto-preview
quarto render --to html

# 2. Preview in default browser
open _book/index.html

# 3. Render to PDF (LaTeX backend; needs TinyTeX or system LaTeX)
quarto render --to pdf

# 4. Render to MECA bundle for journal submission
quarto render --to meca
```

Live preview during edits:

```bash
quarto preview .runtime/<atlas>-quarto-preview --port 4444
```

## Integration in our pipeline

Quarto is the report spine. Every other tool on the superpower roadmap lands its output as an embed in a `.qmd` page:

- cblaster + clinker → `cross-species/bbe-gradient.qmd` (ythe atlas chapter) (`<iframe>` clinker.html)
- JCVI MCScan → `cross-species/synteny-blocks.qmd` (PDF embed)
- Cytoscape.js → `cross-species/pathway-completion.qmd` (CDN script tag)
- Foldseek + ProstT5 → `cross-species/convergence-evidence.qmd` (table from `.m8`)
- CLEAN/HIT-EC → embedded into per-species page enrichment tables
- plantiSMASH → `cross-species/plantismash-only-clusters.qmd`

Project structure already established at `.runtime/<atlas>-quarto-preview/`:
```
_quarto.yml index.qmd species/{coptis,...}.qmd
cross-species/{bbe-gradient,pathway-completion,fact-check}.qmd
methods/{pipeline,reproducibility,caveats}.qmd
data/ _book/ sample-rendered/
```

## Open questions

- Single-file HTML (`embed-resources: true`) for distribution vs multi-file site for richer navigation? (Currently multi-file.)
- PDF backend: LaTeX (default, more journal templates) vs Typst (Quarto 1.9 first-class, faster, no TeX install)?
- Versioned Zenodo deposit per atlas update, Quarto MECA bundle aligns naturally with Zenodo's submission format.

## See also

- `docs/README.md`, full setup runbook (sudo prompt, brand.css, _quarto.yml authoring)
- `docs/tooling/quarto.md`, integration plan
- `docs/biosymphony-genecluster-superpower-roadmap.md`, Priority ★5, **adopted**
- `.runtime/<atlas>-quarto-preview/_book/index.html`, live atlas
