# GeneCluster Resource Registry

Status: draft
Last reviewed: 2026-05-15

This registry is for BioSymphony GeneCluster planning. It lists tools,
databases, and report components that can superpower public or
academic-personal plant pathway, specialized-metabolism, and gene-neighborhood
campaigns while keeping local BioSymphony skill code permissively licensed.

The default posture is local-first analysis of public data. Public webservers
are useful for public accession-derived sequences and teaching/demo work, but
campaigns must not upload private sequences, unpublished assemblies, proprietary
gene sets, embargoed structures, or collaborator-restricted datasets to public
webservers. Use local or controlled cloud containers for those inputs.

This is not legal advice. Every campaign should record exact tool/database
versions and re-check licenses before redistribution, publication, commercial
use, or any upload to hosted services.

## Licensing Policy

BioSymphony skill code should remain MIT licensed where possible.

Third-party resources should be treated as orchestrated dependencies, not
vendored skill content, unless their license is explicitly compatible with
redistribution in this repo.

Do:

- keep wrappers, manifests, validators, and docs in this repo under
 MIT-compatible terms
- install third-party tools in local, RunPod, or container environments from
 upstream channels
- record each dependency license in `versions.json` or `licenses.tsv`
- return links, citations, checksums, and derived summaries instead of copying
 large databases into the repo
- separate personal/academic-friendly tools from resources with commercial,
 redistribution, API, account, or public-upload restrictions
- record whether evidence comes from genome, transcriptome, expression,
 coexpression, synteny, pathway, metabolomics, literature, or manual curation

Do not:

- vendor GPL, LGPL, AGPL, or unreviewed code/databases into the MIT skill repo
- assume "free webserver" means redistributable, private-data-safe, or
 corporate-safe
- upload private sequences, unpublished structures, proprietary datasets, or
 collaborator-restricted files to public webservers
- redistribute KEGG, UniProt, InterPro, NCBI, PMN/PlantCyc, BioCyc/MetaCyc, or
 other database snapshots without checking current terms
- treat predicted BGCs, coexpression modules, or pathway assignments as
 experimentally validated chemistry

## License Classes

Use these classes in `resource-ledger.tsv` and campaign manifests:

- `permissive-code`: MIT, BSD, Apache-2.0, ISC, Artistic, public-domain-style,
 or similar code license
- `copyleft-code`: GPL, LGPL, AGPL, or similar; usable as external tools, but do
 not copy into the MIT repo
- `academic-free-or-web`: free for academic/personal use or public webserver
 use; check before commercial use, redistribution, or private-data upload
- `open-data-with-terms`: public databases with citation, attribution,
 rate-limit, redistribution, account, or bulk-download terms
- `account-or-api-terms`: usable through account/API terms; avoid hardcoding
 tokens and record the governing terms
- `restricted-or-review`: requires manual review before use, redistribution,
 cloud upload, commercial work, or dossier bundling

Do not use `open-source` as a license class in ledgers. Resolve it to one of the
classes above so automation can decide whether vendoring, redistribution, or
commercial use requires review.

## Use Mode Classes

Use these values in `use_mode` fields:

- `local_validator`: repo-owned wrapper or validator
- `local_tool`: local workstation or lab-server execution
- `remote_provider`: compute provider
- `remote_storage`: remote volume or object storage
- `remote_container`: tool runs inside a remote container/env
- `remote_database`: database used remotely or cached on remote storage
- `remote_api`: remote API access
- `webserver`: public webserver upload/use, only for public or approved inputs
- `embedded-ui`: browser/report component bundled into the dossier
- `derived-summary`: small derived result tables
- `deferred_remote_container`: planned remote tool, not used in the v0 run

## Redistribution Policy Classes

When a resource can appear in a dossier, record one of:

- `none`
- `attribution-required`
- `notices-required`
- `no-bulk-redistribution-without-review`
- `commercial-license-required`
- `do-not-vendor-code`
- `public-inputs-only`

## Workflow Engines And Packaging

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| Nextflow | Workflow engine for RunPod/container controller | permissive-code | Preferred v1 engine because resume, reports, containers, and cloud/object-store patterns are mature. |
| nf-core/fetchngs | Public accession import | permissive-code for pipeline; verify dependency licenses | Use for SRA/ENA/GEO/DDBJ metadata and samplesheets. |
| nf-core/rnaseq | Reference RNA-seq lane | permissive-code for pipeline; verify dependency licenses | Use when a good genome/GFF exists; track STAR/Salmon/subread dependency licenses separately. |
| nf-core/nanoseq | Long-read RNA-seq lane | permissive-code for pipeline; verify dependency licenses | Useful for ONT/direct RNA or cDNA lanes; dependency licenses vary. |
| nf-core/modules | Reusable process modules | permissive-code for modules; verify wrapped tools | Good source for robust wrappers, but copy only license-compatible snippets with notices. |
| Snakemake | Alternative workflow engine | permissive-code | Good fallback for Pythonic rules and local lab servers. |
| CWL / WDL | Portable workflow specifications | permissive-code for specs; engines vary | Useful if a collaborator already standardizes on these engines. |
| Bioconda / conda-forge | Package channels | restricted-or-review | Use package-level license reports; do not assume all packages are permissive. |
| Docker / OCI images | Reproducible environments | restricted-or-review | Pin image digests and maintain an image bill of materials. |
| Apptainer / Singularity | HPC-friendly containers | permissive-code | Useful for university clusters where Docker is unavailable. |

