# Cytoscape.js: copy-paste snippet for atlas reports

**Status:** ✅ **ADOPTED**, pathway-completion viewer live at `.runtime/<atlas>-quarto-preview/cross-species/pathway-completion.html`., every embedded interactive graph viewer needs Fit/Reset/+/−/Center buttons + keyboard shortcuts (f/0/+/−/c) + ⌘/Ctrl-gated wheel-zoom. Canonical viewer below ships those defaults. See [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md) for the full inventory.
**Install:** Pure-frontend; no install. Pull from CDN: `<script src="https://unpkg.com/cytoscape@3.33.3/dist/cytoscape.min.js"></script>`.

## Working impl reference

The canonical working impl is `.runtime/<atlas>-quarto-preview/sample-rendered/pathway-completion.html` (lines 90-360). Read it before customizing, it's been pressure-tested for the per-species pathway-completion figure.

## Init values (proven defaults)

```javascript
var cy = cytoscape({
 container: document.getElementById('cy'),
 elements: { nodes: nodes, edges: edges },
 minZoom: 0.25,
 maxZoom: 4,
 wheelSensitivity: 0.2,
 // ...style + layout
});
```

## Toolbar HTML+CSS

```html
<div class="cy-controls" role="toolbar" aria-label="Pathway diagram controls">
 <button id="cy-fit" class="primary" title="Fit all (f)">⤢ Fit</button>
 <button id="cy-reset" title="Reset (0)">⟲ Reset</button>
 <button id="cy-zoom-in" title="Zoom in (+)">＋ Zoom in</button>
 <button id="cy-zoom-out" title="Zoom out (−)">− Zoom out</button>
 <button id="cy-recenter" title="Center (c)">⊙ Center</button>
 <span class="kbd-hint">Keys: <kbd>f</kbd> · <kbd>0</kbd> · <kbd>+</kbd>/<kbd>−</kbd> · <kbd>c</kbd>; scroll-zoom needs <kbd>⌘</kbd>/<kbd>Ctrl</kbd></span>
</div>
<div id="cy" style="width:100%;height:600px;border:1px solid #d8d2c4;border-radius:6px;background:#f6f4ef;"></div>
```

## Cmd/Ctrl-gated wheel zoom (the load-bearing UX detail)

```javascript
// Default OFF: page-scrolling shouldn't accidentally lose the diagram.
cy.userZoomingEnabled(false);
function setZoomMode(e) { cy.userZoomingEnabled(!!(e.ctrlKey || e.metaKey)); }
document.addEventListener('keydown', setZoomMode, { capture: true });
document.addEventListener('keyup', setZoomMode, { capture: true });
document.getElementById('cy').addEventListener('wheel', setZoomMode,
 { capture: true, passive: true });
```

## Toolbar wiring + keyboard shortcuts

```javascript
function fitAll() { cy.animate({ fit: { padding: 30 }, duration: 200 }); }
function resetView() {
 if (initialState) cy.animate({ zoom: initialState.zoom, pan: initialState.pan, duration: 250 });
 else fitAll();
}
function zoomBy(f) {
 var z = Math.max(0.25, Math.min(4, cy.zoom() * f));
 cy.animate({ zoom: { level: z, position: { x: cy.width()/2, y: cy.height()/2 } }, duration: 150 });
}
function centerSelection() {
 var sel = cy.$(':selected');
 cy.animate({ center: { eles: sel.length ? sel : cy.nodes() }, duration: 200 });
}
document.getElementById('cy-fit').addEventListener('click', fitAll);
document.getElementById('cy-reset').addEventListener('click', resetView);
document.getElementById('cy-zoom-in').addEventListener('click', () => zoomBy(1.3));
document.getElementById('cy-zoom-out').addEventListener('click', () => zoomBy(1/1.3));
document.getElementById('cy-recenter').addEventListener('click', centerSelection);

document.addEventListener('keydown', function(e) {
 if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
 if (e.metaKey || e.ctrlKey || e.altKey) return;
 switch (e.key) {
 case 'f': case 'F': fitAll(); e.preventDefault(); break;
 case '0': resetView(); e.preventDefault(); break;
 case '+': case '=': zoomBy(1.3); e.preventDefault(); break;
 case '-': case '_': zoomBy(1/1.3); e.preventDefault(); break;
 case 'c': case 'C': centerSelection(); e.preventDefault(); break;
 }
});
```

## Open questions

- SBGN node styling vs custom, SBGN is the standard but visually busy for ≤13-node pathways
- PNG fallback for PDF Quarto output (Cytoscape.js renders to canvas)
- Layout: `preset` with hand-tuned positions (most readable for fixed pathway) vs `breadthfirst` (auto-rebalances when pathway updates)

## See also

- `docs/tooling/cytoscape-js.md`, full integration plan
- `.runtime/<atlas>-quarto-preview/sample-rendered/pathway-completion.html`, canonical working impl
- `docs/biosymphony-genecluster-superpower-roadmap.md`, reporting agent solo
