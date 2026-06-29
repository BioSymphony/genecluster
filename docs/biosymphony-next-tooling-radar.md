# BioSymphony next tooling radar

**Status:** candidate-tool radar.
**Baseline:** `docs/biosymphony-tooling-status.md`.
**Method:** primary-source checks against project docs, official repositories, and database/paper pages.

This note names tools that could help agents run GeneCluster campaigns with better source handling, tool coverage, review packets, and cloud handoffs. Each candidate includes the first public contract it should produce and the smallest useful smoke test.

## What This Adds Beyond The Previous Tooling Pass

The previous tooling pass checked existing tool pins and nearby releases. This pass asks which tools, repos, databases, and runtimes would make the **specific BioSymphony GeneCluster workflow** more useful over the next few campaigns.

The useful additions cluster into six categories:

1. Stage 0 data acquisition and source-ledger hardening.
2. Plant pathway, synteny, coexpression, and metabolite support sources.
3. Protein structure, protein-complex, pocket, docking, and enzyme-function lanes.
4. Durable provenance and table-schema checks for figure packages.
5. Static review surfaces for genome, structure, and claim inspection.
6. RunPod hardening plus portable cloud overflow paths.

## Immediate Shortlist

| Rank | Candidate | Why It Is Useful Here | First BioSymphony Contract | First Check |
|---:|---|---|---|---|
| 1 | `nf-core/fetchngs` + NCBI Datasets + SRA/ENA/GWH/PubPlant adapters | Stage 0 already depends on public genome/read metadata, but the data acquisition layer should emit stronger normalized ledgers instead of one-off accession heuristics. | `source-ledger.tsv`, `read-accessions.tsv`, `assembly-ledger.tsv`, `checksums.tsv` | Keep raw/private data out of the repo; pin tool versions. |
| 2 | AGAT + `pyGenomeViz` | The cblaster/clinker parked slot exposed annotation-format friction. AGAT is the GFF sanitation workhorse; `pyGenomeViz` gives lightweight static HTML/SVG cluster review without requiring a full browser app. | `annotation-normalization-report.tsv`, `cluster-neighborhood.svg`, `cluster-neighborhood.html` | GPL-3.0 for AGAT; smoke on messy plant GFFs. |
| 3 | PMN 17 / PlantCyc | The repo still frames PlantCyc as PMN 16. PMN 17 is a real upgrade and the best plant-specific pathway/reaction source when license terms are acceptable. | `pmn_pathway_coverage.tsv`, `pmn-reaction-evidence.tsv` | Manual PMN license form; cache outside repo. |
| 4 | PGDD 2.0 / Gramene Plants / PlantPan | BioSymphony needs better source-scout enrichment before running custom synteny. These are plant-specific support sources for precomputed synteny, pangenome, pathway, expression, and orthology context. | `external-synteny-evidence.tsv`, `pangenome-context.tsv` | Species coverage is crop-biased; preserve release numbers. |
| 5 | Workflow Run RO-Crate + Process Run Crate + Data Package v2 | Figure packages need interoperable provenance without forcing every worker into a full workflow engine. RO-Crate captures runs; Data Package/check-jsonschema checks compact tables. | `ro-crate-metadata.json`, `datapackage.json`, `validation-report.json` | Use a path-redaction policy. |
| 6 | Boltz-2 + OpenFold3 + P2Rank/fpocket + GNINA/PoseBusters | Structure work is more useful when the agent records complexes, pockets, docking boxes, pose plausibility, and affinity triage in tables. | `protein_structure_models.tsv`, `binding_pockets.tsv`, `ligand_pose_scores.tsv` | GPU pods and ligand-prep discipline; predictions are triage support. |
| 7 | Intra-cluster protein-complex prediction | A candidate BGC locus can contain adjacent proteins whose functions only make sense as a physical complex or enzyme assembly. This lane turns that into a bounded hypothesis test instead of a full proteome-scale screen. | `cluster_complex_pairs.tsv`, `complex_model_scores.tsv`, `cluster_ppi_network.json` | Candidate/preprint lane; use small public loci first and keep claims hypothesis-level. |
| 8 | LOTUS + Rhea + RetroRules 2026 + ATTED-II | Gene/pathway review is stronger when paired with metabolite occurrence, reaction-template, and public coexpression context, especially for alkaloid route claims. | `metabolite_occurrence.tsv`, `reaction_template_evidence.tsv`, `public_coexpression_context.tsv` | Occurrence and coexpression support context only; synonym and ID cleanup required. |
| 9 | Observable Framework + igv-reports/JBrowse + Molstar/Nightingale | Quarto remains the report spine, but dense review needs sortable claim tables, self-contained locus cards, and pinned protein-structure scenes. | `review/` static site manifest plus per-card HTML/state files | Keep canonical narrative in Quarto; avoid server-only apps. |
| 10 | RunPod S3 artifact pull + rclone/s5cmd | RunPod stays default, but artifact retrieval should prefer direct object-style pulls where available and fall back to proxy-pod pulls only when needed. | `artifact_pull.yaml`, `artifact-pull-report.json` | S3 API is datacenter-limited; keep raw FASTQ/BAM out of the repo. |
| 11 | Nextflow/Wave/Fusion, Snakemake/Apptainer, dstack, SkyPilot | Useful later for standardized overflow lanes, portable smoke jobs, HPC execution, and eventually AWS/GCP Batch after the Symphony/RunPod wrappers stabilize. | provider-neutral `launch-manifest.json` to `nextflow.config`, `Snakefile`, `apptainer.def`, `dstack.yml`, or `sky.yaml` | More credentials/config surface; wait for stable wrapper contracts. |
| 12 | Proto / Evo Design stack | Design-program layer after GeneCluster has a reviewed candidate map. Useful for typed sequence/construct units, generators, constraints, optimizers, and ranked outputs. | `proto-design-candidates.tsv`, `proto-constraint-scores.tsv`, `proto-run-metadata.json` | Local public-data smoke first; hosted MCP uses public inputs and environment credentials. |