## Data Acquisition, QC, And Provenance

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| NCBI SRA Toolkit / fasterq-dump | FASTQ retrieval fallback | open-data-with-terms | Prefer workflow-native fetch first; use local/RunPod only for large public data. |
| NCBI Datasets CLI | Genome/protein/GFF metadata and retrieval | open-data-with-terms | Useful for accession-to-reference resolution; NCBI-created content is low-friction, but submitted/third-party content can carry separate rights. |
| ENA Browser / API | Public reads metadata/download | open-data-with-terms | Often easier/faster for FASTQ retrieval than SRA conversion. |
| DDBJ | Public reads/sequence archive | open-data-with-terms | Include when accession geography or metadata is DDBJ-first. |
| NGDC GWH API | Plant genome/assembly metadata fallback | open-data-with-terms | Public accessions only; record API URL/date and do not bulk-redistribute without review. |
| SRA Cloud public buckets | Public read data in cloud object stores | open-data-with-terms | Prefer for read-heavy campaigns; raw FASTQ/BAM/SRA artifacts stay cloud-side and out of the repo. |
| GEO / ArrayExpress | Expression experiment metadata | open-data-with-terms | Use for public expression evidence; preserve sample annotations and accessions. |
| Phytozome / JGI | Plant genomes and annotations | account-or-api-terms | Strong plant source, but account/license terms and redistribution limits matter. |
| Ensembl Plants / Gramene | Plant genome annotations and comparative context | open-data-with-terms | Good reference annotations and IDs; preserve release numbers. |
| CoGe | Comparative genomics workspace | academic-free-or-web/account-or-api-terms | Useful for public synteny/genome context; avoid private-data upload unless workspace and terms are explicitly approved. |
| ffq | Sequencing metadata resolver | permissive-code | Useful accession metadata helper; external API terms still apply. |
| pysradb | SRA/ENA/GEO metadata resolver | permissive-code | BSD-3 helper; external SRA/ENA/GEO terms still govern acquired data. |
| iSeq | Public sequence data retrieval helper | restricted-or-review | Useful fallback for multi-source accession retrieval; resolve license before enabling by default. |
| fastp | Read trimming/QC | permissive-code | Good default for read preprocessing. |
| FastQC | Read QC | copyleft-code | Feed into MultiQC; run externally. |
| MultiQC | QC aggregation | copyleft-code | Primary QC report component; run externally and record version. |
| BUSCO / compleasm | Assembly and gene-set completeness QC | permissive-code/open-data-with-terms | Use transcriptome/genome/protein mode; record lineage dataset version and dataset terms. |
| QUAST / BUSCO plots / seqkit stats | Assembly and FASTA sanity checks | restricted-or-review | Record contig N50, scaffold count, ambiguous bases, and BUSCO lineage; resolve package licenses per environment. |
| Workflow Run RO-Crate / Process Run Crate | Dossier provenance packaging | permissive-code/open standard | Good target for durable campaign provenance; omit private paths from public exports. |
| Data Package v2 / check-jsonschema | Tabular dossier schemas and validation | permissive-code | Validates compact table resource schemas; does not replace provenance. |

## Genome Annotation And Anchoring

