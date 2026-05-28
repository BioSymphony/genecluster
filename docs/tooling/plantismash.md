# plantiSMASH 2.0.4: integration plan for BioSymphony GeneCluster

**Status:** validated on RunPod at upstream 2.0.4 via the BioSymphony v7 boot recipe. This document started as the original integration plan; current status is mirrored from `docs/biosymphony-tooling-status.md`.
**Priority:** ★1 (top-ranked quick win)
**Endorsed by:** BGC agent + enzyme-function agent (cross-agent consensus)

## Purpose

plantiSMASH is the plant-specific fork of antiSMASH. Version 2.0.4 is the current upstream release as of the upstream-freshness audit. It adds motif-driven detection rules for plant BGCs, including alkaloid, terpene, and saccharide clusters, and ships precomputed clusters for 30,423 plant BGCs across 430 plant genomes (Coptis is in the corpus). It catches clusters our anchor-driven 50 kb sliding window misses entirely.

BioSymphony note: older docs said "plantiSMASH v7." That was not an upstream release. It was the seventh RunPod boot iteration that made upstream 2.0.4 run end-to-end by avoiding the `straight.plugin` editable-install failure mode.

## What it would add to the BIA atlas specifically

Today GeneCluster only produces a cluster window when at least one canonical BIA query (BBE, NCS, CYP80, CYP719, etc.) hits within 50 kb. Any BIA cluster whose only members are uncharacterized P450s or methyltransferases is invisible to us. plantiSMASH would catch those, and would also let us cross-reference Coptis chinensis hits against the precomputed plant-BGC database, validating our calls and surfacing clusters in Houttuynia / Stephania / Phellodendron that have no canonical anchor at all.

## Install

```bash
# Source clone with conda env. Do not use editable pip install; it can leave
# straight.plugin with an empty plugin list.
git clone --branch plantismash-2.0.4 https://github.com/plantismash/plantismash.git
cd plantismash
mamba env create -n plantismash -f environment.yml
conda activate plantismash
python -m pip install .
python -c "from straight.plugin import load; assert list(load('antismash.specific_modules'))"
```

## Sample CLI: running on our existing data

```bash
# Stephania tetrandra genome input (already in .runtime/)
conda run -n plantismash plantismash \
 --taxon plants \
 --genefinding-tool none \
 --outputfolder .runtime/<species>-summary/superpowers/plantismash \
 .runtime/<species>-summary/genomic.gff
```

## Integration point in our pipeline

`pipeline/genecluster_annotation_direct/run.py` after the existing cluster-window detection:

1. New stage: feed each species genome FASTA + GFF to plantiSMASH.
2. Parse `clusters.json` → join with our anchor-driven clusters by genomic coordinate overlap.
3. New columns in postprocess xlsx (`your downstream postprocess script`): `plantismash_cluster_id`, `plantismash_type`, `plantismash_substrate_prediction`.
4. Cross-species comparison: clusters detected by plantiSMASH only (no canonical anchor) become a new sheet `plantismash-only-clusters`.

## Estimated integration cost

Validated for the campaign atlas. Re-entry cost for a new species is now the source-install smoke test plus coordinate-overlap review, not a fresh integration effort.

## Open questions / decisions to make before integrating

- Do we run plantiSMASH on all new species by default, or only when anchor-windowing leaves unexplained cluster gaps?
- Disk: 30,423 precomputed BGCs, do we mirror the full DB locally or query the web service per cluster?
- Coordinate-overlap join policy: union, intersection, or label-only?
- Anchor-only-clusters vs plantiSMASH-only-clusters vs both, which gets the headline panel?

## Citations

- plantiSMASH 2.0 bioRxiv 2025: https://www.biorxiv.org/content/10.1101/2025.10.28.683968v1
- plantiSMASH 2.0 ScienceDirect 2026: https://www.sciencedirect.com/science/article/abs/pii/S0022283626001713
- GitHub: https://github.com/plantismash/plantismash
- Documentation: https://plantismash.github.io/documentation/install/
