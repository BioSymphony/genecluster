## Summary

<One or two sentence scientific goal and artifact outcome.>

## Inputs

- `<input id>` - <source, local path, secure store reference, or database accession>
- Literature scope: recent preprints (bioRxiv, chemRxiv) for fast-moving enzyme/pathway targets, in addition to peer-reviewed references.

## Acceptance Criteria

- [ ] <Specific, testable assertion, e.g. `figure_manifest.json` contains all input IDs and artifact paths.>
- [ ] <Specific render or metric assertion, e.g. final PNG exists at 2200x1700 and is nonblank.>
- [ ] <Specific scientific provenance assertion, e.g. contour level, PDB ID, model source, or score field recorded.>

## Validation Commands

```bash
<exact command from repo root>
```

## Touched Areas

- `<path>` - <why this area is in scope>

## Dependencies

Blocked by: <issue-id>

## Risk Notes

- Do not store secrets, tokens, private sequences, private structures, or unpublished data in Linear.
- Record confidence limitations for predicted structures and affinity estimates.
- Keep raw expert commands disabled unless explicitly required and reviewed.

## Orchestration Guardrails

- Prompt render preflight must prove the issue body is non-empty and has no unresolved template tags.
- Provider payload preflight must check payload byte size before any API call.
- Snapshot or branch preflight must prove required bundle/scripts exist in the Git ref the worker will use.
- Silent fallback to a different worker/team/provider mode is a hard stop.

## Resume / Recovery Contract

- Checkpoint: <state file, Linear comment, or artifact that records last confirmed state>.
- Resume command: <exact command or dispatch step to resume from checkpoint>.
- Degraded recovery: if the worker has to recover missing prompt/body/provider state, mark the issue degraded and report what was recovered.
- Wakeups must rerun diagnostics before retrying the same failed action.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - <path>
complexity: medium
-->
