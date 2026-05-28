# tools/recommended/: install scripts + placeholder runner templates

Idempotent install scripts and placeholder runner templates for the recommended tool stack identified by the superpower-discovery survey.

**Status:** All originally surveyed tools have been dispatched. 4 validated (JCVI MCScan, MMseqs2, Foldseek + ProstT5, P450Rdb) + plantiSMASH validated at upstream 2.0.4 through the BioSymphony v7 boot recipe. 2 parked (cblaster + clinker, needs GFF→GenBank input; CLEAN + HIT-EC . wrapper brittle). The extended testing then validated 17 more tools (DeepBGC, antiSMASH 8.0.4-compatible cookbook pattern, ESM-C 300M, ESM-2 650M, HMMER, InterProScan, TM-align, MAFFT, IQ-TREE, ColabFold, KEGG / KAAS, EnzymeMap, DiffPaSS, DeepEC / ECPred, igv-reports, pyGenomeTracks, Quarto Dashboards). **For the canonical inventory + re-entry recipes, see [`../../docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md).**

The promoted runnable wrappers live under [`../../skills/genecluster-superpowers/scripts/`](../../skills/genecluster-superpowers/scripts/) (each takes a species shorthand as `$1`, exits cleanly with install hint when the underlying tool is missing). The install scripts here are **laptop-targeted**; production-scale runs should use the `genecluster-superpowers` image on the selected remote lane. The install scripts remain for one-off local exploration only. See [`../../docs/tooling/`](../../docs/tooling/) for per-tool integration plans and [`../../docs/biosymphony-genecluster-superpower-roadmap.md`](../../docs/biosymphony-genecluster-superpower-roadmap.md) for the original selection rationale.

## Install scripts (tiered)

| Script | What it installs | Roughly how heavy |
|---|---|---|
| [`install-cheap.sh`](install-cheap.sh) | cblaster, clinker, JCVI, MMseqs2, igv-reports, pip + conda only | A few hundred MB; minutes |
| [`install-medium.sh`](install-medium.sh) | plantiSMASH 2.0.4 source install, MIBiG 4.0 download | A few GB; tens of minutes |
| [`install-heavy.sh`](install-heavy.sh) | Foldseek + ProstT5, CLEAN-Contact, AFDB-SwissProt | Tens of GB + GPU optional; hours |

All scripts:
- Use `set -euxo pipefail`.
- Are safe to re-run (idempotent, they detect existing installs and skip).
- Print a `--version` verification at the end.
- Pin versions where stable (cblaster 1.4.0, clinker 0.0.32, MMseqs2 18-8cc5c, JCVI 1.6.5, Foldseek 10-941cd33, Quarto 1.9.37).
- Use "or latest" comments where the upstream is a moving target.

## Per-tool placeholder runners

| Path | What it would do |
|---|---|
| [`plantismash/run-on-species.sh.template`](plantismash/run-on-species.sh.template) | Run plantiSMASH 2.0.4 against a species genome FASTA/GFF through the validated source-install path |
| [`cblaster/query-cluster.sh.template`](cblaster/query-cluster.sh.template) | cblaster search of a query enzyme set vs the per-species DIAMOND DBs + clinker SVG |
| [`jcvi-mcscan/pairwise-synteny.sh.template`](jcvi-mcscan/pairwise-synteny.sh.template) | JCVI pairwise macro-synteny ribbon between two species |
| [`foldseek/prostt5-search.sh.template`](foldseek/prostt5-search.sh.template) | Foldseek easy-search via ProstT5 sequence-only encoding |
| [`mmseqs2/iterative-profile.sh.template`](mmseqs2/iterative-profile.sh.template) | MMseqs2 `--num-iterations 3` BLAST replacement |
| [`clean-hit-ec/predict-ec.sh.template`](clean-hit-ec/predict-ec.sh.template) | CLEAN inference on cluster candidates → EC labels |

All templates use `{PLACEHOLDER}` markers where actual paths or IDs go. They're deliberately not executable, the file extension is `.sh.template` to make that explicit. Each template documents inputs, outputs, and where its output would feed into the existing pipeline (`pipeline/genecluster_annotation_direct/run.py`, `your downstream postprocess script`, the planned Quarto build).

## Per-tool status table (originally surveyed tools: for the full 25+ tool inventory, see [`../../docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md))

