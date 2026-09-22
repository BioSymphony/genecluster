---
name: genecluster-superpowers
description: Use when extending BioSymphony GeneCluster with public-safe sequence or structure search, BGC detection, synteny, function prediction, reference databases, visualization, or report rendering.
---

# GeneCluster Superpowers

This skill provides quickstarts and wrappers for a subset of the public GeneCluster tool inventory. Use the [tooling status](references/docs/biosymphony-tooling-status.md) as the canonical source for upstream versions, checked baselines, and integration limits.

## When to use it

Use this skill when a campaign needs one of these bounded capabilities:

- sequence or profile search;
- structure search or representation;
- BGC calling and cluster comparison;
- synteny and genome-context visualization;
- enzyme-function evidence;
- pathway or reference-database context;
- interactive review views;
- report rendering.

Use the main `biosymphony` skill for campaign planning, ledgers, routes, claim checks, and provider-neutral handoffs.

## Status terms

- **Available**: public installation or access is documented.
- **Checked baseline**: a public fixture previously produced the expected output shape.
- **Adopted**: a repository contract or wrapper consumes that checked shape.
- **Planned**: relevant, but no public integration claim is made.
- **Gated**: licensing, access, redistribution, or resource requirements limit a public integration.

A newer upstream release does not replace a checked baseline until a public fixture confirms compatibility.

## Packaged subset

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

## Check local availability

```bash
bash scripts/superpowers-status.sh
```

This reports local commands only. It does not change tool status or prove that a campaign integration is complete.

## Optional installers

The mirrored helpers under `tools/recommended/` are opt-in references:

```bash
bash tools/recommended/install-cheap.sh
bash tools/recommended/install-medium.sh
bash tools/recommended/install-heavy.sh
```

Inspect each script before use. Supply reviewed immutable revisions and published checksums where requested. Heavy databases and model caches belong in ignored runtime storage or an external work directory.

## Wrapper examples

```bash
bash scripts/run-cblaster.sh <species>
bash scripts/run-jcvi-mcscan.sh <species-a> <species-b>
bash scripts/run-mmseqs2.sh <species>
bash scripts/run-foldseek-prostt5.sh <species>
```

Wrappers expect campaign-derived inputs under ignored runtime storage. They must fail clearly when a tool or required input is missing.

## Adding a tool

1. Link the official release and license source.
2. Add a public or synthetic fixture.
3. Record exact code, model, and database versions.
4. Define compact inputs, outputs, failure states, and hashes.
5. Keep raw and heavy artifacts outside the repository.
6. Add or update the per-tool guide and wrapper.
7. Promote the status only after the public fixture passes.
8. Update the packaged documentation mirror.

Do not include credentials, private paths, provider payloads, unpublished data, private tracker text, or unpublished run history in public documentation.

## References

- [Canonical tooling status](references/docs/biosymphony-tooling-status.md)
- [Per-tool guides](references/docs/tooling/README.md)
- [Tool roadmap](references/docs/biosymphony-genecluster-superpower-roadmap.md)
- [Atlas authoring guidance](references/docs/biosymphony-atlas-best-practices.md)
