# BioSymphony GeneCluster Atlas In Obsidian

Obsidian is optional. It is useful for reading and editing Markdown narrative, backlinks, and graph relationships; Quarto remains the publishable HTML/PDF route.

## Setup

1. Install Obsidian from `obsidian.md`.
2. Open the public repo root as a vault.
3. Enable `Settings -> Files & Links -> Detect all file extensions` so `.qmd` files appear.
4. Optionally install the community Quarto plugin for better `.qmd` highlighting.

Use `<repo-root>` as the vault path. The public snapshot intentionally omits `.runtime/`, private run logs, provider artifacts, and generated atlas outputs.

## Suggested Reading Order

1. `README.md`
2. `docs/README.md`
3. `docs/architecture.md`
4. `docs/biosymphony-tooling-status.md`
5. `docs/data/pathway-species-catalog.tsv`
6. `docs/data/pathway-species-catalog.tsv`

When you have a local derived atlas, point Obsidian at that summary directory separately or link it from an ignored working note. Do not copy raw/heavy biological data into this repo.

## Quarto Differences

Obsidian renders normal Markdown, tables, Mermaid blocks, and math. It does not execute Quarto shortcodes, embedded JavaScript, or Cytoscape.js panels. Use `quarto render` from a local Quarto project for the interactive or publication view.

## Public Snapshot Rule

Obsidian workspaces can create local metadata. Keep those files ignored or outside the repo unless they are intentionally public-safe docs.
