# plantiSMASH: quickstart

**Status:** ✅ **VALIDATED at upstream 2.0.4 via BioSymphony v7 boot recipe**. Detects multiple clusters per chromosome (mix of alkaloid and saccharide cluster types) on public plant genomes, with thousands of CDS in the output `final.gbk`.
**⚠️ Version pin matters:** "v7" is not an upstream plantiSMASH release; it is BioSymphony's seventh boot iteration. Raw editable installs of plantiSMASH **2.0.4** hit a `straight.plugin` blocker. `pip install -e` registers no detection plugins; `--list-plugins` returns empty. Use the non-editable source install plus the v7 recipe.
**License note:** AGPL-3.0+. Internal command-line use is distinct from hosting a public plantiSMASH service; public service hosting can trigger source-publication requirements. **Validated companion**: DeepBGC (validated) as the LSTM-neural-network alternative, no taxon restriction.
**Plant alternative:** For plant BGC detection, plantiSMASH 2.0.4 + DeepBGC are the validated pair. antiSMASH 8 (validated) dropped `--taxon plants` after v4. use for bacterial / fungal contingency only.
See [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md) for full inventory.

**Install (local-only, not canonical):** Use `pip install .` from a clean clone of `plantismash/plantismash` at tag `plantismash-2.0.4`; avoid editable mode. Canonical dispatch path is RunPod via `genecluster-superpowers` image.

## Sample run on atlas data

```bash
# Coptis as the validation target: known to contain BBE / NOMT / CYP719A clusters
# our anchor-driven 50 kb windowing already detected. plantiSMASH should
# reproduce those AND surface anchor-less clusters we missed.
mkdir -p .runtime/plantismash-out/coptis

conda run -n plantismash plantismash \
 --taxon plants \
 --genefinding-tool none \
 --outputfolder .runtime/plantismash-out/coptis \
 .runtime/<species>-summary/genomic.gff
```

Or use the wrapper: `skills/genecluster-superpowers/scripts/run-plantismash.sh coptis`.

After running, parse the output GenBank/JSON region files and coordinate-overlap-join with our existing `cluster_neighborhoods.tsv` (in `.runtime/<species>-summary/`). Validation question: do plantiSMASH calls reproduce our BBE / NOMT / CYP719A anchors? Discovery question: which plantiSMASH clusters have **no canonical BIA anchor** in our query set?

## Integration in our pipeline

After per-species cluster discovery in `pipeline/genecluster_annotation_direct/run.py`, add a `plantismash_detect` stage. Postprocess adds `plantismash_cluster_id`, `plantismash_type`, `plantismash_substrate_prediction` columns to `clusters-diamond`, plus a new `plantismash-only-clusters` sheet for motif-driven calls anchor-windowing missed.

## Open questions

- Run on all 4 atlas species or only on validation target (Coptis) first?
- Mirror full 30,423-BGC database locally or query the web service per cluster?
- Coordinate-overlap join policy: union, intersection, or label-only?

## See also

- `docs/tooling/plantismash.md`, full integration plan + cost
- `docs/biosymphony-genecluster-superpower-roadmap.md`, Priority ★1, BGC + enzyme-function consensus
- `tools/recommended/plantismash/run-on-species.sh.template`, original placeholder
