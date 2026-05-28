#!/usr/bin/env python3
"""Create provider-neutral GeneCluster launch bundles.

This script does not launch RunPods, open SSH sessions, fetch SRA data, or run
heavy bioinformatics tools. It writes a small, validated control-plane bundle
that another operator or Symphony/Linear issue can use to run the selected
scope later.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from genecluster_preflight import is_object_store_uri, normalize_provider, path_is_under, validate_campaign_manifest  # noqa: E402


HEAVY_RUN_SCOPES = {
    "candidate_search",
    "genome_context",
    "coexpression",
    "synteny",
    "full_public_mining",
    "full_campaign",
    "full_campaign_24h",
}

RUN_SCOPE_ALIASES = {
    "full-campaign": "full_campaign",
    "full-campaign-24h": "full_campaign_24h",
    "campaign-one-day": "full_campaign_24h",
    "one-day-campaign": "full_campaign_24h",
    "full-public-mining": "full_public_mining",
    "candidate-search": "candidate_search",
    "genome-context": "genome_context",
    "next-experiment-design": "next_experiment_design",
}

ALL_REMOTE_SCOPES = [
    "smoke",
    "candidate_search",
    "genome_context",
    "coexpression",
    "synteny",
    "full_public_mining",
    "next_experiment_design",
    "full_campaign",
    "full_campaign_24h",
]

PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "local_lite": {
        "display_name": "Local lite",
        "supported_scopes": ["smoke", "next_experiment_design"],
        "requires_heavy_workdir": False,
        "requires_explicit_opt_in": False,
        "required_env": [],
        "default_heavy_workdir": "",
        "artifact_sync": "local summaries only",
        "notes": [
            "No raw data downloads are allowed.",
            "Use for metadata, ledgers, validation, and dossier rendering.",
        ],
    },
    "local_full": {
        "display_name": "Local full",
        "supported_scopes": ALL_REMOTE_SCOPES,
        "requires_heavy_workdir": True,
        "requires_explicit_opt_in": True,
        "required_env": [],
        "default_heavy_workdir": "",
        "artifact_sync": "write heavy files only to explicit workdir outside repo",
        "notes": [
            "Requires --allow-local-full and --heavy-workdir.",
            "The heavy workdir must be absolute and outside the repo root.",
        ],
    },
    "runpod_pod": {
        "display_name": "RunPod Pod",
        "supported_scopes": ALL_REMOTE_SCOPES,
        "requires_heavy_workdir": True,
        "requires_explicit_opt_in": False,
        "required_env": ["RUNPOD_API_KEY", "GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID", "GENECLUSTER_RUNPOD_DATACENTER"],
        "default_heavy_workdir": "/workspace/genecluster/runs/{run_id}",
        "artifact_sync": "pull back summaries only; keep large artifacts on RunPod volume",
        "notes": [
            "Internal default heavy backend.",
            "This bundle does not launch a pod; it emits launch payload details only.",
        ],
    },
    "ssh_hpc": {
        "display_name": "SSH/HPC",
        "supported_scopes": ALL_REMOTE_SCOPES,
        "requires_heavy_workdir": True,
        "requires_explicit_opt_in": False,
        "required_env": ["GENECLUSTER_SSH_HOST"],
        "default_heavy_workdir": "",
        "artifact_sync": "operator-provided rsync/scp summaries only",
        "notes": [
            "Requires a remote host and workdir.",
            "No private sequences should be uploaded unless operator confirms rights.",
        ],
    },
    "cloud_vm": {
        "display_name": "Cloud VM",
        "supported_scopes": ALL_REMOTE_SCOPES,
        "requires_heavy_workdir": True,
        "requires_explicit_opt_in": False,
        "required_env": ["GENECLUSTER_CLOUD_VM"],
        "default_heavy_workdir": "",
        "artifact_sync": "operator-provided attached-volume summaries only",
        "notes": [
            "Generic VM backend.",
            "Provider-specific provisioning is outside this v1 bundle.",
        ],
    },
    "managed_workflow": {
        "display_name": "Managed workflow",
        "supported_scopes": ALL_REMOTE_SCOPES,
        "requires_heavy_workdir": True,
        "requires_explicit_opt_in": False,
        "required_env": ["GENECLUSTER_MANAGED_WORKFLOW"],
        "default_heavy_workdir": "",
        "artifact_sync": "managed workflow output summaries only",
        "notes": [
            "Deferred backend for Seqera/Nextflow-style systems.",
            "Use only after a provider adapter is implemented.",
        ],
    },
}


RUNPOD_REGISTRY_AUTH_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "GENECLUSTER_CONTAINER_REGISTRY_AUTH_ID",
]

RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL",
    "GENECLUSTER_IMAGE_PUBLIC_PULL",
]

AUTH_SENSITIVE_REGISTRY_HOSTS = {
    "ghcr.io",
    "registry.gitlab.com",
    "quay.io",
}

AUTH_SENSITIVE_REGISTRY_SUFFIXES = (
    ".dkr.ecr.amazonaws.com",
    ".pkg.dev",
    ".azurecr.io",
    ".jfrog.io",
)


RUN_SCOPE_CONFIGS: dict[str, dict[str, Any]] = {
    "smoke": {
        "description": "Metadata/query resolution and validation only.",
        "heavy_compute": False,
        "lanes": [
            "campaign_preflight",
            "data_ledger_preflight",
            "query_ledger_preflight",
            "resource_ledger_preflight",
            "dossier_skeleton",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/data-ledger.tsv",
            "data/query-ledger.tsv",
            "data/resource-ledger.tsv",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
        ],
    },
    "candidate_search": {
        "description": "Candidate search and small dossier.",
        "heavy_compute": True,
        "lanes": [
            "metadata_resolution",
            "query_sequence_resolution",
            "remote_local_blast_or_diamond_search",
            "candidate_homology_search",
            "domain_annotation_light",
            "deduplication_and_isoform_review",
            "candidate_ranking",
            "dossier_generation",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate-ranking.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "data/export.xlsx",
            "dossier-manifest.json",
        ],
    },
    "genome_context": {
        "description": "Genome anchoring, neighboring-gene capture, and cluster/neighborhood review.",
        "heavy_compute": True,
        "lanes": [
            "metadata_resolution",
            "reference_resolution",
            "candidate_coordinate_mapping",
            "neighboring_gene_capture",
            "domain_and_function_labeling",
            "genome_anchoring",
            "bgc_and_neighborhood_context",
            "cluster_visualization_summaries",
            "claim_audit",
            "dossier_generation",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate_anchors.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/neighbor_annotations.tsv",
            "data/domain_labels.tsv",
            "data/annotations.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "neighborhood-visualization.html",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "claim-ledger.md",
            "dossier-manifest.json",
        ],
    },
    "coexpression": {
        "description": "Expression quantification and coexpression support for candidate prioritization.",
        "heavy_compute": True,
        "lanes": [
            "metadata_resolution",
            "sample_design_review",
            "transcriptome_reference_selection",
            "expression_quantification",
            "coexpression_module_scoring",
            "candidate_ranking_update",
            "claim_audit",
            "dossier_generation",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate-ranking.tsv",
            "data/coexpression_edges.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "claim-ledger.md",
            "dossier-manifest.json",
        ],
    },
    "synteny": {
        "description": "Orthology, paralogy, and conserved-neighborhood support for localized candidates.",
        "heavy_compute": True,
        "lanes": [
            "reference_species_selection",
            "protein_set_preparation",
            "orthology_synteny",
            "paralog_and_copy_review",
            "conserved_neighborhood_scoring",
            "claim_audit",
            "dossier_generation",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate_anchors.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/neighbor_annotations.tsv",
            "data/domain_labels.tsv",
            "data/orthogroups.tsv",
            "data/synteny_blocks.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "deferred-lanes.json",
            "neighborhood-visualization.html",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "claim-ledger.md",
            "dossier-manifest.json",
        ],
    },
    "full_public_mining": {
        "description": "Full provider-neutral GeneCluster evidence campaign over public or approved remote data.",
        "heavy_compute": True,
        "lanes": [
            "metadata_resolution",
            "public_data_fetch_remote_only",
            "reference_resolution",
            "query_sequence_resolution",
            "transcriptome_import_or_assembly",
            "long_read_curation",
            "remote_local_blast_or_diamond_search",
            "candidate_homology_search",
            "domain_and_pathway_annotation",
            "deduplication_and_isoform_review",
            "genome_anchoring",
            "neighboring_gene_capture",
            "bgc_and_neighborhood_context",
            "orthology_synteny",
            "coexpression_if_supported",
            "candidate_ranking",
            "claim_audit",
            "dossier_generation",
            "next_experiment_brief",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate-ranking.tsv",
            "data/candidate_anchors.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/neighbor_annotations.tsv",
            "data/domain_labels.tsv",
            "data/annotations.tsv",
            "data/orthogroups.tsv",
            "data/synteny_blocks.tsv",
            "data/coexpression_edges.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "neighborhood-visualization.html",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "data/citations.bib",
            "claim-ledger.md",
            "next-experiment-brief.md",
            "dossier-manifest.json",
        ],
    },
    "next_experiment_design": {
        "description": "Evidence-gap to experiment-plan conversion; no sequence downloads required.",
        "heavy_compute": False,
        "lanes": [
            "claim_ledger_review",
            "evidence_gap_table",
            "sample_design_recommendations",
            "sequencing_lane_recommendations",
            "metabolomics_and_assay_recommendations",
            "vendor_safe_summary",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "next-experiment-brief.md",
            "data/evidence-gaps.tsv",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
        ],
    },
    "full_campaign": {
        "description": "Campaign-specific alias for full_public_mining using the example ledgers.",
        "heavy_compute": True,
        "lanes": [
            "campaign_context_review",
            "metadata_resolution",
            "public_data_fetch_remote_only",
            "reference_resolution",
            "query_sequence_resolution",
            "transcriptome_import_or_assembly",
            "long_read_curation",
            "remote_local_blast_or_diamond_search",
            "candidate_homology_search",
            "domain_and_pathway_annotation",
            "deduplication_and_isoform_review",
            "genome_anchoring",
            "neighboring_gene_capture",
            "bgc_and_neighborhood_context",
            "orthology_synteny",
            "coexpression_if_supported",
            "candidate_ranking",
            "claim_audit",
            "dossier_generation",
            "next_experiment_brief",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate-ranking.tsv",
            "data/candidate_anchors.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/neighbor_annotations.tsv",
            "data/domain_labels.tsv",
            "data/annotations.tsv",
            "data/orthogroups.tsv",
            "data/synteny_blocks.tsv",
            "data/coexpression_edges.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "neighborhood-visualization.html",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "data/citations.bib",
            "claim-ledger.md",
            "next-experiment-brief.md",
            "dossier-manifest.json",
        ],
    },
    "full_campaign_24h": {
        "description": "One-day complete campaign profile: reference-first, cache-first, no de novo assembly by default, and a complete timeboxed dossier.",
        "heavy_compute": True,
        "runtime_budget_hours": 24,
        "completion_mode": "timeboxed_complete_dossier",
        "lanes": [
            "campaign_context_review",
            "runtime_budget_preflight",
            "metadata_resolution",
            "reference_first_import",
            "query_sequence_resolution",
            "provider_cache_preflight",
            "high_roi_local_blast_diamond_mmseqs_hmmer_search",
            "domain_and_pathway_annotation_light",
            "deduplication_and_isoform_review",
            "genome_anchoring_if_reference_available",
            "neighboring_gene_capture_if_anchored",
            "synteny_or_coexpression_only_if_cached_or_small",
            "candidate_ranking",
            "claim_audit",
            "dossier_generation",
            "deferred_lane_manifest",
            "next_experiment_brief",
        ],
        "expected_artifacts": [
            "run_summary.json",
            "data/db-bootstrap-summary.json",
            "data/reference-import-summary.json",
            "data/candidate_hits.tsv",
            "data/candidate-ranking.tsv",
            "data/candidate_anchors.tsv",
            "data/cluster_neighborhoods.tsv",
            "data/neighbor_annotations.tsv",
            "data/domain_labels.tsv",
            "data/annotations.tsv",
            "data/evidence.jsonl",
            "data/evidence.sqlite",
            "data/claim-audit.jsonl",
            "data/search-cache-manifest.json",
            "neighborhood-visualization.html",
            "data/provenance.jsonl",
            "data/versions.json",
            "data/licenses.tsv",
            "data/citations.bib",
            "claim-ledger.md",
            "next-experiment-brief.md",
            "dossier-manifest.json",
        ],
    },
}

WORKFLOW_CLASS_SPECS: dict[str, dict[str, Any]] = {
    "reference_first_anchor_mining": {
        "roi": "very_high",
        "description": "Reference-first candidate mining and genome anchoring before expensive de novo assembly.",
        "input_requirements": ["query_ledger", "data_ledger", "provider_local_search_databases"],
        "required_tools": ["blastp", "diamond", "mmseqs", "hmmsearch", "miniprot"],
        "expected_outputs": ["candidate_hits.tsv", "candidate_anchors.tsv", "anchor_ladder.tsv"],
        "claim_boundary": "homology and anchors support candidates; product chemistry remains unvalidated",
    },
    "long_read_isoform_curation": {
        "roi": "very_high_when_long_reads_exist",
        "description": "Long-read transcript and ORF curation for isoforms that change domain/function calls.",
        "input_requirements": ["long_read_transcriptome_or_isoseq_dataset", "candidate_hits"],
        "required_tools": ["IsoQuant", "SQANTI3", "FLAIR2", "minimap2", "gffread", "TransDecoder"],
        "expected_outputs": ["isoform-ledger.tsv", "isoform-classification.tsv", "isoform-orfs.tsv", "isoform-domain-delta.tsv", "longread-qc.json"],
        "claim_boundary": "long reads support isoforms and ORFs, not product chemistry or physical clusters",
    },
    "transcriptome_only_dossier": {
        "roi": "very_high_for_non_model_organisms",
        "description": "Candidate dossier when no reliable genome/GFF exists.",
        "input_requirements": ["transcriptome_dataset", "query_ledger"],
        "required_tools": ["TransDecoder", "MMseqs2", "BUSCO_or_compleasm", "rnaSPAdes_or_Trinity_if_needed"],
        "expected_outputs": ["transcriptome-build-ledger.tsv", "assembly-qc.tsv", "orf-ledger.tsv", "isoform-groups.tsv"],
        "claim_boundary": "transcriptome-only evidence cannot support physical cluster claims",
    },
    "paralog_homeolog_copy_review": {
        "roi": "very_high_for_broad_families",
        "description": "Copy classification for paralogs, alleles, homeologs, haplotigs, isoforms, and assembly artifacts.",
        "input_requirements": ["candidate_hits", "target_proteins_or_transcripts"],
        "required_tools": ["MMseqs2", "OrthoFinder", "MAFFT_or_FastTree_optional", "GENESPACE_optional"],
        "expected_outputs": ["orthogroup-ledger.tsv", "paralog-homeolog-ledger.tsv", "copy-classification.tsv", "gene-tree-summary.tsv"],
        "claim_boundary": "ortholog/paralog/homeolog labels require explicit evidence and uncertainty",
    },
    "expression_coexpression_support": {
        "roi": "high_when_sample_design_supports_it",
        "description": "Expression, coexpression, and tissue specificity as prioritization evidence.",
        "input_requirements": ["expression_sample_design", "shared_reference_or_transcriptome"],
        "required_tools": ["Salmon", "kallisto", "tximport", "DESeq2", "WGCNA_or_BioNERO"],
        "expected_outputs": ["expression-design.tsv", "expression-matrix-manifest.json", "tissue-specificity.tsv", "coexpression-modules.tsv"],
        "claim_boundary": "coexpression prioritizes candidates but does not prove function or clustering",
    },
    "comparative_synteny_neighborhood": {
        "roi": "high_when_coordinates_exist",
        "description": "Comparative genome context, conserved neighborhoods, and synteny around anchored candidates.",
        "input_requirements": ["genome_or_assembly", "annotation_or_anchor_ladder"],
        "required_tools": ["MCScanX", "JCVI", "GENESPACE", "cblaster", "clinker"],
        "expected_outputs": ["assembly-ledger.tsv", "annotation-ledger.tsv", "coordinate-liftover-ledger.tsv", "comparative_neighborhoods.tsv"],
        "claim_boundary": "neighborhood/synteny supports context hypotheses only",
    },
    "fragmented_genome_rescue": {
        "roi": "medium_high_for_imperfect_assemblies",
        "description": "Anchor rescue when a genome exists but annotation or contiguity is weak.",
        "input_requirements": ["fragmented_genome_or_missing_annotation", "canonical_proteins"],
        "required_tools": ["miniprot", "Liftoff", "RagTag_optional", "AGAT"],
        "expected_outputs": ["coordinate-liftover-ledger.tsv", "candidate_anchors.tsv", "anchor_ladder.tsv"],
        "claim_boundary": "rescued coordinates remain lower confidence until annotation/assembly review",
    },
    "pav_copy_number_matrix": {
        "roi": "high_for_multi_assembly_or_population_questions",
        "description": "Presence/absence and copy-number matrix for candidate genes across assemblies or accessions.",
        "input_requirements": ["two_or_more_assemblies_or_samples", "candidate_anchor_set"],
        "required_tools": ["miniprot", "Liftoff", "OrthoFinder", "SyRI_optional"],
        "expected_outputs": ["pav-copy-number.tsv", "copy-classification.tsv"],
        "claim_boundary": "PAV/copy evidence does not prove enzyme activity",
    },
    "candidate_sv_interval": {
        "roi": "medium_high_when_reads_or_assemblies_support_sv",
        "description": "Structural variation around candidate intervals when multiple assemblies or long reads exist.",
        "input_requirements": ["candidate_intervals", "long_reads_or_multiple_assemblies"],
        "required_tools": ["Sniffles2", "cuteSV", "pbsv", "Jasmine", "Truvari"],
        "expected_outputs": ["sv-ledger.tsv", "candidate_interval_sv.tsv"],
        "claim_boundary": "SV context is association evidence unless functionally validated",
    },
    "graph_pangenome_import": {
        "roi": "advanced_opt_in",
        "description": "Import existing pangenome graph support for candidate loci; do not build a graph by default.",
        "input_requirements": ["existing_graph_or_explicit_multi_assembly_graph_budget"],
        "required_tools": ["minigraph-cactus", "PGGB", "ODGI", "vg"],
        "expected_outputs": ["graph-ledger.tsv", "graph_path_support.tsv"],
        "claim_boundary": "graph support must preserve coordinate-system provenance and uncertainty",
    },
    "singlecell_spatial_context": {
        "roi": "late_evidence_only",
        "description": "Single-cell or spatial expression context after candidates and annotations are stable.",
        "input_requirements": ["single_cell_or_spatial_dataset", "candidate_gene_ids"],
        "required_tools": ["Scanpy_or_Seurat", "spatial_expression_tooling"],
        "expected_outputs": ["singlecell-dataset-ledger.tsv", "spatial-domain-expression.tsv"],
        "claim_boundary": "cell/spatial localization is context evidence, not product validation",
    },
}

WORKFLOW_CLASS_ORDER = list(WORKFLOW_CLASS_SPECS)

CLAIM_LEVEL_ROWS = [
    {
        "claim_level": "candidate",
        "allowed_statement": "A target sequence is a candidate homolog or family member for a pathway step.",
        "required_evidence": "homology_or_domain_hit;query_and_database_provenance",
        "forbidden_overclaim": "do_not_state_product_activity_or_cluster_membership",
        "review_gate": "human_review_required_for_broad_families",
    },
    {
        "claim_level": "genome_localized_candidate",
        "allowed_statement": "A candidate has coordinate-bearing support in the target genome or annotation.",
        "required_evidence": "anchor_ladder_with_coordinate_confidence",
        "forbidden_overclaim": "do_not_infer_physical_cluster_without_neighborhood_evidence",
        "review_gate": "coordinate_conflicts_must_be_resolved",
    },
    {
        "claim_level": "neighborhood_hypothesis",
        "allowed_statement": "Nearby genes make a pathway-context hypothesis plausible.",
        "required_evidence": "anchored_candidate;neighbor_annotations;claim_safe_domain_labels",
        "forbidden_overclaim": "do_not_state_validated_biosynthetic_gene_cluster",
        "review_gate": "manual_neighborhood_review",
    },
    {
        "claim_level": "pathway_hypothesis",
        "allowed_statement": "Multiple evidence classes support a pathway-step hypothesis.",
        "required_evidence": "homology;domain;orthology_or_anchor;claim_audit",
        "forbidden_overclaim": "do_not_state_in_planta_product_chemistry",
        "review_gate": "claim_audit_and_citation_review",
    },
    {
        "claim_level": "validated_elsewhere",
        "allowed_statement": "A function was validated in a cited external study and is used as a seed/control.",
        "required_evidence": "citation;sequence_accession;seed_provenance",
        "forbidden_overclaim": "do_not_transfer_validation_to_unvalidated_target_paralog",
        "review_gate": "citation_seed_audit",
    },
]


def slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return normalized.strip("-") or "genecluster-run"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def normalize_run_scope(run_scope: str) -> str:
    return RUN_SCOPE_ALIASES.get(run_scope, run_scope)


def provider_payload_name(provider: str) -> str:
    return {
        "runpod_pod": "runpod-pod.json",
        "local_full": "local-full.sh",
        "ssh_hpc": "ssh-hpc.sh",
        "cloud_vm": "cloud-vm.sh",
        "local_lite": "local-full.sh",
        "managed_workflow": "cloud-vm.sh",
    }.get(provider, f"{provider}.json")


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def first_present_env(names: list[str]) -> tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return "", ""


def image_registry_host(image: str) -> str:
    image = image.strip()
    if not image:
        return ""
    first = image.split("/", 1)[0]
    if "." in first or ":" in first or first == "localhost":
        return first.lower()
    return "docker.io"


def image_looks_runpod_public(image: str) -> bool:
    image = image.strip().lower()
    return image.startswith("runpod/") or image.startswith("runpod.io/")


def registry_auth_likely_required(image: str) -> bool:
    host = image_registry_host(image)
    if not host or image_looks_runpod_public(image):
        return False
    return host in AUTH_SENSITIVE_REGISTRY_HOSTS or any(host.endswith(suffix) for suffix in AUTH_SENSITIVE_REGISTRY_SUFFIXES)


def build_registry_auth_policy(image: str) -> dict[str, Any]:
    auth_env_name, _auth_id = first_present_env(RUNPOD_REGISTRY_AUTH_ENV_NAMES)
    public_assertion_env = next((name for name in RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES if env_truthy(name)), "")
    auth_likely_required = registry_auth_likely_required(image)
    return {
        "schema_version": 1,
        "registry_host": image_registry_host(image),
        "auth_likely_required": auth_likely_required,
        "auth_sensitive_registry_hosts": sorted(AUTH_SENSITIVE_REGISTRY_HOSTS),
        "auth_sensitive_registry_suffixes": list(AUTH_SENSITIVE_REGISTRY_SUFFIXES),
        "container_registry_auth_id_env_names": RUNPOD_REGISTRY_AUTH_ENV_NAMES,
        "container_registry_auth_id_present": bool(auth_env_name),
        "container_registry_auth_id_source_env": auth_env_name or "unset",
        "container_registry_auth_id_payload_field": "containerRegistryAuthId",
        "public_image_assertion_env_names": RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES,
        "public_image_asserted": bool(public_assertion_env),
        "public_image_assertion_source_env": public_assertion_env or "unset",
        "launch_blocker_if_missing": bool(auth_likely_required and not auth_env_name and not public_assertion_env),
        "notes": [
            "RunPod desiredStatus is not evidence that the container image was pulled.",
            "Private or auth-sensitive images need a RunPod container registry auth id at pod creation.",
            "Only set the public-image assertion when the exact digest-pinned image has been proven pullable without registry auth.",
        ],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_tsv_file(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def remote_stage_flags(run_scope: str, *, runtime_cap_hours: float = 24.0, allow_provider_large_downloads: bool = False) -> list[str]:
    flags = ["--toolcheck"]
    if run_scope == "full_campaign_24h":
        flags.extend(["--max-runtime-hours", _format_cap(runtime_cap_hours)])
    if run_scope in HEAVY_RUN_SCOPES:
        flags.append("--db-bootstrap")
        flags.append("--data-materialization")
        flags.append("--target-db-build")
        flags.append("--workflow-classes")
    flags.append("--cache-preflight")
    if run_scope in HEAVY_RUN_SCOPES:
        flags.append("--reference-import")
    flags.extend(["--query-preflight", "--decoy-preflight"])
    if run_scope in HEAVY_RUN_SCOPES:
        flags.append("--resolve-queries")
    if run_scope == "candidate_search":
        flags.extend(["--candidate-search", "--orthology-anchor", "--pathway-completeness"])
    elif run_scope in {"full_campaign", "full_campaign_24h"}:
        flags.extend([
            "--candidate-search",
            "--anchor-map",
            "--orthology-anchor",
            "--neighborhood-extract",
            "--neighborhood-score",
            "--pathway-completeness",
            "--full-campaign",
        ])
    elif run_scope in HEAVY_RUN_SCOPES:
        flags.extend(["--candidate-search", "--anchor-map", "--orthology-anchor", "--neighborhood-extract", "--neighborhood-score", "--pathway-completeness"])
    if allow_provider_large_downloads:
        flags.append("--allow-large-downloads")
    return flags


def database_row_enabled_for_scope(row: dict[str, str], run_scope: str) -> bool:
    gate = row.get("run_gate") or ("optional_max" if row.get("priority") == "optional_max" else "full_campaign")
    if run_scope == "full_campaign_24h":
        if gate == "candidate_search":
            return True
        if gate in {"full_campaign", "full_public_mining"}:
            return row.get("prep_roi") == "high" or (
                row.get("prep_roi") == "medium" and row.get("cost_class") in {"small", "medium"}
            )
        return False
    if gate == "candidate_search":
        return run_scope in {"candidate_search", "full_campaign", "full_public_mining", "full_campaign_24h"}
    if gate in {"full_campaign", "full_public_mining"}:
        return run_scope in {"full_campaign", "full_public_mining", "genome_context", "synteny", "coexpression"}
    return False


def build_search_plan(
    *,
    run_scope: str,
    heavy_workdir: str,
    database_ledger: Path,
    query_ledger: Path,
    runtime_cap_hours: float = 24.0,
) -> dict[str, Any]:
    rows = read_tsv_rows(database_ledger)
    enabled_rows = [row for row in rows if database_row_enabled_for_scope(row, run_scope)]
    optional_rows = [row for row in rows if row.get("run_gate") == "optional_max"]
    deferred_rows = [row for row in rows if row.get("run_gate") == "deferred_review"]
    db_ids = [row["db_id"] for row in enabled_rows]
    engines = sorted({row["engine"] for row in enabled_rows if row.get("engine") in {"blast", "diamond", "mmseqs", "hmmer"}})
    raw_path = f"{heavy_workdir}/work/search" if heavy_workdir else "not_applicable"
    summary_path = f"{heavy_workdir}/summary" if heavy_workdir else "summary"
    stages = [
        "cache_tool_preflight",
        "query_data_resolution",
        "timeboxed_reference_first_full_candidate_search" if run_scope == "full_campaign_24h" else (
            "full_candidate_search" if run_scope == "full_campaign" else "candidate_search"
        ),
        "domain_annotation",
        "deduplication_and_isoform_review",
        "genome_context",
        "synteny_coexpression_if_supported",
        "claim_audit",
        "dossier_export",
    ]
    forbidden_modes = [
        "ncbi_remote_blast_batch",
        "public_webserver_private_upload",
        "local_repo_raw_download",
    ]
    if run_scope == "full_campaign_24h":
        forbidden_modes.append("de_novo_assembly_without_explicit_budget_override")
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "database_tier": "maximum",
        "stages": stages,
        "search_engines": engines,
        "database_ids": db_ids,
        "optional_database_ids": [row["db_id"] for row in optional_rows],
        "deferred_database_ids": [row["db_id"] for row in deferred_rows],
        "database_groups": {
            "candidate_search": [row["db_id"] for row in rows if row.get("run_gate") == "candidate_search"],
            "full_campaign": [row["db_id"] for row in rows if row.get("run_gate") == "full_campaign"],
            "full_campaign_24h": [row["db_id"] for row in rows if database_row_enabled_for_scope(row, "full_campaign_24h")],
            "optional_max": [row["db_id"] for row in optional_rows],
            "deferred_review": [row["db_id"] for row in deferred_rows],
        },
        "query_strategy": {
            "query_ledger": str(Path("ledgers") / query_ledger.name),
            "resolution": "provider_remote_only",
            "private_sequences_allowed": False,
        },
        "raw_output_policy": {
            "path": raw_path,
            "local_copy": False,
            "retention": "provider_workdir_only",
        },
        "summary_output_policy": {
            "path": summary_path,
            "local_copy": True,
            "max_bytes_per_file": 10 * 1024 * 1024,
        },
        "forbidden_modes": forbidden_modes,
        "runtime_policy": build_runtime_policy(run_scope, runtime_cap_hours=runtime_cap_hours),
    }


def _format_cap(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def build_runtime_policy(run_scope: str, *, runtime_cap_hours: float = 24.0) -> dict[str, Any]:
    if run_scope == "full_campaign_24h":
        cap = runtime_cap_hours if runtime_cap_hours and runtime_cap_hours > 0 else 24
        return {
            "target_runtime_hours": cap,
            "hard_stop_hours": cap,
            "completion_definition": "complete_summary_dossier_with_deferred_lane_manifest",
            "lane_degradation_order": [
                "optional_max_databases",
                "de_novo_transcriptome_assembly",
                "interproscan_full_cache",
                "plantismash_full_run",
                "broad_nr_nt_searches",
                "coexpression_if_sample_design_or_runtime_insufficient",
                "synteny_if_reference_sets_or_runtime_insufficient",
            ],
            "required_to_finish": [
                "toolcheck",
                "cache_preflight",
                "query_resolution_or_blocker_report",
                "high_roi_candidate_search_or_blocker_report",
                "claim_audit",
                "dossier_manifest",
            ],
            "budget_policy": "finish_with_caveats_rather_than_extend_runtime",
        }
    return {
        "target_runtime_hours": None,
        "hard_stop_hours": None,
        "completion_definition": "scope_complete_or_review_gated",
        "lane_degradation_order": [],
        "required_to_finish": [],
        "budget_policy": "reviewed_operator_control",
    }


STAGE_OUTPUTS = {
    "--toolcheck": ["toolcheck.json", "versions.json"],
    "--db-bootstrap": ["db-bootstrap-summary.json"],
    "--data-materialization": ["data-materialization-summary.json", "materialized-targets.tsv"],
    "--target-db-build": ["target-db-build-summary.json", "target-db-indexes.tsv"],
    "--workflow-classes": ["workflow-class-summary.json", "workflow-deferred-lanes.tsv"],
    "--cache-preflight": ["cache-preflight.json"],
    "--reference-import": ["reference-import-summary.json", "resolved-references.tsv"],
    "--query-preflight": ["query-preflight.json"],
    "--resolve-queries": ["query-preflight.json"],
    "--decoy-preflight": ["decoy-preflight.json"],
    "--candidate-search": ["candidate-search-summary.json", "candidate_hits.tsv"],
    "--anchor-map": ["anchor-map-summary.json", "candidate_anchors.tsv"],
    "--orthology-anchor": ["orthology-anchor-summary.json", "orthology_links.tsv", "anchor_ladder.tsv"],
    "--neighborhood-extract": ["neighborhood-extract-summary.json", "cluster_neighborhoods.tsv", "neighbor_annotations.tsv"],
    "--neighborhood-score": ["neighborhood-score-summary.json", "neighborhood_hypotheses.tsv"],
    "--pathway-completeness": ["pathway-completeness-summary.json", "pathway_completeness.tsv"],
}


STAGE_TIMEOUT_MINUTES = {
    "--toolcheck": 10,
    "--db-bootstrap": 90,
    "--data-materialization": 180,
    "--target-db-build": 90,
    "--workflow-classes": 15,
    "--cache-preflight": 10,
    "--reference-import": 90,
    "--query-preflight": 15,
    "--resolve-queries": 30,
    "--decoy-preflight": 15,
    "--candidate-search": 240,
    "--anchor-map": 90,
    "--orthology-anchor": 90,
    "--neighborhood-extract": 120,
    "--neighborhood-score": 45,
    "--pathway-completeness": 30,
}


def stage_contract_required_tools(stage_flags: list[str]) -> list[dict[str, Any]]:
    """Return fail-closed tool proofs for tools commonly called by selected stages."""
    tool_specs = {
        "blastp": ("blastp", "blastp -version"),
        "tblastn": ("tblastn", "tblastn -version"),
        "makeblastdb": ("makeblastdb", "makeblastdb -version"),
        "diamond": ("diamond", "diamond version"),
        "mmseqs": ("mmseqs", "mmseqs version"),
        "hmmsearch": ("hmmsearch", "hmmsearch -h"),
        "hmmscan": ("hmmscan", "hmmscan -h"),
        "hmmpress": ("hmmpress", "hmmpress -h"),
        "miniprot": ("miniprot", "miniprot --version"),
        "datasets": ("datasets", "datasets version"),
        "prefetch": ("prefetch", "prefetch --version"),
        "fasterq-dump": ("fasterq-dump", "fasterq-dump --version"),
        "minimap2": ("minimap2", "minimap2 --version"),
        "nextflow": ("nextflow", "nextflow -version"),
        "hisat2": ("hisat2", "hisat2 --version"),
        "stringtie": ("stringtie", "stringtie --version"),
        "samtools": ("samtools", "samtools --version"),
        "gffread": ("gffread", "gffread --version"),
        "TransDecoder.LongOrfs": ("TransDecoder.LongOrfs", "TransDecoder.LongOrfs --help"),
        "TransDecoder.Predict": ("TransDecoder.Predict", "TransDecoder.Predict --help"),
    }
    by_flag = {
        "--toolcheck": list(tool_specs),
        "--db-bootstrap": ["blastp", "makeblastdb", "diamond", "mmseqs", "hmmsearch", "hmmscan", "hmmpress"],
        "--data-materialization": [
            "datasets",
            "prefetch",
            "fasterq-dump",
            "hisat2",
            "stringtie",
            "samtools",
            "gffread",
            "TransDecoder.LongOrfs",
            "TransDecoder.Predict",
            "minimap2",
        ],
        "--target-db-build": ["makeblastdb", "diamond", "mmseqs"],
        "--reference-import": ["datasets", "miniprot"],
        "--candidate-search": ["blastp", "tblastn", "diamond", "mmseqs", "hmmsearch", "hmmscan"],
        "--anchor-map": ["minimap2", "miniprot"],
        "--orthology-anchor": ["blastp", "diamond", "mmseqs", "miniprot"],
        "--neighborhood-extract": ["miniprot", "hmmscan", "hmmpress"],
        "--neighborhood-score": ["hmmscan"],
    }
    selected: list[str] = []
    seen: set[str] = set()
    for flag in stage_flags:
        for tool_name in by_flag.get(flag, []):
            if tool_name in seen:
                continue
            seen.add(tool_name)
            selected.append(tool_name)
    return [
        {
            "name": tool_name,
            "executable": executable,
            "proof_command": proof_command,
            "fail_closed": True,
        }
        for tool_name in selected
        for executable, proof_command in [tool_specs[tool_name]]
    ]


def stage_id_from_flag(flag: str) -> str:
    return flag.strip("-").replace("-", "_")


def build_stage_contract(
    *,
    run_id: str,
    provider_class: str,
    run_scope: str,
    heavy_workdir: str,
    runtime_cap_hours: float,
    stage_flags: list[str],
) -> dict[str, Any]:
    stages = []
    seen: set[str] = set()
    for flag in stage_flags:
        if flag not in STAGE_OUTPUTS or flag in seen:
            continue
        seen.add(flag)
        stage_id = stage_id_from_flag(flag)
        outputs = STAGE_OUTPUTS[flag]
        stages.append(
            {
                "stage_id": stage_id,
                "run_flag": flag,
                "entrypoint": "remote/genecluster_remote_runner.py",
                "expected_outputs": outputs,
                "done_marker": f"{heavy_workdir}/summary/{outputs[0]}" if heavy_workdir else f"summary/{outputs[0]}",
                "timeout_minutes": STAGE_TIMEOUT_MINUTES.get(flag, 60),
                "resume_strategy": "idempotent rerun of the same provider command; stage must reuse existing done_marker or rewrite it with provenance",
                "failure_policy": "fail-closed with blocked/partial summary rows; never substitute mock/reference-only outputs for target-organism evidence",
                "watch_fields": ["stage_id", "status", "timestamp", "elapsed_seconds", "message"],
            }
        )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "provider_class": provider_class,
        "run_scope": run_scope,
        "runtime_cap_hours": runtime_cap_hours,
        "progress_ledger": f"{heavy_workdir}/summary/stage-progress.jsonl" if heavy_workdir else "summary/stage-progress.jsonl",
        "required_tools": stage_contract_required_tools(stage_flags),
        "heartbeat_interval_minutes": 10,
        "stale_after_minutes": 30,
        "stages": stages,
        "watcher": {
            "required_for_runtime_hours_over": 2,
            "poll_interval_minutes": 10,
            "check_order": [
                "provider runtime is alive",
                "stage-progress.jsonl timestamp advances",
                "current stage log grows or reaches a terminal status",
                "summary artifacts appear under summary_outdir",
            ],
            "false_assumptions_to_avoid": [
                "do not assume stale progress means provider capacity",
                "do not assume provider RUNNING state means the biological stage is advancing",
                "do not assume a clean process exit means the pod will stay stopped without a self-stop wrapper",
            ],
            "allowed_transports": [
                "provider logs",
                "configured summary endpoint",
                "short-lived pull pod fallback",
            ],
        },
        "acceptance": {
            "final_success_requires": [
                "terminal progress row for every required stage",
                "stage expected_outputs present or explicit blocked/partial row",
                "contract self-check passes before target-organism success claim",
            ],
            "partial_verdict_allowed": True,
            "partial_verdict_requires": [
                "failed/skipped stage id",
                "reason and next resume command",
                "claim downgrade in final dossier",
            ],
        },
    }


def data_row_text(row: dict[str, str]) -> str:
    return " ".join(
        str(row.get(key, ""))
        for key in [
            "dataset_id",
            "accession",
            "run_id",
            "data_role",
            "sample_type",
            "technology",
            "organism",
            "notes",
        ]
    ).lower()


def data_row_has_unresolved_metadata(row: dict[str, str]) -> bool:
    text = data_row_text(row)
    return any(token in text for token in ["remote_resolve_required", "metadata_pending", "resolve_required", "pending_metadata"])


def data_row_is_transcriptome(row: dict[str, str]) -> bool:
    text = data_row_text(row)
    return any(token in text for token in ["transcript", "rna", "cdna", "isoseq", "iso-seq"])


def data_row_is_genome(row: dict[str, str]) -> bool:
    text = data_row_text(row)
    return any(token in text for token in ["genome", "assembly", "wgs", "gff", "gtf", "annotation"])


def data_row_is_long_read(row: dict[str, str]) -> bool:
    text = data_row_text(row)
    return any(token in text for token in ["isoseq", "iso-seq", "pacbio", "ont", "nanopore", "sequel", "long-read", "long read"])


def data_signals(data_ledger: Path, query_ledger: Path) -> dict[str, Any]:
    data_rows = read_tsv_rows(data_ledger)
    query_rows = read_tsv_rows(query_ledger)
    lowered_data = " ".join(
        " ".join(str(row.get(key, "")) for key in ["data_role", "sample_type", "technology", "organism"]).lower()
        for row in data_rows
    )
    transcriptome_rows = [row for row in data_rows if data_row_is_transcriptome(row)]
    genome_rows = [row for row in data_rows if data_row_is_genome(row)]
    long_read_rows = [row for row in data_rows if data_row_is_long_read(row)]
    unresolved_transcriptome_rows = [row for row in transcriptome_rows if data_row_has_unresolved_metadata(row)]
    has_genome = bool(genome_rows) or any(token in lowered_data for token in ["genome", "assembly", "wgs"])
    has_transcriptome = bool(transcriptome_rows) or any(token in lowered_data for token in ["transcript", "rna", "isoseq", "iso-seq"])
    has_long_read = bool(long_read_rows) or any(token in lowered_data for token in ["isoseq", "iso-seq", "pacbio", "ont", "nanopore", "sequel", "long-read", "long read"])
    has_expression = sum(1 for row in data_rows if any(token in row.get("data_role", "").lower() for token in ["rna", "transcript", "expression"])) >= 2
    has_annotation = any(token in lowered_data for token in ["gff", "gtf", "annotation", "protein", "proteome"])
    assembly_count = sum(1 for row in data_rows if any(token in row.get("data_role", "").lower() for token in ["genome", "assembly", "wgs"]))
    broad_query_count = sum(1 for row in query_rows if row.get("decoy_or_broad_family_flag") == "true" or row.get("expected_false_positive_risk") == "high")
    has_singlecell_or_spatial = any(token in lowered_data for token in ["single-cell", "single cell", "scrna", "spatial"])
    return {
        "dataset_count": len(data_rows),
        "query_count": len(query_rows),
        "has_genome": has_genome,
        "has_transcriptome": has_transcriptome,
        "has_long_read": has_long_read,
        "metadata_pending_transcriptome_count": len(unresolved_transcriptome_rows),
        "metadata_pending_dataset_ids": [row.get("dataset_id", "") for row in data_rows if data_row_has_unresolved_metadata(row)],
        "transcriptome_dataset_ids": [row.get("dataset_id", "") for row in transcriptome_rows],
        "genome_dataset_ids": [row.get("dataset_id", "") for row in genome_rows],
        "long_read_dataset_ids": [row.get("dataset_id", "") for row in long_read_rows],
        "has_expression_design": has_expression,
        "has_annotation_or_protein": has_annotation,
        "assembly_count": assembly_count,
        "broad_query_count": broad_query_count,
        "has_singlecell_or_spatial": has_singlecell_or_spatial,
    }


def workflow_status(class_id: str, *, run_scope: str, signals: dict[str, Any]) -> tuple[str, str]:
    if run_scope not in HEAVY_RUN_SCOPES:
        return "deferred", "non-heavy scope records the workflow class but does not activate heavy/provider lanes"
    if class_id == "reference_first_anchor_mining":
        return "activated", "required first-pass lane for provider-local candidate discovery"
    if class_id == "long_read_isoform_curation":
        if signals["has_long_read"]:
            return "activated", "long-read/Iso-Seq signal is present"
        if signals.get("metadata_pending_transcriptome_count", 0):
            return "deferred", "transcriptome metadata is unresolved; re-evaluate long-read/Iso-Seq lane after provider metadata resolution"
        return "blocked", "no long-read transcriptome dataset is declared"
    if class_id == "transcriptome_only_dossier":
        if signals["has_transcriptome"] and not signals["has_genome"]:
            return "activated", "transcriptome evidence exists and no genome context is available"
        return "deferred", "not the primary lane when genome/context resources are declared"
    if class_id == "paralog_homeolog_copy_review":
        if signals["broad_query_count"] or run_scope in {"synteny", "full_public_mining", "full_campaign", "full_campaign_24h"}:
            return "activated", "broad-family or full comparative context requires copy review"
        return "deferred", "activate after candidate set shows paralog/homeolog ambiguity"
    if class_id == "expression_coexpression_support":
        if run_scope == "full_campaign_24h":
            return "deferred_by_budget", "24h profile defers slow coexpression unless cached and sample design is already reviewed"
        if run_scope == "coexpression" or signals["has_expression_design"]:
            return "activated", "expression/coexpression scope or multiple transcriptome samples are declared"
        return "blocked", "insufficient expression sample design"
    if class_id == "comparative_synteny_neighborhood":
        if signals["has_genome"]:
            return "activated", "genome/assembly context is declared for anchor-centered neighborhoods"
        return "blocked", "no genome or assembly resource is declared"
    if class_id == "fragmented_genome_rescue":
        if signals["has_genome"] and not signals["has_annotation_or_protein"]:
            return "activated", "genome exists but annotation/protein resources are weak or missing"
        if signals["has_genome"]:
            return "deferred", "available annotations should be tried before rescue lanes"
        return "blocked", "requires a target genome or assembly"
    if class_id == "pav_copy_number_matrix":
        if run_scope == "full_campaign_24h":
            return "deferred_by_budget", "multi-assembly PAV/copy-number review is outside the first 24h lane"
        if signals["assembly_count"] >= 2:
            return "activated", "multiple assemblies/genomes are declared"
        return "deferred", "activate when multiple assemblies or accessions are available"
    if class_id == "candidate_sv_interval":
        if run_scope == "full_campaign_24h":
            return "deferred_by_budget", "SV interval review is deferred in one-day campaigns"
        if signals["has_long_read"] and signals["has_genome"]:
            return "deferred", "available long reads/genome can support SV review after candidates are anchored"
        return "blocked", "requires long reads or multiple assemblies plus candidate intervals"
    if class_id == "graph_pangenome_import":
        if run_scope == "full_campaign_24h":
            return "deferred_by_budget", "graph/pangenome import is advanced opt-in and not part of the first 24h run"
        return "deferred", "only activate when an existing graph or explicit multi-assembly graph budget is provided"
    if class_id == "singlecell_spatial_context":
        if signals["has_singlecell_or_spatial"]:
            return "deferred", "single-cell/spatial context is late evidence after stable candidate IDs"
        return "blocked", "no single-cell or spatial dataset is declared"
    return "blocked", "unknown workflow class"


def build_workflow_class_plan(
    *,
    run_scope: str,
    provider_class: str,
    data_ledger: Path,
    query_ledger: Path,
    runtime_cap_hours: float = 24.0,
) -> dict[str, Any]:
    signals = data_signals(data_ledger, query_ledger)
    runtime_policy = build_runtime_policy(run_scope, runtime_cap_hours=runtime_cap_hours)
    records = []
    for class_id in WORKFLOW_CLASS_ORDER:
        spec = WORKFLOW_CLASS_SPECS[class_id]
        status, reason = workflow_status(class_id, run_scope=run_scope, signals=signals)
        records.append(
            {
                "workflow_class": class_id,
                "status": status,
                "activation_reason": reason,
                "roi": spec["roi"],
                "description": spec["description"],
                "input_requirements": spec["input_requirements"],
                "required_tools": spec["required_tools"],
                "expected_outputs": spec["expected_outputs"],
                "claim_boundary": spec["claim_boundary"],
                "local_copy": True,
            }
        )
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "provider_class": provider_class,
        "signals": signals,
        "runtime_policy": runtime_policy,
        "workflow_classes": records,
        "local_copy": True,
        "heavy_artifact_policy": "provider_workdir_only",
    }


def build_lane_activation_plan(workflow_plan: dict[str, Any]) -> dict[str, Any]:
    records = workflow_plan["workflow_classes"]
    activation_matrix = [
        {
            "workflow_class": record["workflow_class"],
            "status": record["status"],
            "reason": record["activation_reason"],
            "expected_outputs": record["expected_outputs"],
            "claim_boundary": record["claim_boundary"],
        }
        for record in records
    ]
    return {
        "schema_version": 1,
        "run_scope": workflow_plan["run_scope"],
        "activated_lanes": [row["workflow_class"] for row in records if row["status"] == "activated"],
        "blocked_lanes": [row["workflow_class"] for row in records if row["status"] == "blocked"],
        "deferred_lanes": [row["workflow_class"] for row in records if row["status"] in {"deferred", "deferred_by_budget"}],
        "activation_matrix": activation_matrix,
        "local_copy": True,
    }


def build_evidence_escalation_plan(*, run_scope: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "escalation_rules": [
            {
                "evidence_state": "transcript_hit_only",
                "next_workflow_class": "reference_first_anchor_mining",
                "required_before_claim_upgrade": "anchor_ladder coordinate support",
                "claim_boundary": "candidate only; no physical cluster claim",
            },
            {
                "evidence_state": "long_read_isoform_ambiguity",
                "next_workflow_class": "long_read_isoform_curation",
                "required_before_claim_upgrade": "representative ORF and isoform-domain delta review",
                "claim_boundary": "isoform support only",
            },
            {
                "evidence_state": "broad_family_hit",
                "next_workflow_class": "paralog_homeolog_copy_review",
                "required_before_claim_upgrade": "copy classification plus reciprocal/domain/phylogeny support",
                "claim_boundary": "broad family cannot support product chemistry alone",
            },
            {
                "evidence_state": "anchored_candidate",
                "next_workflow_class": "comparative_synteny_neighborhood",
                "required_before_claim_upgrade": "neighbor/domain/synteny evidence with coordinate provenance",
                "claim_boundary": "neighborhood hypothesis only",
            },
            {
                "evidence_state": "missing_step_after_candidate_search",
                "next_workflow_class": "transcriptome_only_dossier",
                "required_before_claim_upgrade": "ORF and domain review or explicit missing status",
                "claim_boundary": "pathway completeness remains partial or missing",
            },
            {
                "evidence_state": "copy_number_or_presence_absence_question",
                "next_workflow_class": "pav_copy_number_matrix",
                "required_before_claim_upgrade": "multi-assembly/sample support",
                "claim_boundary": "copy/PAV support is not functional validation",
            },
        ],
        "forbidden_upgrades": [
            "transcriptome_only_to_physical_cluster",
            "domain_only_to_product_chemistry",
            "coexpression_only_to_enzyme_function",
            "graph_path_only_to_validated_locus",
        ],
        "local_copy": True,
    }


def build_workflow_deferred_rows(workflow_plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for record in workflow_plan["workflow_classes"]:
        if record["status"] not in {"deferred", "deferred_by_budget", "blocked"}:
            continue
        rows.append(
            {
                "workflow_class": record["workflow_class"],
                "deferred_status": record["status"],
                "reason": record["activation_reason"],
                "trigger_to_reactivate": ";".join(record["input_requirements"]),
                "claim_effect": record["claim_boundary"],
                "review_status": "needs-human-review",
            }
        )
    return rows


def build_db_bootstrap_plan(*, run_scope: str, heavy_workdir: str, database_ledger: Path) -> dict[str, Any]:
    rows = read_tsv_rows(database_ledger)
    enabled_rows = [row for row in rows if database_row_enabled_for_scope(row, run_scope)]
    db_cache_root = "not_applicable"
    if run_scope in HEAVY_RUN_SCOPES and heavy_workdir:
        db_cache_root = "/workspace/genecluster/db-cache" if heavy_workdir.startswith("/workspace/") else f"{heavy_workdir}/databases"
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "database_ledger": str(Path("ledgers") / database_ledger.name),
        "db_cache_root": db_cache_root,
        "records": [
            {
                "db_id": row.get("db_id", ""),
                "engine": row.get("engine", ""),
                "remote_path": row.get("remote_path", ""),
                "priority": row.get("priority", ""),
                "run_gate": row.get("run_gate", ""),
                "cost_class": row.get("cost_class", ""),
                "prep_roi": row.get("prep_roi", ""),
                "bootstrap_strategy": row.get("bootstrap_strategy", ""),
                "build_required": row.get("build_required", ""),
                "search_template": row.get("search_template", ""),
            }
            for row in enabled_rows
        ],
        "forbidden_local_paths": True,
        "optional_max_deferred": [row["db_id"] for row in rows if row.get("run_gate") == "optional_max"],
        "execution_policy": "provider_cache_only",
    }


def build_reference_import_plan(*, run_scope: str, heavy_workdir: str, data_ledger: Path, runtime_cap_hours: float = 24.0) -> dict[str, Any]:
    records = []
    for row in read_tsv_rows(data_ledger):
        accession = row.get("accession", "")
        run_id = row.get("run_id", "")
        data_role = row.get("data_role", "")
        planned_action = "metadata_only"
        if run_scope in HEAVY_RUN_SCOPES and accession.startswith(("SRX", "SRR", "ERP", "ERR", "DRR")):
            planned_action = "provider_fetchngs_or_sratools_timeboxed" if run_scope == "full_campaign_24h" else "provider_fetchngs_or_sratools"
        elif row.get("source_url", "").startswith(("http://", "https://", "ftp://")):
            planned_action = "provider_public_reference_review"
        records.append(
            {
                "dataset_id": row.get("dataset_id", ""),
                "accession": accession,
                "run_id": run_id,
                "data_role": data_role,
                "technology": row.get("technology", ""),
                "remote_path": row.get("remote_path", ""),
                "raw_artifact_policy": row.get("raw_artifact_policy", ""),
                "planned_action": planned_action,
            }
        )
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "data_ledger": str(Path("ledgers") / data_ledger.name),
        "provider_inputs_dir": f"{heavy_workdir}/inputs" if heavy_workdir else "not_applicable",
        "records": records,
        "preferred_order": [
            "existing_public_genome_protein_gff",
            "public_transcript_or_protein_import",
            "raw_sra_fetch_remote_only",
            "assembly_only_if_reference_first_fails",
        ],
        "runtime_policy": build_runtime_policy(run_scope, runtime_cap_hours=runtime_cap_hours),
        "local_copy": False,
    }


def build_data_materialization_plan(
    *,
    provider: str,
    run_scope: str,
    heavy_workdir: str,
    data_ledger: Path,
) -> dict[str, Any]:
    rows = read_tsv_rows(data_ledger)
    records: list[dict[str, Any]] = []
    raw_sra_count = 0
    materializable_raw_count = 0
    unsupported_raw_count = 0
    direct_index_count = 0
    reference_count = 0
    for row in rows:
        dataset_id = row.get("dataset_id", "")
        accession = row.get("accession", "")
        run_id = row.get("run_id", "")
        resource_kind = target_resource_kind_for_row(row)
        sequence_type = target_sequence_type_for_data_role(row.get("data_role", ""), row.get("technology", ""))
        remote_path = row.get("remote_path", "")
        if resource_kind == "target_raw_sequence_source":
            raw_sra_count += 1
            materialization_action = "raw_sra_to_target_sequences"
            if sequence_type == "nucleotide":
                materializable_raw_count += 1
                current_runner_support = "implemented_provider_sratools_to_target_fasta"
                execution_gate = "data-materialization-summary.json must report materialized target_sequences.fasta before target DB build"
                expected_provider_outputs = [
                    f"{heavy_workdir}/inputs/sra/{run_id or accession}",
                    f"{heavy_workdir}/inputs/target-sequences/{slug(dataset_id)}/target_sequences.fasta",
                    f"{heavy_workdir}/databases/target/{slug(dataset_id)}/indexes/blast",
                ]
            else:
                unsupported_raw_count += 1
                current_runner_support = "deferred_genome_or_mixed_raw_materialization"
                execution_gate = "defer or provide existing assembly/transcript/protein FASTA before cluster claims"
                expected_provider_outputs = [
                    f"{remote_path}/prefetch",
                    f"{heavy_workdir}/inputs/assemblies/{slug(dataset_id)}",
                ]
        elif sequence_type in {"protein", "nucleotide", "genome"}:
            direct_index_count += 1
            materialization_action = "verify_existing_provider_source_then_index"
            current_runner_support = "implemented_if_source_path_exists"
            execution_gate = "target_db_builder_must_report_built_or_present"
            expected_provider_outputs = [
                remote_path,
                f"{heavy_workdir}/databases/target/{slug(dataset_id)}/indexes",
            ]
        else:
            reference_count += 1
            materialization_action = "metadata_or_reference_review"
            current_runner_support = "metadata_or_reference_import_only"
            execution_gate = "not_a_searchable_target_until_sequence_source_exists"
            expected_provider_outputs = [remote_path]
        records.append(
            {
                "dataset_id": dataset_id,
                "accession": accession,
                "run_id": run_id,
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "resource_kind": resource_kind,
                "sequence_type": sequence_type,
                "remote_path": remote_path,
                "materialization_action": materialization_action,
                "current_runner_support": current_runner_support,
                "execution_gate": execution_gate,
                "expected_provider_outputs": expected_provider_outputs,
                "local_copy": False,
            }
        )
    raw_sra_blocks_current_runner = raw_sra_count > 0 and materializable_raw_count == 0 and run_scope in HEAVY_RUN_SCOPES
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "provider_class": provider,
        "blessed_heavy_provider": "runpod_pod",
        "data_ledger": str(Path("ledgers") / data_ledger.name),
        "provider_workdir": heavy_workdir or "not_applicable",
        "execution_maturity_levels": [
            {
                "level": "L0_control_plane_ready",
                "definition": "Manifests, ledgers, plans, and validation commands exist; no biological execution implied.",
                "claim_allowed": "planning readiness only",
            },
            {
                "level": "L1_provider_tool_ready",
                "definition": "Provider image/toolcheck passes and lifecycle/summary policies validate.",
                "claim_allowed": "provider can start the workflow",
            },
            {
                "level": "L2_provider_db_ready",
                "definition": "Required search/domain databases are present or explicitly built on provider storage.",
                "claim_allowed": "reference database search readiness",
            },
            {
                "level": "L3_target_materialized_ready",
                "definition": "Target species FASTA/GFF/protein/transcript sources exist on provider storage and target indexes were built.",
                "claim_allowed": "target-species candidate search readiness",
            },
            {
                "level": "L4_raw_sra_pipeline_ready",
                "definition": "SRX/SRR reads are resolved, fetched, converted, assembled/imported or translated, and indexed on provider storage.",
                "claim_allowed": "raw-SRA-derived candidate search readiness",
            },
            {
                "level": "L5_claim_audited_dossier_ready",
                "definition": "Candidate, anchor, neighborhood, provenance, versions, and claim-audit summaries validate.",
                "claim_allowed": "review-gated biological hypotheses",
            },
        ],
        "provider_support": {
            "local_lite": "L0 only; no raw downloads or heavy indexes",
            "local_full": "L1-L5 only with explicit opt-in and heavy_workdir outside repo",
            "runpod_pod": "blessed L1-L5 path for internal heavy execution",
            "ssh_hpc": "supported contract; operator supplies host, scheduler conventions, and storage",
            "cloud_vm": "supported contract; operator supplies VM, attached volume, and summary sync",
            "managed_workflow": "future backend",
        },
        "allow_large_downloads_semantics": "Allows provider-side large DB/reference downloads where implemented; it does not by itself implement raw SRA fetch, FASTQ conversion, de novo assembly, ORF calling, or target DB indexing.",
        "target_search_requires_materialized_target_db": True,
        "candidate_promotion_required_gates": [
            "reference-import-summary.json shows imported or intentionally metadata-only resources",
            "target-db-build-summary.json is ok and target-db-indexes.tsv has built/present indexes for target datasets",
            "search-command-plan.json points to target_* databases for target-species candidate claims",
            "candidate_hits.tsv dataset_id and target_db_id identify target species resources, not generic provider_search placeholders",
        ],
        "raw_sra_blocks_current_runner_execution_ready": raw_sra_blocks_current_runner,
        "records": records,
        "summary": {
            "raw_sra_source_count": raw_sra_count,
            "materializable_raw_sra_source_count": materializable_raw_count,
            "unsupported_raw_sra_source_count": unsupported_raw_count,
            "direct_index_source_count": direct_index_count,
            "reference_or_metadata_source_count": reference_count,
            "current_runner_can_materialize_raw_sra": materializable_raw_count > 0,
            "recommended_next_issue": "Use provider data-materialization for transcript-like SRA; provide an assembly/reference or explicit assembly lane before promoting physical cluster claims.",
        },
        "local_copy": False,
    }


def target_sequence_type_for_data_role(data_role: str, technology: str = "") -> str:
    lowered = f"{data_role} {technology}".lower()
    if "protein" in lowered or "proteome" in lowered:
        return "protein"
    if "gff" in lowered or "gtf" in lowered or "annotation" in lowered:
        return "annotation"
    if "genome" in lowered or "assembly" in lowered or "wgs" in lowered:
        return "genome"
    if "transcript" in lowered or "rna" in lowered or "isoseq" in lowered:
        return "nucleotide"
    return "mixed"


def target_resource_kind_for_row(row: dict[str, str]) -> str:
    data_role = row.get("data_role", "").lower()
    accession = row.get("accession", "")
    if accession.startswith(("SRX", "SRR", "ERR", "ERP", "DRR", "DRX")) and "assembly" not in data_role:
        return "target_raw_sequence_source"
    if "assembly" in data_role or "genome" in data_role or "wgs" in data_role:
        return "target_genome_fasta"
    if "transcript" in data_role or "rna" in data_role or "isoseq" in data_role:
        return "target_transcript_nucleotide"
    if "protein" in data_role or "proteome" in data_role:
        return "target_protein_fasta"
    if "gff" in data_role or "annotation" in data_role:
        return "target_annotation_gff"
    return "target_resource"


def build_target_db_plan(*, run_scope: str, heavy_workdir: str, data_ledger: Path) -> dict[str, Any]:
    provider_db_root = f"{heavy_workdir}/databases/target" if heavy_workdir else "not_applicable"
    records: list[dict[str, Any]] = []
    index_targets: list[dict[str, Any]] = []
    source_rows = read_tsv_rows(data_ledger) if run_scope in HEAVY_RUN_SCOPES else []
    for row in source_rows:
        dataset_id = row.get("dataset_id", "")
        resource_kind = target_resource_kind_for_row(row)
        raw_sequence_type = target_sequence_type_for_data_role(row.get("data_role", ""), row.get("technology", ""))
        sequence_type = raw_sequence_type if resource_kind == "target_raw_sequence_source" else raw_sequence_type
        target_db_id = f"target_{slug(dataset_id)}"
        provider_path = f"{provider_db_root}/{slug(dataset_id)}"
        source_path = row.get("remote_path", "")
        index_policy = "coordinate_only"
        if resource_kind == "target_raw_sequence_source":
            if sequence_type in {"nucleotide"}:
                source_path = f"{heavy_workdir}/inputs/target-sequences/{slug(dataset_id)}/target_sequences.fasta"
                index_policy = "blast_tblastn_from_materialized_reads"
            else:
                index_policy = "deferred_raw_genome_or_mixed_materialization_required"
        if sequence_type == "protein":
            index_policy = "blast_diamond_mmseqs"
        elif (
            sequence_type in {"nucleotide", "genome"}
            and index_policy not in {
                "deferred_raw_genome_or_mixed_materialization_required",
                "blast_tblastn_from_materialized_reads",
            }
        ):
            index_policy = "blast_mmseqs_miniprot" if sequence_type == "genome" else "blast_mmseqs"
        build_required = run_scope in HEAVY_RUN_SCOPES and index_policy not in {"coordinate_only", "deferred_raw_genome_or_mixed_materialization_required"}
        if run_scope == "full_campaign_24h" and sequence_type == "genome":
            build_required = False
        records.append(
            {
                "target_db_id": target_db_id,
                "dataset_id": dataset_id,
                "species": row.get("organism", ""),
                "resource_kind": resource_kind,
                "sequence_type": sequence_type,
                "source_path": source_path,
                "provider_path": provider_path,
                "index_policy": index_policy,
                "build_required": build_required,
                "checksum_status": row.get("checksum_status", "remote_pending"),
                "local_copy": False,
                "notes": row.get("notes", ""),
            }
        )
        engines: list[str] = []
        if not build_required:
            engines = []
        elif resource_kind == "target_raw_sequence_source" and index_policy == "deferred_raw_genome_or_mixed_materialization_required":
            engines = []
        elif sequence_type == "protein":
            engines = ["blast", "diamond", "mmseqs"]
        elif sequence_type == "nucleotide":
            engines = ["blast"]
        elif sequence_type == "genome":
            engines = ["blast", "mmseqs", "miniprot"]
        for engine in engines:
            index_targets.append(
                {
                    "target_db_id": target_db_id,
                    "dataset_id": dataset_id,
                    "engine": engine,
                    "sequence_type": sequence_type,
                    "source_path": source_path,
                    "index_path": f"{provider_path}/indexes/{engine}",
                    "build_required": True,
                    "local_copy": False,
                }
            )
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "data_ledger": str(Path("ledgers") / data_ledger.name),
        "provider_db_root": provider_db_root,
        "records": records,
        "index_targets": index_targets,
        "outputs": {
            "build_summary": f"{heavy_workdir}/summary/target-db-build-summary.json" if heavy_workdir else "not_applicable",
            "resolved_ledger": f"{heavy_workdir}/summary/target-db-ledger.resolved.tsv" if heavy_workdir else "not_applicable",
            "index_ledger": f"{heavy_workdir}/summary/target-db-indexes.tsv" if heavy_workdir else "not_applicable",
        },
        "execution_policy": "provider_indexes_only_no_repo_paths",
        "local_copy": False,
    }


def build_candidate_route_plan(
    *,
    run_scope: str,
    provider_class: str,
    heavy_workdir: str,
    data_ledger: Path,
    query_ledger: Path,
    target_db_plan: dict[str, Any],
    runtime_cap_hours: float = 24.0,
) -> dict[str, Any]:
    """Describe the biological route, not just the commands the runner accepts.

    This is intentionally stricter than the launch/preflight contract. A bundle
    can be technically runnable while this plan still says the scientifically
    preferred transcript-first route is not fully wired yet.
    """

    rows = read_tsv_rows(data_ledger)
    signals = data_signals(data_ledger, query_ledger)
    transcriptome_rows = [row for row in rows if data_row_is_transcriptome(row)]
    genome_rows = [row for row in rows if data_row_is_genome(row)]
    direct_annotation_rows = [
        row for row in rows
        if any(token in data_row_text(row) for token in ["protein", "proteome", "gff", "gtf", "annotation"])
    ]
    has_transcriptome = bool(transcriptome_rows)
    has_genome = bool(genome_rows)
    has_unresolved_transcriptome = any(data_row_has_unresolved_metadata(row) for row in transcriptome_rows)

    if has_transcriptome and has_genome:
        primary_route = "transcript_first_then_genome_anchor"
        route_reason = "Transcript evidence plus genome context are declared; candidate proteins should come from transcript/ORF evidence before coordinate anchoring."
    elif has_transcriptome:
        primary_route = "transcript_first_candidate_dossier"
        route_reason = "Transcriptome evidence is declared but genome context is absent; produce transcript/protein candidates and keep cluster claims forbidden."
    elif has_genome:
        primary_route = "genome_direct_rescue"
        route_reason = "Genome is declared without transcript evidence; direct protein-to-genome/tblastn is a rescue route with weaker gene-model confidence."
    else:
        primary_route = "reference_only_or_metadata"
        route_reason = "No target transcriptome or genome sequence source is declared."

    implemented_runner_route = "provider_materialized_nucleotide_tblastn"
    implemented_stages = [
        "provider SRA fetch/FASTQ conversion for transcript-like rows when --allow-large-downloads is set",
        "provider target nucleotide FASTA materialization",
        "provider BLAST nucleotide DB build",
        "protein-query tblastn against target nucleotide DB",
        "summary-only candidate table and provenance",
    ]
    missing_transcript_first_stages = []
    if has_transcriptome:
        missing_transcript_first_stages.extend(
            [
                "transcriptome curation or assembly stage selected from metadata (Iso-Seq cluster/import, long-read curation, Trinity/rnaSPAdes, or public transcript import)",
                "ORF prediction and target proteome FASTA generation",
                "provider target proteome BLAST/DIAMOND/MMseqs indexes",
                "blastp/DIAMOND/MMseqs protein-vs-protein candidate search against target proteome",
                "representative isoform and partial-transcript review",
            ]
        )
    if has_transcriptome and has_genome:
        missing_transcript_first_stages.extend(
            [
                "splice-aware transcript-to-genome mapping for candidate transcripts",
                "coordinate confidence scoring from transcript/genome alignments",
                "anchor-centered window extraction after transcript-supported loci are identified",
            ]
        )

    transcript_first_required = run_scope in HEAVY_RUN_SCOPES and has_transcriptome
    strict_scientific_blockers = []
    if transcript_first_required and missing_transcript_first_stages:
        strict_scientific_blockers.append("transcript_first_route_not_implemented_in_current_runner")
    if has_unresolved_transcriptome:
        strict_scientific_blockers.append("transcriptome_metadata_resolution_required_before_final_route_selection")

    if strict_scientific_blockers:
        science_readiness = "candidate_smoke_ready_not_transcript_first_full_ready"
    elif run_scope in HEAVY_RUN_SCOPES:
        science_readiness = "full_route_ready"
    else:
        science_readiness = "control_plane_only"

    route_records = []
    for row in rows:
        dataset_id = row.get("dataset_id", "")
        sequence_type = target_sequence_type_for_data_role(row.get("data_role", ""), row.get("technology", ""))
        if data_row_is_transcriptome(row):
            preferred_role = "primary_candidate_source"
            preferred_route_stage = "transcript_curation_or_assembly_to_orfs_to_protein_search"
            current_runner_route = "read_or_cDNA_level_tblastn_smoke"
            claim_boundary = "Candidate transcript hit only until ORF/protein and isoform review succeed."
        elif data_row_is_genome(row):
            preferred_role = "coordinate_anchor_after_transcript_candidates"
            preferred_route_stage = "splice_aware_mapping_or_miniprot_rescue_then_neighborhood_capture"
            current_runner_route = "direct_genome_search_rescue_or_deferred"
            claim_boundary = "Direct genome hits are rescue evidence; use transcript-supported coordinates before cluster claims when transcript data exists."
        elif any(token in data_row_text(row) for token in ["protein", "proteome", "gff", "gtf", "annotation"]):
            preferred_role = "direct_reference_import"
            preferred_route_stage = "import_existing_annotation_and_build_target_indexes"
            current_runner_route = "implemented_if_provider_source_exists"
            claim_boundary = "Annotation-derived candidates still require provenance and claim audit."
        else:
            preferred_role = "metadata_or_outgroup_context"
            preferred_route_stage = "metadata_resolution"
            current_runner_route = "metadata_only"
            claim_boundary = "Context only until searchable provider sequences exist."
        route_records.append(
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "data_role": row.get("data_role", ""),
                "technology": row.get("technology", ""),
                "sequence_type": sequence_type,
                "preferred_role": preferred_role,
                "preferred_route_stage": preferred_route_stage,
                "current_runner_route": current_runner_route,
                "metadata_status": "unresolved" if data_row_has_unresolved_metadata(row) else "declared",
                "claim_boundary": claim_boundary,
            }
        )

    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "provider_class": provider_class,
        "provider_workdir": heavy_workdir or "not_applicable",
        "runtime_cap_hours": runtime_cap_hours,
        "data_ledger": str(Path("ledgers") / data_ledger.name),
        "target_db_plan": "target-db-plan.json",
        "signals": signals,
        "primary_route": primary_route,
        "route_reason": route_reason,
        "scientific_default_order": [
            "resolve metadata and classify target resources",
            "prefer public/imported target transcript/protein/annotation resources when available",
            "curate or assemble transcriptome and call ORFs before target-species protein searches",
            "search canonical source proteins against target proteome/transcript ORFs",
            "use reciprocal/domain/paralog filters before promotion",
            "map transcript-supported candidates to genome with splice-aware alignment",
            "use direct genome tblastn/miniprot only as rescue or coordinate support",
            "extract neighborhoods only after coordinate confidence is recorded",
            "claim-audit pathway completeness and cluster/product language",
        ],
        "implemented_runner_route": implemented_runner_route,
        "implemented_runner_stages": implemented_stages,
        "missing_transcript_first_stages": missing_transcript_first_stages,
        "transcript_first_required_for_scientific_full": transcript_first_required,
        "strict_scientific_blockers": strict_scientific_blockers,
        "science_readiness": science_readiness,
        "direct_genome_tblastn_policy": (
            "rescue_only_not_primary_when_transcript_evidence_exists"
            if has_transcriptome else "allowed_as_primary_only_when_transcriptome_unavailable"
        ),
        "target_index_summary": {
            "records": len(target_db_plan.get("records", [])),
            "index_targets": len(target_db_plan.get("index_targets", [])),
            "index_policies": sorted({row.get("index_policy", "") for row in target_db_plan.get("records", [])}),
        },
        "route_records": route_records,
        "route_audit": {
            "basic_command": "python3 skills/biosymphony/scripts/genecluster_route_audit.py --launch-manifest launch-manifest.json",
            "strict_transcript_first_command": "python3 skills/biosymphony/scripts/genecluster_route_audit.py --launch-manifest launch-manifest.json --require-transcript-first",
            "strict_expected_result": "fail until missing_transcript_first_stages is empty and metadata-dependent route selection is resolved",
        },
        "local_copy": True,
    }


def build_anchor_map_plan(*, run_scope: str, heavy_workdir: str) -> dict[str, Any]:
    if run_scope not in HEAVY_RUN_SCOPES or not heavy_workdir:
        candidate_hits = resolved_references = output = "not_applicable"
    else:
        candidate_hits = f"{heavy_workdir}/summary/candidate_hits.tsv"
        resolved_references = f"{heavy_workdir}/summary/resolved-references.tsv"
        output = f"{heavy_workdir}/summary/candidate_anchors.tsv"
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "candidate_hits": candidate_hits,
        "resolved_references": resolved_references,
        "output": output,
        "methods": [
            "gff_attribute_exact_id_join",
            "protein_or_cds_id_join",
            "provider_alignment_fallback",
        ],
        "fail_closed_without_coordinates": True,
        "local_copy": True,
    }


def build_orthology_anchor_plan(*, run_scope: str, heavy_workdir: str) -> dict[str, Any]:
    summary_root = f"{heavy_workdir}/summary" if heavy_workdir else ""
    def sp(name: str) -> str:
        return f"{summary_root}/{name}" if summary_root else "not_applicable"
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "search_directions": [
            "canonical_A_to_target_B",
            "target_B_to_canonical_A",
            "domain_to_target_B",
            "target_B_to_reference_db",
        ],
        "anchor_confidence_classes": [
            "exact_gff_id",
            "reciprocal_best_hit",
            "transcript_to_genome",
            "protein_to_genome",
            "domain_only",
            "unanchored",
        ],
        "inputs": {
            "candidate_hits": sp("candidate_hits.tsv"),
            "candidate_anchors": sp("candidate_anchors.tsv"),
            "target_db_indexes": sp("target-db-indexes.tsv"),
            "query_ledger": "ledgers/query-ledger.tsv",
            "pathway_steps": "ledgers/pathway-steps.tsv",
        },
        "outputs": {
            "orthology_links": sp("orthology_links.tsv"),
            "anchor_ladder": sp("anchor_ladder.tsv"),
            "reciprocal_hits": sp("reciprocal_hits.tsv"),
            "summary": sp("orthology-anchor-summary.json"),
        },
        "fallback_methods": [
            "exact_gff_id",
            "reciprocal_best_hit",
            "transcript_to_genome",
            "protein_to_genome_miniprot",
            "domain_only",
            "unanchored",
        ],
        "claim_policy": "coordinates_required_for_cluster_claims",
        "local_copy": True,
    }


def build_reciprocal_search_plan(*, run_scope: str, heavy_workdir: str) -> dict[str, Any]:
    summary_root = f"{heavy_workdir}/summary" if heavy_workdir else ""
    def sp(name: str) -> str:
        return f"{summary_root}/{name}" if summary_root else "not_applicable"
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "search_directions": ["canonical_A_to_target_B", "target_B_to_canonical_A"],
        "inputs": {
            "candidate_hits": sp("candidate_hits.tsv"),
            "target_db_indexes": sp("target-db-indexes.tsv"),
            "query_fasta": f"{heavy_workdir}/inputs/queries/protein_queries.faa" if heavy_workdir else "not_applicable",
        },
        "outputs": {
            "reciprocal_hits": sp("reciprocal_hits.tsv"),
            "summary": sp("reciprocal-search-summary.json"),
            "raw_outputs": f"{heavy_workdir}/work/reciprocal-search" if heavy_workdir else "not_applicable",
        },
        "scoring_policy": {
            "reciprocal_best_hit_bonus": 0.18,
            "reciprocal_rank_decay": "rank_1_full_rank_5_low",
            "broad_family_penalty": "required_without_orthogonal_evidence",
            "raw_output_policy": "provider_workdir_only",
        },
        "local_copy": True,
    }


def build_pathway_completeness_plan(*, run_scope: str, heavy_workdir: str) -> dict[str, Any]:
    summary_root = f"{heavy_workdir}/summary" if heavy_workdir else ""
    def sp(name: str) -> str:
        return f"{summary_root}/{name}" if summary_root else "not_applicable"
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "inputs": {
            "pathway_steps": "ledgers/pathway-steps.tsv",
            "candidate_hits": sp("candidate_hits.tsv"),
            "orthology_links": sp("orthology_links.tsv"),
            "anchor_ladder": sp("anchor_ladder.tsv"),
            "neighborhood_hypotheses": sp("neighborhood_hypotheses.tsv"),
            "deferred_lanes": sp("deferred-lanes.json"),
        },
        "output": sp("pathway_completeness.tsv"),
        "statuses": [
            "supported",
            "partial",
            "missing",
            "ambiguous",
            "context_only",
            "deferred_by_budget",
        ],
        "budget_policy": (
            "defer_slow_lanes_with_deferred_by_budget_rows"
            if run_scope == "full_campaign_24h"
            else "mark_missing_or_partial_after_available_evidence"
        ),
        "local_copy": True,
    }


def build_neighborhood_plan(*, run_scope: str, heavy_workdir: str, window_kb: int = 100, window_genes: int = 10) -> dict[str, Any]:
    if run_scope not in HEAVY_RUN_SCOPES or not heavy_workdir:
        candidate_anchors = "not_applicable"
        outputs = {
            "cluster_neighborhoods": "not_applicable",
            "neighbor_annotations": "not_applicable",
            "domain_labels": "not_applicable",
            "visualization": "not_applicable",
        }
    else:
        candidate_anchors = f"{heavy_workdir}/summary/candidate_anchors.tsv"
        outputs = {
            "cluster_neighborhoods": f"{heavy_workdir}/summary/cluster_neighborhoods.tsv",
            "neighbor_annotations": f"{heavy_workdir}/summary/neighbor_annotations.tsv",
            "domain_labels": f"{heavy_workdir}/summary/domain_labels.tsv",
            "visualization": f"{heavy_workdir}/summary/neighborhood-visualization.html",
        }
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "candidate_anchors": candidate_anchors,
        "outputs": outputs,
        "window_kb": window_kb,
        "window_genes": window_genes,
        "enzyme_family_profiles": [
            "methyltransferase",
            "cytochrome_p450",
            "reductase",
            "glycosidase",
            "transporter",
            "transcription_factor_context",
        ],
        "claim_policy": "neighborhood_supported_not_product_validated",
        "local_copy": True,
    }


def expected_summary_artifacts(run_scope: str) -> list[str]:
    common = [
        "run_summary.json",
        "stage-progress.jsonl",
        "provenance.jsonl",
        "versions.json",
        "licenses.tsv",
        "dossier-manifest.json",
    ]
    heavy_common = [
        "toolcheck.json",
        "db-bootstrap-summary.json",
        "data-materialization-summary.json",
        "materialized-targets.tsv",
        "target-db-build-summary.json",
        "target-db-ledger.resolved.tsv",
        "target-db-indexes.tsv",
        "reference-import-summary.json",
        "resolved-references.tsv",
        "query-preflight.json",
        "decoy-preflight.json",
        "candidate-search-summary.json",
        "candidate_hits.tsv",
        "orthology_links.tsv",
        "anchor_ladder.tsv",
        "reciprocal_hits.tsv",
        "reciprocal-search-summary.json",
        "orthology-anchor-summary.json",
        "pathway_completeness.tsv",
        "pathway-completeness-summary.json",
        "evidence.jsonl",
        "evidence.sqlite",
        "claim-audit.jsonl",
        "search-cache-manifest.json",
    ]
    context = [
        "candidate_anchors.tsv",
        "cluster_neighborhoods.tsv",
        "neighbor_annotations.tsv",
        "domain_labels.tsv",
        "neighborhood_hypotheses.tsv",
        "neighborhood-score-summary.json",
        "neighborhood-visualization.html",
    ]
    workflow_class_outputs = [
        "workflow-class-summary.json",
        "claim-levels.tsv",
        "workflow-deferred-lanes.tsv",
        "isoform-ledger.tsv",
        "isoform-classification.tsv",
        "isoform-orfs.tsv",
        "isoform-domain-delta.tsv",
        "longread-qc.json",
        "transcriptome-build-ledger.tsv",
        "assembly-qc.tsv",
        "orf-ledger.tsv",
        "isoform-groups.tsv",
        "orthogroup-ledger.tsv",
        "paralog-homeolog-ledger.tsv",
        "copy-classification.tsv",
        "gene-tree-summary.tsv",
        "synteny-support.tsv",
        "expression-design.tsv",
        "expression-matrix-manifest.json",
        "tissue-specificity.tsv",
        "coexpression-modules.tsv",
        "assembly-ledger.tsv",
        "annotation-ledger.tsv",
        "coordinate-liftover-ledger.tsv",
        "comparative_neighborhoods.tsv",
        "pav-copy-number.tsv",
        "sv-ledger.tsv",
        "candidate_interval_sv.tsv",
        "graph-ledger.tsv",
        "graph_path_support.tsv",
        "singlecell-dataset-ledger.tsv",
        "spatial-domain-expression.tsv",
    ]
    if run_scope == "candidate_search":
        return common + heavy_common
    if run_scope == "full_campaign_24h":
        return common + heavy_common + context + workflow_class_outputs + ["deferred-lanes.json"]
    if run_scope in {"genome_context", "coexpression", "synteny", "full_public_mining", "full_campaign"}:
        return common + heavy_common + context + workflow_class_outputs
    return common


def build_query_resolution_plan(*, query_ledger: Path, heavy_workdir: str, embedded_query_fasta: Path | None = None) -> dict[str, Any]:
    records = []
    blockers = []
    warnings = []
    for row in read_tsv_rows(query_ledger):
        sequence_type = row.get("sequence_type", "")
        curation_status = row.get("curation_status", "")
        confidence = row.get("confidence", "")
        accession = row.get("resolved_accession", "")
        sequence_source = row.get("sequence_source", "")
        if curation_status == "context_only":
            action = "context_only_no_sequence"
        elif sequence_type == "domain_family":
            action = "domain_family_profile"
        elif accession == "workbook_sequence" or "embedded" in sequence_source:
            action = "use_embedded_query_fasta"
        elif accession and accession != "remote_resolve_required":
            action = "fetch_public_accession"
        else:
            action = "resolve_public_seed_before_run"
            if confidence == "high" and curation_status != "context_only":
                blockers.append(row.get("query_id", ""))
            elif confidence == "medium" and curation_status != "context_only":
                warnings.append(row.get("query_id", ""))
        records.append(
            {
                "query_id": row.get("query_id", ""),
                "query_name": row.get("query_name", ""),
                "sequence_type": sequence_type,
                "confidence": confidence,
                "curation_status": curation_status,
                "resolved_accession": accession,
                "sequence_source": sequence_source,
                "resolution_action": action,
                "citation": row.get("citation", ""),
            }
        )
    return {
        "schema_version": 1,
        "query_ledger": str(Path("ledgers") / query_ledger.name),
        "output_fasta": f"{heavy_workdir}/inputs/queries/protein_queries.faa" if heavy_workdir else "not_applicable",
        "embedded_query_fasta": str(Path("inputs") / embedded_query_fasta.name) if embedded_query_fasta else "",
        "records": records,
        "blocking_unresolved_query_ids": [value for value in blockers if value],
        "warning_unresolved_query_ids": [value for value in warnings if value],
        "notes": [
            "Resolve public seed sequences on the provider before candidate search.",
            "Embedded workbook query FASTA records are copied into the provider input directory before search.",
            "Domain-family and context-only records are not expected to contribute raw query FASTA sequences.",
        ],
    }


def build_decoy_plan(*, query_ledger: Path, run_scope: str) -> dict[str, Any]:
    records = []
    broad_family_query_ids = []
    high_risk_query_ids = []
    missing_negative_controls = []
    for row in read_tsv_rows(query_ledger):
        flag = row.get("decoy_or_broad_family_flag", "")
        negative_controls = row.get("negative_controls", "")
        risk = row.get("expected_false_positive_risk", "")
        enabled = flag == "true" or bool(negative_controls)
        if not enabled:
            continue
        query_id = row.get("query_id", "")
        if flag == "true":
            broad_family_query_ids.append(query_id)
        if risk == "high":
            high_risk_query_ids.append(query_id)
        if flag == "true" and not negative_controls:
            missing_negative_controls.append(query_id)
        records.append(
            {
                "query_id": query_id,
                "query_name": row.get("query_name", ""),
                "family_scope": row.get("family_scope", ""),
                "pathway_role": row.get("pathway_role", ""),
                "negative_controls": negative_controls,
                "decoy_or_broad_family_flag": flag,
                "expected_false_positive_risk": risk,
                "required_decoy_strategy": "family_decoy_panel" if flag == "true" else "paired_control_review",
                "score_penalty_policy": "broad-family hits require orthogonal evidence before product claims",
            }
        )
    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "query_ledger": str(Path("ledgers") / query_ledger.name),
        "records": records,
        "broad_family_query_ids": [value for value in broad_family_query_ids if value],
        "high_false_positive_risk_query_ids": [value for value in high_risk_query_ids if value],
        "missing_negative_control_query_ids": [value for value in missing_negative_controls if value],
        "enforcement": {
            "broad_family_product_claims": "forbidden_without_orthogonal_evidence",
            "decoy_hits": "reported_as_false_positive_risk_not_candidate_support",
            "claim_audit_rule": "broad_family_hit_does_not_prove_product_chemistry",
        },
    }


def build_run_economics(
    *,
    database_ledger: Path,
    cache_ledger: Path,
    query_resolution_plan: dict[str, Any],
    decoy_plan: dict[str, Any],
    run_scope: str,
    provider_class: str,
    heavy_workdir: str,
    image: str,
    missing_credentials: list[str],
    runtime_cap_hours: float = 24.0,
) -> dict[str, Any]:
    db_rows = read_tsv_rows(database_ledger)
    cache_rows = read_tsv_rows(cache_ledger)
    enabled_rows = [row for row in db_rows if database_row_enabled_for_scope(row, run_scope)]
    required_rows = [row for row in enabled_rows if row.get("priority") == "required"]
    optional_rows = [row for row in db_rows if row.get("run_gate") == "optional_max"]
    deferred_rows = [row for row in db_rows if row.get("run_gate") == "deferred_review"]

    required_free_space = []
    for row in cache_rows:
        if row.get("required") != "true":
            continue
        try:
            required_free_space.append(float(row.get("free_space_gb", "0")))
        except ValueError:
            continue

    cost_classes: dict[str, int] = {}
    prep_roi: dict[str, int] = {}
    for row in enabled_rows:
        cost_classes[row.get("cost_class", "unknown")] = cost_classes.get(row.get("cost_class", "unknown"), 0) + 1
        prep_roi[row.get("prep_roi", "unknown")] = prep_roi.get(row.get("prep_roi", "unknown"), 0) + 1

    placeholder_image = image.lower() in {"", "genecluster-runner:unbuilt", "placeholder", "todo", "tbd"} or image.endswith(":unbuilt")
    launch_blockers = []
    if missing_credentials:
        launch_blockers.extend(f"missing_env:{name}" for name in missing_credentials)
    if placeholder_image:
        launch_blockers.append("placeholder_runner_image")
    registry_auth_policy = build_registry_auth_policy(image)
    if registry_auth_policy["launch_blocker_if_missing"]:
        launch_blockers.append(f"image_pull_auth_missing:{registry_auth_policy['registry_host']}")
    launch_blockers.extend(f"unresolved_high_confidence_query:{qid}" for qid in query_resolution_plan.get("blocking_unresolved_query_ids", []))

    cost_controls = [
        "candidate_search uses only scope-gated high-ROI databases",
        "optional_max databases are deferred until curated/reference passes fail or ambiguity remains",
        "search raw outputs are cached by query/database/tool key on provider storage",
        "local sync remains summaries_only",
    ]
    if run_scope == "full_campaign_24h":
        cost_controls.append("full_campaign_24h finishes a complete dossier within 24h by deferring low-ROI lanes")

    return {
        "schema_version": 1,
        "run_scope": run_scope,
        "provider_class": provider_class,
        "heavy_workdir": heavy_workdir,
        "runtime_budget": build_runtime_policy(run_scope, runtime_cap_hours=runtime_cap_hours),
        "database_budget": {
            "required_enabled_count": len(required_rows),
            "optional_max_count": len(optional_rows),
            "deferred_review_count": len(deferred_rows),
            "enabled_cost_classes": cost_classes,
            "enabled_prep_roi": prep_roi,
            "high_roi_required_database_ids": [
                row["db_id"] for row in required_rows if row.get("prep_roi") == "high"
            ],
            "low_roi_deferred_database_ids": [
                row["db_id"] for row in optional_rows + deferred_rows if row.get("prep_roi") in {"low", "deferred"}
            ],
        },
        "cache_budget": {
            "volume_min_free_space_gb": max(required_free_space) if required_free_space else 0,
            "required_cache_roles": [row.get("cache_role", "") for row in cache_rows if row.get("required") == "true"],
            "search_result_cache_enabled": any(row.get("cache_role") == "search_result_cache" for row in cache_rows),
        },
        "query_budget": {
            "fetch_public_accession_count": len(
                [record for record in query_resolution_plan.get("records", []) if record.get("resolution_action") == "fetch_public_accession"]
            ),
            "blocking_unresolved_query_ids": query_resolution_plan.get("blocking_unresolved_query_ids", []),
            "warning_unresolved_query_ids": query_resolution_plan.get("warning_unresolved_query_ids", []),
            "decoy_or_broad_family_count": len(decoy_plan.get("records", [])),
            "high_false_positive_risk_query_ids": decoy_plan.get("high_false_positive_risk_query_ids", []),
        },
        "cost_controls": cost_controls,
        "launch_blockers": launch_blockers,
        "recommended_live_sequence": (
            [
                "local_lite smoke validation",
                "runpod_pod tool/cache/query/decoy preflight",
                "runpod_pod full_campaign_24h with --max-runtime-hours 24",
                "review complete dossier plus deferred_lane_manifest before any multi-day escalation",
            ]
            if run_scope == "full_campaign_24h"
            else [
                "local_lite smoke validation",
                "runpod_pod tool/cache/query/decoy preflight",
                "runpod_pod candidate_search",
                "review candidate/decoy/claim audit",
                "runpod_pod full_campaign only after candidate and genome-context gates pass",
            ]
        ),
    }


def build_tool_requirements() -> dict[str, Any]:
    rows = [
        ("blastp", "blastp", "BLAST+ protein search", "blastp -version", "open-data-with-terms"),
        ("tblastn", "tblastn", "Protein query against materialized nucleotide target DBs", "tblastn -version", "open-data-with-terms"),
        ("blastdbcmd", "blastdbcmd", "BLAST+ database inspection", "blastdbcmd -version", "open-data-with-terms"),
        ("makeblastdb", "makeblastdb", "BLAST+ custom DB build", "makeblastdb -version", "open-data-with-terms"),
        ("update_blastdb.pl", "update_blastdb.pl", "BLAST+ preformatted DB download on provider volumes", "update_blastdb.pl --help", "open-data-with-terms"),
        ("diamond", "diamond", "DIAMOND fast protein search", "diamond version", "permissive-code"),
        ("mmseqs", "mmseqs", "MMseqs2 high-throughput search", "mmseqs version", "copyleft-code"),
        ("hmmsearch", "hmmsearch", "HMMER/Pfam domain search", "hmmsearch -h", "permissive-code"),
        ("hmmscan", "hmmscan", "HMMER/Pfam protein domain scan", "hmmscan -h", "permissive-code"),
        ("hmmpress", "hmmpress", "HMMER pressed profile DB prep", "hmmpress -h", "permissive-code"),
        ("miniprot", "miniprot", "Spliced protein-to-genome anchoring fallback", "miniprot --version", "permissive-code"),
        ("datasets", "datasets", "NCBI Datasets metadata/reference fetch", "datasets version", "open-data-with-terms"),
        ("prefetch", "prefetch", "SRA provider-side staging", "prefetch --version", "open-data-with-terms"),
        ("fasterq-dump", "fasterq-dump", "SRA provider-side FASTQ conversion", "fasterq-dump --version", "open-data-with-terms"),
        ("minimap2", "minimap2", "Transcript/genome alignment support", "minimap2 --version", "permissive-code"),
        ("hisat2", "hisat2", "Short-read RNA-seq alignment for transcript-first campaigns", "hisat2 --version", "open-data-with-terms"),
        ("stringtie", "stringtie", "Genome-guided transcript assembly/merge support", "stringtie --version", "open-data-with-terms"),
        ("samtools", "samtools", "BAM sort/index and alignment inspection", "samtools --version", "permissive-code"),
        ("gffread", "gffread", "GFF/GTF transcript FASTA extraction", "gffread --version", "permissive-code"),
        ("TransDecoder.LongOrfs", "TransDecoder.LongOrfs", "Transcript ORF discovery for target proteome construction", "TransDecoder.LongOrfs --help", "open-data-with-terms"),
        ("TransDecoder.Predict", "TransDecoder.Predict", "Transcript protein prediction for target proteome construction", "TransDecoder.Predict --help", "open-data-with-terms"),
        ("nextflow", "nextflow", "Workflow execution and resume", "nextflow -version", "copyleft-code"),
        ("rpsblast", "rpsblast", "CDD/RPS-BLAST domain search", "rpsblast -version", "open-data-with-terms"),
        ("interproscan.sh", "interproscan.sh", "InterProScan annotation lane", "interproscan.sh --version", "open-data-with-terms"),
        ("plantismash", "plantismash", "plant BGC/context lane", "plantismash --version", "academic-free-or-web"),
        ("IsoQuant", "isoquant.py", "Long-read isoform discovery/quantification", "isoquant.py --version", "copyleft-code"),
        ("SQANTI3", "sqanti3_qc.py", "Long-read isoform QC", "sqanti3_qc.py --help", "copyleft-code"),
        ("Salmon", "salmon", "Expression quantification", "salmon --version", "copyleft-code"),
        ("OrthoFinder", "orthofinder", "Orthogroup/copy review", "orthofinder -h", "copyleft-code"),
        ("GENESPACE", "Rscript", "Plant synteny context via R package", "Rscript --version", "copyleft-code"),
        ("PGGB", "pggb", "Optional pangenome graph construction/import", "pggb --help", "copyleft-code"),
        ("ODGI", "odgi", "Optional pangenome graph inspection", "odgi version", "permissive-code"),
    ]
    return {
        "schema_version": 1,
        "required_tools": [
            {
                "tool": tool,
                "executable": executable,
                "required_for": required_for,
                "version_command": version_command,
                "license_class": license_class,
            }
            for tool, executable, required_for, version_command, license_class in rows
        ],
    }


def build_campaign_prompt(
    *,
    campaign: dict[str, Any],
    run_id: str,
    run_scope: str,
    provider: str,
    heavy_workdir: str,
    data_ledger: Path,
    query_ledger: Path,
    pathway_steps: Path,
    workflow_plan: dict[str, Any],
    lane_activation_plan: dict[str, Any],
    candidate_route_plan: dict[str, Any],
) -> str:
    data_rows = read_tsv_rows(data_ledger)
    query_rows = read_tsv_rows(query_ledger)
    step_rows = read_tsv_rows(pathway_steps)
    accessions = ", ".join(row.get("accession", "") for row in data_rows if row.get("accession"))
    target_species = ", ".join(sorted({row.get("organism", "") for row in data_rows if row.get("organism")}))
    source_species = ", ".join(sorted({row.get("source_organism", "") for row in query_rows if row.get("source_organism")}))
    query_names = ", ".join(row.get("query_name", "") for row in query_rows[:12] if row.get("query_name"))
    step_ids = ", ".join(row.get("pathway_step_id", "") for row in step_rows if row.get("pathway_step_id"))
    data_lines = "\n".join(
        f"- `{row.get('dataset_id', '')}`: `{row.get('accession', '') or row.get('source_url', '')}`; "
        f"role `{row.get('data_role', '')}`; organism `{row.get('organism', '')}`; technology `{row.get('technology', '')}`"
        for row in data_rows
    ) or "- see `ledgers/data-ledger.tsv`"
    activated = ", ".join(lane_activation_plan.get("activated_lanes", [])) or "none"
    deferred = ", ".join(lane_activation_plan.get("deferred_lanes", [])) or "none"
    blocked = ", ".join(lane_activation_plan.get("blocked_lanes", [])) or "none"
    workflow_classes = ", ".join(row["workflow_class"] for row in workflow_plan.get("workflow_classes", []))
    route_blockers = ", ".join(candidate_route_plan.get("strict_scientific_blockers", [])) or "none"
    return f"""# GeneCluster Campaign Prompt

