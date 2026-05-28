# BioSymphony GeneCluster: superpower roadmap (tools + report style)

**Scope:** survey of tools that extend BioSymphony GeneCluster across sequence/structure search, BGC + synteny + cluster-comparative analysis, enzyme function + pathway prediction, and report generation. Use this when deciding what to add to the skill next.

> **For current validated state**, see [`biosymphony-tooling-status.md`](biosymphony-tooling-status.md), which lists the validated, parked, shelved, gated, and skipped tools with re-entry recipes for parked entries. Two corrections worth flagging up front: (1) plantiSMASH is upstream 2.0.4; BioSymphony validated it through the v7 boot recipe after raw installs hit a `straight.plugin` blocker. (2) DeepBGC validated cleanly and is the plant BGC default. antiSMASH 8.0.4 is validated for bacterial / fungal contingency (cookbook: `biosymphony-antismash-cookbook.md`).

---

## Executive summary: high-value adds

Five categories of tool add meaningful capability beyond a baseline BLAST + HMMER + InterProScan stack:

| Priority | Tool | What it adds | Cost | Cross-agent signal |
|---|---|---|---|---|
| **★1** | **plantiSMASH 2.0** | Motif-driven BGC detection (catches plant clusters that anchor-driven 50 kb windowing misses); a large precomputed plant BGC database to cross-reference against | Medium (Docker) | BGC + enzyme function |
| **★2** | **cblaster + clinker** | "Given a query enzyme set, find homologous clusters across species and draw publication-quality synteny ribbons"; closes a common cross-species cluster homology gap | Low (pip) | BGC + reporting |
| **★3** | **JCVI MCScan (Python)** | Whole-genome macro-synteny backbone; the de-facto way to draw chromosome-to-chromosome alignments before zooming to clusters | Low (pip) | BGC + atlas paper styling |
| **★4 (cross-species evidence layer)** | **Foldseek + ProstT5** | Structure-based homology that catches convergent enzymes invisible to BLAST (same fold, <15% sequence identity, different family) | Medium (CPU + Foldseek server or local AFDB-Plants mirror) | Sequence/structure (alone, but high-impact) |
| **★5 → blessed** ✓ | **Quarto 1.9.37 (ADOPTED)** | Replaces a manual Markdown stack with one `_quarto.yml` project rendering to HTML site + PDF + journal-ready MECA bundle. See `docs/README.md`. | Low-medium (install + render) | Reporting (alone, high-confidence solo recommendation) |

**Total integration time estimate**: 1-2 weeks of focused work to add the cheap ones.

---

## Tool integration matrix (all agent recommendations)

### Sequence / structure search

| Tool | Latest | Adds | Plant fit | Cost | Verdict |
|---|---|---|---|---|---|
| MMseqs2 iterative-profile | Release 18, July 2024 (GPU paper Nat Methods 2025) | +10-15% true orthologs at 25-40% identity vs BLAST; 6.4× speedup | yes | Low | **ADD**, drop-in BLAST replacement, biggest sensitivity win without switching to structure |
| Foldseek + ProstT5 | Release 10 + ProstT5 (Heinzinger 2024 NAR-GAB) | Detects convergent enzymes (same fold, different family) at <15% sequence identity | yes | Medium | **ADD (cross-species evidence layer)** |
| ESM-3 / ESM-C 6B / SaProt 1.3B | ESM-C Dec 2024; SaProt ICLR 2024 | Embedding-based homology in twilight zone (<20% id), +8-12% coverage | yes | Medium-high (GPU) | DEFER, no plant 2°-met benchmark yet |
| AlphaFold3 / AlphaFast | AlphaFast bioRxiv Feb 2026 | Local AF3 predictions at modest per-protein cost | yes | Medium | DEFER, Foldseek+ProstT5 obviates unless depositing structures |
| DIAMOND --ultra-sensitive | v2.1.x | BLAST-grade results, 80-360× faster | yes | Trivial (in stack) | KEEP, useful baseline; doesn't close the divergence gap |
| HHblits / HHsuite3 | 2019 (still standard) | 50-100% more sensitive than PSI-BLAST profile builder | yes | Low | OPTIONAL, augment HMMER profiles |

