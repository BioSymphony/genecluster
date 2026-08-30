# Cytoscape.js interaction pattern

**Status:** Adopted interaction pattern.

Provide Fit, Reset, Zoom in, Zoom out, and Center controls. Support the `f`, `0`, `+`, `-`, and `c` keys. Require Command or Control for wheel zoom so the graph does not capture normal page scrolling.

Use a pinned Cytoscape.js release. Vendor the reviewed file or use a trusted package manager. If you use a CDN, add an integrity hash and a restrictive content security policy.

## Initial values

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

## Toolbar HTML and CSS

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

## Command- or Control-gated wheel zoom

```javascript
// Keep wheel zoom off during normal page scrolling.
cy.userZoomingEnabled(false);
function setZoomMode(e) { cy.userZoomingEnabled(!!(e.ctrlKey || e.metaKey)); }
document.addEventListener('keydown', setZoomMode, { capture: true });
document.addEventListener('keyup', setZoomMode, { capture: true });
document.getElementById('cy').addEventListener('wheel', setZoomMode,
 { capture: true, passive: true });
```

## Toolbar and keyboard shortcuts

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

## Design choices

- Choose SBGN or custom node styles based on the pathway size and review needs.
- Provide a PNG fallback for PDF output because Cytoscape.js renders to a canvas.
- Use `preset` for a fixed, hand-tuned pathway. Use `breadthfirst` when the pathway changes often.

## See also

- [`docs/tooling/cytoscape-js.md`](../../../docs/tooling/cytoscape-js.md)
- [`docs/biosymphony-genecluster-superpower-roadmap.md`](../../../docs/biosymphony-genecluster-superpower-roadmap.md)