Use this section when a GeneCluster campaign needs genomic coordinates, reliable
gene models, or cross-assembly anchoring before calling BGCs.

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| BRAKER3 | Evidence-guided eukaryotic gene prediction | permissive-code/restricted-or-review | Strong default for new eukaryotic genomes with RNA-seq/protein evidence; GeneMark licensing and AUGUSTUS config handling need explicit review. |
| AUGUSTUS | Ab initio/evidence-assisted gene prediction | permissive-code for code; trained parameters vary | Often pulled through BRAKER/GALBA; record species model source. |
| TSEBRA | Transcript selector for BRAKER predictions | permissive-code; verify resolved package | Useful to combine and rank gene predictions. |
| GALBA | Protein-guided annotation for novel genomes | permissive-code/restricted-or-review | Useful when high-quality related proteins exist and RNA-seq is absent; resolve dependencies before defaulting. |
| Tiberius | Deep-learning gene finder | permissive-code | Promising extra lane for eukaryotic gene models; treat as evidence until benchmarked for the species. |
| MAKER / MAKER-P | Classic evidence-integrating annotation pipeline | restricted-or-review | Useful but dependency and license environment should be resolved before default use. |
| EvidenceModeler | Consensus gene model integration | restricted-or-review | Good for merging ab initio, transcript, and protein evidence; verify license/dependencies. |
| PASA | Transcript alignment assembly and annotation update | restricted-or-review | Useful for UTRs, splice refinement, and annotation updates; run externally. |
| Liftoff | Annotation lift-over between close assemblies | copyleft-code | Good for anchoring known genes to a new assembly; report unmapped/partial/duplicated genes. |
| Miniprot | Protein-to-genome spliced alignment | permissive-code | Good fast protein evidence lane; preserve alignment scores and frameshift flags. |
| miniprot/minimap2 | Genome/protein anchoring alignments | permissive-code | Use for lift-over sanity checks and neighborhood anchoring; do not replace gene model review. |
| AGAT | GFF/GTF normalization and repair | copyleft-code | GPL-3.0; useful before BGC/synteny tools; run externally and emit `annotation-normalization-report.tsv`. |
| gffread / gffcompare | Transcript and GFF/GTF conversion/comparison | permissive-code | Core utility for extracting CDS/proteins and comparing annotations. |
| BEDTools / SAMtools / HTSlib | Coordinate and alignment plumbing | permissive-code | Keep as external dependencies; record versions and package-level licenses. |
| EDTA / RepeatModeler / RepeatMasker / Dfam | Repeat annotation and masking | restricted-or-review | Plant genomes need repeat-aware annotation; Dfam/RepBase/RepeatMasker terms differ. |
| NCBI Genome Annotation Pipeline output | Reference gene models when available | open-data-with-terms | Good for public references; preserve accession, assembly version, and annotation release. |

## Transcriptome Assembly, Isoforms, Splicing, And Deduplication

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| Trinity | Short-read transcriptome assembly baseline | permissive-code | Keep as a comparison lane, not sole truth. |
| rnaSPAdes | Short-read/hybrid transcript assembly | copyleft-code | Strong current default lane for de novo transcriptomes; run externally. |
| RNA-Bloom2 | De novo transcriptome assembly | copyleft-code | Useful for large/non-model transcriptomes; run externally. |
| Oyster River Protocol | Ensemble transcriptome assembly | restricted-or-review | Useful for benchmarking/ensemble assemblies; resolve current repo/package licenses before default use. |
| TransPi | De novo transcriptome pipeline | restricted-or-review | Useful as an ensemble/non-model transcriptome lane; resolve current license before default use. |
| Trans2express | Plant-focused de novo transcriptome workflow | restricted-or-review | Consider as plant-oriented lane after license/tool review. |
| StringTie2 | Genome-guided transcript assembly | permissive-code | Useful when a reference genome exists. |
| Scallop / PsiCLASS | Genome-guided transcript assembly alternatives | restricted-or-review | Useful benchmark lanes; verify license and maintenance. |
| IsoQuant | Long-read transcript discovery/quantification | copyleft-code | Strong Iso-Seq/ONT lane; run externally. |
| FLAIR2 | Long-read isoform correction/annotation | restricted-or-review | Use with short-read splice correction where available after license review. |
| TALON | Long-read transcript discovery and annotation | restricted-or-review | Useful alternative isoform catalog lane; verify current license. |
| bambu | Long-read transcript discovery/quantification | permissive-code | R/Bioconductor lane; verify package license in resolved env. |
| SQANTI3 | Long-read isoform QC/curation | copyleft-code | Current standard for long-read isoform artifact filtering; run externally. |
| Cupcake / cDNA_Cupcake | Iso-Seq cleanup utilities | restricted-or-review | Useful for collapse, polish, and classification; verify terms. |
| TransDecoder | ORF prediction | permissive-code | Standard coding-sequence extraction from transcriptomes. |
| EvidentialGene | Transcript deduplication and best-ORF selection | restricted-or-review | Useful for transcriptome-only campaigns; record thresholds to avoid collapsing paralogs. |
| CD-HIT | Redundancy reduction | copyleft-code | Use cautiously to avoid collapsing paralogs/alleles; run externally. |
| MMseqs2 cluster / linclust | Large-scale sequence clustering and deduplication | permissive-code | Preferred fast clustering lane as of current MIT-licensed releases; record release because older references may cite GPL. |
| OrthoFinder longest-transcript helper | Orthology input de-isoforming | copyleft-code | Useful when preparing proteomes for comparative work; keep original isoform table in dossier. |
| SUPPA2 / rMATS / MAJIQ | Alternative splicing analysis | restricted-or-review | Optional when splice regulation is part of the biological hypothesis; resolve package licenses first. |

## Local Similarity Search And Sequence Stores