### Biosynthetic gene cluster (BGC) + synteny

| Tool | Latest | Adds | Plant fit | Cost | Verdict |
|---|---|---|---|---|---|
| plantiSMASH 2.0 | bioRxiv Oct 2025; ScienceDirect 2026 | Motif-driven cluster detection across 12 BGC types; large precomputed plant BGC database | yes (de-facto) | Medium (Docker) | **★ ADD** |
| cblaster + clinker | cblaster v1.3 (2023), clinker v0.0.30 (2024) | Cross-species cluster homology + publication-quality synteny ribbons; CAGECAT webserver for no-install | yes | Low (pip) | **★ ADD** |
| JCVI MCScan (Python) | iMeta 2024 | Pairwise/multi-species macro-synteny; gold standard for plant comparative genomics | yes | Low (pip) | **★ ADD** |
| MIBiG 4.0 | NAR Dec 2024 | Thousands of curated BGCs incl. plant alkaloid; cross-reference target for cblaster | yes | Low (DB lookup) | ADD, cheap, useful |
| BiG-SLiCE 2.0 / BiG-FAM | NatCommun 2026 | Hierarchical clustering of BGCs into families | maybe (microbial-biased) | Medium | DEFER until plant BGC family DB matures |
| DeepBGC / GECCO / BGC-Prophet | 2024-2025 | ML-based BGC detection | no (poor plant performance) | Medium | SKIP, wait for plant-trained models |
| antiSMASH 7.1 | June 2024 | Bacterial/fungal BGC detection | no | Low | SKIP for plant work, use plantiSMASH instead |

### Enzyme function + pathway prediction

| Tool | Latest | Adds | Plant fit | Cost | Verdict |
|---|---|---|---|---|---|
| CLEAN / CLEAN-Contact | Yu Science 2023; Comm Biol 2024 (CLEAN-Contact) | Contrastive-learning EC prediction, beats BLASTp/DeepEC; structure-augmented in CLEAN-Contact | yes (off-label) | Low (Python + GPU helpful) | **★ ADD** for EC labels on novel candidates |
| HIT-EC | NatCommun 2026 | 4-level hierarchical transformer with calibrated abstention | yes | Low | **★ ADD as alternative** to CLEAN, especially for novel enzymes (abstention is critical) |
| GraphEC | NatCommun Sep 2024 | GCN on ESMFold structures + active-site head; F1 0.6131 on Price-149 | yes | Medium (needs ESMFold) | OPTIONAL, heaviest of the three |
| PlantCyc / PMN 16 | NAR 2025 | 155 species, 1,200 pathways, 1.3M enzymes; explicit BIA pathways for Papaver and Coptis-relatives | yes (best plant fit) | Low (DB) | **★ ADD** for "% complete vs canonical pathway" panel |
| P450Rdb | Database 2023 | Hand-curated 1,600 reactions / 590 P450s across 200 species incl. plants | yes | Low (DB) | **★ ADD** for plant P450 reference (CYP71B/CYP80/CYP719 anchors) |
| KEGG mapper / KAAS / BlastKOALA | 2007-2023 | KEGG ortholog assignment; map.00950 BIA biosynthesis canonical | yes | Low (web) | ADD, pathway-completion baseline |
| EnzymeMap | Chem Sci 2023 | Atom-mapped reactions; substrate matching by reaction-template fingerprint | maybe | Medium | OPTIONAL, reaction-level ranking layer |
| DiffPaSS | Bioinformatics 2025 | Differentiable mirror-tree paralog pairing | yes | Low | OPTIONAL, for finding co-evolving pathway anchors |
| CYPstrate / CypReact / DeepP450 | 2018-2024 | P450 substrate prediction | NO (human drug-met only) | Low (web) | SKIP, wrong domain for plant CYPs |

### Coevolution + structure-based docking (all DEFER)

