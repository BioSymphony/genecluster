# GeneCluster Provider-Neutral Execution Contract

Status: run-ready contract v1
Last reviewed: 2026-04-30

This note defines the provider-neutral execution contract for BioSymphony GeneCluster. RunPod is the best-supported heavy backend in this repo today, but the skill must also plan and validate local-lite, explicit local-full, SSH/HPC, generic cloud VM, and future managed workflow lanes.

## Local Controller Policy

The local BioSymphony repo is the control plane only. It may contain:

- campaign manifests
- small ledgers
- query seed references
- validation summaries
- small dossiers and spreadsheet exports
- remote artifact pointers

It must not contain raw SRA/FASTQ files, BAM/CRAM/SAM files, large genome assemblies, BLAST databases, InterProScan databases, or workflow work directories.

## Provider Classes

- `local_lite`: safe public-skill default for metadata, ledgers, validation, and dossier rendering. No raw data downloads.
- `local_full`: explicit opt-in heavy local execution. Requires a configured workdir outside the repo.
- `runpod_pod`: supported heavy backend. Uses `/workspace/genecluster/runs/<run_id>` by convention.
- `ssh_hpc`: remote shell/HPC execution with a configured remote workdir.
- `cloud_vm`: generic VM execution with a configured attached-volume workdir.
- `managed_workflow`: deferred Nextflow/Seqera-style backend.

## RunPod v0 Defaults

- Use a RunPod Pod, not Serverless, for the candidate-search workflow.
- Mount a RunPod Network Volume at `/workspace`.
- Use `/workspace/genecluster/runs/<run_id>` as the remote work directory.
- Use `/workspace/genecluster/db-cache`, `/workspace/genecluster/nextflow-cache`, `/workspace/genecluster/sra-cache`, and `/workspace/genecluster/scratch` for persistent provider-side caches.
- Treat object-store URIs as backup/archive targets only in v1. Executable
  heavy workdirs, DB paths, and cache paths must be mounted filesystem paths.
- Keep all large inputs and intermediate artifacts on the remote volume.
- Pull back only small summaries and manifests.
- Use provider-local BLAST/DIAMOND/MMseqs/HMMER only. NCBI remote BLAST batch execution is not part of the approved search policy.

## Local Full Defaults

- Requires an explicit heavy workdir outside the repo.
- Must still block raw sequence data under the repo root.
- Uses the same runner contract and artifact policy as remote providers.

## Run Scopes

- `smoke`: metadata/query resolution and validation only.
- `candidate_search`: candidate search and small dossier.
- `full_public_mining`: candidate search plus genome context, optional coexpression/synteny, dossier, and claim audit where supported by inputs.
- `next_experiment_design`: convert reviewed evidence gaps into sequencing, annotation, metabolomics, or biochemical-validation options.

For first execution, use `smoke` or `candidate_search`. Treat open-ended
full public mining as an escalation path after candidate evidence identifies a
specific evidence gap worth a longer run. Private/example campaigns may define
their own aliases, but public skill instructions should not depend on them.

## Execution Maturity Gates

RunPod is the most complete heavy path today, but the same gates apply to
`local_full`, `ssh_hpc`, and `cloud_vm` when the user supplies adequate storage
and tools.

- `L0_control_plane_ready`: launch bundle, ledgers, plans, and issue contracts
  exist; no biological execution is implied.
- `L1_provider_tool_ready`: provider image/toolcheck, lifecycle, and summary
  transport pass.
- `L2_provider_db_ready`: required reference/domain databases are present or
  explicitly built on provider storage.
- `L3_target_materialized_ready`: target organism FASTA/protein/transcript/genome
  inputs are present and target search indexes are built.
- `L4_raw_sra_pipeline_ready`: SRA reads were fetched/converted and turned into
  searchable target sequences or an explicit assembly/import output.
- `L5_claim_audited_dossier_ready`: target candidates, provenance, versions,
  claim audit, and deferred-lane caveats validate.