## June 2026 Tool Intake

This refresh records recent public tools and databases that fill gaps in the radar. These entries are knowledge-base candidates, not checked tool rows. Promote one only after a small smoke run produces the named contract.

| Candidate | Fit | First Contract | Decision |
|---|---|---|---|
| PubPlant | Publication-backed plant genome catalogue for Stage 0 source scouting. | `published_genome_sources.tsv` folded into `source-ledger.tsv` | Add to the source adapter pack. |
| GATOR-GC | Required/optional-protein cluster search for known or suspected cluster families. | `targeted_cluster_windows.tsv`, `gator_gc_similarity.tsv` | Smoke after cblaster/Scan Cluster handoff shape is stable. |
| BGC-QUAST | Compares antiSMASH, DeepBGC, and GECCO-style BGC calls and emits reviewable reports. | `bgc_caller_comparison.tsv`, `bgc-quast-report/` | Add a narrow BGC-caller comparison smoke. |
| BGC-Prophet | Fast microbial/metagenome BGC triage using a transformer-style model. | `microbial_bgc_triage.tsv` | Watch for microbial/fungal expansion. |
| BGCFlow | Snakemake workflow for pangenome-scale BGC analysis across genome collections. | `bgcflow_project_manifest.json`, `bgcflow_summary.tsv` | Watch for microbial/fungal or large comparator campaigns; prokaryotic focus. |
| BiG-SCAPE 2 / BiG-SLiCE 2 | BGC similarity-family networks after candidate clusters are normalized. | `gcf_novelty.tsv`, `mibig_similarity.tsv` | Run externally; AGPL/current terms and microbial-bias caveats apply. |
| IGUA | Content-agnostic gene-cluster family identification that is not limited to Pfam-domain representation. | `igua_gcf_assignments.tsv`, `cluster_family_graph.json` | GPL-3.0; use after candidate clusters have GenBank-style records. |
| CHAMOIS | Secondary-metabolism chemical-hierarchy approximation for cluster class cross-checks. | `chemical_hierarchy_predictions.tsv` | Verify model assets, license, and benchmark fit before use. |
| FunBGCeX | Fungal BGC extractor for fungal or endophyte campaigns. | `fungal_bgc_regions.tsv`, `fungal_bgc_manifest.json` | Scope to fungal campaigns; not a plant default. |
| PanBGC / PanBGC-DB | Pangenome-style family context for BGC families. | `bgc_family_pan_context.tsv` | Watch for microbial/fungal family work. |
| MEANtools | Multi-omics metabolite and pathway inference when expression and metabolomics evidence both exist. | `multiomics_metabolite_links.tsv`, `pathway_prediction_evidence.tsv` | Requires compatible public inputs; treat predictions as context, not proof. |
| GNPS2 | Current public metabolomics analysis hub and workflow context for MS/MS evidence. | `metabolomics_dataset_ledger.tsv`, `gnps2_workflow_summary.tsv` | Public or approved spectra only; preserve dataset accessions and terms. |
| PGAP2 | Pan-genome analysis reference for bacterial/fungal comparator sets. | `pangenome_context.tsv`, `gene_family_presence.tsv` | Not a plant default; resolve current license/dependency posture. |
| chatBGC | RAG-style question layer over BGCFlow outputs. | `bgc_qa_index_manifest.json`, sanitized source-summary index | Use only over public summaries or approved local outputs. |
| ATTED-II v13 | Public plant coexpression lookup before campaign-specific CoExpPhylo work. | `public_coexpression_context.tsv` | Add when species coverage fits. |
| AF2BIND + PoseBench | Binding-site predictions and pose benchmark context before docking tables. | `binding_site_predictions.tsv`, `pose_benchmark_report.json` | Smoke AF2BIND after P2Rank/fpocket; watch PoseBench. |
| MAPred / ProtDETR / TopEC | Second-wave EC/function-scoring alternatives with structure or residue-level signals. | `protein_function_votes.tsv` | Watch after HIT-EC/EnzyMM/DeepEC contracts settle. |
| Apptainer 1.4 + Snakemake 9 plugins | HPC runtime path for sites where Docker or Nextflow is awkward. | `apptainer.def`, `Snakefile`, `snakemake-profile.yaml` | Add when an HPC user appears. |
| A2A / MCP / Agents SDK handoff patterns | Shared vocabulary for task, tool, and artifact handoff manifests. | `agent-handoff-manifest.json` | Watch; keep the skill runtime-agnostic. |
| Proto / Evo Design stack | Sequence/construct design architecture and standardized tool execution pattern. | `proto-design-candidates.tsv`, `proto-constraint-scores.tsv`, `proto-run-metadata.json` | Keep as radar until a local public smoke proves exports. |

## Stage 0 Acquisition And Source Scouting

### NCBI Datasets CLI

**Fit:** keep as the primary genome/annotation fetcher for public assemblies. The official CLI downloads genome data packages that may include genome, transcript/protein sequences, annotation, and data reports.

**Integration shape:**

- Add a `ncbi_datasets` source provider behind `genecluster_source_scout.py`.
- Record CLI version, accession, dataset include flags, dehydrated/rehydrated status, and `assembly_data_report.jsonl` fields.
- Normalize to `assembly-ledger.tsv` and `source-ledger.tsv`; do not store downloaded packages in git.