| Tool | Priority | Status | Validating task | Re-entry recipe (if parked) |
|---|---|---|---|---|
| plantiSMASH | ★1 | ✅ **VALIDATED at upstream 2.0.4 via BioSymphony v7 boot recipe** (raw editable install had `straight.plugin` blocker; non-editable source install + recipe works); detects multiple clusters per chromosome on public plant genomes | validated | . |
| cblaster | ★2 | ⛔ **PARKED** . needs GenBank input which we don't have | validated | Stage GenBanks per species via NCBI Datasets CLI, build local cblaster DB, then query |
| clinker | ★2 | ⛔ **PARKED** (paired with cblaster) | validated | Resolves with cblaster |
| JCVI MCScan | ★3 | ✅ **VALIDATED**, thousands of pairwise anchors between two public plant species | validated | . |
| Foldseek + ProstT5 | ★4 | ✅ **VALIDATED**, thousands of PDB structural hits returned on a public plant query set | validated | . |
| MMseqs2 | cheap-add | ✅ **VALIDATED**, +8, 21 % homologs vs blastp | validated | . |
| CLEAN | ★ | ⛔ **PARKED** . `CLEAN_infer_fasta.py` wrapper brittle (4 boot revs). **Alternative validated:** DeepEC / ECPred (validated) | validated | Bypass wrapper; call `CLEAN.infer.infer_maxsep` directly with pre-computed fair-esm embeddings |
| HIT-EC | ★ | ⛔ **PARKED** (paired with CLEAN) | validated | Resolves with CLEAN |
| PlantCyc PMN 16 | cheap-add | ⏸️ **GATED**, academic license required | . | Apply for academic license; KEGG mapper / KAAS (validated) covers pathway-completion in the interim |
| P450Rdb | cheap-add | ✅ **VALIDATED**, 3 BIA queries at 100 % identity. (FASTA pre-clean) | validated | . |
| Cytoscape.js 3.33.3 | cheap-add | ✅ **ADOPTED**, atlas pathway-completion viewer with Fit/Reset controls | validated | . |
| **Quarto 1.9.37** | **★ blessed** | ✅ **ADOPTED**, atlas book renderer for `.runtime/<atlas>-quarto-preview/_book/` | validated | . |

**Also validated in extended extended testing (not in this directory's install scripts):** antiSMASH 8 (validated), DeepBGC (validated), MIBiG 4.0 (validated), ESM-C 300M Synthyra (validated), ESM-2 650M (validated), HMMER (validated), InterProScan (validated), TM-align / mTM-align (validated), MAFFT (validated), IQ-TREE (validated), ColabFold (validated), KEGG mapper / KAAS (validated), EnzymeMap (validated), DiffPaSS (validated), DeepEC / ECPred (validated), igv-reports (validated), pyGenomeTracks (validated), Quarto Dashboards (validated). Also parked: HHblits / HHsuite3 (validated) . needs cpu5g + PDB70 pre-stage split.

**Shelved-but-could-test (license-free, just not key for current work):** MultiQC, JBrowse 2, SaProt 1.3B, GraphEC, AlphaFill, DiffDock-L / GNINA / SurfDock, EnzymeFlow / GENzyme / CLIPZyme, AlphaFast. See [`../../docs/biosymphony-tooling-status.md`](../../docs/biosymphony-tooling-status.md) for effort estimates + re-entry recipes.

## When to actually run an install

Production-scale bio-tool execution should run on a configured remote lane (RunPod by default; AWS / GCP / neocloud documented as forward research in `docs/cloud-runtimes/`). These install scripts remain for one-off local exploration only; the canonical dispatch path for validated tools is the `genecluster-superpowers` image plus per-tool boot scripts generated under ignored `.runtime/` launch folders.
