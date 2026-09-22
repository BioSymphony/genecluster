# Claude Code Entry Point

Use GeneCluster’s tool knowledge base and calling helpers to investigate candidate biosynthetic genes and gene clusters. Select tools for the user’s question, run suitable commands, and connect their outputs into the next analysis or report.

## Start With Tools

1. Read `skills/genecluster-superpowers/SKILL.md`.
2. Use `docs/tooling/README.md` for tool inputs, commands, and outputs.
3. Read `docs/tooling/tool-chaining.md` for runnable entry points and required format conversions.
4. Check versions and integration limits in `docs/biosymphony-tooling-status.md`.

Follow `AGENTS.md` for repository rules and validation commands. Use `skills/biosymphony/SKILL.md` when a longer analysis needs input tracking, route selection, or restart support.

## Connect Results

Resolve identifiers and coordinate conventions before joining tool outputs. Extract matched sequences when the next tool requires FASTA. Convert supported columns before using table helpers. Check exit status, output files, and empty results before starting a dependent call.

Keep similarity scores, predicted function, genomic proximity, and experimental evidence distinct. Return the findings and plots that answer the question, with sources and limits.

Prepare the scope and resource limits before obtaining approval for external compute. Keep credentials, private paths, provider responses, private tracker text, raw data, and unpublished sequences outside public artifacts.

## Repository Checks

- Full release check: `make public-release-check`.
- Local fixture demo: `make demo-campaign-dry-run`.
- Tool availability: `bash skills/genecluster-superpowers/scripts/superpowers-status.sh`.
- Publication checks without the demo: `make public-audit-strict`.
