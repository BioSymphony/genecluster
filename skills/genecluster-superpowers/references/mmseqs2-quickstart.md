# MMseqs2 iterative-profile: quickstart

**Status:** ✅ **VALIDATED**. `--num-iterations 3 -s 7.5` adds +8, 21 % homologs vs blastp across the campaign species set; per-species TSVs at `<volume>/superpowers/mmseqs2/results/`. Drop-in BLAST replacement for any campaign needing twilight-zone ortholog recovery. See [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md) for full inventory.
**Install (local-only, not canonical):** `brew install mmseqs2` or `mamba install -c bioconda "mmseqs2>=18"`. Canonical dispatch path is RunPod via `genecluster-superpowers` image.

## Sample run on atlas data

```bash
mkdir -p .runtime/mmseqs2-out/phellodendron tmp

# 1. Build query and target DBs
mmseqs createdb \
 .runtime/<species>-launch/queries-with-controls.faa \
 .runtime/mmseqs2-out/queries.db
mmseqs createdb \
 .runtime/<species>-summary/proteome.faa \
 .runtime/mmseqs2-out/phellodendron/target.db

# 2. Iterative-profile search (--num-iterations 3 is the headline mode)
mmseqs search \
 .runtime/mmseqs2-out/queries.db \
 .runtime/mmseqs2-out/phellodendron/target.db \
 .runtime/mmseqs2-out/phellodendron/result \
 tmp \
 --num-iterations 3 \
 --sensitivity 7.5 \
 --threads 8

# 3. Convert to BLAST tabular (parse_outfmt6 already handles this)
mmseqs convertalis \
 .runtime/mmseqs2-out/queries.db \
 .runtime/mmseqs2-out/phellodendron/target.db \
 .runtime/mmseqs2-out/phellodendron/result \
 .runtime/mmseqs2-out/phellodendron/queries-vs-target.outfmt6 \
 --format-mode 0
```

Or use the wrapper: `skills/genecluster-superpowers/scripts/run-mmseqs2.sh phellodendron`.

The proof-point query for sensitivity gain is **Q001 BBE vs Phellodendron**. Compare row count to the existing `.runtime/<species>-summary/blastp_hits.tsv`. the delta is the recovered twilight-zone ortholog set.

## Integration in our pipeline

Drop-in BLAST replacement: `pipeline/genecluster_annotation_direct/run.py --search-engine mmseqs2`. Output is BLAST-tabular so `parse_outfmt6` (cap-fix in commit `0e5a3bc`) reuses unchanged. Postprocess adds `search_engine` column per row and a new `mmseqs2-vs-diamond` sheet listing rows recovered only by iterative profile, the headline +10-15% twilight-zone gain.

## Open questions

- `--num-iterations 3` is the upper safe bound for plant 2°-met enzymes, fix or expose?
- Memory: profile mode is heavier than DIAMOND default, `--split-memory-limit` on 16 GB laptops?
- Keep DIAMOND default and ship MMseqs2 opt-in, or flip the default?

## See also

- `docs/tooling/mmseqs2.md`, full integration plan
- `docs/biosymphony-genecluster-superpower-roadmap.md`, cheap-add tier
- `tools/recommended/mmseqs2/iterative-profile.sh.template`, original placeholder
