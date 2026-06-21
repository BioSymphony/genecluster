# Skills

Two canonical skills live here:

## 1. `biosymphony/`: campaign orchestration

```text
skills/biosymphony/
 SKILL.md
 references/
 capability-matrix.md
 contract-template.md
 figure-manifest.schema.json
 scripts/
 capability_probe.py
 preflight_check.py
 figure_manifest_check.py
```

Routes comparative-genomics atlas campaigns through task contracts, source/query ledgers, route scouting, candidate search, function scoring, checks, and provenance. Structural-biology helpers remain sibling capabilities, but this public snapshot leads with GeneCluster.

The repo-local discovery shim at `.codex/skills/biosymphony/SKILL.md` points future Codex/Symphony workers back to this canonical source.

Run these from the repo root:

```bash
python3 skills/biosymphony/scripts/capability_probe.py --json
python3 skills/biosymphony/scripts/preflight_check.py path/to/issue.md
python3 skills/biosymphony/scripts/figure_manifest_check.py figure-dossier/figure_manifest.json
```

## 2. `genecluster-superpowers/`: recommended-tool kit

```text
skills/genecluster-superpowers/
 SKILL.md
 references/
 {tool}-quickstart.md (9 docs, terse install + sample-run + integration)
 scripts/
 superpowers-status.sh (which recommended tools are installed)
 run-{tool}.sh (canonical invocation against atlas data, 6 wrappers)
```

Packages the recommended-tool survey plus upstream freshness notes as ready-to-invoke shortcuts. Current state: **Quarto**, **plantiSMASH 2.0.4 via BioSymphony v7 boot**, **JCVI MCScan**, **MMseqs2**, **Foldseek+ProstT5**, **P450Rdb**, and **Cytoscape.js** are adopted or checked; **cblaster + clinker**, **CLEAN/HIT-EC**, and **HHsuite** are parked with re-entry recipes; **PlantCyc PMN 16** is gated.

Status check:

```bash
bash skills/genecluster-superpowers/scripts/superpowers-status.sh
```

Sample invocation (each runner takes a species shorthand as `$1`):

```bash
bash skills/genecluster-superpowers/scripts/run-cblaster.sh phellodendron
bash skills/genecluster-superpowers/scripts/run-jcvi-mcscan.sh coptis phellodendron
bash skills/genecluster-superpowers/scripts/run-foldseek-prostt5.sh coptis
```

If the underlying tool is not installed, each runner exits cleanly with the install command.

See:
- Recommended-tool roadmap: `docs/biosymphony-genecluster-superpower-roadmap.md`
- Per-tool integration plans: `docs/tooling/<tool>.md`
- Atlas authoring best practices: `docs/README.md`