You are executing a BioSymphony GeneCluster campaign from a validated launch bundle. Do not download raw SRA/FASTQ/genome/database artifacts to the repo. Heavy data, indexes, search outputs, and workflow work directories stay under the configured provider workdir.

Campaign id: `{campaign.get('campaign_id', '')}`
Run id: `{run_id}`
Run scope: `{run_scope}`
Provider class: `{provider}`
Heavy workdir: `{heavy_workdir or 'not_applicable'}`
Target pathway: `{campaign.get('target_pathway', '')}`
Target species/datasets: `{target_species or campaign.get('organism', '')}`
Canonical/source species from query ledger: `{source_species or 'public canonical proteins/literature seeds'}`
Accessions/resources to resolve on provider only: `{accessions}`

Known data inputs from `ledgers/data-ledger.tsv`:
{data_lines}

Input-first rule:
Before asking the operator for accessions, links, query lists, or resource slots, run `genecluster_input_audit.py --launch-manifest launch-manifest.json --require-known-data --interview-mode standard` and read `ledgers/data-ledger.tsv`, `ledgers/query-ledger.tsv`, and the generated audit. Ask only generated `intake_interview.questions` whose answers are not already present. Do not ask for links or accessions already present in the ledgers. If the operator says "skip and go" or "use defaults", switch to `--interview-mode skip`, record assumptions, and continue only within the resulting claim limits.