| Tool | Latest | Adds | Verdict |
|---|---|---|---|
| AlphaFill | Nat Methods 2023 | Ligand transplant from PDB to AF models; works for OMTs, weak for novel CYP71B | DEFER unless depositing structures |
| DiffDock-L / GNINA 1.3 / SurfDock | J Cheminform 2025 | Score substrates into AF2 pockets | DEFER |
| EnzymeFlow / GENzyme / CLIPZyme | arXiv 2024 | Generate/match catalytic pockets from reaction SMILES | DEFER (research-grade) |

### Reporting + dashboards + visualization

| Tool | Latest | Adds | Cost | Verdict |
|---|---|---|---|---|
| **Quarto 1.9.37** | brew-installable, 1.9.37 (Mar 2026) | Pandoc-based; one `.qmd` source → HTML site + PDF + Word + MECA bundle. Replaces a manual Markdown stack. | Low-medium | ✓ **ADOPTED. blessed report path** |
| clinker (clustermap.js) | 2024 | Cluster-to-cluster orthology coloring HTML | Low | **★ ADD** (also in BGC stack) |
| Cytoscape.js | 2023 PMC9889963 | Embed pathway as SBGN graph with click-to-highlight enzymes | Medium (write JSON once) | **★ ADD** for pathway-completion diagrams |
| igv-reports | v1.16.0 (Sep 2025) | Self-contained HTML embedding igv.js for cluster track views | Low (small BED converter) | ADD, analyst-favorite |
| pyGenomeTracks | 3.9 | Static publication-figure path (matplotlib backend) | Low | ALTERNATIVE to igv-reports for static figures |
| Quarto Dashboards | GA 1.4 (Jan 2024) | `format: dashboard` over notebooks for click-through queries | Low | OPTIONAL (interactive add-on) |
| Streamlit / Shiny / Reflex | Various 2024-2025 | Server-required interactive dashboards | Low-high | SKIP for a one-off atlas; Quarto is static-site sufficient |
| MultiQC | v1.27+ (2025) | QC aggregation with custom_content YAML | Low | OPTIONAL, appendix only |
| Snakemake/Nextflow report | Various | Workflow-native reports | Low | SKIP, not worth orchestrator adoption |
| JBrowse 2 | Genome Biology 2023 | Synteny views and large-track parallelism | Medium | DEFER unless adding many tracks |
| Datapane | (defunct 2023) |, |, | SKIP |

---

## Comparative-atlas paper styling: what good 2024-2026 papers look like

This section is useful for any team building a comparative gene-cluster atlas. The conventions below are the de-facto reference in the recent plant secondary-metabolism literature.

### 5 reference papers (de-facto comparative-genomics atlas templates)

