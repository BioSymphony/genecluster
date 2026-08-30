# Cytoscape.js

**Status:** checked baseline 3.33.3; current upstream 3.34.2 as of 2026-08-30.

Cytoscape.js renders interactive pathway and evidence graphs in a browser. A GeneCluster report can use a shared graph model and overlay per-species coverage or candidate evidence.

## Baseline policy

Keep the exact library version in the page or package lock. Recheck rendering and export behavior before moving the public baseline from 3.33.3.

```bash
npm install "cytoscape@3.33.3"
```

## Output contract

Retain the graph JSON, style definition, layout settings, exact Cytoscape.js version, a static fallback for non-JavaScript readers, and hashes of released assets.

Sources: [Cytoscape.js documentation](https://js.cytoscape.org/) and [npm package](https://www.npmjs.com/package/cytoscape).