Primary scientific task:
Find candidate target-species genes/proteins for the pathway steps `{step_ids}` using the A-to-B ladder: canonical proteins from source species A -> target species B search -> reciprocal/orthology scoring -> genome anchoring -> neighborhood capture -> pathway completeness and reviewable evidence package.

Workflow-class plan:
- Available classes: `{workflow_classes}`
- Activated lanes: `{activated}`
- Deferred lanes: `{deferred}`
- Blocked lanes: `{blocked}`
- Treat activation gates as part of the scientific contract. Do not silently skip a blocked/deferred lane; record it in `workflow-deferred-lanes.tsv` or `deferred-lanes.json`.

Candidate route plan:
- Primary scientific route: `{candidate_route_plan.get('primary_route', '')}`
- Current runner route: `{candidate_route_plan.get('implemented_runner_route', '')}`
- Science readiness: `{candidate_route_plan.get('science_readiness', '')}`
- Strict scientific blockers: `{route_blockers}`
- Direct genome `tblastn` policy: `{candidate_route_plan.get('direct_genome_tblastn_policy', '')}`
- If transcript evidence exists, do not jump straight to raw-genome `tblastn` as the primary route. Transcript/ORF/protein candidates come first, then splice-aware genome anchoring and neighborhood extraction. Direct genome search is rescue/support evidence unless transcript evidence is unavailable.

