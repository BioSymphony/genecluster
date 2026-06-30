# MMseqs2 iterative-profile: integration plan for BioSymphony GeneCluster

**Status:** validated on RunPod during validation testing; upstream release 18-8cc5c confirmed current in the latest audit.
**Priority:** cheap-add (drop-in BLAST replacement)
**Endorsed by:** sequence/structure agent (solo)

## Purpose

MMseqs2 (Steinegger lab; release 18-8cc5c, July 2025; GPU paper *Nat Methods* 2025) is the modern descendant of BLAST and PSI-BLAST. The iterative-profile mode (`mmseqs search --num-iterations 3`) recovers +10-15% true orthologs in the 25-40% identity twilight zone where BLAST starts to miss, with a 6.4× speedup. It is the cheapest sensitivity win available without switching to structure-based search.

## What it would add to the BIA atlas specifically

GeneCluster currently uses DIAMOND (BLAST-grade) for protein-vs-proteome searches. Many BIA enzymes, particularly P450s and methyltransferases, have closely-related paralogs at 30-50% identity that DIAMOND will rank below the cluster threshold. Switching to MMseqs2 iterative profiles would surface those paralogs as candidate cluster members, expanding our "BIA candidate" rosters per species without changing the rest of the pipeline.

## Install

```bash
# Bioconda (recommended)
conda install -c conda-forge -c bioconda "mmseqs2>=18"

# Or static binary
# macOS
brew install mmseqs2
# Linux AVX2
# wget https://mmseqs.com/latest/mmseqs-linux-avx2.tar.gz; tar xvzf mmseqs-linux-avx2.tar.gz

# Verify
mmseqs version
```

## Sample CLI: running on our existing data

```bash
mkdir -p .runtime/mmseqs2-out tmp

# 1. Build a target DB from a species proteome
mmseqs createdb \
 .runtime/<species>-summary/proteome.faa \
 .runtime/mmseqs2-out/houttuynia.target.db

# 2. Build a query DB from BIA queries + controls
mmseqs createdb \
 pipeline/genecluster_annotation_direct/queries-with-controls.faa \
 .runtime/mmseqs2-out/queries.db

# 3. Iterative-profile search (--num-iterations 3 is the headline mode)
mmseqs search \
 .runtime/mmseqs2-out/queries.db \
 .runtime/mmseqs2-out/houttuynia.target.db \
 .runtime/mmseqs2-out/queries-vs-houttuynia.result \
 tmp \
 --num-iterations 3 \
 --sensitivity 7.5 \
 --threads 8

# 4. Convert to BLAST tabular for compatibility with our existing parser
mmseqs convertalis \
 .runtime/mmseqs2-out/queries.db \
 .runtime/mmseqs2-out/houttuynia.target.db \
 .runtime/mmseqs2-out/queries-vs-houttuynia.result \
 .runtime/mmseqs2-out/queries-vs-houttuynia.outfmt6 \
 --format-mode 0
```

## Integration point in our pipeline

- `pipeline/genecluster_annotation_direct/run.py`: optional flag `--search-engine mmseqs2` that calls MMseqs2 instead of DIAMOND. Output is BLAST-tabular so the existing `parse_outfmt6` parser is reusable (the cap fix from `c2e9e24` already applies).
- New column in postprocess xlsx: `search_engine` per row, distinguishing BLAST/DIAMOND/MMseqs2 origin.
- Comparison sheet: `mmseqs2-vs-diamond` listing rows recovered only by iterative profile (the headline gain).

## Estimated integration cost

1-2 days focused.
- Day 1: Wire MMseqs2 as an alternative engine; verify outfmt6 compatibility with our parser cap.
- Day 2: Run on one species end-to-end; write `mmseqs2-vs-diamond` delta sheet.

## Open questions / decisions to make before integrating

- `--num-iterations 3` is the upper safe bound; deeper runs risk profile drift on plant 2°-met enzymes, fix value or expose as flag?
- Memory: profile mode is heavier than DIAMOND default; may need `--split-memory-limit` on 16 GB laptops.
- Do we keep DIAMOND as the default and ship MMseqs2 as opt-in, or flip the default?

## Citations

- MMseqs2 GitHub: https://github.com/soedinglab/mmseqs2
- MMseqs2 GPU paper *Nat Methods* 2025: https://www.nature.com/articles/s41592-025-02819-8
- Bioconda: https://bioconda.github.io/recipes/mmseqs2/README.html
- Static binary downloads: https://mmseqs.com/latest/
