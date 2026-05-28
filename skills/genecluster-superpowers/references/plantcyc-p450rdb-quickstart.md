# PlantCyc PMN 16 + P450Rdb: quickstart

**Status (mixed):**
- **P450Rdb:** ✅ **VALIDATED**. 3 BIA queries at 100 % identity vs curated P450 sequences. Pre-clean FASTA before `diamond makedb`. line 355 of P450Rdb v2.0 `sequences.fasta` contains only `/` which trips diamond; memory.
- **PlantCyc / PMN 16:** ⏸️ **GATED**, academic license required (~1 business-day approval). Not yet applied. **Validated alternative:** KEGG mapper / KAAS (validated) covers pathway-completion baseline in the interim.

See [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md) for full inventory.

**Install:** No installer. manual download. PMN 16 needs license submission at https://plantcyc.org/downloads/license-agreement. P450Rdb is free from the publication supplementary (Database 2023, PMID 37871773) and now pre-staged on the provider volume at `<volume>/db-cache/p450rdb/`.

## Sample run on atlas data

Goal: a "% complete vs canonical Coptis BIA pathway" panel per species, plus plant-aware reference annotations for our CYP71B / CYP80 / CYP719 anchors.

```bash
# Once PMN 16 is staged at .runtime/databases/pmn-16/
# (after license approval and tar extraction)

# 1. Build a DIAMOND DB from PMN's enzyme sequences
diamond makedb \
 --in .runtime/databases/pmn-16/all_enzymes.faa \
 --db .runtime/databases/pmn-16/pmn16-enzymes.dmnd

# 2. BLAST each species' cluster proteins against PMN
for sp in coptis houttuynia stephania phellodendron; do
 diamond blastp \
 --query .runtime/campaign-${sp}-summary/cluster-sequences.faa \
 --db .runtime/databases/pmn-16/pmn16-enzymes.dmnd \
 --outfmt 6 qseqid sseqid pident evalue stitle \
 --out .runtime/pmn-pathway-coverage/${sp}-vs-pmn.tsv \
 --max-target-seqs 5 --evalue 1e-20
done

# 3. Annotate our CYP candidates against P450Rdb
# (P450Rdb is a curated TSV: join on closest BLAST hit)
```

No wrapper script, both are databases, not tools. Use the snippet above directly once `.runtime/databases/pmn-16/` and `.runtime/databases/p450rdb/p450rdb.tsv` exist.

## Integration in our pipeline

New enrichment helpers: ``pipeline/genecluster_annotation_direct/`` joins our cluster candidates to PMN pathway-step IDs; `pipeline/genecluster_annotation_direct/enrichment/p450rdb_anchor.py` annotates P450 hits with curated reaction labels. Postprocess adds `pmn_pathway_step` column on `top-hits` and `clusters-diamond` and a new `pathway-coverage` sheet listing `n_enzymes_in_pathway / n_canonical_steps` per species. Quarto: `cross-species/pathway-completion.qmd` heatmap of per-step coverage across the campaign species set.

## Open questions

- PMN 16 license terms, confirm they permit redistribution as part of a public Zenodo/manuscript bundle.
- Pathway-step matching: best-BLAST-hit, RBH, or HMM profile against pathway-step alignments?
- P450Rdb update cadence (2023 release), refresh before manuscript submission?

## See also

- `docs/tooling/plantcyc-p450rdb.md`, full integration plan
- `docs/biosymphony-genecluster-superpower-roadmap.md`, cheap-add (DB-only)
- PMN 16 *NAR* 2025: https://academic.oup.com/nar/article/53/D1/D1606/7903387
