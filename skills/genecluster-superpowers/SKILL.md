---
name: genecluster-superpowers
description: Use when extending the BioSymphony GeneCluster comparative atlas with new tooling, sequence/structure search, biosynthetic-gene-cluster (BGC) detection, synteny ribbons, EC prediction, plant-aware reference databases, interactive viewers, or scientific report rendering. Packages the recommended-tool survey, the extended testing sweep, and the upstream freshness check as ready-to-invoke shortcuts. **Canonical tool-status inventory: `docs/biosymphony-tooling-status.md`** (25 checked / 3 parked / 8 shelved / 2 gated).
---

# GeneCluster Superpowers

This skill collects every recommended tool from the superpower-discovery survey + the public test sweep into one invocable kit. Use it as the single shortcut for "I want to extend the atlas with X, what's already wired up?"

**Single source of truth for tool status:** [`docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md). The status tables in this skill mirror that doc for the originally surveyed subset; the canonical inventory covers the full 25-tool checked set + parked + shelved.

## When to use this skill

- Adding a new species to the atlas and you want better-than-BLAST sequence homology (MMseqs2, Foldseek)
- Detecting BGCs that anchor-windowing missed (plantiSMASH 2.0.4 via the checked v7 boot recipe)
- Drawing cross-species cluster synteny ribbons (cblaster + clinker, JCVI MCScan)
- Predicting EC numbers / function for non-Pfam-annotatable candidates (CLEAN-Contact, HIT-EC)
- Layering plant-aware pathway/database context on existing hits (PlantCyc PMN 16, P450Rdb)
- Embedding interactive viewers in atlas reports (Cytoscape.js, copy-paste pattern)
- Rendering the atlas to a publishable HTML book or journal-ready PDF (Quarto, already adopted)

## When To Use Something Else

- Running the upstream pipeline itself, that's `skills/biosymphony/` and `pipeline/genecluster_annotation_direct/`.
- Routine xlsx postprocess, that's `your downstream postprocess script`.
- Dispatching RunPod pipeline jobs, that's `.runtime/<species>-launch/dispatch.py`.

## Operating model

Four states per tool: **adopted**, **parked**, **shelved**, or **gated**.

- **Adopted (✅)** = checked on RunPod, output integrated into the atlas, canonical path. Just call it.
- **Parked (⛔)** = install proven on RunPod but a downstream runtime blocker stopped atlas-quality output. **Each parked tool has a documented re-entry recipe in [`docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md). pick up at the recipe, not at "what's the install path?"**
- **Shelved (❓)** = on the roadmap, license-free, with no dispatch recorded. Listed in the canonical inventory with effort estimate + re-entry recipe; lower priority for current work.
- **Gated (⏸️)** = blocked on license application or API key access. Alternative checked where available.

