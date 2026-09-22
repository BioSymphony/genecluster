# Skills

Use `biosymphony` to coordinate a campaign and `genecluster-superpowers` to add a supported tool.

| Skill | Purpose | Entry point |
|---|---|---|
| `biosymphony` | Plan the analysis, track inputs, select a route, validate outputs, and assemble reports | [Campaign instructions](biosymphony/SKILL.md) |
| `genecluster-superpowers` | Find tool quickstarts and wrappers for searches, annotation, comparisons, and reporting | [Tool instructions](genecluster-superpowers/SKILL.md) |

## Check Local Availability

From the repository root, inspect campaign capabilities:

```bash
python3 skills/biosymphony/scripts/capability_probe.py --json
```

Check commands used by the tool wrappers:

```bash
bash skills/genecluster-superpowers/scripts/superpowers-status.sh
```

These checks report local availability. Use [tooling status](../docs/biosymphony-tooling-status.md) to check versions, tested baselines, and integration limits.

## Select a Tool

Read the relevant [tool guide](../docs/tooling/README.md) before running a wrapper. Each guide describes required inputs and setup; installing a command does not validate its campaign output.

For a proposed addition, use the [tool evaluation contract](../docs/tooling/tool-evaluation.md). For a new campaign, use the [goal prompt](../templates/goal-prompt.md).
