# BioSymphony GeneCluster Agent Guide

This repo is the public BioSymphony GeneCluster skill kit for agents and agent harnesses.

## Operating Rules

- Keep durable public docs in `docs/`.
- Keep reusable skill material under `skills/`.
- Use `templates/linear-issue.md` for tracker-neutral issue drafts.
- Do not store API keys, tokens, provider IDs, private run logs, raw/heavy biological data, or unpublished biological sequences in this repo.
- Prefer placeholders such as `<AUTONOMY_HOME>`, `<RUNPOD_ENV_FILE>`, and `<PUBLIC_REPO_URL>` over local workstation paths.

## Dev Commands

- Inspect repo status: `git status --short --branch`
- List public files: `find docs skills templates pipeline images data -maxdepth 2 -type f | sort`
- Run the full public release check: `make public-release-check`
- Scan for accidental local raw/heavy artifacts: `make artifact-scan`
- Run the local GeneCluster demo harness: `make demo-campaign-dry-run`
- Run smaller/larger demo scopes: `make demo-campaign-smoke` or `make demo-campaign-public-mining`
- Probe local capabilities: `python3 skills/biosymphony/scripts/capability_probe.py --json`
- Check the public skill: `python3 skills/biosymphony/scripts/biosymphony_public_skill_audit.py --skill-root skills/biosymphony`
- Check a drafted issue: `python3 skills/biosymphony/scripts/preflight_check.py templates/linear-issue.md`
- Check GeneCluster example ledgers: use the command in `README.md`.

## Product Direction

BioSymphony GeneCluster gives agents tool knowledge and helpers for comparative genome and transcriptome analysis:

- Lead with tool selection, concrete calls, and useful chains across search, annotation, genome context, and visualization.
- Describe inputs, output formats, identifiers, versions, and integration readiness precisely.
- Agents prepare conversions between tools and keep conclusions tied to the resulting evidence.
- Provider lanes handle larger workloads behind finite launch contracts.
- Campaign helpers add resumable stages and input tracking when needed. Trackers and Symphony-style workers are optional execution choices.
- Use `templates/goal-prompt.md` for solo-agent work with the same artifact contracts.

## Public Safety

- Do not copy private structures, raw reads, unpublished sequences, API keys, tokens, provider response JSON, or private tracker text into this repo.
- Public examples must use public, synthetic, or placeholder data.
- Provider examples must use environment variable names or placeholder paths only, with no secret values.
- Runtime outputs belong under ignored `.runtime/` and should not be committed.
