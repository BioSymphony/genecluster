# Review an atlas in Obsidian

Obsidian is an optional Markdown review surface. It does not replace the campaign artifacts or the Quarto report.

## Open the repository

Open `<REPO_ROOT>` as an Obsidian vault. Start with:

1. `README.md`
2. `docs/README.md`
3. `docs/workflow-campaigns.md`
4. `docs/architecture.md`
5. `docs/biosymphony-tooling-status.md`

Use a separate ignored workspace for generated campaign summaries. Do not copy raw or heavy data into the repository.

## Rendering limits

Obsidian renders Markdown, tables, Mermaid blocks, and math. It does not run Quarto shortcodes or embedded JavaScript.

Use `quarto render` when you need the publication or interactive report.