For private, unpublished, or proprietary inputs, use local BLAST/DIAMOND/MMseqs2
databases or controlled containers. Public remote BLAST-like services are for
public or explicitly approved inputs only.

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| BLAST+ | Compatibility sequence search | open-data-with-terms | Useful for CRO-style output compatibility and exact BLAST expectations. |
| DIAMOND | Fast protein/translated nucleotide similarity search | copyleft-code | Default for large protein hit searches; GPL-family tool, run externally. |
| MMseqs2 | Fast sequence search, clustering, taxonomy, and GPU-accelerated search | permissive-code | Current releases are MIT licensed; record release and binary source. |
| HMMER / pyhmmer | Profile-HMM search | permissive-code | Required for domain/family searches and GECCO-style feature lanes. |
| LAST / LASTZ | Pairwise genome/protein alignments | restricted-or-review | Useful in synteny workflows and older MCscan recipes; resolve package licenses. |
| minimap2 | Long-read/genome/protein-adjacent anchoring | permissive-code | Useful for coordinate anchors and assembly comparisons. |
| Foldseek | Protein-structure similarity search | permissive-code | Optional for enzyme family or fold-neighborhood evidence. |
| seqkit | FASTA/FASTQ table utilities | permissive-code | Good for reproducible counts, filtering, and checksums. |
| sourmash / Mash | Sketching and contamination/context checks | permissive-code | Optional for accession sanity checks and public dataset triage. |

## Homology, Domains, Enzymes, And Pathway Annotation

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| InterProScan | Protein family/domain annotation | open-data-with-terms/restricted-or-review | Powerful but heavy; run remotely/local container and record member DB versions/tool licenses. |
| Pfam via InterPro | Protein families/domains | open-data-with-terms | Pfam is integrated under InterPro; record release. |
| NCBI CDD / RPS-BLAST | Conserved domains | open-data-with-terms | Use CDD as cross-check; verify bulk use/redistribution terms. |
| eggNOG-mapper | Orthology/function annotation | copyleft-code | Record eggNOG DB version and citation; run externally. |
| OrthoDB / BUSCO lineages | Orthology and lineage completeness references | open-data-with-terms | Useful for ortholog context and QC. |
| KofamScan / KOfamKOALA | KO/HMM pathway annotation | academic-free-or-web/open-data-with-terms | Check KEGG-related licensing before redistribution/commercial use. |
| KEGG | KO/pathway context | restricted-or-review | Useful, but licensing is often the compliance bottleneck. Avoid redistributing KEGG-derived tables unless terms allow. |
| UniProt / UniRef / Swiss-Prot | Protein references | open-data-with-terms | Preserve release and attribution; do not relicense bundled bulk data as MIT. |
| UniProt ID mapping | Cross-reference normalization | open-data-with-terms | Use as `remote_api`; respect rate limits and record mapping date. |
| Mercator4 / MapMan4 | Plant pathway binning | academic-free-or-web | Useful plant-aware annotation/binning lane; record server/tool terms and release. |
| Blast2GO / OmicsBox | GO and functional annotation | restricted-or-review | Useful in labs that already license it; do not assume availability. |
| GOATOOLS / topGO / clusterProfiler | GO enrichment and summaries | restricted-or-review | Use for derived summaries; preserve ontology release and package licenses. |
| PlantTFDB / PlantRegMap | Plant transcription-factor context | open-data-with-terms | Useful regulator candidates; check database/API terms. |
| iTAK | Plant TF/protein kinase identification | restricted-or-review | Useful local/container regulator annotation after license review. |
| CYPminer / CYP clans | Cytochrome P450 annotation | restricted-or-review | Useful family-specific CYP triage; does not prove product chemistry. |
| dbCAN / CAZy annotations | Carbohydrate-active enzymes | restricted-or-review | Useful for glycosyltransferase and polysaccharide-related clusters; CAZy redistribution is restricted. |
| Rhea / MetaNetX | Reaction cross-references | open-data-with-terms | Good for reaction normalization in dossiers. |
| HIT-EC | Enzyme EC/function prediction | permissive-code | MIT; use as function-vote evidence, not proof of chemistry. |
| EnzPlacer | Novel-enzyme EC1-3 prediction | copyleft-code | GPL-3.0; run externally/containerized and do not vendor code. |
| EnzyMM | 3D catalytic-site motif evidence | permissive-code | MIT; use as catalytic-site evidence only. |

## Expression, Differential Expression, And Coexpression

