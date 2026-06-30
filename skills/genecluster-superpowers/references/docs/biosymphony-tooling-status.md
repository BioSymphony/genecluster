# BioSymphony tooling status: canonical inventory

**Scope:** every bioinformatics and reporting tool considered, validated, parked, shelved, gated, or skipped for the BioSymphony GeneCluster skill. This is the **single source of truth** for tool status. The roadmap doc (`biosymphony-genecluster-superpower-roadmap.md`) captures the rationale and priority order for each tool; this doc captures the current validated state.
**Freshness policy:** validated BioSymphony pins are not automatically changed just because an upstream project cuts a new release. Upgrade only after a smoke test proves the same output contract, then update the row below and the mirror docs in `skills/genecluster-superpowers/` and `tools/recommended/`.

**Counts:** 25 validated · 3 parked · 8 shelved-untested · 2 gated · ~10 skipped

## Expansive next-tooling addendum

A broader tooling review looked beyond pin freshness and asked which new tools, repos, databases, and runtime patterns would make the BioSymphony GeneCluster workflow more useful. The durable shortlist lives in [`biosymphony-next-tooling-radar.md`](biosymphony-next-tooling-radar.md).

Headline additions to consider for future smoke flights:

- **Stage 0 acquisition:** NCBI Datasets adapters, `nf-core/fetchngs`, SRA/ENA/GWH metadata normalization, PubPlant, `ffq`, and `pysradb`.
- **Annotation / cluster cards:** AGAT plus `pyGenomeViz`; keep Scan Cluster as high-fit but blocked until a public runnable repo/package is confirmed. GATOR-GC, BGC-QUAST, BGC-Prophet, BGCFlow, BiG-SCAPE 2 / BiG-SLiCE 2, IGUA, CHAMOIS, FunBGCeX, PanBGC, PGAP2, and chatBGC are radar-only additions for targeted cluster windows, caller comparison, pangenome context, review interfaces, and microbial/fungal expansion.
- **Plant evidence:** PMN 17 / PlantCyc, PGDD 2.0, Gramene Plants, Ensembl Plants release 62, PlantPan, CoExpPhylo, ATTED-II, LOTUS, GNPS2, MEANtools, Rhea, and RetroRules 2026.
- **Structure / docking:** Boltz-2, OpenFold3, P2Rank, fpocket, AF2BIND, GNINA, PoseBench, PoseBusters, and normalized pocket/pose tables.
- **Dossiers:** Workflow Run RO-Crate / Process Run Crate, Data Package v2, `check-jsonschema`, Observable Framework, igv-reports/JBrowse, Molstar/Nightingale.
- **Runtime:** RunPod REST + network-volume + S3-compatible artifact pulls, `rclone`/`s5cmd`, Nextflow/Wave/Fusion as a future portability layer, Snakemake/Apptainer for HPC portability, A2A/MCP/Agents SDK handoff patterns as interface references, and dstack/SkyPilot only for overflow experiments.

These are **not validated rows** yet. Promote only after a smoke run creates the output contract named in the radar doc.

## Upstream freshness audit

These are the version-sensitive tools with explicit pins in this repo. Current upstream releases were checked against project release endpoints; rows marked "same" need no repo change beyond this audit note, while rows marked "newer upstream" keep their validated BioSymphony pin until a smoke test upgrades the contract.

### Core pinned tools

