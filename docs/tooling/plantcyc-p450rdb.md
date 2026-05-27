# PlantCyc PMN 16 + P450Rdb: integration plan for BioSymphony GeneCluster

**Status:** split: PlantCyc / PMN 16 remains gated on academic license approval; P450Rdb is validated on RunPod during validation testing.
**Priority:** cheap-add (database-only, no compute)
**Endorsed by:** enzyme-function agent

## Purpose

PlantCyc / PMN 16 (NAR 2025) is the canonical plant metabolic-pathway database: 155 species, 1,200 pathways, 1.3M enzymes, 8,000 metabolites, 10,000 reactions, 15,000 citations. It contains explicit BIA pathway models for Papaver and Coptis-relatives, providing the ground truth the atlas should be benchmarked against. P450Rdb (Database 2023, Wang et al.) hand-curates 1,600 reactions across 590 P450s in 200 species, the exact reference set for our CYP71B / CYP80 / CYP719 anchors.

> **Availability flag:** the SNU host (`p450.riceblast.snu.ac.kr`) returned a TCP timeout from one of the audit agents. May be transient. but if a re-run needs the FASTA, mirror the validated copy on the campaign RunPod volume rather than fetching live.

## What it would add to the BIA atlas specifically

Two things the atlas currently lacks:

1. **Pathway-completion benchmark**: "Coptis chinensis BIA pathway: 11 of 13 canonical PlantCyc enzymes detected in our pipeline." This converts the loose narrative into a quantitative completeness panel comparable across species (Astilbe-style variable-cardinality table).
2. **P450 reference anchor lookup**: instead of `BLAST → SwissProt → "uncharacterized P450 73E2-like"`, P450Rdb gives us `BLAST → P450Rdb → "CYP719A1, scoulerine 9-O-methyltransferase, validated in Coptis japonica"`.

## Install

```bash
# PlantCyc PMN 16: license-walled but free; submit license form, receive download instructions ~1 business day
# Manual step: https://plantcyc.org/downloads/license-agreement
# Once approved, download flat-file release (~5 GB) and unpack:
PMN_DIR="$(pwd)/.runtime/databases/pmn-16"
mkdir -p "$PMN_DIR"
# tar xvzf pmn-16-release-flatfiles.tar.gz -C "$PMN_DIR"

# P450Rdb: download from publication supplementary or maintainer's site
# Database 2023, PMID 37871773
P450_DIR="$(pwd)/.runtime/databases/p450rdb"
mkdir -p "$P450_DIR"
# wget -O "$P450_DIR/p450rdb.tsv" <maintainer URL or paper supplementary>

# Verify
ls -la "$PMN_DIR"/*.dat "$P450_DIR"/*.tsv
```

## Sample CLI: running on our existing data

```bash
# 1. Build a DIAMOND DB from PMN 16 enzyme sequences
diamond makedb --in .runtime/databases/pmn-16/all_enzymes.faa \
 --db .runtime/databases/pmn-16/pmn16-enzymes.dmnd

# 2. Map our cluster candidates against PMN to get pathway-step assignments
diamond blastp \
 --query .runtime/<species>-summary/cluster-candidates.faa \
 --db .runtime/databases/pmn-16/pmn16-enzymes.dmnd \
 --outfmt 6 qseqid sseqid pident evalue stitle \
 --out .runtime/pmn-pathway-coverage/coptis-vs-pmn.tsv \
 --max-target-seqs 5 --evalue 1e-20

# 3. Annotate our P450 candidates against P450Rdb
# (P450Rdb is a curated TSV; join on closest BLAST hit)
```

## Integration point in our pipeline

- New helper: ``pipeline/genecluster_annotation_direct/``, joins cluster candidates to PMN 16 pathway step IDs.
- New helper: `pipeline/genecluster_annotation_direct/enrichment/p450rdb_anchor.py`, annotates our P450 hits with P450Rdb reaction labels.
- Postprocess: new column `pmn_pathway_step` on `top-hits` and `clusters-diamond` sheets; new sheet `pathway-coverage` listing `n_enzymes_in_pathway / n_canonical_steps` per pathway per species.
- Quarto: cross-species page `pathway-completion.qmd` rendering a heatmap of per-step coverage across the campaign species set.

## Estimated integration cost

2-3 days focused (gated on PMN license approval, ~1 business day).
- Day 0: Submit PMN 16 license request.
- Day 1: Build DIAMOND DB; run BLAST against PMN; parse pathway-step joins.
- Day 2: Wire pathway-coverage into postprocess; build pathway-completion sheet.
- Day 3: Quarto heatmap + headline panel.

## Open questions / decisions to make before integrating

- PMN 16 license terms: confirm they permit redistribution as part of a public manuscript/Zenodo bundle.
- Pathway-step matching: best-BLAST-hit, RBH, or HMM profile against pathway-step alignments?
- P450Rdb update cadence: 2023 release; check for refresh before manuscript submission.
- Do we publish our pathway-coverage TSV as a supplementary table?

## Citations

- PMN 16 *NAR* 2025: https://academic.oup.com/nar/article/53/D1/D1606/7903387
- PMN downloads: https://plantcyc.org/downloads/
- P450Rdb *Database* 2023: PMID 37871773, https://pubmed.ncbi.nlm.nih.gov/37871773/
