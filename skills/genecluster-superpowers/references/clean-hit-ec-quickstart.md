# CLEAN / HIT-EC: quickstart

**Status:** ⛔ **PARKED**, validated. Env builds clean across 4 boot revs, but `CLEAN_infer_fasta.py` wrapper hard-codes `./data/` cwd and shells to `esm/scripts/extract.py` whose child Python loses the conda env. **Validated EC alternative shipped instead: DeepEC / ECPred (validated).**
**Re-entry recipe:** Bypass the wrapper. Pre-compute ESM-1b embeddings via the fair-esm conda Python API directly, then call `CLEAN.infer.infer_maxsep` from a custom script. Skip `CLEAN_infer_fasta.py` entirely. Effort: small GPU pod + 3 h author time. Full details in [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md). HIT-EC v2.0.0 is now public (was "pending" at the original writeup) so the paired-tool plan is back on the table once CLEAN works.
**Install (local-only, not canonical path):** `tools/recommended/install-heavy.sh` for laptop; canonical is a GPU pod via the `genecluster-superpowers` image.

## Sample run on atlas data

Predict EC numbers for the ~500 cluster-neighbor proteins in Phellodendron. Cross-tab against the existing `neighbor_swissprot.tsv` annotations to see where CLEAN adds an EC label that SwissProt didn't.

```bash
# CLEAN expects to run from inside its own clone
cd tools/recommended/clean-hit-ec/src/CLEAN

# 1. Pre-compute ESM-1b embeddings (one-time per FASTA, ~20 min on M1 Pro)
python3 build.py install

# 2. Inference: cluster neighbor proteins for one species
python3 CLEAN_infer_fasta.py \
 --fasta_data ../../../../.runtime/<species>-summary/cluster-sequences.faa \
 --pretrained 70 # 70%-identity clustering split (better generalization)

# Output: results/cluster-sequences_maxsep.csv
mv results/cluster-sequences_maxsep.csv \
 ../../../../.runtime/<species>-summary/superpowers/clean-hit-ec/
```

Or use the wrapper: `skills/genecluster-superpowers/scripts/run-clean-hit-ec.sh phellodendron`.

The cross-tab to verify quality: join the CSV's `EC_pred` column against `neighbor_swissprot.tsv` on `protein_id`. Where SwissProt says "uncharacterized P450 73E2-like", CLEAN should propose an EC like `1.14.14.110` (S-stylopine synthase) with a maxsep confidence score.

## Integration in our pipeline

New enrichment module ``pipeline/genecluster_annotation_direct/`` parses the CSV; `your downstream postprocess script` adds an `ec-clean` sheet. Once HIT-EC ships, mirror with `ec_hit_ec.py` and add an `ec-consensus` sheet (both predictors agree above confidence threshold). Headline panel: "% of cluster candidates with confident EC assignment" per species.

## Open questions

- HIT-EC code release timing, is the Nat Commun 2026 reference repo public yet?
- 70% vs 100% identity split, flag-driven or fixed at 70%?
- Confidence threshold for "consensus EC": both ≥0.5? CLEAN's `maxsep` sets per-protein thresholds.

## See also

- `docs/tooling/clean-hit-ec.md`, full integration plan + cost
- `docs/biosymphony-genecluster-superpower-roadmap.md`, high-confidence solo recommendation (enzyme-function agent)
- `tools/recommended/clean-hit-ec/predict-ec.sh.template`, original placeholder
