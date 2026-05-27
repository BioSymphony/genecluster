#!/usr/bin/env python3
"""Check GeneCluster run outputs against the scientific contract.

This is the guardrail an execution agent should run before posting a final
success plan/comment. It catches the failure mode where a workflow produced
plausible-looking rows from reference databases or mocks but did not search
materialized target-organism data.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def real_target_db_id(value: str) -> bool:
    return value.startswith("target_") and not value.startswith("target_mock")


def placeholder_candidate(row: dict[str, str]) -> bool:
    candidate_id = row.get("candidate_id", "")
    dataset_id = row.get("dataset_id", "")
    target_db_id = row.get("target_db_id", "")
    gene_id = row.get("gene_or_transcript_id", "")
    return (
        candidate_id.startswith("GCAND_MOCK")
        or dataset_id in {"provider_search", "mock_provider_summary"}
        or target_db_id in {"provider_search", "target_mock_provider_summary"}
        or gene_id.startswith("mock_")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GeneCluster run outputs against target-search acceptance criteria.")
    parser.add_argument("--summary-dir", type=Path, required=True, help="Returned provider summary directory.")
    parser.add_argument("--require-real-target-search", action="store_true", help="Fail unless target organism materialization, target DB build, and target candidate search are proven.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result.")
    args = parser.parse_args()

    summary_dir = args.summary_dir
    errors: list[str] = []
    warnings: list[str] = []

    run_summary_path = summary_dir / "run_summary.json"
    run_summary = read_json(run_summary_path) if run_summary_path.exists() else {}
    if not run_summary:
        errors.append("missing run_summary.json")

    data_materialization = read_json(summary_dir / "data-materialization-summary.json") if (summary_dir / "data-materialization-summary.json").exists() else {}
    target_db = read_json(summary_dir / "target-db-build-summary.json") if (summary_dir / "target-db-build-summary.json").exists() else {}
    candidate_summary = read_json(summary_dir / "candidate-search-summary.json") if (summary_dir / "candidate-search-summary.json").exists() else {}
    candidate_hits = read_tsv(summary_dir / "candidate_hits.tsv")
    target_indexes = read_tsv(summary_dir / "target-db-indexes.tsv")
    materialized_targets = read_tsv(summary_dir / "materialized-targets.tsv")

    materialized_by_dataset = {
        row.get("dataset_id", ""): row
        for row in materialized_targets
        if row.get("materialization_status") in {"target_fasta_materialized", "present", "existing_provider_source"}
    }
    target_index_rows = [
        row for row in target_indexes
        if real_target_db_id(row.get("target_db_id", "")) and row.get("build_status") in {"built", "present"}
    ]
    target_index_by_id = {row.get("target_db_id", ""): row for row in target_index_rows}
    target_candidate_rows = [
        row for row in candidate_hits
        if (
            real_target_db_id(row.get("target_db_id", ""))
            and row.get("target_db_id", "") in target_index_by_id
            and row.get("dataset_id", "") == target_index_by_id[row.get("target_db_id", "")].get("dataset_id", "")
            and row.get("dataset_id") not in {"", "provider_search", "mock_provider_summary"}
            and row.get("target_species") not in {"", "reference_database"}
            and not placeholder_candidate(row)
        )
    ]
    placeholder_rows = [
        row for row in candidate_hits
        if placeholder_candidate(row)
    ]
    target_candidate_ids_without_materialized_source = [
        row.get("candidate_id", "")
        for row in target_candidate_rows
        if materialized_targets and row.get("dataset_id", "") not in materialized_by_dataset
    ]

    if args.require_real_target_search:
        if run_summary.get("toolcheck_ok") is False:
            errors.append("toolcheck failed")
        if data_materialization.get("mock_tools") is True or data_materialization.get("dry_run") is True:
            errors.append("data materialization summary is mock/dry-run output")
        if data_materialization.get("ok") is not True:
            errors.append("data materialization did not report ok:true")
        if target_db.get("mock_tools") is True or target_db.get("dry_run") is True:
            errors.append("target DB build summary is mock/dry-run output")
        if target_db.get("ok") is not True:
            errors.append("target DB build did not report ok:true")
        if candidate_summary.get("mock_tools") is True:
            errors.append("candidate search summary is mock output")
        if run_summary.get("candidate_search_ok") is not True:
            errors.append("candidate search did not report ok:true")
        if run_summary.get("real_target_search_ok") is not True or candidate_summary.get("real_target_search_ok") is not True:
            errors.append("real target search was not proven by candidate-search-summary.json and run_summary.json")
        if run_summary.get("heavy_execution_performed") is not True:
            errors.append("run_summary heavy_execution_performed is not true")
        if int(candidate_summary.get("target_commands_completed") or 0) < 1:
            errors.append("candidate-search-summary.json has no completed target search command")
        if not materialized_targets:
            warnings.append("materialized-targets.tsv is missing or empty; acceptable only when target indexes came from existing FASTA/protein/GFF inputs")
        if not target_index_rows:
            errors.append("target-db-indexes.tsv has no built/present target_* indexes")
        if not target_candidate_rows:
            errors.append("candidate_hits.tsv has no rows tied to target_* databases")
        if target_candidate_ids_without_materialized_source:
            errors.append(
                "target candidate rows do not join to materialized target datasets: "
                + ", ".join(target_candidate_ids_without_materialized_source[:10])
            )
        if placeholder_rows:
            errors.append(f"candidate_hits.tsv contains {len(placeholder_rows)} placeholder/reference-only rows")

    result = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary_dir": str(summary_dir),
        "candidate_rows": len(candidate_hits),
        "target_candidate_rows": len(target_candidate_rows),
        "target_index_rows": len(target_index_rows),
        "placeholder_rows": len(placeholder_rows),
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("BioSymphony GeneCluster contract self-check:", "ok" if result["ok"] else "failed")
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
