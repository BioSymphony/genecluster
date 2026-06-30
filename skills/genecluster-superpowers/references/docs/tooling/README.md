# BioSymphony GeneCluster: tooling integration index

**Status:** mirror of the canonical inventory plus an unvalidated radar. The original integration plans are still useful for install shape and sample CLI, but the actual validated state lives in [`../biosymphony-tooling-status.md`](../biosymphony-tooling-status.md): 25 validated, 3 parked, 8 shelved-untested, 2 gated. The expansive next-candidate pass lives in [`../biosymphony-next-tooling-radar.md`](../biosymphony-next-tooling-radar.md), including the June 2026 additions for BGC workflows, metabolomics context, pangenomes, and review interfaces.

This directory captures the integration plan for the recommended tool stack identified by the superpower-discovery survey. The authoritative ranking and rationale live in [`../biosymphony-genecluster-superpower-roadmap.md`](../biosymphony-genecluster-superpower-roadmap.md).

## Status table

| Tool | Priority | Tier | Current status | Endorsed by | Doc |
|---|---|---|---|---|---|
| plantiSMASH 2.0.4 | ★1 | medium-add | validated via BioSymphony v7 boot recipe | BGC + enzyme-function agents | [plantismash.md](plantismash.md) |
| cblaster + clinker | ★2 | cheap-add | parked; install OK, needs GenBank input path | BGC + reporting agents | [cblaster-clinker.md](cblaster-clinker.md) |
| JCVI MCScan (Python) | ★3 | cheap-add | validated on RunPod | BGC + atlas-styling agents | [jcvi-mcscan.md](jcvi-mcscan.md) |
| Foldseek + ProstT5 | ★4 | cross-species evidence layer | validated on RunPod | sequence/structure agent (solo) | [foldseek-prostt5.md](foldseek-prostt5.md) |
| MMseqs2 iterative |, | cheap-add | validated on RunPod | sequence/structure agent (solo) | [mmseqs2.md](mmseqs2.md) |
| CLEAN / HIT-EC | ★ | cheap-add | parked; CLEAN wrapper brittle, DeepEC/ECPred is validated fallback | enzyme-function agent (solo, high-confidence) | [clean-hit-ec.md](clean-hit-ec.md) |
| PlantCyc PMN 16 + P450Rdb |, | cheap-add (DB-only) | PlantCyc gated; P450Rdb validated | enzyme-function agent (solo) | [plantcyc-p450rdb.md](plantcyc-p450rdb.md) |
| Cytoscape.js 3.33.3 |, | cheap-add | adopted in atlas viewer snippets | reporting agent (solo) | [cytoscape-js.md](cytoscape-js.md) |
| Quarto 1.9.37 | ★5 | blessed report spine | adopted | reporting agent (solo, high-confidence) | [quarto.md](quarto.md) |
| Proto |, | design-layer candidate | track for next-experiment design and sequence-optimization flow | design / model-routing agent | [proto.md](proto.md) |

## How to read these docs

Each per-tool doc follows a consistent template:
1. What it does and why we want it.
2. What it would add to the BIA atlas specifically.
3. Install commands (macOS / Linux, version-pinned where stable).
4. Sample CLI on derived atlas data. The public snapshot intentionally omits `.runtime/`; use a local path such as `ATLAS_SUMMARY_DIR=/path/to/your/summary`.
5. Where the output would feed in (`pipeline/genecluster_annotation_direct/run.py`, postprocess scripts, dispatch).
6. Estimated integration cost.
7. Open questions to settle before integrating.
8. Citations.

## Companion install scripts

`tools/recommended/` holds idempotent install shell scripts split into three tiers:

- `install-cheap.sh`, `pip` + `conda` only: cblaster, clinker, JCVI, MMseqs2, igv-reports, Quarto.
- `install-medium.sh`, heavier conda envs / downloads: plantiSMASH 2.0.4 source install, MIBiG download.
- `install-heavy.sh`, GPU + large model downloads: Foldseek + ProstT5, CLEAN-Contact, AFDB-Plants.

Each subdirectory under `tools/recommended/<tool>/` carries a `*.sh.template` stub showing the eventual CLI invocation. Templates are intentionally not executable, they are foundation only.

## When to actually integrate

Default trigger: a campaign produces an output that the existing pipeline cannot explain (twilight-zone homologs, missing cluster signal, novel-EC requests) and the relevant tool is the cheapest fix on the table. At that point, start from the status in `docs/biosymphony-tooling-status.md`: adopted tools can be reused, parked tools need their re-entry recipe, and newer upstream releases need a smoke test before replacing a validated pin.

Use Proto after BioSymphony has a reviewed candidate map. It is a design-program layer for ranked sequence and construct candidates.