| Tool | Current upstream | BioSymphony validated / pinned state | Action |
|---|---:|---|---|
| antiSMASH | 8.0.4 (2025-09-05) | antiSMASH 8 cookbook pattern | Same; track as 8.0.4-compatible, smoke before changing cookbook artifacts. |
| plantiSMASH | 2.0.4 (2025-10-25, canonical org `plantismash/plantismash`) | 2.0.4 with the validated v7 boot recipe | Same; do not describe "v7" as an upstream release, it is the internal boot iteration that fixed the install/runtime path. Older `kblin/` and `satria-ks/` fork paths now 404. |
| DeepBGC | 0.1.31 (PyPI + bioconda; upstream `Merck/deepbgc` GH 0.1.29 / 2021 moribund) | 0.1.31 via bioconda | Same; PyPI/bioconda carry the maintained builds. |
| Quarto CLI | 1.9.37 (stable; 1.10.x in pre-release, no 2.0) | 1.9.37 | Same; keep pin. |
| MMseqs2 | 18-8cc5c (bioconda 18.8cc5c-0) | 18 / iterative-profile settings | Same major release; keep recipe. |
| Foldseek | 10-941cd33 (bioconda 10.941cd33-1) | 10 / ProstT5 search | Same release; keep recipe. |
| cblaster | 1.4 (2025-10-28; adds ClusteredNR support) | 1.4.0 | Same package age; parked on GenBank input shape. ClusteredNR is a new re-entry option, see parked row. |
| clinker | 0.0.32 (2025-12-22) | 0.0.31 minimum in old local scripts | Bumped local-only minimum to 0.0.32 (still latest). |
| JCVI | 1.6.5 (PyPI 2026-03-31; bioconda 1.6.5-0) | 1.4 minimum in old local scripts | Bumped local-only minimum to 1.6.5; RunPod validation during validation testing. **Note: JCVI ships GitHub tags only, no GitHub Releases. verify via PyPI / bioconda, not the GH `/releases` endpoint.** |
| MIBiG | 4.0 (2025-01-06; no 4.1 cut) | 4.0 | Same; keep recipe. |
| igv-reports | 1.16.2 (2026-04-01) | 1.16.0 minimum in old local scripts | Bumped local-only minimum to 1.16.2. |
| Cytoscape.js | 3.33.3 (2024-04-29) | 3.30.2 in old frontend snippets | Bump snippets to 3.33.3 when next pathway-viewer chapter is touched. |
| IQ-TREE | bioconda default now resolves to **3.1.1** (upstream 3.1.2 / 2026-05-07); IQ-TREE 2.0.6 (2024-06) still installable via `iqtree=2.*` | not pinned; campaigns ran on 2.x via bioconda | **Drift flag.** Any new `mamba install iqtree` silently jumps major version. `-nt AUTO` still applies on 3.x; pin `iqtree=2.*` if reproducing a 2.x-era result. |
| Pfam-A (HMMscan target) | 38.1 (2026-01-13; 37.4 → 38.0 → 38.1 between Jun 2025 and Jan 2026, +1.7M sequences, +1.9k families) | 37.x at the time of validation | **Reproducibility flag.** Fresh HMMscan runs auto-pick up the bigger DB. Past validation outputs were on 37.x. Pin DB release in supplementary if reproducing. |
| InterProScan | 5.77-108.0 (2026-01-29; bundles Pfam 38.x) | 5.x at the time of validation | Same family; new release ships Pfam 38, so re-runs are consistent with the Pfam flag above. |

### Frozen-upstream (no movement since pin)

These tools have not cut a meaningful release in >=12 months, so nothing to do, listed here so future operators do not waste a fresh review pass on them.

| Tool | Last upstream movement | Notes |
|---|---|---|
| HMMER | 3.4 (2023-08-15) | Static; bioconda ships 3.4. |
| MAFFT | 7.526 (2024-04) | No movement in >2 years. |
| fair-esm (PyPI) | 2.0.0 (2022-11-01) | Library unmaintained; PyTorch 2.6 `weights_only` compatibility patch required. |
| ESM-2 650M weights (HF) | safetensors 2023-03-21 | Weights frozen. |
| ColabFold | 1.6.1 (2024-03-17) | `--af3-json` adds AF3-compatible input emission; core backend still AF2. |
| CLEAN | 1.0.1 (2023-03-31) | Release-lite; definitively parked after validation attempts. |
| HHsuite3 | 3.3.0 (2020-08-25) | Unchanged ~5.5y. |
| DeepEC / ECPred | DeepEC 2019-08-07 / ECPred 1.1 2018-12-19 | Validated as fallback EC predictor; will not move upstream. |
| EnzymeMap | 2024-04-11 commit (no releases) | Stable. |
| DiffPaSS | 0.2.0 (2024-05-15) | Stable. |
| TM-align | pre-existing binary; zhanggroup hosting redirects | No upstream cadence. |

### Supporting libraries (used in atlas `scripts/` and rendering: not validated tools per se)

| Lib | Latest | Used at | Pinned? |
|---|---|---|---|
| openpyxl | 3.1.5 (2024-06-28) | `.runtime/atlas-*/scripts/build-readme-sheets.py`, `add-sequences-to-sheets.py`, post-process scripts | No, use latest via `pip install openpyxl` |
| matplotlib | 3.10.9 (2026-04-24) | atlas figure generators (`draw-fig5.py`, `draw-fig15-cost.py`) | No |
| pyGenomeTracks | 3.9 (2024-05-06 GH / 2024-07-10 PyPI) | per-species static cluster figures | No |
| BLAST+ (laptop, Homebrew) | 2.17.0+ (2025-07) | Stage-2 paralog inventory via `makeblastdb` + `blastp` | No, `brew install blast` |

