#!/usr/bin/env python3
"""Wave 10 worker, claim auditor.

For one literature claim, evaluates each testable_prediction against the
campaign's own Wave 4 metrics and Wave 5 classification, then emits a
verdict in {supported, qualified, not_supported, untestable}.

Usage:
    python3 claim_audit.py \\
        --claim T790M_gatekeeper_clash \\
        --claims examples/egfr-resistance-v1/claims.yaml \\
        --metrics-dir metrics/T790M/ \\
        --classification-dir classification/T790M/ \\
        --out audit/T790M_gatekeeper_clash/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.load_yaml import load_yaml  # noqa: E402

# Map metric names referenced in claims.yaml to (metric_file, json_path).
# `json_path` is a dotted path into the metric JSON document.
METRIC_LOOKUP: dict[str, tuple[str, list[str]]] = {
    "gatekeeper_vdw_overlap": ("gatekeeper_distance", ["max_vdw_overlap_angstrom"]),
    "gatekeeper_vdw_overlap_osimertinib": (
        "gatekeeper_distance",
        ["max_vdw_overlap_angstrom"],
    ),
    "drug_contact_loss": ("contact_diff", ["diff", "lost_count"]),
    "drug_contact_loss_osimertinib": ("contact_diff", ["diff", "lost_count"]),
    "drug_contact_loss_first_gen": ("contact_diff", ["diff", "lost_count"]),
    "covalent_residue_mutated": ("classification", ["covalent_residue_mutated"]),
    "covalent_bond_distance": ("gatekeeper_distance", ["min_distance_angstrom"]),
    "p_loop_local_rmsd": ("pocket_geometry", ["delta", "mean_pairwise_distance"]),
    "p_loop_length_residues": ("classification", ["p_loop_length_residues"]),
    "pocket_shape_delta": ("pocket_geometry", ["delta", "pocket_shape_delta"]),
    "local_backbone_rmsd_helix_c": (
        "pocket_geometry",
        ["delta", "radius_of_gyration"],
    ),
    "helix_c_orientation_angle": ("classification", ["helix_c_orientation_angle"]),
    "helix_c_orientation_angle_change": (
        "classification",
        ["helix_c_orientation_angle_change"],
    ),
    "direct_tki_contact_residue": (
        "classification",
        ["direct_tki_contact_residue"],
    ),
    "residue_718_to_aniline_min_distance": (
        "gatekeeper_distance",
        ["min_distance_angstrom"],
    ),
    "classifier_label": ("classification", ["classification", "mechanism"]),
}

OPS: dict[str, Any] = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def get_in(d: Any, path: list[str]) -> Any:
    for key in path:
        if d is None:
            return None
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


def find_claim(claims_doc: dict, claim_id: str) -> dict | None:
    for c in claims_doc.get("claims", []):
        if c.get("id") == claim_id:
            return c
    return None


def evaluate_predictions(
    claim: dict,
    metrics: dict[str, dict | None],
    classification: dict | None,
) -> tuple[str, list[dict]]:
    """Evaluate each testable_prediction. Returns (verdict, per-prediction results)."""
    predictions = claim.get("testable_predictions") or []
    if not predictions:
        return "untestable", [
            {
                "metric": None,
                "status": "untestable",
                "reason": "claim has no testable_predictions",
            }
        ]

    results: list[dict] = []
    untestable_count = 0
    pass_count = 0
    fail_count = 0
    notes: list[str] = []

    metric_data: dict[str, Any] = dict(metrics)
    metric_data["classification"] = classification or {}

    for pred in predictions:
        metric = pred.get("metric")
        op_str = pred.get("operator")
        threshold = pred.get("threshold")
        spec_notes = pred.get("notes", "")

        # Untestable: metric not mapped in this campaign
        lookup = METRIC_LOOKUP.get(metric)
        if lookup is None:
            untestable_count += 1
            results.append(
                {
                    "metric": metric,
                    "status": "untestable",
                    "reason": "metric not produced by Tier A v1 campaign",
                    "claim_notes": spec_notes,
                }
            )
            continue

        source_name, path = lookup
        source_doc = metric_data.get(source_name)
        if source_doc is None:
            untestable_count += 1
            results.append(
                {
                    "metric": metric,
                    "status": "untestable",
                    "reason": f"source metric '{source_name}' missing from campaign output",
                    "claim_notes": spec_notes,
                }
            )
            continue

        value = get_in(source_doc, path)
        if value is None:
            untestable_count += 1
            results.append(
                {
                    "metric": metric,
                    "status": "untestable",
                    "reason": f"value at {source_name}:{'.'.join(path)} is null",
                    "claim_notes": spec_notes,
                }
            )
            continue

        if op_str is None or threshold is None:
            # Existence check: just record the value
            results.append(
                {
                    "metric": metric,
                    "status": "informational",
                    "value": value,
                    "claim_notes": spec_notes,
                }
            )
            continue

        op = OPS.get(op_str)
        if op is None:
            untestable_count += 1
            results.append(
                {
                    "metric": metric,
                    "status": "untestable",
                    "reason": f"unknown operator '{op_str}'",
                    "claim_notes": spec_notes,
                }
            )
            continue

        try:
            ok = op(value, threshold)
        except TypeError as e:
            untestable_count += 1
            results.append(
                {
                    "metric": metric,
                    "status": "untestable",
                    "reason": f"comparison failed: {e}",
                    "claim_notes": spec_notes,
                }
            )
            continue

        results.append(
            {
                "metric": metric,
                "status": "pass" if ok else "fail",
                "value": value,
                "operator": op_str,
                "threshold": threshold,
                "claim_notes": spec_notes,
            }
        )
        if ok:
            pass_count += 1
        else:
            fail_count += 1

    # Verdict logic
    if untestable_count == len(predictions):
        verdict = "untestable"
    elif fail_count == 0 and pass_count > 0:
        verdict = "supported"
    elif pass_count > 0 and fail_count == 0 and untestable_count > 0:
        verdict = "qualified"
    elif pass_count > 0 and fail_count > 0:
        verdict = "qualified"
    elif fail_count > 0 and pass_count == 0:
        verdict = "not_supported"
    else:
        verdict = "untestable"

    return verdict, results


def write_audit_md(payload: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Claim audit, {payload['claim']['id']}")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append(f"Variant: `{payload['claim']['variant_ref']}`")
    lines.append(f"Drug context: {', '.join(payload['claim'].get('drug_context', [])) or '(none)'}")
    lines.append(f"Citation: `{payload['claim'].get('citation', '?')}`")
    lines.append(f"Expected verdict (from claims.yaml): `{payload['claim'].get('expected_verdict', 'unset')}`")
    lines.append("")
    lines.append(f"## Verdict: **{payload['verdict']}**")
    lines.append("")
    matched_expected = (
        payload["claim"].get("expected_verdict") == payload["verdict"]
    )
    lines.append(
        f"Matches expected verdict: **{'yes' if matched_expected else 'no'}**"
    )
    lines.append("")
    lines.append("## Claim text")
    lines.append("")
    lines.append("> " + " ".join(payload["claim"]["claim"].split()))
    lines.append("")
    lines.append("## Per-prediction evaluation")
    lines.append("")
    for r in payload["results"]:
        m = r.get("metric")
        s = r.get("status")
        reason = r.get("reason")
        if reason:
            lines.append(f"- `{m}` → **{s}** . {reason}")
        elif "value" in r:
            lines.append(
                f"- `{m}` → **{s}** "
                f"(value={r.get('value')}, op={r.get('operator')}, threshold={r.get('threshold')})"
            )
        else:
            lines.append(f"- `{m}` → **{s}**")
        if r.get("claim_notes"):
            lines.append(f"  - notes: {r['claim_notes']}")
    if payload.get("expected_rationale"):
        lines.append("")
        lines.append("## Author rationale (from claims.yaml)")
        lines.append("")
        lines.append("> " + " ".join(payload["expected_rationale"].split()))
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="BioSymphony Wave 10 claim auditor.")
    parser.add_argument("--claim", required=True, help="Claim ID from claims.yaml.")
    parser.add_argument("--claims", type=Path, required=True, help="Path to claims.yaml.")
    parser.add_argument("--metrics-dir", type=Path, required=True, help="Directory with Wave 4 metric JSONs.")
    parser.add_argument("--classification-dir", type=Path, required=False, help="Directory with Wave 5 classification.")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.claims.is_file():
        print(f"claims file not found: {args.claims}", file=sys.stderr)
        return 1

    claims_doc = load_yaml(args.claims)
    claim = find_claim(claims_doc, args.claim)
    if claim is None:
        print(f"claim not found: {args.claim}", file=sys.stderr)
        return 1

    metrics: dict[str, dict | None] = {}
    if args.metrics_dir and args.metrics_dir.is_dir():
        for name in ["contact_diff", "gatekeeper_distance", "hbond_diff", "pocket_geometry"]:
            p = args.metrics_dir / f"{name}.json"
            metrics[name] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None

    classification: dict | None = None
    if args.classification_dir and args.classification_dir.is_dir():
        cp = args.classification_dir / "classification.json"
        if cp.is_file():
            classification = json.loads(cp.read_text(encoding="utf-8"))

    verdict, results = evaluate_predictions(claim, metrics, classification)

    payload = {
        "schema_version": 1,
        "campaign": "mechanistic-variant-atlas",
        "claim": claim,
        "verdict": verdict,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "expected_rationale": claim.get("rationale", ""),
        "results": results,
        "diagnostics": {
            "metrics_present": {k: v is not None for k, v in metrics.items()},
            "classification_present": classification is not None,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "audit.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_audit_md(payload, args.out / "audit.md")

    print(
        f"claim={args.claim} verdict={verdict} "
        f"expected={claim.get('expected_verdict', '?')} "
        f"match={'yes' if claim.get('expected_verdict') == verdict else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