Agents must not treat runner flags as proof of a maturity level. A full run is
not successful if `candidate_hits.tsv` came from SwissProt/Pfam/reference
databases while target DB materialization failed.

For target-organism discovery, the minimum success proof is joined and
non-mock: `data-materialization-summary.json`, `target-db-indexes.tsv`,
`candidate-search-summary.json`, `candidate_hits.tsv`, and `run_summary.json`
must agree that at least one built/present `target_*` index was searched and
produced target candidate rows. The required final gate is
`genecluster_contract_self_check.py --require-real-target-search`.

## Biological Route Gate

Execution readiness and scientific route readiness are separate. A bundle can
be technically launchable on RunPod for a provider-side target nucleotide
`tblastn` search while still not being ready for a transcript-first full
discovery claim.

When transcriptome evidence exists, the preferred scientific route is:

1. Resolve metadata and classify transcript/genome/annotation resources.
2. Import, curate, or assemble target transcripts.
3. Call ORFs and build a target proteome.
4. Search canonical/source proteins against the target proteome.
5. Review isoforms, partials, reciprocal support, domains, and paralogs.
6. Map transcript-supported candidates to the genome with splice-aware methods.
7. Extract neighborhoods only after coordinate confidence is recorded.

Direct genome `tblastn`/protein-to-genome search is rescue or coordinate-support
evidence when transcript data exists. Treat it as a fallback, with transcript-based
candidate discovery taking precedence for multi-exon candidates.

Run this before choosing or claiming the route:

```bash
python3 skills/biosymphony/scripts/genecluster_route_audit.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json
```

Run this before claiming transcript-first full scientific readiness:

```bash
python3 skills/biosymphony/scripts/genecluster_route_audit.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --require-transcript-first
```

If the strict route audit fails, either downgrade the run language to
candidate-smoke/rescue or implement the missing transcriptome/ORF/proteome and
transcript-to-genome stages before launch.

## Credential Policy

Do not store tokens in repo files, `.env`, `env.sh`, ledgers, or Linear issue bodies.

Expected RunPod operator setup:

```bash
Load `RUNPOD_API_KEY` from the operator's secure local secret store before launch.
export GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID=<volume id>
export GENECLUSTER_RUNPOD_DATACENTER=<datacenter id>
```

If object storage is added later, use the provider's normal environment variables or short-lived credentials from a secure store. Do not commit credentials.

## Remote Image Requirements

The remote image or setup script for heavy providers should include:

- workflow runner: Nextflow preferred, Snakemake acceptable
- SRA/ENA retrieval tooling
- `fastp`, FastQC, MultiQC
- DIAMOND and/or MMseqs2
- BLAST+ for compatibility checks
- HMMER
- miniprot for spliced protein-to-genome anchoring when protein/GFF IDs fail
- InterProScan/Pfam or a documented deferred domain-scan lane
- Python 3 with the standard scientific TSV/JSON stack
- optional later lanes: plantiSMASH, cblaster, clinker, OrthoFinder, MCScan/GENESPACE

Pin image digest, workflow revision, and tool versions in `versions.json`.

For live RunPod execution, prefer a private, digest-pinned image over a
first-boot `mamba install`. First-boot installs are acceptable only as emergency
or development fallback because they make failures harder to distinguish from
real biological pipeline failures. The image must include OpenJDK 17+ for
Nextflow; a Conda/Mambaforge base image alone is not enough. The launch payload
and `tool-requirements.json` require BLAST+, `update_blastdb.pl`, DIAMOND,
MMseqs2, HMMER, miniprot, SRA Toolkit, NCBI Datasets, minimap2, Nextflow,
Python, and SQLite.

Standard GeneCluster launch preflights reject package installs inside
`dockerStartCmd` (`mamba install`, `conda install`, `apt-get install`, `pip
install`). Those installs can fail mid-boot, trigger RunPod restarts, and look
like a biological pipeline failure. Use `--allow-first-boot-install` only for a
deliberate degraded smoke/debug run with persistent boot logs and a watcher.
The REST launcher also defaults to an 80 GB container disk safety floor; smaller
disks require `--allow-small-container-disk`.

