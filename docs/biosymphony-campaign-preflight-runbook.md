# BioSymphony: campaign preflight runbook

**Date:** 2026-05-12
**Status:** authoritative for all new campaigns
**Scope:** the mandatory Stage 0 step that every BioSymphony campaign must complete before any compute is spent.

This runbook tells you (a) why Stage 0 exists, (b) how to run it, (c) what to do when it complains, and (d) how to feed the catalog after the campaign so the next campaign starts richer.

## Why Stage 0 exists

Before Stage 0 was wired in, every campaign re-derived "what do we know about this target species + what related species share the pathway?" by hand. Prior campaigns each spent meaningful operator time and parallel research-agent dispatch on this question. The answers were good but they lived only in their campaign docs, so the next campaign re-derived them from scratch. The public catalog at `data/pathway-species-catalog.tsv` now persists those answers across campaigns.

Stage 0 fixes this. It:

1. **Forces** every campaign to start with a structured 5-pillar evaluation (Data / Inputs / Relevance / Novelty / Importance) before any pipeline launch is allowed.
2. Pulls known producers of the target pathway from `data/pathway-species-catalog.tsv` instead of re-deriving them.
3. Auto-discovers additional candidates via NCBI taxonomy walk + NCBI Datasets v2 + SRA esearch + NGDC GWH fallback.
4. Produces a downstream contract (`campaign-launch-readiness.json`) that every other `genecluster_*` stage must honor.

If the operator forgets to provide a comparator list, the system asks NCBI + the catalog itself rather than launching against the target in isolation.

## Stage 0 contract (what downstream stages depend on)

After a successful preflight, the campaign directory MUST contain these artifacts:

| File | Purpose |
|---|---|
| `campaign-launch-readiness.json` | Downstream contract. `preflight_status == "ready"` is required for any L0→L1 stage to proceed. |
| `campaign-preflight-summary.md` | Top-level Markdown report of the 5 pillars. |
| `species_scout.tsv` | One row per candidate species, with assembly, SRA, scoring. |
| `species_scout.json` | Full structured findings. |
| `relevance-novelty-summary.md` | Human-friendly 5-section narrative. |
| `seed-query-candidates.tsv` | KEGG-derived placeholder enzymes (when pathway resolves) or operator-supplied set. |

If `preflight_status` is `blocked` or `needs_audit`, every `genecluster_*` script will refuse to advance the maturity ladder past `L0_control_plane_ready`.

## How to run it

### Quick start: operator does NOT know the comparator list

```bash
python3 skills/biosymphony/scripts/genecluster_campaign_preflight.py \
 --target "Coptis chinensis" \
 --pathway BIA \
 --campaign-id coptis-bia-example \
 --out-dir .runtime/coptis-bia-example-preflight \
 --max-candidates 10 \
 --ncbi-api-key "$NCBI_API_KEY"
```

The preflight invokes the species scout, which:

1. Pulls every catalog row tagged with `pathway_id=BIA` (or pathway-name match).
2. Resolves *Coptis chinensis* taxonomy via NCBI E-utilities, gets `genus=Coptis, family=Ranunculaceae, order=Ranunculales`.
3. Walks the genus, family, and order for related species (e.g., *Coptis teeta*, *Hydrastis canadensis*, *Berberis vulgaris*).
4. For each candidate (target + ≤9 relatives), queries NCBI Datasets v2 for best assembly, esearch SRA for tissue breadth, and probes NGDC GWH plants for fallback assemblies when NCBI is empty.
5. Resolves `BIA` → KEGG `map00950` and pulls the enzyme list as seed-query placeholders.
6. Composes the 5-section relevance/novelty summary.

### Quick start: operator KNOWS comparators (skip auto-discover)

```bash
python3 skills/biosymphony/scripts/genecluster_campaign_preflight.py \
 --target "Coptis chinensis" \
 --pathway BIA \
 --campaign-id coptis-bia-example \
 --out-dir .runtime/coptis-bia-example-preflight \
 --comparative-species "Berberis vulgaris,Eschscholzia californica,Argemone mexicana" \
 --seed-queries-tsv .runtime/coptis-bia-example-preflight/operator-seeds.tsv
```

The preflight validates the comparator list against the catalog (flagging unknown / cross-pathway species) and validates the seed-queries TSV shape (required columns, controls, duplicate `query_id`, missing UniProt anchors).

### Dry run (no NCBI fetches)

```bash
python3 skills/biosymphony/scripts/genecluster_campaign_preflight.py \
 --target "Coptis chinensis" \
 --pathway BIA \
 --campaign-id coptis-bia-example \
 --out-dir .runtime/coptis-bia-example-preflight \
 --dry-run
```

Dry run produces the catalog-derived report without hitting any REST endpoint. Useful for offline scaffolding.

## The five-pillar report: what each section tells you

### 1. Data

Per candidate species:

- Best NCBI assembly (accession, level chromosome/scaffold/contig, year)
- NGDC GWH fallback accession when NCBI is empty
- Annotation presence flag (yes / partial / unknown / no)
- SRA RNA-Seq breadth: total run count + per-tissue counts (root / leaf / stem / flower / fruit / rhizome / latex / etc.)
- Top 1, 3 BioProjects
- Most recent submission year

This is the answer to "is there anything to run on?" before you launch.

### 2. Inputs