Required execution behavior:
- Use provider-local BLAST/DIAMOND/MMseqs/HMMER; do not run NCBI remote BLAST batch jobs.
- Build target BLAST/DIAMOND/MMseqs/miniprot indexes only under provider DB/cache paths.
- Use `miniprot` for protein-to-genome fallback when protein/GFF IDs do not anchor candidates.
- Pull back summaries only: candidate tables, ledgers, provenance, versions, claim audit, pathway completeness, and dossier artifacts.
- Keep cluster claims gated: transcript-only, broad CYP/OMT/reductase, or domain-only evidence cannot prove physical clusters or product chemistry.

Initial query context:
{query_names or 'see ledgers/query-ledger.tsv'}

Outputs expected from the execution worker:
- `target-db-build-summary.json`, `target-db-ledger.resolved.tsv`, `target-db-indexes.tsv`
- `candidate_hits.tsv`, `orthology_links.tsv`, `anchor_ladder.tsv`, `reciprocal_hits.tsv`
- `candidate_anchors.tsv`, `cluster_neighborhoods.tsv`, `neighbor_annotations.tsv`, `domain_labels.tsv`, `neighborhood_hypotheses.tsv`
- `pathway_completeness.tsv`, `claim-audit.jsonl`, `evidence.jsonl`, `provenance.jsonl`, `versions.json`, `licenses.tsv`, `dossier-manifest.json`
- workflow class summaries including isoform, transcriptome-only, copy, expression, comparative, PAV/SV, graph, and single-cell/spatial ledgers when activated or explicitly deferred

