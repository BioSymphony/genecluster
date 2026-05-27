# Foldseek + ProstT5: quickstart

**Status:** ✅ **VALIDATED** on public data. AFDB-SwissProt or AFDB-Plants staged on the provider volume at `<volume>/db-cache/foldseek/`. Sample-run command + integration notes preserved below for re-execution. Cross-species evidence-layer role: detects convergent-enzyme cases (one enzyme family substituting for another at the same reaction step) invisible to BLAST at <15 % sequence identity. Full details in [`docs/biosymphony-tooling-status.md`](../../../docs/biosymphony-tooling-status.md).
**Install (local-only, not canonical):** `tools/recommended/install-heavy.sh` for laptop. Canonical dispatch path is a GPU pod via the `genecluster-superpowers` image; ProstT5 model + AFDB pre-staged on the provider volume.

## Sample run on atlas data

The hypothesis-test: take a canonical query enzyme and search comparator proteomes for structure-similar candidates BLAST missed at <40% identity. This is the regime where convergent-enzyme stories live.

```bash
mkdir -p .runtime/foldseek-out/<species> tmp

# 1. Build a Foldseek DB from the target species proteome (sequence-only via ProstT5)
foldseek easy-search \
 .runtime/<species>-summary/cluster-sequences.faa \
 .runtime/<species>-summary/proteome.faa \
 .runtime/foldseek-out/<species>/query-vs-target.m8 \
 tmp \
 --prostt5-model Rostlab/ProstT5 \
 --threads 8 \
 --format-output query,target,evalue,bits,prob,alntmscore
```

Or use the wrapper: `skills/genecluster-superpowers/scripts/run-foldseek-prostt5.sh <species>`.

The headline output is `prob` (>0.9 = same fold) and `alntmscore` (>0.5 = structural match). Cross-tab against `blastp_hits.tsv`: any row with high TM-score but missing from BLAST output is a fold-level convergent candidate worth manuscript ink.

## Integration in our pipeline

New stage gated on `--enable-foldseek` in `pipeline/genecluster_annotation_direct/run.py`. Output `.m8` parses into ``pipeline/genecluster_annotation_direct/`` → `tm_top_hit`, `tm_score`, `tm_evalue` per protein. Postprocess adds `structure-foldseek` xlsx sheet and flags rows where Foldseek hit ≠ BLAST hit. Quarto: `cross-species/convergence-evidence.qmd` lists the convergence cases.

## Open questions

- Local AFDB-Plants (~350 GB) vs EBI Foldseek server (no disk, throttled)?
- Apple Silicon: does ProstT5 run via Metal (`-mps`) acceptably without an NVIDIA GPU?
- Convergence threshold: probability + TM-score combination, or just TM ≥ 0.5?

## See also

- `docs/tooling/foldseek-prostt5.md`, full integration plan + cost
- `docs/biosymphony-genecluster-superpower-roadmap.md`, Priority ★4 (cross-species evidence layer)
- `tools/recommended/foldseek/prostt5-search.sh.template`, original placeholder