| Ref | Paper | Why it's the template |
|---|---|---|
| 1 | Shan, Zhou, Zhu et al. 2025 *Nat Commun* 16:7669 ([10.1038/s41467-025-63175-x](https://www.nature.com/articles/s41467-025-63175-x)) | Cross-angiosperm BIA atlas. Phylogeny + pathway + in vitro assays + micro-synteny blocks + reaction-coupling-driven convergence framing |
| 2 | Sun et al. 2024 *Sci Adv* eads3596 ([10.1126/sciadv.ads3596](https://www.science.org/doi/10.1126/sciadv.ads3596)) | Convergent berberine biosynthesis. Fig 1 hybrid: pathway + 17-species phylogeny + metabolite heatmap + MALDI-MSI tissue distribution |
| 3 | Li et al. 2024 *Hortic Res* uhae203 ([10.1093/hr/uhae203](https://academic.oup.com/hr/article/11/9/uhae203/7718721)) | Houttuynia decaploid genome. **Fig 4 master layout** = pathway + tissue PCA + cross-species circle-size phylogeny + tissue heatmap on one page |
| 4 | MIA C3-stereo 2025 *Nat Commun* ([s41467-025-65543-z](https://www.nature.com/articles/s41467-025-65543-z)) | Ancestral-cluster reconstruction template across 6+ Gentianales species |
| 5 | Astilbe chinensis 2025 *Nat Commun* ([s41467-025-64842-9](https://www.nature.com/articles/s41467-025-64842-9)) | Variable-cardinality synteny matrix across 6 species; precedent for any cross-family pathway-step gradient |

### Required / Strong / Bonus elements

- **Required**: dated phylogeny, KEGG-style pathway diagram, per-species pipeline metrics table (genome size, BUSCO, ploidy, hit-counts).
- **Strong**: cross-species synteny block of conserved cluster regions; identity-matrix heatmap of pathway-step conservation. The Houttuynia 7-layer Circos and Astilbe variable-cardinality synteny table are canonical conventions.
- **Bonus**: in vitro assay for at least one validated enzyme; HPLC/LC-MS metabolite confirmation; MALDI-MSI tissue localization; transgenic/VIGS knockdown.

### Anti-patterns to avoid

1. **Overstating "absence"** from negative BLAST. Negative BLAST against a query set you compiled is not biological absence; it is intake-blocked. The skill's intake-blocked claim-ceiling pattern exists to prevent this.
2. **Convergence claims without ancestral-state reconstruction**, add ancestral-state reconstruction across orders before any convergence claim ships.
3. **Tissue heatmaps without controls**, every recent paper co-plots ACT/GAPDH-equivalents; downstream reporting should too.
4. **Single-species pathway fig + multi-species synteny appendix split**, combine pathway and synteny per-species per Houttuynia Fig 4.
5. **Decaploid analyses without subgenome phasing**, Houttuynia AAAAABBBBB phasing is now expected.

---

## Proposed report-style template

Use this as a starting structure when building a Quarto-based comparative-atlas report.

```
.runtime/<atlas>-final-deliverable/
├── _quarto.yml ← Quarto project config
├── index.qmd ← Atlas landing page
├── species/
│ └── <species>.qmd ← one per-species page
├── cross-species/
│ ├── <gradient>.qmd ← variable-cardinality synteny per Astilbe convention
│ ├── pathway-completion.qmd ← Cytoscape.js pathway diagram
│ ├── synteny-blocks.qmd ← clinker cluster figures + JCVI macro-synteny
│ └── fact-check-addendum.qmd ← audit verdict + reframing
├── methods/
│ ├── pipeline.qmd ← run.py + enrichment + DeepSig
│ ├── reproducibility.qmd ← versions, configs, hashes
│ └── caveats.qmd ← known limitations
├── data/ ← bundled deliverables (per-species xlsx)
└── _build/
 ├── html/ ← rendered static site
 └── pdf/atlas.pdf ← journal-ready PDF
```

### Per-species page template (`<species>.qmd`)

```yaml
---
title: "<Species name>, <Family> / <Order>"
subtitle: "Pathway candidate discovery"
format:
 html:
 toc: true
 code-fold: true
 embed-resources: true # single-file HTML
 pdf:
 documentclass: article
---
```

Structure:
1. **Headline panel**, pipeline metrics box (proteome size, hits, controls verdict, signal-peptide rate)
2. **Pathway diagram** (Cytoscape.js embed) colored by per-step coverage in this species
3. **Per-query top-hits table** (auto-generated from biology-interpretation.md)
4. **Cluster discoveries**, clinker SVG embed for each cluster plus neighbor list
5. **Enrichment summary**, TM/signal/subcellular distributions vs other atlas species
6. **Caveats**, intake-blocked query notes go here when applicable
7. **Raw-data link**, points to the per-species summary dir plus xlsx

### Cross-species page template

A typical cross-species page combines:
1. **Astilbe-style variable-cardinality synteny table**, species × pathway-step matrix with color-encoded identity
2. **clinker SVG**, target cluster plus cross-species homologs
3. **JCVI MCScan macro-synteny**, chromosome-block ribbon diagram
4. **Cytoscape.js pathway diagram**, pathway with per-species coverage colored on each enzyme

### Atlas index template (`index.qmd`)

1. **Atlas hero**, per-species figure (Houttuynia Fig 4 layout)
2. **Pipeline metrics aggregate table**, one row per species
3. **Headline findings**, short bullet list
4. **Pressure-test caveats**, link to fact-check addendum
5. **How to navigate**, pointer to per-species pages, methods, data
6. **Reproducibility**, Zenodo DOI placeholder, repo URL, version pinning

### Fact-check addendum template (auto-generated from agent JSON)

A multi-agent fact-check produces verdict matrices renderable via Quarto:
- Component-by-component verdict table
- Attack-vector strength matrix
- Honest-reframing abstract

This becomes a templated `.qmd` that takes agent JSON output as input, eliminating the manual writing step.

### Implementation phases

| Phase | Work | Time | Output |
|---|---|---|---|
| **Phase 1** (1-2 days) | Set up Quarto project, port existing Markdown to `.qmd`, render baseline HTML site | Low | Static HTML mirror of current docs |
| **Phase 2** (1 day) | Add Cytoscape.js pathway diagram + per-species coverage coloring | Medium | Cross-species pathway page |
| **Phase 3** (2-3 days) | Add cblaster + clinker for cluster figures; embed SVGs in per-species pages | Medium-high | Cluster ribbon visualizations |
| **Phase 4** (1-2 days) | Add JCVI MCScan macro-synteny; embed in cross-species page | Medium | Whole-genome synteny |
| **Phase 5** (1 day) | Set up auto-rendering on data update; PDF/MECA bundle output for manuscript submission | Low | Reproducible build |

**Total**: ~1 week of focused work to ship a Quarto-based atlas report with cluster figures, synteny, and pathway diagram.

---

## Cross-tool consensus signals (high-confidence picks)

When multiple independent surveys endorse the same tool, that's the highest-confidence signal:

| Tool | Endorsed by | Decision |
|---|---|---|
| **plantiSMASH 2.0** | BGC + enzyme function | ★ ADD |
| **clinker** | BGC + reporting | ★ ADD |
| **JCVI MCScan** | BGC + atlas paper styling (de-facto) | ★ ADD |
| **CLEAN / HIT-EC** | enzyme function only | ★ ADD (high-confidence solo) |
| **Quarto 1.9.37** | reporting only | ✓ **ADOPTED**, blessed canonical path |
| **Foldseek + ProstT5** | sequence/structure only | ★ ADD (cross-species evidence layer) |
| **Cytoscape.js** | reporting only | ADD (for pathway diagram) |
| **PlantCyc / PMN 16** | enzyme function only | ADD |
| **MIBiG 4.0** | BGC only | ADD (cheap cross-reference) |
| **MMseqs2 iterative** | sequence/structure only | ADD (drop-in BLAST replacement) |

---

## Sources cited

### Comparative-genomics atlas reference papers
1. [Shan et al. 2025, BIA gene clustering, Nat Commun](https://www.nature.com/articles/s41467-025-63175-x) PMID 40826018
2. [Sun et al. 2024, Convergent berberine biosynthesis, Sci Adv](https://www.science.org/doi/10.1126/sciadv.ads3596) PMID 39612339
3. [Li et al. 2024, Houttuynia decaploid, Hortic Res](https://academic.oup.com/hr/article/11/9/uhae203/7718721) PMID 39308792
4. [MIA C3-stereo 2025, Nat Commun](https://www.nature.com/articles/s41467-025-65543-z)
5. [Astilbe chinensis 2025, Nat Commun](https://www.nature.com/articles/s41467-025-64842-9)
6. [Magnoliid genomes & BIA Nat Commun 2025](https://www.nature.com/articles/s41467-025-59343-8)
7. [Stephania CYP80B PubMed 40383618](https://pubmed.ncbi.nlm.nih.gov/40383618/)
8. [Phellodendron T2T genome Nat Commun 2025](https://www.nature.com/articles/s41467-025-66357-9)

### BGC + synteny tools
9. [plantiSMASH 2.0 bioRxiv 2025](https://www.biorxiv.org/content/10.1101/2025.10.28.683968v1)
10. [plantiSMASH 2.0 ScienceDirect 2026](https://www.sciencedirect.com/science/article/abs/pii/S0022283626001713)
11. [cblaster Bioinformatics Advances 2021](https://academic.oup.com/bioinformaticsadvances/article/1/1/vbab016/6342405)
12. [clinker Bioinformatics 2021](https://academic.oup.com/bioinformatics/article/37/16/2473/6103786)
13. [JCVI iMeta 2024](https://onlinelibrary.wiley.com/doi/10.1002/imt2.211)
14. [MIBiG 4.0 NAR 2024](https://academic.oup.com/nar/article/53/D1/D678/7919508)
15. [BiG-SLiCE 2.0 Nat Commun 2026](https://www.nature.com/articles/s41467-026-68733-5)

### Sequence + structure tools
16. [MMseqs2 GPU Nat Methods 2025](https://www.nature.com/articles/s41592-025-02819-8)
17. [Foldseek Nat Biotech 2024](https://www.nature.com/articles/s41587-023-01773-0)
18. [ProstT5 NAR Genomics 2024](https://academic.oup.com/nargab/article/6/4/lqae150/7901286)
19. [pLM-BLAST Bioinformatics 2023](https://academic.oup.com/bioinformatics/article/39/10/btad579/7277200)
20. [DIAMOND v2 Nat Methods 2021](https://www.nature.com/articles/s41592-021-01101-x)
21. [HH-suite3 BMC Bioinformatics 2019](https://link.springer.com/article/10.1186/s12859-019-3019-7)
22. [AlphaFast bioRxiv 2026](https://www.biorxiv.org/content/10.64898/2026.02.17.706409v1.full)

### Enzyme function tools
23. [CLEAN Yu Science 2023](https://www.science.org/doi/10.1126/science.adf2465)
24. [CLEAN-Contact Comm Biol 2024](https://www.nature.com/articles/s42003-024-07359-z)
25. [GraphEC Nat Commun 2024](https://www.nature.com/articles/s41467-024-52533-w)
26. [HIT-EC Nat Commun 2026](https://www.nature.com/articles/s41467-026-68727-3)
27. [DeepGO-SE Nat MI 2024](https://www.nature.com/articles/s42256-024-00795-w)
28. [PlantCyc/PMN 16 NAR 2025](https://academic.oup.com/nar/article/53/D1/D1606/7903387)
29. [P450Rdb Database 2023](https://pubmed.ncbi.nlm.nih.gov/37871773/)
30. [DiffPaSS Bioinformatics 2025](https://academic.oup.com/bioinformatics/article/41/1/btae738/7923417)

### Reporting + visualization tools
31. [Quarto Manuscripts](https://quarto.org/docs/manuscripts/)
32. [Quarto Dashboards](https://quarto.org/docs/dashboards/)
33. [igv-reports GitHub](https://github.com/igvteam/igv-reports)
34. [JBrowse 2 Genome Biology 2023](https://pmc.ncbi.nlm.nih.gov/articles/PMC10108523/)
35. [Cytoscape.js 2023 PMC9889963](https://pmc.ncbi.nlm.nih.gov/articles/PMC9889963/)
36. [Jupyter Book 2 SciPy 2025](https://proceedings.scipy.org/articles/hwcj9957)
37. [pyGenomeTracks docs](https://pygenometracks.readthedocs.io/)
38. [Arabidopsis cell-cycle atlas Nat Plants 2025](https://www.nature.com/articles/s41477-025-02072-z)

---

## Foundation

The integration scaffolding for this roadmap lives in two places:

- [`docs/tooling/`](tooling/), one Markdown integration plan per recommended tool, each covering install, sample CLI, where output feeds into `pipeline/genecluster_annotation_direct/`, integration cost, and open questions.
- [`tools/recommended/`](../tools/recommended/), three idempotent install scripts (`install-cheap.sh`, `install-medium.sh`, `install-heavy.sh`) plus per-tool `*.sh.template` placeholder runners.

Use [`biosymphony-tooling-status.md`](biosymphony-tooling-status.md) and [`docs/tooling/README.md`](tooling/README.md) for current validated, parked, shelved, and gated state.
