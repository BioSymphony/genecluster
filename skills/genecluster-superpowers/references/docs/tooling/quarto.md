# Quarto 1.9: integration plan for BioSymphony GeneCluster

**Status:** ✓ ADOPTED. blessed canonical atlas-report path. A recent upstream freshness audit confirms Quarto CLI 1.9.37 is still the current release; campaign rendered as a Quarto book.
**Priority:** ★5 → blessed
**Endorsed by:** reporting agent (solo, but high-confidence)

## Purpose

Quarto 1.9.37 is the Pandoc-based scientific publishing system that renders a single `.qmd` source to HTML site + PDF + Word + journal-ready MECA bundle. It is the de-facto report spine for 2024-2026 reproducible bioinformatics manuscripts. It replaces our current 4-Markdown-doc + xlsx stack with a single project-level config that auto-rebuilds on data updates.

## What it would add to the BIA atlas specifically

Today the atlas deliverable is 4 hand-written biology MD files, 4 xlsx workbooks, and a hand-written cross-species comparison MD. There is no canonical "atlas index", no auto-PDF, no journal-submission bundle. Quarto rolls all of that into:
- A static HTML site with per-species pages, cross-species pages, and a methods section.
- A PDF / MECA bundle for journal submission.
- Auto-rebuild on data update (re-render `.qmd` → re-export PDF in one command).
- Embeds for clinker SVGs, JCVI synteny PDFs, Cytoscape.js pathway diagrams, igv-reports tracks.

This is the structural change that lets every other tool on the roadmap actually *show up* in the manuscript without manual cut-and-paste.

## Install

```bash
# macOS (.pkg installer; recommended)
curl -LO https://github.com/quarto-dev/quarto-cli/releases/download/v1.9.37/quarto-1.9.37-macos.pkg
sudo installer -pkg quarto-1.9.37-macos.pkg -target /

# Linux (deb)
# wget https://github.com/quarto-dev/quarto-cli/releases/download/v1.9.37/quarto-1.9.37-linux-amd64.deb
# sudo dpkg -i quarto-1.9.37-linux-amd64.deb

# Or via PyPI wrapper (works cross-platform)
pip install "quarto-cli==1.9.*"

# Verify
quarto --version
```

## Sample CLI: running on our existing data

```bash
# 1. Initialize a Quarto project in the deliverable dir
cd .runtime/<atlas>-final-deliverable
quarto create-project --type website .

# 2. Render the static site (writes _site/)
quarto render

# 3. Render the PDF (writes _book/atlas.pdf)
quarto render --to pdf

# 4. Render the MECA bundle for journal submission (Quarto Manuscripts)
quarto render --to meca
```

Project structure (target):

```
.runtime/<atlas>-final-deliverable/
├── _quarto.yml # project config
├── index.qmd # landing page (Houttuynia-Fig-4-style hero)
├── species/{coptis,houttuynia,stephania,phellodendron}.qmd
├── cross-species/{bbe-gradient,pathway-completion,synteny-blocks,fact-check}.qmd
├── methods/{pipeline,reproducibility,caveats}.qmd
├── data/ # bundled xlsx + JSON + SVG
└── _site/ _book/ # rendered outputs
```

## Integration point in our pipeline

- One-time bootstrap: port the existing 4 biology MDs and the cross-species MD into `.qmd` files.
- New helper: `tools/quarto_render.sh`, a thin wrapper that runs `quarto render` after each campaign update.
- Postprocess scripts continue producing xlsx; Quarto reads xlsx via Python chunks for the per-species summary tables.
- All future tooling integrations (cblaster SVGs, JCVI synteny PDFs, Cytoscape.js graphs, Foldseek convergence tables) embed directly into the relevant `.qmd` page.

## Estimated integration cost

3-5 days for the baseline (Phase 1 of the roadmap implementation plan).
- Day 1: `quarto create-project`; port `index.qmd` and one species page.
- Day 2: Port remaining species pages + cross-species pages.
- Day 3: Port methods + caveats; pin Pandoc/Quarto versions in `_quarto.yml`.
- Day 4: Wire xlsx → per-species summary tables via Python chunks.
- Day 5: PDF + MECA output validation; CI hook for auto-render on data update.

## Open questions / decisions to make before integrating

- Single-file HTML (`embed-resources: true`) for easy distribution vs multi-file site for richer navigation?
- PDF backend: LaTeX (default) vs Typst (Quarto 1.9 first-class), Typst is faster, no TeX install, but LaTeX has more journal templates.
- Where do builds go? Inside `.runtime/` (gitignored) or committed to repo for stable URLs?
- Versioned Zenodo deposit per atlas update, Quarto MECA bundle aligns naturally with Zenodo's submission format.

## Citations

- Quarto 1.9 release announcement (2026-03-24): https://quarto.org/docs/blog/posts/2026-03-24-1.9-release/
- Quarto Manuscripts: https://quarto.org/docs/manuscripts/
- Quarto Dashboards: https://quarto.org/docs/dashboards/
- Download: https://quarto.org/docs/download/
- GitHub releases: https://github.com/quarto-dev/quarto-cli/releases
