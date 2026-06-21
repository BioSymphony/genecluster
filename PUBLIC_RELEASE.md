# Public Release Checklist

This repo is a public-safe source snapshot, not a mirror of internal working repos. It intentionally excludes raw/heavy biological data, runtime outputs, provider responses, credentials, private tracker text, and local operator state.

The snapshot is ready for public publication only when all checks pass:

- `make public-release-check`
- no `.runtime/`, logs, caches, provider responses, pod IDs, or heavy biological files are tracked
- no local workstation paths or private automation paths appear in public docs
- examples use public, synthetic, or placeholder data
- provider launch examples require explicit credentials from environment variables or untracked secure env files
- public examples pass checks without paid provider access
- image examples use `<owner>` placeholders or repository-owner-derived names, not private registry owners
- historical run notes omit provider run IDs, account numbers, volume IDs, signed URLs, and private issue IDs

## GitHub Repository Settings

Suggested About description:

> Agent skill kit for genome-mining campaigns from molecule or pathway goals to reviewable biosynthetic gene-cluster work packets.

Suggested topics:

`agentic-bioinformatics`, `genome-mining`, `biosynthetic-gene-clusters`,
`natural-products`, `comparative-genomics`, `pathway-discovery`,
`pathway-gap-filling`, `transcriptomics`, `bioinformatics`, `multi-agent`,
`claude-code`, `codex`, `symphony`, `runpod`

Suggested social preview image:

`docs/diagrams/genecluster-social-preview.jpg`

Initialize or commit a fresh public git history only after the public release checks pass.
