#!/usr/bin/env python3
"""Validate GeneCluster provider stage contracts and progress ledgers.

The point of this check is to catch long-run fragility before it becomes a
scientific failure: every provider stage needs an expected output, timeout,
checkpoint/resume story, and a fail-closed policy. A launch can be valid while
still being too opaque for a multi-hour run; this contract makes that visible.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_ROOT_KEYS = {
    "schema_version",
    "run_id",
    "provider_class",
    "run_scope",
    "progress_ledger",
    "heartbeat_interval_minutes",
    "stale_after_minutes",
    "stages",
    "watcher",
    "acceptance",
}

REQUIRED_STAGE_KEYS = {
    "stage_id",
    "run_flag",
    "entrypoint",
    "expected_outputs",
    "done_marker",
    "timeout_minutes",
    "resume_strategy",
    "failure_policy",
}

TERMINAL_STATUSES = {
    "completed",
    "completed_with_blockers",
    "skipped_runtime_budget_exhausted",
    "skipped_by_policy",
    "failed",
    "partial",
}

PROGRESS_STATUSES = TERMINAL_STATUSES | {"started", "heartbeat"}

TOOL_LOCATION_KEYS = {"executable", "absolute_path", "path_discovery"}
TOOL_PROOF_KEYS = {"proof_command", "version_command"}

KNOWN_STAGE_TOOL_PATTERNS = {
    "TransDecoder.LongOrfs": "transdecoder_longorfs",
    "TransDecoder.Predict": "transdecoder_predict",
    "hisat2": "hisat2",
    "stringtie": "stringtie",
    "samtools": "samtools",
    "gffread": "gffread",
    "minimap2": "minimap2",
    "blastp": "blastp",
    "makeblastdb": "makeblastdb",
    "hmmscan": "hmmscan",
    "hmmpress": "hmmpress",
    "miniprot": "miniprot",
    "fasterq-dump": "fasterq_dump",
    "prefetch": "prefetch",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def tool_names(tools: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for tool in tools:
        for key in ["name", "tool", "executable"]:
            value = tool.get(key)
            if value:
                names.add(str(value))
    return names


def validate_required_tools(
    tools: Any,
    *,
    label: str,
    errors: list[str],
    warnings: list[str],
) -> list[dict[str, Any]]:
    if tools is None:
        return []
    if not isinstance(tools, list):
        errors.append(f"{label}: required_tools must be a list")
        return []

    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, tool in enumerate(tools, start=1):
        if not isinstance(tool, dict):
            errors.append(f"{label}: required_tools item {idx} must be an object")
            continue
        name = str(tool.get("name") or tool.get("tool") or "")
        if not name:
            errors.append(f"{label}: required_tools item {idx} missing name")
        elif name in seen:
            errors.append(f"{label}: duplicate required tool: {name}")
        seen.add(name)

        if not any(tool.get(key) for key in TOOL_LOCATION_KEYS):
            errors.append(f"{label}: required tool {name or idx} needs executable, absolute_path, or path_discovery")
        if not any(tool.get(key) for key in TOOL_PROOF_KEYS):
            errors.append(f"{label}: required tool {name or idx} needs proof_command or version_command")
        if tool.get("fail_closed") is not True:
            errors.append(f"{label}: required tool {name or idx} must set fail_closed=true")
        if tool.get("path_discovery") and not tool.get("proof_command"):
            errors.append(f"{label}: required tool {name or idx} with path_discovery must include proof_command")

        fallback = str(tool.get("fallback_policy", "")).lower()
        if "warn" in fallback and tool.get("fail_closed") is not True:
            warnings.append(f"{label}: required tool {name or idx} has warning-only fallback")
        validated.append(tool)
    return validated


def validate_stage_contract(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "path": str(path)}

    missing = REQUIRED_ROOT_KEYS - set(data)
    if missing:
        errors.append("stage contract missing root keys: " + ", ".join(sorted(missing)))
    if data.get("schema_version") != 1:
        errors.append("stage contract schema_version must be 1")

    try:
        heartbeat = float(data.get("heartbeat_interval_minutes", 0))
    except (TypeError, ValueError):
        heartbeat = 0
        errors.append("heartbeat_interval_minutes must be numeric")
    try:
        stale = float(data.get("stale_after_minutes", 0))
    except (TypeError, ValueError):
        stale = 0
        errors.append("stale_after_minutes must be numeric")
    if heartbeat <= 0 or heartbeat > 15:
        errors.append("heartbeat_interval_minutes must be in (0, 15]")
    if stale < max(heartbeat * 2, 10):
        errors.append("stale_after_minutes must be at least two heartbeats and >= 10")

    root_required_tools = validate_required_tools(
        data.get("required_tools"),
        label="root",
        errors=errors,
        warnings=warnings,
    )
    root_tool_names = tool_names(root_required_tools)

    watcher = data.get("watcher", {})
    if not isinstance(watcher, dict):
        errors.append("watcher must be an object")
    else:
        if watcher.get("required_for_runtime_hours_over", 0) is None:
            errors.append("watcher.required_for_runtime_hours_over is required")
        if watcher.get("poll_interval_minutes", 999) > 15:
            errors.append("watcher.poll_interval_minutes must be <= 15")
        if "capacity" not in " ".join(watcher.get("false_assumptions_to_avoid", [])):
            warnings.append("watcher should explicitly avoid assuming stale progress means provider capacity")

    stages = data.get("stages", [])
    if not isinstance(stages, list) or not stages:
        errors.append("stage contract stages must be a non-empty list")
    else:
        seen: set[str] = set()
        for idx, stage in enumerate(stages, start=1):
            if not isinstance(stage, dict):
                errors.append(f"stage {idx} must be an object")
                continue
            missing_stage = REQUIRED_STAGE_KEYS - set(stage)
            if missing_stage:
                errors.append(f"stage {idx} missing keys: {', '.join(sorted(missing_stage))}")
            stage_id = str(stage.get("stage_id", ""))
            if not stage_id:
                errors.append(f"stage {idx} missing stage_id")
            if stage_id in seen:
                errors.append(f"duplicate stage_id: {stage_id}")
            seen.add(stage_id)
            outputs = stage.get("expected_outputs", [])
            if not isinstance(outputs, list) or not outputs:
                errors.append(f"{stage_id or idx}: expected_outputs must be a non-empty list")
            if not stage.get("done_marker"):
                errors.append(f"{stage_id or idx}: done_marker is required")
            try:
                timeout = float(stage.get("timeout_minutes", 0))
            except (TypeError, ValueError):
                timeout = 0
                errors.append(f"{stage_id or idx}: timeout_minutes must be numeric")
            if timeout <= 0:
                errors.append(f"{stage_id or idx}: timeout_minutes must be positive")
            if "idempotent" not in str(stage.get("resume_strategy", "")).lower():
                warnings.append(f"{stage_id or idx}: resume_strategy should document idempotent rerun behavior")
            failure_policy = str(stage.get("failure_policy", "")).lower()
            if "fail" not in failure_policy or "closed" not in failure_policy:
                errors.append(f"{stage_id or idx}: failure_policy must be fail-closed")
            stage_required_tools = validate_required_tools(
                stage.get("required_tools"),
                label=stage_id or f"stage {idx}",
                errors=errors,
                warnings=warnings,
            )
            available_tool_names = root_tool_names | tool_names(stage_required_tools)
            stage_text = json.dumps(stage, sort_keys=True)
            for pattern, canonical_name in KNOWN_STAGE_TOOL_PATTERNS.items():
                if pattern not in stage_text:
                    continue
                if pattern not in available_tool_names and canonical_name not in available_tool_names:
                    message = (
                        f"{stage_id or idx}: stage mentions {pattern} but has no fail-closed "
                        "required_tools proof for that executable"
                    )
                    if pattern.startswith("TransDecoder"):
                        errors.append(message)
                    else:
                        warnings.append(message)

    acceptance = data.get("acceptance", {})
    if not isinstance(acceptance, dict):
        errors.append("acceptance must be an object")
    else:
        if acceptance.get("partial_verdict_allowed") is not True:
            warnings.append("partial_verdict_allowed should be true for timeboxed biological runs")
        if not acceptance.get("final_success_requires"):
            errors.append("acceptance.final_success_requires must not be empty")
        if not acceptance.get("partial_verdict_requires"):
            errors.append("acceptance.partial_verdict_requires must not be empty")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path": str(path),
        "stage_count": len(stages) if isinstance(stages, list) else 0,
    }


def candidate_output_paths(expected_output: str, artifact_root: Path) -> list[Path]:
    output_path = Path(expected_output)
    if output_path.is_absolute():
        return [output_path]
    return [
        artifact_root / output_path,
        artifact_root / "summary" / output_path,
        artifact_root / "outputs" / output_path,
    ]


def validate_expected_outputs(stage_contract: Path, artifact_root: Path) -> dict[str, Any]:
    """Validate that contract-declared primary outputs exist and are non-empty.

    This is intentionally separate from contract-shape validation so it can be
    run at stage closeout or after local summary pullback. It catches the
    common failure mode where a pipeline writes a done marker but did not
    actually materialize the deliverable that downstream workers depend on.
    """

    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = read_json(stage_contract)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "checked": [], "missing": []}

    checked: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    stages = data.get("stages", [])
    if not isinstance(stages, list):
        return {"ok": False, "errors": ["stage contract stages must be a list"], "warnings": [], "checked": [], "missing": []}

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        stage_id = str(stage.get("stage_id", ""))
        outputs = stage.get("expected_outputs", [])
        if not isinstance(outputs, list):
            continue
        for expected in outputs:
            expected_str = str(expected)
            candidates = candidate_output_paths(expected_str, artifact_root)
            found = next((path for path in candidates if path.exists()), None)
            if found is None:
                missing.append({"stage_id": stage_id, "expected_output": expected_str})
                errors.append(f"{stage_id}: expected output missing: {expected_str}")
                continue
            if found.is_file() and found.stat().st_size <= 0:
                missing.append({"stage_id": stage_id, "expected_output": expected_str, "path": str(found)})
                errors.append(f"{stage_id}: expected output is empty: {found}")
                continue
            checked.append({"stage_id": stage_id, "expected_output": expected_str, "path": str(found)})

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked": checked,
        "missing": missing,
        "artifact_root": str(artifact_root),
        "stage_contract": str(stage_contract),
    }


def read_progress(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                rows.append({"_parse_error": f"line {line_no}: {exc}"})
            else:
                rows.append(row)
    return rows


def validate_progress_ledger(
    progress_path: Path,
    *,
    stage_contract: Path | None = None,
    require_terminal: bool = False,
    max_stale_minutes: float | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not progress_path.exists():
        return {"ok": False, "errors": [f"progress ledger missing: {progress_path}"], "warnings": [], "path": str(progress_path)}

    rows = read_progress(progress_path)
    if not rows:
        errors.append("progress ledger is empty")

    contract_stage_ids: set[str] = set()
    if stage_contract is not None:
        contract = read_json(stage_contract)
        contract_stage_ids = {str(stage.get("stage_id", "")) for stage in contract.get("stages", []) if isinstance(stage, dict)}

    latest_by_stage: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows, start=1):
        if "_parse_error" in row:
            errors.append(str(row["_parse_error"]))
            continue
        stage_id = str(row.get("stage_id", ""))
        status = str(row.get("status", ""))
        if not stage_id:
            errors.append(f"progress row {idx} missing stage_id")
        if status not in PROGRESS_STATUSES:
            errors.append(f"progress row {idx} has unknown status: {status}")
        if parse_timestamp(str(row.get("timestamp", ""))) is None:
            errors.append(f"progress row {idx} has invalid timestamp")
        if stage_id:
            latest_by_stage[stage_id] = row

    if contract_stage_ids:
        unknown = sorted(set(latest_by_stage) - contract_stage_ids)
        if unknown:
            errors.append("progress ledger contains unknown stages: " + ", ".join(unknown))
        missing = sorted(contract_stage_ids - set(latest_by_stage))
        if require_terminal and missing:
            errors.append("progress ledger missing contract stages: " + ", ".join(missing))

    if require_terminal:
        nonterminal = sorted(
            stage_id
            for stage_id, row in latest_by_stage.items()
            if str(row.get("status", "")) not in TERMINAL_STATUSES
        )
        if nonterminal:
            errors.append("progress ledger has non-terminal stages: " + ", ".join(nonterminal))

    if max_stale_minutes is not None and latest_by_stage:
        latest_times = [parse_timestamp(str(row.get("timestamp", ""))) for row in latest_by_stage.values()]
        latest_times = [ts for ts in latest_times if ts is not None]
        if latest_times:
            latest = max(latest_times)
            if latest.tzinfo is None:
                latest = latest.replace(tzinfo=timezone.utc)
            age_minutes = (datetime.now(timezone.utc) - latest).total_seconds() / 60.0
            if age_minutes > max_stale_minutes:
                errors.append(f"progress ledger is stale: {age_minutes:.1f} minutes since last update")
        else:
            warnings.append("progress ledger has no parseable timestamps for staleness check")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path": str(progress_path),
        "rows": len(rows),
        "stages_seen": sorted(latest_by_stage),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GeneCluster stage contract/progress files.")
    parser.add_argument("--stage-contract", type=Path, help="stage-contract.json to validate.")
    parser.add_argument("--progress-jsonl", type=Path, help="stage-progress.jsonl to validate.")
    parser.add_argument("--artifact-root", type=Path, help="Root containing pulled/provider summary artifacts.")
    parser.add_argument("--check-expected-outputs", action="store_true", help="Require every stage expected_output to exist under --artifact-root.")
    parser.add_argument("--require-terminal", action="store_true", help="Require every seen/contract stage to have a terminal status.")
    parser.add_argument("--max-stale-minutes", type=float, help="Fail if the latest progress row is older than this many minutes.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results: dict[str, Any] = {}
    errors: list[str] = []
    warnings: list[str] = []
    if args.stage_contract:
        contract_result = validate_stage_contract(args.stage_contract)
        results["stage_contract"] = contract_result
        errors.extend(f"stage_contract: {error}" for error in contract_result["errors"])
        warnings.extend(f"stage_contract: {warning}" for warning in contract_result["warnings"])
    if args.check_expected_outputs:
        if not args.stage_contract:
            errors.append("--check-expected-outputs requires --stage-contract")
        if not args.artifact_root:
            errors.append("--check-expected-outputs requires --artifact-root")
        if args.stage_contract and args.artifact_root:
            outputs_result = validate_expected_outputs(args.stage_contract, args.artifact_root)
            results["expected_outputs"] = outputs_result
            errors.extend(f"expected_outputs: {error}" for error in outputs_result["errors"])
            warnings.extend(f"expected_outputs: {warning}" for warning in outputs_result["warnings"])
    if args.progress_jsonl:
        progress_result = validate_progress_ledger(
            args.progress_jsonl,
            stage_contract=args.stage_contract,
            require_terminal=args.require_terminal,
            max_stale_minutes=args.max_stale_minutes,
        )
        results["progress"] = progress_result
        errors.extend(f"progress: {error}" for error in progress_result["errors"])
        warnings.extend(f"progress: {warning}" for warning in progress_result["warnings"])
    if not args.stage_contract and not args.progress_jsonl:
        errors.append("supply --stage-contract and/or --progress-jsonl")

    result = {"ok": not errors, "errors": errors, "warnings": warnings, "details": results}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("GeneCluster stage contract:", "ok" if result["ok"] else "failed")
        for error in errors:
            print(f"ERROR: {error}")
        for warning in warnings:
            print(f"WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
