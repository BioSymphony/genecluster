# Contributing

Contribute campaign instructions, tool adapters, validators, public examples, or documentation. Describe the problem your change solves and how you checked the result.

Before opening a change:

- Keep raw reads, private sequences, generated heavy outputs, provider logs, and credentials out of the repo.
- Use public, synthetic, or placeholder data in examples.
- Install Bash, Make, ripgrep, and Python 3 with `openpyxl` and `PyYAML`. Run `make public-release-check`. For content, artifact, and link checks alone, run `make public-audit-strict`.
- Limit claims to what the included public evidence supports.

Use environment variable names and placeholder paths in provider examples.
