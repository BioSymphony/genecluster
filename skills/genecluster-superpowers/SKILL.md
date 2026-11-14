---
name: genecluster-superpowers
description: Choose and call bioinformatics tools, prepare their inputs, and chain sequence search, annotation, genome-context analysis, visualization, and reports.
---

# GeneCluster Superpowers

Use this skill to choose tools, run them, and connect their outputs.

1. Check data, database, version, and compute requirements in the [tool knowledge base](references/docs/tooling/README.md).
2. Run `bash scripts/superpowers-status.sh` from this skill directory. Use the [calling guide](references/docs/tooling/tool-chaining.md) to choose a native command or wrapper.
3. Give each run explicit inputs and a fresh output directory. Check its exit status, output columns, and identifiers.
4. Prepare the next input by extracting sequences, converting formats, or joining tables by gene or protein ID. Record commands, source accessions, and database versions.

## Calling Helpers

These commands show the required flags without invoking the tools:

```bash
bash scripts/run-mmseqs2.sh --help
bash scripts/run-cblaster.sh --help
```

MMseqs2 and cblaster have synthetic smoke checks and CLI regression tests. The [readiness table](references/docs/tooling/tool-chaining.md#choose-a-tool) lists the drafts that need adaptation.

## Versions And Installation

[Tooling status](references/docs/biosymphony-tooling-status.md) records upstream releases and tested versions. Find installers and templates under `tools/recommended/`. Use published checksums for downloaded packages.

## Longer Analyses

Use the [campaign helpers](https://github.com/BioSymphony/genecluster/blob/main/skills/biosymphony/SKILL.md) for input tracking and resumable stages.

## Add a Tool

Link official sources, define inputs and outputs, and add a public or synthetic fixture. Record code, model, and database versions. Promote integration status after the fixture passes, then update the guide and packaged documentation mirror.
