# Contributing

BioSymphony GeneCluster is a public control-plane repository. Contributions should improve reusable contracts, validators, examples, documentation, or workflow scaffolding.

Before opening a change:

- Keep raw reads, private sequences, generated heavy outputs, provider logs, and credentials out of the repo.
- Use public, synthetic, or placeholder data in examples.
- Run `make public-release-check` before publication. Use `make public-audit` for a faster documentation-only pass while editing.
- Limit claims to what the included public evidence supports.

Provider examples should use environment variable names and placeholder paths only.
