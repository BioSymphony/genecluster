# cblaster + clinker: quickstart

**Status:** ⛔ **PARKED**, validated. Install path works in a cloud pod; the campaign-breaker is that cblaster expects **GenBank input** and the campaign species ship as protein FASTA + GFF only. A retry hit a transient provider proxy 502.
**Re-entry recipe:** (1) stage GenBanks per species via NCBI Datasets CLI: `datasets download genome accession GCA_xxx --include gbff`. (2) Build cblaster local DB from those. (3) Run cblaster query against the per-species DB and pipe clusters to clinker for SVG. Effort: small CPU pod + 2 h author time. Full details in [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md).
**Install (local-only, not canonical path):** `pip install "cblaster>=1.4.0" "clinker>=0.0.32"`. The canonical dispatch is a cloud pod via the `genecluster-superpowers` image, not laptop install.

## Sample run on atlas data

```bash
# 1. Build per-species DIAMOND DBs (one-time, ~2 min per species)
mkdir -p .runtime/cblaster-dbs
for sp in coptis houttuynia stephania phellodendron; do
 cblaster makedb \
 .runtime/campaign-${sp}-summary/proteome.faa \
 .runtime/cblaster-dbs/${sp}.dmnd
done

# 2. cblaster search: query enzyme set vs all campaign species
cblaster search \
 --query_file .runtime/<species>-launch/queries-with-controls.faa \
 --mode local \
 --database .runtime/cblaster-dbs/*.dmnd \
 --max_distance 50000 \
 --min_hits 3 \
 --output .runtime/cblaster-out/bia-clusters.csv \
 --plot .runtime/cblaster-out/bia-clusters.html

# 3. clinker: synteny SVG over the per-cluster GenBank slices
cblaster extract --query .runtime/cblaster-out/bia-clusters.csv \
 --output .runtime/cblaster-out/clusters --format genbank
clinker .runtime/cblaster-out/clusters/*.gbk \
 --output_html .runtime/cblaster-out/clinker.html \
 --output_svg .runtime/cblaster-out/clinker.svg
```

Or run the wrapper: `skills/genecluster-superpowers/scripts/run-cblaster.sh coptis`.

## Integration in our pipeline

Output flows into `cross-species/bbe-gradient.qmd` (ythe atlas chapter) (Quarto) as an `<iframe>` embed of `clinker.html`. The cluster CSV joins onto the per-species `clusters-diamond` xlsx sheet via `cblaster_join.py` (planned). Replaces the hand-written gradient table in `data/pathway-species-catalog.tsv` with auto-generated SVG ribbons, the Shan / Sun / Astilbe paper figure style.

## Open questions

- `--max_distance 50000` matches our 50 kb anchor window; experiment with 75 kb for sparser BIA clusters
- `--min_hits 3` may be too strict for 2-enzyme bisBIA clusters, drop to 2?
- Mirror MIBiG 4.0 as a second cblaster DB target for ground-truth cross-checks?

## See also

- `docs/tooling/cblaster-clinker.md`, full integration plan + cost
- `docs/biosymphony-genecluster-superpower-roadmap.md`, Priority ★2, BGC + reporting consensus
- `tools/recommended/cblaster/query-cluster.sh.template`, original placeholder