Before live execution, validate this bundle with `genecluster_preflight.py --launch-manifest launch-manifest.json` and `genecluster_route_audit.py --launch-manifest launch-manifest.json`. Before claiming a transcript-first scientific run is ready, the strict route audit `genecluster_route_audit.py --launch-manifest launch-manifest.json --require-transcript-first` must pass. Credentials, volume metadata, image digest, and non-placeholder provider paths must be supplied through environment/secret stores, not repo files.
"""


def build_runpod_payload(
    *,
    run_id: str,
    run_scope: str,
    heavy_workdir: str,
    image: str,
    command: list[str],
) -> dict[str, Any]:
    network_volume_id = os.environ.get("GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID") or os.environ.get("RUNPOD_VOLUME_ID") or "env:GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID"
    datacenter = os.environ.get("GENECLUSTER_RUNPOD_DATACENTER") or os.environ.get("RUNPOD_DC_ID") or "env:GENECLUSTER_RUNPOD_DATACENTER"
    image_digest = image.split("@", 1)[1] if "@sha256:" in image else "unresolved"
    return {
        "schema_version": 1,
        "provider_class": "runpod_pod",
        "run_id": run_id,
        "run_scope": run_scope,
        "network_volume_id": network_volume_id,
        "datacenter": datacenter,
        "mount_path": "/workspace",
        "image": image,
        "image_digest": image_digest,
        "start_script": "provider/runpod-docker-start.sh",
        "env_var_names": [
            "RUNPOD_API_KEY",
            "GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID",
            "GENECLUSTER_RUNPOD_DATACENTER",
            "GENECLUSTER_DB_CACHE_ROOT",
            "GENECLUSTER_SEARCH_CACHE_ROOT",
            "NXF_HOME",
            "GENECLUSTER_RUNPOD_IDLE_SECONDS",
            *RUNPOD_REGISTRY_AUTH_ENV_NAMES,
            *RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES,
        ],
        "heavy_workdir": heavy_workdir,
        "db_cache_root": "/workspace/genecluster/db-cache",
        "summary_dir": f"{heavy_workdir}/summary",
        "command": command,
        "pod_lifecycle_policy": {
            "self_stop_on_completion": False,
            "operator_side_cleanup_required": True,
            "provider_api_key_inside_pod": False,
            "idle_after_completion_seconds": 900,
            "avoid_restart_loop": True,
            "start_command_holds_for_operator_cleanup": True,
            "watch_runtime_uptime_seconds_required": True,
            "runtime_null_timeout_seconds": 600,
            "status_file": f"{heavy_workdir}/.genecluster_status",
            "stop_not_delete_until_summary_verified": True,
            "delete_only_after_operator_review": True,
            "cleanup_order": [
                "write final run_summary.json and dossier-manifest.json",
                "hold the pod briefly for operator-side summary sync and cleanup",
                "sync summaries through configured summary transport",
                "delete pod only after summaries and remote artifact boundaries validate",
            ],
        },
        "runpod_api_policy": {
            "preferred_launch": "template_or_rest_api",
            "rest_endpoint": "https://rest.runpod.io/v1/pods",
            "mcp_wrapper_limitations": [
                "some RunPod MCP create-pod schemas do not expose computeType",
                "some RunPod MCP create-pod schemas do not expose networkVolumeId",
                "some RunPod MCP create-pod schemas do not expose dockerStartCmd",
            ],
            "status_checks": [
                "desiredStatus alone is not sufficient",
                "runtime must be non-null after provisioning timeout",
                "runtime.uptimeInSeconds must advance before treating the run as started",
            ],
        },
        "image_policy": {
            "digest_pinned_required_for_execution_ready": True,
            "first_boot_mamba_install": "emergency_only",
            "first_boot_install_allowed_for_standard_launch": False,
            "tool_install_strategy": "baked_image_required",
            "requires_openjdk_for_nextflow": True,
            "required_boot_tools": [
                "blastp",
                "tblastn",
                "blastdbcmd",
                "makeblastdb",
                "update_blastdb.pl",
                "diamond",
                "mmseqs",
                "hmmsearch",
                "hmmscan",
                "hmmpress",
                "miniprot",
                "datasets",
                "prefetch",
                "fasterq-dump",
                "minimap2",
                "nextflow",
                "python3",
                "sqlite3",
                "curl",
            ],
        },
        "registry_auth_policy": build_registry_auth_policy(image),
        "db_bootstrap_policy": {
            "bootstrap_mode": "verify_or_provider_download_only",
            "required_database_fail_closed": True,
            "allow_large_downloads_default": False,
            "first_run_recommendation": "pre-stage required curated DBs or run db-bootstrap with an explicit provider-only allow-large-downloads override",
        },
        "summary_sync_policy": {
            "mode": "pull_summaries_only",
            "preferred_transport": "runpod_s3_or_configured_summary_endpoint",
            "fallback_transport": "short_lived_http_pull_pod",
            "avoid_capacity_dependent_pull_pod_when_s3_available": True,
            "s3_endpoint_template": "https://s3api-{datacenter}.runpod.io",
            "http_pull_pod_lifetime_minutes": 5,
            "include": [
                "run_summary.json",
                "db-bootstrap-summary.json",
                "data-materialization-summary.json",
                "materialized-targets.tsv",
                "target-db-build-summary.json",
                "target-db-ledger.resolved.tsv",
                "target-db-indexes.tsv",
                "reference-import-summary.json",
                "candidate_hits.tsv",
                "candidate_anchors.tsv",
                "orthology_links.tsv",
                "anchor_ladder.tsv",
                "reciprocal_hits.tsv",
                "reciprocal-search-summary.json",
                "orthology-anchor-summary.json",
                "cluster_neighborhoods.tsv",
                "neighbor_annotations.tsv",
                "domain_labels.tsv",
                "neighborhood_hypotheses.tsv",
                "neighborhood-score-summary.json",
                "pathway_completeness.tsv",
                "pathway-completeness-summary.json",
                "workflow-class-summary.json",
                "claim-levels.tsv",
                "workflow-deferred-lanes.tsv",
                "isoform-ledger.tsv",
                "isoform-classification.tsv",
                "isoform-orfs.tsv",
                "isoform-domain-delta.tsv",
                "longread-qc.json",
                "transcriptome-build-ledger.tsv",
                "assembly-qc.tsv",
                "orf-ledger.tsv",
                "isoform-groups.tsv",
                "orthogroup-ledger.tsv",
                "paralog-homeolog-ledger.tsv",
                "copy-classification.tsv",
                "gene-tree-summary.tsv",
                "synteny-support.tsv",
                "expression-design.tsv",
                "expression-matrix-manifest.json",
                "tissue-specificity.tsv",
                "coexpression-modules.tsv",
                "assembly-ledger.tsv",
                "annotation-ledger.tsv",
                "coordinate-liftover-ledger.tsv",
                "comparative_neighborhoods.tsv",
                "pav-copy-number.tsv",
                "sv-ledger.tsv",
                "candidate_interval_sv.tsv",
                "graph-ledger.tsv",
                "graph_path_support.tsv",
                "singlecell-dataset-ledger.tsv",
                "spatial-domain-expression.tsv",
                "evidence.jsonl",
                "evidence.sqlite",
                "claim-audit.jsonl",
                "decoy-preflight.json",
                "search-cache-manifest.json",
                "neighborhood-visualization.html",
                "provenance.jsonl",
                "versions.json",
                "licenses.tsv",
                "dossier-manifest.json",
            ],
            "exclude": ["*.sra", "*.fastq*", "*.bam", "*.sam", "*.cram", "*.dmnd", "work/**", "databases/**"],
        },
        "artifact_boundaries": {
            "large_artifacts": "provider_workdir_only",
            "local_sync": "summaries_only",
            "raw_outputs": f"{heavy_workdir}/work",
        },
    }


def build_artifact_pull_manifest(
    *,
    run_id: str,
    provider: str,
    heavy_workdir: str,
    runpod_payload: dict[str, Any],
) -> dict[str, Any]:
    summary_policy = runpod_payload.get("summary_sync_policy", {})
    include = [
        {"path": rel, "required": rel in {"run_summary.json", "candidate_hits.tsv", "dossier-manifest.json"}}
        for rel in summary_policy.get("include", [])
    ]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "provider_class": provider,
        "mode": "pull_summaries_only",
        "remote_summary_dir": f"{heavy_workdir}/summary" if heavy_workdir else "summary",
        "preferred_transport": summary_policy.get("preferred_transport", ""),
        "fallback_transport": summary_policy.get("fallback_transport", ""),
        "s3_endpoint_template": summary_policy.get("s3_endpoint_template", ""),
        "include": include,
        "exclude": summary_policy.get("exclude", []),
        "max_file_bytes": 10 * 1024 * 1024,
        "max_total_bytes": 100 * 1024 * 1024,
        "checksum_mode": "require_sha256_after_pull",
        "raw_artifact_policy": "forbid",
        "local_destination_policy": {
            "default_root": f".runtime/genecluster-summary-pulls/{run_id}",
            "repo_paths_allowed": ".runtime only",
            "must_remain_summary_only": True,
        },
        "report_path": "artifact-pull-report.json",
    }


def write_provider_scripts(provider_dir: Path, *, heavy_workdir: str, command: list[str]) -> None:
    provider_dir.mkdir(parents=True, exist_ok=True)
    command_text = " ".join(command)
    status_file = f"{heavy_workdir}/.genecluster_status" if heavy_workdir else "/workspace/genecluster/runs/<run_id>/.genecluster_status"
    scripts = {
        "runpod-docker-start.sh": f"""#!/usr/bin/env bash
