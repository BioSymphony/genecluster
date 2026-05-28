# CLEAN / HIT-EC: integration plan for BioSymphony GeneCluster

**Status:** parked. Install path was proven, but the CLEAN wrapper is brittle on RunPod; DeepEC / ECPred is the validated EC fallback. See `docs/biosymphony-tooling-status.md` for the re-entry recipe.
**Priority:** ★ (high-confidence solo recommendation)
**Endorsed by:** enzyme-function agent

## Purpose

CLEAN (Yu et al. *Science* 2023) is a contrastive-learning EC-number predictor that beats BLASTp and DeepEC. CLEAN-Contact (PNNL-CompBio, *Comm Biol* 2024) augments it with structural inference. HIT-EC (Liu et al. *Nat Commun* 2026) is a 4-level hierarchical transformer with calibrated abstention, it knows when it doesn't know, which is critical for novel BIA enzymes that don't match anything in SwissProt. Together they put EC labels on the half of our cluster candidates that BLAST hits at <40% identity to a SwissProt enzyme.

## What it would add to the BIA atlas specifically

Our current xlsx flags candidates with names like "uncharacterized P450 73E2-like", accurate but not actionable. CLEAN/HIT-EC would tag the same row with `EC 1.14.14.110` (S-stylopine synthase) plus a confidence score, giving reviewers an immediate read on enzymatic function. HIT-EC's abstention is especially important: for the convergent-enzyme cases where Foldseek finds a fold match without sequence homology, HIT-EC will correctly say "uncertain" rather than confidently mis-labeling.

## Install

```bash
# CLEAN: clone + Python deps
mkdir -p tools/recommended/clean-hit-ec/src && cd tools/recommended/clean-hit-ec/src
git clone https://github.com/tttianhao/CLEAN.git
cd CLEAN
git clone https://github.com/facebookresearch/esm.git
pip install -r requirements.txt
cd esm && pip install . && cd ..

# HIT-EC: installable via pip once the Nat Commun 2026 release lands on PyPI
# Until then, clone from the paper's reference repo (placeholder)
# git clone https://github.com/<HIT-EC-org>/HIT-EC.git

# CLEAN-Contact (structure-augmented variant)
git clone https://github.com/PNNL-CompBio/CLEAN-Contact.git

# Verify CLEAN
cd CLEAN && python CLEAN_infer_fasta.py --help
```

## Sample CLI: running on our existing data

```bash
# CLEAN inference on our cluster candidates
cd tools/recommended/clean-hit-ec/src/CLEAN

# 1. Pre-compute ESM-1b embeddings for queries
python build.py install
python CLEAN_infer_fasta.py \
 --fasta_data ../../../../.runtime/<species>-summary/cluster-candidates.faa \
 --pretrained 70 # 70% identity clustering split

# 2. Output: results/{fasta_data}_maxsep.csv with EC predictions per protein
```

## Integration point in our pipeline

- New enrichment module: ``pipeline/genecluster_annotation_direct/`` invoking CLEAN inference on cluster candidates.
- New enrichment module (parallel): ``pipeline/genecluster_annotation_direct/`` invoking HIT-EC.
- Postprocess: new sheets `ec-clean` and `ec-hit-ec` in per-species xlsx; consensus `ec-consensus` sheet (where both agree above confidence threshold).
- Headline panel: "% of cluster candidates with confident EC assignment" per species, direct competition signal vs PlantCyc/PMN expert curation.

## Estimated integration cost

3-4 days focused.
- Day 1: CLEAN install + ESM-1b embedding pre-compute on one species.
- Day 2: Wire CLEAN inference into enrichment pipeline; postprocess xlsx integration.
- Day 3: HIT-EC integration once package is publicly available; consensus sheet.
- Day 4: Cross-species coverage panel + Quarto embed.

## Open questions / decisions to make before integrating

- HIT-EC code release timing, is the Nat Commun 2026 reference repo public yet?
- ESM-1b embeddings on a 30k-protein proteome: ~1-2 hours on M1 Pro; do we cache to disk or re-compute per run?
- 70% vs 100% identity split: 70% generalizes better, 100% is more accurate on enzymes with close SwissProt homologs, flag-driven or fixed?
- Confidence threshold for "consensus EC": both CLEAN and HIT-EC ≥0.5? CLEAN's `maxsep` algorithm sets its own per-protein threshold.

## Citations

- CLEAN *Science* 2023: https://www.science.org/doi/10.1126/science.adf2465
- CLEAN GitHub: https://github.com/tttianhao/CLEAN
- CLEAN-Contact *Comm Biol* 2024: https://www.nature.com/articles/s42003-024-07359-z
- CLEAN-Contact GitHub: https://github.com/PNNL-CompBio/CLEAN-Contact
- HIT-EC *Nat Commun* 2026: https://www.nature.com/articles/s41467-026-68727-3
