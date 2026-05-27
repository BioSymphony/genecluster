# Claude Code Entry Point

This repo is an agent skill for finding biosynthetic gene clusters and assembling pathway evidence across genomes and transcriptomes. When a user opens this repo in Claude Code, treat the repo as the agent skill and the user as the mission supervisor. The user names a pathway, a target molecule, an evidence gap, or a comparative question. You assemble the campaign: scout public genomes and transcriptomes, pick a defensible evidence route, run candidate-gene search, anchor candidates in genomic context via synteny and neighborhood capture, detect clusters, score function across the tool jury, check pathway completeness, and produce a reviewable evidence package. The user reviews and approves cloud launches.

## First Steps

1. Read `skills/biosymphony/SKILL.md` for the canonical campaign-orchestration skill: Stage 0 preflight, route scouting, contracts, validators, claim audit, closeout standard.
2. Read `skills/genecluster-superpowers/SKILL.md` when extending the atlas with new tools.
3. Read `docs/agent-orchestrator-guide.md` for orchestrator-side workflow and the default flow for a new goal.
4. Read `docs/glossary.md` for terms-of-art (claim ceiling, route card, maturity ladder, evidence normalizer, and more).
5. Operating rules and dev commands live in `AGENTS.md`.

## Agent Posture

- Translate the user's goal into a campaign packet without waiting for every field to be pre-filled.
- Run validators before dispatch and after artifact pullback.
- Pick the route, claim ceiling, and next bounded wave from the contracts in `skills/biosymphony/`.
- Make conservative choices that match the existing repo patterns. Surface uncertainties at closeout rather than blocking on every judgment call.
- Escalate to cloud only after a launch bundle and stage contract validate locally.

## Public Safety

Never commit API keys, tokens, private tracker text, raw biological data, provider response JSON, unpublished sequences, or local workstation paths. Use placeholders for any secret value. Heavy outputs belong in ignored `.runtime/` directories. Examples must use public, synthetic, or placeholder data.

## Validation Commands You Will Invoke

- Full release check: `make public-release-check`
- Demo harness: `make demo-campaign-dry-run`, `make demo-campaign-smoke`, `make demo-campaign-public-mining`
- Capability probe: `python3 skills/biosymphony/scripts/capability_probe.py --json`
- Skill audit: `python3 skills/biosymphony/scripts/biosymphony_public_skill_audit.py --skill-root skills/biosymphony`
- Issue validation: `python3 skills/biosymphony/scripts/preflight_check.py path/to/issue.md`
- Local-artifact scan: `make artifact-scan`

## Closeout Standard

Every campaign pass should finish with:

- the selected route and claim ceiling
- artifacts produced (paths and hashes where applicable)
- validation commands run
- next bounded worker or issue wave
- biological uncertainties that need user judgment, separated from orchestration gaps you can close yourself
