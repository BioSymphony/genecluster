# JCVI MCScan (Python): quickstart

**Status:** ✅ **VALIDATED**. Thousands of pairwise anchors returned between two public plant species; dotplot PDF at `.runtime/<atlas>-quarto-preview/figures/jcvi/` (atlas chapter). NGDC-GFF parser fallback required for any genome submitted via NGDC GWH. See [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md) for full inventory.
**Install (local-only, not canonical):** `pip install "jcvi>=1.6.5"` plus `conda install -c bioconda last`. Canonical dispatch path is a CPU pod via the `genecluster-superpowers` image.

## Sample run on atlas data

```bash
# Pairwise synteny ribbons between Coptis and Stephania
mkdir -p .runtime/jcvi-synteny/coptis-vs-stephania
cd .runtime/jcvi-synteny/coptis-vs-stephania

# 1. Convert each species' GFF to JCVI BED
python3 -m jcvi.formats.gff bed --type=mRNA --key=ID \
 ../../../.runtime/<species>-summary/genomic.gff -o coptis.bed
python3 -m jcvi.formats.gff bed --type=mRNA --key=ID \
 ../../../.runtime/<species>-summary/genomic.gff -o stephania.bed

# 2. Stage CDS: extract from proteome+GFF or use the .cds file if shipped
ln -sf ../../../.runtime/<species>-summary/proteome.faa coptis.cds
ln -sf ../../../.runtime/<species>-summary/proteome.faa stephania.cds

# 3. Pairwise LAST + MCScan ortholog catalog
python3 -m jcvi.compara.catalog ortholog coptis stephania --no_strip_names

# 4. Synteny ribbon plot (seqids.txt + layout.txt are hand-edited per-pair)
python3 -m jcvi.graphics.synteny seqids.txt layout.txt \
 --outfile coptis-vs-stephania-synteny.pdf
```

Or use the wrapper: `skills/genecluster-superpowers/scripts/run-jcvi-mcscan.sh coptis stephania`.

## Integration in our pipeline

Output is the chromosome-level macro-synteny backbone (e.g., "<species-A> chrN ⇔ <species-B> chrM ⇔ <species-C> chrK") before zooming to specific BIA clusters. Embeds into `cross-species/synteny-blocks.qmd`. Anchor counts join into a new `synteny-blocks` sheet on each per-species xlsx via the planned ``pipeline/genecluster_annotation_direct/``. This is the figure style in Houttuynia 2024 *Hortic Res* and Astilbe 2025 *Nat Commun*.

## Open questions

- N species → N·(N-1)/2 pairwise comparisons: present all of them, or just the ones anchored on the comparator of interest?
- Ribbon (linear, MCScan default) vs Circos (Houttuynia Fig 4 style)?
- For decaploids like Houttuynia (AAAAABBBBB), phase subgenomes first or run on the assembly as-is?

## See also

- `docs/tooling/jcvi-mcscan.md`, full integration plan + cost
- `docs/biosymphony-genecluster-superpower-roadmap.md`, Priority ★3, BGC + atlas-styling consensus (de-facto)
- `tools/recommended/jcvi-mcscan/pairwise-synteny.sh.template`, original placeholder
