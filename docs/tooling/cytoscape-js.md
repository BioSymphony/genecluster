# Cytoscape.js: integration plan for BioSymphony GeneCluster

**Status:** adopted in atlas viewer snippets; current npm release refreshed recently.
**Priority:** cheap-add (for pathway diagrams)
**Endorsed by:** reporting agent

## Purpose

Cytoscape.js (v3.33.3, current npm release; PMC9889963 2023 update) is a graph-theory library for embedding interactive network and pathway diagrams in HTML. It is the de-facto choice for SBGN-style pathway diagrams in modern bio papers and works seamlessly inside Quarto pages. Once our BIA pathway is encoded as a JSON graph, every per-species page can color-overlay coverage on the same diagram.

## What it would add to the BIA atlas specifically

The headline cross-species pathway-completion figure ("11/13 enzymes detected in Coptis, 9/13 in Houttuynia, 7/13 in Stephania, 8/13 in Phellodendron") is currently a hand-written table in the cross-species comparison MD. Cytoscape.js converts that into an interactive SBGN diagram per species: hover an enzyme node to see candidate counts, click to navigate to the per-protein evidence row in the xlsx.

## Install

```bash
# Pure-frontend; no backend Python install needed. Pulled via npm or CDN.
# Option A: install into the Quarto project for embedding
cd .runtime/<atlas>-final-deliverable
npm init -y
npm install "cytoscape@^3.33.3"

# Option B: CDN (zero-install, used inline in .qmd files)
# <script src="https://unpkg.com/cytoscape@3.33.3/dist/cytoscape.min.js"></script>
```

## Sample CLI: running on our existing data

This is a Quarto / HTML embed, not a CLI. Sketch:

```html
<!-- Inside cross-species/pathway-completion.qmd or a per-species .qmd -->
<div id="bia-pathway" style="width: 100%; height: 600px;"></div>
<script src="https://unpkg.com/cytoscape@3.33.3/dist/cytoscape.min.js"></script>
<script>
fetch('../data/bia-pathway-graph.json')
 .then(r => r.json())
 .then(graph => {
 cytoscape({
 container: document.getElementById('bia-pathway'),
 elements: graph.elements,
 style: graph.style,
 layout: { name: 'breadthfirst', directed: true }
 });
 });
</script>
```

The companion `bia-pathway-graph.json` (~1 file, hand-encoded once from the canonical Coptis BIA pathway, then auto-overlayed with per-species coverage at build time) lives at `.runtime/<atlas>-final-deliverable/data/bia-pathway-graph.json`.

## Integration point in our pipeline

- New helper: `pipeline/genecluster_annotation_direct/pathway_graph_builder.py`, generates the BIA pathway graph JSON once (from PMN 16 / KEGG map00950), then overlays per-species coverage from postprocess output.
- Quarto: `cross-species/pathway-completion.qmd` and per-species `.qmd` pages embed the graph via the snippet above.
- Postprocess: per-species coverage data already exists in `top-hits` and `clusters-diamond` sheets; pathway_graph_builder reads from there.

## Estimated integration cost

2 days focused.
- Day 1: Hand-encode canonical BIA pathway to a Cytoscape.js JSON; verify rendering in a standalone HTML page.
- Day 2: Wire per-species coverage overlay; embed into Quarto pages.

## Open questions / decisions to make before integrating

- SBGN vs custom node styling, SBGN is the standard but visually busy for a pathway with 13 nodes.
- Layout: hand-tuned positions (most readable for fixed pathway) or algorithmic `breadthfirst` (auto-rebalances when pathway updates)?
- PNG fallback: Cytoscape.js renders to canvas and supports PNG export, use it for PDF Quarto output.
- Static-image fallback for non-JS readers (PDF / journal print)?

## Citations

- Cytoscape.js docs: https://js.cytoscape.org/
- npm: https://www.npmjs.com/package/cytoscape
- 2023 update *Bioinformatics* PMC9889963: https://pmc.ncbi.nlm.nih.gov/articles/PMC9889963/
