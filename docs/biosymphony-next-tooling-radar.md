# Tooling Radar

Reviewed 2026-11-13. Evaluate a tool when its output resolves a specific gap in
a campaign. Use the [evaluation checklist](tooling/tool-evaluation.md)
to record the fixture, versions, output checks, and decision.

## Annotation And Gene Order

| Tool | Use | Evaluation |
|---|---|---|
| [AEGIS 1.0.1](https://github.com/Tomsbiolab/aegis/releases/tag/v1.0.1), 2026-11-10 | Normalize GFF3, extract proteins, and compare annotation releases. | A one-CDS synthetic translation passed. Compare strand, phase, and parent IDs with the existing parser on an Arabidopsis fixture. Orthology requires additional tools. [Paper](https://doi.org/10.1093/bioinformatics/btag363) |
| [Tiberius 2.0.9](https://github.com/Gaius-Augustus/Tiberius/releases/tag/v2.0.9), 2026-10-05, or [GeneCAD 0.6.1](https://github.com/plantcad/genecad/releases/tag/v0.6.1), 2026-10-19 | Predict plant gene models when the assembly lacks annotation. | Use one caller and an independent comparator. Check exon recovery, long introns, coordinate and transcript IDs, and checkpoint terms. [Tiberius preprint](https://doi.org/10.64898/2026.04.24.720536), [GeneCAD preprint](https://doi.org/10.1101/2025.10.31.685877) |
| [SyntenyQC](https://github.com/Tim-Kirkwood/SyntenyQC) | Select representative cblaster neighborhoods for clinker. | Check accession mapping and selection stability. Preserve coordinates when pruning similar regions. [Paper](https://doi.org/10.1093/bioinformatics/btaf626) |
| [OrthoFinder 3.2](https://github.com/OrthoFinder/OrthoFinder/releases/tag/v3.2), 2026-10-23 | Infer orthogroups and duplication history across proteomes. | Preserve co-orthologs and join protein IDs to coordinates before making gene-order claims. Update parsers for renamed `Orthologs/` and compressed per-species TSVs. [Methods paper](https://doi.org/10.1038/s41592-026-03126-6) |
| [SyMAP 5.9.3](https://github.com/csoderlund/SyMAP/releases/tag/v5.9.3), 2026-11-08, or [ntSynt 1.0.9](https://github.com/BirolLab/ntSynt/releases/tag/v1.0.9), 2026-08-20 | Compare assembly-scale blocks. SyMAP takes genomic sequence and optionally GFF. ntSynt works without annotation. | Compare a known block and resolve the sequence IDs and coordinates used by the annotation. SyMAP needs Java and MySQL. [SyMAP documentation](https://agcol.arizona.edu/SyMAP/), [ntSynt paper](https://doi.org/10.1186/s12915-025-02455-w) |
| [HIT-EC 2.0.0](https://github.com/datax-lab/HIT-EC/releases/tag/v2.0.0) | Add EC predictions and residue relevance to candidate evidence. | Compare coverage, rare-class error, and abstention with homology and CLEAN on held-out plant proteins. Record model terms separately. [Paper](https://doi.org/10.1038/s41467-026-68727-3) |

Consider [Helixer](https://doi.org/10.1038/s41592-025-02939-1) or
[PlantGeneAnn v2](https://doi.org/10.64898/2026.06.25.733695) as a gene-caller
comparator. Evaluate [PlantCAD2](https://doi.org/10.1016/j.xgen.2026.101329)
only with a defined prediction task, a simple baseline, and a species-held-out
split.

## Transcriptome Evidence

| Tool | Use | Evaluation |
|---|---|---|
| [pyTransRate](https://github.com/macmanes-lab/pytransrate), [October preprint](https://arxiv.org/abs/2610.37031v2) | Check a de novo transcriptome against its source reads, or summarize contigs from FASTA alone. | FASTA-only check passed with two synthetic contigs. Test read-based metrics on paired reads before using them to filter candidates. Compare scores only within the same library and implementation. |
| [IsoQuant 4.1.0](https://github.com/ablab/IsoQuant/releases/tag/v4.1.0) and [SQANTI3 6.1](https://github.com/ConesaLab/SQANTI3/releases/tag/v6.1), 2026-10-20 | Reconstruct transcripts from genome-aligned long reads, then classify and inspect isoforms. | Check transcript IDs, splice junctions, and support across samples. SQANTI3 6.1 requantifies during rescue by default. Record whether rescue affects the reported counts. |

Use the transcriptome-only route when the source lacks reliable genome
coordinates. Report transcript support and retain the source contig IDs.

## Find Public Inputs

| Source | Use | Record |
|---|---|---|
| [NCBI Datasets 18.41.1](https://github.com/ncbi/datasets/releases/tag/v18.41.1), 2026-11-13 | Retrieve assembly metadata and selected genome, annotation, or protein files. | Versioned assembly accession, annotation release, requested file types, and checksum. |
| [Ensembl](https://www.ensembl.org/) | Browse plant assemblies and annotations on the unified site. Its 2026-07 release included genesets from Ensembl Genomes 63. | Browser release and assembly accession. Use the [archive](https://www.ensembl.org/help/articles/archives) to reproduce an older run. [Migration notice](https://www.ebi.ac.uk/about/news/updates-from-data-resources/ensembl-new-website/) |
| [PGDD 2.0](https://plantgenome.uga.edu/) | Look up plant duplication and collinearity records before computing synteny. | Source assembly and annotation releases. Cross-check a known block. [Paper](https://doi.org/10.1093/nar/gkaf1287) |
| [nf-core/fetchngs 1.13.0](https://github.com/nf-core/fetchngs/releases/tag/1.13.0), 2026-09-15 | Retrieve public read metadata and stage FASTQs when RNA-seq is in scope. | Sample-to-run mapping, archive accessions, and data volume. Use metadata first. |

For plant pathways and curated enzyme records, see
[PlantCyc and P450 resources](tooling/plantcyc-p450rdb.md) and
[Rhea](https://www.rhea-db.org/). Use [ATTED-II 13](https://atted.jp/) for
coexpression and [PlantPAN 5.0](https://doi.org/10.1093/nar/gkag1140) for
regulatory context. For PlantPAN, record the species, assembly and experimental
condition. Keep motif predictions separate from measured binding.

## Source Adapters And Provenance

Prefer the provider API for accession lookups. The [InterPro API](https://interpro-documentation.readthedocs.io/en/latest/api.html)
and [InterPro MCP](https://doi.org/10.1093/nar/gkag1114) cover public signature
and protein records. For a missing lookup, consider
[ToolUniverse 1.5.9](https://github.com/mims-harvard/ToolUniverse/releases/tag/v1.5.9)
or [BioContextAI](https://github.com/biocontext-ai/knowledgebase-mcp). Record the
accession, source release, and retrieval date.

Use [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/)
if a downstream tool needs portable run metadata. Start with existing
provenance fields and artifact hashes. Use small synthetic cases for missing
records and misleading metadata.