If the pathway resolves to a KEGG map (`BIA→map00950`, `MIA→map00901`, etc.), the scout emits a placeholder query set (`PROPQ001…PROPQNN`) from KEGG enzymes. **These are placeholders.** Each row's `uniprot` column shows `(needs_anchor_resolution)`; the operator (or a Codex dispatch agent) must replace these with canonical SwissProt accessions before launch.

Standard controls are always appended:
- `POSCTRL_ACTIN` (ACT2, Arabidopsis P0CJ47)
- `POSCTRL_GAPDH` (Arabidopsis P25856)
- `NEGCTRL_RANDOM` (shuffled 150 aa)

When the operator passes `--seed-queries-tsv path/to/seeds.tsv`, the scout uses that file directly and validates: required columns (`query_id`, `enzyme_name`, `uniprot`), presence of all three control types, no duplicate `query_id`, no missing anchors.

### 3. Relevance

Candidates are bucketed by taxonomy relationship to the target:

- **Same family**, direct sister species (highest synteny; near-1:1 ortholog mapping expected)
- **Same order, different family**, broader convergence baseline
- **Different order (convergent producers)**, independent-origin signal

This is the answer to "how much pathway overlap is the candidate likely to give us?"

### 4. Novelty

Candidates with a tracked `key_publication_pmid` in `data/pathway-species-catalog.tsv` are listed with their existing publication and the `novelty_window` field. Candidates without a tracked publication are flagged for a literature audit (the 3-Opus dispatch pattern).

**Operator action when novelty is unclear:** trigger the lit-audit agent fan-out before committing the campaign. The audit writes back into the catalog's `key_publication_pmid` + `novelty_window` columns so the next campaign benefits.

### 5. Importance

Composite ranking via deterministic score:

| Signal | Weight |
|---|---|
| Chromosome-scale assembly | +30 |
| Scaffold assembly | +15 |
| NGDC-GWH fallback assembly | +18 |
| Annotation present | +20 |
| ≥3 tissues in SRA | +15 |
| 1, 2 tissues in SRA | +7 |
| Year ≥ 2024 | +10 |
| Year ≥ 2020 | +5 |
| Catalog `comparative_value=HIGH` | +15 |
| Catalog `comparative_value=BASELINE` (canonical target) | +12 |
| Catalog `comparative_value=MED` | +7 |

Top 3 by score are reported as "recommended comparators" plus a sequencing-priority order (NCBI fastest path first, then NGDC GWH, then de novo RNA-Seq).

## What blocks a preflight

| Status | Trigger | Operator action |
|---|---|---|
| `ready` | All checks pass | Proceed to L1 |
| `blocked` | Scout produced 0 candidates OR seed-queries TSV failed validation | Inspect `status_reasons` in the readiness JSON; fix and re-run |
| `needs_audit` | `--require-novelty-audit` set and `novelty-audit.md` not present | Run the 3-Opus literature audit, save output as `<out-dir>/novelty-audit.md`, re-run preflight |

The `genecluster_*` downstream scripts grep `preflight_status` from the readiness JSON before doing anything else. If `ready` is missing, they exit non-zero with a pointer back to this runbook.

## Adding to the catalog (post-campaign)

After a campaign ships, enrich `data/pathway-species-catalog.tsv` with what you learned. Edit the TSV directly (it is tab-separated, 21 columns; trailing empty cells are fine):

```
pathway_id pathway_name species common_name genus family plant_order
 best_genome_accession genome_source genome_level annotation_present
 rna_seq_bioprojects tissues_covered year_latest key_publication_pmid
 key_publication_doi comparative_value novelty_window campaign_used_in
 last_audit_date notes
```

Recommended per-campaign updates:

1. **Update `last_audit_date`** for every catalog row you touched.
2. **Set `comparative_value`** from MEDIUM (predicted) to HIGH (proven) when the campaign confirmed strong synteny / cluster signal. or down to LOW when it disappointed.
3. **Fill in `key_publication_pmid` / `novelty_window`** if the literature audit produced new citations.
4. **Add new species rows** for any tax-walk candidate the scout surfaced that wasn't already there.
5. **Reference the campaign in `campaign_used_in`** (e.g., `campaign-sp2`).

## Operator quality bar

- **Never bypass Stage 0.** If `preflight_status` is anything but `ready`, the campaign is not ready. The 5-pillar report is not optional paperwork. It is the difference between "we ran a campaign" and "we ran a defensible campaign."
- **Catalog rows are evidence, not opinion.** When you update `comparative_value`, cite the specific cluster/anchor evidence. When you fill `key_publication_pmid`, the publication must actually mention the species + pathway pair.
- **Treat KEGG placeholder queries as TODOs.** They never go to a launch bundle as-is. Either an operator or a Codex agent fan-out resolves UniProt anchors first.
- **Always include controls.** Positive (ACTIN, GAPDH) and negative (shuffled). Stage 0 enforces this on user-supplied TSVs but does not enforce it on the placeholder set. You do.

## Cross-references

- `skills/biosymphony/SKILL.md`, Stage 0 section, mandatory contract
- `skills/biosymphony/scripts/genecluster_campaign_preflight.py`, wrapper script
- `skills/biosymphony/scripts/genecluster_species_scout.py`, fan-out scout
- `data/pathway-species-catalog.tsv`, public pathway × species catalog used as institutional memory