set -euo pipefail
BUNDLE_DIR="${{GENECLUSTER_BUNDLE_DIR:-$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)}}"
STATUS_FILE="${{GENECLUSTER_STATUS_FILE:-{status_file}}}"
mkdir -p "$(dirname "$STATUS_FILE")"
date -u +"%Y-%m-%dT%H:%M:%SZ start" > "$STATUS_FILE"

genecluster_closeout() {{
  local exit_code="$1"
  date -u +"%Y-%m-%dT%H:%M:%SZ exit_code=$exit_code" >> "$STATUS_FILE" || true
  local idle_seconds="${{GENECLUSTER_RUNPOD_IDLE_SECONDS:-900}}"
  if [[ "$idle_seconds" =~ ^[0-9]+$ ]] && (( idle_seconds > 0 )); then
    date -u +"%Y-%m-%dT%H:%M:%SZ awaiting_operator_cleanup idle_seconds=$idle_seconds" >> "$STATUS_FILE" || true
    sleep "$idle_seconds"
  fi
}}

trap 'code=$?; genecluster_closeout "$code"; exit "$code"' EXIT
cd "$BUNDLE_DIR"
{command_text}
""",
        "local-full.sh": f"""#!/usr/bin/env bash
set -euo pipefail
BUNDLE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
: "${{GENECLUSTER_LOCAL_FULL_WORKDIR:={heavy_workdir or '/ABSOLUTE/PATH/OUTSIDE/REPO/genecluster-runs'}}}"
mkdir -p "$GENECLUSTER_LOCAL_FULL_WORKDIR"
cd "$BUNDLE_DIR"
{command_text}
""",
        "ssh-hpc.sh": f"""#!/usr/bin/env bash
