# BioSymphony next tooling radar

**Status:** expansive research pass; not a validated-tool inventory.
**Baseline:** `docs/biosymphony-tooling-status.md`.
**Method:** four parallel research lanes, followed by primary-source checks against project docs, official repositories, and database/paper pages.

This note is intentionally practical. It names tools that fill BioSymphony workflow gaps, the output contracts they should produce, and the next smoke tests that would turn promising candidates into validated BioSymphony lanes.

## What This Adds Beyond The Previous Audit

The previous audit answered "are the existing listed tools current?" and "which new releases are closest to the existing atlas stack?" This pass asks a broader question: what tools, repos, databases, and runtimes would make the **specific BioSymphony GeneCluster workflow** more useful over the next few campaigns?

The answer is not "add everything." The useful additions cluster into six categories:

1. Stage 0 data acquisition and source-ledger hardening.
2. Plant pathway, synteny, coexpression, and metabolite evidence sources.
3. Protein structure, pocket, docking, and enzyme-function lanes.
4. Durable provenance and table-schema validation for figure dossiers.
5. Static review surfaces for genome, structure, and claim inspection.
6. RunPod hardening plus portable cloud overflow paths.

## Immediate Shortlist

| Rank | Candidate | Why It Is Useful Here | First BioSymphony Contract | Gate |
|---:|---|---|---|---|
| 1 | `nf-core/fetchngs` + NCBI Datasets + SRA/ENA/GWH adapters | Stage 0 already depends on public genome/read metadata, but the data acquisition layer should emit stronger normalized ledgers instead of one-off accession heuristics. | `source-ledger.tsv`, `read-accessions.tsv`, `assembly-ledger.tsv`, `checksums.tsv` | No private/raw-heavy files in repo; pin tool versions. |
| 2 | AGAT + `pyGenomeViz` | The cblaster/clinker parked slot exposed annotation-format friction. AGAT is the GFF sanitation workhorse; `pyGenomeViz` gives lightweight static HTML/SVG cluster review without requiring a full browser app. | `annotation-normalization-report.tsv`, `cluster-neighborhood.svg`, `cluster-neighborhood.html` | GPL-3.0 for AGAT; smoke on messy plant GFFs. |
| 3 | PMN 17 / PlantCyc | The repo still frames PlantCyc as PMN 16. PMN 17 is a real upgrade and the best plant-specific pathway/reaction source when license terms are acceptable. | `pmn_pathway_coverage.tsv`, `pmn-reaction-evidence.tsv` | Manual PMN license form; cache outside repo. |
| 4 | PGDD 2.0 / Gramene Plants / PlantPan | BioSymphony needs better source-scout enrichment before running custom synteny. These are plant-specific evidence sources for precomputed synteny, pangenome, pathway, expression, and orthology context. | `external-synteny-evidence.tsv`, `pangenome-context.tsv` | Species coverage is crop-biased; preserve release numbers. |
| 5 | Workflow Run RO-Crate + Process Run Crate + Data Package v2 | Figure dossiers need interoperable provenance without forcing every worker into a full workflow engine. RO-Crate captures runs; Data Package/check-jsonschema validates compact tables. | `ro-crate-metadata.json`, `datapackage.json`, `validation-report.json` | Decide private-path redaction policy. |
| 6 | Boltz-2 + OpenFold3 + P2Rank/fpocket + GNINA/PoseBusters | The structure lane should graduate from "ColabFold structure exists" to "complex, pockets, docking boxes, pose plausibility, and affinity triage are tabulated." | `protein_structure_models.tsv`, `binding_pockets.tsv`, `ligand_pose_scores.tsv` | GPU pods and ligand-prep discipline; predictions are triage evidence. |
| 7 | LOTUS + Rhea + RetroRules 2026 | Gene/pathway evidence should be paired with metabolite occurrence and reaction-template evidence, especially for alkaloid route claims. | `metabolite_occurrence.tsv`, `reaction_template_evidence.tsv` | Occurrence is not biosynthetic proof; synonym cleanup required. |
| 8 | Observable Framework + igv-reports/JBrowse + Molstar/Nightingale | Quarto remains the report spine, but dense review needs sortable claim tables, self-contained locus cards, and pinned protein-structure scenes. | `review/` static site manifest plus per-card HTML/state files | Keep canonical narrative in Quarto; avoid server-only apps. |
| 9 | RunPod S3 artifact pull + rclone/s5cmd | RunPod stays default, but artifact retrieval should prefer direct object-style pulls where available and fall back to proxy-pod pulls only when needed. | `artifact_pull.yaml`, `artifact-pull-report.json` | S3 API is datacenter-limited; never sync raw FASTQ/BAM into repo. |
| 10 | Nextflow/Wave/Fusion, dstack, SkyPilot | Not a v1 replacement for Symphony/RunPod wrappers, but useful for standardized overflow lanes, portable smoke jobs, and eventually AWS/GCP Batch. | provider-neutral `launch-manifest.json` to `nextflow.config`, `dstack.yml`, or `sky.yaml` | More credentials/config surface; use only after wrapper contracts stabilize. |

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

