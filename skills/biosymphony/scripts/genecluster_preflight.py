#!/usr/bin/env python3
"""Validate BioSymphony GeneCluster campaign ledgers and dossiers.

The checks are intentionally conservative: v0 assumes the local repo is a
control plane and any raw sequence or large intermediate artifact belongs on
remote storage, not in git-tracked workspace paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.load_yaml import load_yaml  # noqa: E402


ALLOWED_PROVIDER_CLASSES = {
    "local_lite",
    "local_full",
    "runpod_pod",
    "ssh_hpc",
    "cloud_vm",
    "managed_workflow",
}

PROVIDER_ALIASES = {
    "local-lite": "local_lite",
    "local-full": "local_full",
    "runpod-pod": "runpod_pod",
    "ssh-hpc": "ssh_hpc",
    "cloud-vm": "cloud_vm",
    "nextflow-managed": "managed_workflow",
}

ALLOWED_RUN_SCOPES = {
    "smoke",
    "candidate_search",
    "genome_context",
    "coexpression",
    "synteny",
    "full_public_mining",
    "next_experiment_design",
    "full_campaign",
    "full_campaign_24h",
}

HEAVY_RUN_SCOPES = {
    "candidate_search",
    "genome_context",
    "coexpression",
    "synteny",
    "full_public_mining",
    "full_campaign",
    "full_campaign_24h",
}

ALLOWED_EVIDENCE_CLASSES = {
    "transcript_hit",
    "protein_hit",
    "domain_hit",
    "genome_localized",
    "neighborhood_supported",
    "coexpression_supported",
    "review_required",
}

ALLOWED_REVIEW_STATUSES = {
    "new",
    "needs-human-review",
    "accepted",
    "rejected",
    "needs-rerun",
    "publication-candidate",
}

ALLOWED_HIT_TYPES = {
    "transcript_hit",
    "protein_hit",
    "domain_hit",
    "genome_localized",
    "neighborhood_supported",
    "coexpression_supported",
}

LICENSE_CLASSES = {
    "permissive-code",
    "copyleft-code",
    "academic-free-or-web",
    "open-data-with-terms",
    "account-or-api-terms",
    "restricted-or-review",
}

WORKFLOW_CLASSES = {
    "reference_first_anchor_mining",
    "long_read_isoform_curation",
    "transcriptome_only_dossier",
    "paralog_homeolog_copy_review",
    "expression_coexpression_support",
    "comparative_synteny_neighborhood",
    "fragmented_genome_rescue",
    "pav_copy_number_matrix",
    "candidate_sv_interval",
    "graph_pangenome_import",
    "singlecell_spatial_context",
}

WORKFLOW_CLASS_STATUSES = {"activated", "blocked", "deferred", "deferred_by_budget"}

WORKFLOW_CLASS_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "provider_class",
    "signals",
    "runtime_policy",
    "workflow_classes",
    "local_copy",
    "heavy_artifact_policy",
}

LANE_ACTIVATION_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "activated_lanes",
    "blocked_lanes",
    "deferred_lanes",
    "activation_matrix",
    "local_copy",
}

EVIDENCE_ESCALATION_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "escalation_rules",
    "forbidden_upgrades",
    "local_copy",
}

CLAIM_LEVEL_COLUMNS = {
    "claim_level",
    "allowed_statement",
    "required_evidence",
    "forbidden_overclaim",
    "review_gate",
}

WORKFLOW_DEFERRED_LANE_COLUMNS = {
    "workflow_class",
    "deferred_status",
    "reason",
    "trigger_to_reactivate",
    "claim_effect",
    "review_status",
}

PROJECT_GOALS_REQUIRED_KEYS = {
    "schema_version",
    "project_id",
    "scientific_goal",
    "organism",
    "target_pathway",
    "default_run_scope",
    "database_tier",
    "execution_defaults",
    "priorities",
    "allowed_compute_lanes",
    "forbidden_compute_lanes",
    "stop_conditions",
    "claim_boundaries",
    "approved_resources",
}

PATHWAY_STEP_COLUMNS = {
    "pathway_step_id",
    "step_name",
    "role",
    "substrate",
    "product",
    "expected_enzyme_families",
    "known_seed_examples",
    "query_ids",
    "expected_evidence",
    "unresolved_caveats",
    "claim_limit",
}

DATABASE_LEDGER_COLUMNS = {
    "db_id",
    "engine",
    "sequence_type",
    "remote_path",
    "version",
    "source",
    "checksum_status",
    "license_class",
    "build_required",
    "search_template",
    "retention_policy",
    "backup_policy",
    "priority",
    "notes",
}

CACHE_LEDGER_COLUMNS = {
    "cache_id",
    "provider_class",
    "cache_role",
    "remote_path",
    "mount_path",
    "required",
    "free_space_gb",
    "retention_policy",
    "backup_policy",
    "env_var",
    "notes",
}

DATA_LEDGER_COLUMNS = {
    "dataset_id",
    "accession",
    "run_id",
    "data_role",
    "sample_type",
    "organism",
    "bioproject",
    "technology",
    "expected_size",
    "source_url",
    "remote_path",
    "checksum_status",
    "data_sensitivity",
    "allowed_compute_location",
    "allowed_upload",
    "redistribution_policy",
    "terms_checked_date",
    "license_url",
    "citation_doi",
    "md5_or_sha256",
    "frozen_metadata_path",
    "raw_artifact_policy",
    "retention_policy",
    "operator_approval_id",
}

QUERY_LEDGER_COLUMNS = {
    "query_id",
    "query_name",
    "source_organism",
    "sequence_source",
    "enzyme_class",
    "pathway_role",
    "confidence",
    "citation",
    "resolved_accession",
    "sequence_type",
    "sequence_length",
    "checksum",
    "family_scope",
    "motif_requirements",
    "negative_controls",
    "decoy_or_broad_family_flag",
    "expected_false_positive_risk",
    "curation_status",
    "last_resolved_at",
}

QUERY_REGISTRY_COLUMNS = {
    "query_id",
    "canonical_name",
    "claim_id",
    "source_organism",
    "sequence_status",
    "sequence_kind",
    "resolved_accession",
    "sequence_length",
    "checksum",
    "resolution_method",
    "resolution_evidence",
    "proxy_for",
    "fallback_for",
    "required_for_claims",
    "claim_ceiling_if_unresolved",
    "claim_ceiling_if_resolved",
    "last_checked_at",
    "source_scout_status",
    "notes",
}

REQUIRED_CLAIM_COLUMNS = {
    "claim_id",
    "statement",
    "required_query_ids",
    "required_source_classes",
    "minimum_query_status",
    "allowed_if_unresolved",
    "blocked_output_labels",
    "review_gate",
    "assertion_status",
}

SOURCE_LEDGER_COLUMNS = {
    "source_id",
    "source_record_type",
    "source_provider",
    "source_accession",
    "source_accession_kind",
    "material_type",
    "acquisition_policy",
    "organism",
    "proteome_fasta",
    "gff",
    "genome_fasta",
    "transcriptome",
    "transcriptome_species",
    "source_class",
    "probe_status",
    "scout_status",
}

READ_ACCESSIONS_COLUMNS = {
    "source_id",
    "source_record_type",
    "source_provider",
    "source_accession",
    "source_accession_kind",
    "material_type",
    "acquisition_policy",
    "dataset_id",
    "input_accession",
    "run_accession",
    "library_layout",
    "layout_branch",
    "remote_path",
    "raw_artifact_policy",
    "status",
}

QUERY_SEQUENCE_STATUSES = {
    "resolved",
    "resolved_as_proxy",
    "fallback_used",
    "unresolved_intake_blocked",
    "remote_resolve_required",
    "family_seed",
    "context_only",
    "deprecated",
}

RESOLVED_QUERY_STATUSES = {"resolved", "resolved_as_proxy", "fallback_used"}

RESOURCE_LEDGER_COLUMNS = {
    "resource",
    "resource_type",
    "version",
    "license_class",
    "use_mode",
    "citation",
}

CANDIDATE_HIT_COLUMNS = {
    "candidate_id",
    "query_id",
    "gene_or_transcript_id",
    "dataset_id",
    "source_species",
    "target_species",
    "search_direction",
    "target_db_id",
    "hit_type",
    "pct_identity",
    "coverage",
    "evalue",
    "domain_calls",
    "pathway_role",
    "evidence_score",
    "review_status",
    "pathway_step_id",
    "novelty_status",
    "novelty_basis",
    "closest_characterized_identity",
    "dedupe_group",
    "representative_id",
    "duplicate_class",
    "duplicate_confidence",
    "splice_variant_status",
    "partial_status",
    "dedupe_rationale",
    "query_coverage",
    "target_coverage",
    "bitscore",
    "reciprocal_rank",
    "reciprocal_best_hit",
    "anchor_method",
    "anchor_confidence",
    "coordinate_confidence",
    "orthogroup_id",
    "paralog_flag",
    "isoform_group",
    "domain_architecture",
    "catalytic_motif_status",
    "subcellular_prediction",
    "transmembrane_prediction",
    "expression_tpm",
    "coexpression_module",
    "genome_locus",
    "synteny_block_id",
    "neighborhood_cluster_id",
    "product_claim_level",
    "evidence_weights_json",
}

TARGET_DB_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "data_ledger",
    "provider_db_root",
    "records",
    "index_targets",
    "outputs",
    "local_copy",
}

CANDIDATE_ROUTE_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "provider_class",
    "provider_workdir",
    "data_ledger",
    "target_db_plan",
    "signals",
    "primary_route",
    "route_reason",
    "scientific_default_order",
    "implemented_runner_route",
    "implemented_runner_stages",
    "missing_transcript_first_stages",
    "transcript_first_required_for_scientific_full",
    "strict_scientific_blockers",
    "science_readiness",
    "direct_genome_tblastn_policy",
    "route_records",
    "route_audit",
    "local_copy",
}

ORTHOLOGY_ANCHOR_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "search_directions",
    "anchor_confidence_classes",
    "inputs",
    "outputs",
    "fallback_methods",
    "claim_policy",
    "local_copy",
}

RECIPROCAL_SEARCH_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "search_directions",
    "inputs",
    "outputs",
    "scoring_policy",
    "local_copy",
}

PATHWAY_COMPLETENESS_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "inputs",
    "output",
    "statuses",
    "budget_policy",
    "local_copy",
}

TARGET_DB_LEDGER_COLUMNS = {
    "target_db_id",
    "dataset_id",
    "species",
    "resource_kind",
    "sequence_type",
    "source_path",
    "provider_path",
    "index_policy",
    "build_status",
    "checksum_status",
    "local_copy",
    "notes",
}

TARGET_DB_INDEX_COLUMNS = {
    "target_db_id",
    "dataset_id",
    "engine",
    "sequence_type",
    "index_path",
    "source_path",
    "build_status",
    "command",
    "checksum_status",
}

ORTHOLOGY_LINK_COLUMNS = {
    "orthology_link_id",
    "candidate_id",
    "source_species",
    "target_species",
    "query_id",
    "target_id",
    "search_direction",
    "target_db_id",
    "pct_identity",
    "query_coverage",
    "target_coverage",
    "evalue",
    "bitscore",
    "reciprocal_rank",
    "reciprocal_best_hit",
    "orthology_status",
    "evidence_score_delta",
    "claim_limit",
}

ANCHOR_LADDER_COLUMNS = {
    "candidate_id",
    "query_id",
    "target_id",
    "source_species",
    "target_species",
    "anchor_method",
    "anchor_confidence",
    "coordinate_confidence",
    "genome_locus",
    "contig",
    "start",
    "end",
    "strand",
    "fallback_order",
    "evidence_basis",
    "claim_gate",
}

RECIPROCAL_HIT_COLUMNS = {
    "reciprocal_hit_id",
    "candidate_id",
    "query_id",
    "forward_target_id",
    "reverse_query_id",
    "reciprocal_rank",
    "reciprocal_best_hit",
    "forward_bitscore",
    "reverse_bitscore",
    "status",
}

NEIGHBORHOOD_HYPOTHESIS_COLUMNS = {
    "hypothesis_id",
    "neighborhood_id",
    "candidate_id",
    "anchor_gene_id",
    "neighbor_feature_id",
    "distance_bp",
    "domain_relevance",
    "enzyme_family_label",
    "hypothesis_score",
    "claim_safe_label",
    "claim_gate",
    "evidence_basis",
    "review_status",
}

PATHWAY_COMPLETENESS_COLUMNS = {
    "pathway_step_id",
    "step_name",
    "query_ids",
    "target_candidate_ids",
    "reciprocal_status",
    "domain_support",
    "anchor_support",
    "neighborhood_support",
    "status",
    "claim_limit",
    "deferred_reason",
    "review_status",
}

ISOFORM_LEDGER_COLUMNS = {
    "isoform_id",
    "gene_or_locus_id",
    "source_dataset_id",
    "tool",
    "classification",
    "full_length_status",
    "orf_status",
    "protein_id",
    "domain_architecture",
    "domain_delta_vs_representative",
    "candidate_hit_ids",
    "expression_support",
    "representative_status",
    "review_status",
    "claim_boundary",
}

ISOFORM_CLASSIFICATION_COLUMNS = {
    "isoform_id",
    "gene_or_locus_id",
    "classification",
    "subcategory",
    "qc_status",
    "artifact_risk",
    "supporting_reads",
    "review_status",
}

ISOFORM_ORF_COLUMNS = {
    "isoform_id",
    "orf_id",
    "protein_id",
    "orf_status",
    "protein_length",
    "start_codon_status",
    "stop_codon_status",
    "review_status",
}

ISOFORM_DOMAIN_DELTA_COLUMNS = {
    "isoform_id",
    "representative_isoform_id",
    "domain_architecture",
    "domain_delta_vs_representative",
    "functional_risk",
    "review_status",
}

TRANSCRIPTOME_BUILD_LEDGER_COLUMNS = {
    "build_id",
    "dataset_id",
    "strategy",
    "tool",
    "status",
    "remote_workdir",
    "raw_artifact_policy",
    "review_status",
}

ASSEMBLY_QC_COLUMNS = {
    "build_id",
    "metric",
    "value",
    "threshold",
    "status",
    "review_status",
}

ORF_LEDGER_COLUMNS = {
    "orf_id",
    "transcript_id",
    "protein_id",
    "orf_status",
    "protein_length",
    "domain_architecture",
    "candidate_hit_ids",
    "review_status",
}

ISOFORM_GROUP_COLUMNS = {
    "isoform_group_id",
    "gene_or_locus_id",
    "member_isoform_ids",
    "representative_isoform_id",
    "group_basis",
    "review_status",
}

ORTHOGROUP_LEDGER_COLUMNS = {
    "orthogroup_id",
    "candidate_ids",
    "source_species",
    "target_species",
    "method",
    "copy_count",
    "review_status",
}

PARALOG_HOMEOLOG_LEDGER_COLUMNS = {
    "copy_group_id",
    "candidate_id",
    "copy_class",
    "copy_class_evidence",
    "orthogroup_id",
    "tree_node",
    "locus_id",
    "synteny_status",
    "tandem_status",
    "expression_distinction",
    "domain_distinction",
    "review_status",
}

COPY_CLASSIFICATION_COLUMNS = PARALOG_HOMEOLOG_LEDGER_COLUMNS

GENE_TREE_SUMMARY_COLUMNS = {
    "tree_id",
    "orthogroup_id",
    "method",
    "candidate_ids",
    "support_summary",
    "review_status",
}

SYNTENY_SUPPORT_COLUMNS = {
    "synteny_block_id",
    "candidate_id",
    "source_species",
    "target_species",
    "support_status",
    "evidence_basis",
    "review_status",
}

EXPRESSION_DESIGN_COLUMNS = {
    "sample_id",
    "dataset_id",
    "tissue",
    "condition",
    "replicate",
    "include",
    "review_status",
}

TISSUE_SPECIFICITY_COLUMNS = {
    "candidate_id",
    "tissue",
    "metric",
    "value",
    "support_status",
    "review_status",
}

COEXPRESSION_MODULE_COLUMNS = {
    "module_id",
    "candidate_id",
    "method",
    "edge_count",
    "module_score",
    "support_status",
    "review_status",
}

ASSEMBLY_LEDGER_COLUMNS = {
    "assembly_id",
    "species",
    "accession",
    "assembly_role",
    "remote_path",
    "coordinate_system",
    "checksum_status",
    "review_status",
}

ANNOTATION_LEDGER_COLUMNS = {
    "annotation_id",
    "assembly_id",
    "annotation_role",
    "remote_path",
    "format",
    "checksum_status",
    "review_status",
}

ROUTE_ANNOTATION_LEDGER_COLUMNS = {
    "source_id",
    "organism",
    "proteome_fasta",
    "gff",
    "genome_fasta",
    "transcriptome",
    "transcriptome_species",
    "proteome_count",
    "gff_protein_count",
    "protein_gff_join_count",
    "controls_ok",
    "recommended_route",
    "claim_ceiling",
    "blockers",
}

ROUTE_ANNOTATION_ROUTES = {
    "annotation_direct",
    "annotation_direct_then_context",
    "transcript_first",
    "genome_context",
    "transcriptome_only",
    "tblastn_rescue",
    "coexpression",
    "synteny",
    "next_experiment_design",
}

ROUTE_CLAIM_CEILINGS = {
    "L0_route_only",
    "L1_candidate_gene_only",
    "L1_sequence_rescue_only",
    "L2_coordinate_context_ready",
    "L2_annotation_assets_need_join_repair",
    "L3_annotation_neighborhood_ready",
}

COORDINATE_LIFTOVER_LEDGER_COLUMNS = {
    "liftover_id",
    "candidate_id",
    "source_coordinate_system",
    "target_coordinate_system",
    "method",
    "status",
    "coordinate_confidence",
    "review_status",
}

COMPARATIVE_NEIGHBORHOOD_COLUMNS = {
    "comparative_neighborhood_id",
    "candidate_id",
    "assembly_id",
    "anchor_gene_id",
    "neighbor_summary",
    "synteny_status",
    "claim_gate",
    "review_status",
}

PAV_COPY_NUMBER_COLUMNS = {
    "candidate_id",
    "sample_or_assembly_id",
    "presence_status",
    "copy_number",
    "method",
    "evidence_basis",
    "review_status",
}

SV_LEDGER_COLUMNS = {
    "sv_id",
    "candidate_id",
    "assembly_or_sample_id",
    "sv_type",
    "interval",
    "method",
    "support_status",
    "review_status",
}

CANDIDATE_INTERVAL_SV_COLUMNS = {
    "candidate_id",
    "interval_id",
    "sv_ids",
    "distance_to_candidate_bp",
    "functional_risk",
    "claim_gate",
    "review_status",
}

GRAPH_LEDGER_COLUMNS = {
    "graph_id",
    "graph_type",
    "source",
    "remote_path",
    "coordinate_system",
    "status",
    "review_status",
}

GRAPH_PATH_SUPPORT_COLUMNS = {
    "candidate_id",
    "graph_id",
    "path_id",
    "support_status",
    "coordinate_confidence",
    "claim_gate",
    "review_status",
}

SINGLECELL_DATASET_LEDGER_COLUMNS = {
    "singlecell_dataset_id",
    "dataset_id",
    "technology",
    "cell_or_spatial_unit",
    "status",
    "review_status",
}

SPATIAL_DOMAIN_EXPRESSION_COLUMNS = {
    "candidate_id",
    "domain_or_cell_type",
    "expression_metric",
    "value",
    "support_status",
    "claim_gate",
    "review_status",
}

CANDIDATE_RANKING_COLUMNS = {
    "rank",
    "candidate_id",
    "evidence_score",
    "evidence_tier",
    "summary",
    "review_status",
}

LAUNCH_MANIFEST_REQUIRED_KEYS = {
    "schema_version",
    "run_id",
    "campaign_id",
    "campaign_manifest",
    "data_ledger",
    "query_ledger",
    "resource_ledger",
    "project_goals",
    "pathway_steps",
    "database_ledger",
    "cache_ledger",
    "db_bootstrap_plan",
    "data_materialization_plan",
    "target_db_plan",
    "candidate_route_plan",
    "reference_import_plan",
    "anchor_map_plan",
    "neighborhood_extract_plan",
    "orthology_anchor_plan",
    "reciprocal_search_plan",
    "pathway_completeness_plan",
    "campaign_prompt",
    "query_resolution_plan",
    "decoy_plan",
    "run_economics",
    "workflow_class_plan",
    "lane_activation_plan",
    "evidence_escalation_plan",
    "claim_levels",
    "workflow_deferred_lanes",
    "search_plan",
    "tool_requirements",
    "provider_payload",
    "provider_class",
    "run_scope",
    "local_repo_root",
    "heavy_workdir",
    "artifact_policy",
    "runner",
    "expected_artifacts",
    "validation_commands",
    "provider_notes",
    "adapter_contract",
}

EXECUTION_READY_REQUIRED_KEYS = {
    "summary_outdir",
    "remote_artifact_boundaries",
    "database_ledger",
    "cache_ledger",
    "db_bootstrap_plan",
    "data_materialization_plan",
    "target_db_plan",
    "candidate_route_plan",
    "reference_import_plan",
    "anchor_map_plan",
    "neighborhood_extract_plan",
    "orthology_anchor_plan",
    "reciprocal_search_plan",
    "pathway_completeness_plan",
    "query_resolution_plan",
    "decoy_plan",
    "run_economics",
    "workflow_class_plan",
    "lane_activation_plan",
    "evidence_escalation_plan",
    "claim_levels",
    "workflow_deferred_lanes",
    "search_plan",
    "tool_requirements",
    "provider_payload",
}

QUERY_RESOLUTION_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "query_ledger",
    "output_fasta",
    "records",
    "blocking_unresolved_query_ids",
}

DB_BOOTSTRAP_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "database_ledger",
    "db_cache_root",
    "records",
    "forbidden_local_paths",
    "execution_policy",
}

REFERENCE_IMPORT_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "data_ledger",
    "provider_inputs_dir",
    "records",
    "preferred_order",
    "local_copy",
}

ANCHOR_MAP_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "candidate_hits",
    "resolved_references",
    "output",
    "methods",
    "fail_closed_without_coordinates",
    "local_copy",
}

NEIGHBORHOOD_EXTRACT_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "candidate_anchors",
    "outputs",
    "window_kb",
    "window_genes",
    "enzyme_family_profiles",
    "claim_policy",
    "local_copy",
}

DECOY_PLAN_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "query_ledger",
    "records",
    "broad_family_query_ids",
    "high_false_positive_risk_query_ids",
    "enforcement",
}

RUN_ECONOMICS_REQUIRED_KEYS = {
    "schema_version",
    "run_scope",
    "provider_class",
    "database_budget",
    "cache_budget",
    "query_budget",
    "cost_controls",
    "launch_blockers",
    "recommended_live_sequence",
}

CLUSTER_NEIGHBORHOOD_COLUMNS = {
    "cluster_id",
    "candidate_id",
    "anchor_gene_id",
    "distance_to_anchor_kb",
    "pfams",
    "pfam_descriptions",
    "top_cdd_hit",
    "sequence_length",
    "sequence_policy",
    "coordinate_status",
    "evidence_ids",
    "review_status",
}

CANDIDATE_ANCHOR_COLUMNS = {
    "candidate_id",
    "query_id",
    "gene_or_transcript_id",
    "dataset_id",
    "matched_feature_id",
    "matched_attribute",
    "contig",
    "start",
    "end",
    "strand",
    "feature_type",
    "genome_locus",
    "anchor_status",
    "anchor_confidence",
    "source_gff",
    "pathway_step_id",
    "domain_calls",
    "evidence_score",
    "product_claim_level",
    "context_claim_gate",
    "match_notes",
}

NEIGHBORHOOD_SUMMARY_COLUMNS = {
    "neighborhood_id",
    "candidate_id",
    "query_id",
    "contig",
    "candidate_start",
    "candidate_end",
    "window_start",
    "window_end",
    "window_kb",
    "window_genes",
    "neighbor_count",
    "candidate_domain_calls",
    "pathway_step_id",
    "product_claim_level",
    "claim_gate",
    "context_claim_gate",
}

NEIGHBOR_ANNOTATION_COLUMNS = {
    "neighborhood_id",
    "candidate_id",
    "neighbor_rank",
    "feature_id",
    "feature_type",
    "contig",
    "start",
    "end",
    "strand",
    "distance_bp",
    "overlaps_window",
    "is_candidate",
    "product",
    "source_gff",
}

DOMAIN_LABEL_COLUMNS = {
    "neighborhood_id",
    "candidate_id",
    "feature_id",
    "domain_label",
    "label_source",
    "pathway_step_id",
    "product_claim_level",
}

REMOTE_PREFIXES = (
    "/workspace/",
    "/runpod-volume/",
    "s3://",
    "r2://",
    "b2://",
    "gs://",
    "az://",
)

OBJECT_STORE_PREFIXES = ("s3://", "r2://", "b2://", "gs://", "az://")

URL_PREFIXES = ("https://", "http://", "ftp://")

RAW_OR_LARGE_SUFFIXES = (
    ".sra",
    ".fastq",
    ".fq",
    ".fastq.gz",
    ".fq.gz",
    ".fasta",
    ".fa",
    ".fna",
    ".ffn",
    ".faa",
    ".frn",
    ".gff",
    ".gff3",
    ".gtf",
    ".gb",
    ".gbk",
    ".vcf",
    ".vcf.gz",
    ".bam",
    ".cram",
    ".sam",
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".bt2",
    ".bwt",
    ".mmi",
    ".dmnd",
    ".pin",
    ".phr",
    ".psq",
    ".nin",
    ".nhr",
    ".nsq",
)

BLOCKED_LOCAL_DIR_NAMES = {
    "sra-cache",
    "raw-sequence-data",
    "genecluster-runs",
    "workflow-work",
    "work",
    ".nextflow",
    "blastdb",
    "mmseqsdb",
    "interproscan-data",
}

DEFAULT_LOCAL_SUMMARY_LIMIT_BYTES = 10 * 1024 * 1024
ALLOWED_LOCAL_ARTIFACT_FIXTURES = {
    Path("skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/query-with-controls.faa"),
    Path("skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/fixture-proteome.faa"),
    Path("skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/fixture-genomic.gff"),
}
ALLOWED_LOCAL_ARTIFACT_FIXTURE_MAX_BYTES = 4096

DATABASE_ENGINES = {
    "blast",
    "diamond",
    "mmseqs",
    "hmmer",
    "rpsblast",
    "interpro",
    "eggnog",
    "kofam",
    "mibig",
    "plantismash",
    "custom",
}

DATABASE_SEQUENCE_TYPES = {"protein", "nucleotide", "domain", "mixed", "taxonomy"}

CHECKSUM_STATUSES = {"remote_pending", "verified", "not_applicable", "pending"}

BOOLEAN_VALUES = {"true", "false"}

DATABASE_PRIORITIES = {"required", "optional", "optional_max"}

DATABASE_RUN_GATES = {"candidate_search", "full_public_mining", "full_campaign", "optional_max", "deferred_review"}

DATABASE_COST_CLASSES = {"tiny", "small", "medium", "large", "huge"}

DATABASE_PREP_ROI = {"high", "medium", "low", "deferred"}

CACHE_RETENTION_POLICIES = {"runpod_volume_persistent", "delete_after_review", "not_applicable"}

CACHE_BACKUP_POLICIES = {
    "external_backup_required",
    "external_backup_optional",
    "local_summary_sync_allowed",
    "not_applicable",
}

CLAIM_LIMITS = {"candidate_only", "candidate_or_context", "pathway_hypothesis", "review_required", "context_only"}

NOVELTY_STATUSES = {
    "known_seed_like",
    "known_family_candidate",
    "novel_candidate",
    "broad_family_uncertain",
    "not_assessed",
}

DUPLICATE_CLASSES = {
    "representative",
    "paralog",
    "paralog_candidate",
    "allele",
    "homeolog",
    "isoform",
    "assembly_artifact",
    "broad_family",
    "unknown",
}

DUPLICATE_CONFIDENCE = {"high", "medium", "low", "not_assessed"}

SPLICE_VARIANT_STATUSES = {
    "not_assessed",
    "no_isoform_evidence",
    "isoform_pending",
    "splice_variant_candidate",
    "intron_retained",
    "alt_3",
    "alt_5",
    "exon_skipped",
    "novel_isoform",
}

PARTIAL_STATUSES = {"complete", "complete_orf_pending", "partial", "unknown"}

CLAIM_AUDIT_VERDICTS = {"supported", "qualified", "not_supported", "untestable", "needs_more_data"}

PLACEHOLDER_IMAGE_VALUES = {"", "genecluster-runner:unbuilt", "placeholder", "todo", "tbd"}

RUNPOD_REGISTRY_AUTH_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "GENECLUSTER_CONTAINER_REGISTRY_AUTH_ID",
]

RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL",
    "GENECLUSTER_IMAGE_PUBLIC_PULL",
]

SEARCH_DIRECTIONS = {
    "canonical_A_to_target_B",
    "target_B_to_canonical_A",
    "domain_to_target_B",
    "target_B_to_reference_db",
}

ANCHOR_CONFIDENCE_CLASSES = {
    "exact_gff_id",
    "reciprocal_best_hit",
    "transcript_to_genome",
    "protein_to_genome",
    "domain_only",
    "unanchored",
}

ANCHOR_METHODS = {
    "exact_gff_id",
    "reciprocal_best_hit",
    "transcript_to_genome",
    "protein_to_genome",
    "miniprot",
    "domain_only",
    "unanchored",
    "not_assessed",
}

COORDINATE_CONFIDENCE_VALUES = ANCHOR_CONFIDENCE_CLASSES | {"high", "medium", "low", "none", "mock", "remote_pending"}

PATHWAY_COMPLETENESS_STATUSES = {
    "supported",
    "partial",
    "missing",
    "ambiguous",
    "context_only",
    "deferred_by_budget",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
            return rows, list(reader.fieldnames or [])
    except OSError as exc:
        return [], [f"could not read {path}: {exc}"]


def is_remote_path(value: str) -> bool:
    return value.startswith(REMOTE_PREFIXES)


def is_object_store_uri(value: str) -> bool:
    return value.startswith(OBJECT_STORE_PREFIXES)


def is_url(value: str) -> bool:
    return value.startswith(URL_PREFIXES)


def has_raw_or_large_suffix(value: str) -> bool:
    lower = value.lower()
    return any(lower.endswith(suffix) for suffix in RAW_OR_LARGE_SUFFIXES)


def path_is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def normalize_provider(provider: str) -> str:
    return PROVIDER_ALIASES.get(provider, provider)


def any_env_present(names: list[str]) -> bool:
    return any(os.environ.get(name, "").strip() for name in names)


def any_env_truthy(names: list[str]) -> bool:
    return any(os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"} for name in names)


def registry_auth_missing(policy: dict[str, Any]) -> bool:
    env_names = policy.get("container_registry_auth_id_env_names", RUNPOD_REGISTRY_AUTH_ENV_NAMES)
    public_env_names = policy.get("public_image_assertion_env_names", RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES)
    if not isinstance(env_names, list):
        env_names = RUNPOD_REGISTRY_AUTH_ENV_NAMES
    if not isinstance(public_env_names, list):
        public_env_names = RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES
    auth_present = any_env_present([str(name) for name in env_names])
    public_asserted = bool(policy.get("public_image_asserted")) or any_env_truthy([str(name) for name in public_env_names])
    auth_needed = bool(policy.get("auth_likely_required") or policy.get("launch_blocker_if_missing"))
    return auth_needed and not auth_present and not public_asserted


def validate_campaign_manifest(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    required = {
        "campaign_id",
        "organism",
        "target_pathway",
        "accessions",
        "query_set",
        "execution",
        "artifact_policy",
        "license_policy",
        "review_policy",
    }
    for key in sorted(required):
        if key not in data:
            errors.append(f"campaign manifest missing root key: {key}")

    if data.get("schema_version") != 1:
        errors.append("campaign manifest schema_version must be 1")

    accessions = data.get("accessions")
    if not isinstance(accessions, list) or not accessions:
        errors.append("accessions must be a non-empty list")
    else:
        seen = {str(item.get("id", "")) for item in accessions if isinstance(item, dict)}
        for expected in {"SRX9153204", "SRX16999876", "SRX9153201"}:
            if expected not in seen:
                warnings.append(f"expected Coptis demo accession not listed: {expected}")

    execution = data.get("execution", {})
    if not isinstance(execution, dict):
        errors.append("execution must be an object")
        execution = {}

    provider = normalize_provider(str(execution.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("execution.provider_class is not an allowed provider class")
    if execution.get("large_local_downloads") is not False:
        errors.append("execution.large_local_downloads must be false")
    if execution.get("artifact_policy") != "summaries_only":
        errors.append("execution.artifact_policy must be summaries_only")
    if execution.get("web_tool_policy") != "container-only":
        errors.append("execution.web_tool_policy must be container-only")

    remote_workdir = str(execution.get("remote_workdir", ""))
    if provider == "runpod_pod" and not remote_workdir.startswith("/workspace/genecluster/runs/"):
        errors.append("execution.remote_workdir must be under /workspace/genecluster/runs/ for runpod_pod")

    evidence_classes = set(data.get("evidence_classes", []))
    missing_evidence = ALLOWED_EVIDENCE_CLASSES - evidence_classes
    if missing_evidence:
        errors.append(f"evidence_classes missing: {', '.join(sorted(missing_evidence))}")

    statuses = set(data.get("review_policy", {}).get("statuses", []))
    missing_statuses = ALLOWED_REVIEW_STATUSES - statuses
    if missing_statuses:
        errors.append(f"review_policy.statuses missing: {', '.join(sorted(missing_statuses))}")

    run_scopes = data.get("run_scopes", {})
    if run_scopes:
        if not isinstance(run_scopes, dict):
            errors.append("run_scopes must be an object when present")
        else:
            unknown_scopes = set(run_scopes) - ALLOWED_RUN_SCOPES
            if unknown_scopes:
                errors.append(f"run_scopes contains unknown scopes: {', '.join(sorted(unknown_scopes))}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_project_goals(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = load_yaml(path) or {}
    except (OSError, SystemExit) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["project goals must be a YAML object"], "warnings": []}

    missing = PROJECT_GOALS_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"project goals missing root keys: {', '.join(sorted(missing))}")

    if data.get("schema_version") != 1:
        errors.append("project goals schema_version must be 1")

    run_scope = str(data.get("default_run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"project goals default_run_scope is not allowed: {run_scope}")

    if data.get("database_tier") not in {"minimum", "standard", "maximum"}:
        errors.append("project goals database_tier must be minimum, standard, or maximum")

    execution_defaults = data.get("execution_defaults", {})
    if not isinstance(execution_defaults, dict):
        errors.append("project goals execution_defaults must be an object")
        execution_defaults = {}
    provider = normalize_provider(str(execution_defaults.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("project goals execution_defaults.provider_class is not allowed")
    if execution_defaults.get("return_policy") != "summaries_only":
        errors.append("project goals execution_defaults.return_policy must be summaries_only")
    for key in ["mount_path", "db_cache_root", "nextflow_cache_root", "scratch_root"]:
        value = str(execution_defaults.get(key, ""))
        if value and value != "/workspace" and not is_remote_path(value):
            errors.append(f"project goals execution_defaults.{key} must be remote/provider storage: {value}")

    forbidden = set(data.get("forbidden_compute_lanes") or [])
    if "ncbi_remote_blast_batch" not in forbidden:
        errors.append("project goals must explicitly forbid ncbi_remote_blast_batch")
    if "public_webserver_private_upload" not in forbidden:
        errors.append("project goals must explicitly forbid public_webserver_private_upload")

    allowed = set(data.get("allowed_compute_lanes") or [])
    for required_lane in {"local_blast", "diamond", "mmseqs2", "hmmer"}:
        if required_lane not in allowed:
            warnings.append(f"project goals allowed_compute_lanes should include {required_lane}")

    claim_boundaries = data.get("claim_boundaries", {})
    if not isinstance(claim_boundaries, dict):
        errors.append("project goals claim_boundaries must be an object")
    else:
        if claim_boundaries.get("transcriptome_cluster_claim") != "forbidden":
            errors.append("claim_boundaries.transcriptome_cluster_claim must be forbidden")
        if claim_boundaries.get("broad_family_product_claim") != "forbidden":
            errors.append("claim_boundaries.broad_family_product_claim must be forbidden")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_pathway_steps(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = PATHWAY_STEP_COLUMNS - fields
    if missing:
        errors.append(f"pathway steps missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("pathway steps must contain at least one row")

    seen: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        label = row.get("pathway_step_id") or f"row {idx}"
        if not label.startswith("STEP_"):
            errors.append(f"{label}: pathway_step_id must start with STEP_")
        if label in seen:
            errors.append(f"{label}: duplicate pathway_step_id")
        seen.add(label)
        if row.get("claim_limit") not in CLAIM_LIMITS:
            errors.append(f"{label}: claim_limit is not recognized: {row.get('claim_limit')}")
        if not row.get("expected_enzyme_families"):
            warnings.append(f"{label}: expected_enzyme_families is empty")
        if not row.get("query_ids"):
            warnings.append(f"{label}: query_ids is empty")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_database_ledger(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    repo_root = (repo_root or Path.cwd()).resolve()
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = DATABASE_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"database ledger missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("database ledger must contain at least one row")

    required_engines = {"blast", "diamond", "mmseqs", "hmmer"}
    seen_engines: set[str] = set()
    seen_required: set[str] = set()
    seen_ids: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        label = row.get("db_id") or f"row {idx}"
        if label in seen_ids:
            errors.append(f"{label}: duplicate db_id")
        seen_ids.add(label)
        engine = row.get("engine", "")
        if engine not in DATABASE_ENGINES:
            errors.append(f"{label}: engine is not recognized: {engine}")
        else:
            seen_engines.add(engine)
        if row.get("sequence_type") not in DATABASE_SEQUENCE_TYPES:
            errors.append(f"{label}: sequence_type is not recognized: {row.get('sequence_type')}")
        remote_path = row.get("remote_path", "")
        if not remote_path:
            errors.append(f"{label}: remote_path is required")
        elif is_object_store_uri(remote_path):
            errors.append(f"{label}: database remote_path must be a mounted filesystem path for v1 execution, not object storage: {remote_path}")
        elif not is_remote_path(remote_path):
            local_candidate = Path(remote_path)
            if not local_candidate.is_absolute():
                errors.append(f"{label}: database remote_path must be remote/provider storage or absolute configured workdir")
            elif path_is_under(local_candidate, repo_root):
                errors.append(f"{label}: database path must not be under the repo root")
        if row.get("checksum_status") not in CHECKSUM_STATUSES:
            errors.append(f"{label}: checksum_status is not recognized: {row.get('checksum_status')}")
        if row.get("license_class") not in LICENSE_CLASSES:
            errors.append(f"{label}: license_class is not recognized: {row.get('license_class')}")
        if row.get("build_required") not in BOOLEAN_VALUES:
            errors.append(f"{label}: build_required must be true or false")
        priority = row.get("priority", "")
        if priority not in DATABASE_PRIORITIES:
            errors.append(f"{label}: priority is not recognized: {priority}")
        if priority == "required":
            seen_required.add(label)
        run_gate = row.get("run_gate", "")
        if run_gate and run_gate not in DATABASE_RUN_GATES:
            errors.append(f"{label}: run_gate is not recognized: {run_gate}")
        if row.get("cost_class", "") and row.get("cost_class") not in DATABASE_COST_CLASSES:
            errors.append(f"{label}: cost_class is not recognized: {row.get('cost_class')}")
        if row.get("prep_roi", "") and row.get("prep_roi") not in DATABASE_PREP_ROI:
            errors.append(f"{label}: prep_roi is not recognized: {row.get('prep_roi')}")
        if priority == "required" and run_gate in {"optional_max", "deferred_review"}:
            errors.append(f"{label}: required priority cannot use optional/deferred run_gate")
        if row.get("prep_roi") == "high" and not row.get("bootstrap_strategy"):
            errors.append(f"{label}: high ROI database rows require bootstrap_strategy")
        template = row.get("search_template", "")
        if "-remote" in template or "remote_blast" in template.lower():
            errors.append(f"{label}: remote BLAST/search execution is forbidden")
        if has_raw_or_large_suffix(remote_path) and not remote_path.startswith("/workspace/genecluster/db-cache/diamond/"):
            warnings.append(f"{label}: database path has sequence-like suffix; ensure this is provider cache only")

    missing_engines = required_engines - seen_engines
    if missing_engines:
        errors.append(f"database ledger missing required search engines: {', '.join(sorted(missing_engines))}")
    # Required DB set for `full_campaign_24h` 4h-cap scope: SwissProt BLAST/DIAMOND + Pfam.
    # mmseqs_uniprotkb is supported but demoted to optional_max for the demo run because
    # the UniProtKB index build is the dominant DB-stage cost (1-3h) and SwissProt+Pfam
    # covers the candidate set for well-characterized seeds. Re-add to this set if a
    # campaign legitimately needs full UniProtKB recall.
    for required_db in {"blast_swissprot", "diamond_swissprot", "hmmer_pfam"}:
        if required_db not in seen_required:
            errors.append(f"database ledger missing required DB row: {required_db}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_cache_ledger(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    repo_root = (repo_root or Path.cwd()).resolve()
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = CACHE_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"cache ledger missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("cache ledger must contain at least one row")

    seen_roles: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        label = row.get("cache_id") or f"row {idx}"
        provider = normalize_provider(row.get("provider_class", ""))
        if provider not in ALLOWED_PROVIDER_CLASSES:
            errors.append(f"{label}: provider_class is not recognized: {row.get('provider_class')}")
        remote_path = row.get("remote_path", "")
        if not remote_path:
            errors.append(f"{label}: remote_path is required")
        elif is_object_store_uri(remote_path):
            errors.append(f"{label}: cache remote_path must be a mounted filesystem path for v1 execution, not object storage: {remote_path}")
        elif not is_remote_path(remote_path):
            local_candidate = Path(remote_path.replace("<run_id>", "run"))
            if not local_candidate.is_absolute():
                errors.append(f"{label}: cache remote_path must be remote/provider storage or absolute configured workdir")
            elif path_is_under(local_candidate, repo_root):
                errors.append(f"{label}: cache path must not be under the repo root")
        if row.get("required") not in BOOLEAN_VALUES:
            errors.append(f"{label}: required must be true or false")
        try:
            free_space = float(row.get("free_space_gb", ""))
            if free_space < 0:
                errors.append(f"{label}: free_space_gb must be non-negative")
        except ValueError:
            errors.append(f"{label}: free_space_gb must be numeric")
        if row.get("retention_policy") not in CACHE_RETENTION_POLICIES:
            errors.append(f"{label}: retention_policy is not recognized: {row.get('retention_policy')}")
        if row.get("backup_policy") not in CACHE_BACKUP_POLICIES:
            errors.append(f"{label}: backup_policy is not recognized: {row.get('backup_policy')}")
        if row.get("required") == "true":
            seen_roles.add(row.get("cache_role", ""))

    for role in {
        "network_volume_mount",
        "database_cache",
        "search_result_cache",
        "run_root",
        "nextflow_cache",
        "sra_cache",
        "fast_scratch",
        "summary_export",
    }:
        if role not in seen_roles:
            errors.append(f"cache ledger missing required cache role: {role}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_search_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    required = {
        "schema_version",
        "run_scope",
        "stages",
        "search_engines",
        "database_ids",
        "query_strategy",
        "raw_output_policy",
        "summary_output_policy",
        "forbidden_modes",
    }
    missing = required - set(data)
    if missing:
        errors.append(f"search plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("search plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"search plan run_scope is not allowed: {data.get('run_scope')}")
    engines = set(data.get("search_engines") or [])
    if run_scope in {"candidate_search", "full_campaign", "full_public_mining"}:
        for engine in {"blast", "diamond", "mmseqs", "hmmer"}:
            if engine not in engines:
                errors.append(f"search plan missing required search engine: {engine}")
    forbidden = set(data.get("forbidden_modes") or [])
    if "ncbi_remote_blast_batch" not in forbidden:
        errors.append("search plan must forbid ncbi_remote_blast_batch")
    raw_policy = data.get("raw_output_policy", {})
    if not isinstance(raw_policy, dict):
        errors.append("search plan raw_output_policy must be an object")
    else:
        if raw_policy.get("local_copy") is not False:
            errors.append("search plan raw_output_policy.local_copy must be false")
        raw_path = str(raw_policy.get("path", ""))
        if raw_path and raw_path != "not_applicable" and not is_remote_path(raw_path) and not Path(raw_path).is_absolute():
            errors.append(f"search plan raw_output_policy.path must be remote/provider storage or an absolute configured workdir: {raw_path}")
    summary_policy = data.get("summary_output_policy", {})
    if not isinstance(summary_policy, dict):
        errors.append("search plan summary_output_policy must be an object")
    else:
        if summary_policy.get("local_copy") is not True:
            errors.append("search plan summary_output_policy.local_copy must be true")
    if run_scope in HEAVY_RUN_SCOPES and not data.get("database_ids"):
        errors.append("search plan database_ids must not be empty")
    if not data.get("stages"):
        errors.append("search plan stages must not be empty")
    if "ncbi_remote_blast_batch" in engines:
        errors.append("search plan search_engines cannot include ncbi_remote_blast_batch")
    if "ncbi_remote_blast_batch" not in forbidden:
        warnings.append("search plan should make remote BLAST ban explicit")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_remote_or_absolute(value: str, *, label: str) -> list[str]:
    if not value or value == "not_applicable":
        return []
    if is_remote_path(value):
        return []
    if Path(value).is_absolute():
        return []
    return [f"{label} must be remote/provider storage or an absolute configured workdir: {value}"]


def path_under_repo_error(value: str, repo_root: Path, *, label: str) -> str | None:
    if not value or value == "not_applicable" or is_remote_path(value) or is_object_store_uri(value):
        return None
    candidate = Path(value)
    if candidate.is_absolute() and path_is_under(candidate, repo_root):
        return f"{label} must not be under the repo root: {value}"
    return None


def validate_target_db_plan(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = (repo_root or Path.cwd()).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    missing = TARGET_DB_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"target DB plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("target DB plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"target DB plan run_scope is not allowed: {run_scope}")
    provider_db_root = str(data.get("provider_db_root", ""))
    errors.extend(validate_remote_or_absolute(provider_db_root, label="target DB plan provider_db_root"))
    repo_error = path_under_repo_error(provider_db_root, repo_root, label="target DB plan provider_db_root")
    if repo_error:
        errors.append(repo_error)
    if data.get("local_copy") is not False:
        errors.append("target DB plan local_copy must be false")
    outputs = data.get("outputs", {})
    if not isinstance(outputs, dict):
        errors.append("target DB plan outputs must be an object")
        outputs = {}
    else:
        for key, value in outputs.items():
            errors.extend(validate_remote_or_absolute(str(value), label=f"target DB plan output {key}"))
            repo_error = path_under_repo_error(str(value), repo_root, label=f"target DB plan output {key}")
            if repo_error:
                errors.append(repo_error)
    records = data.get("records", [])
    if not isinstance(records, list):
        errors.append("target DB plan records must be a list")
        records = []
    if run_scope in HEAVY_RUN_SCOPES and not records:
        errors.append("target DB plan records must not be empty for heavy scopes")
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"target DB plan record {idx} must be an object")
            continue
        for key in ["target_db_id", "dataset_id", "species", "resource_kind", "sequence_type", "provider_path", "index_policy"]:
            if not record.get(key):
                errors.append(f"target DB plan record {idx} missing {key}")
        sequence_type = str(record.get("sequence_type", ""))
        if sequence_type not in {"protein", "nucleotide", "genome", "annotation", "mixed"}:
            errors.append(f"target DB plan {record.get('target_db_id', idx)} sequence_type is not recognized: {sequence_type}")
        provider_path = str(record.get("provider_path", ""))
        errors.extend(validate_remote_or_absolute(provider_path, label=f"target DB plan {record.get('target_db_id', idx)} provider_path"))
        repo_error = path_under_repo_error(provider_path, repo_root, label=f"target DB plan {record.get('target_db_id', idx)} provider_path")
        if repo_error:
            errors.append(repo_error)
        if str(record.get("local_copy", "false")).lower() != "false":
            errors.append(f"target DB plan {record.get('target_db_id', idx)} local_copy must be false")
    index_targets = data.get("index_targets", [])
    if not isinstance(index_targets, list):
        errors.append("target DB plan index_targets must be a list")
        index_targets = []
    for idx, item in enumerate(index_targets, start=1):
        if not isinstance(item, dict):
            errors.append(f"target DB plan index target {idx} must be an object")
            continue
        if item.get("engine") not in {"blast", "diamond", "mmseqs", "miniprot", "none"}:
            errors.append(f"target DB plan index target {idx} has unsupported engine: {item.get('engine')}")
        if str(item.get("index_path", "")):
            errors.extend(validate_remote_or_absolute(str(item["index_path"]), label=f"target DB plan index target {idx} index_path"))
            repo_error = path_under_repo_error(str(item["index_path"]), repo_root, label=f"target DB plan index target {idx} index_path")
            if repo_error:
                errors.append(repo_error)
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_candidate_route_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    missing = CANDIDATE_ROUTE_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"candidate route plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("candidate route plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"candidate route plan run_scope is not allowed: {run_scope}")
    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("candidate route plan provider_class is not allowed")
    primary_route = str(data.get("primary_route", ""))
    if primary_route not in {
        "transcript_first_then_genome_anchor",
        "transcript_first_candidate_dossier",
        "genome_direct_rescue",
        "reference_only_or_metadata",
    }:
        errors.append(f"candidate route plan primary_route is not recognized: {primary_route}")
    if data.get("local_copy") is not True:
        errors.append("candidate route plan local_copy must be true")
    default_order = data.get("scientific_default_order", [])
    if not isinstance(default_order, list) or len(default_order) < 4:
        errors.append("candidate route plan scientific_default_order must list the biological route stages")
    records = data.get("route_records", [])
    if not isinstance(records, list):
        errors.append("candidate route plan route_records must be a list")
        records = []
    elif run_scope in HEAVY_RUN_SCOPES and not records:
        errors.append("candidate route plan route_records must not be empty for heavy scopes")
    for idx, row in enumerate(records, start=1):
        if not isinstance(row, dict):
            errors.append(f"candidate route plan route record {idx} must be an object")
            continue
        for key in ["dataset_id", "preferred_role", "preferred_route_stage", "current_runner_route", "claim_boundary"]:
            if not row.get(key):
                errors.append(f"candidate route plan route record {idx} missing {key}")
    missing_stages = data.get("missing_transcript_first_stages", [])
    blockers = data.get("strict_scientific_blockers", [])
    transcript_first_required = data.get("transcript_first_required_for_scientific_full") is True
    if transcript_first_required and missing_stages and "transcript_first_route_not_implemented_in_current_runner" not in blockers:
        errors.append("candidate route plan must block strict transcript-first readiness when transcript-first stages are missing")
    readiness = str(data.get("science_readiness", ""))
    if transcript_first_required and missing_stages and readiness == "full_route_ready":
        errors.append("candidate route plan cannot be full_route_ready while transcript-first stages are missing")
    if "transcript_first" in primary_route and data.get("direct_genome_tblastn_policy") != "rescue_only_not_primary_when_transcript_evidence_exists":
        errors.append("candidate route plan must mark direct genome tblastn as rescue-only when transcript evidence exists")
    if blockers:
        warnings.append("strict scientific route blockers present: " + ", ".join(map(str, blockers)))
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_orthology_anchor_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = ORTHOLOGY_ANCHOR_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"orthology/anchor plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("orthology/anchor plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"orthology/anchor plan run_scope is not allowed: {run_scope}")
    directions = set(data.get("search_directions") or [])
    missing_directions = SEARCH_DIRECTIONS - directions
    if missing_directions:
        errors.append(f"orthology/anchor plan missing search directions: {', '.join(sorted(missing_directions))}")
    classes = set(data.get("anchor_confidence_classes") or [])
    missing_classes = ANCHOR_CONFIDENCE_CLASSES - classes
    if missing_classes:
        errors.append(f"orthology/anchor plan missing anchor confidence classes: {', '.join(sorted(missing_classes))}")
    for container_key in ["inputs", "outputs"]:
        container = data.get(container_key, {})
        if not isinstance(container, dict) or not container:
            errors.append(f"orthology/anchor plan {container_key} must be a non-empty object")
            continue
        for key, value in container.items():
            if str(value).startswith("ledgers/"):
                continue
            errors.extend(validate_remote_or_absolute(str(value), label=f"orthology/anchor plan {container_key}.{key}"))
    methods = set(data.get("fallback_methods") or [])
    for required in {"exact_gff_id", "reciprocal_best_hit", "transcript_to_genome", "protein_to_genome_miniprot", "domain_only"}:
        if required not in methods:
            errors.append(f"orthology/anchor plan missing fallback method: {required}")
    if data.get("claim_policy") != "coordinates_required_for_cluster_claims":
        errors.append("orthology/anchor plan claim_policy must require coordinates for cluster claims")
    if data.get("local_copy") is not True:
        errors.append("orthology/anchor plan local_copy must be true")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_reciprocal_search_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = RECIPROCAL_SEARCH_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"reciprocal search plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("reciprocal search plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"reciprocal search plan run_scope is not allowed: {run_scope}")
    directions = set(data.get("search_directions") or [])
    for required in {"canonical_A_to_target_B", "target_B_to_canonical_A"}:
        if required not in directions:
            errors.append(f"reciprocal search plan missing direction: {required}")
    for container_key in ["inputs", "outputs"]:
        container = data.get(container_key, {})
        if not isinstance(container, dict) or not container:
            errors.append(f"reciprocal search plan {container_key} must be a non-empty object")
            continue
        for key, value in container.items():
            if str(value).startswith("ledgers/"):
                continue
            errors.extend(validate_remote_or_absolute(str(value), label=f"reciprocal search plan {container_key}.{key}"))
    policy = data.get("scoring_policy", {})
    if not isinstance(policy, dict):
        errors.append("reciprocal search plan scoring_policy must be an object")
    else:
        if policy.get("broad_family_penalty") != "required_without_orthogonal_evidence":
            errors.append("reciprocal search plan must penalize broad families without orthogonal evidence")
    if data.get("local_copy") is not True:
        errors.append("reciprocal search plan local_copy must be true")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_pathway_completeness_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = PATHWAY_COMPLETENESS_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"pathway completeness plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("pathway completeness plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"pathway completeness plan run_scope is not allowed: {run_scope}")
    statuses = set(data.get("statuses") or [])
    missing_statuses = PATHWAY_COMPLETENESS_STATUSES - statuses
    if missing_statuses:
        errors.append(f"pathway completeness plan missing statuses: {', '.join(sorted(missing_statuses))}")
    inputs = data.get("inputs", {})
    if not isinstance(inputs, dict) or not inputs:
        errors.append("pathway completeness plan inputs must be a non-empty object")
    else:
        for key, value in inputs.items():
            if str(value).startswith("ledgers/"):
                continue
            errors.extend(validate_remote_or_absolute(str(value), label=f"pathway completeness plan input {key}"))
    errors.extend(validate_remote_or_absolute(str(data.get("output", "")), label="pathway completeness plan output"))
    if run_scope == "full_campaign_24h" and data.get("budget_policy") != "defer_slow_lanes_with_deferred_by_budget_rows":
        errors.append("24h pathway completeness plan must emit deferred_by_budget rows when slow lanes are skipped")
    if data.get("local_copy") is not True:
        errors.append("pathway completeness plan local_copy must be true")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_db_bootstrap_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = DB_BOOTSTRAP_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"db bootstrap plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("db bootstrap plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"db bootstrap plan run_scope is not allowed: {run_scope}")
    errors.extend(validate_remote_or_absolute(str(data.get("db_cache_root", "")), label="db bootstrap plan db_cache_root"))
    if data.get("forbidden_local_paths") is not True:
        errors.append("db bootstrap plan forbidden_local_paths must be true")
    if data.get("execution_policy") != "provider_cache_only":
        errors.append("db bootstrap plan execution_policy must be provider_cache_only")
    records = data.get("records", [])
    if not isinstance(records, list):
        errors.append("db bootstrap plan records must be a list")
        records = []
    if run_scope in HEAVY_RUN_SCOPES and not records:
        errors.append("db bootstrap plan records must not be empty for heavy scopes")
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"db bootstrap plan record {idx} must be an object")
            continue
        for key in ["db_id", "engine", "remote_path", "priority", "run_gate", "bootstrap_strategy"]:
            if not record.get(key):
                errors.append(f"db bootstrap plan record {idx} missing {key}")
        if record.get("engine") and record.get("engine") not in DATABASE_ENGINES:
            errors.append(f"db bootstrap plan {record.get('db_id', idx)} has unknown engine")
        remote_path = str(record.get("remote_path", ""))
        if remote_path:
            errors.extend(validate_remote_or_absolute(remote_path, label=f"db bootstrap plan {record.get('db_id', idx)} remote_path"))
        if record.get("run_gate") == "optional_max":
            warnings.append(f"db bootstrap plan includes optional_max DB: {record.get('db_id', idx)}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_reference_import_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = REFERENCE_IMPORT_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"reference import plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("reference import plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"reference import plan run_scope is not allowed: {run_scope}")
    errors.extend(validate_remote_or_absolute(str(data.get("provider_inputs_dir", "")), label="reference import provider_inputs_dir"))
    if data.get("local_copy") is not False:
        errors.append("reference import plan local_copy must be false")
    records = data.get("records", [])
    if not isinstance(records, list) or not records:
        errors.append("reference import plan records must be a non-empty list")
        records = []
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"reference import plan record {idx} must be an object")
            continue
        for key in ["dataset_id", "accession", "data_role", "remote_path", "raw_artifact_policy", "planned_action"]:
            if not record.get(key):
                errors.append(f"reference import plan record {idx} missing {key}")
        if record.get("remote_path"):
            errors.extend(validate_remote_or_absolute(str(record["remote_path"]), label=f"reference import {record.get('dataset_id', idx)} remote_path"))
        if record.get("planned_action") not in {
            "metadata_only",
            "provider_fetchngs_or_sratools",
            "provider_fetchngs_or_sratools_timeboxed",
            "provider_public_reference_review",
        }:
            errors.append(f"reference import plan {record.get('dataset_id', idx)} has unknown planned_action")
    preferred = data.get("preferred_order", [])
    if not isinstance(preferred, list) or "existing_public_genome_protein_gff" not in preferred:
        warnings.append("reference import plan should prefer existing public genome/protein/GFF resources")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_data_materialization_plan(path: Path, *, execution_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    required = {
        "schema_version",
        "run_scope",
        "provider_class",
        "blessed_heavy_provider",
        "execution_maturity_levels",
        "provider_support",
        "allow_large_downloads_semantics",
        "target_search_requires_materialized_target_db",
        "candidate_promotion_required_gates",
        "records",
        "summary",
        "local_copy",
    }
    missing = required - set(data)
    if missing:
        errors.append(f"data materialization plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("data materialization plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"data materialization plan run_scope is not allowed: {run_scope}")
    if data.get("blessed_heavy_provider") != "runpod_pod":
        errors.append("data materialization plan blessed_heavy_provider must be runpod_pod")
    if data.get("target_search_requires_materialized_target_db") is not True:
        errors.append("data materialization plan must require materialized target DBs for target search")
    if data.get("local_copy") is not False:
        errors.append("data materialization plan local_copy must be false")
    semantics = str(data.get("allow_large_downloads_semantics", ""))
    if "does not by itself implement raw SRA" not in semantics:
        errors.append("data materialization plan must clarify that --allow-large-downloads alone is not raw-SRA execution")

    levels = data.get("execution_maturity_levels", [])
    level_names = {str(item.get("level", "")) for item in levels if isinstance(item, dict)}
    for level in {"L0_control_plane_ready", "L3_target_materialized_ready", "L4_raw_sra_pipeline_ready", "L5_claim_audited_dossier_ready"}:
        if level not in level_names:
            errors.append(f"data materialization plan missing maturity level: {level}")

    records = data.get("records", [])
    if not isinstance(records, list):
        errors.append("data materialization plan records must be a list")
        records = []
    if run_scope in HEAVY_RUN_SCOPES and not records:
        errors.append("data materialization plan records must not be empty for heavy scopes")
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"data materialization plan record {idx} must be an object")
            continue
        for key in ["dataset_id", "resource_kind", "sequence_type", "remote_path", "materialization_action", "current_runner_support", "execution_gate"]:
            if not record.get(key):
                errors.append(f"data materialization plan record {idx} missing {key}")
        remote_path = str(record.get("remote_path", ""))
        if remote_path:
            errors.extend(validate_remote_or_absolute(remote_path, label=f"data materialization {record.get('dataset_id', idx)} remote_path"))
        if record.get("resource_kind") == "target_raw_sequence_source" and str(record.get("current_runner_support", "")).startswith("deferred_"):
            message = f"raw target materialization is deferred for {record.get('dataset_id', idx)}"
            if execution_ready:
                warnings.append(message)
            else:
                warnings.append(message)
    summary = data.get("summary", {})
    if not isinstance(summary, dict):
        errors.append("data materialization plan summary must be an object")
    elif execution_ready:
        raw_count = int(summary.get("raw_sra_source_count", 0) or 0)
        materializable_count = int(summary.get("materializable_raw_sra_source_count", 0) or 0)
        if raw_count > 0 and materializable_count == 0:
            errors.append("execution-ready raw-SRA campaign requires at least one materializable target source or an existing target FASTA/protein/assembly")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_anchor_map_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = ANCHOR_MAP_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"anchor map plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("anchor map plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"anchor map plan run_scope is not allowed: {run_scope}")
    for key in ["candidate_hits", "resolved_references", "output"]:
        errors.extend(validate_remote_or_absolute(str(data.get(key, "")), label=f"anchor map plan {key}"))
    if data.get("fail_closed_without_coordinates") is not True:
        errors.append("anchor map plan fail_closed_without_coordinates must be true")
    if data.get("local_copy") is not True:
        errors.append("anchor map plan local_copy must be true")
    methods = data.get("methods", [])
    if not isinstance(methods, list) or not methods:
        errors.append("anchor map plan methods must be a non-empty list")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_neighborhood_extract_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = NEIGHBORHOOD_EXTRACT_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"neighborhood extract plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("neighborhood extract plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"neighborhood extract plan run_scope is not allowed: {run_scope}")
    errors.extend(validate_remote_or_absolute(str(data.get("candidate_anchors", "")), label="neighborhood extract candidate_anchors"))
    outputs = data.get("outputs", {})
    if not isinstance(outputs, dict) or not outputs:
        errors.append("neighborhood extract plan outputs must be a non-empty object")
        outputs = {}
    for key, value in outputs.items():
        errors.extend(validate_remote_or_absolute(str(value), label=f"neighborhood extract output {key}"))
    for key in ["window_kb", "window_genes"]:
        try:
            value = int(data.get(key, 0))
            if value <= 0:
                errors.append(f"neighborhood extract plan {key} must be positive")
        except (TypeError, ValueError):
            errors.append(f"neighborhood extract plan {key} must be an integer")
    profiles = data.get("enzyme_family_profiles", [])
    if not isinstance(profiles, list) or "methyltransferase" not in profiles:
        errors.append("neighborhood extract plan must include methyltransferase profile")
    if data.get("claim_policy") != "neighborhood_supported_not_product_validated":
        errors.append("neighborhood extract plan claim_policy must preserve product-validation boundary")
    if data.get("local_copy") is not True:
        errors.append("neighborhood extract plan local_copy must be true")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_query_resolution_plan(path: Path, *, execution_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    missing = QUERY_RESOLUTION_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"query resolution plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("query resolution plan schema_version must be 1")
    output_fasta = str(data.get("output_fasta", ""))
    if output_fasta and output_fasta != "not_applicable" and not is_remote_path(output_fasta) and not Path(output_fasta).is_absolute():
        errors.append(f"query resolution plan output_fasta must be provider/remote storage or absolute configured workdir: {output_fasta}")
    records = data.get("records", [])
    if not isinstance(records, list) or not records:
        errors.append("query resolution plan records must be a non-empty list")
        records = []
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"query resolution plan record {idx} must be an object")
            continue
        for key in ["query_id", "query_name", "resolution_action", "sequence_type"]:
            if not record.get(key):
                errors.append(f"query resolution plan record {idx} missing {key}")
        if record.get("resolution_action") not in {
            "fetch_public_accession",
            "use_embedded_query_fasta",
            "resolve_public_seed_before_run",
            "domain_family_profile",
            "context_only_no_sequence",
        }:
            errors.append(f"query resolution plan {record.get('query_id', idx)} has unknown resolution_action")
    blockers = data.get("blocking_unresolved_query_ids", [])
    if blockers:
        message = "query resolution plan has unresolved high-confidence seeds: " + ", ".join(map(str, blockers))
        if execution_ready:
            errors.append(message)
        else:
            warnings.append(message)
    warning_ids = data.get("warning_unresolved_query_ids", [])
    if warning_ids:
        warnings.append("query resolution plan has unresolved medium-confidence seeds: " + ", ".join(map(str, warning_ids)))
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_decoy_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    missing = DECOY_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"decoy plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("decoy plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"decoy plan run_scope is not allowed: {run_scope}")
    records = data.get("records", [])
    if not isinstance(records, list):
        errors.append("decoy plan records must be a list")
        records = []
    if run_scope in HEAVY_RUN_SCOPES and not records:
        warnings.append("heavy decoy plan has no broad-family or negative-control records")
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"decoy plan record {idx} must be an object")
            continue
        for key in ["query_id", "family_scope", "negative_controls", "expected_false_positive_risk", "required_decoy_strategy"]:
            if not record.get(key):
                errors.append(f"decoy plan record {idx} missing {key}")
        if record.get("expected_false_positive_risk") not in {"low", "medium", "high"}:
            errors.append(f"decoy plan {record.get('query_id', idx)} has invalid expected_false_positive_risk")
    if data.get("missing_negative_control_query_ids"):
        errors.append(
            "decoy plan has broad-family queries without negative controls: "
            + ", ".join(map(str, data["missing_negative_control_query_ids"]))
        )
    enforcement = data.get("enforcement", {})
    if not isinstance(enforcement, dict):
        errors.append("decoy plan enforcement must be an object")
    else:
        if enforcement.get("broad_family_product_claims") != "forbidden_without_orthogonal_evidence":
            errors.append("decoy plan must forbid broad-family product claims without orthogonal evidence")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_run_economics(path: Path, *, execution_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    missing = RUN_ECONOMICS_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"run economics missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("run economics schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"run economics run_scope is not allowed: {run_scope}")
    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("run economics provider_class is not allowed")

    db_budget = data.get("database_budget", {})
    if not isinstance(db_budget, dict):
        errors.append("run economics database_budget must be an object")
        db_budget = {}
    elif run_scope in HEAVY_RUN_SCOPES and int(db_budget.get("required_enabled_count", 0) or 0) <= 0:
        errors.append("run economics requires at least one enabled required database for heavy scopes")

    cache_budget = data.get("cache_budget", {})
    if not isinstance(cache_budget, dict):
        errors.append("run economics cache_budget must be an object")
        cache_budget = {}
    else:
        if run_scope in HEAVY_RUN_SCOPES and not cache_budget.get("search_result_cache_enabled"):
            errors.append("run economics requires search_result_cache_enabled for heavy scopes")
        try:
            free_space = float(cache_budget.get("volume_min_free_space_gb", 0))
            if run_scope in HEAVY_RUN_SCOPES and free_space <= 0:
                errors.append("run economics volume_min_free_space_gb must be positive for heavy scopes")
        except (TypeError, ValueError):
            errors.append("run economics volume_min_free_space_gb must be numeric")

    cost_controls = data.get("cost_controls", [])
    if not isinstance(cost_controls, list) or not cost_controls:
        errors.append("run economics cost_controls must be a non-empty list")

    runtime_budget = data.get("runtime_budget", {})
    if run_scope == "full_campaign_24h":
        if not isinstance(runtime_budget, dict):
            errors.append("full_campaign_24h run economics requires runtime_budget object")
        else:
            try:
                target_hours = float(runtime_budget.get("target_runtime_hours", 0))
                hard_stop_hours = float(runtime_budget.get("hard_stop_hours", 0))
            except (TypeError, ValueError):
                target_hours = hard_stop_hours = 0
                errors.append("full_campaign_24h runtime_budget hours must be numeric")
            if target_hours <= 0 or target_hours > 24:
                errors.append("full_campaign_24h target_runtime_hours must be positive and <= 24")
            if hard_stop_hours <= 0 or hard_stop_hours > 24:
                errors.append("full_campaign_24h hard_stop_hours must be positive and <= 24")
            if runtime_budget.get("completion_definition") != "complete_summary_dossier_with_deferred_lane_manifest":
                errors.append("full_campaign_24h must complete as a summary dossier with deferred lane manifest")
            if runtime_budget.get("budget_policy") != "finish_with_caveats_rather_than_extend_runtime":
                errors.append("full_campaign_24h must finish with caveats rather than extend runtime")

    blockers = data.get("launch_blockers", [])
    if blockers:
        message = "run economics launch blockers: " + ", ".join(map(str, blockers))
        if execution_ready:
            errors.append(message)
        else:
            warnings.append(message)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_workflow_class_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = WORKFLOW_CLASS_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"workflow class plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("workflow class plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"workflow class plan run_scope is not allowed: {run_scope}")
    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("workflow class plan provider_class is not allowed")
    if data.get("local_copy") is not True:
        errors.append("workflow class plan local_copy must be true")
    if data.get("heavy_artifact_policy") != "provider_workdir_only":
        errors.append("workflow class plan heavy_artifact_policy must be provider_workdir_only")
    records = data.get("workflow_classes", [])
    if not isinstance(records, list) or not records:
        errors.append("workflow class plan workflow_classes must be a non-empty list")
        records = []
    seen = set()
    for idx, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"workflow class plan record {idx} must be an object")
            continue
        class_id = str(record.get("workflow_class", ""))
        seen.add(class_id)
        if class_id not in WORKFLOW_CLASSES:
            errors.append(f"workflow class plan has unknown workflow_class: {class_id}")
        status = str(record.get("status", ""))
        if status not in WORKFLOW_CLASS_STATUSES:
            errors.append(f"workflow class {class_id or idx}: status is not recognized: {status}")
        for key in ["activation_reason", "roi", "description", "claim_boundary"]:
            if not record.get(key):
                errors.append(f"workflow class {class_id or idx}: missing {key}")
        for key in ["input_requirements", "required_tools", "expected_outputs"]:
            if not isinstance(record.get(key), list):
                errors.append(f"workflow class {class_id or idx}: {key} must be a list")
        if record.get("local_copy") is not True:
            errors.append(f"workflow class {class_id or idx}: local_copy must be true")
    missing_classes = WORKFLOW_CLASSES - seen
    if missing_classes:
        errors.append(f"workflow class plan missing workflow classes: {', '.join(sorted(missing_classes))}")
    if run_scope == "full_campaign_24h":
        deferred_budget = [record for record in records if record.get("status") == "deferred_by_budget"]
        if not deferred_budget:
            errors.append("full_campaign_24h workflow class plan must include deferred_by_budget lanes")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_lane_activation_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = LANE_ACTIVATION_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"lane activation plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("lane activation plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"lane activation plan run_scope is not allowed: {run_scope}")
    if data.get("local_copy") is not True:
        errors.append("lane activation plan local_copy must be true")
    all_named = set()
    for key in ["activated_lanes", "blocked_lanes", "deferred_lanes"]:
        values = data.get(key, [])
        if not isinstance(values, list):
            errors.append(f"lane activation plan {key} must be a list")
            continue
        all_named.update(map(str, values))
        unknown = set(map(str, values)) - WORKFLOW_CLASSES
        if unknown:
            errors.append(f"lane activation plan {key} contains unknown workflow classes: {', '.join(sorted(unknown))}")
    if "reference_first_anchor_mining" not in all_named:
        errors.append("lane activation plan must account for reference_first_anchor_mining")
    matrix = data.get("activation_matrix", [])
    if not isinstance(matrix, list) or not matrix:
        errors.append("lane activation plan activation_matrix must be a non-empty list")
        matrix = []
    for idx, row in enumerate(matrix, start=1):
        if not isinstance(row, dict):
            errors.append(f"lane activation matrix row {idx} must be an object")
            continue
        if row.get("workflow_class") not in WORKFLOW_CLASSES:
            errors.append(f"lane activation matrix row {idx} has unknown workflow_class: {row.get('workflow_class')}")
        if row.get("status") not in WORKFLOW_CLASS_STATUSES:
            errors.append(f"lane activation matrix row {idx} has unknown status: {row.get('status')}")
        if not row.get("reason"):
            errors.append(f"lane activation matrix row {idx} missing reason")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_evidence_escalation_plan(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    missing = EVIDENCE_ESCALATION_PLAN_REQUIRED_KEYS - set(data)
    if missing:
        errors.append(f"evidence escalation plan missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("evidence escalation plan schema_version must be 1")
    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append(f"evidence escalation plan run_scope is not allowed: {run_scope}")
    if data.get("local_copy") is not True:
        errors.append("evidence escalation plan local_copy must be true")
    rules = data.get("escalation_rules", [])
    if not isinstance(rules, list) or not rules:
        errors.append("evidence escalation plan escalation_rules must be a non-empty list")
        rules = []
    for idx, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            errors.append(f"evidence escalation rule {idx} must be an object")
            continue
        for key in ["evidence_state", "next_workflow_class", "required_before_claim_upgrade", "claim_boundary"]:
            if not rule.get(key):
                errors.append(f"evidence escalation rule {idx} missing {key}")
        if rule.get("next_workflow_class") not in WORKFLOW_CLASSES:
            errors.append(f"evidence escalation rule {idx} next_workflow_class is unknown: {rule.get('next_workflow_class')}")
    forbidden = set(data.get("forbidden_upgrades") or [])
    for required in {"transcriptome_only_to_physical_cluster", "domain_only_to_product_chemistry"}:
        if required not in forbidden:
            errors.append(f"evidence escalation plan missing forbidden upgrade: {required}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_summary_table(
    path: Path,
    *,
    required_columns: set[str],
    label: str,
    repo_root: Path | None = None,
    allow_empty: bool = False,
) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    repo_root = (repo_root or Path.cwd()).resolve()
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = required_columns - fields
    if missing:
        errors.append(f"{label} missing columns: {', '.join(sorted(missing))}")
    if not rows and not allow_empty:
        errors.append(f"{label} must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        row_label = next((row.get(key, "") for key in ["candidate_id", "isoform_id", "workflow_class", "assembly_id", "graph_id", "sample_id"] if row.get(key)), f"row {idx}")
        status = row.get("review_status")
        if "review_status" in required_columns and status not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label} {row_label}: review_status is not recognized: {status}")
        for field, value in row.items():
            if not value or value in {"remote_pending", "not_applicable", "none", "blocked"}:
                continue
            field_lower = field.lower()
            if "path" not in field_lower and field_lower not in {"remote_workdir", "interval"}:
                continue
            candidate = Path(value)
            if candidate.is_absolute() and path_is_under(candidate, repo_root):
                errors.append(f"{label} {row_label}: {field} must not be under the repo root: {value}")
            if has_raw_or_large_suffix(value) and candidate.is_absolute() and path_is_under(candidate, repo_root):
                errors.append(f"{label} {row_label}: raw/heavy artifact path is under repo root: {value}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_route_annotation_ledger(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    result = validate_summary_table(
        path,
        required_columns=ROUTE_ANNOTATION_LEDGER_COLUMNS,
        label="route annotation ledger",
        repo_root=repo_root,
    )
    errors = list(result["errors"])
    warnings = list(result["warnings"])
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return result

    for idx, row in enumerate(rows, start=2):
        label = row.get("source_id") or f"row {idx}"
        route = row.get("recommended_route", "")
        claim_ceiling = row.get("claim_ceiling", "")
        controls_ok = row.get("controls_ok", "").lower()

        if route not in ROUTE_ANNOTATION_ROUTES:
            errors.append(f"route annotation ledger {label}: recommended_route is not recognized: {route}")
        if claim_ceiling not in ROUTE_CLAIM_CEILINGS:
            errors.append(f"route annotation ledger {label}: claim_ceiling is not recognized: {claim_ceiling}")
        if controls_ok not in {"true", "false"}:
            errors.append(f"route annotation ledger {label}: controls_ok must be true or false")

        counts: dict[str, int] = {}
        for field in ["proteome_count", "gff_protein_count", "protein_gff_join_count"]:
            try:
                value = int(row.get(field, ""))
            except ValueError:
                errors.append(f"route annotation ledger {label}: {field} must be an integer")
                continue
            if value < 0:
                errors.append(f"route annotation ledger {label}: {field} must be non-negative")
            counts[field] = value

        if route == "annotation_direct":
            if controls_ok != "true":
                errors.append(f"route annotation ledger {label}: annotation_direct requires controls_ok=true")
            if counts.get("protein_gff_join_count", 0) <= 0:
                errors.append(f"route annotation ledger {label}: annotation_direct requires a positive protein/GFF join count")
            if claim_ceiling != "L3_annotation_neighborhood_ready":
                errors.append(f"route annotation ledger {label}: annotation_direct must use L3_annotation_neighborhood_ready")
        elif route in {"annotation_direct_then_context", "genome_context", "tblastn_rescue", "transcriptome_only"} and controls_ok != "true":
            errors.append(f"route annotation ledger {label}: {route} requires controls_ok=true")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_claim_levels(path: Path) -> dict[str, Any]:
    result = validate_summary_table(path, required_columns=CLAIM_LEVEL_COLUMNS, label="claim levels")
    errors = list(result["errors"])
    warnings = list(result["warnings"])
    rows, _ = read_tsv(path)
    seen = {row.get("claim_level", "") for row in rows}
    for required in {"candidate", "genome_localized_candidate", "neighborhood_hypothesis", "pathway_hypothesis"}:
        if required not in seen:
            errors.append(f"claim levels missing required claim level: {required}")
    for row in rows:
        if "validated" in row.get("allowed_statement", "").lower() and row.get("claim_level") != "validated_elsewhere":
            warnings.append(f"claim level {row.get('claim_level')}: check validated wording")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_workflow_deferred_lanes(path: Path, *, require_deferred_budget: bool = False) -> dict[str, Any]:
    result = validate_summary_table(path, required_columns=WORKFLOW_DEFERRED_LANE_COLUMNS, label="workflow deferred lanes")
    errors = list(result["errors"])
    warnings = list(result["warnings"])
    rows, _ = read_tsv(path)
    seen_budget = False
    for row in rows:
        if row.get("workflow_class") not in WORKFLOW_CLASSES:
            errors.append(f"workflow deferred lanes unknown workflow_class: {row.get('workflow_class')}")
        if row.get("deferred_status") not in WORKFLOW_CLASS_STATUSES:
            errors.append(f"workflow deferred lanes {row.get('workflow_class')}: deferred_status is not recognized")
        if row.get("deferred_status") == "deferred_by_budget":
            seen_budget = True
    if require_deferred_budget and not seen_budget:
        errors.append("workflow deferred lanes must include at least one deferred_by_budget row")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_expression_matrix_manifest(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = (repo_root or Path.cwd()).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    for key in ["schema_version", "matrix_id", "status", "local_copy", "raw_matrix_policy", "review_status"]:
        if key not in data:
            errors.append(f"expression matrix manifest missing key: {key}")
    if data.get("schema_version") != 1:
        errors.append("expression matrix manifest schema_version must be 1")
    if data.get("local_copy") is not True:
        errors.append("expression matrix manifest local_copy must be true")
    if data.get("raw_matrix_policy") != "provider_workdir_only":
        errors.append("expression matrix manifest raw_matrix_policy must be provider_workdir_only")
    if data.get("review_status") not in ALLOWED_REVIEW_STATUSES:
        errors.append("expression matrix manifest review_status is not recognized")
    for key in ["matrix_path", "counts_path"]:
        value = str(data.get(key, ""))
        if value and value not in {"not_applicable", "remote_pending"}:
            candidate = Path(value)
            if candidate.is_absolute() and path_is_under(candidate, repo_root):
                errors.append(f"expression matrix manifest {key} must not be under repo root")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_longread_qc(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    for key in ["schema_version", "status", "raw_reads_policy", "review_status"]:
        if key not in data:
            errors.append(f"longread QC missing key: {key}")
    if data.get("schema_version") != 1:
        errors.append("longread QC schema_version must be 1")
    if data.get("raw_reads_policy") != "provider_workdir_only":
        errors.append("longread QC raw_reads_policy must be provider_workdir_only")
    if data.get("review_status") not in ALLOWED_REVIEW_STATUSES:
        errors.append("longread QC review_status is not recognized")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_tool_requirements(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    if data.get("schema_version") != 1:
        errors.append("tool requirements schema_version must be 1")
    tools = data.get("required_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("tool requirements required_tools must be a non-empty list")
        tools = []

    seen: set[str] = set()
    for idx, tool in enumerate(tools, start=1):
        if not isinstance(tool, dict):
            errors.append(f"tool requirements item {idx} must be an object")
            continue
        name = str(tool.get("tool", ""))
        seen.add(name)
        for key in ["tool", "executable", "required_for", "version_command", "license_class"]:
            if not tool.get(key):
                errors.append(f"tool requirements {name or idx}: missing {key}")
        if tool.get("license_class") not in LICENSE_CLASSES:
            errors.append(f"tool requirements {name}: license_class is not recognized: {tool.get('license_class')}")

    for required_tool in {
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
        "hisat2",
        "stringtie",
        "samtools",
        "gffread",
        "TransDecoder.LongOrfs",
        "TransDecoder.Predict",
        "nextflow",
    }:
        if required_tool not in seen:
            errors.append(f"tool requirements missing required tool: {required_tool}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_provider_payload(path: Path, repo_root: Path | None = None, *, execution_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = (repo_root or Path.cwd()).resolve()

    if path.suffix == ".sh":
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}
        if "set -euo pipefail" not in text:
            errors.append(f"provider shell payload should use strict bash mode: {path.name}")
        if "RUNPOD_API_KEY=" in text or "TOKEN=" in text:
            errors.append(f"provider shell payload must not embed secrets: {path.name}")
        return {"ok": not errors, "errors": errors, "warnings": warnings}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    required = {
        "schema_version",
        "provider_class",
        "command",
        "artifact_boundaries",
        "summary_sync_policy",
    }
    missing = required - set(data)
    if missing:
        errors.append(f"provider payload missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("provider payload schema_version must be 1")
    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("provider payload provider_class is not allowed")

    command = data.get("command")
    if not isinstance(command, list) or not command:
        errors.append("provider payload command must be a non-empty list")

    boundaries = data.get("artifact_boundaries", {})
    if not isinstance(boundaries, dict):
        errors.append("provider payload artifact_boundaries must be an object")
    else:
        if boundaries.get("large_artifacts") != "provider_workdir_only":
            errors.append("provider payload large_artifacts boundary must be provider_workdir_only")
        if boundaries.get("local_sync") != "summaries_only":
            errors.append("provider payload local_sync boundary must be summaries_only")

    summary_sync_policy = data.get("summary_sync_policy", {})
    if not isinstance(summary_sync_policy, dict):
        errors.append("provider payload summary_sync_policy must be an object")
    else:
        if summary_sync_policy.get("mode") != "pull_summaries_only":
            errors.append("provider payload summary_sync_policy.mode must be pull_summaries_only")
        include = summary_sync_policy.get("include")
        exclude = summary_sync_policy.get("exclude")
        if not isinstance(include, list) or not include:
            errors.append("provider payload summary_sync_policy.include must be a non-empty list")
        if not isinstance(exclude, list) or not exclude:
            errors.append("provider payload summary_sync_policy.exclude must be a non-empty list")

    for key in ["heavy_workdir", "db_cache_root", "summary_dir"]:
        value = str(data.get(key, ""))
        if value and not is_remote_path(value):
            local_candidate = Path(value)
            if local_candidate.is_absolute() and path_is_under(local_candidate, repo_root):
                errors.append(f"provider payload {key} must not be under the repo root")

    if provider == "runpod_pod":
        for key in ["network_volume_id", "datacenter", "mount_path", "image"]:
            if not data.get(key):
                errors.append(f"RunPod provider payload missing {key}")
        if data.get("mount_path") != "/workspace":
            errors.append("RunPod provider payload mount_path must be /workspace")
        image = str(data.get("image", ""))
        if image.lower() in PLACEHOLDER_IMAGE_VALUES or image.endswith(":unbuilt"):
            message = "RunPod provider payload image is a placeholder"
            if execution_ready:
                errors.append(message)
            else:
                warnings.append(message)
        image_policy = data.get("image_policy", {})
        if not isinstance(image_policy, dict):
            errors.append("RunPod provider payload image_policy must be an object")
        else:
            if image_policy.get("digest_pinned_required_for_execution_ready") is not True:
                errors.append("RunPod provider payload image_policy must require digest-pinned execution-ready images")
            if image_policy.get("first_boot_mamba_install") != "emergency_only":
                warnings.append("RunPod provider payload should treat first-boot mamba install as emergency_only")
            if image_policy.get("first_boot_install_allowed_for_standard_launch") is not False:
                errors.append("RunPod provider payload must forbid first-boot package installation for standard launches")
            if image_policy.get("tool_install_strategy") != "baked_image_required":
                errors.append("RunPod provider payload image_policy.tool_install_strategy must be baked_image_required")
            if image_policy.get("requires_openjdk_for_nextflow") is not True:
                errors.append("RunPod provider payload image_policy must require OpenJDK for Nextflow")
            required_boot_tools = image_policy.get("required_boot_tools", [])
            if not isinstance(required_boot_tools, list):
                errors.append("RunPod provider payload image_policy.required_boot_tools must be a list")
            else:
                for tool in [
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
                ]:
                    if tool not in required_boot_tools:
                        errors.append(f"RunPod provider payload image_policy.required_boot_tools missing {tool}")
        image_digest = str(data.get("image_digest", ""))
        if not image_digest.startswith("sha256:") or len(image_digest) < len("sha256:") + 32:
            message = "RunPod provider payload image_digest must be resolved to a digest-pinned image"
            if execution_ready:
                errors.append(message)
            else:
                warnings.append(message)
        registry_auth_policy = data.get("registry_auth_policy", {})
        if not isinstance(registry_auth_policy, dict):
            errors.append("RunPod provider payload registry_auth_policy must be an object")
        else:
            if registry_auth_policy.get("schema_version") != 1:
                errors.append("RunPod provider payload registry_auth_policy schema_version must be 1")
            if registry_auth_policy.get("container_registry_auth_id_payload_field") != "containerRegistryAuthId":
                errors.append("RunPod provider payload registry_auth_policy must declare containerRegistryAuthId payload field")
            auth_env_names = registry_auth_policy.get("container_registry_auth_id_env_names", [])
            public_env_names = registry_auth_policy.get("public_image_assertion_env_names", [])
            if not isinstance(auth_env_names, list) or not auth_env_names:
                errors.append("RunPod provider payload registry_auth_policy must list container registry auth env names")
            if not isinstance(public_env_names, list) or not public_env_names:
                errors.append("RunPod provider payload registry_auth_policy must list public image assertion env names")
            if registry_auth_policy.get("auth_likely_required") and registry_auth_policy.get("registry_host") in {"", "docker.io"}:
                warnings.append("RunPod provider payload registry_auth_policy marks a low-information registry host as auth-sensitive")
            if registry_auth_missing(registry_auth_policy):
                message = (
                    "RunPod provider payload image registry likely requires auth; set "
                    "GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID/RUNPOD_CONTAINER_REGISTRY_AUTH_ID "
                    "or assert a proven public-pull image with GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL=1"
                )
                if execution_ready:
                    errors.append(message)
                else:
                    warnings.append(message)
        for key in ["network_volume_id", "datacenter"]:
            value = str(data.get(key, ""))
            if not value or value.startswith("env:"):
                message = f"RunPod provider payload {key} must be resolved for execution-ready validation"
                if execution_ready:
                    errors.append(message)
                else:
                    warnings.append(message)
        env_names = data.get("env_var_names", [])
        if not isinstance(env_names, list):
            errors.append("RunPod provider payload env_var_names must be a list")
        else:
            for value in env_names:
                if "=" in str(value):
                    errors.append("RunPod provider payload env_var_names must contain names only")
        lifecycle_policy = data.get("pod_lifecycle_policy", {})
        if not isinstance(lifecycle_policy, dict):
            errors.append("RunPod provider payload pod_lifecycle_policy must be an object")
        else:
            self_stop = lifecycle_policy.get("self_stop_on_completion") is True
            operator_cleanup = lifecycle_policy.get("operator_side_cleanup_required") is True
            if not (self_stop or operator_cleanup):
                errors.append("RunPod provider payload must declare self-stop or operator-side cleanup to avoid restart loops")
            if operator_cleanup:
                if lifecycle_policy.get("provider_api_key_inside_pod") is not False:
                    errors.append("RunPod operator-side cleanup requires provider_api_key_inside_pod=false")
                try:
                    idle_seconds = int(lifecycle_policy.get("idle_after_completion_seconds", 0))
                    if idle_seconds < 60:
                        errors.append("RunPod operator-side cleanup needs idle_after_completion_seconds >= 60")
                except (TypeError, ValueError):
                    errors.append("RunPod operator-side cleanup idle_after_completion_seconds must be an integer")
            if lifecycle_policy.get("avoid_restart_loop") is not True:
                errors.append("RunPod provider payload must declare restart-loop avoidance")
            if lifecycle_policy.get("watch_runtime_uptime_seconds_required") is not True:
                errors.append("RunPod provider payload must require runtime uptime checks")
            if lifecycle_policy.get("stop_not_delete_until_summary_verified") is not True:
                errors.append("RunPod provider payload must stop, not delete, until summaries are verified")
            try:
                timeout = int(lifecycle_policy.get("runtime_null_timeout_seconds", 0))
                if timeout < 300:
                    errors.append("RunPod provider payload runtime_null_timeout_seconds must be at least 300")
            except (TypeError, ValueError):
                errors.append("RunPod provider payload runtime_null_timeout_seconds must be numeric")
            status_file = str(lifecycle_policy.get("status_file", ""))
            if not status_file.startswith("/workspace/"):
                errors.append("RunPod provider payload status_file must be under /workspace")
        runpod_api_policy = data.get("runpod_api_policy", {})
        if not isinstance(runpod_api_policy, dict):
            errors.append("RunPod provider payload runpod_api_policy must be an object")
        else:
            if runpod_api_policy.get("rest_endpoint") != "https://rest.runpod.io/v1/pods":
                errors.append("RunPod provider payload runpod_api_policy.rest_endpoint must point to RunPod pod REST API")
            status_checks = runpod_api_policy.get("status_checks", [])
            if not isinstance(status_checks, list) or not any("runtime.uptimeInSeconds" in str(check) for check in status_checks):
                errors.append("RunPod provider payload runpod_api_policy must require runtime.uptimeInSeconds checks")
        db_bootstrap_policy = data.get("db_bootstrap_policy", {})
        if not isinstance(db_bootstrap_policy, dict):
            errors.append("RunPod provider payload db_bootstrap_policy must be an object")
        else:
            if db_bootstrap_policy.get("required_database_fail_closed") is not True:
                errors.append("RunPod provider payload must fail closed when required DBs are missing")
            if db_bootstrap_policy.get("allow_large_downloads_default") is not False:
                errors.append("RunPod provider payload allow_large_downloads_default must be false")
        if isinstance(summary_sync_policy, dict):
            if summary_sync_policy.get("preferred_transport") != "runpod_s3_or_configured_summary_endpoint":
                warnings.append("RunPod provider payload should prefer RunPod S3 or a configured summary endpoint for summaries")
            if summary_sync_policy.get("fallback_transport") != "short_lived_http_pull_pod":
                warnings.append("RunPod provider payload should document a short-lived HTTP pull pod fallback")
            if summary_sync_policy.get("avoid_capacity_dependent_pull_pod_when_s3_available") is not True:
                warnings.append("RunPod provider payload should avoid capacity-dependent pull pods when S3 is available")
            if "{datacenter}" not in str(summary_sync_policy.get("s3_endpoint_template", "")):
                warnings.append("RunPod provider payload should record the RunPod S3 endpoint template")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def normalize_include_entry(entry: Any) -> tuple[str, bool]:
    if isinstance(entry, str):
        return entry, False
    if isinstance(entry, dict):
        return str(entry.get("path", "")), bool(entry.get("required", False))
    return "", False


def validate_artifact_pull_manifest(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root_resolved = (repo_root or Path.cwd()).resolve()
    try:
        data = load_yaml(path)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - preflight reports malformed operator files.
        return {"ok": False, "errors": [f"artifact pull manifest invalid: {exc}"], "warnings": []}

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["artifact pull manifest root must be an object"], "warnings": []}

    required = {
        "schema_version",
        "run_id",
        "provider_class",
        "mode",
        "remote_summary_dir",
        "include",
        "exclude",
        "max_file_bytes",
        "max_total_bytes",
        "checksum_mode",
        "raw_artifact_policy",
        "local_destination_policy",
    }
    missing = required - set(data)
    if missing:
        errors.append(f"artifact pull manifest missing root keys: {', '.join(sorted(missing))}")
    if data.get("schema_version") != 1:
        errors.append("artifact pull manifest schema_version must be 1")
    if data.get("mode") != "pull_summaries_only":
        errors.append("artifact pull manifest mode must be pull_summaries_only")
    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("artifact pull manifest provider_class is not allowed")
    remote_summary_dir = str(data.get("remote_summary_dir", ""))
    if remote_summary_dir:
        remote_summary_path = Path(remote_summary_dir)
        remote_summary_ok = is_remote_path(remote_summary_dir) or remote_summary_dir == "summary"
        if not remote_summary_ok and remote_summary_path.is_absolute():
            if provider == "local_lite":
                errors.append("artifact pull manifest local_lite remote_summary_dir must be summary")
            elif path_is_under(remote_summary_path, repo_root_resolved):
                errors.append("artifact pull manifest absolute remote_summary_dir must not be under the repo root")
            else:
                remote_summary_ok = True
        if not remote_summary_ok:
            errors.append("artifact pull manifest remote_summary_dir must be remote, summary, or an absolute path outside the repo")

    try:
        max_file_bytes = int(data.get("max_file_bytes", 0))
        if max_file_bytes <= 0 or max_file_bytes > DEFAULT_LOCAL_SUMMARY_LIMIT_BYTES:
            errors.append("artifact pull manifest max_file_bytes must be >0 and <= local summary limit")
    except (TypeError, ValueError):
        errors.append("artifact pull manifest max_file_bytes must be numeric")
        max_file_bytes = 0
    try:
        max_total_bytes = int(data.get("max_total_bytes", 0))
        if max_total_bytes < max_file_bytes:
            errors.append("artifact pull manifest max_total_bytes must be at least max_file_bytes")
    except (TypeError, ValueError):
        errors.append("artifact pull manifest max_total_bytes must be numeric")

    if data.get("checksum_mode") not in {"require_sha256_after_pull", "verify_when_declared"}:
        errors.append("artifact pull manifest checksum_mode is not allowed")
    if data.get("raw_artifact_policy") != "forbid":
        errors.append("artifact pull manifest raw_artifact_policy must be forbid")

    include = data.get("include", [])
    if not isinstance(include, list) or not include:
        errors.append("artifact pull manifest include must be a non-empty list")
        include = []
    required_seen = False
    seen_paths: set[str] = set()
    for index, entry in enumerate(include):
        rel, required_flag = normalize_include_entry(entry)
        if not rel:
            errors.append(f"artifact pull manifest include[{index}] missing path")
            continue
        if rel in seen_paths:
            errors.append(f"artifact pull manifest duplicate include path: {rel}")
        seen_paths.add(rel)
        required_seen = required_seen or required_flag
        candidate = Path(rel)
        if candidate.is_absolute() or ".." in candidate.parts:
            errors.append(f"artifact pull manifest include path must be relative and contained: {rel}")
        if has_raw_or_large_suffix(rel):
            errors.append(f"artifact pull manifest include cannot pull raw/large artifact: {rel}")
        if rel.startswith(("work/", "databases/", "nextflow-work/")):
            errors.append(f"artifact pull manifest include cannot pull heavy workdir path: {rel}")
    if include and not required_seen:
        warnings.append("artifact pull manifest has no required include paths")

    exclude = data.get("exclude", [])
    if not isinstance(exclude, list) or not exclude:
        errors.append("artifact pull manifest exclude must be a non-empty list")
        exclude = []
    exclude_text = " ".join(str(item) for item in exclude)
    for required_pattern in ["*.fastq", "*.sra", "*.bam", "work/", "databases/"]:
        if required_pattern not in exclude_text:
            errors.append(f"artifact pull manifest exclude should block {required_pattern}")

    destination_policy = data.get("local_destination_policy", {})
    if not isinstance(destination_policy, dict):
        errors.append("artifact pull manifest local_destination_policy must be an object")
    else:
        if destination_policy.get("must_remain_summary_only") is not True:
            errors.append("artifact pull manifest local destination must remain summary-only")
        default_root = str(destination_policy.get("default_root", ""))
        if not default_root:
            errors.append("artifact pull manifest local_destination_policy.default_root is required")
        elif Path(default_root).is_absolute():
            if path_is_under(Path(default_root), repo_root_resolved):
                warnings.append("artifact pull manifest default_root is inside repo; prefer .runtime for local summaries")
        elif not default_root.startswith(".runtime/"):
            warnings.append("artifact pull manifest default_root should be under .runtime")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_claim_audit_jsonl(path: Path) -> dict[str, Any]:
    result = validate_jsonl(
        path,
        required_keys={"audit_id", "mode", "subject_id", "verdict", "rule_id", "review_status"},
        label="claim-audit.jsonl",
    )
    errors = list(result["errors"])
    warnings = list(result["warnings"])

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("verdict") not in CLAIM_AUDIT_VERDICTS:
                    errors.append(f"claim-audit.jsonl line {line_no}: unrecognized verdict: {record.get('verdict')}")
                if record.get("mode") not in {"overclaim", "pathway_completeness", "citation_seed"}:
                    errors.append(f"claim-audit.jsonl line {line_no}: unrecognized mode: {record.get('mode')}")
    except OSError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_data_ledger(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = DATA_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"data ledger missing columns: {', '.join(sorted(missing))}")

    if not rows:
        errors.append("data ledger must contain at least one row")

    for idx, row in enumerate(rows, start=2):
        label = row.get("dataset_id") or f"row {idx}"
        remote_path = row.get("remote_path", "")
        if not remote_path:
            errors.append(f"{label}: remote_path is required")
        elif not is_remote_path(remote_path):
            errors.append(f"{label}: remote_path must point to remote storage, got {remote_path}")

        local_path = row.get("local_path", "")
        if local_path and local_path.lower() not in {"not_applicable", "none", "n/a"}:
            errors.append(f"{label}: local_path must be empty for v0 remote-only campaigns")

        checksum_status = row.get("checksum_status", "")
        if checksum_status not in {"remote_pending", "verified", "not_applicable", "pending"}:
            errors.append(f"{label}: checksum_status is not recognized: {checksum_status}")

        if row.get("data_sensitivity") not in {"public", "private", "restricted", "unpublished", "controlled"}:
            errors.append(f"{label}: data_sensitivity is not recognized: {row.get('data_sensitivity')}")

        if row.get("allowed_upload") not in {"no_public_webserver_upload", "approved_public_webserver_upload", "controlled_remote_only"}:
            errors.append(f"{label}: allowed_upload is not recognized: {row.get('allowed_upload')}")

        if row.get("raw_artifact_policy") not in {"remote_only", "controlled_workdir_only", "not_applicable"}:
            errors.append(f"{label}: raw_artifact_policy is not recognized: {row.get('raw_artifact_policy')}")

        if row.get("data_sensitivity") != "public" and row.get("operator_approval_id") in {"", "not_required_public_data"}:
            errors.append(f"{label}: non-public data requires operator_approval_id")

        if row.get("allowed_upload") == "approved_public_webserver_upload" and row.get("operator_approval_id") in {"", "not_required_public_data"}:
            errors.append(f"{label}: approved public webserver upload requires operator_approval_id")

        source_url = row.get("source_url", "")
        if source_url and not is_url(source_url):
            warnings.append(f"{label}: source_url does not look like a URL")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_query_ledger(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = QUERY_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"query ledger missing columns: {', '.join(sorted(missing))}")

    if not rows:
        errors.append("query ledger must contain at least one row")

    valid_confidence = {"high", "medium", "medium-low", "low", "context"}
    valid_curation_status = {
        "resolved",
        "resolved_as_proxy",
        "fallback_used",
        "unresolved",
        "unresolved_intake_blocked",
        "remote_resolve_required",
        "family_seed",
        "context_only",
        "deprecated",
    }
    for idx, row in enumerate(rows, start=2):
        label = row.get("query_id") or f"row {idx}"
        if row.get("confidence") not in valid_confidence:
            errors.append(f"{label}: confidence must be one of {', '.join(sorted(valid_confidence))}")
        if row.get("curation_status") not in valid_curation_status:
            errors.append(f"{label}: curation_status is not recognized: {row.get('curation_status')}")
        if row.get("decoy_or_broad_family_flag") not in {"true", "false"}:
            errors.append(f"{label}: decoy_or_broad_family_flag must be true or false")
        if row.get("expected_false_positive_risk") not in {"low", "medium", "high"}:
            errors.append(f"{label}: expected_false_positive_risk must be low, medium, or high")
        if row.get("sequence_type") not in {"protein", "protein_seed", "mRNA", "mRNA_and_protein", "domain_family", "literature_seed"}:
            errors.append(f"{label}: sequence_type is not recognized: {row.get('sequence_type')}")
        citation = row.get("citation", "")
        if citation and not (is_url(citation) or citation.startswith("doi:")):
            warnings.append(f"{label}: citation should be a URL or DOI")
        source = row.get("sequence_source", "")
        if has_raw_or_large_suffix(source):
            errors.append(f"{label}: sequence_source must not point to raw local sequence data")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def split_cell(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").replace("|", ";").replace(",", ";").split(";") if item.strip()]


def validate_query_registry(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = QUERY_REGISTRY_COLUMNS - fields
    if missing:
        errors.append(f"query registry missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("query registry must contain at least one row")

    seen: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        label = row.get("query_id") or f"row {idx}"
        if label in seen:
            errors.append(f"{label}: duplicate query_id in query registry")
        seen.add(label)
        status = row.get("sequence_status", "")
        if status not in QUERY_SEQUENCE_STATUSES:
            errors.append(f"{label}: sequence_status is not recognized: {status}")
        if row.get("sequence_kind") not in {"protein", "protein_seed", "mRNA", "mRNA_and_protein", "domain_family", "literature_seed", "context_only"}:
            errors.append(f"{label}: sequence_kind is not recognized: {row.get('sequence_kind')}")
        try:
            length = int(str(row.get("sequence_length", "0") or "0"))
        except ValueError:
            errors.append(f"{label}: sequence_length must be an integer")
            length = 0
        if status in RESOLVED_QUERY_STATUSES:
            if not row.get("resolved_accession"):
                errors.append(f"{label}: resolved query needs resolved_accession")
            if length <= 0:
                errors.append(f"{label}: resolved query needs positive sequence_length")
            if not row.get("checksum"):
                errors.append(f"{label}: resolved query needs checksum")
        if status == "unresolved_intake_blocked" and row.get("claim_ceiling_if_unresolved") != "not_tested_intake_blocked":
            errors.append(f"{label}: unresolved intake-blocked query must use claim_ceiling_if_unresolved=not_tested_intake_blocked")
        if status == "unresolved_intake_blocked" and not split_cell(row.get("required_for_claims", "")):
            errors.append(f"{label}: unresolved intake-blocked query must declare at least one entry in required_for_claims")
        if row.get("source_scout_status") in {"blocked", "not_found"} and "NGDC" not in row.get("resolution_evidence", ""):
            warnings.append(f"{label}: blocked/not_found source scout status should include NGDC/GWH evidence before final blocker")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def load_query_registry_rows(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {}
    return {row.get("query_id", ""): row for row in rows if row.get("query_id")}


def validate_required_claims(path: Path, *, query_registry: Path | None = None) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = REQUIRED_CLAIM_COLUMNS - fields
    if missing:
        errors.append(f"required claims missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("required claims must contain at least one row")

    registry = load_query_registry_rows(query_registry)
    for idx, row in enumerate(rows, start=2):
        label = row.get("claim_id") or f"row {idx}"
        if row.get("assertion_status") not in {"asserted", "active", "planned", "deferred"}:
            errors.append(f"{label}: assertion_status is not recognized: {row.get('assertion_status')}")
        required_query_ids = split_cell(row.get("required_query_ids", ""))
        if not required_query_ids:
            errors.append(f"{label}: required_query_ids must list at least one query")
        unresolved: list[str] = []
        for query_id in required_query_ids:
            query = registry.get(query_id)
            if registry and query is None:
                errors.append(f"{label}: required query is missing from query registry: {query_id}")
                continue
            status = query.get("sequence_status", "") if query else ""
            if query and status not in RESOLVED_QUERY_STATUSES:
                unresolved.append(query_id)
        active = row.get("assertion_status") in {"asserted", "active"}
        allowed = str(row.get("allowed_if_unresolved", "")).lower() in {"true", "yes", "1"}
        if active and unresolved and not allowed:
            errors.append(f"{label}: required claim has unresolved required queries: {', '.join(unresolved)}")
        elif unresolved:
            warnings.append(f"{label}: unresolved required queries keep claim below asserted status: {', '.join(unresolved)}")
        blocked_labels = {item.lower() for item in split_cell(row.get("blocked_output_labels", ""))}
        if unresolved and not {"absent", "0 hits", "missing from target", "no homolog found"} & blocked_labels:
            errors.append(f"{label}: unresolved required query must block absence-style output labels")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_source_ledger(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    route_minimum = {"source_id", "organism", "proteome_fasta", "gff", "genome_fasta", "transcriptome", "transcriptome_species"}
    scout_minimum = {"query_id", "query_name", "claim_id", "source_name", "probe_status"}
    is_route_ledger = route_minimum <= fields
    is_scout_ledger = scout_minimum <= fields
    if not is_route_ledger and not is_scout_ledger:
        missing_route = route_minimum - fields
        missing_scout = scout_minimum - fields
        errors.append(
            "source ledger must be a route source ledger or source-scout probe ledger; "
            f"missing route columns: {', '.join(sorted(missing_route))}; "
            f"missing scout columns: {', '.join(sorted(missing_scout))}"
        )
    if not rows:
        errors.append("source ledger must contain at least one row")
    seen: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        if is_route_ledger:
            label = row.get("source_id") or f"row {idx}"
            if label in seen:
                errors.append(f"{label}: duplicate source_id in source ledger")
            seen.add(label)
            if not row.get("organism"):
                errors.append(f"{label}: organism is required")
            if row.get("scout_status") in {"blocked", "not_found"} and "NGDC" not in row.get("probe_status", ""):
                warnings.append(f"{label}: blocked scout_status should include NGDC/GWH probe evidence")
        if is_scout_ledger:
            label = f"{row.get('query_id')}/{row.get('source_name')}" or f"row {idx}"
            if row.get("source_record_type") and row.get("source_record_type") != "source_scout_probe":
                errors.append(f"{label}: source_record_type must be source_scout_probe")
            if row.get("acquisition_policy") and row.get("acquisition_policy") != "metadata_only_no_network_no_raw_download":
                errors.append(f"{label}: source scout acquisition_policy must be metadata_only_no_network_no_raw_download")
            if row.get("network_call_planned") not in {"", "false", "False"}:
                errors.append(f"{label}: source scout ledger must not plan network calls")
            if row.get("raw_download_planned") not in {"", "false", "False"}:
                errors.append(f"{label}: source scout ledger must not plan raw downloads")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_read_accessions(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = READ_ACCESSIONS_COLUMNS - fields
    if missing:
        errors.append(f"read accessions missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("read accessions must contain at least one row")

    seen: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        label = row.get("source_id") or f"row {idx}"
        if not row.get("source_id"):
            errors.append(f"{label}: source_id is required")
        elif row["source_id"] in seen:
            errors.append(f"{label}: duplicate source_id in read accessions")
        seen.add(row.get("source_id", ""))
        if row.get("source_record_type") != "read_acquisition":
            errors.append(f"{label}: source_record_type must be read_acquisition")
        if not row.get("source_provider"):
            errors.append(f"{label}: source_provider is required")
        if row.get("status") == "resolved" and not row.get("run_accession"):
            errors.append(f"{label}: resolved read accession requires run_accession")
        if row.get("library_layout") not in {"SINGLE", "PAIRED", "UNKNOWN", ""}:
            errors.append(f"{label}: invalid library_layout")
        if row.get("layout_branch") not in {"single_end", "paired_end", "mixed_layout_review_required", "review_required", "resolution_failed", ""}:
            errors.append(f"{label}: invalid layout_branch")
        remote_path = row.get("remote_path", "")
        if remote_path and not is_remote_path(remote_path):
            errors.append(f"{label}: remote_path must point to remote storage")
        if has_raw_or_large_suffix(remote_path) and not is_remote_path(remote_path):
            errors.append(f"{label}: raw read path must not be local")
        raw_policy = row.get("raw_artifact_policy", "")
        if raw_policy and raw_policy != "remote_only":
            warnings.append(f"{label}: raw_artifact_policy should be remote_only")
        if row.get("acquisition_policy") != "metadata_resolved_raw_remote_only":
            errors.append(f"{label}: acquisition_policy must be metadata_resolved_raw_remote_only")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_resource_ledger(path: Path, *, web_tool_policy: str = "container-only", strict: bool = False) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = RESOURCE_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"resource ledger missing columns: {', '.join(sorted(missing))}")

    if not rows:
        errors.append("resource ledger must contain at least one row")

    for idx, row in enumerate(rows, start=2):
        label = row.get("resource") or f"row {idx}"
        license_class = row.get("license_class", "")
        if license_class not in LICENSE_CLASSES:
            errors.append(f"{label}: unrecognized license_class: {license_class}")
        use_mode = row.get("use_mode", "")
        if web_tool_policy == "container-only" and "web" in use_mode:
            errors.append(f"{label}: webserver use is not allowed under container-only policy")
        if license_class == "restricted-or-review":
            approval = row.get("approval_status", "")
            if approval != "approved":
                message = f"{label}: restricted-or-review resource requires explicit approval"
                if strict:
                    errors.append(message)
                else:
                    warnings.append(message)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_candidate_hits(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = CANDIDATE_HIT_COLUMNS - fields
    if missing:
        errors.append(f"candidate hits missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("candidate hits must contain at least one row")

    for idx, row in enumerate(rows, start=2):
        label = row.get("candidate_id") or f"row {idx}"
        if row.get("search_direction") not in SEARCH_DIRECTIONS:
            errors.append(f"{label}: search_direction is not recognized: {row.get('search_direction')}")
        if row.get("anchor_method") not in ANCHOR_METHODS:
            errors.append(f"{label}: anchor_method is not recognized: {row.get('anchor_method')}")
        if row.get("anchor_confidence") not in ANCHOR_CONFIDENCE_CLASSES:
            errors.append(f"{label}: anchor_confidence is not recognized: {row.get('anchor_confidence')}")
        if row.get("coordinate_confidence") not in COORDINATE_CONFIDENCE_VALUES:
            errors.append(f"{label}: coordinate_confidence is not recognized: {row.get('coordinate_confidence')}")
        for field in ["source_species", "target_species", "target_db_id"]:
            if not row.get(field):
                errors.append(f"{label}: {field} is required")
        if row.get("hit_type") not in ALLOWED_HIT_TYPES:
            errors.append(f"{label}: hit_type is not recognized: {row.get('hit_type')}")
        if row.get("review_status") not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label}: review_status is not recognized: {row.get('review_status')}")
        if row.get("product_claim_level") not in {"none", "candidate", "pathway_hypothesis", "cluster_hypothesis", "validated_elsewhere"}:
            errors.append(f"{label}: product_claim_level is not recognized: {row.get('product_claim_level')}")
        if row.get("hit_type") == "transcript_hit" and row.get("product_claim_level") == "cluster_hypothesis":
            errors.append(f"{label}: transcript_hit cannot carry cluster_hypothesis product_claim_level")
        broad_family = row.get("hit_type") == "domain_hit" or row.get("duplicate_class") == "broad_family"
        if broad_family and row.get("product_claim_level") in {"pathway_hypothesis", "cluster_hypothesis", "validated_elsewhere"}:
            errors.append(f"{label}: broad-family/domain-only evidence cannot carry product/pathway/cluster claim level without separate claim audit support")
        if row.get("product_claim_level") == "cluster_hypothesis" and row.get("anchor_confidence") in {"domain_only", "unanchored"}:
            errors.append(f"{label}: cluster_hypothesis requires coordinate-bearing anchor evidence")
        if broad_family and row.get("reciprocal_best_hit") not in {"yes", "ambiguous"} and row.get("anchor_confidence") in {"domain_only", "unanchored"}:
            warnings.append(f"{label}: broad-family hit lacks reciprocal or coordinate support; keep claim-limited")
        if not row.get("pathway_step_id", "").startswith("STEP_"):
            errors.append(f"{label}: pathway_step_id must start with STEP_")
        if row.get("novelty_status") not in NOVELTY_STATUSES:
            errors.append(f"{label}: novelty_status is not recognized: {row.get('novelty_status')}")
        if row.get("duplicate_class") not in DUPLICATE_CLASSES:
            errors.append(f"{label}: duplicate_class is not recognized: {row.get('duplicate_class')}")
        if row.get("duplicate_confidence") not in DUPLICATE_CONFIDENCE:
            errors.append(f"{label}: duplicate_confidence is not recognized: {row.get('duplicate_confidence')}")
        if row.get("splice_variant_status") not in SPLICE_VARIANT_STATUSES:
            errors.append(f"{label}: splice_variant_status is not recognized: {row.get('splice_variant_status')}")
        if row.get("partial_status") not in PARTIAL_STATUSES:
            errors.append(f"{label}: partial_status is not recognized: {row.get('partial_status')}")
        for field in ["dedupe_group", "representative_id", "dedupe_rationale", "novelty_basis"]:
            if not row.get(field):
                warnings.append(f"{label}: {field} is empty")
        weights = row.get("evidence_weights_json", "")
        if weights:
            try:
                json.loads(weights)
            except json.JSONDecodeError:
                errors.append(f"{label}: evidence_weights_json must be valid JSON")
        try:
            score = float(row.get("evidence_score", ""))
            if not 0 <= score <= 1:
                errors.append(f"{label}: evidence_score must be between 0 and 1")
        except ValueError:
            errors.append(f"{label}: evidence_score must be numeric")
        try:
            coverage = float(row.get("coverage", ""))
            if not 0 <= coverage <= 1:
                errors.append(f"{label}: coverage must be between 0 and 1")
        except ValueError:
            warnings.append(f"{label}: coverage is not numeric")
        for field in ["query_coverage", "target_coverage"]:
            try:
                value = float(row.get(field, ""))
                if not 0 <= value <= 1:
                    errors.append(f"{label}: {field} must be between 0 and 1")
            except ValueError:
                warnings.append(f"{label}: {field} is not numeric")
        bitscore = row.get("bitscore", "")
        if bitscore and bitscore != "remote_pending":
            try:
                float(bitscore)
            except ValueError:
                errors.append(f"{label}: bitscore must be numeric or remote_pending")
        reciprocal_rank = row.get("reciprocal_rank", "")
        if reciprocal_rank and reciprocal_rank not in {"remote_pending", "not_assessed", "none"}:
            try:
                rank_value = int(reciprocal_rank)
                if rank_value < 0:
                    errors.append(f"{label}: reciprocal_rank must be non-negative")
            except ValueError:
                errors.append(f"{label}: reciprocal_rank must be an integer, remote_pending, not_assessed, or none")
        if row.get("reciprocal_best_hit") not in {"yes", "no", "ambiguous", "not_assessed", "remote_pending", "reciprocal_pending"}:
            errors.append(f"{label}: reciprocal_best_hit is not recognized: {row.get('reciprocal_best_hit')}")
        closest = row.get("closest_characterized_identity", "")
        if closest and closest != "remote_pending":
            try:
                identity = float(closest)
                if not 0 <= identity <= 100:
                    errors.append(f"{label}: closest_characterized_identity must be between 0 and 100")
            except ValueError:
                errors.append(f"{label}: closest_characterized_identity must be numeric or remote_pending")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_candidate_ranking(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = CANDIDATE_RANKING_COLUMNS - fields
    if missing:
        errors.append(f"candidate ranking missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("candidate ranking must contain at least one row")

    previous_rank = 0
    for idx, row in enumerate(rows, start=2):
        label = row.get("candidate_id") or f"row {idx}"
        try:
            rank = int(row.get("rank", ""))
            if rank <= previous_rank:
                errors.append(f"{label}: ranks must be increasing")
            previous_rank = rank
        except ValueError:
            errors.append(f"{label}: rank must be an integer")
        if row.get("review_status") not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label}: review_status is not recognized: {row.get('review_status')}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_cluster_neighborhoods(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    legacy_missing = CLUSTER_NEIGHBORHOOD_COLUMNS - fields
    summary_missing = NEIGHBORHOOD_SUMMARY_COLUMNS - fields
    missing = set() if not legacy_missing or not summary_missing else legacy_missing
    if missing:
        errors.append(
            "cluster neighborhoods missing columns for both supported schemas; "
            f"legacy missing: {', '.join(sorted(legacy_missing))}; "
            f"summary missing: {', '.join(sorted(summary_missing))}"
        )
    if not rows:
        errors.append("cluster neighborhoods must contain at least one row")

    if not legacy_missing:
        for idx, row in enumerate(rows, start=2):
            label = row.get("cluster_id") or f"row {idx}"
            if row.get("review_status") not in ALLOWED_REVIEW_STATUSES:
                errors.append(f"{label}: review_status is not recognized: {row.get('review_status')}")
            if row.get("sequence_policy") not in {"remote_only", "summary_only", "not_included"}:
                errors.append(f"{label}: sequence_policy must be remote_only, summary_only, or not_included")
            if row.get("coordinate_status") not in {"genome_localized", "transcript_only", "unknown"}:
                errors.append(f"{label}: coordinate_status is not recognized: {row.get('coordinate_status')}")
    elif not summary_missing:
        for idx, row in enumerate(rows, start=2):
            label = row.get("neighborhood_id") or f"row {idx}"
            if row.get("product_claim_level") not in {"none", "candidate", "pathway_hypothesis", "cluster_hypothesis", "validated_elsewhere"}:
                errors.append(f"{label}: product_claim_level is not recognized: {row.get('product_claim_level')}")
            elif row.get("product_claim_level") in {"pathway_hypothesis", "cluster_hypothesis"}:
                errors.append(f"{label}: neighborhood summaries must cap pathway/cluster product claims to candidate")
            try:
                if int(row.get("neighbor_count", "0")) < 0:
                    errors.append(f"{label}: neighbor_count cannot be negative")
            except ValueError:
                errors.append(f"{label}: neighbor_count must be an integer")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_candidate_anchors(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = CANDIDATE_ANCHOR_COLUMNS - fields
    if missing:
        errors.append(f"candidate anchors missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("candidate anchors must contain at least one row")

    for idx, row in enumerate(rows, start=2):
        label = row.get("candidate_id") or f"row {idx}"
        if row.get("product_claim_level") not in {"none", "candidate", "pathway_hypothesis", "cluster_hypothesis", "validated_elsewhere"}:
            errors.append(f"{label}: product_claim_level is not recognized: {row.get('product_claim_level')}")
        elif row.get("product_claim_level") in {"pathway_hypothesis", "cluster_hypothesis"}:
            errors.append(f"{label}: candidate anchor summaries must cap pathway/cluster product claims to candidate")
        if row.get("anchor_status") not in {"anchored", "unanchored", "mapped", "unmapped", "ambiguous", "mock_mapped", "blocked"}:
            errors.append(f"{label}: anchor_status is not recognized: {row.get('anchor_status')}")
        if row.get("anchor_confidence") not in ({"high", "medium", "low", "none", "mock"} | ANCHOR_CONFIDENCE_CLASSES):
            errors.append(f"{label}: anchor_confidence is not recognized: {row.get('anchor_confidence')}")
        if row.get("pathway_step_id") and not row.get("pathway_step_id", "").startswith("STEP_"):
            warnings.append(f"{label}: pathway_step_id does not start with STEP_")
        for field in ["start", "end"]:
            value = row.get(field, "")
            if value:
                try:
                    int(value)
                except ValueError:
                    errors.append(f"{label}: {field} must be an integer")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_neighbor_annotations(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = NEIGHBOR_ANNOTATION_COLUMNS - fields
    if missing:
        errors.append(f"neighbor annotations missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("neighbor annotations must contain at least one row")

    for idx, row in enumerate(rows, start=2):
        label = row.get("feature_id") or f"row {idx}"
        if row.get("overlaps_window") not in {"true", "false", "True", "False"}:
            errors.append(f"{label}: overlaps_window must be true or false")
        if row.get("is_candidate") not in {"true", "false", "True", "False"}:
            errors.append(f"{label}: is_candidate must be true or false")
        for field in ["start", "end", "distance_bp", "neighbor_rank"]:
            try:
                int(row.get(field, ""))
            except ValueError:
                errors.append(f"{label}: {field} must be an integer")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_domain_labels(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}

    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = DOMAIN_LABEL_COLUMNS - fields
    if missing:
        errors.append(f"domain labels missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("domain labels must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        label = row.get("feature_id") or f"row {idx}"
        if not row.get("domain_label"):
            warnings.append(f"{label}: domain_label is empty")
        if row.get("product_claim_level") not in {"none", "candidate", "pathway_hypothesis", "cluster_hypothesis", "validated_elsewhere"}:
            errors.append(f"{label}: product_claim_level is not recognized: {row.get('product_claim_level')}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_target_db_resolved(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    repo_root = (repo_root or Path.cwd()).resolve()
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = TARGET_DB_LEDGER_COLUMNS - fields
    if missing:
        errors.append(f"target DB resolved ledger missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("target DB resolved ledger must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        label = row.get("target_db_id") or f"row {idx}"
        if row.get("sequence_type") not in {"protein", "nucleotide", "genome", "annotation", "mixed"}:
            errors.append(f"{label}: sequence_type is not recognized: {row.get('sequence_type')}")
        for field in ["source_path", "provider_path"]:
            value = row.get(field, "")
            errors.extend(validate_remote_or_absolute(value, label=f"{label}: {field}"))
            repo_error = path_under_repo_error(value, repo_root, label=f"{label}: {field}")
            if repo_error:
                errors.append(repo_error)
        if row.get("local_copy") != "false":
            errors.append(f"{label}: local_copy must be false")
        if row.get("checksum_status") not in CHECKSUM_STATUSES:
            errors.append(f"{label}: checksum_status is not recognized: {row.get('checksum_status')}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_target_db_indexes(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    repo_root = (repo_root or Path.cwd()).resolve()
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = TARGET_DB_INDEX_COLUMNS - fields
    if missing:
        errors.append(f"target DB indexes missing columns: {', '.join(sorted(missing))}")
    if not rows:
        warnings.append("target DB indexes table is empty; this is allowed only before provider-side build")
    for idx, row in enumerate(rows, start=2):
        label = row.get("target_db_id") or f"row {idx}"
        if row.get("engine") not in {"blast", "diamond", "mmseqs", "miniprot", "none"}:
            errors.append(f"{label}: engine is not recognized: {row.get('engine')}")
        if row.get("sequence_type") not in {"protein", "nucleotide", "genome", "annotation", "mixed"}:
            errors.append(f"{label}: sequence_type is not recognized: {row.get('sequence_type')}")
        for field in ["index_path", "source_path"]:
            value = row.get(field, "")
            errors.extend(validate_remote_or_absolute(value, label=f"{label}: {field}"))
            repo_error = path_under_repo_error(value, repo_root, label=f"{label}: {field}")
            if repo_error:
                errors.append(repo_error)
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_orthology_links(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = ORTHOLOGY_LINK_COLUMNS - fields
    if missing:
        errors.append(f"orthology links missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("orthology links must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        label = row.get("orthology_link_id") or f"row {idx}"
        if row.get("search_direction") not in SEARCH_DIRECTIONS:
            errors.append(f"{label}: search_direction is not recognized: {row.get('search_direction')}")
        if row.get("reciprocal_best_hit") not in {"yes", "no", "ambiguous", "not_assessed", "remote_pending"}:
            errors.append(f"{label}: reciprocal_best_hit is not recognized: {row.get('reciprocal_best_hit')}")
        if row.get("orthology_status") not in {"supported", "candidate", "ambiguous", "broad_family_limited", "not_supported", "not_assessed"}:
            errors.append(f"{label}: orthology_status is not recognized: {row.get('orthology_status')}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_anchor_ladder(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = ANCHOR_LADDER_COLUMNS - fields
    if missing:
        errors.append(f"anchor ladder missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("anchor ladder must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        label = row.get("candidate_id") or f"row {idx}"
        if row.get("anchor_method") not in ANCHOR_METHODS:
            errors.append(f"{label}: anchor_method is not recognized: {row.get('anchor_method')}")
        if row.get("anchor_confidence") not in ANCHOR_CONFIDENCE_CLASSES:
            errors.append(f"{label}: anchor_confidence is not recognized: {row.get('anchor_confidence')}")
        if row.get("coordinate_confidence") not in COORDINATE_CONFIDENCE_VALUES:
            errors.append(f"{label}: coordinate_confidence is not recognized: {row.get('coordinate_confidence')}")
        if row.get("claim_gate") == "cluster_claim_allowed" and row.get("anchor_confidence") in {"domain_only", "unanchored"}:
            errors.append(f"{label}: cluster claims require coordinate-bearing anchor evidence")
        for field in ["start", "end"]:
            value = row.get(field, "")
            if value and value != "not_applicable":
                try:
                    int(value)
                except ValueError:
                    errors.append(f"{label}: {field} must be an integer or not_applicable")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_reciprocal_hits(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = RECIPROCAL_HIT_COLUMNS - fields
    if missing:
        errors.append(f"reciprocal hits missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("reciprocal hits must contain at least one row")
    for idx, row in enumerate(rows, start=2):
        label = row.get("reciprocal_hit_id") or f"row {idx}"
        if row.get("reciprocal_best_hit") not in {"yes", "no", "ambiguous", "not_assessed", "remote_pending"}:
            errors.append(f"{label}: reciprocal_best_hit is not recognized: {row.get('reciprocal_best_hit')}")
        if row.get("status") not in {"supported", "candidate", "ambiguous", "blocked", "not_assessed", "mock"}:
            errors.append(f"{label}: status is not recognized: {row.get('status')}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_neighborhood_hypotheses(path: Path) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = NEIGHBORHOOD_HYPOTHESIS_COLUMNS - fields
    if missing:
        errors.append(f"neighborhood hypotheses missing columns: {', '.join(sorted(missing))}")
    if not rows:
        warnings.append("neighborhood hypotheses table is empty; no anchored neighborhoods may have been available")
    for idx, row in enumerate(rows, start=2):
        label = row.get("hypothesis_id") or f"row {idx}"
        if row.get("review_status") not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label}: review_status is not recognized: {row.get('review_status')}")
        if "validated" in row.get("claim_safe_label", "").lower():
            errors.append(f"{label}: neighborhood hypotheses cannot use validated product labels")
        try:
            score = float(row.get("hypothesis_score", ""))
            if not 0 <= score <= 1:
                errors.append(f"{label}: hypothesis_score must be between 0 and 1")
        except ValueError:
            errors.append(f"{label}: hypothesis_score must be numeric")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_pathway_completeness(path: Path, *, require_deferred_budget: bool = False) -> dict[str, Any]:
    rows, fields_or_errors = read_tsv(path)
    if fields_or_errors and fields_or_errors[0].startswith("could not read "):
        return {"ok": False, "errors": fields_or_errors, "warnings": []}
    fields = set(fields_or_errors)
    errors: list[str] = []
    warnings: list[str] = []
    missing = PATHWAY_COMPLETENESS_COLUMNS - fields
    if missing:
        errors.append(f"pathway completeness missing columns: {', '.join(sorted(missing))}")
    if not rows:
        errors.append("pathway completeness must contain at least one row")
    seen_deferred = False
    for idx, row in enumerate(rows, start=2):
        label = row.get("pathway_step_id") or f"row {idx}"
        status = row.get("status", "")
        if status not in PATHWAY_COMPLETENESS_STATUSES:
            errors.append(f"{label}: status is not recognized: {status}")
        if status == "deferred_by_budget":
            seen_deferred = True
        if row.get("review_status") not in ALLOWED_REVIEW_STATUSES:
            errors.append(f"{label}: review_status is not recognized: {row.get('review_status')}")
        if row.get("claim_limit") not in CLAIM_LIMITS:
            errors.append(f"{label}: claim_limit is not recognized: {row.get('claim_limit')}")
        broad_only = row.get("domain_support") == "broad_family_only"
        if status == "supported" and broad_only:
            warnings.append(f"{label}: supported status rests on broad-family domain evidence; require orthogonal review")
    if require_deferred_budget and not seen_deferred:
        errors.append("24h pathway completeness output must include at least one deferred_by_budget row")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_jsonl(path: Path, *, required_keys: set[str], label: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                count += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"{label} line {line_no}: invalid JSON: {exc}")
                    continue
                missing = required_keys - set(record)
                if missing:
                    errors.append(f"{label} line {line_no}: missing keys: {', '.join(sorted(missing))}")
                status = record.get("review_status")
                if status and status not in ALLOWED_REVIEW_STATUSES:
                    errors.append(f"{label} line {line_no}: unrecognized review_status: {status}")
                evidence_class = record.get("evidence_class")
                if evidence_class and evidence_class not in ALLOWED_EVIDENCE_CLASSES:
                    errors.append(f"{label} line {line_no}: unrecognized evidence_class: {evidence_class}")
    except OSError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    if count == 0:
        errors.append(f"{label} must contain at least one JSONL record")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_claim_ledger(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    for phrase in ["Allowed claims", "Forbidden overclaims", "Validation caveats"]:
        if phrase not in text:
            errors.append(f"claim ledger missing section phrase: {phrase}")
    if "transcriptome-only" not in text.lower():
        warnings.append("claim ledger should mention transcriptome-only caveats")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_dossier_manifest(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = (repo_root or Path.cwd()).resolve()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    required = {
        "schema_version",
        "campaign_id",
        "created_at",
        "artifact_policy",
        "artifacts",
        "large_artifacts_remote_only",
        "validation",
    }
    for key in sorted(required):
        if key not in data:
            errors.append(f"dossier manifest missing root key: {key}")

    if data.get("schema_version") != 1:
        errors.append("dossier manifest schema_version must be 1")
    if data.get("artifact_policy") != "summaries_only":
        errors.append("dossier manifest artifact_policy must be summaries_only")

    root = path.parent.resolve()
    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("dossier artifacts must be a non-empty list")
        artifacts = []

    expected_paths = {
        "summary.html",
        "clusters.html",
        "review.html",
        "evidence.html",
        "provenance.html",
        "claim-ledger.md",
        "data/export.xlsx",
        "data/data-ledger.tsv",
        "data/query-ledger.tsv",
        "data/resource-ledger.tsv",
        "data/project-goals.yaml",
        "data/pathway-steps.tsv",
        "data/database-ledger.tsv",
        "data/cache-ledger.tsv",
        "data/candidate_hits.tsv",
        "data/cluster_neighborhoods.tsv",
        "data/candidate-ranking.tsv",
        "data/evidence.jsonl",
        "data/claim-audit.jsonl",
        "data/provenance.jsonl",
        "data/licenses.tsv",
        "data/versions.json",
        "data/citations.bib",
        "data/dossier_index.json",
        "datapackage.json",
        "ro-crate-metadata.json",
        "validation-report.json",
    }
    seen_paths: set[str] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            errors.append("dossier artifact entries must be objects")
            continue
        rel = str(item.get("path", ""))
        seen_paths.add(rel)
        if not rel:
            errors.append("dossier artifact missing path")
            continue
        if Path(rel).is_absolute():
            errors.append(f"dossier artifact must use relative path: {rel}")
            continue
        if has_raw_or_large_suffix(rel):
            errors.append(f"dossier artifact cannot be a raw/large sequence artifact: {rel}")
        artifact_path = (root / rel).resolve()
        if not artifact_path.exists():
            errors.append(f"dossier artifact path missing: {rel}")
        elif artifact_path.is_file() and artifact_path.stat().st_size > 10 * 1024 * 1024:
            errors.append(f"dossier artifact exceeds 10 MB local summary limit: {rel}")
        elif item.get("sha256"):
            actual = sha256_file(artifact_path)
            if actual.lower() != str(item["sha256"]).lower():
                errors.append(f"dossier artifact sha256 mismatch: {rel}")
        else:
            warnings.append(f"dossier artifact lacks sha256: {rel}")
        if path_is_under(artifact_path, repo_root) and has_raw_or_large_suffix(str(artifact_path)):
            errors.append(f"raw/large artifact is under repo root: {rel}")

    missing_artifacts = expected_paths - seen_paths
    if missing_artifacts:
        errors.append(f"dossier manifest missing expected artifacts: {', '.join(sorted(missing_artifacts))}")

    large_artifacts = data.get("large_artifacts_remote_only", [])
    if not isinstance(large_artifacts, list):
        errors.append("large_artifacts_remote_only must be a list")
    else:
        for value in large_artifacts:
            remote_path = str(value)
            if not is_remote_path(remote_path):
                errors.append(f"large artifact pointer must be remote-only: {remote_path}")

    if not data.get("validation"):
        errors.append("dossier manifest validation list must not be empty")

    datapackage_result = validate_dossier_datapackage(root / "datapackage.json")
    errors.extend(datapackage_result["errors"])
    warnings.extend(datapackage_result["warnings"])

    ro_crate_result = validate_dossier_ro_crate(root / "ro-crate-metadata.json")
    errors.extend(ro_crate_result["errors"])
    warnings.extend(ro_crate_result["warnings"])

    validation_report_result = validate_dossier_validation_report(root / "validation-report.json")
    errors.extend(validation_report_result["errors"])
    warnings.extend(validation_report_result["warnings"])

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_dossier_datapackage(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root = path.parent.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"datapackage.json invalid: {exc}"], "warnings": []}

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["datapackage.json root must be an object"], "warnings": []}
    if data.get("profile") != "data-package":
        errors.append("datapackage.json profile must be data-package")
    resources = data.get("resources", [])
    if not isinstance(resources, list) or not resources:
        errors.append("datapackage.json resources must be a non-empty list")
        resources = []

    seen_names: set[str] = set()
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            errors.append(f"datapackage.json resources[{index}] must be an object")
            continue
        name = str(resource.get("name", ""))
        if not name:
            errors.append(f"datapackage.json resources[{index}] missing name")
        elif name in seen_names:
            errors.append(f"datapackage.json duplicate resource name: {name}")
        seen_names.add(name)
        rel = str(resource.get("path", ""))
        if not rel:
            errors.append(f"datapackage.json resources[{index}] missing path")
            continue
        if Path(rel).is_absolute():
            errors.append(f"datapackage.json resource path must be relative: {rel}")
            continue
        if has_raw_or_large_suffix(rel):
            errors.append(f"datapackage.json resource cannot point at raw/large artifact: {rel}")
        resource_path = (root / rel).resolve()
        if not resource_path.exists():
            errors.append(f"datapackage.json resource path missing: {rel}")
            continue
        expected_hash = resource.get("hash")
        if expected_hash and resource_path.is_file():
            actual = sha256_file(resource_path)
            if str(expected_hash).lower() != actual.lower():
                errors.append(f"datapackage.json resource hash mismatch: {rel}")
        else:
            warnings.append(f"datapackage.json resource lacks hash: {rel}")
        if rel.endswith(".tsv"):
            schema = resource.get("schema", {})
            fields = schema.get("fields") if isinstance(schema, dict) else None
            if not isinstance(fields, list) or not fields:
                errors.append(f"datapackage.json TSV resource lacks schema fields: {rel}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_dossier_ro_crate(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root = path.parent.resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"ro-crate-metadata.json invalid: {exc}"], "warnings": []}

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["ro-crate-metadata.json root must be an object"], "warnings": []}
    if "@context" not in data:
        errors.append("ro-crate-metadata.json missing @context")
    graph = data.get("@graph")
    if not isinstance(graph, list) or not graph:
        errors.append("ro-crate-metadata.json @graph must be a non-empty list")
        graph = []

    ids = {str(item.get("@id", "")) for item in graph if isinstance(item, dict)}
    if "./" not in ids:
        errors.append("ro-crate-metadata.json missing root Dataset entity")
    if "#create-dossier-skeleton" not in ids:
        errors.append("ro-crate-metadata.json missing CreateAction entity")
    for required_id in ["dossier-manifest.json", "datapackage.json", "validation-report.json"]:
        if required_id not in ids:
            errors.append(f"ro-crate-metadata.json missing file entity: {required_id}")

    for item in graph:
        if not isinstance(item, dict):
            continue
        rel = str(item.get("@id", ""))
        item_type = item.get("@type")
        if item_type != "File" or not rel:
            continue
        if Path(rel).is_absolute():
            errors.append(f"ro-crate-metadata.json file @id must be relative: {rel}")
            continue
        if has_raw_or_large_suffix(rel):
            errors.append(f"ro-crate-metadata.json file cannot be raw/large artifact: {rel}")
        if not (root / rel).exists():
            errors.append(f"ro-crate-metadata.json file path missing: {rel}")
        # The dossier manifest owns artifact hashes, so RO-Crate hashing it creates
        # circular metadata; require the entity but do not require its hash here.
        if (root / rel).exists() and "sha256" not in item and rel != "dossier-manifest.json":
            warnings.append(f"ro-crate-metadata.json file lacks sha256: {rel}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def validate_dossier_validation_report(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [f"validation-report.json invalid: {exc}"], "warnings": []}

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["validation-report.json root must be an object"], "warnings": []}
    if data.get("schema_version") != 1:
        errors.append("validation-report.json schema_version must be 1")
    if data.get("status") not in {"passed", "warning", "failed"}:
        errors.append("validation-report.json status must be passed, warning, or failed")
    checks = data.get("checks", [])
    if not isinstance(checks, list) or not checks:
        errors.append("validation-report.json checks must be a non-empty list")
        checks = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            errors.append(f"validation-report.json checks[{index}] must be an object")
            continue
        if not check.get("name"):
            errors.append(f"validation-report.json checks[{index}] missing name")
        if check.get("status") not in {"passed", "warning", "failed"}:
            errors.append(f"validation-report.json checks[{index}] has invalid status")
    if data.get("status") == "passed" and any(isinstance(check, dict) and check.get("status") == "failed" for check in checks):
        errors.append("validation-report.json cannot be passed when a check failed")
    if not data.get("recommended_validation_command"):
        warnings.append("validation-report.json lacks recommended_validation_command")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def resolve_manifest_path(value: str, repo_root: Path, manifest_dir: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if manifest_dir is not None and (manifest_dir / path).exists():
        return manifest_dir / path
    return repo_root / path


def validate_launch_manifest(
    path: Path,
    repo_root: Path | None = None,
    *,
    launch_ready: bool = False,
    execution_ready: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = (repo_root or Path.cwd()).resolve()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    for key in sorted(LAUNCH_MANIFEST_REQUIRED_KEYS):
        if key not in data:
            errors.append(f"launch manifest missing root key: {key}")

    if data.get("schema_version") != 1:
        errors.append("launch manifest schema_version must be 1")

    provider = normalize_provider(str(data.get("provider_class", "")))
    if provider not in ALLOWED_PROVIDER_CLASSES:
        errors.append("launch manifest provider_class is not allowed")

    run_scope = str(data.get("run_scope", ""))
    if run_scope not in ALLOWED_RUN_SCOPES:
        errors.append("launch manifest run_scope is not allowed")

    if data.get("artifact_policy") != "summaries_only":
        errors.append("launch manifest artifact_policy must be summaries_only")

    heavy_workdir = str(data.get("heavy_workdir", ""))
    if run_scope not in HEAVY_RUN_SCOPES and provider == "local_lite":
        if heavy_workdir:
            warnings.append("local_lite non-heavy scope should not need a heavy_workdir")
    elif not heavy_workdir:
        errors.append("launch manifest heavy_workdir is required for heavy providers/scopes")
    elif is_object_store_uri(heavy_workdir):
        errors.append("launch manifest heavy_workdir must be a mounted filesystem path, not object storage")

    if heavy_workdir and not is_remote_path(heavy_workdir):
        heavy_path = Path(heavy_workdir)
        if not heavy_path.is_absolute():
            errors.append("local heavy_workdir must be an absolute path")
        elif path_is_under(heavy_path, repo_root):
            errors.append("local heavy_workdir must not be under the repo root")

    runner = data.get("runner", {})
    if not isinstance(runner, dict):
        errors.append("launch manifest runner must be an object")
    else:
        command = runner.get("command")
        if not isinstance(command, list) or not command:
            errors.append("launch manifest runner.command must be a non-empty list")
        if run_scope == "full_campaign_24h":
            if "--max-runtime-hours" not in command:
                errors.append("full_campaign_24h runner.command must include --max-runtime-hours")
            else:
                try:
                    value = float(command[command.index("--max-runtime-hours") + 1])
                    if value > 24 or value <= 0:
                        errors.append("full_campaign_24h --max-runtime-hours must be positive and <= 24")
                except (IndexError, TypeError, ValueError):
                    errors.append("full_campaign_24h --max-runtime-hours must have a numeric value")

    runtime_policy = data.get("runtime_policy", {})
    if run_scope == "full_campaign_24h":
        if not isinstance(runtime_policy, dict):
            errors.append("full_campaign_24h launch manifest requires runtime_policy object")
        else:
            try:
                target_hours = float(runtime_policy.get("target_runtime_hours", 0))
                hard_stop_hours = float(runtime_policy.get("hard_stop_hours", 0))
            except (TypeError, ValueError):
                target_hours = hard_stop_hours = 0
                errors.append("full_campaign_24h runtime_policy hours must be numeric")
            if target_hours <= 0 or target_hours > 24:
                errors.append("full_campaign_24h runtime_policy target_runtime_hours must be positive and <= 24")
            if hard_stop_hours <= 0 or hard_stop_hours > 24:
                errors.append("full_campaign_24h runtime_policy hard_stop_hours must be positive and <= 24")
            if runtime_policy.get("completion_definition") != "complete_summary_dossier_with_deferred_lane_manifest":
                errors.append("full_campaign_24h runtime_policy must require a complete summary dossier with deferred lanes")

    adapter_contract = data.get("adapter_contract", {})
    if not isinstance(adapter_contract, dict):
        errors.append("launch manifest adapter_contract must be an object")
    else:
        if normalize_provider(str(adapter_contract.get("provider_class", ""))) != provider:
            errors.append("adapter_contract.provider_class must match launch provider_class")
        if adapter_contract.get("credential_policy") != "environment_or_secret_store_only":
            errors.append("adapter_contract.credential_policy must be environment_or_secret_store_only")
        if adapter_contract.get("large_artifacts_policy") != "remote_only":
            errors.append("adapter_contract.large_artifacts_policy must be remote_only")
        if adapter_contract.get("public_webserver_uploads") != "forbidden":
            errors.append("adapter_contract.public_webserver_uploads must be forbidden")

    expected = data.get("expected_artifacts", [])
    if not isinstance(expected, list) or not expected:
        errors.append("launch manifest expected_artifacts must be a non-empty list")
    else:
        for item in expected:
            if not isinstance(item, dict):
                errors.append("expected_artifacts entries must be objects")
                continue
            rel = str(item.get("path", ""))
            if not rel:
                errors.append("expected artifact missing path")
            if rel and Path(rel).is_absolute():
                errors.append(f"expected artifact path must be relative: {rel}")
            if rel and has_raw_or_large_suffix(rel):
                errors.append(f"expected artifact cannot be raw/large data: {rel}")

    missing_credentials = data.get("missing_credentials", [])
    if missing_credentials and not isinstance(missing_credentials, list):
        errors.append("missing_credentials must be a list when present")
    for value in missing_credentials if isinstance(missing_credentials, list) else []:
        if "=" in str(value):
            errors.append("missing_credentials must contain variable names only, not values")
    if (launch_ready or execution_ready) and missing_credentials:
        errors.append("launch-ready validation requires all provider credentials to be present")

    if (launch_ready or execution_ready) and run_scope in HEAVY_RUN_SCOPES:
        for key in sorted(EXECUTION_READY_REQUIRED_KEYS):
            if not data.get(key):
                errors.append(f"execution-ready heavy scope requires launch manifest key: {key}")
        image = str(runner.get("image", "")) if isinstance(runner, dict) else ""
        if image.lower() in PLACEHOLDER_IMAGE_VALUES or image.endswith(":unbuilt"):
            errors.append("execution-ready heavy scope requires a non-placeholder runner image")
        boundaries = data.get("remote_artifact_boundaries", {})
        if not isinstance(boundaries, dict):
            errors.append("remote_artifact_boundaries must be an object for execution-ready heavy scopes")
        else:
            if boundaries.get("local_sync") != "summaries_only":
                errors.append("remote_artifact_boundaries.local_sync must be summaries_only")
            if boundaries.get("large_artifacts") != "provider_workdir_only":
                errors.append("remote_artifact_boundaries.large_artifacts must be provider_workdir_only")
        materialization_path_value = str(data.get("data_materialization_plan", ""))
        if materialization_path_value and isinstance(runner, dict):
            materialization_path = resolve_manifest_path(materialization_path_value, repo_root, path.parent)
            try:
                materialization_plan = json.loads(materialization_path.read_text(encoding="utf-8"))
                materializable_count = int(materialization_plan.get("summary", {}).get("materializable_raw_sra_source_count", 0) or 0)
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                materializable_count = 0
            command = runner.get("command", [])
            if materializable_count > 0 and isinstance(command, list) and "--allow-large-downloads" not in command:
                errors.append("execution-ready raw-SRA materialization requires provider runner command to include --allow-large-downloads")

    ledger_hashes = data.get("ledger_hashes", {})
    if not isinstance(ledger_hashes, dict) or not ledger_hashes:
        errors.append("ledger_hashes must be a non-empty object")
    else:
        ledger_paths = {
            "campaign": data.get("campaign_manifest", ""),
            "data_ledger": data.get("data_ledger", ""),
            "query_ledger": data.get("query_ledger", ""),
            "resource_ledger": data.get("resource_ledger", ""),
            "project_goals": data.get("project_goals", ""),
            "pathway_steps": data.get("pathway_steps", ""),
            "database_ledger": data.get("database_ledger", ""),
            "cache_ledger": data.get("cache_ledger", ""),
            "db_bootstrap_plan": data.get("db_bootstrap_plan", ""),
            "data_materialization_plan": data.get("data_materialization_plan", ""),
            "target_db_plan": data.get("target_db_plan", ""),
            "candidate_route_plan": data.get("candidate_route_plan", ""),
            "reference_import_plan": data.get("reference_import_plan", ""),
            "anchor_map_plan": data.get("anchor_map_plan", ""),
            "neighborhood_extract_plan": data.get("neighborhood_extract_plan", ""),
            "orthology_anchor_plan": data.get("orthology_anchor_plan", ""),
            "reciprocal_search_plan": data.get("reciprocal_search_plan", ""),
            "pathway_completeness_plan": data.get("pathway_completeness_plan", ""),
            "campaign_prompt": data.get("campaign_prompt", ""),
            "query_resolution_plan": data.get("query_resolution_plan", ""),
            "decoy_plan": data.get("decoy_plan", ""),
            "run_economics": data.get("run_economics", ""),
            "workflow_class_plan": data.get("workflow_class_plan", ""),
            "lane_activation_plan": data.get("lane_activation_plan", ""),
            "evidence_escalation_plan": data.get("evidence_escalation_plan", ""),
            "claim_levels": data.get("claim_levels", ""),
            "workflow_deferred_lanes": data.get("workflow_deferred_lanes", ""),
            "search_plan": data.get("search_plan", ""),
            "tool_requirements": data.get("tool_requirements", ""),
            "provider_payload": data.get("provider_payload", ""),
        }
        if data.get("artifact_pull_manifest"):
            ledger_paths["artifact_pull_manifest"] = data.get("artifact_pull_manifest", "")
        for name, value in ledger_paths.items():
            if not value:
                errors.append(f"launch manifest missing {name} path")
                continue
            ledger_path = resolve_manifest_path(str(value), repo_root, path.parent)
            if not ledger_path.exists():
                errors.append(f"launch manifest referenced ledger missing: {value}")
                continue
            expected_hash = ledger_hashes.get(name)
            if not expected_hash:
                errors.append(f"ledger_hashes missing {name}")
                continue
            actual_hash = sha256_file(ledger_path)
            if actual_hash.lower() != str(expected_hash).lower():
                errors.append(f"ledger hash mismatch: {name}")

    if data.get("project_goals"):
        results = [
            ("project_goals", validate_project_goals(resolve_manifest_path(str(data["project_goals"]), repo_root, path.parent))),
            ("pathway_steps", validate_pathway_steps(resolve_manifest_path(str(data.get("pathway_steps", "")), repo_root, path.parent))),
            ("database_ledger", validate_database_ledger(resolve_manifest_path(str(data.get("database_ledger", "")), repo_root, path.parent), repo_root=repo_root)),
            ("cache_ledger", validate_cache_ledger(resolve_manifest_path(str(data.get("cache_ledger", "")), repo_root, path.parent), repo_root=repo_root)),
            ("db_bootstrap_plan", validate_db_bootstrap_plan(resolve_manifest_path(str(data.get("db_bootstrap_plan", "")), repo_root, path.parent))),
            (
                "data_materialization_plan",
                validate_data_materialization_plan(
                    resolve_manifest_path(str(data.get("data_materialization_plan", "")), repo_root, path.parent),
                    execution_ready=(launch_ready or execution_ready),
                ),
            ),
            ("target_db_plan", validate_target_db_plan(resolve_manifest_path(str(data.get("target_db_plan", "")), repo_root, path.parent), repo_root=repo_root)),
            ("candidate_route_plan", validate_candidate_route_plan(resolve_manifest_path(str(data.get("candidate_route_plan", "")), repo_root, path.parent))),
            ("reference_import_plan", validate_reference_import_plan(resolve_manifest_path(str(data.get("reference_import_plan", "")), repo_root, path.parent))),
            ("anchor_map_plan", validate_anchor_map_plan(resolve_manifest_path(str(data.get("anchor_map_plan", "")), repo_root, path.parent))),
            ("neighborhood_extract_plan", validate_neighborhood_extract_plan(resolve_manifest_path(str(data.get("neighborhood_extract_plan", "")), repo_root, path.parent))),
            ("orthology_anchor_plan", validate_orthology_anchor_plan(resolve_manifest_path(str(data.get("orthology_anchor_plan", "")), repo_root, path.parent))),
            ("reciprocal_search_plan", validate_reciprocal_search_plan(resolve_manifest_path(str(data.get("reciprocal_search_plan", "")), repo_root, path.parent))),
            ("pathway_completeness_plan", validate_pathway_completeness_plan(resolve_manifest_path(str(data.get("pathway_completeness_plan", "")), repo_root, path.parent))),
            ("workflow_class_plan", validate_workflow_class_plan(resolve_manifest_path(str(data.get("workflow_class_plan", "")), repo_root, path.parent))),
            ("lane_activation_plan", validate_lane_activation_plan(resolve_manifest_path(str(data.get("lane_activation_plan", "")), repo_root, path.parent))),
            ("evidence_escalation_plan", validate_evidence_escalation_plan(resolve_manifest_path(str(data.get("evidence_escalation_plan", "")), repo_root, path.parent))),
            ("claim_levels", validate_claim_levels(resolve_manifest_path(str(data.get("claim_levels", "")), repo_root, path.parent))),
            (
                "workflow_deferred_lanes",
                validate_workflow_deferred_lanes(
                    resolve_manifest_path(str(data.get("workflow_deferred_lanes", "")), repo_root, path.parent),
                    require_deferred_budget=(run_scope == "full_campaign_24h"),
                ),
            ),
            (
                "query_resolution_plan",
                validate_query_resolution_plan(
                    resolve_manifest_path(str(data.get("query_resolution_plan", "")), repo_root, path.parent),
                    execution_ready=(launch_ready or execution_ready),
                ),
            ),
            ("decoy_plan", validate_decoy_plan(resolve_manifest_path(str(data.get("decoy_plan", "")), repo_root, path.parent))),
            (
                "run_economics",
                validate_run_economics(
                    resolve_manifest_path(str(data.get("run_economics", "")), repo_root, path.parent),
                    execution_ready=(launch_ready or execution_ready),
                ),
            ),
            ("search_plan", validate_search_plan(resolve_manifest_path(str(data.get("search_plan", "")), repo_root, path.parent))),
            ("tool_requirements", validate_tool_requirements(resolve_manifest_path(str(data.get("tool_requirements", "")), repo_root, path.parent))),
            (
                "provider_payload",
                validate_provider_payload(
                    resolve_manifest_path(str(data.get("provider_payload", "")), repo_root, path.parent),
                    repo_root=repo_root,
                    execution_ready=(launch_ready or execution_ready),
                ),
            ),
        ]
        if data.get("artifact_pull_manifest"):
            results.append(
                (
                    "artifact_pull_manifest",
                    validate_artifact_pull_manifest(
                        resolve_manifest_path(str(data.get("artifact_pull_manifest", "")), repo_root, path.parent),
                        repo_root=repo_root,
                    ),
                )
            )
        for name, result in results:
            errors.extend(f"{name}: {error}" for error in result["errors"])
            warnings.extend(f"{name}: {warning}" for warning in result["warnings"])

    payload_hash = data.get("launch_payload_sha256")
    if payload_hash:
        copied = dict(data)
        copied.pop("launch_payload_sha256", None)
        actual = hashlib.sha256(json.dumps(copied, sort_keys=True).encode("utf-8")).hexdigest()
        if actual.lower() != str(payload_hash).lower():
            errors.append("launch_payload_sha256 mismatch")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def scan_local_artifacts(root: Path, *, max_bytes: int = DEFAULT_LOCAL_SUMMARY_LIMIT_BYTES) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root = root.resolve()
    skip_dirs = {".git", ".runtime", "__pycache__", "node_modules", ".venv", "dist", "build"}

    for path in root.rglob("*"):
        rel = path.relative_to(root)
        parts = set(rel.parts)
        if parts & skip_dirs:
            continue
        if path.is_dir():
            if path.name in BLOCKED_LOCAL_DIR_NAMES:
                errors.append(f"blocked local heavy-work directory present: {rel}")
            continue
        if path.name in {".DS_Store"}:
            continue
        lower = path.name.lower()
        if rel in ALLOWED_LOCAL_ARTIFACT_FIXTURES:
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > ALLOWED_LOCAL_ARTIFACT_FIXTURE_MAX_BYTES:
                errors.append(f"public fixture exceeds tiny-fixture limit ({size} bytes): {rel}")
            continue
        if any(lower.endswith(suffix) for suffix in RAW_OR_LARGE_SUFFIXES):
            errors.append(f"blocked local raw/large artifact present: {rel}")
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > max_bytes:
            warnings.append(f"large local file exceeds summary limit ({size} bytes): {rel}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def merge_results(results: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    for name, result in results:
        details[name] = result
        errors.extend(f"{name}: {error}" for error in result["errors"])
        warnings.extend(f"{name}: {warning}" for warning in result["warnings"])
    return {"ok": not errors, "errors": errors, "warnings": warnings, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GeneCluster campaign prep artifacts.")
    parser.add_argument("--campaign", type=Path, help="Campaign manifest JSON.")
    parser.add_argument("--project-goals", type=Path, help="project-goals.yaml.")
    parser.add_argument("--pathway-steps", type=Path, help="pathway-steps.tsv.")
    parser.add_argument("--data-ledger", type=Path, help="data-ledger.tsv.")
    parser.add_argument("--query-ledger", type=Path, help="query-ledger.tsv.")
    parser.add_argument("--query-registry", type=Path, help="genecluster-query-registry.tsv.")
    parser.add_argument("--required-claims", type=Path, help="required-claims.tsv.")
    parser.add_argument("--source-ledger", type=Path, help="source-ledger.tsv.")
    parser.add_argument("--read-accessions", type=Path, help="read-accessions.tsv.")
    parser.add_argument("--resource-ledger", type=Path, help="resource-ledger.tsv.")
    parser.add_argument("--database-ledger", type=Path, help="database-ledger.tsv.")
    parser.add_argument("--cache-ledger", type=Path, help="cache-ledger.tsv.")
    parser.add_argument("--db-bootstrap-plan", type=Path, help="db-bootstrap-plan.json.")
    parser.add_argument("--data-materialization-plan", type=Path, help="data-materialization-plan.json.")
    parser.add_argument("--target-db-plan", type=Path, help="target-db-plan.json.")
    parser.add_argument("--candidate-route-plan", type=Path, help="candidate-route-plan.json.")
    parser.add_argument("--reference-import-plan", type=Path, help="reference-import-plan.json.")
    parser.add_argument("--anchor-map-plan", type=Path, help="anchor-map-plan.json.")
    parser.add_argument("--neighborhood-extract-plan", type=Path, help="neighborhood-extract-plan.json.")
    parser.add_argument("--orthology-anchor-plan", type=Path, help="orthology-anchor-plan.json.")
    parser.add_argument("--reciprocal-search-plan", type=Path, help="reciprocal-search-plan.json.")
    parser.add_argument("--pathway-completeness-plan", type=Path, help="pathway-completeness-plan.json.")
    parser.add_argument("--query-resolution-plan", type=Path, help="query-resolution-plan.json.")
    parser.add_argument("--decoy-plan", type=Path, help="decoy-plan.json.")
    parser.add_argument("--run-economics", type=Path, help="run-economics.json.")
    parser.add_argument("--workflow-class-plan", type=Path, help="workflow-class-plan.json.")
    parser.add_argument("--lane-activation-plan", type=Path, help="lane-activation-plan.json.")
    parser.add_argument("--evidence-escalation-plan", type=Path, help="evidence-escalation-plan.json.")
    parser.add_argument("--claim-levels", type=Path, help="claim-levels.tsv.")
    parser.add_argument("--workflow-deferred-lanes", type=Path, help="workflow-deferred-lanes.tsv.")
    parser.add_argument("--search-plan", type=Path, help="search-plan.json.")
    parser.add_argument("--tool-requirements", type=Path, help="tool-requirements.json.")
    parser.add_argument("--provider-payload", type=Path, help="Provider payload JSON or shell script.")
    parser.add_argument("--artifact-pull-manifest", type=Path, help="artifact_pull.yaml or compatible JSON.")
    parser.add_argument("--candidate-hits", type=Path, help="candidate_hits.tsv.")
    parser.add_argument("--candidate-ranking", type=Path, help="candidate-ranking.tsv.")
    parser.add_argument("--candidate-anchors", type=Path, help="candidate_anchors.tsv.")
    parser.add_argument("--cluster-neighborhoods", type=Path, help="cluster_neighborhoods.tsv.")
    parser.add_argument("--neighbor-annotations", type=Path, help="neighbor_annotations.tsv.")
    parser.add_argument("--domain-labels", type=Path, help="domain_labels.tsv.")
    parser.add_argument("--target-db-resolved", type=Path, help="target-db-ledger.resolved.tsv.")
    parser.add_argument("--target-db-indexes", type=Path, help="target-db-indexes.tsv.")
    parser.add_argument("--orthology-links", type=Path, help="orthology_links.tsv.")
    parser.add_argument("--anchor-ladder", type=Path, help="anchor_ladder.tsv.")
    parser.add_argument("--reciprocal-hits", type=Path, help="reciprocal_hits.tsv.")
    parser.add_argument("--neighborhood-hypotheses", type=Path, help="neighborhood_hypotheses.tsv.")
    parser.add_argument("--pathway-completeness", type=Path, help="pathway_completeness.tsv.")
    parser.add_argument("--isoform-ledger", type=Path, help="isoform-ledger.tsv.")
    parser.add_argument("--isoform-classification", type=Path, help="isoform-classification.tsv.")
    parser.add_argument("--isoform-orfs", type=Path, help="isoform-orfs.tsv.")
    parser.add_argument("--isoform-domain-delta", type=Path, help="isoform-domain-delta.tsv.")
    parser.add_argument("--longread-qc", type=Path, help="longread-qc.json.")
    parser.add_argument("--transcriptome-build-ledger", type=Path, help="transcriptome-build-ledger.tsv.")
    parser.add_argument("--assembly-qc", type=Path, help="assembly-qc.tsv.")
    parser.add_argument("--orf-ledger", type=Path, help="orf-ledger.tsv.")
    parser.add_argument("--isoform-groups", type=Path, help="isoform-groups.tsv.")
    parser.add_argument("--orthogroup-ledger", type=Path, help="orthogroup-ledger.tsv.")
    parser.add_argument("--paralog-homeolog-ledger", type=Path, help="paralog-homeolog-ledger.tsv.")
    parser.add_argument("--copy-classification", type=Path, help="copy-classification.tsv.")
    parser.add_argument("--gene-tree-summary", type=Path, help="gene-tree-summary.tsv.")
    parser.add_argument("--synteny-support", type=Path, help="synteny-support.tsv.")
    parser.add_argument("--expression-design", type=Path, help="expression-design.tsv.")
    parser.add_argument("--expression-matrix-manifest", type=Path, help="expression-matrix-manifest.json.")
    parser.add_argument("--tissue-specificity", type=Path, help="tissue-specificity.tsv.")
    parser.add_argument("--coexpression-modules", type=Path, help="coexpression-modules.tsv.")
    parser.add_argument("--assembly-ledger", type=Path, help="assembly-ledger.tsv.")
    parser.add_argument("--annotation-ledger", type=Path, help="annotation-ledger.tsv.")
    parser.add_argument("--route-annotation-ledger", type=Path, help="route-scout annotation-ledger.tsv.")
    parser.add_argument("--coordinate-liftover-ledger", type=Path, help="coordinate-liftover-ledger.tsv.")
    parser.add_argument("--comparative-neighborhoods", type=Path, help="comparative_neighborhoods.tsv.")
    parser.add_argument("--pav-copy-number", type=Path, help="pav-copy-number.tsv.")
    parser.add_argument("--sv-ledger", type=Path, help="sv-ledger.tsv.")
    parser.add_argument("--candidate-interval-sv", type=Path, help="candidate_interval_sv.tsv.")
    parser.add_argument("--graph-ledger", type=Path, help="graph-ledger.tsv.")
    parser.add_argument("--graph-path-support", type=Path, help="graph_path_support.tsv.")
    parser.add_argument("--singlecell-dataset-ledger", type=Path, help="singlecell-dataset-ledger.tsv.")
    parser.add_argument("--spatial-domain-expression", type=Path, help="spatial-domain-expression.tsv.")
    parser.add_argument("--require-deferred-budget", action="store_true", help="Require at least one deferred_by_budget pathway completeness row.")
    parser.add_argument("--evidence-jsonl", type=Path, help="evidence.jsonl.")
    parser.add_argument("--claim-audit-jsonl", type=Path, help="claim-audit.jsonl.")
    parser.add_argument("--provenance-jsonl", type=Path, help="provenance.jsonl.")
    parser.add_argument("--claim-ledger", type=Path, help="claim-ledger.md.")
    parser.add_argument("--launch-manifest", type=Path, help="launch-manifest.json.")
    parser.add_argument("--dossier-manifest", type=Path, help="dossier-manifest.json.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repo root for local artifact checks.")
    parser.add_argument("--launch-ready", action="store_true", help="Require launch credentials/provider setup, not just review-ready payloads.")
    parser.add_argument("--execution-ready", action="store_true", help="Require full heavy-run DB/cache/search/provider readiness.")
    parser.add_argument("--strict-resources", action="store_true", help="Treat restricted-or-review resources without approval as errors.")
    parser.add_argument("--scan-local-artifacts", action="store_true", help="Scan repo root for raw sequence, database, and heavy workflow artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    results: list[tuple[str, dict[str, Any]]] = []
    web_policy = "container-only"

    if args.campaign:
        campaign_result = validate_campaign_manifest(args.campaign)
        results.append(("campaign", campaign_result))
        try:
            campaign_data = json.loads(args.campaign.read_text(encoding="utf-8"))
            web_policy = campaign_data.get("execution", {}).get("web_tool_policy", "container-only")
        except (OSError, json.JSONDecodeError):
            pass
    if args.project_goals:
        results.append(("project-goals", validate_project_goals(args.project_goals)))
    if args.pathway_steps:
        results.append(("pathway-steps", validate_pathway_steps(args.pathway_steps)))
    if args.data_ledger:
        results.append(("data-ledger", validate_data_ledger(args.data_ledger)))
    if args.query_ledger:
        results.append(("query-ledger", validate_query_ledger(args.query_ledger)))
    if args.query_registry:
        results.append(("query-registry", validate_query_registry(args.query_registry)))
    if args.required_claims:
        results.append(("required-claims", validate_required_claims(args.required_claims, query_registry=args.query_registry)))
    if args.source_ledger:
        results.append(("source-ledger", validate_source_ledger(args.source_ledger)))
    if args.read_accessions:
        results.append(("read-accessions", validate_read_accessions(args.read_accessions)))
    if args.resource_ledger:
        results.append(("resource-ledger", validate_resource_ledger(args.resource_ledger, web_tool_policy=web_policy, strict=args.strict_resources)))
    if args.database_ledger:
        results.append(("database-ledger", validate_database_ledger(args.database_ledger, repo_root=args.repo_root)))
    if args.cache_ledger:
        results.append(("cache-ledger", validate_cache_ledger(args.cache_ledger, repo_root=args.repo_root)))
    if args.db_bootstrap_plan:
        results.append(("db-bootstrap-plan", validate_db_bootstrap_plan(args.db_bootstrap_plan)))
    if args.data_materialization_plan:
        results.append(("data-materialization-plan", validate_data_materialization_plan(args.data_materialization_plan, execution_ready=args.execution_ready or args.launch_ready)))
    if args.target_db_plan:
        results.append(("target-db-plan", validate_target_db_plan(args.target_db_plan, repo_root=args.repo_root)))
    if args.candidate_route_plan:
        results.append(("candidate-route-plan", validate_candidate_route_plan(args.candidate_route_plan)))
    if args.reference_import_plan:
        results.append(("reference-import-plan", validate_reference_import_plan(args.reference_import_plan)))
    if args.anchor_map_plan:
        results.append(("anchor-map-plan", validate_anchor_map_plan(args.anchor_map_plan)))
    if args.neighborhood_extract_plan:
        results.append(("neighborhood-extract-plan", validate_neighborhood_extract_plan(args.neighborhood_extract_plan)))
    if args.orthology_anchor_plan:
        results.append(("orthology-anchor-plan", validate_orthology_anchor_plan(args.orthology_anchor_plan)))
    if args.reciprocal_search_plan:
        results.append(("reciprocal-search-plan", validate_reciprocal_search_plan(args.reciprocal_search_plan)))
    if args.pathway_completeness_plan:
        results.append(("pathway-completeness-plan", validate_pathway_completeness_plan(args.pathway_completeness_plan)))
    if args.query_resolution_plan:
        results.append(("query-resolution-plan", validate_query_resolution_plan(args.query_resolution_plan, execution_ready=args.execution_ready or args.launch_ready)))
    if args.decoy_plan:
        results.append(("decoy-plan", validate_decoy_plan(args.decoy_plan)))
    if args.run_economics:
        results.append(("run-economics", validate_run_economics(args.run_economics, execution_ready=args.execution_ready or args.launch_ready)))
    if args.workflow_class_plan:
        results.append(("workflow-class-plan", validate_workflow_class_plan(args.workflow_class_plan)))
    if args.lane_activation_plan:
        results.append(("lane-activation-plan", validate_lane_activation_plan(args.lane_activation_plan)))
    if args.evidence_escalation_plan:
        results.append(("evidence-escalation-plan", validate_evidence_escalation_plan(args.evidence_escalation_plan)))
    if args.claim_levels:
        results.append(("claim-levels", validate_claim_levels(args.claim_levels)))
    if args.workflow_deferred_lanes:
        results.append(("workflow-deferred-lanes", validate_workflow_deferred_lanes(args.workflow_deferred_lanes, require_deferred_budget=args.require_deferred_budget)))
    if args.search_plan:
        results.append(("search-plan", validate_search_plan(args.search_plan)))
    if args.tool_requirements:
        results.append(("tool-requirements", validate_tool_requirements(args.tool_requirements)))
    if args.provider_payload:
        results.append(("provider-payload", validate_provider_payload(args.provider_payload, repo_root=args.repo_root, execution_ready=args.execution_ready or args.launch_ready)))
    if args.artifact_pull_manifest:
        results.append(("artifact-pull-manifest", validate_artifact_pull_manifest(args.artifact_pull_manifest, repo_root=args.repo_root)))
    if args.candidate_hits:
        results.append(("candidate-hits", validate_candidate_hits(args.candidate_hits)))
    if args.candidate_ranking:
        results.append(("candidate-ranking", validate_candidate_ranking(args.candidate_ranking)))
    if args.candidate_anchors:
        results.append(("candidate-anchors", validate_candidate_anchors(args.candidate_anchors)))
    if args.cluster_neighborhoods:
        results.append(("cluster-neighborhoods", validate_cluster_neighborhoods(args.cluster_neighborhoods)))
    if args.neighbor_annotations:
        results.append(("neighbor-annotations", validate_neighbor_annotations(args.neighbor_annotations)))
    if args.domain_labels:
        results.append(("domain-labels", validate_domain_labels(args.domain_labels)))
    if args.target_db_resolved:
        results.append(("target-db-resolved", validate_target_db_resolved(args.target_db_resolved, repo_root=args.repo_root)))
    if args.target_db_indexes:
        results.append(("target-db-indexes", validate_target_db_indexes(args.target_db_indexes, repo_root=args.repo_root)))
    if args.orthology_links:
        results.append(("orthology-links", validate_orthology_links(args.orthology_links)))
    if args.anchor_ladder:
        results.append(("anchor-ladder", validate_anchor_ladder(args.anchor_ladder)))
    if args.reciprocal_hits:
        results.append(("reciprocal-hits", validate_reciprocal_hits(args.reciprocal_hits)))
    if args.neighborhood_hypotheses:
        results.append(("neighborhood-hypotheses", validate_neighborhood_hypotheses(args.neighborhood_hypotheses)))
    if args.pathway_completeness:
        results.append(("pathway-completeness", validate_pathway_completeness(args.pathway_completeness, require_deferred_budget=args.require_deferred_budget)))
    if args.isoform_ledger:
        results.append(("isoform-ledger", validate_summary_table(args.isoform_ledger, required_columns=ISOFORM_LEDGER_COLUMNS, label="isoform ledger", repo_root=args.repo_root)))
    if args.isoform_classification:
        results.append(("isoform-classification", validate_summary_table(args.isoform_classification, required_columns=ISOFORM_CLASSIFICATION_COLUMNS, label="isoform classification", repo_root=args.repo_root)))
    if args.isoform_orfs:
        results.append(("isoform-orfs", validate_summary_table(args.isoform_orfs, required_columns=ISOFORM_ORF_COLUMNS, label="isoform ORFs", repo_root=args.repo_root)))
    if args.isoform_domain_delta:
        results.append(("isoform-domain-delta", validate_summary_table(args.isoform_domain_delta, required_columns=ISOFORM_DOMAIN_DELTA_COLUMNS, label="isoform domain delta", repo_root=args.repo_root)))
    if args.longread_qc:
        results.append(("longread-qc", validate_longread_qc(args.longread_qc)))
    if args.transcriptome_build_ledger:
        results.append(("transcriptome-build-ledger", validate_summary_table(args.transcriptome_build_ledger, required_columns=TRANSCRIPTOME_BUILD_LEDGER_COLUMNS, label="transcriptome build ledger", repo_root=args.repo_root)))
    if args.assembly_qc:
        results.append(("assembly-qc", validate_summary_table(args.assembly_qc, required_columns=ASSEMBLY_QC_COLUMNS, label="assembly QC", repo_root=args.repo_root)))
    if args.orf_ledger:
        results.append(("orf-ledger", validate_summary_table(args.orf_ledger, required_columns=ORF_LEDGER_COLUMNS, label="ORF ledger", repo_root=args.repo_root)))
    if args.isoform_groups:
        results.append(("isoform-groups", validate_summary_table(args.isoform_groups, required_columns=ISOFORM_GROUP_COLUMNS, label="isoform groups", repo_root=args.repo_root)))
    if args.orthogroup_ledger:
        results.append(("orthogroup-ledger", validate_summary_table(args.orthogroup_ledger, required_columns=ORTHOGROUP_LEDGER_COLUMNS, label="orthogroup ledger", repo_root=args.repo_root)))
    if args.paralog_homeolog_ledger:
        results.append(("paralog-homeolog-ledger", validate_summary_table(args.paralog_homeolog_ledger, required_columns=PARALOG_HOMEOLOG_LEDGER_COLUMNS, label="paralog/homeolog ledger", repo_root=args.repo_root)))
    if args.copy_classification:
        results.append(("copy-classification", validate_summary_table(args.copy_classification, required_columns=COPY_CLASSIFICATION_COLUMNS, label="copy classification", repo_root=args.repo_root)))
    if args.gene_tree_summary:
        results.append(("gene-tree-summary", validate_summary_table(args.gene_tree_summary, required_columns=GENE_TREE_SUMMARY_COLUMNS, label="gene tree summary", repo_root=args.repo_root)))
    if args.synteny_support:
        results.append(("synteny-support", validate_summary_table(args.synteny_support, required_columns=SYNTENY_SUPPORT_COLUMNS, label="synteny support", repo_root=args.repo_root)))
    if args.expression_design:
        results.append(("expression-design", validate_summary_table(args.expression_design, required_columns=EXPRESSION_DESIGN_COLUMNS, label="expression design", repo_root=args.repo_root)))
    if args.expression_matrix_manifest:
        results.append(("expression-matrix-manifest", validate_expression_matrix_manifest(args.expression_matrix_manifest, repo_root=args.repo_root)))
    if args.tissue_specificity:
        results.append(("tissue-specificity", validate_summary_table(args.tissue_specificity, required_columns=TISSUE_SPECIFICITY_COLUMNS, label="tissue specificity", repo_root=args.repo_root)))
    if args.coexpression_modules:
        results.append(("coexpression-modules", validate_summary_table(args.coexpression_modules, required_columns=COEXPRESSION_MODULE_COLUMNS, label="coexpression modules", repo_root=args.repo_root)))
    if args.assembly_ledger:
        results.append(("assembly-ledger", validate_summary_table(args.assembly_ledger, required_columns=ASSEMBLY_LEDGER_COLUMNS, label="assembly ledger", repo_root=args.repo_root)))
    if args.annotation_ledger:
        results.append(("annotation-ledger", validate_summary_table(args.annotation_ledger, required_columns=ANNOTATION_LEDGER_COLUMNS, label="annotation ledger", repo_root=args.repo_root)))
    if args.route_annotation_ledger:
        results.append(("route-annotation-ledger", validate_route_annotation_ledger(args.route_annotation_ledger, repo_root=args.repo_root)))
    if args.coordinate_liftover_ledger:
        results.append(("coordinate-liftover-ledger", validate_summary_table(args.coordinate_liftover_ledger, required_columns=COORDINATE_LIFTOVER_LEDGER_COLUMNS, label="coordinate liftover ledger", repo_root=args.repo_root)))
    if args.comparative_neighborhoods:
        results.append(("comparative-neighborhoods", validate_summary_table(args.comparative_neighborhoods, required_columns=COMPARATIVE_NEIGHBORHOOD_COLUMNS, label="comparative neighborhoods", repo_root=args.repo_root)))
    if args.pav_copy_number:
        results.append(("pav-copy-number", validate_summary_table(args.pav_copy_number, required_columns=PAV_COPY_NUMBER_COLUMNS, label="PAV copy number", repo_root=args.repo_root)))
    if args.sv_ledger:
        results.append(("sv-ledger", validate_summary_table(args.sv_ledger, required_columns=SV_LEDGER_COLUMNS, label="SV ledger", repo_root=args.repo_root)))
    if args.candidate_interval_sv:
        results.append(("candidate-interval-sv", validate_summary_table(args.candidate_interval_sv, required_columns=CANDIDATE_INTERVAL_SV_COLUMNS, label="candidate interval SV", repo_root=args.repo_root)))
    if args.graph_ledger:
        results.append(("graph-ledger", validate_summary_table(args.graph_ledger, required_columns=GRAPH_LEDGER_COLUMNS, label="graph ledger", repo_root=args.repo_root)))
    if args.graph_path_support:
        results.append(("graph-path-support", validate_summary_table(args.graph_path_support, required_columns=GRAPH_PATH_SUPPORT_COLUMNS, label="graph path support", repo_root=args.repo_root)))
    if args.singlecell_dataset_ledger:
        results.append(("singlecell-dataset-ledger", validate_summary_table(args.singlecell_dataset_ledger, required_columns=SINGLECELL_DATASET_LEDGER_COLUMNS, label="single-cell dataset ledger", repo_root=args.repo_root)))
    if args.spatial_domain_expression:
        results.append(("spatial-domain-expression", validate_summary_table(args.spatial_domain_expression, required_columns=SPATIAL_DOMAIN_EXPRESSION_COLUMNS, label="spatial/domain expression", repo_root=args.repo_root)))
    if args.evidence_jsonl:
        results.append((
            "evidence-jsonl",
            validate_jsonl(
                args.evidence_jsonl,
                required_keys={"claim_id", "subject_id", "evidence_class", "source_artifact", "confidence", "review_status"},
                label="evidence.jsonl",
            ),
        ))
    if args.claim_audit_jsonl:
        results.append(("claim-audit-jsonl", validate_claim_audit_jsonl(args.claim_audit_jsonl)))
    if args.provenance_jsonl:
        results.append((
            "provenance-jsonl",
            validate_jsonl(
                args.provenance_jsonl,
                required_keys={"kind", "campaign_id"},
                label="provenance.jsonl",
            ),
        ))
    if args.claim_ledger:
        results.append(("claim-ledger", validate_claim_ledger(args.claim_ledger)))
    if args.launch_manifest:
        results.append(("launch-manifest", validate_launch_manifest(args.launch_manifest, repo_root=args.repo_root, launch_ready=args.launch_ready, execution_ready=args.execution_ready)))
    if args.dossier_manifest:
        results.append(("dossier-manifest", validate_dossier_manifest(args.dossier_manifest, repo_root=args.repo_root)))
    if args.scan_local_artifacts:
        results.append(("local-artifact-scan", scan_local_artifacts(args.repo_root)))

    if not results:
        parser.error("provide at least one artifact to validate")

    result = merge_results(results)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("BioSymphony GeneCluster preflight: ok" if result["ok"] else "BioSymphony GeneCluster preflight: failed")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
