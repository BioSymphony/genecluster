# Memory note template

This is the shape every file under `.bioprospector-memory/` should follow. The folder is gitignored and lives only on the user's machine; notes survive `git pull` from upstream and compound across campaigns. See the Local Memory section in `skills/biosymphony/SKILL.md` for the audit-vs-behavior-change distinction.

## Path convention

```
.bioprospector-memory/YYYY-MM-DD-<short-kebab-slug>.md
```

One note per lesson. Keep slugs short and descriptive so the agent can scan a directory listing and find a relevant note fast.

## Five-section shape

Every note has five short sections in this order. Brief is good. A reader should be able to take the lesson without reading anything else.

```markdown
# <One-line title that names the lesson>

Date: YYYY-MM-DD

## What happened

One paragraph: the failure mode or surprise, with enough detail that the next
agent can recognize the same situation. Name the tool, the command, the symptom.

## What was tried

- Approach A. One sentence on why it did not work.
- Approach B. One sentence on why it did not work.

## What worked

The minimal fix or pattern that resolved it. Include the exact command or
config when that is the lesson.

## When this applies

The conditions under which to reach for this lesson. Be specific so the
next agent does not over-apply it.

## What to skip

Approaches that look tempting but are dead ends, so the next agent does
not re-run them.
```

## Worked example (non-biology, agent-process)

The example below is illustrative. It is about a CLI gotcha, not a campaign finding, and it makes no claim about biology. Notice how it would compound: any future session that hits this surface picks up the workaround without having to rediscover it.

```markdown
# Demo harness tempdir path must be read from stdout, not guessed

Date: 2026-05-12

## What happened

Ran `make demo-explore` and tried to chain the next step by hardcoding
the system tempdir path (e.g. `/var/folders/.../biosymphony-genecluster-demo.XXXXXX/`
on macOS) in a follow-up script. The path changes on every run because the
harness uses `mktemp -d`, so the follow-up step always opened a stale directory.

## What was tried

- Hardcoded the tempdir path from a prior run. Path was stale on the next run.
- Globbed `/var/folders/**/biosymphony-genecluster-demo.*/` and picked
  the newest. Worked once, then matched a stale directory from a previous
  session that had not been cleaned up.

## What worked

Capture the harness stdout and parse the `output_dir=...` line. The harness
prints the tempdir as its first line of output, so:

    OUTPUT_DIR=$(bash tools/genecluster_demo_harness.sh | awk -F= '/^output_dir/{print $2}')

Now downstream scripts always reference the current run's directory.

## When this applies

Any time the agent needs to chain a step after the demo harness, or programmatically
inspect demo artifacts. Not relevant for the harness itself.

## What to skip

Do not hardcode the tempdir path. Do not glob `/var/folders/`. Do not rely
on `$TMPDIR` either; the harness picks its own tempdir below it.
```

## What never goes in a memory note

The folder is gitignored, but notes still get read by agents and can leak into other artifacts. Never include any of the following:

- secrets, tokens, API keys, signed URLs
- private filesystem paths (use `~/...` or `<repo-root>/...` placeholders)
- campaign-specific organism, accession, gene, or pathway identifiers (those belong in the campaign dossier, not in cross-campaign memory)
- raw sequences (protein, nucleotide, or otherwise) or large outputs
- provider-specific instance IDs, pod IDs, project IDs, account IDs
- private-tracker URLs or ticket bodies

If a lesson can only be expressed by naming campaign-specific data, it belongs in the campaign dossier, not in `.bioprospector-memory/`.