- Use it only when a campaign needs raw public reads or transcript-first evidence.
- Convert fetchngs output samplesheets into BioSymphony `read-accessions.tsv`, `read-materialization.tsv`, and `checksums.tsv`.
- Keep Nextflow reports as secondary artifacts under the cloud run directory.

**Smoke test:** 3-6 small public SRR/ERR/DRR accessions; verify md5 and samplesheet normalization, not biological results.

**Source:** [nf-core/fetchngs GitHub](https://github.com/nf-core/fetchngs).

### SRA Toolkit, ENA API, GWH API, ffq, pysradb

**Fit:** adapters, not competing default platforms.

- SRA Toolkit remains the low-level fallback for `.sra` to FASTQ conversion; use `fasterq-dump` where it fits disk constraints.
- SRA Cloud is the right path when read movement dominates; NCBI documents faster cloud access and unlimited concurrent cloud-bucket downloads.
- ENA Browser/Portal APIs should be used for accession resolution and FTP/metadata mirrors.
- GWH API fills the China National Genomics Data Center plant assembly fallback already named in Stage 0.
- `ffq` and `pysradb` are useful lightweight metadata cross-checkers, especially when nf-core/Nextflow is too heavy for a scout.

**Contract:** every adapter writes the same fields: provider, query, accession, organism, taxid, material type, assembly/read metadata, download URL, checksum when available, license/terms note, timestamp, tool version.

**Sources:** [SRA Toolkit](https://github.com/ncbi/sra-tools), [SRA in the Cloud](https://www.ncbi.nlm.nih.gov/sra/docs/sra-cloud/), [ENA programmatic access](https://ena-docs.readthedocs.io/en/latest/retrieval/programmatic-access.html), [GWH API docs](https://ngdc.cncb.ac.cn/gwh/api_documents), [ffq](https://github.com/pachterlab/ffq), [pysradb](https://github.com/saketkc/pysradb).

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

- Use for first-pass cluster-neighborhood evidence cards.
- Inputs: normalized GFF/GenBank, FASTA coordinates, pairwise similarity links from MMseqs2/blastp.
- Outputs: `cluster-neighborhood.svg`, `cluster-neighborhood.html`, `cluster-neighborhood.links.tsv`.

**Source:** [pyGenomeViz GitHub](https://github.com/moshi4/pyGenomeViz).

### Scan Cluster

**Fit:** best conceptual match for the cblaster/clinker parked slot because it claims database-independent multi-genome conserved-cluster detection from protein FASTA + GFF.

**Current gate:** do not dispatch yet unless a public runnable repo/package is found. The preprint is not enough for a BioSymphony smoke run.

**Action:** keep as `watch-high` and re-check before the next cblaster/clinker investment.

**Source:** [bioRxiv preprint](https://www.biorxiv.org/content/10.64898/2026.04.29.721675v1).

## Plant Pathway, Synteny, Coexpression, And Chemistry Evidence

### PMN 17 / PlantCyc

**Fit:** strongest plant-specific pathway/reaction ground truth once licensing is cleared. PMN 17 includes 583 single-species databases and updated PMN 16 databases, regenerated with Pathway Tools 29.0, E2P2 v5, and updated SAVI validation lists.

**Integration shape:**

- Keep PMN data outside the repo.
- Add `pmn_pathway_coverage.tsv`: candidate protein, projected pathway, PlantCyc reaction, evidence source, orthology method, confidence ceiling.
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

- Add external-evidence adapters that enrich source scout output without replacing BioSymphony's own validation.
- Store release, species coverage, exact query, and any exported row IDs.
- Use as evidence ceilings: "external synteny support" rather than final cluster calls.

**Sources:** [PGDD 2.0 NAR article](https://academic.oup.com/nar/article/54/D1/D1753/8343508), [Gramene Plants 2025 NAR article](https://academic.oup.com/nar/article/54/D1/D1720/8363844), [Ensembl Plants FTP release page](https://plants.ensembl.org/info/data/ftp/index.html), [PlantPan docs](https://ngdc.cncb.ac.cn/plantpan/documentation).

### CoExpPhylo

**Fit:** better than a generic WGCNA lane for biosynthetic discovery. It starts from bait genes and per-species TPM matrices, then combines coexpression, orthology, and phylogeny across species.

**Integration shape:**

- Optional lane after transcript quantification, not a Stage 0 requirement.
- Inputs: bait genes, per-species TPMs, CDS/pep FASTA, sample metadata.
- Outputs: `coexpression_candidate_groups.tsv`, `coexpression_edges.tsv`, `bait_phylogeny.newick`, `coexpression-caveats.md`.

**Gate:** useful only with enough biologically relevant samples; expect ID normalization and memory requirements.

**Sources:** [CoExpPhylo GitHub](https://github.com/bpucker/CoExpPhylo), [BMC Genomics article](https://link.springer.com/article/10.1186/s12864-025-12061-3).

### LOTUS, Rhea, RetroRules 2026

**Fit:** adds non-gene evidence to pathway claims.

- LOTUS provides referenced natural-product structure-organism occurrence pairs under CC0.
- Rhea release 140 has 18,343 unique reaction quartets.
- RetroRules 2026 is the reaction-template upgrade already flagged in the canonical tooling status.

**Integration shape:**

- Add `metabolite_occurrence.tsv`: compound, structure ID, organism/taxon, reference, LOTUS/Wikidata IDs, match method.
- Add `reaction_template_evidence.tsv`: route step, Rhea/RetroRules ID, EC, substrate/product mapping, radius/template, caveat.
- Use this as plausibility and route-context evidence, not proof that a candidate enzyme performs a step.

**Sources:** [LOTUS homepage](https://lotus.nprod.net/), [LOTUS manuscript](https://lotus.nprod.net/lotus-manuscript/), [Rhea statistics](https://www.rhea-db.org/statistics), [RetroRules 2026 NAR article](https://academic.oup.com/nar/article/54/D1/D1799/8373943).

### BiG-SCAPE 2.0 / BiG-SLiCE 2.0

**Fit:** useful only after BioSymphony normalizes plant BGC calls. It can support "known vs novel cluster-family" claims, but microbial bias remains material.

**Integration shape:** convert plantiSMASH/DeepBGC/Scan Cluster regions to minimal GenBank-like cluster records, then emit `gcf_novelty.tsv` and `mibig_similarity.tsv`.

**Gate:** caveat negative evidence heavily for dispersed plant pathways.

**Source:** [BiG-SCAPE GitHub](https://github.com/medema-group/BiG-SCAPE).

## Protein Structure, Docking, And Enzyme Function

### Boltz-2

**Fit:** first-choice open protein-ligand/affinity triage backend. The repo states Boltz-2 models complex structures and binding affinities; code and weights are MIT-licensed.

**Integration shape:**

- Run on GPU pods with fresh environments.
- Output `protein_structure_models.tsv`, `complex_confidence.json`, `affinity_scores.tsv`, and model CIF/PDB files.
- Mark affinity as triage evidence, not experimental binding.

**Gate:** known resolver sensitivity around Python/numpy/CUDA environments; use a clean image.

**Source:** [Boltz GitHub](https://github.com/jwohlwend/boltz).

### OpenFold3 And Protenix-v2

**Fit:** open AF3-style alternatives.

- OpenFold3-preview is Apache-2.0, intended as an AlphaFold3-style biomolecular prediction reproduction and available for academic and commercial use.
- Protenix-v2 remains high-upside, but the local/RunPod audit found a CUDA extension compile/import blocker. Keep it parked until a wheel or custom image path is stable.

**Integration shape:** same structure-model table as Boltz, with model name, license, inputs, GPU type, confidence metrics, and command provenance.

**Sources:** [OpenFold3 GitHub](https://github.com/aqlaboratory/openfold-3), [Protenix GitHub](https://github.com/bytedance/Protenix).

### P2Rank + fpocket

**Fit:** cheap pocket atlas before docking. P2Rank emits pocket centers/residues/probabilities from protein structures; fpocket gives fast Voronoi-based pocket descriptors.

**Integration shape:**

- Run both on predicted/experimental structures.
- Merge into `binding_pockets.tsv`: structure ID, pocket ID, center coordinates, residues, rank, method, confidence, recommended docking box.
- Generate PyMOL/ChimeraX pocket surfaces and Molstar state files.

**Sources:** [P2Rank GitHub](https://github.com/rdk/p2rank), [fpocket GitHub](https://github.com/Discngine/fpocket).

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

**Fit:** turns function calls into a jury instead of a single EC guess.

- HIT-EC is now validated locally in the repo, and its interpretability/contribution-score angle fits enzyme-function votes.
- EnzPlacer fills EC1-3 novelty space, especially outside training-corpus comfort zones.
- EnzyMM adds M-CSA-derived 3D catalytic-motif evidence.
- ESM-C 300M, SaProt, and ProstT5 support protein-family maps and structure-aware similarity.

**Integration shape:**

- Normalize all function evidence into `protein_function_votes.tsv`.
- Add `catalytic_site_evidence.tsv` for EnzyMM/site-template calls.
- Add `plm_embedding_index.tsv` for embedding files, model, dimensionality, sequence hash, and downstream plot/table links.

**Sources:** [HIT-EC GitHub](https://github.com/datax-lab/HIT-EC), [EnzPlacer GitHub](https://github.com/drxiangma/EnzPlacer), [EnzyMM GitHub](https://github.com/rayhackett/enzymm), [SaProt GitHub](https://github.com/westlake-repl/SaProt), [ProstT5 GitHub](https://github.com/mheinzinger/ProstT5).

## Provenance, Dossier Packaging, And Review Surfaces

### Workflow Run RO-Crate + Process Run Crate

**Fit:** best match for BioSymphony's scientific-ledger model. Process Run Crate explicitly supports ad hoc command-line runs, which matches Symphony workers better than forcing a full workflow engine.

**Integration shape:**

- Keep `figure_manifest.json` as the local BioSymphony contract.
- Add `ro-crate-metadata.json` as the interoperable provenance envelope.
- Represent each worker command as a `CreateAction` with inputs, outputs, software, versions, container image digest, Linear issue ID, run status, and validation command.
- Redact private absolute paths in public/exportable crates.

**Sources:** [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/), [Process Run Crate](https://www.researchobject.org/workflow-run-crate/profiles/process_run_crate/), [ro-crate-py](https://pypi.org/project/rocrate/), [runcrate](https://www.researchobject.org/runcrate/readme.html).

### Data Package v2 + check-jsonschema

**Fit:** cheap schema validation for compact TSV/CSV/JSON deliverables. It complements RO-Crate; it does not replace provenance.

**Integration shape:**

- Add `datapackage.json` to figure dossiers and provider handoffs.
- Use `check-jsonschema` in `genecluster_atlas_contracts.py` or a companion validator for manifest schemas and table resource schemas.

**Sources:** [Data Package GitHub](https://github.com/frictionlessdata/datapackage), [check-jsonschema GitHub](https://github.com/python-jsonschema/check-jsonschema).

### Observable Framework

**Fit:** static review site for dense tables and filtering. Use it when Quarto pages become too narrative-heavy for claim triage.

**Integration shape:** generate `review/observable/` from compact TSV/JSON ledgers: claim ledger, species/candidate tables, validation status, source hashes, artifact manifest.

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
figure-dossier/
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

**Integration shape:** profiles such as `local-smoke`, `runpod-docker-wrapper`, `awsbatch`, `google-batch`, and `k8s`. Treat this as a future portability layer, not a replacement for the current Symphony issue-contract model.

**Sources:** [Nextflow executors](https://www.nextflow.io/docs/latest/executor.html), [Wave containers](https://docs.seqera.io/nextflow/wave), [Fusion file system](https://docs.seqera.io/nextflow/fusion).

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
| F4 | Dossier provenance skeleton | Add RO-Crate + Data Package skeleton for an existing `.runtime` figure dossier | parseable `ro-crate-metadata.json`, `datapackage.json`, validation report | local |
| F5 | Pocket/docking table smoke | P2Rank + fpocket on one ColabFold model; PoseBusters on one known ligand pose | `binding_pockets.tsv`, `posebusters.json` | small CPU pod, minutes |
| F6 | Boltz-2 clean-image smoke | One protein-ligand YAML on a fresh GPU pod | model CIF/PDB, confidence JSON, affinity TSV | small GPU pod, minutes |
| F7 | Cloud artifact-pull abstraction | No paid biological run; test against a tiny volume/file set where the provider's object-storage API exists | `artifact-pull-report.json`, checksum report | maybe free/local + tiny pod |
| F8 | Observable claim explorer prototype | Build from existing atlas TSV/JSON only | static `review/observable/` | local |

**Implementation note:** F4 has a first local implementation in
`skills/biosymphony/scripts/genecluster_dossier_skeleton.py`: generated
GeneCluster dossier skeletons now include `datapackage.json` and
`ro-crate-metadata.json` plus `validation-report.json`, and
`genecluster_preflight.py --dossier-manifest` validates those sidecars.

F1 also has a first local contract hardening pass: `genecluster_source_scout.py`
now emits self-identifying source-scout rows with provider/accession/material
fields, `genecluster_sra_runinfo.py` emits `read-accessions.tsv`, and
`genecluster_preflight.py` validates both the no-network source-scout policy and
normalized read-acquisition rows.

F7 also has a local control-plane implementation: launch bundles now emit
`artifact_pull.yaml`, and `genecluster_preflight.py --artifact-pull-manifest`
validates summary-only includes, raw/heavy excludes, max-byte limits, checksum
mode, and local destination policy before any artifact sync happens.
`--launch-manifest` validation follows and hashes the same pull-manifest pointer
when present, so launch bundles catch artifact-return policy drift as part of
the normal preflight.

## Reject Or Defer

| Candidate | Decision |
|---|---|
| AlphaFold3 | Defer as a BioSymphony default: parameter/terms gates and non-commercial constraints do not fit open worker lanes. |
| Chai-2 | Defer: partner/API access, not a public repo lane. |
| ESM-3 / ESM-C 6B | Defer for default workflow: gated/commercial surfaces; use ESM-C 300M, ESM-2, SaProt, and ProstT5 where appropriate. |
| PanBGC / GECCO / antiSMASH as plant defaults | Defer for this workflow: bacterial/fungal or PKS/NRPS-heavy; plantiSMASH + DeepBGC remain the plant BGC defaults. |
| NPAtlas / COCONUT as primary evidence | Keep as chemistry background only; LOTUS is a better fit for taxon-compound occurrence claims. |
| Generic Streamlit/Shiny/Reflex dashboards | Defer as default. Static Quarto/Observable/HTML dossiers are better for durable review and handoff. |
| Replacing RunPod with AWS/GCP immediately | Reject. RunPod remains the validated default; AWS/GCP are overflow paths for SRA-heavy or regulated/auditable runs. |
| Vast.ai for private data | Reject. Marketplace trust model is not acceptable for unpublished/private biological material. |
| Object storage as executable POSIX workdir | Reject unless a workflow/filesystem layer handles it. Use object stores for inputs, caches, and derived artifact pulls. |
| Full workflow-engine migration just for metadata | Reject. RO-Crate/Data Package solves the immediate provenance gap with less operational churn. |

## Working Recommendation

Do not replace the current validated atlas stack. Add **one narrow smoke flight per gap**:

1. Acquisition ledgers.
2. Annotation/cluster visualization.
3. Dossier provenance.
4. Pocket/docking tables.
5. RunPod artifact pulls.

That gives BioSymphony the most leverage: better inputs, better evidence cards, better provenance, and better cloud hygiene before spending time on heavier AF3-class or workflow-engine rewrites.
