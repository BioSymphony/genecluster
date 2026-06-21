# BioSymphony Public Skill Export Policy

Status: draft guardrail v1
Last reviewed: 2026-04-30

BioSymphony can use non-public campaigns to harden the skill, but the public
skill must stay reusable and provider-neutral.

## Public Defaults

- Use generic GeneCluster scopes: `smoke`, `candidate_search`,
  `genome_context`, `coexpression`, `synteny`, `full_public_mining`, and
  `next_experiment_design`.
- Treat `runpod_pod` as the most mature heavy adapter, not as the only valid
  execution mode.
- Keep the campaign shape cross-species and goal-driven:
  source-species canonical proteins -> target-species datasets -> reciprocal
  support -> anchoring -> neighborhoods -> reviewable pathway packet.
- Ask only unanswered intake questions. If ledgers already include accessions,
  source URLs, query seeds, or provider choices, summarize them before asking
  the operator for anything.
- Use public/open data examples only when bundled in the public skill.
  Non-public demo work stays outside public examples.

## Public Export Exclusions

Exclude these from a public skill release:

- `references/internal/`
- `.runtime/`, `dry-run/`, repo snapshots, and provider pullback summaries
- raw FASTQ/SRA/BAM/CRAM/SAM files, genome assemblies, BLAST/MMseqs/HMMER
  databases, indexes, and workflow workdirs
- operator-specific absolute paths, email addresses, secrets, API keys, volume
  ids, datacenter ids, and non-public GitHub repo defaults
- unpublished biological sequences and collaborator-restricted data
- campaign aliases or runbooks that only make sense for an internal run

## Compatibility Allowances

Development workspaces may keep example fixtures and backward-compatible aliases
while the skill is under development. Those are acceptable only when
public-facing docs do not present them as defaults and checks prevent them
from becoming silent execution claims.

## Required Check

Before packaging or reviewing the public skill, run:

```bash
python3 skills/biosymphony/scripts/biosymphony_public_skill_audit.py \
  --skill-root skills/biosymphony
```

The check fails on hard private tokens in public skill paths and warns on
example-specific biological terms outside examples/tests/internal notes.
Use `--include-code-warnings` for a deeper compatibility-code scan before a
public release branch cleanup.