Digest pinning does not prove that RunPod can pull the image. For GHCR,
GitLab registry, ECR/GAR/ACR, Quay, or other auth-sensitive registries, configure
a RunPod container registry auth record and expose only its id through
`GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID` or
`RUNPOD_CONTAINER_REGISTRY_AUTH_ID`. The REST launcher passes that value as
`containerRegistryAuthId` at pod creation. If the exact digest-pinned image is
public-pullable, the operator may set `GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL=1`;
that assertion should be used only after an independent pull test or a known
public registry policy. A pod with `desiredStatus: RUNNING` but no runtime is not
evidence that a private image pulled successfully.

## RunPod Lifecycle Guardrails

RunPod Pod status needs a stronger check than `desiredStatus: RUNNING`.
Treat a pod as truly started only after `runtime` is non-null and
`runtime.uptimeInSeconds` is advancing. If `runtime` remains null past the
launch payload's timeout, assume capacity/provisioning failure and stop the run
before burning orchestration time.

When using `dockerStartCmd` for a finite GeneCluster run, keep long-lived
provider API keys operator-side. Otherwise a clean command exit can be
interpreted as "desired RUNNING pod should start again", causing a restart loop.
Generated bundles include `provider/runpod-docker-start.sh`, which writes a
small status file under the run workdir and idles briefly after completion so
the operator-side monitor can pull summaries and stop the pod.

Workload completion and lifecycle cleanup are separate facts. A pod can write
`pipeline_exit=0` and all expected summary artifacts, then still need
operator-side cleanup. In that case, stop the pod after pulling and validating
the artifacts, and report any missed cleanup window as successful workload with
degraded lifecycle cleanup. Do not keep waiting only because
`desiredStatus=RUNNING`, and do not call the scientific run failed until the
durable status/artifact files say the workload failed.

Stop pods before deleting them. Stop preserves the chance to inspect container
state while summary retrieval and validation finish; delete only after summary
artifacts, remote artifact boundaries, and cleanup decisions have been reviewed.

RunPod MCP wrappers can lag the REST API. If an MCP `create-pod` schema does not
expose `computeType`, `networkVolumeId`, or `dockerStartCmd`, use a RunPod
template or the REST API fallback recorded in `provider/runpod-pod.json`.

Before every REST launch, the launcher checks serialized payload size and
`dockerStartCmd` size. Payloads near 50 KB warn; payloads above 60 KB fail by
default because provider-side limits can appear as misleading capacity errors.
Keep REST payloads thin: clone or mount a durable bundle, then run
`provider/runpod-docker-start.sh`; do not embed large scripts, FASTA, or
workflow state directly in the API request.

For independent checks:

```bash
python3 skills/biosymphony/scripts/symphony_orchestration_preflight.py \
  --provider-payload path/to/runpod-rest-payload.json
```

## Summary Retrieval

Preferred summary retrieval for serious runs is RunPod S3 / network-volume
object access or another configured summary endpoint. The endpoint shape is
`https://s3api-{datacenter}.runpod.io`; access keys are operator secrets and
must not be written into the repo, launch bundle, or Linear issue body.

A short-lived HTTP pull pod remains a fallback for small demos: mount the same
network volume, serve the run summary directory briefly, fetch only files listed
in `summary_sync_policy.include`, then stop/delete the pull pod. Do not rely on
this fallback when provider capacity is tight; if no second pod can be
provisioned, summary fetch stalls even if the main run finished correctly.

## Run-Ready Bundle Contents

`genecluster_launch_bundle.py` now emits a portable launch bundle containing:

