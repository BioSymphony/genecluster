# Tooling Radar

Reviewed: 2026-09-22. Dates below identify publications or releases, not local validation.

Prioritize HIT-EC for enzyme evidence, SyntenyQC for neighborhood review, and one plant gene caller where annotation is missing. Evaluate PlantCAD2 only for a defined prediction task. These candidates remain **planned**; this review adds no installed tools, downloaded models, or checked baselines.

Choose one primary gene caller and one comparator per fixture. SyntenyQC selects local neighborhoods; ntSynt maps assembly-scale blocks; PGDD supplies precomputed collinearity.

## Evaluate First

| Candidate and source | Recent evidence | Potential input/output | Terms, resources, and adoption requirement |
|---|---|---|---|
| [HIT-EC](https://github.com/datax-lab/HIT-EC) | [Nature Communications, 2026-01-30](https://doi.org/10.1038/s41467-026-68727-3); v2.0.0 | Protein FASTA → hierarchical EC predictions and residue relevance maps | MIT code; check model/data terms separately. CPU/GPU demo. Compare held-out plant proteins with homology and CLEAN; measure abstention and rare-class errors. Relevance maps are not calibrated confidence. |
| [SyntenyQC](https://github.com/Tim-Kirkwood/SyntenyQC) | [Bioinformatics, 2025-11-13](https://doi.org/10.1093/bioinformatics/btaf626); 2.0 released 2025-08-22 | cblaster results/accessions → selected GenBank neighborhoods and similarity tables for clinker | MIT. Retrieval and DIAMOND costs grow with neighborhood count. Check identifier mapping and reproducible selection. Similarity-based pruning does not establish orthology or BGC boundaries. |
| [Tiberius](https://github.com/Gaius-Augustus/Tiberius) | [Preprint v2, 2026-07-29](https://doi.org/10.64898/2026.04.24.720536); [code v2.0.7](https://github.com/Gaius-Augustus/Tiberius/releases/tag/v2.0.7) | Genome FASTA, optionally expression/protein evidence → GTF/GFF3 gene models | MIT code; confirm checkpoint terms. GPU recommended; CPU supported. Evaluate an angiosperm checkpoint against held-out annotation and evidence-supported gene callers. Structural annotation does not assign biochemical function. |
| [GeneCAD](https://github.com/plantcad/genecad) | [Preprint v4, 2026-05-12](https://doi.org/10.1101/2025.10.31.685877); [v0.5.0 released 2026-09-20](https://github.com/plantcad/genecad/releases/tag/v0.5.0) | Plant genome FASTA → predicted and filtered GFF3 | Apache-2.0 code; record each dependent model revision and license. NVIDIA GPU; large intermediate arrays. Test coordinate conventions, long introns, and canonical-transcript coverage before downstream use. |
| [PlantCAD2](https://github.com/plantcad/plantcad) | [Cell Genomics, 2026-09-09](https://doi.org/10.1016/j.xgen.2026.101329) | DNA windows → embeddings or task-specific predictions | Apache-2.0 repository code; verify checkpoint, data, and paper terms separately. Models span 88M–694M parameters and 8,192-bp windows. Use a species-held-out test and a simple baseline. Embeddings do not establish function, causality, or physical clustering. |
| [PGDD 2.0](https://plantgenome.uga.edu/) | [NAR paper, 2025-11-26](https://doi.org/10.1093/nar/gkaf1287) | Public identifiers → collinearity, duplication, and synteny context | Prefer compact precomputed records. Preserve genome release and accession provenance; source-data terms vary. Verify the retrieval interface and cross-check a known block before adoption. |

## Compare or Watch

| Candidate | Reason to retain | Reason to defer |
|---|---|---|
| [PlantGeneAnn v2](https://github.com/qzzhang0131/PlantGeneAnn), [preprint, 2026-06-26](https://doi.org/10.64898/2026.06.25.733695) | Independent plant FASTA → GFF3 comparator; code labeled MIT; verify checkpoint terms | CUDA-specific stack and large probability caches. Use only after one primary gene caller has a checked fixture. |
| [Helixer](https://github.com/usadellab/Helixer), [Nature Methods, 2025-11-24](https://doi.org/10.1038/s41592-025-02939-1) | Established genome → primary gene-model GFF3 baseline | GPL-3.0 code; verify checkpoint terms. Retain as a comparator instead of adding another default runtime. |
| [ntSynt](https://github.com/BirolLab/ntSynt), [BMC Biology, 2025-12-29](https://doi.org/10.1186/s12915-025-02455-w) | Annotation-free macrosynteny blocks from multiple assemblies; GPL-3.0-or-later | Needs a plant/polyploid fixture and memory budget. Macrosynteny does not resolve gene-level neighborhoods. |
| [RXNRECer](https://github.com/kingstdio/RXNRECer), [preprint, 2026-03-13](https://arxiv.org/abs/2603.12694) | Protein FASTA → Rhea reaction candidates; MIT code | Consider the smaller S1 stage first. Full stages add large downloads, GPU/container dependencies, and an external LLM. Reaction scores need independent evaluation. |
| [PlantBGC](https://pypi.org/project/plantbgc/), [preprint, 2026-07-29](https://arxiv.org/abs/2607.27258) | Plant-domain sequences → candidate-locus scores | Code-license statements conflict; resolve them before integration. Weak labels do not establish boundaries or chemistry. |
| [PlantBiMoE](https://github.com/HUST-Keep-Lin/PlantBiMoE), [preprint, 2025-12-08](https://arxiv.org/abs/2512.07113) | Long-context plant sequence representation | Model-card and repository licensing differ in completeness. No direct neighborhood contract; compare only for a defined sequence task. |
| [ANNEVO](https://github.com/xjtu-omics/ANNEVO), [Nature Methods, 2026-03-12](https://doi.org/10.1038/s41592-026-03036-7) | Additional genome → GFF3 comparator | Noncommercial code terms limit reuse; gene callers already cover the immediate evaluation need. |
| [Horizyn](https://github.com/dayhofflabs/horizyn), [PNAS, 2026-03-17](https://doi.org/10.1073/pnas.2520070123) | Enzyme/reaction similarity evidence | Noncommercial code and separate hosted access. Similarity scores are not calibrated function probabilities. |

## Agent Tools and Evaluation

| Resource | Useful addition | Keep the integration small |
|---|---|---|
| [ToolUniverse v1.5.1](https://github.com/mims-harvard/ToolUniverse/releases/tag/v1.5.1), released 2026-09-22 | Discover and inspect scientific tool interfaces through SDK, CLI, or MCP; Apache-2.0 | Evaluate a few read-only source lookups. Pin an allowed subset and retain source identifiers and retrieval dates. Upstream service terms remain separate; the full server can expose code execution. |
| [BioContextAI Knowledgebase MCP](https://github.com/biocontext-ai/knowledgebase-mcp), [Nature Biotechnology paper](https://doi.org/10.1038/s41587-025-02900-9) | Literature and knowledgebase retrieval through an Apache-2.0 server | Choose it only where an existing adapter is missing. Public hosting is a test service with fair-use limits; data licenses remain separate. |
| [BioAgent Bench](https://github.com/bioagent-bench/bioagent-bench), [preprint, 2026-01-29](https://arxiv.org/abs/2601.21800) | Corrupted-input, decoy-file, and prompt-bloat evaluation patterns | CC BY-4.0 benchmark materials; dataset terms vary. Use small synthetic checks; upstream agent/grader scores do not establish correctness here. |
| [BixBench3](https://github.com/EdisonScientific/BixBench3), [preprint, 2026-08-26](https://arxiv.org/abs/2608.25286) | Artifact-based grading of multi-step analyses | CC BY-SA-4.0 harness/materials; source-data terms vary. Defer full runs: billed cloud/model access, large datasets, and separately licensed software. |
| [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) | Portable provenance profiles for existing output manifests | Start with metadata references and hashes. Keep raw data, credentials, environment captures, and full execution logs outside public packages. The foundational paper is from 2024. |

Choose a source gateway only where a direct adapter is missing; avoid installing both general catalogs. Pin BioContextAI locally for repeatable retrieval.

Defer [Biomni](https://github.com/snap-stanford/Biomni) until a defined missing capability, isolated runtime, component license inventory, and public fixture justify its broader environment.

## Promotion Requirements

Use the [tool evaluation contract](tooling/tool-evaluation.md) before adding a wrapper or changing a baseline. Record immutable code, model, and database versions separately. Keep one evaluation record per candidate, with public sources, resource limits, compact results, and an explicit decision.

Existing [Ensembl Plants](https://plants.ensembl.org/), [ATTED-II](https://atted.jp/), [Rhea](https://www.rhea-db.org/), and [RetroRules](https://retrorules.org/) remain source options. Check the release used by each campaign. Design-generation tools remain outside this annotation and comparative-analysis shortlist.