**Smoke test:** one target plus one comparator from `skills/biosymphony/examples/genecluster-coptis-bia-public-v0`, with `--include genome,gff3,protein,rna` where available.

**Source:** [NCBI Datasets GitHub](https://github.com/ncbi/datasets), [datasets download genome docs](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/reference-docs/command-line/datasets/download/genome/).

### nf-core/fetchngs

**Fit:** strongest ready-made public-read materialization lane. It resolves SRA/ENA/DDBJ/GEO IDs, fetches metadata via ENA, downloads FASTQ, checks MD5, and emits samplesheets.

**Integration shape:**

- Use it only when a campaign needs raw public reads or transcript-first support.
- Convert fetchngs output samplesheets into BioSymphony `read-accessions.tsv`, `read-materialization.tsv`, and `checksums.tsv`.
- Keep Nextflow reports as secondary artifacts under the cloud run directory.

**Smoke test:** 3-6 small public SRR/ERR/DRR accessions; verify md5 and samplesheet normalization.

**Source:** [nf-core/fetchngs GitHub](https://github.com/nf-core/fetchngs).

### SRA Toolkit, ENA API, GWH API, PubPlant, ffq, pysradb

**Fit:** focused adapters for the same source-ledger flow.

- SRA Toolkit remains the low-level fallback for `.sra` to FASTQ conversion; use `fasterq-dump` where it fits disk constraints.
- SRA Cloud is the right path when read movement dominates; NCBI documents faster cloud access and unlimited concurrent cloud-bucket downloads.
- ENA Browser/Portal APIs should be used for accession resolution and FTP/metadata mirrors.
- GWH API fills the China National Genomics Data Center plant assembly fallback already named in Stage 0.
- PubPlant fills a publication-backed plant genome catalogue role, useful for checking whether a target species has a public genome, publication, and downloadable source before deeper acquisition work starts.
- `ffq` and `pysradb` are useful lightweight metadata cross-checkers, especially when nf-core/Nextflow is too heavy for a scout.

**Contract:** every adapter writes the same fields: provider, query, accession, organism, taxid, material type, assembly/read metadata, download URL, checksum when available, license/terms note, timestamp, tool version.

**Sources:** [SRA Toolkit](https://github.com/ncbi/sra-tools), [SRA in the Cloud](https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/), [ENA programmatic access](https://ena-docs.readthedocs.io/en/latest/retrieval/programmatic-access.html), [GWH API docs](https://ngdc.cncb.ac.cn/gwh/api_documents), [PubPlant](https://www.plabipd.de/pubplant_main.html), [ffq](https://github.com/pachterlab/ffq), [pysradb](https://github.com/saketkc/pysradb).

## Annotation And Cluster Visualization

### AGAT

**Fit:** direct fix for messy GFF/GTF handoffs. AGAT checks, fixes, pads, standardizes, converts, extracts sequences, and repairs common GFF/GTF problems.

**Integration shape:**

- Add an annotation-normalization step before cblaster/clinker/Scan Cluster/JBrowse package generation.
- Emit `annotation-normalization-report.tsv` with input counts, output counts, fixed IDs, missing parents added, longest-isoform policy, and command line.
- Treat AGAT as a cloud-side dependency because it is GPL-3.0 and Perl-heavy.

**Source:** [AGAT GitHub](https://github.com/NBISweden/AGAT).

### pyGenomeViz

**Fit:** lower-friction figure generator than a full genome browser for small comparative neighborhoods. It supports GenBank/GFF inputs and can save JPG/PNG/SVG/PDF/HTML.

**Integration shape:**

- Use for first-pass cluster-neighborhood review cards.
- Inputs: normalized GFF/GenBank, FASTA coordinates, pairwise similarity links from MMseqs2/blastp.
- Outputs: `cluster-neighborhood.svg`, `cluster-neighborhood.html`, `cluster-neighborhood.links.tsv`.

**Source:** [pyGenomeViz GitHub](https://github.com/moshi4/pyGenomeViz).

### Scan Cluster

**Fit:** best conceptual match for the cblaster/clinker parked slot because it claims database-independent multi-genome conserved-cluster detection from protein FASTA + GFF.

**Current gate:** dispatch only after a public runnable repo/package is found. The preprint alone is not enough for a BioSymphony smoke run.

**Action:** keep as `watch-high` and re-check before the next cblaster/clinker investment.

**Source:** [bioRxiv preprint](https://www.biorxiv.org/content/10.64898/2026.04.29.721675v1).

### GATOR-GC, BGC-QUAST, BGC-Prophet, And PanBGC

**Fit:** useful around the plantiSMASH/DeepBGC/Scan Cluster layer, but each tool should stay in a narrow role until a smoke run proves the handoff.

- GATOR-GC is a targeted cluster-search tool for required and optional proteins. It is useful when BioSymphony already has a seed enzyme set and wants conserved windows around those proteins.
- BGC-QUAST is a comparison and quality-assessment layer for BGC caller outputs. It can help compare antiSMASH, DeepBGC, and GECCO-style predictions once BioSymphony has normalized input formats.
- BGC-Prophet is a transformer-style microbial/metagenome BGC predictor and classifier. Keep it out of the plant default path, but record it for microbial/fungal expansion.
- PanBGC and PanBGC-DB are useful for bacterial/fungal pangenome-shaped family context. They are not plant defaults.

**Integration shape:**

- Add `targeted_cluster_windows.tsv`: query protein, required/optional role, contig, window coordinates, neighboring genes, distance thresholds, and support notes.
- Add `bgc_caller_comparison.tsv`: region ID, caller, coordinates, class, overlap set, disagreement reason, and source file.
- Add `microbial_bgc_triage.tsv` only for microbial/fungal campaigns.
- Add `bgc_family_pan_context.tsv` only when a campaign asks for pangenome-family context.

**Sources:** [GATOR-GC NAR article](https://academic.oup.com/nar/article/53/13/gkaf606/8192810), [GATOR-GC GitHub](https://github.com/chevrettelab/gator-gc), [BGC-QUAST preprint](https://www.biorxiv.org/content/10.64898/2026.05.04.722653v1.full-text), [BGC-QUAST GitHub](https://github.com/gurevichlab/bgc-quast), [BGC-Prophet NAR article](https://academic.oup.com/nar/article/53/7/gkaf305/8113170), [BGC-Prophet GitHub](https://github.com/HUST-NingKang-Lab/BGC-Prophet), [PanBGC-DB GitHub](https://github.com/ZiemertLab/PanBGC-DB), [PanBGC article](https://academic.oup.com/ismecommun/article/5/1/ycaf225/8346042).

## Plant Pathway, Synteny, Coexpression, And Chemistry Context

### PMN 17 / PlantCyc

**Fit:** strongest plant-specific pathway/reaction reference once licensing is cleared. PMN 17 includes 583 single-species databases and updated PMN 16 databases, regenerated with Pathway Tools 29.0, E2P2 v5, and updated SAVI lists.

**Integration shape:**

- Keep PMN data outside the repo.
- Add `pmn_pathway_coverage.tsv`: candidate protein, projected pathway, PlantCyc reaction, support source, orthology method, confidence ceiling.
- Add `pmn-reaction-evidence.tsv`: reaction IDs, EC, compounds, taxon-specific availability, caveats.

**Gate:** manual license form and redistribution review.

**Sources:** [PMN 17 release](https://plantcyc.org/pmn-17-released/), [PMN downloads/license page](https://plantcyc.org/downloads/).

### PGDD 2.0, Gramene Plants, Ensembl Plants, PlantPan

**Fit:** source-scout enrichment before custom synteny spend.

- PGDD 2.0 adds plant collinearity and standard downloads such as TSV, GFF3, and MCScan collinearity, with SynVisio/riparian/dotplot viewers.
- Gramene Plants 2025 integrates Ensembl, Plant Reactome, Expression Atlas/BAR, APIs, and crop pangenome portals; it reports growth to 233 hosted genomes across recent releases.
- Ensembl Plants release 62 is the current FTP release visible in the checked docs.
- PlantPan covers pangenome analysis for 195 genomes from 11 crop species, including genes, gene groups, variation, synteny, and functional annotations.

**Integration shape:**

- Add external-context adapters that enrich source scout output alongside BioSymphony's own checks.
- Store release, species coverage, exact query, and any exported row IDs.
- Use these rows as external synteny support, with final cluster calls still coming from the campaign's own ledgers and review.

**Sources:** [PGDD 2.0 NAR article](https://academic.oup.com/nar/article/54/D1/D1753/8343508), [Gramene Plants 2025 NAR article](https://academic.oup.com/nar/article/54/D1/D1720/8363844), [Ensembl Plants FTP release page](https://plants.ensembl.org/info/data/ftp/index.html), [PlantPan docs](https://ngdc.cncb.ac.cn/plantpan/documentation).

### CoExpPhylo

**Fit:** better than a generic WGCNA lane for biosynthetic discovery. It starts from bait genes and per-species TPM matrices, then combines coexpression, orthology, and phylogeny across species.

**Integration shape:**

- Optional lane after transcript quantification.
- Inputs: bait genes, per-species TPMs, CDS/pep FASTA, sample metadata.
- Outputs: `coexpression_candidate_groups.tsv`, `coexpression_edges.tsv`, `bait_phylogeny.newick`, `coexpression-caveats.md`.

**Gate:** useful only with enough biologically relevant samples; expect ID normalization and memory requirements.

**Sources:** [CoExpPhylo GitHub](https://github.com/bpucker/CoExpPhylo), [BMC Genomics article](https://link.springer.com/article/10.1186/s12864-025-12061-3).

### ATTED-II v13

**Fit:** public coexpression lookup before spending on campaign-specific transcript quantification. It is especially useful when a target or comparator species is covered well enough to provide gene-level neighborhood context.

**Integration shape:**

- Add `public_coexpression_context.tsv`: query gene, source species, matched public gene ID, coexpressed partner, score/rank, source release, URL or row ID, and ID-mapping caveat.
- Use as context for candidate ranking; do not treat coexpression alone as cluster or enzyme proof.

**Source:** [ATTED-II](https://atted.jp/).

### LOTUS, Rhea, RetroRules 2026

**Fit:** adds non-gene context to pathway claims.

- LOTUS provides referenced natural-product structure-organism occurrence pairs under CC0.
- Rhea release 141 reports 18,558 unique reaction quartets.
- RetroRules current public download is release 3.0.0, with CC BY 4.0 terms and radius 0-10 templates.

**Integration shape:**

- Add `metabolite_occurrence.tsv`: compound, structure ID, organism/taxon, reference, LOTUS/Wikidata IDs, match method.
- Add `reaction_template_evidence.tsv`: route step, Rhea/RetroRules ID, EC, substrate/product mapping, radius/template, caveat.
- Use this as plausibility and route context for review; route enzyme claims still need separate support.

**Sources:** [LOTUS homepage](https://lotus.nprod.net/), [LOTUS manuscript](https://lotus.nprod.net/lotus-manuscript/), [Rhea statistics](https://www.rhea-db.org/statistics), [RetroRules downloads](https://retrorules.org/download), [RetroRules 2026 NAR article](https://academic.oup.com/nar/article/54/D1/D1799/8373943).

### BiG-SCAPE 2.0 / BiG-SLiCE 2.0

**Fit:** useful only after BioSymphony normalizes plant BGC calls. It can support "known vs novel cluster-family" claims, but microbial bias remains material.

**Integration shape:** convert plantiSMASH/DeepBGC/Scan Cluster regions to minimal GenBank-like cluster records, then emit `gcf_novelty.tsv` and `mibig_similarity.tsv`.

**Gate:** treat missing similarity cautiously for dispersed plant pathways.

**Source:** [BiG-SCAPE GitHub](https://github.com/medema-group/BiG-SCAPE).

## Protein Structure, Docking, And Enzyme Function

### Boltz-2

**Fit:** first-choice open protein-ligand/affinity triage backend. The repo states Boltz-2 models complex structures and binding affinities; code and weights are MIT-licensed.

**Integration shape:**

- Run on GPU pods with fresh environments.
- Output `protein_structure_models.tsv`, `complex_confidence.json`, `affinity_scores.tsv`, and model CIF/PDB files.
- Mark affinity as triage support.

**Gate:** known resolver sensitivity around Python/numpy/CUDA environments; use a clean image.

**Source:** [Boltz GitHub](https://github.com/jwohlwend/boltz).

### OpenFold3 And Protenix-v2

**Fit:** open AF3-style alternatives.

- OpenFold3-preview is Apache-2.0, intended as an AlphaFold3-style biomolecular prediction reproduction and available for academic and commercial use.
- Protenix-v2 remains high-upside, but the local/RunPod check found a CUDA extension compile/import blocker. Keep it parked until a wheel or custom image path is stable.

**Integration shape:** same structure-model table as Boltz, with model name, license, inputs, GPU type, confidence metrics, and command provenance.

**Sources:** [OpenFold3 GitHub](https://github.com/aqlaboratory/openfold-3), [Protenix GitHub](https://github.com/bytedance/Protenix).

### Intra-cluster Protein-Complex Prediction

**Fit:** useful after BioSymphony has already narrowed a campaign to one or a few candidate loci. The agent can ask whether proteins encoded near a candidate cluster have a plausible stable interaction that changes how the locus should be reviewed.

**Integration shape:**

- Enumerate protein pairs from reviewed cluster calls and neighboring-gene windows.
- Filter before GPU work: remove very large pairs, obvious bystanders, low-quality gene models, and membrane-anchor artifacts.
- Prioritize pairs using coevolution, domain, pathway, and orthology context.
- Run multimer structure prediction only on the small candidate set.
- Score models with ipTM plus PAE-aware interface metrics such as ipSAE, then normalize to `complex_model_scores.tsv`.
- Return compact summaries and caveats locally; keep model files and large intermediate outputs in the provider run area or approved artifact storage.

**Contract:** `cluster_complex_pairs.tsv` should record locus, protein IDs, pair class, filter decision, and reason. `complex_model_scores.tsv` should record model backend, version, ipTM, ipSAE or comparable interface score, interface residues/counts, and caveats. `cluster_ppi_network.json` should expose a reviewable graph for the static review surface.

**First check:** candidate-only until a public smoke run exercises the full contract. Use this for soluble enzyme-pair hypotheses and uncharacterized neighboring proteins. Keep transient metabolon behavior, membrane-bound P450 relay specificity, and final enzyme function at low claim levels until separate assays or strong external support exist.

**Sources:** [Moriwaki et al. bioRxiv preprint](https://www.biorxiv.org/content/10.1101/2025.10.26.684697v1), [DunbrackLab IPSAE GitHub](https://github.com/DunbrackLab/IPSAE).

### P2Rank + fpocket

**Fit:** cheap pocket atlas before docking. P2Rank emits pocket centers/residues/probabilities from protein structures; fpocket gives fast Voronoi-based pocket descriptors.

**Integration shape:**

- Run both on predicted/experimental structures.
- Merge into `binding_pockets.tsv`: structure ID, pocket ID, center coordinates, residues, rank, method, confidence, recommended docking box.
- Generate PyMOL/ChimeraX pocket surfaces and Molstar state files.

**Sources:** [P2Rank GitHub](https://github.com/rdk/p2rank), [fpocket GitHub](https://github.com/Discngine/fpocket).

### AF2BIND + PoseBench

**Fit:** binding-site prediction and benchmark context before full docking spend. AF2BIND is a good smoke candidate because it turns protein structures into pocket/binding-site hypotheses, while PoseBench is better kept as a benchmark harness until BioSymphony has multiple pose generators to compare.

**Integration shape:**

- Add `binding_site_predictions.tsv`: structure ID, model backend, predicted site, residue set, ligand class or query ligand, score, and caveat.
- Add `pose_benchmark_report.json` only when comparing multiple docking or pose-prediction backends.
- Keep AF2BIND downstream of P2Rank/fpocket so the first smoke compares cheap pocket calls to a model-based binding-site signal.

**Sources:** [AF2BIND GitHub](https://github.com/sokrypton/af2bind), [AF2BIND Nature Methods article](https://www.nature.com/articles/s41592-026-03011-2), [PoseBench GitHub](https://github.com/BioinfoMachineLearning/PoseBench).

### GNINA + PoseBusters + ProDock

**Fit:** pragmatic docking and plausibility-check lane once pocket/state prep is controlled.

**Integration shape:**

- GNINA on GPU for pose generation and CNN scoring.
- PoseBusters on CPU for geometry/plausibility checks.
- Optional ProDock if its table/SQLite shape is helpful for batch review.
- Output `ligand_pose_scores.tsv`, docked SDFs, `posebusters.json`, and interaction TSVs.

**Gate:** ligand protonation/tautomer prep is the real failure mode; GNINA's OpenBabel path has GPL implications.

**Sources:** [GNINA GitHub](https://github.com/gnina/gnina), [PoseBusters docs](https://posebusters.readthedocs.io/), [ProDock GitHub](https://github.com/Medicine-Artificial-Intelligence/ProDock).

### HIT-EC, EnzPlacer, EnzyMM, PLM Embeddings

**Fit:** turns function calls into a multi-tool score instead of a single EC guess.

- HIT-EC is now checked locally in the repo, and its interpretability/contribution-score angle fits enzyme-function votes.
- EnzPlacer fills EC1-3 novelty space, especially outside training-corpus comfort zones.
- EnzyMM adds M-CSA-derived 3D catalytic-motif context.
- ESM-C 300M, SaProt, and ProstT5 support protein-family maps and structure-aware similarity.
- MAPred, ProtDETR, and TopEC are second-wave alternatives that add sequence plus 3Di, residue-level, or local 3D-structure signals. Watch them until the baseline `protein_function_votes.tsv` contract is stable.

**Integration shape:**

- Normalize all function calls into `protein_function_votes.tsv`.
- Add `catalytic_site_evidence.tsv` for EnzyMM/site-template calls.
- Add `plm_embedding_index.tsv` for embedding files, model, dimensionality, sequence hash, and downstream plot/table links.

**Sources:** [HIT-EC GitHub](https://github.com/datax-lab/HIT-EC), [EnzPlacer GitHub](https://github.com/drxiangma/EnzPlacer), [EnzyMM GitHub](https://github.com/rayhackett/enzymm), [SaProt GitHub](https://github.com/westlake-repl/SaProt), [ProstT5 GitHub](https://github.com/mheinzinger/ProstT5), [MAPred GitHub](https://github.com/Rongdingyi/MAPred), [ProtDETR GitHub](https://github.com/yangzhao1230/ProtDETR), [TopEC GitHub](https://github.com/IBG4-CBCLab/TopEC).

### Proto / Evo Design

**Fit:** design-program sidecar after BioSymphony has reviewed candidate genes, clusters, structures, or evidence gaps. Proto defines sequence or construct units, generates candidates, scores constraints, and optimizes toward a ranked shortlist.

What to borrow even before live integration:

- `proto-language` vocabulary for sequences, segments, constructs, generators, constraints, optimizers, and programs.
- `proto-tools` style Input / Config / Output wrappers for bioinformatics tools and biological-AI models.
- Hosted MCP access pattern for discover -> inspect schema -> run -> fetch assets and design -> validate -> run -> inspect metrics.

**Integration shape:** keep Proto outputs compact:

```text
proto-design/
  proto-program.py
  proto-program-export/
  proto-design-candidates.tsv
  proto-constraint-scores.tsv
  proto-run-metadata.json
  validation-report.json
```

**Run shape:** use public inputs for hosted MCP. Keep credentials, runtime caches, and model caches outside git. Record tool licenses in `proto-run-metadata.json`.

**Sources:** [Proto about](https://proto.evodesign.org/about), [Proto MCP docs](https://proto.evodesign.org/docs/mcp/introduction), [`proto-language`](https://github.com/evo-design/proto-language), [`proto-tools`](https://github.com/evo-design/proto-tools), [`proto-client`](https://github.com/evo-design/proto-client). See [`tooling/proto.md`](tooling/proto.md) for the BioSymphony-specific review.

## Provenance, Package, And Review Surfaces

### Workflow Run RO-Crate + Process Run Crate

**Fit:** best match for BioSymphony's scientific-ledger model. Process Run Crate explicitly supports ad hoc command-line runs, which matches Symphony workers better than forcing a full workflow engine.

**Integration shape:**

- Keep `figure_manifest.json` as the local BioSymphony contract.
- Add `ro-crate-metadata.json` as the interoperable provenance envelope.
- Represent each worker command as a `CreateAction` with inputs, outputs, software, versions, container image digest, Linear issue ID, run status, and check command.
- Omit private absolute paths from public/exportable crates.

**Sources:** [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/), [Process Run Crate](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate/), [ro-crate-py](https://pypi.org/project/rocrate/), [runcrate](https://www.researchobject.org/runcrate/readme.html).

### Data Package v2 + check-jsonschema

**Fit:** cheap schema checks for compact TSV/CSV/JSON deliverables. It complements RO-Crate while provenance stays in the run crate.

**Integration shape:**

- Add `datapackage.json` to figure packages and provider handoffs.
- Use `check-jsonschema` in `genecluster_atlas_contracts.py` or a companion checker for manifest schemas and table resource schemas.

**Sources:** [Data Package GitHub](https://github.com/frictionlessdata/datapackage), [check-jsonschema GitHub](https://github.com/python-jsonschema/check-jsonschema).

### Observable Framework

**Fit:** static review site for dense tables and filtering. Use it when Quarto pages become too narrative-heavy for claim triage.

**Integration shape:** generate `review/observable/` from compact TSV/JSON ledgers: claim ledger, species/candidate tables, check status, source hashes, artifact manifest.

**Gate:** do not split canonical narrative; Quarto remains the manuscript/report spine.

**Source:** [Observable Framework GitHub](https://github.com/observablehq/framework).

### igv-reports, JBrowse 2, Molstar, Nightingale

**Fit:** review surfaces mapped to artifact type.

- `igv-reports`: self-contained locus cards for a small set of genomic sites.
- JBrowse 2 embedded components: richer multi-track and larger comparative genome views.
- PDBe Molstar/Molstar: pinned structure scenes, pocket overlays, ligand pose cards.
- Nightingale: protein-domain and feature strips above structure views.

**Integration shape:**

```
figure-package/
  figure_manifest.json
  ro-crate-metadata.json
  datapackage.json
  review/
    index.html
    observable/
    loci/
    structures/
    proteins/
    clusters/
```

**Sources:** [igv-reports GitHub](https://github.com/igvteam/igv-reports), [JBrowse embedded components](https://jbrowse.org/jb2/docs/embedded_components/), [Molstar GitHub](https://github.com/molstar/molstar), [PDBe Molstar GitHub](https://github.com/molstar/pdbe-molstar), [Nightingale paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10287899/).

## Cloud Runtime And Artifact Movement

### RunPod Hardening

**Fit:** keep RunPod as default, but make pod creation and artifact retrieval more explicit.

**Changes to consider:**

- Require digest-pinned image names in launch manifests.
- Include `networkVolumeId`, data center, GPU type priority, and `/workspace` mount path explicitly.
- Add an artifact-pull abstraction that tries RunPod S3-compatible API first when the volume/datacenter supports it, then falls back to proxy-pod/SSH pulls.
- Store compact summaries locally; raw FASTQ/BAM/reference caches stay on cloud volumes or object storage.

**Sources:** [RunPod Create Pod API](https://docs.runpod.io/api-reference/pods/POST/pods), [RunPod network volumes](https://docs.runpod.io/storage/network-volumes), [RunPod S3-compatible API](https://docs.runpod.io/storage/s3-api).

### rclone + s5cmd

**Fit:** provider-neutral artifact movement across RunPod S3-compatible API, AWS S3, GCS S3-compatible surfaces, R2, MinIO, Lambda workflows, and CoreWeave object storage.

**Integration shape:** `artifact_pull.yaml` with include/exclude globs, max bytes, checksum mode, backend, and local destination policy.

**Sources:** [rclone](https://rclone.org/), [s5cmd GitHub](https://github.com/peak/s5cmd).

### Nextflow + Wave + Fusion

**Fit:** only after BioSymphony lanes are stable enough to standardize. Nextflow can target local, AWS Batch, Google Batch, Kubernetes, and other executors; Wave can build/provision containers; Fusion can reduce object-store staging friction on supported platforms.

**Integration shape:** profiles such as `local-smoke`, `runpod-docker-wrapper`, `awsbatch`, `google-batch`, and `k8s`. Treat this as a future portability layer alongside the current Symphony issue-contract model.

**Sources:** [Nextflow executors](https://www.nextflow.io/docs/latest/executor.html), [Wave containers](https://docs.seqera.io/nextflow/wave), [Fusion file system](https://docs.seqera.io/nextflow/fusion).

### Snakemake 9, Apptainer 1.4, And Handoff Specs

**Fit:** runtime portability and interface discipline for users outside the default RunPod wrapper path.

- Snakemake 9 executor and storage plugins are useful for labs that already operate Snakemake profiles or cluster schedulers.
- Apptainer 1.4 is the likely container path for university HPC sites where Docker is unavailable.
- A2A, MCP, and Agents SDK handoff patterns are useful vocabulary for a future `agent-handoff-manifest.json`; keep them as interface references, not runtime dependencies.

**Integration shape:** add these only after a real user path needs them. The first contract should be tiny: `Snakefile`, `snakemake-profile.yaml`, `apptainer.def`, or `agent-handoff-manifest.json`, each pointing at existing BioSymphony tables rather than introducing a parallel workflow model.

**Sources:** [Snakemake executors](https://snakemake.readthedocs.io/en/v9.17.2/executing/executors.html), [Apptainer 1.4 release](https://apptainer.org/news/apptainer-1-4-0-20250318/), [A2A GitHub](https://github.com/a2aproject/A2A), [MCP tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools), [OpenAI Agents SDK handoffs](https://openai.github.io/openai-agents-python/handoffs/).

### dstack, SkyPilot, AWS/GCP Batch, Vast.ai, Lambda, CoreWeave

**Fit:** overflow and portability experiments.

- `dstack`: practical YAML launcher with RunPod integration, but credential config needs discipline.
- SkyPilot: broad AI workload launcher across clouds, Kubernetes, Slurm, and on-prem; useful for smoke jobs and price/availability exploration.
- AWS/GCP Batch: best for SRA-heavy lanes because SRA cloud access can avoid slow raw downloads from RunPod.
- Vast.ai: public-data GPU overflow only; not for private/unpublished biology.
- Lambda/CoreWeave: higher-confidence GPU alternatives; CoreWeave becomes interesting if BioSymphony needs Kubernetes and enterprise storage patterns.

**Sources:** [RunPod dstack integration](https://docs.runpod.io/integrations/dstack), [SkyPilot GitHub](https://github.com/skypilot-org/skypilot), [SRA in the Cloud](https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/), [AWS Batch docs](https://aws.amazon.com/documentation-overview/batch/), [GCP Batch + Nextflow](https://cloud.google.com/batch/docs/nextflow).

## Concrete Next Smoke Flights

These are ordered by value-to-cost for the next operator pass.

| Flight | Goal | Commands / Shape | Expected Output | Cost |
|---|---|---|---|---|
| F1 | Source-acquisition adapter smoke | NCBI Datasets + ENA/GWH metadata queries + 3-accession fetchngs test | normalized `source-ledger.tsv`, `read-accessions.tsv`, checksums | small CPU pod, minutes |
| F2 | Annotation and small cluster card smoke | AGAT normalize one messy GFF; render one `pyGenomeViz` neighborhood | `annotation-normalization-report.tsv`, SVG/HTML card | small CPU pod, minutes |
| F3 | PMN 17 paperwork + parser dry run | Submit license form; build parser against a tiny permitted local sample only | `pmn_pathway_coverage.tsv` schema and no bundled PMN data | manual gate |
| F4 | Review-package provenance skeleton | Add RO-Crate + Data Package skeleton for an existing `.runtime` figure package | parseable `ro-crate-metadata.json`, `datapackage.json`, check report | local |
| F5 | Pocket/docking table smoke | P2Rank + fpocket on one ColabFold model; PoseBusters on one known ligand pose | `binding_pockets.tsv`, `posebusters.json` | small CPU pod, minutes |
| F6 | Boltz-2 clean-image smoke | One protein-ligand YAML on a fresh GPU pod | model CIF/PDB, confidence JSON, affinity TSV | small GPU pod, minutes |
| F7 | Intra-cluster complex smoke | Enumerate pairs for one small public candidate locus, filter hard, model the top few pairs, and score interfaces | `cluster_complex_pairs.tsv`, `complex_model_scores.tsv`, `cluster_ppi_network.json` | small GPU candidate set |
| F8 | Cloud artifact-pull abstraction | No paid biological run; test against a tiny volume/file set where the provider's object-storage API exists | `artifact-pull-report.json`, checksum report | maybe free/local + tiny pod |
| F9 | Observable claim explorer prototype | Build from existing atlas TSV/JSON only | static `review/observable/` | local |
| F10 | BGC caller and targeted-window comparison | Run BGC-QUAST on tiny antiSMASH/DeepBGC/GECCO-style public examples; run GATOR-GC on one small seed set | `bgc_caller_comparison.tsv`, `targeted_cluster_windows.tsv` | small CPU pod |
| F11 | Public coexpression context | Query ATTED-II for a small public target/comparator set and normalize IDs | `public_coexpression_context.tsv` | local or no-cost HTTP |
| F12 | AF2BIND binding-site smoke | Run AF2BIND on one existing public structure model and compare to P2Rank/fpocket pockets | `binding_site_predictions.tsv` | small GPU or CPU path, depending on setup |
| F13 | HPC portability skeleton | Wrap one existing smoke lane in Snakemake plus Apptainer without changing the core BioSymphony tables | `Snakefile`, `snakemake-profile.yaml`, `apptainer.def` | local or HPC login node dry run |
| F14 | Proto design-program smoke | Run a local public toy program with open components, export results, and convert them into BioSymphony ledgers | `proto-design-candidates.tsv`, `proto-constraint-scores.tsv`, `proto-run-metadata.json` | local CPU first |

**Implementation note:** F4 has a first local implementation. Generated
GeneCluster review packages now include `datapackage.json`,
`ro-crate-metadata.json`, and `validation-report.json`; preflight checks those
sidecars.

F1 also has a first local contract hardening pass: `genecluster_source_scout.py`
now emits self-identifying source-scout rows with provider/accession/material
fields, `genecluster_sra_runinfo.py` emits `read-accessions.tsv`, and
`genecluster_preflight.py` checks both the no-network source-scout policy and
normalized read-acquisition rows.

F8 also has a local control-plane implementation: launch bundles now emit
`artifact_pull.yaml`, and `genecluster_preflight.py --artifact-pull-manifest`
validates summary-only includes, raw/heavy excludes, max-byte limits, checksum
mode, and local destination policy before any artifact sync happens.
`--launch-manifest` checking follows and hashes the same pull-manifest pointer
when present, so launch bundles catch artifact-return policy drift as part of
the normal preflight.

## Defer Or Park

| Candidate | Decision |
|---|---|
| AlphaFold3 | Defer as a BioSymphony default: parameter/terms gates and non-commercial constraints do not fit open worker lanes. |
| Chai-2 | Defer: partner/API access belongs outside the current public repo lane. |
| ESM-3 / ESM-C 6B | Defer for default workflow: gated/commercial surfaces; use ESM-C 300M, ESM-2, SaProt, and ProstT5 where appropriate. |
| GECCO / antiSMASH as plant defaults | Defer for this workflow: bacterial/fungal or PKS/NRPS-heavy; plantiSMASH + DeepBGC remain the plant BGC defaults. |
| PanBGC as default plant family context | Watch for bacterial/fungal or pangenome-shaped work; do not make it the plant default until a plant-fit smoke run proves the contract. |
| NPAtlas / COCONUT 2.0 as primary source context | Keep as chemistry background only; LOTUS is a better fit for taxon-compound occurrence claims. |
| Generic Streamlit/Shiny/Reflex dashboards | Defer as default. Static Quarto/Observable/HTML review packets are better for durable review and handoff. |
| Replacing RunPod with AWS/GCP immediately | Keep RunPod as the current checked default; AWS/GCP are overflow paths for SRA-heavy or regulated runs. |
| Vast.ai for private data | Use only for public-data GPU overflow. |
| Object storage as executable POSIX workdir | Park unless a workflow/filesystem layer handles it. Use object stores for inputs, caches, and derived artifact pulls. |
| Full workflow-engine migration just for metadata | Defer. RO-Crate/Data Package solves the immediate provenance gap with less operational churn. |

## Working Recommendation

Keep the current checked atlas stack and add **one narrow smoke flight per gap**:

1. Acquisition ledgers.
2. Annotation/cluster visualization.
3. Review-package provenance.
4. Pocket/docking tables.
5. RunPod artifact pulls.
6. Proto design-program sidecar for next-experiment design.

That gives BioSymphony the most leverage: better inputs, better review cards, better provenance, and better cloud hygiene before spending time on heavier AF3-class or workflow-engine rewrites.
