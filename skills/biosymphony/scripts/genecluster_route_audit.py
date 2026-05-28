#!/usr/bin/env python3
"""Audit GeneCluster biological route readiness.

This catches the failure mode where a campaign is technically launchable but a
worker silently uses a weaker biological route than the task deserves, such as
jumping straight to genome `tblastn` when transcript evidence exists.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidate = manifest_path.parent / path
    if candidate.exists():
        return candidate
    return path


def load_route_plan(*, launch_manifest: Path | None, candidate_route_plan: Path | None) -> tuple[Path, dict[str, Any]]:
    if candidate_route_plan is not None:
        return candidate_route_plan, read_json(candidate_route_plan)
    if launch_manifest is None:
        raise ValueError("either --launch-manifest or --candidate-route-plan is required")
    manifest = read_json(launch_manifest)
    route_value = str(manifest.get("candidate_route_plan", ""))
    if not route_value:
        raise ValueError("launch manifest does not reference candidate_route_plan")
    route_path = resolve_manifest_path(route_value, launch_manifest)
    return route_path, read_json(route_path)


def audit_route_plan(plan: dict[str, Any], *, require_transcript_first: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    primary_route = str(plan.get("primary_route", ""))
    readiness = str(plan.get("science_readiness", ""))
    blockers = [str(item) for item in plan.get("strict_scientific_blockers", [])]
    missing_stages = [str(item) for item in plan.get("missing_transcript_first_stages", [])]
    direct_genome_policy = str(plan.get("direct_genome_tblastn_policy", ""))
    transcript_first_required = plan.get("transcript_first_required_for_scientific_full") is True

    if not primary_route:
        errors.append("candidate route plan missing primary_route")
    if transcript_first_required and "transcript_first" not in primary_route:
        errors.append("transcript-first is required but primary_route is not transcript-first")
    if "transcript_first" in primary_route and direct_genome_policy != "rescue_only_not_primary_when_transcript_evidence_exists":
        errors.append("direct genome tblastn must be rescue-only when transcript evidence exists")
    if transcript_first_required and missing_stages and "transcript_first_route_not_implemented_in_current_runner" not in blockers:
        errors.append("missing transcript-first stages must create a strict scientific blocker")
    if readiness == "full_route_ready" and blockers:
        errors.append("science_readiness cannot be full_route_ready while strict scientific blockers are present")

    if require_transcript_first:
        if not transcript_first_required:
            errors.append("--require-transcript-first was set but the route plan does not mark transcript-first as required")
        if missing_stages:
            errors.append("transcript-first scientific readiness is not satisfied; missing stages: " + "; ".join(missing_stages))
        if blockers:
            errors.append("strict scientific blockers remain: " + ", ".join(blockers))
        if readiness != "full_route_ready":
            errors.append(f"science_readiness is {readiness}, not full_route_ready")
    elif blockers:
        warnings.append("strict scientific route blockers present: " + ", ".join(blockers))
        if missing_stages:
            warnings.append("missing transcript-first stages: " + "; ".join(missing_stages))

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "primary_route": primary_route,
        "science_readiness": readiness,
        "strict_scientific_blockers": blockers,
        "missing_transcript_first_stage_count": len(missing_stages),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit GeneCluster biological route readiness.")
    parser.add_argument("--launch-manifest", type=Path, help="launch-manifest.json containing candidate_route_plan.")
    parser.add_argument("--candidate-route-plan", type=Path, help="candidate-route-plan.json.")
    parser.add_argument("--require-transcript-first", action="store_true", help="Fail unless the transcript-first scientific route is fully implemented and unblocked.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result.")
    args = parser.parse_args()

    errors: list[str] = []
    try:
        route_path, plan = load_route_plan(
            launch_manifest=args.launch_manifest,
            candidate_route_plan=args.candidate_route_plan,
        )
        result = audit_route_plan(plan, require_transcript_first=args.require_transcript_first)
        result["candidate_route_plan"] = str(route_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors.append(str(exc))
        result = {
            "ok": False,
            "errors": errors,
            "warnings": [],
            "candidate_route_plan": "",
        }

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("BioSymphony GeneCluster route audit:", "ok" if result["ok"] else "failed")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