Current status (after the extended testing sweep and upstream freshness check, for the full 25-tool inventory see [`docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md)):

| Tool | Status | Tier | Check task | Notes |
|---|---|---|---|---|
| **Quarto 1.9.37** | ✅ ADOPTED | blessed | (adopted) | Quarto atlas book live |
| **plantiSMASH 2.0.4 (v7 boot recipe)** | ✅ ADOPTED | medium-add | checked | Upstream latest is 2.0.4; "v7" names BioSymphony's checked boot iteration. Raw editable installs had `straight.plugin` discovery blockers; use the non-editable source install + recipe. Detects multiple clusters per chromosome on public plant genomes. AGPL-3.0+. Review license terms before public service use. |
| **antiSMASH 8.0.4** (bacterial / fungal) | ✅ ADOPTED | (added P12) | checked | Cookbook at `docs/biosymphony-antismash-cookbook.md`. Mambaforge + cpu5g. No `--taxon plants`. |
| **DeepBGC** (plant BGC default) | ✅ ADOPTED | (added during testing) | checked | Tens of BGCs detected across multiple chromosomes on a public plant genome |
| **JCVI MCScan** | ✅ ADOPTED | cheap-add | checked | Thousands of pairwise anchors between two public plant species |
| **MMseqs2 iterative** | ✅ ADOPTED | cheap-add | checked | +8, 21 % homologs vs blastp |
| **Foldseek + ProstT5** | ✅ ADOPTED | cross-species support layer | checked | Thousands of PDB structural hits returned on a public plant query set |
| **cblaster + clinker** | ⛔ PARKED | cheap-add | checked | Re-entry: stage GenBanks via NCBI Datasets CLI -> local cblaster DB -> query. |
| **CLEAN + HIT-EC** | ⛔ PARKED | cheap-add | checked | Wrapper brittle; re-entry: bypass `CLEAN_infer_fasta.py`, call `CLEAN.infer.infer_maxsep` directly. **DeepEC / ECPred is the checked EC alternative.** |
| **HHblits / HHsuite3** | ⛔ PARKED | optional | checked | cpu3g OOM on PDB70; re-entry: cpu5g + pre-stage PDB70 in separate pod. MMseqs2 + Foldseek cover divergent-homolog space. |
| **PlantCyc PMN 16** | ⏸️ GATED | DB-only |. | Academic license required. KEGG / KAAS covers pathway-completion in the interim. |
| **P450Rdb** | ✅ ADOPTED | DB-only | checked | 3 BIA queries at 100 % identity |
| **Cytoscape.js 3.33.3** | ✅ ADOPTED | frontend |. | Pathway-completion viewer with Fit/Reset/zoom controls |

**Also checked in the extended test campaigns:** MIBiG 4.0, ESM-C 300M Synthyra, ESM-2 650M, HMMER, InterProScan, TM-align / mTM-align, MAFFT, IQ-TREE, ColabFold, KEGG mapper / KAAS, EnzymeMap, DiffPaSS, DeepEC / ECPred, igv-reports, pyGenomeTracks, and Quarto Dashboards.

The canonical roadmap with original verdict matrices and citations: `docs/biosymphony-genecluster-superpower-roadmap.md` (pre-test predictions, current state lives in `docs/biosymphony-tooling-status.md`).
The per-tool integration plans with install + sample CLI: `docs/tooling/<tool>.md`.
The per-tool quickstarts (terse + actionable): `references/<tool>-quickstart.md` (in this skill).

## Quick start: what's installed?

Before you do anything, check what's available:

```bash
bash skills/genecluster-superpowers/scripts/superpowers-status.sh
```

Output shows which tools are installed, their version, and the install command for the missing ones.

## Install tiers

Three idempotent install scripts at `tools/recommended/`:

```bash
# Cheap tier: pip + bioconda + brew installables
bash tools/recommended/install-cheap.sh # cblaster, clinker, JCVI, MMseqs2, igv-reports, Quarto

# Medium tier: Docker + heavier conda
bash tools/recommended/install-medium.sh # plantiSMASH 2.0.4 source install, MIBiG download

# Heavy tier: GPU / large model downloads
bash tools/recommended/install-heavy.sh # Foldseek + ProstT5, CLEAN-Contact
```

You usually want cheap-tier first; medium and heavy land when you need the specific capability.

## Per-tool quickstarts

Each `references/<tool>-quickstart.md` has the same shape: status, install one-liner, sample run on atlas data, integration in our pipeline, open questions, see-also links. The runner scripts in `scripts/run-<tool>.sh` mirror the sample-run command with sane defaults pointing at `.runtime/campaign-<species>-summary/`.

**Adopted (just use):**
- [`quarto-quickstart.md`](references/quarto-quickstart.md), render the atlas
- [`jcvi-mcscan-quickstart.md`](references/jcvi-mcscan-quickstart.md), whole-genome synteny ribbons
- [`mmseqs2-quickstart.md`](references/mmseqs2-quickstart.md), iterative-profile ortholog recovery
- [`plantismash-quickstart.md`](references/plantismash-quickstart.md), motif-driven plant BGC detection (use upstream 2.0.4 through the checked v7 boot recipe)
- [`foldseek-prostt5-quickstart.md`](references/foldseek-prostt5-quickstart.md), structure-similarity for convergent enzymes (cross-species support layer)
- [`plantcyc-p450rdb-quickstart.md`](references/plantcyc-p450rdb-quickstart.md), P450Rdb checked; PlantCyc still gated on academic license
- [`cytoscape-js-snippet.md`](references/cytoscape-js-snippet.md), copy-paste viewer pattern

**Parked. re-entry recipe required before retry (read `docs/biosymphony-tooling-status.md` first):**
- [`cblaster-quickstart.md`](references/cblaster-quickstart.md), needs GFF -> GenBank step OR NCBI Datasets fetch
- [`clean-hit-ec-quickstart.md`](references/clean-hit-ec-quickstart.md), bypass `CLEAN_infer_fasta.py`; DeepEC / ECPred is the checked alternative

## Sample invocation pattern

Every runner takes a species shorthand as `$1`:

```bash
# Run cblaster on a species' cluster against the canonical query set
bash skills/genecluster-superpowers/scripts/run-cblaster.sh <species>

# Pairwise synteny: species A vs species B
bash skills/genecluster-superpowers/scripts/run-jcvi-mcscan.sh <species-a> <species-b>

# MMseqs2 iterative profile on a species
bash skills/genecluster-superpowers/scripts/run-mmseqs2.sh <species>

# Foldseek + ProstT5: find structurally similar candidates to a query enzyme
bash skills/genecluster-superpowers/scripts/run-foldseek-prostt5.sh <species>
```

If the underlying tool is not installed, each runner exits cleanly with the exact install command.

## Required checks before using this skill

```bash
# 1. Status check: what's installed
bash skills/genecluster-superpowers/scripts/superpowers-status.sh

# 2. Atlas-data sanity - point at your own derived summary directory.
# The public snapshot intentionally omits .runtime/ outputs.
ATLAS_SUMMARY_DIR=/path/to/your/atlas-summary
test -d "$ATLAS_SUMMARY_DIR"

# 3. Quarto render still works when a local atlas project is available.
QUARTO_PROJECT=/path/to/your/quarto-atlas
test -f "$QUARTO_PROJECT/_quarto.yml" && (cd "$QUARTO_PROJECT" && quarto render --to html)
```

Run these any time before kicking off a tool integration.

## When to add a new tool to this skill

When a new tool gets recommended (via a focused tooling review or a new paper), the integration follows the foundation-laying pattern:

1. **Survey & decide**, usually via a focused tooling review; end with a verdict in the superpower roadmap doc.
2. **Doc**, add `docs/tooling/<tool>.md` with install + sample CLI + integration point + open questions.
3. **Install script**, extend `tools/recommended/install-{cheap,medium,heavy}.sh` with the new install (pin version where stable, leave a "or latest" comment otherwise).
4. **Runner**, add `tools/recommended/<tool>/run-on-species.sh.template` for the canonical CLI shape, then promote to `skills/genecluster-superpowers/scripts/run-<tool>.sh` once the runner is concrete.
5. **Quickstart**, add `skills/genecluster-superpowers/references/<tool>-quickstart.md` (300 words or fewer, terse).
6. **Status table**, update this `SKILL.md`'s status table + the `tools/recommended/README.md` status table + `docs/biosymphony-genecluster-superpower-roadmap.md`.
7. **Lessons**, if the tool's adoption codifies a non-obvious lesson (Cytoscape gradient bug, Quarto stub references, etc.), capture it inline in the quickstart and status table so future readers see it without external context.

When a tool gets ADOPTED (installed, integrated, used in production), promote its row in the status table from "foundation" to "✓ ADOPTED" and update its quickstart's status header. If upstream has cut a newer release, record both the upstream release and the BioSymphony checked pin until a smoke test proves the upgrade.

## Cross-references

- **Tool roadmap with verdict matrices**: `docs/biosymphony-genecluster-superpower-roadmap.md`
- **Per-tool integration docs**: `docs/tooling/<tool>.md` (10 files)
- **Atlas authoring best practices**: `docs/README.md`
- **Quarto rendering runbook**: `docs/README.md`
- **Obsidian view companion**: `docs/biosymphony-atlas-obsidian-walkthrough.md`
- **Pipeline / RunPod dispatch**: `skills/biosymphony/SKILL.md` + `pipeline/genecluster_annotation_direct/`
## Provenance

**Discovery survey:** parallel tool surveys along five angles (sequence/structure search, BGC detection, enzyme function, reporting, comparative-atlas paper styling). Cross-checking picked five high-confidence adds (Quarto adopted; plantiSMASH + cblaster + JCVI + Foldseek + CLEAN queued for adoption when use case lands).

**Test sweep:** Public-safe provider-side checks covered every tool above plus 17 extended tools. Result: 25 checked, 3 parked (cblaster + clinker, CLEAN + HIT-EC, HHblits), 2 gated (PlantCyc, ESM-C 6B). Raw run logs are omitted from this public snapshot; see [`docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md) for the canonical public inventory and re-entry recipes.

**Freshness check:** Verified current release endpoints for the explicitly pinned tools. Corrections applied here: plantiSMASH is upstream 2.0.4 with a BioSymphony v7 boot recipe rather than upstream "v7"; antiSMASH current line is 8.0.4; local-only pins for clinker, JCVI, igv-reports, and Cytoscape.js were refreshed.

**Cloud-runtime forward research: 2026-05-11.** Provider-portability reference docs for AWS / GCP / neocloud live at `docs/cloud-runtimes/`. Result: RunPod stays default for both CPU and GPU; clear exceptions documented (NCBI-bandwidth-bound work -> GCP, formal-review work -> AWS, large-scale H100 training -> CoreWeave).

This skill and the linked inventory are durable shortcuts. Future iterations can consult this skill, read the inventory, and pick the right starting point.
