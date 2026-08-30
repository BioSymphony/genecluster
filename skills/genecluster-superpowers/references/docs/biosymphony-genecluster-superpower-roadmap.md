# GeneCluster tooling roadmap

Last reviewed: 2026-08-30

This roadmap describes public integration work. Current versions and evidence levels live in the [tooling status](biosymphony-tooling-status.md).

## Current foundation

The repository already documents or packages representative tools for:

- BGC calling: antiSMASH, plantiSMASH, DeepBGC;
- search: MMseqs2, cblaster, Foldseek, HMMER;
- comparison: clinker and JCVI MCScan;
- function evidence: InterProScan, DeepEC/ECPred, CLEAN/HIT-EC planning;
- review: igv-reports, Cytoscape.js, Quarto;
- reference data: MIBiG, Pfam, PMN access guidance.

Not every inventory entry has a runner. The packaged skill identifies the supported subset.

## Next public milestones

### 1. Versioned public fixtures

Add small public or synthetic fixtures for each wrapper. Record the command, version, output schema, expected failure behavior, and output hash.

### 2. BGC comparison packet

Join BGC calls, cblaster results, clinker plots, and neighborhood tables through stable cluster identifiers. Preserve caller-specific evidence rather than collapsing disagreements.

### 3. Synteny packet

Add a JCVI fixture with normalized feature identifiers, assembly-quality notes, anchors, plot output, and claim limits.

### 4. Function-evidence packet

Define a compact schema for sequence similarity, domains, structure, EC prediction, confidence, and abstention. Keep each evidence channel visible.

### 5. Report fixture

Render one public campaign packet with the checked Quarto baseline and an exact Cytoscape.js version. Include static fallbacks and accessible figure descriptions.

### 6. Release automation

Check documentation mirrors, local/private paths, credential patterns, generated runtime artifacts, large biological files, and wrapper syntax before publication.

## Promotion rule

A tool moves from planned or available to checked only when the repository contains:

- a public or synthetic fixture;
- a repeatable command;
- exact code, model, and database versions;
- a documented output contract;
- expected resource limits;
- license and redistribution notes;
- compact checked outputs or hashes.

Upstream popularity or an unpublished test is not enough for a public integration claim.
