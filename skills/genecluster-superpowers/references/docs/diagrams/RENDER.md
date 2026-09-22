# Render the GeneCluster Diagrams

## README Figures

The three README figures use editable SVG sources:

| Source | Purpose |
|---|---|
| `genecluster-session-flow.svg` | Campaign stages and responsibilities |
| `genecluster-route-claim-ceiling.svg` | Available data and supported results |
| `genecluster-local-cloud-boundary.svg` | Local and optional external compute |

Each figure also has a `-mobile.svg` layout with the same content in stacked panels. The READMEs select that layout below 600 pixels with the [picture element](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#the-picture-element). Both layouts use SVG for sharp text. Open an image to inspect it at full size. Each SVG includes a text title and description. Matching PNGs remain available for viewers that need raster images.

Keep labels consistent in the wide and mobile SVGs. After editing a wide SVG, regenerate its PNG with [CairoSVG](https://cairosvg.org/). The checked rendering version is 2.8.2; it is an optional documentation dependency.

```bash
python3 -m cairosvg docs/diagrams/genecluster-session-flow.svg \
  -o docs/diagrams/genecluster-session-flow.png -s 2
```

Repeat for the other changed SVGs. Check the complete figure for clipped labels and arrows before updating the packaged documentation.

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
