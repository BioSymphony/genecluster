# Tooling status and version watch

Last reviewed: 2026-08-30

This page records public upstream versions, the baselines represented by this repository, and the level of public integration evidence. It is a knowledge base, not a live service-status page.

## Status terms

- **Available**: the tool is public and has a documented installation or access route.
- **Checked baseline**: a public fixture and repeatable command have previously produced the expected output shape. This documentation review did not rerun those tools.
- **Adopted**: repository contracts or runners consume that checked output shape.
- **Planned**: the tool is relevant, but this repository does not yet make an integration claim.
- **Gated**: access, licensing, redistribution, or resource requirements prevent a fully public integration.

A newer upstream release does not automatically replace a checked baseline. Promote a version only after a public fixture and output-contract check.

## Version watch

| Tool | Current upstream | Public baseline in this repo | Status | Note |
|---|---:|---:|---|---|
| antiSMASH | 8.0.4 | 8.0.4 | Checked baseline | Bacterial and fungal BGC calling |
| plantiSMASH | 2.0.4 | 2.0.4 | Checked baseline | Plant BGC calling; non-editable source installation |
| DeepBGC | 0.1.31 | 0.1.31 | Checked baseline | ML-based BGC scoring |
| cblaster | 1.4.2 | >=1.4.0 | Available | Recheck the packaged minimum against 1.4.2 before promoting |
| clinker | 0.0.32 | >=0.0.32 | Available | HTML plot output uses `--plot <path>` |
| JCVI | 1.6.6 | >=1.6.5 | Available | MCScan synteny workflow |
| MMseqs2 | 18-8cc5c | 18 | Checked baseline | Large protein search |
| Foldseek | 10-941cd33 | 10 | Checked baseline | Structure search |
| MIBiG | 4.0 | 4.0 | Available | Curated BGC reference data |
| igv-reports | 1.16.3 | >=1.16.2 | Available | Static genome review reports |
| Cytoscape.js | 3.34.2 | 3.33.3 | Checked baseline | Recheck before updating the vendored/CDN baseline |
| Quarto | 1.10.18 | 1.9.37 | Checked baseline | 1.11 is prerelease; recheck manuscript output before promoting |
| InterProScan | 5.78-109.0 | 5.x | Available | Current release bundles Pfam 38.2 |
| Pfam | 38.2 | 37.x | Available | Update dependent database manifests together |
| Plant Metabolic Network | 17.0 | access by provider terms | Gated | Do not redistribute provider data |
| HIT-EC | public repository | none | Planned | Public source exists; no public fixture is committed here |
| ESM-C 6B | provider/model terms | none | Gated | Large-model access and compute requirements |

Sources: [antiSMASH releases](https://github.com/antismash/antismash/releases), [plantiSMASH releases](https://github.com/plantismash/plantismash/releases), [cblaster on PyPI](https://pypi.org/project/cblaster/), [clinker](https://github.com/gamcil/clinker), [JCVI on PyPI](https://pypi.org/project/jcvi/), [MMseqs2 releases](https://github.com/soedinglab/MMseqs2/releases), [Foldseek releases](https://github.com/steineggerlab/foldseek/releases), [igv-reports on PyPI](https://pypi.org/project/igv-reports/), [Cytoscape.js](https://www.npmjs.com/package/cytoscape), [Quarto releases](https://github.com/quarto-dev/quarto-cli/releases), [InterProScan release notes](https://interproscan-docs.readthedocs.io/en/v5/ReleaseNotes.html), and [PMN 17](https://plantcyc.org/pmn-17-released/).

## Adopted capability groups

The public contracts cover these capability groups:

- source and accession scouting;
- sequence and profile search;
- BGC calling and comparison;
- domain and function annotation;
- structure search and representation;
- synteny and genome-context review;
- report and visualization generation.

An adopted group may have more tools in the inventory than packaged runners. The [per-tool guides](tooling/README.md) identify the subset with public quickstarts or wrappers.

## Planned or gated integrations

- **cblaster + clinker**: available upstream; the local-genome route needs GenBank inputs and a public end-to-end fixture.
- **CLEAN + HIT-EC**: public sources are available; the combined output contract still needs a public fixture.
- **Large structure/model lanes**: database size, model terms, and compute requirements must be recorded before adoption.
- **PMN data**: access and redistribution remain governed by the provider’s current terms.

## Maintenance rule

For each version change:

1. link the upstream release source;
2. run a public or synthetic fixture;
3. record the command, version, output shape, and hash;
4. update the relevant quickstart and wrapper;
5. update the packaged documentation mirror;
6. avoid claims that depend on private infrastructure or unpublished data.