- `launch-manifest.json`
- copied campaign contracts under `ledgers/`
- `db-bootstrap-plan.json`
- `target-db-plan.json`
- `candidate-route-plan.json`
- `reference-import-plan.json`
- `anchor-map-plan.json`
- `neighborhood-extract-plan.json`
- `orthology-anchor-plan.json`
- `reciprocal-search-plan.json`
- `pathway-completeness-plan.json`
- `query-resolution-plan.json`
- `decoy-plan.json`
- `run-economics.json`
- `search-plan.json`
- `tool-requirements.json`
- `campaign-prompt.md`
- provider payloads under `provider/`
- `remote/genecluster_remote_runner.py`
- `run-later.sh`

For execution readiness, validate with:

```bash
python3 skills/biosymphony/scripts/genecluster_preflight.py \
  --launch-manifest .runtime/<bundle>/launch-manifest.json \
  --execution-ready
```

Execution-ready validation intentionally fails if the image is still a placeholder, RunPod volume metadata is unresolved, required credentials are only named but not present, or DB/cache/search contracts are missing.

## Maximum Database Tier

The maximum tier is described by `database-ledger.tsv` and `cache-ledger.tsv`, not by local downloads. Provider caches may include:

- BLAST+: `nr`, `nt` where feasible, `swissprot`, `refseq_protein`, and `taxdb`
- DIAMOND: SwissProt, plant TrEMBL, plant RefSeq, NR or plant NR where storage allows
- MMseqs2: UniProtKB, UniRef, NR, Pfam, CDD, eggNOG, custom campaign DBs
- Domain/pathway: Pfam/HMMER, CDD/RPS-BLAST, InterProScan, KOfam, MIBiG 4.0, plantiSMASH 2.0 resources
- Custom public pathway DBs built only inside the provider cache

Network volumes are persistent execution storage, not archival storage. Cache ledgers therefore require backup policy fields.

## Artifact Sync Policy

Remote-only:

- raw reads
- converted FASTQ
- genome assemblies
- BAM/CRAM/SAM
- BLAST/MMseqs/DIAMOND databases
- InterProScan databases
- workflow work directories

Local allowed:

- `run_summary.json`
- `candidate_hits.tsv`
- `evidence.jsonl`
- `evidence.sqlite`
- `db-bootstrap-summary.json`
- `target-db-build-summary.json`
- `target-db-ledger.resolved.tsv`
- `target-db-indexes.tsv`
- `reference-import-summary.json`
- `resolved-references.tsv`
- `candidate_anchors.tsv`
- `orthology_links.tsv`
- `anchor_ladder.tsv`
- `reciprocal_hits.tsv`
- `cluster_neighborhoods.tsv`
- `neighbor_annotations.tsv`
- `domain_labels.tsv`
- `neighborhood_hypotheses.tsv`
- `pathway_completeness.tsv`
- `neighborhood-visualization.html`
- `claim-audit.jsonl`
- `decoy-preflight.json`
- `search-cache-manifest.json`
- `deferred-lanes.json` for 24-hour complete runs
- `provenance.jsonl`
- `versions.json`
- `licenses.tsv`
- `export.xlsx`
- compact HTML dossier pages

## Failure Recovery

Every remote run should record:

- `run_id`
- image digest
- workflow git SHA or package version
- input manifest hash
- remote workdir
- RunPod volume identifier
- tools run
- warnings and incomplete steps

Resumable engines should keep their cache/work directories under the same remote workdir. Local retry should never require downloading large remote artifacts.

Candidate search is fail-closed on required enabled databases: a partial hit set
does not make the lane successful when a required scope-gated database is
missing or failed. Optional maximum-tier databases remain deferred unless the
operator explicitly escalates.

## Provider-Side Query And Cache Prep

Heavy launch bundles include DB bootstrap, data materialization, reference
import, query resolution, target dataset DB/index planning, candidate search,
reciprocal/orthology summaries, anchor mapping, neighborhood extraction/scoring,
and pathway completeness stages. The
provider runner resolves public protein accessions from
`query-resolution-plan.json` into
`/workspace/genecluster/runs/<run_id>/inputs/queries/protein_queries.faa`. It
does not use NCBI remote BLAST; it only fetches small public seed FASTA records
needed to run provider-local BLAST/DIAMOND/MMseqs/HMMER.