Expression evidence should be tied back to sample metadata, tissue, treatment,
developmental stage, and accession provenance. Coexpression is hypothesis
support, not proof of physical clustering or biosynthesis.

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| STAR | Spliced RNA-seq aligner | copyleft-code | High-performance reference RNA-seq lane; run externally. |
| HISAT2 | Spliced RNA-seq aligner | permissive-code | Good lightweight alternative for reference-guided expression. |
| Salmon | Transcript quantification | copyleft-code | Fast quantification; record transcriptome build and decoy strategy. |
| kallisto | Transcript quantification | permissive-code | Useful fast alternative; record index build and transcript source. |
| RSEM | Expression estimation | copyleft-code | Useful when paired with STAR/Bowtie; run externally. |
| featureCounts / subread | Gene-level counting | copyleft-code | Common for DESeq2/edgeR workflows. |
| tximport / tximeta | Transcript-to-gene summarization/provenance | permissive-code/Bioconductor terms | Good for reproducible transcriptome provenance. |
| DESeq2 | Differential expression | copyleft-code | Standard differential expression evidence; record design formula. |
| edgeR / limma-voom | Differential expression | copyleft-code | Strong alternatives for count/rate models. |
| WGCNA | Coexpression modules | copyleft-code | First-class expression evidence for multi-sample campaigns; run externally. |
| CoExpPhylo | Cross-species coexpression plus orthology/phylogeny | copyleft-code | GPL-3.0; coexpression hypotheses only and useful only with adequate sample breadth. |
| BioNERO | Coexpression/network analysis | copyleft-code | Useful R/Bioconductor coexpression lane; run externally. |
| multiWGCNA | Multi-condition coexpression | restricted-or-review | Useful for tissue/treatment comparisons after license review. |
| ATTED-II | Plant coexpression resource | open-data-with-terms | Hosted/bulk terms must be recorded; useful as public reference evidence. |
| CoNekT | Comparative plant coexpression | open-data-with-terms | Useful reference pattern/resource; record terms. |
| Camoco | Coanalysis molecular components | restricted-or-review | Useful gene-expression/genotype integration when applicable after license review. |
| STRING / Cytoscape resources | Interaction/network context | restricted-or-review | Use for context only; commercial and redistribution terms can be restrictive. |

## Orthology, Synteny, And Comparative Genomics

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| OrthoFinder 3 | Orthogroups, gene trees, and scalable core-assign comparative genomics | copyleft-code | GPLv3; strong default orthology layer but invoke externally. |
| PGAP2 | Pan-genome analysis pipeline | restricted-or-review | Useful for bacterial/fungal comparator sets and side campaigns; not a plant default. |
| SonicParanoid / Proteinortho / Broccoli | Orthology alternatives | restricted-or-review | Useful for benchmarking sensitive families or large species sets; resolve package licenses. |
| MCScanX | Synteny/collinearity | permissive-code | Classic synteny lane; current maintained fork reports BSD-2-Clause. |
| JCVI MCscan | Python synteny workflow and plots | permissive-code | Good modern plotting/workflow support; JBrowse 2 can consume `.anchors` in recent workflows. |
| GENESPACE | Plant comparative genomics/synteny | copyleft-code | GPL-family package; strong for plant pangenome-style context. Pin compatible OrthoFinder versions. |
| PGDD 2.0 | Precomputed plant synteny/collinearity evidence | open-data-with-terms | External synteny support only; cite release/article and preserve query/export IDs. |
| PlantPan | Crop pangenome, synteny, pathway, and variation context | open-data-with-terms | Crop-biased coverage; preserve release and query IDs, and review commercial/bulk use. |
| SynMap / CoGe | Hosted synteny analysis | academic-free-or-web/account-or-api-terms | Use for public data or approved workspaces only; do not upload private/unpublished sequences without explicit approval. |
| SyRI | Structural rearrangement and synteny from whole-genome alignments | copyleft-code | Useful for genome-to-genome rearrangement context around BGCs. |
| minimap2 / nucmer / MUMmer4 | Whole-genome alignment anchors | restricted-or-review | Use for coordinate context; record alignment presets and package licenses. |
| D-GENIES / dotplotly | Whole-genome dotplot visualization | restricted-or-review | Good dossier visual lane; hosted use is public-inputs-only unless approved. |
| ParaAT / KaKs_Calculator / PAML | Evolutionary rate estimates | restricted-or-review | Optional for duplicated cluster evolution; license and model assumptions need review. |

