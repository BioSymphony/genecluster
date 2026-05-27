#!/usr/bin/env python3
"""Validate GeneCluster Atlas ledgers, review surfaces, and provider handoffs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


CLAIM_LEVELS = {
    "L0_route_only",
    "L1_candidate_gene_only",
    "L1_sequence_rescue_only",
    "L2_coordinate_context_ready",
    "L2_annotation_assets_need_join_repair",
    "L3_annotation_neighborhood_ready",
    "L4_consensus_supported",
    "L5_claim_audited_dossier_ready",
}

CLUSTER_CALLERS = {
    "annotation_direct",
    "plantiSMASH",
    "plantismash",
    "cblaster",
    "clinker",
    "antiSMASH",
    "antismash",
    "mock_plantiSMASH",
    "mock_cblaster",
    "mock_clinker",
}

BGC_VERDICTS = {
    "supported",
    "candidate",
    "weak_support",
    "conflict",
    "rejected",
    "deferred",
    "not_run",
}

DISAGREEMENT_STATUSES = {"none", "present", "insufficient_callers"}

PROTEIN_JURY_VERDICTS = {
    "supported",
    "candidate",
    "ambiguous",
    "contradictory",
    "unknown",
    "rejected",
    "deferred",
}

REVIEW_STATUSES = {"accepted", "rejected", "needs-human-review", "publication-candidate"}

COMPARATIVE_STATUSES = {
    "present",
    "absent",
    "not_run",
    "candidate",
    "supported",
    "conflict",
    "fixture",
}

RAW_HEAVY_SUFFIXES = (
    ".fastq",
    ".fastq.gz",
    ".fq",
    ".fq.gz",
    ".sra",
    ".bam",
    ".sam",
    ".cram",
    ".fasta",
    ".fa",
    ".fna",
    ".faa",
    ".gff",
    ".gff3",
    ".gtf",
    ".dmnd",
    ".hmm",
    ".bt2",
    ".mmi",
    ".idx",
    ".sqlite",
)

CLUSTER_CALL_COLUMNS = {
    "cluster_id",
    "caller",
    "source_species",
    "target_species",
    "contig",
    "start",
    "end",
    "core_genes",
    "confidence",
    "claim_level",
}

BGC_CONSENSUS_COLUMNS = {
    "consensus_id",
    "cluster_id",
    "verdict",
    "caller_count",
    "agreeing_callers",
    "disagreeing_callers",
    "disagreement_status",
    "claim_level",
    "caller_versions",
    "caller_licenses",
}

PROTEIN_FUNCTION_VOTE_COLUMNS = {
    "protein_id",
    "tool",
    "function_label",
    "confidence",
    "evidence_level",
    "tool_version",
    "license",
}

PROTEIN_FUNCTION_JURY_COLUMNS = {
    "protein_id",
    "verdict",
    "claim_level",
    "supporting_tools",
    "contradicting_tools",
    "confidence",
}

COMPARATIVE_ATLAS_FILES = {
    "species-ledger.tsv": {"species_id", "scientific_name", "assembly_id", "annotation_id", "data_status", "license"},
    "orthogroups.tsv": {"orthogroup_id", "species_id", "protein_id", "paralog_group", "orthology_status"},
    "synteny_blocks.tsv": {"block_id", "species_id", "contig", "start", "end", "anchor_gene", "support_status"},
    "cluster_call_matrix.tsv": {"cluster_id", "species_id", "caller", "call_status", "claim_level"},
    "comparative_neighborhoods.tsv": {"neighborhood_id", "species_id", "cluster_id", "gene_id", "relative_order", "function_label"},
    "atlas-summary.md": set(),
}


def result(errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    return {"ok": not errors, "errors": errors, "warnings": warnings or []}


def read_tsv(path: Path, required_columns: set[str], label: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            fieldnames = set(reader.fieldnames or [])
            missing = sorted(required_columns - fieldnames)
            if missing:
                errors.append(f"{label} missing columns: {', '.join(missing)}")
            rows = [dict(row) for row in reader]
    except OSError as exc:
        return [], result([f"{label}: {exc}"])
    if not rows and path.suffix == ".tsv":
        errors.append(f"{label} must contain at least one row")
    return rows, result(errors)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[;,|]", value or "") if item.strip()]


def parse_int(value: str, label: str, errors: list[str]) -> int | None:
    try:
        return int(str(value).replace(",", ""))
    except ValueError:
        errors.append(f"{label} must be an integer")
        return None


def validate_confidence(value: str, label: str, errors: list[str]) -> None:
    text = str(value or "").strip()
    if not text:
        errors.append(f"{label} confidence is required")
        return
    if text.lower() in {"low", "medium", "high", "unknown", "not_applicable"}:
        return
    try:
        numeric = float(text)
    except ValueError:
        errors.append(f"{label} confidence must be 0..1 or a recognized label")
        return
    if numeric < 0 or numeric > 1:
        errors.append(f"{label} confidence must be between 0 and 1")


def validate_claim_level(value: str, label: str, errors: list[str]) -> None:
    if value not in CLAIM_LEVELS:
        errors.append(f"{label} invalid claim_level: {value}")


def parse_key_value_map(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in split_list(value):
        if "=" in item:
            key, val = item.split("=", 1)
            parsed[key.strip()] = val.strip()
    return parsed


def normalized_gene_set(value: str) -> tuple[str, ...]:
    return tuple(sorted(split_list(value)))


def path_is_raw_heavy(path_value: str) -> bool:
    lower = path_value.lower()
    return any(lower.endswith(suffix) for suffix in RAW_HEAVY_SUFFIXES)


def validate_cluster_calls(path: Path) -> dict[str, Any]:
    rows, header_result = read_tsv(path, CLUSTER_CALL_COLUMNS, "cluster_calls.tsv")
    errors = list(header_result["errors"])
    warnings = list(header_result["warnings"])
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        row_label = f"cluster_calls.tsv line {index}"
        key = (row.get("cluster_id", ""), row.get("caller", ""))
        if not key[0]:
            errors.append(f"{row_label} cluster_id is required")
        if not key[1]:
            errors.append(f"{row_label} caller is required")
        elif key[1] not in CLUSTER_CALLERS:
            warnings.append(f"{row_label} caller is not in the known caller list: {key[1]}")
        if key in seen:
            errors.append(f"{row_label} duplicates cluster_id/caller pair: {key[0]} {key[1]}")
        seen.add(key)
        start = parse_int(row.get("start", ""), f"{row_label} start", errors)
        end = parse_int(row.get("end", ""), f"{row_label} end", errors)
        if start is not None and end is not None and end < start:
            errors.append(f"{row_label} end must be >= start")
        if not row.get("contig"):
            errors.append(f"{row_label} contig is required")
        if not split_list(row.get("core_genes", "")):
            errors.append(f"{row_label} core_genes must list at least one gene")
        validate_confidence(row.get("confidence", ""), row_label, errors)
        validate_claim_level(row.get("claim_level", ""), row_label, errors)
    return result(errors, warnings)


def cluster_disagreement_map(cluster_call_rows: list[dict[str, str]]) -> dict[str, bool]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in cluster_call_rows:
        grouped.setdefault(row.get("cluster_id", ""), []).append(row)
    disagreements: dict[str, bool] = {}
    for cluster_id, rows in grouped.items():
        signatures = {
            (
                row.get("contig", ""),
                row.get("start", ""),
                row.get("end", ""),
                normalized_gene_set(row.get("core_genes", "")),
            )
            for row in rows
        }
        callers = {row.get("caller", "") for row in rows}
        disagreements[cluster_id] = len(callers) > 1 and len(signatures) > 1
    return disagreements


def validate_bgc_consensus(path: Path, cluster_calls: Path | None = None) -> dict[str, Any]:
    rows, header_result = read_tsv(path, BGC_CONSENSUS_COLUMNS, "bgc_consensus.tsv")
    errors = list(header_result["errors"])
    disagreements: dict[str, bool] = {}
    call_cluster_ids: set[str] = set()
    call_callers_by_cluster: dict[str, set[str]] = {}
    if cluster_calls:
        call_rows, call_result = read_tsv(cluster_calls, CLUSTER_CALL_COLUMNS, "cluster_calls.tsv")
        errors.extend(call_result["errors"])
        disagreements = cluster_disagreement_map(call_rows)
        for call in call_rows:
            cluster_id = call.get("cluster_id", "")
            caller = call.get("caller", "")
            if cluster_id:
                call_cluster_ids.add(cluster_id)
                if caller:
                    call_callers_by_cluster.setdefault(cluster_id, set()).add(caller)
    consensus_cluster_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        row_label = f"bgc_consensus.tsv line {index}"
        if not row.get("consensus_id"):
            errors.append(f"{row_label} consensus_id is required")
        if not row.get("cluster_id"):
            errors.append(f"{row_label} cluster_id is required")
        consensus_cluster_ids.add(row.get("cluster_id", ""))
        if call_cluster_ids and row.get("cluster_id", "") not in call_cluster_ids:
            errors.append(f"{row_label} cluster_id is not present in cluster_calls.tsv")
        if row.get("verdict") not in BGC_VERDICTS:
            errors.append(f"{row_label} verdict must be one of {', '.join(sorted(BGC_VERDICTS))}")
        caller_count = parse_int(row.get("caller_count", ""), f"{row_label} caller_count", errors) or 0
        agreeing = split_list(row.get("agreeing_callers", ""))
        disagreeing = split_list(row.get("disagreeing_callers", ""))
        if caller_count != len(set(agreeing + disagreeing)):
            errors.append(f"{row_label} caller_count must match agreeing_callers plus disagreeing_callers")
        if call_callers_by_cluster.get(row.get("cluster_id", "")) and set(agreeing + disagreeing) != call_callers_by_cluster[row.get("cluster_id", "")]:
            errors.append(f"{row_label} caller list must cover every caller in cluster_calls.tsv")
        status = row.get("disagreement_status", "")
        if status not in DISAGREEMENT_STATUSES:
            errors.append(f"{row_label} disagreement_status must be none, present, or insufficient_callers")
        if caller_count > 1 and disagreements.get(row.get("cluster_id", ""), False) and status != "present":
            errors.append(f"{row_label} collapses caller disagreement; disagreement_status must be present")
        if caller_count > 1 and not disagreements.get(row.get("cluster_id", ""), False) and status == "present":
            errors.append(f"{row_label} marks disagreement present but caller boundaries/core genes agree")
        if status == "present" and not disagreeing:
            errors.append(f"{row_label} disagreement_status present requires disagreeing_callers")
        version_map = parse_key_value_map(row.get("caller_versions", ""))
        license_map = parse_key_value_map(row.get("caller_licenses", ""))
        for caller in set(agreeing + disagreeing):
            if caller not in version_map:
                errors.append(f"{row_label} caller_versions missing {caller}")
            if caller not in license_map:
                errors.append(f"{row_label} caller_licenses missing {caller}")
        validate_claim_level(row.get("claim_level", ""), row_label, errors)
    if call_cluster_ids:
        missing = sorted(call_cluster_ids - consensus_cluster_ids)
        if missing:
            errors.append("bgc_consensus.tsv missing consensus rows for cluster_calls.tsv clusters: " + ", ".join(missing))
    return result(errors)


def validate_protein_function_votes(path: Path) -> dict[str, Any]:
    rows, header_result = read_tsv(path, PROTEIN_FUNCTION_VOTE_COLUMNS, "protein_function_votes.tsv")
    errors = list(header_result["errors"])
    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, start=2):
        row_label = f"protein_function_votes.tsv line {index}"
        for column in ("protein_id", "tool", "function_label", "tool_version", "license"):
            if not row.get(column):
                errors.append(f"{row_label} {column} is required")
        key = (row.get("protein_id", ""), row.get("tool", ""), row.get("function_label", ""))
        if key in seen:
            errors.append(f"{row_label} duplicates protein/tool/function vote: {key[0]} {key[1]} {key[2]}")
        seen.add(key)
        validate_confidence(row.get("confidence", ""), row_label, errors)
        if row.get("evidence_level") not in CLAIM_LEVELS:
            errors.append(f"{row_label} evidence_level must be a GeneCluster claim/evidence level")
    return result(errors)


def vote_contradiction_map(vote_rows: list[dict[str, str]]) -> dict[str, bool]:
    grouped: dict[str, set[str]] = {}
    for row in vote_rows:
        grouped.setdefault(row.get("protein_id", ""), set()).add(row.get("function_label", ""))
    return {protein_id: len({label for label in labels if label}) > 1 for protein_id, labels in grouped.items()}


def validate_protein_function_jury(path: Path, votes: Path | None = None) -> dict[str, Any]:
    rows, header_result = read_tsv(path, PROTEIN_FUNCTION_JURY_COLUMNS, "protein_function_jury.tsv")
    errors = list(header_result["errors"])
    contradictions: dict[str, bool] = {}
    vote_proteins: set[str] = set()
    vote_tools_by_protein: dict[str, set[str]] = {}
    if votes:
        vote_rows, vote_result = read_tsv(votes, PROTEIN_FUNCTION_VOTE_COLUMNS, "protein_function_votes.tsv")
        errors.extend(vote_result["errors"])
        contradictions = vote_contradiction_map(vote_rows)
        for vote in vote_rows:
            protein = vote.get("protein_id", "")
            tool = vote.get("tool", "")
            if protein:
                vote_proteins.add(protein)
                if tool:
                    vote_tools_by_protein.setdefault(protein, set()).add(tool)
    jury_proteins: set[str] = set()
    for index, row in enumerate(rows, start=2):
        row_label = f"protein_function_jury.tsv line {index}"
        if not row.get("protein_id"):
            errors.append(f"{row_label} protein_id is required")
        jury_proteins.add(row.get("protein_id", ""))
        if not row.get("verdict"):
            errors.append(f"{row_label} verdict is required")
        validate_confidence(row.get("confidence", ""), row_label, errors)
        validate_claim_level(row.get("claim_level", ""), row_label, errors)
        if contradictions.get(row.get("protein_id", ""), False) and not split_list(row.get("contradicting_tools", "")):
            errors.append(f"{row_label} collapses contradictory function votes; contradicting_tools is required")
        referenced_tools = set(split_list(row.get("supporting_tools", "")) + split_list(row.get("contradicting_tools", "")))
        available_tools = vote_tools_by_protein.get(row.get("protein_id", ""), set())
        if available_tools and not referenced_tools <= available_tools:
            errors.append(f"{row_label} references tools that did not vote for this protein")
    if vote_proteins:
        missing = sorted(vote_proteins - jury_proteins)
        if missing:
            errors.append("protein_function_jury.tsv missing jury rows for voted proteins: " + ", ".join(missing))
    return result(errors)


def validate_comparative_atlas(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    tables: dict[str, list[dict[str, str]]] = {}
    for name, columns in COMPARATIVE_ATLAS_FILES.items():
        file_path = path / name
        if not file_path.exists():
            errors.append(f"comparative_atlas missing {name}")
            continue
        if file_path.suffix == ".tsv":
            rows, table_result = read_tsv(file_path, columns, name)
            tables[name] = rows
            errors.extend(table_result["errors"])
        elif file_path.suffix == ".md" and not file_path.read_text(encoding="utf-8").strip():
            errors.append(f"{name} must not be empty")

    species_ids = {row.get("species_id", "") for row in tables.get("species-ledger.tsv", [])}
    cluster_ids = {row.get("cluster_id", "") for row in tables.get("cluster_call_matrix.tsv", [])}
    for name in ("orthogroups.tsv", "synteny_blocks.tsv", "cluster_call_matrix.tsv", "comparative_neighborhoods.tsv"):
        for index, row in enumerate(tables.get(name, []), start=2):
            row_label = f"{name} line {index}"
            species_id = row.get("species_id", "")
            if species_ids and species_id not in species_ids:
                errors.append(f"{row_label} species_id is not present in species-ledger.tsv: {species_id}")
            if "claim_level" in row and row.get("claim_level"):
                validate_claim_level(row.get("claim_level", ""), row_label, errors)
            if row.get("call_status") and row.get("call_status") not in COMPARATIVE_STATUSES:
                errors.append(f"{row_label} call_status is not recognized: {row.get('call_status')}")
            if row.get("support_status") and row.get("support_status") not in COMPARATIVE_STATUSES | {"supported", "candidate", "not_applicable"}:
                errors.append(f"{row_label} support_status is not recognized: {row.get('support_status')}")
            if name in {"synteny_blocks.tsv"}:
                start = parse_int(row.get("start", ""), f"{row_label} start", errors)
                end = parse_int(row.get("end", ""), f"{row_label} end", errors)
                if start is not None and end is not None and end < start:
                    errors.append(f"{row_label} end must be >= start")
            if name == "comparative_neighborhoods.tsv":
                try:
                    int(str(row.get("relative_order", "")).replace(",", ""))
                except ValueError:
                    errors.append(f"{row_label} relative_order must be an integer")
                cluster_id = row.get("cluster_id", "")
                if cluster_ids and cluster_id not in cluster_ids:
                    errors.append(f"{row_label} cluster_id is not present in cluster_call_matrix.tsv: {cluster_id}")
    return result(errors)


def load_json(path: Path, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, result([f"{label}: {exc}"])
    except json.JSONDecodeError as exc:
        return {}, result([f"{label}: invalid JSON: {exc}"])
    if not isinstance(data, dict):
        return {}, result([f"{label}: root must be a JSON object"])
    return data, result([])


def iter_artifacts(data: Any) -> list[tuple[str, dict[str, Any]]]:
    artifacts: list[tuple[str, dict[str, Any]]] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in {"source_tables", "generated_files", "expected_artifacts", "artifacts"} and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        artifacts.append((key, item))
            else:
                artifacts.extend(iter_artifacts(value))
    elif isinstance(data, list):
        for item in data:
            artifacts.extend(iter_artifacts(item))
    return artifacts


def validate_no_raw_heavy_artifacts(data: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for group, artifact in iter_artifacts(data):
        path_value = str(artifact.get("path") or artifact.get("local_path") or artifact.get("uri") or "")
        artifact_type = str(artifact.get("artifact_type") or artifact.get("role") or "")
        sensitivity = str(artifact.get("sensitivity") or artifact.get("data_sensitivity") or "")
        if path_value and path_is_raw_heavy(path_value):
            errors.append(f"{label} {group} artifact is raw/heavy and must not be pulled back locally: {path_value}")
        if artifact_type in {"raw_sequence", "raw_reads", "database", "index", "blast_database"}:
            errors.append(f"{label} {group} artifact_type is forbidden for local handoff: {artifact_type}")
        if sensitivity in {"raw", "private_raw", "unpublished_sequence"}:
            errors.append(f"{label} {group} artifact sensitivity is forbidden for local handoff: {sensitivity}")
    return errors


def validate_review_surface_manifest(path: Path) -> dict[str, Any]:
    data, json_result = load_json(path, "review_surface_manifest.json")
    errors = list(json_result["errors"])
    if errors:
        return result(errors)
    for key in ("schema_version", "review_id", "source_tables", "generated_files", "claims"):
        if key not in data:
            errors.append(f"review_surface_manifest.json missing key: {key}")
    if data.get("schema_version") != "genecluster_review_surface.v1":
        errors.append("review_surface_manifest.json schema_version must be genecluster_review_surface.v1")
    if not isinstance(data.get("source_tables", []), list) or not data.get("source_tables"):
        errors.append("review_surface_manifest.json source_tables must be a non-empty list")
    if not isinstance(data.get("generated_files", []), list) or not data.get("generated_files"):
        errors.append("review_surface_manifest.json generated_files must be a non-empty list")
    else:
        generated_paths = [str(item.get("path", "")) for item in data.get("generated_files", []) if isinstance(item, dict)]
        if not any(path.endswith(".html") for path in generated_paths):
            errors.append("review_surface_manifest.json generated_files must include at least one HTML review file")
    claims = data.get("claims", [])
    if not isinstance(claims, list) or not claims:
        errors.append("review_surface_manifest.json claims must be a non-empty list")
    else:
        seen_claim_ids: set[str] = set()
        for index, claim in enumerate(claims, start=1):
            if not isinstance(claim, dict):
                errors.append(f"review_surface_manifest.json claims[{index}] must be an object")
                continue
            for key in ("claim_id", "statement", "claim_level", "evidence_level", "caveat", "review_status"):
                if not claim.get(key):
                    errors.append(f"review_surface_manifest.json claims[{index}] missing {key}")
            claim_id = str(claim.get("claim_id", ""))
            if claim_id in seen_claim_ids:
                errors.append(f"review_surface_manifest.json claims[{index}] duplicates claim_id: {claim_id}")
            seen_claim_ids.add(claim_id)
            if claim.get("review_status") in {"unresolved", "new"}:
                errors.append(f"review_surface_manifest.json claims[{index}] has unresolved review_status")
            elif claim.get("review_status") and claim.get("review_status") not in REVIEW_STATUSES:
                errors.append(f"review_surface_manifest.json claims[{index}] invalid review_status")
            if claim.get("claim_level") and claim.get("claim_level") not in CLAIM_LEVELS:
                errors.append(f"review_surface_manifest.json claims[{index}] invalid claim_level")
            if claim.get("evidence_level") and claim.get("evidence_level") not in CLAIM_LEVELS:
                errors.append(f"review_surface_manifest.json claims[{index}] invalid evidence_level")
    errors.extend(validate_no_raw_heavy_artifacts(data, "review_surface_manifest.json"))
    return result(errors)


def secret_like(value: str) -> bool:
    if not value:
        return False
    if re.search(r"(RUNPOD_API_KEY|HF_TOKEN|OPENAI_API_KEY|GITHUB_TOKEN)\s*=", value):
        return True
    if re.search(r"\b(sk-[A-Za-z0-9_-]{12,}|hf_[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{12,}|rp_[A-Za-z0-9_-]{12,})\b", value):
        return True
    return False


def safe_secret_reference(value: str) -> bool:
    return bool(
        re.match(r"^[A-Z][A-Z0-9_]{3,}$", value)
        or value.startswith("env:")
        or value.startswith("secret://")
        or value.startswith("secure://")
    )


def find_secret_values(data: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = str(key).lower()
            next_path = f"{path}.{key}"
            if isinstance(value, str):
                if secret_like(value):
                    errors.append(f"{next_path} contains a secret-looking value")
                if any(term in key_lower for term in ("api_key", "token", "secret", "password")) and not safe_secret_reference(value):
                    errors.append(f"{next_path} must be an env name or secure reference, not a literal value")
            else:
                errors.extend(find_secret_values(value, next_path))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            errors.extend(find_secret_values(item, f"{path}[{index}]"))
    return errors


def validate_provider_handoff_manifest(path: Path) -> dict[str, Any]:
    data, json_result = load_json(path, "provider_handoff_manifest.json")
    errors = list(json_result["errors"])
    if errors:
        return result(errors)
    for key in ("schema_version", "provider", "workload", "artifact_egress", "safety"):
        if key not in data:
            errors.append(f"provider_handoff_manifest.json missing key: {key}")
    if data.get("schema_version") != "genecluster_provider_handoff.v1":
        errors.append("provider_handoff_manifest.json schema_version must be genecluster_provider_handoff.v1")
    provider = data.get("provider", {})
    if not isinstance(provider, dict):
        errors.append("provider_handoff_manifest.json provider must be an object")
    elif provider.get("adapter") not in {"runpod_bridge", "runpod-bridge"}:
        errors.append("provider_handoff_manifest.json provider.adapter must be runpod_bridge")
    if provider.get("mutation_owner", "host_side_hook") not in {"host_side_hook", "runpod_bridge"}:
        errors.append("provider_handoff_manifest.json provider.mutation_owner must keep paid mutation with host-side bridge hooks")
    workload = data.get("workload", {})
    if not isinstance(workload, dict):
        errors.append("provider_handoff_manifest.json workload must be an object")
    else:
        for key in ("stage_contract", "route_decision"):
            if not workload.get(key):
                errors.append(f"provider_handoff_manifest.json workload.{key} is required")
        cost_bounds = workload.get("cost_bounds", {})
        if not isinstance(cost_bounds, dict) or not cost_bounds:
            errors.append("provider_handoff_manifest.json workload.cost_bounds is required")
        else:
            try:
                max_usd = float(str(cost_bounds.get("max_usd", "")))
                if max_usd <= 0:
                    errors.append("provider_handoff_manifest.json workload.cost_bounds.max_usd must be positive")
            except ValueError:
                errors.append("provider_handoff_manifest.json workload.cost_bounds.max_usd must be numeric")
            if not cost_bounds.get("stop_when_exceeded"):
                errors.append("provider_handoff_manifest.json workload.cost_bounds.stop_when_exceeded is required")
    artifact_egress = data.get("artifact_egress", {})
    if not isinstance(artifact_egress, dict):
        errors.append("provider_handoff_manifest.json artifact_egress must be an object")
    else:
        if artifact_egress.get("summary_only") is not True:
            errors.append("provider_handoff_manifest.json artifact_egress.summary_only must be true")
        if artifact_egress.get("hash_algorithm") not in {"sha256", "SHA256"}:
            errors.append("provider_handoff_manifest.json artifact_egress.hash_algorithm must be sha256")
        expected = artifact_egress.get("expected_artifacts", [])
        if not isinstance(expected, list) or not expected:
            errors.append("provider_handoff_manifest.json artifact_egress.expected_artifacts must be a non-empty list")
        for index, artifact in enumerate(expected if isinstance(expected, list) else [], start=1):
            if not isinstance(artifact, dict):
                errors.append(f"provider_handoff_manifest.json expected_artifacts[{index}] must be an object")
                continue
            if not artifact.get("path"):
                errors.append(f"provider_handoff_manifest.json expected_artifacts[{index}] path is required")
            if artifact.get("artifact_type") in {"raw_sequence", "raw_reads", "database", "index", "blast_database"}:
                errors.append(f"provider_handoff_manifest.json expected_artifacts[{index}] artifact_type is forbidden for egress")
        if not artifact_egress.get("hash_ledger"):
            errors.append("provider_handoff_manifest.json artifact_egress.hash_ledger is required")
    cleanup = data.get("cleanup", {})
    if not isinstance(cleanup, dict) or not cleanup:
        errors.append("provider_handoff_manifest.json cleanup is required")
    else:
        if cleanup.get("verify_pod_stopped") is not True:
            errors.append("provider_handoff_manifest.json cleanup.verify_pod_stopped must be true")
        if cleanup.get("verify_artifacts_fetched") is not True:
            errors.append("provider_handoff_manifest.json cleanup.verify_artifacts_fetched must be true")
    safety = data.get("safety", {})
    if isinstance(safety, dict):
        credentials = safety.get("credentials", [])
        if credentials and not isinstance(credentials, list):
            errors.append("provider_handoff_manifest.json safety.credentials must be a list")
        for index, credential in enumerate(credentials if isinstance(credentials, list) else [], start=1):
            if not isinstance(credential, dict):
                errors.append(f"provider_handoff_manifest.json safety.credentials[{index}] must be an object")
                continue
            value = str(credential.get("env_name") or credential.get("secure_ref") or "")
            if not value:
                errors.append(f"provider_handoff_manifest.json safety.credentials[{index}] needs env_name or secure_ref")
            elif not safe_secret_reference(value):
                errors.append(f"provider_handoff_manifest.json safety.credentials[{index}] must use env_name or secure_ref")
    errors.extend(find_secret_values(data))
    errors.extend(validate_no_raw_heavy_artifacts(data, "provider_handoff_manifest.json"))
    return result(errors)


def combine(results: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, dict[str, Any]] = {}
    for name, item in results:
        checks[name] = item
        errors.extend(f"{name}: {error}" for error in item["errors"])
        warnings.extend(f"{name}: {warning}" for warning in item["warnings"])
    return {"ok": not errors, "errors": errors, "warnings": warnings, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GeneCluster Atlas contract artifacts.")
    parser.add_argument("--cluster-calls", type=Path)
    parser.add_argument("--bgc-consensus", type=Path)
    parser.add_argument("--protein-function-votes", type=Path)
    parser.add_argument("--protein-function-jury", type=Path)
    parser.add_argument("--comparative-atlas", type=Path)
    parser.add_argument("--review-surface-manifest", type=Path)
    parser.add_argument("--provider-handoff-manifest", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    checks: list[tuple[str, dict[str, Any]]] = []
    if args.cluster_calls:
        checks.append(("cluster_calls", validate_cluster_calls(args.cluster_calls)))
    if args.bgc_consensus:
        checks.append(("bgc_consensus", validate_bgc_consensus(args.bgc_consensus, cluster_calls=args.cluster_calls)))
    if args.protein_function_votes:
        checks.append(("protein_function_votes", validate_protein_function_votes(args.protein_function_votes)))
    if args.protein_function_jury:
        checks.append(("protein_function_jury", validate_protein_function_jury(args.protein_function_jury, votes=args.protein_function_votes)))
    if args.comparative_atlas:
        checks.append(("comparative_atlas", validate_comparative_atlas(args.comparative_atlas)))
    if args.review_surface_manifest:
        checks.append(("review_surface_manifest", validate_review_surface_manifest(args.review_surface_manifest)))
    if args.provider_handoff_manifest:
        checks.append(("provider_handoff_manifest", validate_provider_handoff_manifest(args.provider_handoff_manifest)))
    if not checks:
        checks.append(("arguments", result(["at least one artifact path is required"])))

    combined = combine(checks)
    if args.json:
        print(json.dumps(combined, indent=2, sort_keys=True))
    else:
        print("GeneCluster Atlas contracts: ok" if combined["ok"] else "GeneCluster Atlas contracts: failed")
        for error in combined["errors"]:
            print(f"ERROR: {error}")
        for warning in combined["warnings"]:
            print(f"WARN: {warning}")
    return 0 if combined["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