set -euo pipefail
BUNDLE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
: "${{GENECLUSTER_SSH_HOST:?set remote SSH host}}"
: "${{GENECLUSTER_SSH_WORKDIR:={heavy_workdir or '/remote/genecluster/runs/<run_id>'}}}"
ssh "$GENECLUSTER_SSH_HOST" "mkdir -p '$GENECLUSTER_SSH_WORKDIR'"
rsync -az --delete "$BUNDLE_DIR"/ "$GENECLUSTER_SSH_HOST:$GENECLUSTER_SSH_WORKDIR"/
ssh "$GENECLUSTER_SSH_HOST" "cd '$GENECLUSTER_SSH_WORKDIR' && {command_text}"
""",
        "cloud-vm.sh": f"""#!/usr/bin/env bash
set -euo pipefail
BUNDLE_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")/.." && pwd)"
: "${{GENECLUSTER_CLOUD_VM:?set cloud VM target}}"
: "${{GENECLUSTER_CLOUD_WORKDIR:={heavy_workdir or '/mnt/genecluster/runs/<run_id>'}}}"
ssh "$GENECLUSTER_CLOUD_VM" "mkdir -p '$GENECLUSTER_CLOUD_WORKDIR'"
rsync -az --delete "$BUNDLE_DIR"/ "$GENECLUSTER_CLOUD_VM:$GENECLUSTER_CLOUD_WORKDIR"/
ssh "$GENECLUSTER_CLOUD_VM" "cd '$GENECLUSTER_CLOUD_WORKDIR' && {command_text}"
""",
    }
    for name, text in scripts.items():
        path = provider_dir / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)


def check_heavy_workdir(provider: str, run_scope: str, heavy_workdir: str, repo_root: Path) -> list[str]:
    errors: list[str] = []
    config = PROVIDER_CONFIGS[provider]
    scope = RUN_SCOPE_CONFIGS[run_scope]
    if provider == "local_lite" and scope["heavy_compute"]:
        errors.append("local_lite cannot run heavy scopes")
    if config["requires_heavy_workdir"] and scope["heavy_compute"] and not heavy_workdir:
        errors.append(f"{provider} requires a heavy_workdir")
    if heavy_workdir and is_object_store_uri(heavy_workdir):
        errors.append("heavy_workdir must be a mounted filesystem path, not object storage")
    elif heavy_workdir and not heavy_workdir.startswith(("/workspace/", "/runpod-volume/")):
        path = Path(heavy_workdir)
        if not path.is_absolute():
            errors.append("local/generic heavy_workdir must be an absolute path")
        elif path_is_under(path, repo_root):
            errors.append("heavy_workdir must not be under the repo root")
    return errors


def build_launch_bundle(
    *,
    campaign_path: Path,
    out: Path,
    provider_class: str,
    run_scope: str,
    repo_root: Path,
    heavy_workdir: str = "",
    run_id: str = "",
    allow_local_full: bool = False,
    image: str = "genecluster-runner:unbuilt",
    runtime_cap_hours: float = 24.0,
    allow_provider_large_downloads: bool = False,
) -> Path:
    provider = normalize_provider(provider_class)
    run_scope = normalize_run_scope(run_scope)
    if provider not in PROVIDER_CONFIGS:
        raise ValueError(f"unknown provider_class: {provider_class}")
    if run_scope not in RUN_SCOPE_CONFIGS:
        raise ValueError(f"unknown run_scope: {run_scope}")

    campaign_result = validate_campaign_manifest(campaign_path)
    if not campaign_result["ok"]:
        raise ValueError(f"campaign preflight failed: {campaign_result['errors']}")

    config = PROVIDER_CONFIGS[provider]
    if run_scope not in config["supported_scopes"]:
        raise ValueError(f"{provider} does not support run_scope {run_scope}")
    if config["requires_explicit_opt_in"] and not allow_local_full:
        raise ValueError(f"{provider} requires explicit opt-in")

    campaign = load_json(campaign_path)
    run_id = slug(run_id or f"{campaign['campaign_id']}-{run_scope}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    if not heavy_workdir:
        heavy_workdir = str(config["default_heavy_workdir"]).format(run_id=run_id)

    repo_root = repo_root.resolve()
    errors = check_heavy_workdir(provider, run_scope, heavy_workdir, repo_root)
    if errors:
        raise ValueError("; ".join(errors))

    out.mkdir(parents=True, exist_ok=True)
    bundle_dir = out.resolve()
    ledgers_dir = bundle_dir / "ledgers"
    inputs_dir = bundle_dir / "inputs"
    provider_dir = bundle_dir / "provider"
    remote_dir = bundle_dir / "remote"
    ledgers_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    provider_dir.mkdir(parents=True, exist_ok=True)
    remote_dir.mkdir(parents=True, exist_ok=True)

    example_dir = campaign_path.parent
    source_ledgers = {
        "campaign": campaign_path,
        "data_ledger": example_dir / "data-ledger.tsv",
        "query_ledger": example_dir / "query-ledger.tsv",
        "resource_ledger": example_dir / "resource-ledger.tsv",
        "project_goals": example_dir / "project-goals.yaml",
        "pathway_steps": example_dir / "pathway-steps.tsv",
        "database_ledger": example_dir / "database-ledger.tsv",
        "cache_ledger": example_dir / "cache-ledger.tsv",
    }
    missing_sources = [str(path) for path in source_ledgers.values() if not path.exists()]
    if missing_sources:
        raise ValueError(f"missing required campaign contract files: {', '.join(missing_sources)}")

    bundled_ledgers: dict[str, Path] = {}
    for name, source in source_ledgers.items():
        target_name = "campaign-manifest.json" if name == "campaign" else source.name
        target = ledgers_dir / target_name
        shutil.copyfile(source, target)
        bundled_ledgers[name] = target

    bundled_query_fasta: Path | None = None
    query_fasta_value = str(campaign.get("query_set", {}).get("sequence_fasta", ""))
    if query_fasta_value:
        query_fasta_name = Path(query_fasta_value).name
        query_fasta_candidates = [
            (example_dir / query_fasta_value).resolve(),
            (example_dir / query_fasta_name).resolve(),
            (example_dir.parent / "inputs" / query_fasta_name).resolve(),
        ]
        query_fasta_source = next((path for path in query_fasta_candidates if path.exists()), None)
        if query_fasta_source is not None:
            bundled_query_fasta = inputs_dir / query_fasta_source.name
            shutil.copyfile(query_fasta_source, bundled_query_fasta)

    missing_credentials = [
        env_name for env_name in config["required_env"]
        if not os.environ.get(env_name)
    ]

    stage_flags = remote_stage_flags(
        run_scope,
        runtime_cap_hours=runtime_cap_hours,
        allow_provider_large_downloads=allow_provider_large_downloads,
    )
    runner_command = [
        "python3",
        "remote/genecluster_remote_runner.py",
        "--launch-manifest",
        "launch-manifest.json",
        *stage_flags,
    ]

    search_plan = build_search_plan(
        run_scope=run_scope,
        heavy_workdir=heavy_workdir,
        database_ledger=bundled_ledgers["database_ledger"],
        query_ledger=bundled_ledgers["query_ledger"],
        runtime_cap_hours=runtime_cap_hours,
    )
    search_plan_path = bundle_dir / "search-plan.json"
    write_json(search_plan_path, search_plan)

    stage_contract_path = bundle_dir / "stage-contract.json"
    write_json(
        stage_contract_path,
        build_stage_contract(
            run_id=run_id,
            provider_class=provider,
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
            runtime_cap_hours=runtime_cap_hours,
            stage_flags=stage_flags,
        ),
    )

    db_bootstrap_plan_path = bundle_dir / "db-bootstrap-plan.json"
    write_json(
        db_bootstrap_plan_path,
        build_db_bootstrap_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
            database_ledger=bundled_ledgers["database_ledger"],
        ),
    )

    data_materialization_plan_path = bundle_dir / "data-materialization-plan.json"
    write_json(
        data_materialization_plan_path,
        build_data_materialization_plan(
            provider=provider,
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
            data_ledger=bundled_ledgers["data_ledger"],
        ),
    )

    target_db_plan = build_target_db_plan(
        run_scope=run_scope,
        heavy_workdir=heavy_workdir,
        data_ledger=bundled_ledgers["data_ledger"],
    )
    target_db_plan_path = bundle_dir / "target-db-plan.json"
    write_json(target_db_plan_path, target_db_plan)

    candidate_route_plan = build_candidate_route_plan(
        run_scope=run_scope,
        provider_class=provider,
        heavy_workdir=heavy_workdir,
        data_ledger=bundled_ledgers["data_ledger"],
        query_ledger=bundled_ledgers["query_ledger"],
        target_db_plan=target_db_plan,
        runtime_cap_hours=runtime_cap_hours,
    )
    candidate_route_plan_path = bundle_dir / "candidate-route-plan.json"
    write_json(candidate_route_plan_path, candidate_route_plan)

    reference_import_plan_path = bundle_dir / "reference-import-plan.json"
    write_json(
        reference_import_plan_path,
        build_reference_import_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
            data_ledger=bundled_ledgers["data_ledger"],
        ),
    )

    orthology_anchor_plan_path = bundle_dir / "orthology-anchor-plan.json"
    write_json(
        orthology_anchor_plan_path,
        build_orthology_anchor_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
        ),
    )

    reciprocal_search_plan_path = bundle_dir / "reciprocal-search-plan.json"
    write_json(
        reciprocal_search_plan_path,
        build_reciprocal_search_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
        ),
    )

    pathway_completeness_plan_path = bundle_dir / "pathway-completeness-plan.json"
    write_json(
        pathway_completeness_plan_path,
        build_pathway_completeness_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
        ),
    )

    anchor_map_plan_path = bundle_dir / "anchor-map-plan.json"
    write_json(
        anchor_map_plan_path,
        build_anchor_map_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
        ),
    )

    neighborhood_extract_plan_path = bundle_dir / "neighborhood-extract-plan.json"
    write_json(
        neighborhood_extract_plan_path,
        build_neighborhood_plan(
            run_scope=run_scope,
            heavy_workdir=heavy_workdir,
        ),
    )

    query_resolution_plan = build_query_resolution_plan(
        query_ledger=bundled_ledgers["query_ledger"],
        heavy_workdir=heavy_workdir,
        embedded_query_fasta=bundled_query_fasta,
    )
    query_resolution_plan_path = bundle_dir / "query-resolution-plan.json"
    write_json(query_resolution_plan_path, query_resolution_plan)

    decoy_plan = build_decoy_plan(
        query_ledger=bundled_ledgers["query_ledger"],
        run_scope=run_scope,
    )
    decoy_plan_path = bundle_dir / "decoy-plan.json"
    write_json(decoy_plan_path, decoy_plan)

    run_economics_path = bundle_dir / "run-economics.json"
    write_json(
        run_economics_path,
        build_run_economics(
            database_ledger=bundled_ledgers["database_ledger"],
            cache_ledger=bundled_ledgers["cache_ledger"],
            query_resolution_plan=query_resolution_plan,
            decoy_plan=decoy_plan,
            run_scope=run_scope,
            provider_class=provider,
            heavy_workdir=heavy_workdir,
            image=image,
            missing_credentials=missing_credentials,
            runtime_cap_hours=runtime_cap_hours,
        ),
    )

    tool_requirements_path = bundle_dir / "tool-requirements.json"
    write_json(tool_requirements_path, build_tool_requirements())

    workflow_class_plan = build_workflow_class_plan(
        run_scope=run_scope,
        provider_class=provider,
        data_ledger=bundled_ledgers["data_ledger"],
        query_ledger=bundled_ledgers["query_ledger"],
        runtime_cap_hours=runtime_cap_hours,
    )
    workflow_class_plan_path = bundle_dir / "workflow-class-plan.json"
    write_json(workflow_class_plan_path, workflow_class_plan)

    lane_activation_plan = build_lane_activation_plan(workflow_class_plan)
    lane_activation_plan_path = bundle_dir / "lane-activation-plan.json"
    write_json(lane_activation_plan_path, lane_activation_plan)

    evidence_escalation_plan_path = bundle_dir / "evidence-escalation-plan.json"
    write_json(evidence_escalation_plan_path, build_evidence_escalation_plan(run_scope=run_scope))

    claim_levels_path = bundle_dir / "claim-levels.tsv"
    write_tsv_file(
        claim_levels_path,
        CLAIM_LEVEL_ROWS,
        ["claim_level", "allowed_statement", "required_evidence", "forbidden_overclaim", "review_gate"],
    )

    workflow_deferred_lanes_path = bundle_dir / "workflow-deferred-lanes.tsv"
    write_tsv_file(
        workflow_deferred_lanes_path,
        build_workflow_deferred_rows(workflow_class_plan),
        ["workflow_class", "deferred_status", "reason", "trigger_to_reactivate", "claim_effect", "review_status"],
    )

    campaign_prompt_path = bundle_dir / "campaign-prompt.md"
    campaign_prompt_path.write_text(
        build_campaign_prompt(
            campaign=campaign,
            run_id=run_id,
            run_scope=run_scope,
            provider=provider,
            heavy_workdir=heavy_workdir,
            data_ledger=bundled_ledgers["data_ledger"],
            query_ledger=bundled_ledgers["query_ledger"],
            pathway_steps=bundled_ledgers["pathway_steps"],
            workflow_plan=workflow_class_plan,
            lane_activation_plan=lane_activation_plan,
            candidate_route_plan=candidate_route_plan,
        ),
        encoding="utf-8",
    )

    runpod_payload_path = provider_dir / "runpod-pod.json"
    runpod_payload = build_runpod_payload(
        run_id=run_id,
        run_scope=run_scope,
        heavy_workdir=heavy_workdir,
        image=image,
        command=runner_command,
    )
    write_json(runpod_payload_path, runpod_payload)
    artifact_pull_manifest_path = bundle_dir / "artifact_pull.yaml"
    artifact_pull_manifest_path.write_text(
        json.dumps(
            build_artifact_pull_manifest(
                run_id=run_id,
                provider=provider,
                heavy_workdir=heavy_workdir,
                runpod_payload=runpod_payload,
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_provider_scripts(provider_dir, heavy_workdir=heavy_workdir, command=runner_command)

    provider_payload_path = provider_dir / provider_payload_name(provider)

    scope = RUN_SCOPE_CONFIGS[run_scope]
    expected_artifacts = [
        {"path": rel, "local_policy": "summary_only"}
        for rel in expected_summary_artifacts(run_scope)
    ]
    preflight_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_preflight.py"
    input_audit_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_input_audit.py"
    route_audit_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_route_audit.py"
    contract_self_check_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_contract_self_check.py"
    stage_contract_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_stage_contract.py"
    sra_runinfo_script = repo_root / "skills" / "biosymphony" / "scripts" / "genecluster_sra_runinfo.py"
    launch_manifest_path = out / "launch-manifest.json"
    validation_commands = [
        f"python3 {input_audit_script} "
        f"--launch-manifest {launch_manifest_path} "
        f"--require-known-data --interview-mode standard "
        f"--out {out / 'input-audit.json'} --markdown-out {out / 'input-audit.md'}",
        f"python3 {sra_runinfo_script} "
        f"--data-ledger {bundled_ledgers['data_ledger']} "
        f"--out-dir {out / 'sra-runinfo'}",
        f"python3 {preflight_script} "
        f"--campaign {bundled_ledgers['campaign']} "
        f"--project-goals {bundled_ledgers['project_goals']} "
        f"--pathway-steps {bundled_ledgers['pathway_steps']} "
        f"--data-ledger {bundled_ledgers['data_ledger']} "
        f"--query-ledger {bundled_ledgers['query_ledger']} "
        f"--resource-ledger {bundled_ledgers['resource_ledger']} "
        f"--database-ledger {bundled_ledgers['database_ledger']} "
        f"--cache-ledger {bundled_ledgers['cache_ledger']}",
        f"python3 {preflight_script} "
        f"--db-bootstrap-plan {db_bootstrap_plan_path} "
        f"--data-materialization-plan {data_materialization_plan_path} "
        f"--target-db-plan {target_db_plan_path} "
        f"--candidate-route-plan {candidate_route_plan_path} "
        f"--reference-import-plan {reference_import_plan_path} "
        f"--anchor-map-plan {anchor_map_plan_path} "
        f"--neighborhood-extract-plan {neighborhood_extract_plan_path} "
        f"--orthology-anchor-plan {orthology_anchor_plan_path} "
        f"--reciprocal-search-plan {reciprocal_search_plan_path} "
        f"--pathway-completeness-plan {pathway_completeness_plan_path} "
        f"--query-resolution-plan {query_resolution_plan_path} "
        f"--decoy-plan {decoy_plan_path} --run-economics {run_economics_path} "
        f"--workflow-class-plan {workflow_class_plan_path} "
        f"--lane-activation-plan {lane_activation_plan_path} "
        f"--evidence-escalation-plan {evidence_escalation_plan_path} "
        f"--claim-levels {claim_levels_path} --workflow-deferred-lanes {workflow_deferred_lanes_path} "
        f"--search-plan {search_plan_path} --tool-requirements {tool_requirements_path} "
        f"--provider-payload {provider_payload_path} "
        f"--artifact-pull-manifest {artifact_pull_manifest_path}",
        f"python3 {route_audit_script} --launch-manifest {launch_manifest_path}",
        f"python3 {preflight_script} --launch-manifest {launch_manifest_path}",
        f"python3 {stage_contract_script} --stage-contract {stage_contract_path}",
        f"python3 {stage_contract_script} --stage-contract {stage_contract_path} "
        f"--artifact-root <returned-summary-dir> --check-expected-outputs",
        f"python3 {contract_self_check_script} --summary-dir <returned-summary-dir> --require-real-target-search",
    ]

    ledger_paths: dict[str, Path] = {
        **bundled_ledgers,
        "db_bootstrap_plan": db_bootstrap_plan_path,
        "data_materialization_plan": data_materialization_plan_path,
        "target_db_plan": target_db_plan_path,
        "candidate_route_plan": candidate_route_plan_path,
        "reference_import_plan": reference_import_plan_path,
        "anchor_map_plan": anchor_map_plan_path,
        "neighborhood_extract_plan": neighborhood_extract_plan_path,
        "orthology_anchor_plan": orthology_anchor_plan_path,
        "reciprocal_search_plan": reciprocal_search_plan_path,
        "pathway_completeness_plan": pathway_completeness_plan_path,
        "query_resolution_plan": query_resolution_plan_path,
        "decoy_plan": decoy_plan_path,
        "run_economics": run_economics_path,
        "workflow_class_plan": workflow_class_plan_path,
        "lane_activation_plan": lane_activation_plan_path,
        "evidence_escalation_plan": evidence_escalation_plan_path,
        "claim_levels": claim_levels_path,
        "workflow_deferred_lanes": workflow_deferred_lanes_path,
        "search_plan": search_plan_path,
        "stage_contract": stage_contract_path,
        "tool_requirements": tool_requirements_path,
        "artifact_pull_manifest": artifact_pull_manifest_path,
        "campaign_prompt": campaign_prompt_path,
        "provider_payload": provider_payload_path,
    }
    if bundled_query_fasta is not None:
        ledger_paths["query_fasta"] = bundled_query_fasta
    ledger_hashes = {
        name: file_sha256(path) if path.exists() else "missing"
        for name, path in ledger_paths.items()
    }
    launch_manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "campaign_id": campaign["campaign_id"],
        "campaign_manifest": "ledgers/campaign-manifest.json",
        "data_ledger": "ledgers/data-ledger.tsv",
        "query_ledger": "ledgers/query-ledger.tsv",
        "resource_ledger": "ledgers/resource-ledger.tsv",
        "project_goals": "ledgers/project-goals.yaml",
        "pathway_steps": "ledgers/pathway-steps.tsv",
        "database_ledger": "ledgers/database-ledger.tsv",
        "cache_ledger": "ledgers/cache-ledger.tsv",
        "query_fasta": "" if bundled_query_fasta is None else f"inputs/{bundled_query_fasta.name}",
        "db_bootstrap_plan": "db-bootstrap-plan.json",
        "data_materialization_plan": "data-materialization-plan.json",
        "target_db_plan": "target-db-plan.json",
        "candidate_route_plan": "candidate-route-plan.json",
        "reference_import_plan": "reference-import-plan.json",
        "anchor_map_plan": "anchor-map-plan.json",
        "neighborhood_extract_plan": "neighborhood-extract-plan.json",
        "orthology_anchor_plan": "orthology-anchor-plan.json",
        "reciprocal_search_plan": "reciprocal-search-plan.json",
        "pathway_completeness_plan": "pathway-completeness-plan.json",
        "query_resolution_plan": "query-resolution-plan.json",
        "decoy_plan": "decoy-plan.json",
        "run_economics": "run-economics.json",
        "workflow_class_plan": "workflow-class-plan.json",
        "lane_activation_plan": "lane-activation-plan.json",
        "evidence_escalation_plan": "evidence-escalation-plan.json",
        "claim_levels": "claim-levels.tsv",
        "workflow_deferred_lanes": "workflow-deferred-lanes.tsv",
        "search_plan": "search-plan.json",
        "stage_contract": "stage-contract.json",
        "tool_requirements": "tool-requirements.json",
        "artifact_pull_manifest": "artifact_pull.yaml",
        "campaign_prompt": "campaign-prompt.md",
        "provider_payload": str(Path("provider") / provider_payload_name(provider)),
        "campaign_manifest_sha256": ledger_hashes["campaign"],
        "provider_class": provider,
        "run_scope": run_scope,
        "local_repo_root": str(repo_root),
        "heavy_workdir": heavy_workdir,
        "summary_outdir": f"{heavy_workdir}/summary" if heavy_workdir else "summary",
        "artifact_policy": "summaries_only",
        "large_local_downloads": False,
        "provider_large_downloads_allowed": allow_provider_large_downloads,
        "web_tool_policy": "container-only",
        "runner": {
            "type": "python",
            "image": image,
            "command": runner_command,
        },
        "runtime_policy": build_runtime_policy(run_scope, runtime_cap_hours=runtime_cap_hours),
        "mandatory_stages": search_plan["stages"],
        "lanes": scope["lanes"],
        "workflow_classes": lane_activation_plan["activated_lanes"],
        "deferred_workflow_classes": lane_activation_plan["deferred_lanes"],
        "blocked_workflow_classes": lane_activation_plan["blocked_lanes"],
        "candidate_route_readiness": {
            "primary_route": candidate_route_plan["primary_route"],
            "science_readiness": candidate_route_plan["science_readiness"],
            "strict_scientific_blockers": candidate_route_plan["strict_scientific_blockers"],
            "direct_genome_tblastn_policy": candidate_route_plan["direct_genome_tblastn_policy"],
        },
        "expected_artifacts": expected_artifacts,
        "validation_commands": validation_commands,
        "ledger_hashes": ledger_hashes,
        "remote_artifact_boundaries": {
            "large_artifacts": "provider_workdir_only",
            "local_sync": "summaries_only",
            "raw_outputs": f"{heavy_workdir}/work" if heavy_workdir else "not_applicable",
            "database_cache": "/workspace/genecluster/db-cache" if provider == "runpod_pod" else f"{heavy_workdir}/databases",
            "nextflow_work": f"{heavy_workdir}/nextflow-work" if heavy_workdir else "not_applicable",
        },
        "provider_notes": {
            "display_name": config["display_name"],
            "artifact_sync": config["artifact_sync"],
            "notes": config["notes"],
            "live_launch_performed": False,
        },
        "adapter_contract": {
            "provider_class": provider,
            "required_env": config["required_env"],
            "credential_policy": "environment_or_secret_store_only",
            "workdir_policy": "remote_or_configured_heavy_workdir",
            "artifact_sync_policy": config["artifact_sync"],
            "large_artifacts_policy": "remote_only",
            "public_webserver_uploads": "forbidden",
            "live_launch_performed": False,
        },
        "missing_credentials": missing_credentials,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    launch_manifest["launch_payload_sha256"] = sha256_text(json.dumps(launch_manifest, sort_keys=True))

    for remote_name in [
        "genecluster_remote_runner.py",
        "genecluster_db_bootstrap.py",
        "genecluster_data_materialization.py",
        "genecluster_target_db_builder.py",
        "genecluster_reference_import.py",
        "genecluster_anchor_map.py",
        "genecluster_orthology_anchor.py",
        "genecluster_neighborhood_extract.py",
        "genecluster_neighborhood_score.py",
    ]:
        remote_source = SCRIPT_DIR.parent / "remote" / remote_name
        remote_target = remote_dir / remote_name
        if remote_source.exists():
            remote_target.write_text(remote_source.read_text(encoding="utf-8"), encoding="utf-8")
            remote_target.chmod(0o755)

    manifest_path = bundle_dir / "launch-manifest.json"
    manifest_path.write_text(json.dumps(launch_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run_script = bundle_dir / "run-later.sh"
    run_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "# This script is launch prep only. Review credentials/provider setup before running.\n"
        f"cd {bundle_dir}\n"
        + " ".join(runner_command)
        + "\n",
        encoding="utf-8",
    )
    run_script.chmod(0o755)

    checklist = bundle_dir / "README.md"
    checklist.write_text(
        f"""# GeneCluster Launch Bundle