## Specialized Metabolism Databases

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| PMN 17 / PlantCyc / Plant Metabolic Network | Plant pathway context | account-or-api-terms | Complete database downloads require PMN license agreement; cache outside repo, preserve notices/authors/source DB, and avoid bulk redistribution without review. |
| Plant Reactome | Plant pathway context | open-data-with-terms | Prefer data tables over bundled artwork; preserve attribution for icons/branding. |
| MetaCyc / BioCyc | Curated metabolic reactions/pathways | restricted-or-review | Powerful but license-controlled; avoid redistribution unless terms allow. |
| KEGG / KEGG Mapper | KO/pathway context | restricted-or-review | Use behind explicit review; avoid bundling KEGG-derived bulk tables. |
| MIBiG | Experimentally characterized BGC reference | open-data-with-terms | Attribution expected; use for characterized cluster comparison and evidence standards. |
| antiSMASH database | Precomputed microbial BGC context | open-data-with-terms/restricted-or-review | Useful for cross-kingdom context; check database terms before bulk reuse. |
| NPAtlas | Natural product compound/source context | open-data-with-terms | Useful compound-name and organism cross-checks; preserve citation and release. |
| COCONUT | Open natural product database | open-data-with-terms | Useful broad natural-product chemical context; preserve license and version. |
| LOTUS | Natural products occurrence database | open-data-with-terms | Useful taxon-compound occurrence evidence; preserve source and confidence. |
| KNApSAcK | Plant metabolite/species associations | open-data-with-terms/restricted-or-review | Useful plant occurrence context; check download and redistribution terms. |
| GNPS2 / GNPS / MassIVE | Public metabolomics and molecular networking | open-data-with-terms/account-or-api-terms | Useful when public MS/MS evidence exists; preserve dataset accession, workflow, and terms. Hosted uploads are public-inputs-only unless explicitly approved. |
| MEANtools | Multi-omics metabolite and pathway inference | restricted-or-review | Useful when public expression and metabolomics evidence both exist; treat predictions as route/context support, not enzyme proof. |
| BRENDA | Enzyme function and kinetic context | restricted-or-review | Powerful but license-controlled; use derived summaries only after review. |
| Rhea / ChEBI / PubChem | Reaction and compound normalization | open-data-with-terms | Good for stable identifiers; preserve release/download date and source terms. |
| RetroRules 2026 | Reaction-template evidence | open-data-with-terms | CC BY 4.0 plus upstream source terms; use as reaction-template plausibility, not enzyme proof. |
| P450Rdb | Plant cytochrome P450 reference database | open-data-with-terms | Cite source and prefer the validated mirrored copy/hash when the live host is unavailable. |

## Plant BGC Calling And Neighborhood Visualization

Plant BGC callers need genome/GFF quality, domain annotation quality, and
biological review. Treat outputs as candidate neighborhoods with confidence
levels, not final natural-product claims.

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| plantiSMASH 2.0 | Primary plant BGC caller | copyleft-code; AGPL noted by upstream | Use as external local/container dependency or webserver for public inputs only; do not vendor into MIT repo. Version 2 adds expanded plant rules, substrate prediction, TFBS/regulatory features, and a larger precomputed database. |
| plantiSMASH database | Precomputed plant candidate BGCs | open-data-with-terms/restricted-or-review | Useful as public comparison set; check database terms before bulk reuse. |
| PlantClusterFinder | Complementary plant cluster caller | restricted-or-review | Adds enzyme/reaction/proximity perspective; resolve current code/data terms. |
| PhytoClust | Complementary plant cluster caller | restricted-or-review | Uses plant-specialized-metabolism HMM families and optional coexpression; resolve current code/data terms. |
| antiSMASH 8+ | General BGC caller and comparative output format | copyleft-code; AGPL | Complementary lane, not primary plant truth; local/container preferred for non-public data. |
| GECCO | CRF-based BGC prediction | copyleft-code | GPLv3; better suited to microbial/metagenomic BGCs but useful exploratory contrast. |
| DeepBGC | Deep-learning BGC detection/classification | permissive-code | MIT; microbial/fungal-trained context, so treat plant results as exploratory only. |
| BGCFlow | Pangenome-scale BGC workflow | permissive-code; verify wrapped tools | Useful for microbial/fungal or comparator campaigns; prokaryotic focus, so do not promote as a plant default without a smoke run. |
| BiG-SCAPE 2 / BiG-SLiCE 2 | BGC similarity networks | copyleft-code | AGPL-family current code; useful for broader cluster families; run externally and record terms. |
| BGC-Prophet | Deep-learning BGC caller | restricted-or-review | Watchlist caller; evaluate against plantiSMASH/DeepBGC/antiSMASH on public fixtures before use. |
| IGUA | Gene-cluster family identification | copyleft-code | GPL-3.0; content-agnostic GCF assignment over GenBank clusters, useful after candidate cluster normalization. |
| CHAMOIS | Secondary-metabolism cluster chemical-hierarchy prediction | restricted-or-review | Candidate-class cross-check; verify license, model assets, and benchmark fit before use. |
| FunBGCeX | Fungal BGC extractor | restricted-or-review | Fungal/endophyte-specific lane; not a plant default. |
| chatBGC | Question layer over BGCFlow outputs | permissive-code; verify dependencies | Use only over sanitized public summaries or local approved outputs; never index private notes, raw logs, or unpublished data. |
| CORASON | Core-region-based cluster phylogeny | copyleft-code/restricted-or-review | Useful around homologous cluster families; verify current packaging and dependencies. |
| cblaster | Homologous gene cluster search | permissive-code | Excellent for cross-genome cluster similarity; remote NCBI mode needs email/rate-limit compliance and public-query caution. |
| clinker / clustermap.js | Gene cluster comparison visualization | permissive-code | MIT-compatible dossier visualization component. |
| clinker-py / genbank conversion utilities | Cluster visualization plumbing | restricted-or-review | Useful to normalize GFF/GenBank outputs from plantiSMASH/GECCO/custom neighborhoods. |
| Artemis / ACT / UGENE | Local genome neighborhood inspection | restricted-or-review | Optional manual review tools; do not rely on screenshots without source coordinates. |
| JBrowse 2 / Apollo-style tracks | Neighborhood browser | permissive-code/restricted-or-review | Prefer JBrowse 2 for embedded dossier track browsing; review Apollo-style server dependencies separately. |

