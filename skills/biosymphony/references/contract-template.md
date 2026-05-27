# BioSymphony Linear Contract Template

Every Symphony-dispatched issue should use this shape.

````markdown
## Summary

<One or two sentence scientific goal and artifact outcome.>

## Inputs

- `<input id>` - <source, local path, secure store reference, or database accession>

## Acceptance Criteria

- [ ] <Specific, testable assertion.>
- [ ] <Specific artifact assertion, e.g. final PNG exists, dimensions match, and file is nonblank.>
- [ ] <Specific provenance assertion, e.g. source, contour level, software version, or score field recorded.>

## Validation Commands

```bash
<exact command from repo root>
```

## Touched Areas

- `<path>` - <why this area is in scope>

## Dependencies

Blocked by: <issue-id>

## Risk Notes

- Do not store secrets, private structures, unpublished sequences, or raw private data in Linear.
- Record caveats for predicted structures, affinity estimates, generated designs, and rendering assumptions.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
touched_areas:
  - <path>
complexity: medium
-->
````

## Contract Rules

- `Acceptance Criteria` must be testable.
- `Validation Commands` must contain exact shell commands.
- `Touched Areas` must match the expected worker diff.
- `Dependencies` must match Linear blocker relations.
- The `symphony:schema` block must be present.
- Use `Backlog` for blocked downstream issues and activate only the first wave.
