# Cytoscape.js

Use Cytoscape.js to display pathways and compare candidate evidence across
species. Reuse one graph structure and add species-specific evidence as data
fields.

Use 3.33.3 to reproduce the checked viewer. The 2026-11-13 upstream review found
[3.35.0](https://github.com/cytoscape/cytoscape.js/releases/tag/v3.35.0).
Before updating the pin, check selection, fit and reset controls, and export in
the target browser.

```bash
npm install --save-exact cytoscape@3.33.3
```

Retain the graph JSON, styles, layout settings, exact version, and a static
fallback that readers can open without JavaScript.