## Protein Structure, Pockets, And Docking

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| Boltz-2 | Biomolecular complex and affinity prediction | permissive-code | MIT code/weights; run in remote containers and label affinity as triage evidence. |
| OpenFold3-preview | AF3-style biomolecular prediction | permissive-code | Apache-2.0 code path; record model/checkpoint access terms and GPU environment. |
| Protenix-v2 | AF3-class structure prediction candidate | permissive-code | Apache-2.0; currently parked behind CUDA extension/image stability until smoke-tested. |
| P2Rank / fpocket | Pocket detection | permissive-code | Emit `binding_pockets.tsv`; pocket calls need state/oligomer and downstream validation. |
| GNINA | Docking and CNN pose scoring | copyleft-code | Treat OpenBabel/GPL path as copyleft; run externally and do not vendor. |
| PoseBusters | Docked-pose plausibility checks | permissive-code | Geometry/plausibility evidence only; not binding validation. |

## Visualization, Dossier, And Evidence Tools

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| Quarto | Static reports/dashboards | copyleft-code | Good for reproducible dossier generation; run as external tool. |
| Observable Framework | Static interactive web dossier | permissive-code | Strong for rich interactive reports. |
| Evidence.dev | SQL-backed data app/report | permissive-code | Useful if SQL-first dossier is preferred. |
| DuckDB / DuckDB-Wasm | Local analytic database/browser queries | permissive-code | Good for agent-queryable dossier data. |
| SQLite / Datasette | Evidence browser | permissive-code | Fast path for searchable evidence ledgers. |
| Parquet / Arrow | Columnar result storage | open standards; implementations vary | Good for large tables and browser-side analytics. |
| JBrowse 2 | Genome/neighborhood browser | permissive-code | Strong embedded genome browser for GFF, BAM/CRAM, BigWig, VCF, BED, and synteny anchors. |
| igv.js | Embedded genome viewer | permissive-code | Good lightweight track viewer. |
| clinker / clustermap.js | Gene neighborhood comparison UI | permissive-code | Default microsynteny/BGC-neighborhood figure component. |
| pyGenomeViz | Genome feature and synteny plots | permissive-code | Good static SVG/PNG/HTML neighborhood panels; emit `cluster-neighborhood.svg/html`. |
| Circos / pyCirclize | Whole-genome circular summaries | restricted-or-review | Use sparingly for overview figures; resolve package licenses and keep detailed tracks elsewhere. |
| Nightingale | Protein feature/domain viewer | permissive-code | Good for InterPro/UniProt-style protein feature drilldown. |
| MSAViewer / Jalview exports | Alignment views | restricted-or-review | Use for curated alignments and query-hit comparisons; verify current licenses. |
| Mol* | Structure viewer | permissive-code | Optional for protein structure evidence. |
| Cytoscape.js | Evidence/network graph | permissive-code | Useful for gene-domain-cluster-pathway graphs. |
| Vega-Lite / Observable Plot / Plotly.js | Interactive plots | permissive-code | Use for heatmaps, ranking plots, expression plots, and evidence matrices. |
| Mermaid / Excalidraw exports | Workflow and claim diagrams | restricted-or-review | Useful for human-readable campaign summaries; preserve source files and verify export terms. |
| Workflow Run RO-Crate / Process Run Crate | Machine-readable run provenance | permissive-code/open standard | Good for portability and provenance; keep `figure_manifest.json` as local contract. |
| Data Package v2 / check-jsonschema | Machine-readable table schemas | permissive-code | Good for compact dossier table validation; not a provenance substitute. |

## Runtime And Artifact Movement

| Resource | Role | License class | Notes |
| --- | --- | --- | --- |
| RunPod S3-compatible API | Network-volume artifact access | account-or-api-terms | Datacenter-limited; secrets never enter repo; do not sync raw FASTQ/BAM into local summaries. |
| rclone / s5cmd | Cross-provider artifact movement | permissive-code | Enforce include/exclude globs, max-byte policies, and checksums. |
| dstack | Multi-provider job launcher | permissive-code/account-or-api-terms | Optional overflow launcher; credentials stay in local secret stores. |
| SkyPilot | Multi-cloud AI/batch launcher | permissive-code/account-or-api-terms | Optional smoke/overflow launcher, not a provenance layer. |

