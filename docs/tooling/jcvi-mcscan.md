# JCVI MCScan (Python): integration plan for BioSymphony GeneCluster

**Status:** validated; local-only install guidance refreshed recently.
**Priority:** ★3
**Endorsed by:** BGC + atlas-paper-styling tool surveys (cross-agent consensus; de-facto in 2024-2026 plant comparative-genomics papers)

## Purpose

The JCVI Python toolkit (Tang et al., iMeta 2024) ships an MCScan re-implementation that does pairwise and multi-species macro-synteny: chromosome-block ribbon diagrams that establish "species-A chrN ⇔ species-B chrM ⇔ species-C chrK" before zooming to individual clusters. It is the gold standard for plant comparative genomics and is the visualization most 2024-2026 reference papers use.

## What it adds to a comparative atlas

When a cross-species view jumps from per-species cluster lists straight to a hand-written gradient table, JCVI MCScan fills the missing layer: a chromosome-level ribbon plot showing which chromosomes are syntenic across species, with cluster coordinates overlaid. This is the figure style in Houttuynia 2024 *Hortic Res*, Astilbe 2025 *Nat Commun*, and Shan 2025 *Nat Commun*.

## Install

```bash
# JCVI is on PyPI and bioconda
pip install "jcvi>=1.6.5"

# Required external binaries
conda install -c bioconda last lastdb

# Optional graphics dep
brew install imagemagick # macOS
# apt-get install imagemagick # Linux

# Verify
python -m jcvi.compara.catalog --help
```

## Sample CLI: running on our existing data

```bash
# Pairwise synteny between Coptis and Stephania
mkdir -p .runtime/jcvi-synteny && cd .runtime/jcvi-synteny

# 1. Stage CDS + BED from each species
python -m jcvi.formats.gff bed --type=mRNA --key=ID \
 ../campaign-coptis-chinensis-summary/genome.gff > coptis.bed
python -m jcvi.formats.gff bed --type=mRNA --key=ID \
 ../campaign-stephania-tetrandra-summary/genome.gff > stephania.bed

# 2. Pairwise LAST + MCscan
python -m jcvi.compara.catalog ortholog coptis stephania --no_strip_names

# 3. Synteny ribbon plot
python -m jcvi.graphics.synteny seqids.txt layout.txt \
 --outfile coptis-vs-stephania-synteny.pdf
```

## Integration point in our pipeline

- New helper: ``pipeline/genecluster_annotation_direct/`` orchestrating the multi-species pairwise sweep.
- Output: `.runtime/jcvi-synteny/<sp1>-vs-<sp2>.{anchors,pdf,svg}`.
- Postprocess: `your downstream postprocess script` adds a `synteny-blocks` sheet pointing to the relevant SVG/PDF and listing macro-synteny anchor counts.
- Quarto: `cross-species/synteny-blocks.qmd` embeds the SVG.

## Estimated integration cost

3-4 days focused.
- Day 1: GFF→BED conversion for all campaign species; one pairwise run end-to-end.
- Day 2: All 6 pairwise combinations + multi-species karyotype plot.
- Day 3: Wire anchor counts into postprocess xlsx.
- Day 4: Quarto embed + Astilbe-style variable-cardinality synteny table.

## Open questions / decisions to make before integrating

- 4 species → 6 pairwise comparisons; do we present all 6 or just the 3 anchored on Coptis?
- Layout: linear ribbon (MCScan default) vs Circos (Houttuynia Fig 4 style) vs both?
- Houttuynia is decaploid (AAAAABBBBB), do we phase subgenomes before synteny, or use the assembly as-is?

## Citations

- JCVI iMeta 2024: https://onlinelibrary.wiley.com/doi/10.1002/imt2.211
- GitHub: https://github.com/tanghaibao/jcvi
- MCscan Python wiki: https://github.com/tanghaibao/jcvi/wiki/MCscan-(Python-version)
- PyPI: https://pypi.org/project/jcvi/
