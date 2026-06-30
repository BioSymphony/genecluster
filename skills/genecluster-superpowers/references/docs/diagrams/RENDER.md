# Rendering the GeneCluster diagrams

The diagrams are authored as Mermaid sources (`*.mmd`) and rendered to PNG in a
"synth-lab" style (neon nodes on a dark background, soft per-node glow) that
echoes the project banner. Each `*.mmd` carries its own `%%{init}%%` theme
(palette, `lineColor`, `edgeLabelBackground`) and `classDef` colours, so the
palette lives with the source.

## Regenerate a PNG

Requires [`@mermaid-js/mermaid-cli`](https://github.com/mermaid-js/mermaid-cli)
(`mmdc`). No global install needed:

```bash
npx -y @mermaid-js/mermaid-cli \
  -i docs/diagrams/<name>.mmd \
  -o docs/diagrams/<name>.png \
  -b "#0a1024" \
  -s 2 \
  --cssFile docs/diagrams/synth-theme.css
```

- `-b "#0a1024"` sets the dark canvas background.
- `-s 2` renders at 2x for crisp text.
- `--cssFile synth-theme.css` injects the neon glow and edge-label colour
  (geometry-free, so it never shifts the layout).

## Regenerate all

```bash
for f in docs/diagrams/*.mmd; do
  n="${f%.mmd}"
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "$n.png" -b "#0a1024" -s 2 \
    --cssFile docs/diagrams/synth-theme.css
done
```

The hero banner (`genecluster-retro-synth-banner.jpg`) and social preview are
standalone art, not generated from Mermaid.
