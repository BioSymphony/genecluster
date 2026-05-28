# cblaster + clinker: integration plan for BioSymphony GeneCluster

**Status:** parked. Install path is current; atlas-quality output is blocked on GenBank input preparation. See `docs/biosymphony-tooling-status.md` for the re-entry recipe.
**Priority:** ★2
**Endorsed by:** BGC agent + reporting agent (cross-agent consensus)

## Purpose

`cblaster` (1.4, 2025-10-28, adds **ClusteredNR** support for `--mode remote --database nr_cluster_seq`, which can sidestep the GenBank-staging step entirely) takes a query enzyme set and finds clusters of co-located homologs across user-supplied genomes. local DIAMOND, remote NCBI BLAST, or remote ClusteredNR. `clinker` (0.0.32, 2025-12-22) draws publication-quality SVG synteny ribbons of those clusters with cluster-to-cluster orthology coloring. Together they close the cross-species cluster-homology gap directly: "given the Coptis BBE-NCS-CYP80 cluster, find homologous clusters in Houttuynia/Stephania/Phellodendron and draw the figure."

## What it would add to the BIA atlas specifically

Our current cross-species comparison (`data/pathway-species-catalog.tsv`) is a hand-written gradient table. cblaster + clinker would replace that with auto-generated SVG ribbons showing exactly which BIA cluster genes are conserved, lost, or duplicated across the campaign species set. This is the de-facto figure style in 2024-2026 plant 2°-met papers (Shan *Nat Commun* 2025, Sun *Sci Adv* 2024, Astilbe *Nat Commun* 2025).

## Install

```bash
# Both tools ship to PyPI; bioconda recipe also available
pip install "cblaster>=1.4.0" "clinker>=0.0.32"

# DIAMOND is needed for local searches (likely already installed)
conda install -c bioconda "diamond>=2.1"

# Verify
cblaster --version
clinker --version
```

## Sample CLI: running on our existing data

```bash
# 1. Build a local DIAMOND DB from each species' proteome
mkdir -p .runtime/cblaster-dbs
for sp in coptis-chinensis houttuynia-cordata stephania-tetrandra phellodendron-amurense; do
 cblaster makedb \
 .runtime/campaign-${sp}-summary/proteome.faa \
 .runtime/cblaster-dbs/${sp}.dmnd
done

# 2a. cblaster search using the BIA query set as cluster definition (local DIAMOND)
cblaster search \
 --query_file pipeline/genecluster_annotation_direct/queries-with-controls.faa \
 --mode local \
 --database .runtime/cblaster-dbs/*.dmnd \
 --max_distance 50000 \
 --min_hits 3 \
 --output .runtime/cblaster-out/bia-clusters.csv \
 --plot .runtime/cblaster-out/bia-clusters.html

# 2b. ALTERNATIVE: cblaster 1.4 remote ClusteredNR (no local GenBank prep)
# This is the new re-entry path for the parked-on-GFF-input blocker; trades
# a network round-trip for the GFF→GBK staging step.
cblaster search \
 --query_file pipeline/genecluster_annotation_direct/queries-with-controls.faa \
 --mode remote \
 --database nr_cluster_seq \
 --max_distance 50000 \
 --min_hits 3 \
 --output .runtime/cblaster-out/bia-clusters-cnr.csv \
 --plot .runtime/cblaster-out/bia-clusters-cnr.html

# 3. clinker on the cblaster-extracted GenBank slices
clinker .runtime/cblaster-out/clusters/*.gbk \
 --output_html .runtime/cblaster-out/clinker.html \
 --output_svg .runtime/cblaster-out/clinker.svg
```

## Integration point in our pipeline

- `pipeline/genecluster_annotation_direct/run.py`: optional new stage `cblaster_search` after the existing per-species cluster discovery.
- New helper: `pipeline/genecluster_annotation_direct/cblaster_join.py` to match cblaster cluster IDs onto our existing per-species cluster rows.
- `your downstream postprocess script`: embed clinker SVG link in the per-species xlsx `clusters-diamond` sheet.
- Quarto cross-species page (`bbe-gradient.qmd`): `<iframe>` the clinker HTML.

## Estimated integration cost

2-3 days focused.
- Day 1: Build per-species DIAMOND DBs and run a single cblaster search end-to-end.
- Day 2: Wire cblaster CSV into postprocess; embed clinker HTML/SVG paths in xlsx.
- Day 3: Cross-species figure styling + Quarto embed.

## Open questions / decisions to make before integrating

- `--max_distance 50000` matches our anchor-window definition, keep aligned, or experiment?
- `--min_hits 3` is the cblaster default; for BIA pathway clusters with only 2 enzymes, may need to drop to 2.
- Should we mirror MIBiG 4.0 as an additional cblaster DB target for ground-truth cross-checks?

## Citations

- cblaster 1.4.0: https://pypi.org/project/cblaster/ ; docs https://cblaster.readthedocs.io/
- cblaster paper: Gilchrist et al. *Bioinformatics Advances* 2021. https://academic.oup.com/bioinformaticsadvances/article/1/1/vbab016/6342405
- clinker 0.0.32: https://pypi.org/project/clinker/ ; GitHub https://github.com/gamcil/clinker
- clinker paper: Gilchrist & Chooi *Bioinformatics* 2021. https://academic.oup.com/bioinformatics/article/37/16/2473/6103786
- CAGECAT no-install web server: https://cagecat.bioinformatics.nl/