For transcript-like SRA rows, the blessed RunPod path can materialize target
nucleotide FASTA under
`/workspace/genecluster/runs/<run_id>/inputs/target-sequences/<dataset>/` with
SRA Toolkit and then build a BLAST nucleotide DB. Candidate search uses
`tblastn` for canonical protein queries against these materialized target
databases. This is a real target-organism candidate search, but it is not a
de novo transcriptome assembly and it does not support physical cluster claims
without genome coordinates.

SRA materialization must distinguish the ledger accession from the conversion
input. A ledger may contain an experiment accession such as `SRX...`, but
`prefetch` writes concrete run artifacts such as `SRR.../*.sra`.
Provider-side runners should discover the downloaded `.sra` file or resolved
run directory before calling `fasterq-dump`; passing a guessed
`/.../SRX...` path to `fasterq-dump` is a known crash-loop cause and should fail
preflight or the first SRA smoke stage.

Provider-side runners must also resolve layout before alignment or assembly.
`LibraryLayout=SINGLE` means downstream stages must accept one FASTQ and use
single-read flags, for example HISAT2 `-U`. `LibraryLayout=PAIRED` means both
mates must exist and paired flags such as `-1/-2` are required. Mixed or
incomplete layout evidence should be recorded as a degraded branch, not silently
forced through paired-end assumptions.

`--allow-large-downloads` permits provider-side large DB/reference/SRA downloads
where a lane is implemented. The flag does not itself imply assembly, ORF calling,
genome annotation, or cluster evidence; downstream stages must declare those separately.

The runner writes:

- `db-bootstrap-summary.json` and `db-bootstrap-plan.tsv` for provider cache and
  safe local DB-build status
- `data-materialization-summary.json` and `materialized-targets.tsv` for
  provider-side target sequence materialization
- `target-db-build-summary.json`, `target-db-ledger.resolved.tsv`, and
  `target-db-indexes.tsv` for source/target resource discovery and provider-only
  BLAST/DIAMOND/MMseqs/miniprot index status
- `reference-import-summary.json` and `resolved-references.tsv` for public
  reference/genome/protein/GFF import planning
- `query-preflight.json` for seed FASTA and unresolved-seed status
- `decoy-preflight.json` for broad-family false-positive controls
- `search-cache-manifest.json` for provider-side search cache hits/writes
- `orthology_links.tsv`, `reciprocal_hits.tsv`, and `anchor_ladder.tsv` for the
  A-to-B ladder from canonical source proteins to target-species candidates and
  coordinate confidence classes
- `candidate_anchors.tsv` and `anchor-map-summary.json` when genome/GFF
  coordinates are available
- `cluster_neighborhoods.tsv`, `neighbor_annotations.tsv`,
  `domain_labels.tsv`, `neighborhood_hypotheses.tsv`, and
  `neighborhood-visualization.html` for
  summary-only anchor-centered context
- `pathway_completeness.tsv` for per-step supported/partial/missing/ambiguous/
  context-only/deferred-by-budget status
- `evidence.sqlite` for agent-queryable candidate/evidence/audit summaries

Raw search outputs and cache entries remain under `/workspace/genecluster`.
Neighborhood outputs are evidence summaries only; product chemistry and physical
cluster claims remain claim-audited and require coordinate/neighborhood support.

`genecluster_db_bootstrap.py` can run provider-side preformatted BLAST database
downloads for curated, non-huge resources such as SwissProt when
`update_blastdb.pl` is present in the image. Large required DB downloads/builds
are gated behind `--allow-large-downloads`; optional maximum-tier resources stay
deferred until the operator explicitly changes scope or ledgers.

Reference import is also gated: genome/protein/GFF downloads through NCBI
Datasets require `--allow-reference-downloads` directly, or
`--allow-large-downloads` through the umbrella remote runner. Without that flag,
the helper writes a plan and blocker instead of downloading heavy references.