## Recommended Default Stack

For personal or academic public-data GeneCluster campaigns, start with:

- public NCBI/ENA/DDBJ/GEO/ArrayExpress accessions and local/controlled
 downloads
- NCBI Datasets, Ensembl Plants/Gramene, Phytozome/JGI when terms permit, and
 accession-stable reference genomes
- nf-core/fetchngs and nf-core/rnaseq when reference inputs exist
- BRAKER3/GALBA/Tiberius/MAKER-style annotation only when genome quality and
 evidence justify it, with all dependency licenses recorded
- Liftoff/miniprot/AGAT/gffread for anchoring, annotation normalization, and
 coordinate hygiene
- rnaSPAdes, TransPi, RNA-Bloom2, or Trinity only as benchmarked assembly lanes
- IsoQuant, FLAIR2, StringTie2, bambu, SQANTI3, and transcript deduplication
 lanes for long-read or transcriptome-only evidence
- local BLAST+, DIAMOND, MMseqs2, HMMER, InterPro/Pfam, CDD, eggNOG-mapper, and
 plant-aware pathway annotation
- PlantCyc/PMN, Plant Reactome, Mercator4/MapMan4, UniProt, MIBiG, NPAtlas,
 COCONUT, LOTUS, and public metabolomics resources with attribution/terms
 recorded
- plantiSMASH 2.0 plus PlantClusterFinder/PhytoClust and non-plant callers only
 when genome/GFF evidence exists and outputs are labeled as candidate evidence
- OrthoFinder, MCScanX/JCVI, GENESPACE, WGCNA/BioNERO/ATTED-II/CoNekT for
 orthology, synteny, expression, and coexpression context
- DuckDB/Parquet/SQLite plus Quarto/Observable/JBrowse/clinker for dossiers

Put KEGG, BioCyc/MetaCyc, BRENDA, public webserver uploads,
AGPL-as-a-service exposure, unreviewed PlantBGC-like tools, and bulk database
redistribution behind explicit review.

## Repositories And Indices To Monitor

The skill should maintain a small monitoring list rather than pretending a
static list stays current:

- nf-core pipeline registry and module updates
- Bioconda recipes and package metadata
- conda-forge package metadata
- GitHub releases for GeneCluster-pinned tools
- NCBI SRA, Assembly, WGS, Taxonomy, CDD, BLAST, and Datasets resources
- ENA, GEO, ArrayExpress, Ensembl Plants, Gramene, Phytozome/JGI, and CoGe
- EMBL-EBI InterPro/Pfam
- UniProt release notes
- Plant Metabolic Network / PlantCyc and Plant Reactome
- KEGG, BioCyc/MetaCyc, Rhea, ChEBI, PubChem, and BRENDA terms
- MIBiG, antiSMASH database, NPAtlas, COCONUT, LOTUS, KNApSAcK, GNPS, and
 MassIVE releases/terms
- plantiSMASH releases, documentation, Docker images, and precomputed database
- antiSMASH, GECCO, DeepBGC, BiG-SCAPE/BiG-SLiCE, cblaster, clinker, and
 clustermap.js releases
- JBrowse, igv.js, pyGenomeViz, MultiQC, Quarto, Observable, DuckDB, Datasette,
 Cytoscape.js, and Vega-Lite releases

## Readiness Checks For A Campaign

Before dispatching a GeneCluster run:

1. Generate `resource-ledger.tsv` from the campaign manifest.
2. Mark each resource with license class, version, URL, citation, use mode, and
 redistribution policy.
3. Fail preflight if any resource is `restricted-or-review` without explicit
 operator approval.
4. Fail preflight if any public webserver would receive private, unpublished,
 proprietary, or collaborator-restricted sequences.
5. Fail preflight if a GPL/AGPL/copyleft dependency is copied into the MIT skill
 repo instead of installed externally.
6. Warn if a database permits use but not redistribution of derived/bulk tables.
7. Warn if a BGC call lacks genome/GFF quality evidence, domain evidence, and at
 least one orthology/synteny/expression/context cross-check.
8. Write `licenses.tsv`, `citations.bib`, `versions.json`,
 `resource-ledger.tsv`, `data-ledger.tsv`, and `figure_manifest.json` into the
 dossier.

## Practical Default

For personal or academic public-data campaigns, prefer:

- local MIT wrappers and validators
- local or RunPod-hosted containers with external third-party tools
- public accession downloads on local/controlled compute only
- small local summaries and web dossiers
- explicit citations, licenses, versions, checksums, and input-accession
 provenance
- "candidate neighborhood" language until biological evidence supports a
 stronger claim

For corporate, publication, or private-data campaigns, require stricter
compliance review before use of public webservers, KEGG/BioCyc/BRENDA-derived
data, AGPL network exposure, account-gated databases, cloud uploads, or database
redistribution.