Run id: `{run_id}`

Provider: `{provider}`

Scope: `{run_scope}`

Heavy workdir: `{heavy_workdir or 'not required'}`

This bundle does not launch compute. It is ready for review by Symphony/Linear before execution.

## Missing Credentials

{chr(10).join(f'- `{item}`' for item in missing_credentials) if missing_credentials else '- none detected'}

## Validation

```bash
python3 skills/biosymphony/scripts/genecluster_preflight.py --launch-manifest {manifest_path}
```
""",
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a provider-neutral GeneCluster launch bundle.")
    parser.add_argument("--campaign", type=Path, required=True, help="Campaign manifest JSON.")
    parser.add_argument("--out", type=Path, required=True, help="Output launch bundle directory.")
    parser.add_argument("--provider-class", required=True, help="Provider class, e.g. runpod_pod or local_lite.")
    parser.add_argument("--run-scope", required=True, choices=sorted(set(RUN_SCOPE_CONFIGS) | set(RUN_SCOPE_ALIASES)), help="Run scope.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repo root for safety checks.")
    parser.add_argument("--heavy-workdir", default="", help="Heavy workdir for local_full/ssh_hpc/cloud_vm, or override for remote providers.")
    parser.add_argument("--run-id", default="", help="Stable run id for reproducible tests.")
    parser.add_argument("--allow-local-full", action="store_true", help="Explicit opt-in for local_full.")
    parser.add_argument("--image", default="genecluster-runner:unbuilt", help="Remote runner image reference.")
    parser.add_argument("--runtime-cap-hours", type=float, default=24.0, help="Hard runtime cap for full_campaign_24h scope (1-24, default 24).")
    parser.add_argument("--allow-provider-large-downloads", action="store_true", help="Add --allow-large-downloads to the provider runner command. Provider-only; never local repo downloads.")
    args = parser.parse_args()

    if not (0 < args.runtime_cap_hours <= 24):
        print(f"ERROR: --runtime-cap-hours must be in (0, 24], got {args.runtime_cap_hours}", file=sys.stderr)
        return 2

    try:
        manifest = build_launch_bundle(
            campaign_path=args.campaign,
            out=args.out,
            provider_class=args.provider_class,
            run_scope=args.run_scope,
            repo_root=args.repo_root,
            heavy_workdir=args.heavy_workdir,
            run_id=args.run_id,
            allow_local_full=args.allow_local_full,
        image=args.image,
        runtime_cap_hours=args.runtime_cap_hours,
        allow_provider_large_downloads=args.allow_provider_large_downloads,
    )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