---

## Ecosystem scan

A tooling review swept the BGC / PLM / structure-prediction / EC / plant-2°-met / atlas-authoring ecosystems for recent releases, repos, and papers. Full table + sources documented separately. The candidates below are the ones that genuinely fill a gap in the current atlas pipeline.

### Parked-slot unblockers (highest priority)

| # | Candidate | Date | Unblocks | Verdict | Smoke cost |
|---|---|---|---|---|---|
| E1 | **Scan Cluster** (bioRxiv 2026-04-29, [link](https://www.biorxiv.org/content/10.64898/2026.04.29.721675v1)) | 2026-04 | **cblaster + clinker parked slot.** Database-independent multi-genome conserved-cluster finder; works directly on protein FASTA + GFF (no GenBank input blocker); outputs clinker-ready. Validated by authors vs antiSMASH + DeepBGC. | strongly recommend smoke | small CPU pod, ~1 h |
| E1-alt | **cblaster ClusteredNR** (1.4.0) |. | ClusteredNR mode against NCBI's clustered NR DB. **Note:** BOTH config fixes baked in (`--query_file` + `[cblaster]` section). BLAST stage completed: thousands of hits returned across the BIA query panel vs NR at e≤1e-5/id≥30%/cov≥50%. Real biological signal. Died on IPG efetch (HTTP 400) because `api_key` field was empty in config.ini. v7 = one-line fix (populate api_key from your env). | ✓ BLAST validated, IPG one-line fix away | small CPU pod + key |
| E2 | **HIT-EC** (Nat Commun 2026, art. [s41467-026-68727-3](https://www.nature.com/articles/s41467-026-68727-3)) | 2026-04 (peer review) | **CLEAN + HIT-EC parked slot. VALIDATED on canonical FASTA.** High accuracy at EC1, dropping at EC3 and EC4, on a small BIA panel. An earlier "OOD" claim was traced to an accession-mapping bug. Calibrated abstention works on novel + shuffled inputs. Two failure modes named: NCS reclassification artifact, non-enzymes (ACT7) confident false positives. | ✓ validated | small CPU pod, ~5 min |
| E3 | **EnzPlacer** ([`drxiangma/EnzPlacer`](https://github.com/drxiangma/EnzPlacer)) + **Enzymm** ([`rayhackett/enzymm`](https://github.com/rayhackett/enzymm), bioRxiv 2026-04-24) | 2026-02 + 2026-04 | CLEAN-parked alternative path: EnzPlacer predicts EC1-3 for proteins outside training corpus (the niche we hit constantly); Enzymm matches 6,780 M-CSA 3D catalytic-site templates for interpretable active-site rationale. **Note:** install paths validated. Actual CLI is `scripts/infer_knn.py` and requires precomputed ESM-1b embeddings for query + reference. Time-to-first-prediction: roughly 3 min ESM-1b precompute + infer_knn on a small CPU pod. | partial. install ✓, CLI documented for next iteration | small CPU pod, ~10 min combined |

### New backends / replacements for validated tools

| # | Candidate | Date | Replaces / extends | Verdict | Smoke cost |
|---|---|---|---|---|---|
| E4 | **Protenix-v2** ([`bytedance/Protenix`](https://github.com/bytedance/Protenix), Apache-2.0) | 2026-02 | ColabFold AF2 backend. First fully open-source structure predictor matching/beating AF3 at same data/compute. Supports protein + DNA + RNA + ligand. ColabFold-compatible MSA path → ports cleanly into the pipeline. Includes Protenix-Mini for cheap inference + PXMeter benchmark. **Note:** pip install validated on a single mid-range GPU pod, but `fast_layer_norm_cuda_v2` JIT compile fails on first import, leaving the entire `protenix.model` namespace unimportable. Parked until upstream ships wheels OR a custom image with the extension pre-compiled is built. | ✗ blocked. upstream wheel issue | small GPU pod per complex |
| E5 | **FoldMason** ([`steineggerlab/foldmason`](https://github.com/steineggerlab/foldmason), Science 2026) | 2026 | mTM-align hops for multi-structure alignment. Steinegger-lab tool; Foldseek + TM-align based progressive MSTA; SOTA quality at ~100× speed. **Validated:** a small plant BIA PDB panel aligned in a few minutes on a CPU pod. Outputs amino-acid MSA + 3Di-alphabet MSA + interactive HTML viewer + Newick tree. | ✓ validated | CPU, <1 pod-hour |
| E6 | **Foldseek 10 GPU mode + `result2profile`** (already-pinned release; under-utilized features) | 2026-01 release | Pin upgrade for the `foldseek` env. `--gpu 1` gives 4, 37× speedup on GPU pods; `result2profile` builds structural-profile DBs for BIA enzyme families. **Iteration sequence:** v1 needed `makepaddedseqdb` (per error msg). v2 followed error msg verbatim → "needs header info" failure. v3 used BASE db name (no `_ss` suffix) → padded DB produced successfully (218 MB padded SS file). HOWEVER `easy-search --gpu 1 db/afdb-sp_pad` still routes `ungappedprefilter` through un-padded `db/afdb-sp_ss` internally. Workaround: use module-level `foldseek search` instead of `easy-search`. CPU mode unaffected. | ⚠ easy-search blocked, module-level workaround | small GPU pod-hour |
| E4-alt | **Boltz-1** ([`jwohlwend/boltz`](https://github.com/jwohlwend/boltz), MIT) | 2024-late | Protenix-v2 alternative for protein+ligand prediction. PyPI install up through boltz 2.2.1 has numpy<2.0 transitive pin vs mambaforge base numpy 2.4.4 → `ResolutionImpossible`. Fix: pre-install `numpy=1.26.4` via mamba BEFORE `pip install boltz`. **Latest attempt:** numpy pre-pin applied but pod EXITED early; GPU host capacity exhausted, restart blocked by the provider's "not enough free GPUs" gate. Numpy fix unverified. | ⚠ install-fix unverified, GPU capacity blocker | small GPU pod-hour |

### New databases

| # | Candidate | Date | Replaces / extends | Verdict | Smoke cost |
|---|---|---|---|---|---|
| E7 | **RetroRules 2026** (NAR D1799, [link](https://academic.oup.com/nar/article/54/D1/D1799/8373943)) | 2026-Q1 NAR DB issue | Drop-in upgrade for EnzymeMap. 1.17M reaction templates from MetaNetX v4.5 + Rhea 139 + USPTO; radius 0, 10; covers 5,796 EC4 terms; new OpenAPI. Useful for retrosynthesis on alkaloid scaffolds. | strongly recommend | low. HTTP fetch + parse |
| E8 | **MetaNetX v4.5** (NAR D617) | 2026-Q1 NAR DB issue | Data substrate behind RetroRules. New chemical + reaction reconciliation across Rhea / Reactome / BiGG. | monitor | n/a |

### Atlas authoring

| # | Candidate | Date | What it adds | Verdict | Smoke cost |
|---|---|---|---|---|---|
| E9 | **Quarto 1.9 `llms.txt` native emission** ([Quarto 1.9 blog](https://quarto.org/docs/blog/posts/2026-03-24-1.9-release/)) | 2026-03 | Single flag in `_quarto.yml` emits LLM-readable atlas index. makes the rendered book AI-friendly without restructure | worth a smoke test | ~30 min, $0 |
| E10 | **Quarto `pdf-standard` (PDF/A, PDF/UA)** | 2026-03 | Journal-grade accessible PDF for MECA submission. | monitor (only if we target an accessibility-strict journal) | ~1 h |

### Design-program sidecar

| # | Candidate | Date | What it adds | Verdict | Smoke cost |
|---|---|---|---|---|---|
| E11 | **Proto** (`evo-design/proto-language`, `evo-design/proto-tools`; MIT; hosted MCP at `https://mcp.evodesign.org/mcp`) | 2026-06 | Design-program layer for ranked sequence and construct candidates after GeneCluster has reviewed evidence. Proto expresses biological design as sequences or constructs plus generators, constraints, and optimizers. `proto-tools` wraps BLAST, MMseqs2, MAFFT, Foldseek, TM-align, InterProScan, NCBI retrieval, Evo2, ESM-family models, Chai-1, Boltz-2, and structure scorers. Hosted MCP supports discover -> inspect schema -> run -> fetch assets and design -> validate -> inspect metrics. | local public-data smoke for `next_experiment_design` | local CPU first |

### New reference data (Coptis MIA-specific; no campaign planned)

Headline candidates to re-check before any MIA campaign: *Berberis vulgaris* chromosome-level genome + MpAO/MpDAR/MpSOS triad; *Uncaria rhynchophylla* T2T + UrCYP13; Chinese goldthread strictosidine pathway paper (13 functional genes + MsNPF2.6 transporter); interactomics Chinese goldthread paper (6 novel MDRs + charlamine BGC).

### Skip / monitor (called out so future scans don't re-research)

- **ESM-3**, gated weights (Forge / SageMaker only); ESM-C 300M Synthyra remains our PLM workhorse
- **DiffDock-L-Allo / DiffDock v2.2.0**, worth a smoke test *once we have Protenix complexes to dock into*; not the next bottleneck
- **PanBGC + PanBGC-DB**, bacterial/fungal-heavy; relevant only if we extend to fungal endophytes
- **VenusRXN**, no code yet; revisit when public
- **NPannotator**, Type-I PKS NRP/PKS focus; out of plant-alkaloid scope
- **Chai-2**, partner-access only
- **ntSynt-viz**, alternative to JCVI MCScan; current JCVI works, low priority

### How candidates graduate

A candidate becomes a validated row above only after a RunPod smoke run that produces atlas-compatible output. Suggested test recipes for the **strongly-recommend** rows above ship in the test-recipe table at the end of this doc once the operator decides to dispatch them.

---

## ✅ Validated: 25 tools

All of these have been dispatched to RunPod, produced atlas-quality output, and are integrated into `.runtime/<atlas>-quarto-preview/` (the Quarto book) OR documented in a methods chapter / cookbook. Each row links to the canonical task ID + the atlas chapter that consumes its output.

### BGC + synteny (6)

| Tool | Task | Where in atlas | Notes |
|---|---|---|---|
| **antiSMASH 8.0.4** | validated | `methods/<cookbook>.qmd` | B. subtilis 168 demo, ~15 BGCs in ~5 min on a small CPU pod. Cookbook: `docs/biosymphony-antismash-cookbook.md`. **Mambaforge image plus 32 GB RAM floor** (smaller pods OOM at the database load). No `--taxon plants` after v4. |
| **DeepBGC** | validated | cross-species BGC analysis | Tens of BGCs detected across multiple chromosomes on a public plant genome panel. LSTM neural network, no plant-taxon restriction. |
| **JCVI MCScan** | validated | `cross-species/synteny.qmd` | Thousands of pairwise anchors between two public plant species, dotplot PDF on volume. (NGDC GFF parser fallback). |
| **MMseqs2 iterative** | validated | per-species pages | `--num-iterations 3 -s 7.5` adds +8, 21 % homologs vs blastp across the campaign species set. |
| **MIBiG 4.0** | validated | cross-ref target for cluster homology | Curated BGC lookup. |
| **plantiSMASH 2.0.4 (v7 boot recipe)** | validated | `species/<species>.qmd` independent validation | Multiple clusters detected across multiple chromosomes on a public plant genome (mix of alkaloid and saccharide cluster types), with thousands of CDS in the output `final.gbk`. The upstream release is 2.0.4; "v7" is BioSymphony's validated boot iteration. Raw editable installs and some Docker paths hit `straight.plugin` discovery failures; use the non-editable source install + v7 recipe. AGPL-3.0+. Private use is fine. |

### Sequence / structure search & PLMs (8)

| Tool | Task | Where in atlas | Notes |
|---|---|---|---|
| **Foldseek + ProstT5** | validated | `cross-species/fact-check-addendum.qmd` upgrade | Thousands of PDB structural hits returned on a public plant query set. AFDB-Plants pre-staged on volume. |
| **ESM-C 300M (Synthyra/ESMplusplus_small)** | validated | `<deep-dive>.qmd` | Drop-in for restricted ESM-C 6B. (`_dynamo` config patch needed for torch 2.4, 2.6). |
| **ESM-2 650M** | validated | `<deep-dive>.qmd` | Higher-resolution PLM follow-up. |
| **HMMER / HMMscan Pfam-A** | validated | `<deep-dive>.qmd` | `p86-hmmscan-table.tsv`. |
| **InterProScan** | validated | `<deep-dive>.qmd` | Per-candidate domain calls. |
| **TM-align / mTM-align** | validated | `<deep-dive>.qmd` | Structural-distance alternative to Foldseek. |
| **MAFFT** | validated | `<deep-dive>.qmd` | `p86-all.aln.fa` + concentric-ring sequence-similarity network figure (`figures/p86-sequence-network.{png,svg}`). |
| **IQ-TREE** | validated | `<deep-dive>.qmd` | CYP80 phylogenetic placement, `p82-cyp80-tree.contree`. |

### Structure prediction (1)

| Tool | Task | Where in atlas | Notes |
|---|---|---|---|
| **ColabFold** | validated | `<deep-dive>.qmd` | Candidate PDBs at `p84a-pdb-urls.json` + substrate-pocket analysis. |

### Enzyme function + pathway (5)

| Tool | Task | Where in atlas | Notes |
|---|---|---|---|
| **P450Rdb** | validated | `cross-species/p450-classification.qmd` | 3 BIA queries match curated P450s at 100 % identity. (FASTA pre-clean). **Availability flag:** the SNU host (`p450.riceblast.snu.ac.kr`) returned a TCP timeout during validation. May be transient, but if a re-run needs the FASTA, mirror the validated copy on the provider volume instead of fetching live. |
| **KEGG mapper / KAAS** | validated | `<deep-dive>.qmd` | KO assignment + map.00950 BIA biosynthesis. |
| **EnzymeMap** | validated | `<deep-dive>.qmd` | bisBIA radical-coupling reaction-template match. |
| **DiffPaSS** | validated | `<deep-dive>.qmd` | Co-evolving paralog pairing for BIA-P450 family partners. |
| **DeepEC / ECPred** | validated | (CLEAN alternative) | EC labels when CLEAN is the alternative we wanted but couldn't wire. |

### Reporting / visualization (5)

| Tool | Task | Where in atlas | Notes |
|---|---|---|---|
| **Quarto 1.9.37** | adopted | atlas-wide | Quarto book at `.runtime/<atlas>-quarto-preview/`. Current upstream release. |
| **Cytoscape.js 3.33.3** | adopted | your pathway-completion viewer | Interactive pathway viewer with Fit/Reset/zoom controls. |
| **igv-reports** | validated | per-species | BIA clusters as IGV HTML. |
| **pyGenomeTracks** | validated | per-species | Static publication figures of BIA clusters. |
| **Quarto Dashboards** | validated | an example deep-dive dashboard | Interactive deep-dive. |

---

## ⛔ Parked: 3 tools (install proven, runtime blocker)

These got onto a RunPod pod and exercised their install path, but a downstream blocker stopped them from producing atlas-quality output. **Each has a documented re-entry recipe**, the next operator picks up at the recipe, not at "what's the install path?"

| Tool | Task(s) | Blocker | Re-entry recipe |
|---|---|---|---|
| **cblaster + clinker** | validated. | Needs GenBank input, but the campaign species ship as protein FASTA + GFF only. Test validated parked; a retry hit a transient provider proxy 502. | (1) Stage GenBanks per species via NCBI Datasets CLI: `datasets download genome accession GCA_xxx --include gbff`. (2) Build cblaster local DB from those. (3) Run cblaster query against the per-species DB; pipe clusters to clinker for SVG. Effort: small CPU pod + 2 h author time. **New re-entry path (cblaster 1.4, 2025-10-28):** upstream added **ClusteredNR** support. `cblaster search --mode remote --database nr_cluster_seq` queries NCBI's clustered NR without needing local GenBanks. Trades a network round-trip for the GFF→GBK step, so the parked blocker may now be sidesteppable for a smoke test. clinker 0.0.32 (2025-12-22) still latest. **Alternative tool (2026-04-29 ecosystem-scan candidate E1):** **Scan Cluster** ([bioRxiv](https://www.biorxiv.org/content/10.64898/2026.04.29.721675v1)) is a database-independent multi-genome conserved-cluster finder that operates directly on protein FASTA + GFF (no GenBank step). Validated by authors against antiSMASH + DeepBGC. Outputs clinker-ready. Recommended for the next smoke flight at this slot. |
| **CLEAN + HIT-EC** | validated. failed on HIT-EC's broken `requirements.txt` (`python==3.9.16` literal that pip cannot satisfy). used modern pins + a sanitized inference helper; | Original blocker: `CLEAN_infer_fasta.py` wrapper hard-codes `./data/` cwd and shells to `esm/scripts/extract.py` whose child Python loses the conda env. Four boot revs across two sessions. Env builds clean, the wrapper is the problem. Secondary blocker found: HIT-EC's own `requirements.txt` is unusable. | Three independent paths now exist: **(a) HIT-EC-solo via a sanitized inference helper**, skip HIT-EC's broken `requirements.txt`, install modern pins (`torch==2.7.0+cpu`, `pytorch-lightning>=2.4`, `scikit-learn`, `keras-preprocessing`, `biopython`), download `model.ckpt` v2.0.0, and run a sanitized HIT-EC inference boot recipe. Effort: small CPU pod, ~7-10 min wall. **(b) EnzPlacer + Enzymm pair** (E3). Fills the same CLEAN-parked niche for EC1-3 + interpretable catalytic-site templates if HIT-EC v2 also fails. **(c) DeepEC / ECPred** (validated) is the validated fallback for the BIA atlas. The CLEAN wrapper hack (pre-compute ESM-1b embeddings + call `CLEAN.infer.infer_maxsep` directly) remains documented but path (a) is cheaper. |
| **HHblits / HHsuite3** | validated. | An 8 GB RAM CPU pod OOMs during the PDB70 stage. HHsuite ffindex memory-maps to ~10 GB+. | (1) Pre-stage pod: download PDB70 to provider volume. (2) Inference pod: 16+ GB RAM CPU pod, run HHblits against the pre-staged PDB70. Two-pod split is mandatory; single-pod won't fit. MMseqs2 + Foldseek already cover divergent-homolog space, so HHblits is "nice-to-have" not "must-have". Effort: small CPU pod + 2 h author time. |

---

## ❓ Shelved (untested, no license needed): 8 tools

On the roadmap, license-free, but never dispatched. Listed here so a future operator knows what's already triaged. Each row carries the roadmap verdict + the effort estimate so the decision to validate is one read away.

| Tool | Roadmap verdict | Effort to validate | Why we'd want it |
|---|---|---|---|
| **MultiQC** | OPTIONAL | small CPU pod, ~20 min | Appendix-grade QC dashboard across the campaign species set's raw inputs. Single `pip install`. |
| **JBrowse 2** | DEFER | small CPU pod, ~1 h | Synteny + multi-track browser; better than igv-reports for >5 tracks. |
| **SaProt 1.3B** | DEFER | small GPU pod, ~1 h | Alternative PLM (uses Foldseek 3Di structural-token vocabulary); gives PLM-ensemble diversity vs ESM-C / ESM-2. |
| **GraphEC** | OPTIONAL | ~$1 GPU (needs ESMFold pipeline first) | GCN on ESMFold structures + active-site head; F1 0.6131 on Price-149. Heaviest of the three EC predictors. |
| **AlphaFill** | DEFER | small CPU pod, ~1 h | Transplants PDB ligands into ColabFold candidate models. Useful if reviewers want substrate-pocket evidence beyond TM-align. |
| **DiffDock-L / GNINA 1.3 / SurfDock** | DEFER (docking suite) | ~$1.50 GPU, 4 h | Dock reticuline / scoulerine into our ColabFold models. Only if reviewers ask for substrate-pocket evidence. |
| **EnzymeFlow / GENzyme / CLIPZyme** | DEFER (research-grade) | unknown | Generative substrate-pocket matching from reaction SMILES. No plant 2°-met benchmark yet. |
| **AlphaFast** | DEFER | small GPU pod + setup | Local AF3 alternative. Foldseek + ProstT5 obviates unless depositing structures. |

---

## ⏸️ Gated: 2 tools (license / API key required)

| Tool | Gate | What we did instead |
|---|---|---|
| **PlantCyc / PMN 16** | Academic license required (manual application) | KEGG mapper / KAAS (validated) covers pathway-completion baseline. Re-evaluate at license-review time if reviewers want PlantCyc-specific identifiers. |
| **ESM-C 6B (open-weights gated)** | Forge API key required from EvolutionaryScale | ESM-C 300M (Synthyra/ESMplusplus_small) used as drop-in (validated). For higher capacity, ESM-2 650M (validated) was the chosen alternative. |

---

## ⛔ Skipped: wrong domain or superseded

These are intentionally not on the test list. Listed here so future operators don't propose them.

| Category | Tools | Reason |
|---|---|---|
| Superseded | antiSMASH 7.1 | antiSMASH 8 supersedes for bacteria/fungi; plantiSMASH + DeepBGC cover plants. |
| Wrong domain | CYPstrate, CypReact, DeepP450 | Trained on human drug-metabolism CYPs; do not transfer to plant CYPs. |
| Tool-class duplicate | Streamlit, Shiny, Reflex, Datapane | Quarto + Quarto Dashboards cover the atlas-publication and interactive-dashboard needs without a server-required stack. Datapane was defunct as of 2023. |
| Tool-class duplicate | Snakemake / Nextflow report | Atlas already renders via Quarto; orchestrator-native reports add no value here. |

---

## Re-entry quick reference (the one table a returning operator should read)

```
NEED → TOOL → STATUS → STARTING POINT
================================ ================================================ ========= ===========================================
bacterial / fungal BGC detection antiSMASH 8 ✓ docs/biosymphony-antismash-cookbook.md
plant BGC detection plantiSMASH 2.0.4 via v7 boot OR DeepBGC ✓ plantismash: see test plan validated
cross-species cluster homology cblaster + clinker ⛔ parked re-entry recipe above; needs GFF→GBK step
whole-genome macro-synteny JCVI MCScan ✓ .runtime/<atlas>-quarto-preview/cross-species/synteny.qmd
deeper-than-BLAST homology MMseqs2 iterative profile ✓ per-species pages
structure-based homology Foldseek + ProstT5 ✓ cross-species/fact-check-addendum.qmd
even deeper homology (HHM-vs-HMM) HHblits / HHsuite3 ⛔ parked re-entry recipe above; needs 16+ GB RAM CPU pod + PDB70 pre-stage
PLM embeddings ESM-C 300M (Synthyra) OR ESM-2 650M ✓ <deep-dive>.qmd
EC prediction DeepEC / ECPred ✓ validated
EC prediction (alternative) CLEAN + HIT-EC ⛔ parked re-entry recipe above; bypass the wrapper
P450 family classification P450Rdb ✓ cross-species/p450-classification.qmd
KEGG / pathway-completion KEGG mapper / KAAS ✓ <deep-dive>.qmd
reaction-template matching EnzymeMap ✓ <deep-dive>.qmd
co-evolving paralog pairing DiffPaSS ✓ <deep-dive>.qmd
design-program sidecar Proto 🔬 cand docs/tooling/proto.md
domain calls HMMER + InterProScan ✓ <deep-dive>.qmd
phylogenetic placement IQ-TREE ✓ <deep-dive>.qmd
structure prediction ColabFold ✓ <deep-dive>.qmd
structural distance TM-align / mTM-align ✓ <deep-dive>.qmd
multiple sequence alignment MAFFT ✓ <deep-dive>.qmd
atlas rendering Quarto 1.9.37 ✓ docs/README.md
interactive pathway viewer Cytoscape.js ✓ pathway-completion.html
chromosomal browser (interactive) igv-reports ✓ per-species
chromosomal browser (static) pyGenomeTracks ✓ per-species
appendix-grade QC dashboard MultiQC ❓ shelved small CPU pod, ~20 min
deeper PLM ensemble SaProt 1.3B ❓ shelved small GPU pod
substrate docking DiffDock-L / GNINA / SurfDock ❓ shelved ~$1.50 GPU; only if reviewers ask
ligand transplant AlphaFill ❓ shelved small CPU pod
managed pathway DB PlantCyc / PMN 16 ⏸️ gated academic license required
```

---

## Cross-references

**Canonical sources of truth (consult these before this doc when you need the underlying detail):**
- `docs/biosymphony-superpower-test-plan.md`, the original test inventory with per-tool protocol
- `docs/biosymphony-genecluster-superpower-roadmap.md`, the tool roadmap and rationale
- `docs/biosymphony-antismash-cookbook.md`, antiSMASH 8 cookbook (validated)
- `docs/cloud-runtimes/README.md`, when / whether to port any of this to AWS / GCP / neocloud (forward-research only)
- full test log including the parking decisions
- `skills/genecluster-superpowers/SKILL.md`, the invocable skill
- `tools/recommended/README.md`, install scripts + per-tool runner templates
- `.runtime/<atlas>-quarto-preview/`, the Quarto atlas (the actual integrated output)

**Memory entries with non-obvious lessons baked in (consult before re-trying anything parked):**

**How to update this doc when a new tool gets tested:**
1. Move its row to the correct status section (validated → parked → shelved, whichever applies).
2. Add the task ID + atlas chapter (if validated) or re-entry recipe (if parked).
3. Update the count line at the top.
4. If a non-obvious lesson was learned, capture it inline in the row's note so future readers see it without external context.
5. Update the test plan's status line at the same time (the test plan's first paragraph should never lie about state again).
