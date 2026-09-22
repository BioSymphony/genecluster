# Render the GeneCluster Diagrams

## README Figures

The two README figures use editable SVG sources:

| Source | Purpose |
|---|---|
| `genecluster-session-flow.svg` | Tool knowledge, calls, and preparation for the next call |
| `genecluster-tool-chain.svg` | Protein search, sequence extraction, annotation, and reporting |

Each figure also has a `-mobile.svg` layout with the same content in stacked panels. The READMEs select that layout below 600 pixels with the [picture element](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#the-picture-element). Both layouts use SVG for sharp text. Open an image to inspect it at full size. Each SVG includes a text title and description. The session-flow figure also has a PNG for viewers that need a raster image.

Keep labels consistent in the wide and mobile SVGs. After editing a wide SVG, regenerate its PNG with [CairoSVG](https://cairosvg.org/). The checked rendering version is 2.8.2; it is an optional documentation dependency.

```bash
python3 -m cairosvg docs/diagrams/genecluster-session-flow.svg \
  -o docs/diagrams/genecluster-session-flow.png -s 2
```

Regenerate an existing PNG when its SVG changes. Check the complete figure for clipped labels and arrows before updating the packaged documentation.

## Supporting Figures

`genecluster-route-claim-ceiling.svg` explains data requirements. `genecluster-local-cloud-boundary.svg` explains compute options. Both retain mobile layouts and PNG copies.

## Other Diagrams

The remaining diagrams use Mermaid sources (`*.mmd`). Each source defines its colors and layout. The shared `synth-theme.css` adds the existing glow treatment.

Requires [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli). To render one source:

```bash
npx -y @mermaid-js/mermaid-cli \
  -i docs/diagrams/<name>.mmd \
  -o docs/diagrams/<name>.png \
  -b "#0a1024" -s 2 \
  --cssFile docs/diagrams/synth-theme.css
```

The hero banner (`genecluster-retro-synth-banner.jpg`) and social preview are standalone artwork.
