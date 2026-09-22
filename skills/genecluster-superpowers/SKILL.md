---
name: genecluster-superpowers
description: Choose and call bioinformatics tools, prepare their inputs, and chain sequence search, annotation, genome-context analysis, visualization, and reports.
---

# GeneCluster Superpowers

Use this skill to select tools for genome and transcriptome analysis, call them through command-line or Python interfaces, and connect their outputs. Start with the biological question and available data.

## Select, Call, and Connect

1. Read the relevant guide in the [tool knowledge base](references/docs/tooling/README.md). Check required data, databases, versions, and compute.
2. Inspect local availability with `bash scripts/superpowers-status.sh` from this skill directory.
3. Read the [calling guide](references/docs/tooling/tool-chaining.md) for wrapper readiness. Use an installed tool's native CLI when a wrapper needs adaptation.
4. Prepare explicit inputs and a separate output directory. Run the approved analysis and inspect errors, output columns, and empty results.
5. Prepare the next input: extract sequences, convert formats, or join stable gene and protein IDs. Retain the commands and source references with the results.

For example, chain MMseqs2 hits, matched protein sequences, HMMER or InterProScan annotations, and a Quarto report. For cluster comparisons, the cblaster wrapper chains a search session, GenBank extraction, and clinker. The agent handles any conversions between independent tools.

## Calling Helpers

These commands show the required flags without invoking the tools:

```bash
bash scripts/run-mmseqs2.sh --help
bash scripts/run-cblaster.sh --help
```

Both wrappers have fake-CLI regression tests. Foldseek/ProstT5, JCVI, plantiSMASH, and CLEAN wrappers are adaptation templates; review the [readiness table](references/docs/tooling/tool-chaining.md#choose-a-tool) before use.

## Tool Knowledge Base

| Tool | Public status | Guide |
|---|---|---|
| Quarto | Checked baseline 1.9.37; upstream 1.10.18 | [Quickstart](references/quarto-quickstart.md) |
| plantiSMASH | Checked baseline 2.0.4 | [Quickstart](references/plantismash-quickstart.md) |
| antiSMASH | Checked baseline 8.0.4 | [Guide](references/docs/biosymphony-antismash-cookbook.md) |
| JCVI MCScan | Available; minimum 1.6.5, upstream 1.6.7 | [Quickstart](references/jcvi-mcscan-quickstart.md) |
| MMseqs2 | Checked baseline 18 | [Quickstart](references/mmseqs2-quickstart.md) |
| Foldseek + ProstT5 | Checked baseline | [Quickstart](references/foldseek-prostt5-quickstart.md) |
| cblaster + clinker | Available; wrapper fixture planned | [Quickstart](references/cblaster-quickstart.md) |
| CLEAN + HIT-EC | Planned | [Quickstart](references/clean-hit-ec-quickstart.md) |
| Cytoscape.js | Checked baseline 3.33.3; upstream 3.34.3 | [Snippet](references/cytoscape-js-snippet.md) |
| Plant Metabolic Network | Gated by provider terms | [Quickstart](references/plantcyc-p450rdb-quickstart.md) |
| ESM-C 6B | Gated by model access and compute requirements | [Status](references/docs/biosymphony-tooling-status.md) |

The canonical inventory includes additional tools and explains the evidence behind each status.

## Versions and Installation

[Tooling status](references/docs/biosymphony-tooling-status.md) records checked baselines, upstream releases, and integration limits. Local command availability does not change those statuses. A tool baseline does not validate every wrapper or a later release.

The opt-in installers under `tools/recommended/` group smaller tools, medium downloads, and model/database setup. Inspect each script and supply the requested immutable revisions and checksums. Store large data and model caches in ignored runtime storage or an external work directory.

## Longer Analyses

The [campaign helpers](https://github.com/BioSymphony/genecluster/blob/main/skills/biosymphony/SKILL.md) add input tracking and resumable stages. Use them when the analysis needs those features; a tracker is optional.

## Add a Tool

Link official sources, define inputs and outputs, and add a public or synthetic fixture. Record code, model, and database versions. Promote integration status after the fixture passes, then update the guide and packaged documentation mirror.

Keep credentials, private paths, unpublished data, and private run history out of public materials.
