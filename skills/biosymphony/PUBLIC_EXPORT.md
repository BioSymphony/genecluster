# Publication boundary

The public skill contains reusable contracts, validators, public or synthetic examples, and provider-neutral guidance.

## Allowed

- public and synthetic fixtures;
- schemas, templates, validators, and compact example outputs;
- stable public accessions and citations;
- placeholder paths and credential variable names;
- summary-only provenance with no provider or account identifiers.

## Excluded

- credentials, signed URLs, account or provider identifiers;
- local workstation paths and private tracker content;
- raw or heavy biological data, databases, indexes, models, and run logs;
- unpublished sequences, structures, or collaborator-restricted data;
- generated runtime state and provider response payloads.

## Check

Run the public skill audit before publication:

```bash
python3 skills/biosymphony/scripts/biosymphony_public_skill_audit.py \
  --skill-root skills/biosymphony
```

The audit is a targeted guardrail. It does not replace review or a dedicated secret scan.
