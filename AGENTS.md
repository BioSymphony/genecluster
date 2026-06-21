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

BioSymphony GeneCluster should help agents run comparative-genomics campaigns that are easier to plan, inspect, and resume:

- Linear or another tracker stores task contracts, dependencies, acceptance criteria, check commands, and artifact handoffs.
- Symphony-style workers execute bounded source scouting, candidate search, comparative analysis, visualization, QA, and review-limit checks.
- Provider lanes handle heavy search and model work behind finite launch contracts.
- Review surfaces should keep conclusions tied to ledgers, versions, hashes, and stated limits.
- A capable Codex/Claude-style agent remains the orchestrator: use the repo's contracts and checks, but make ordinary campaign decisions without waiting for every detail to be encoded as a script.
- For `/goal` or solo-agent setups, use `templates/goal-prompt.md` and the same artifact contracts instead of forcing a tracker when one is unnecessary.

## Public Safety

- Do not copy private structures, raw reads, unpublished sequences, API keys, tokens, provider response JSON, or private tracker text into this repo.
- Public examples must use public, synthetic, or placeholder data.
- Provider examples must use environment variable names or placeholder paths only, with no secret values.
- Runtime outputs belong under ignored `.runtime/` and should not be committed.
