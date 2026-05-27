#!/usr/bin/env python3
"""Wave 5 worker, rule-based mechanism classifier.

Reads the per-variant metric files emitted by Wave 4 and assigns the variant
to one of the campaign mechanism families:

    active_site | allosteric | stability | compensatory | ambiguous

The rules are documented in references/campaigns/mechanistic-variant-atlas.md
under "Wave 5: mechanism classification". This script implements them.

Usage:
    python3 classify_mechanism.py \\
        --variant T790M \\
        --metrics-dir metrics/T790M/ \\
        --out classification/T790M/

Exit codes:
    0 success
    1 usage / file error
    6 metric file missing or unreadable (campaign should re-run Wave 4)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Thresholds aligned with the campaign spec. Tuned for v1 EGFR data.
THRESHOLDS = {
    "gatekeeper_overlap_clash_angstrom": 0.5,
    "gatekeeper_distance_clash_angstrom": 3.5,
    "drug_contact_loss_count": 3,
    "pocket_shape_delta": 0.10,
    "hbond_loss_count": 5,
    "ambiguity_margin": 0.10,
}


def load_metric(metrics_dir: Path, name: str) -> dict | None:
    p = metrics_dir / f"{name}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def evaluate(metrics: dict[str, dict | None]) -> dict:
    """Apply the campaign's classification rules.

    Returns a dict with all candidate evidence and the chosen mechanism.
    """
    evidence: list[dict] = []

    contact = metrics.get("contact_diff")
    gate = metrics.get("gatekeeper_distance")
    hbond = metrics.get("hbond_diff")
    pocket = metrics.get("pocket_geometry")

    # Active site: gatekeeper steric clash
    if gate and gate.get("max_vdw_overlap_angstrom", 0) > THRESHOLDS["gatekeeper_overlap_clash_angstrom"]:
        evidence.append(
            {
                "family": "active_site",
                "confidence": 0.92,
                "reason": (
                    f"gatekeeper VDW overlap "
                    f"{gate['max_vdw_overlap_angstrom']:.2f} Å exceeds "
                    f"threshold {THRESHOLDS['gatekeeper_overlap_clash_angstrom']:.2f} Å"
                ),
                "source_metric": "gatekeeper_distance",
            }
        )
    elif gate and gate.get("min_distance_angstrom", 99.0) < THRESHOLDS["gatekeeper_distance_clash_angstrom"]:
        evidence.append(
            {
                "family": "active_site",
                "confidence": 0.78,
                "reason": (
                    f"gatekeeper-ligand min distance "
                    f"{gate['min_distance_angstrom']:.2f} Å is close enough to suggest contact"
                ),
                "source_metric": "gatekeeper_distance",
            }
        )

    # Active site: drug contact loss
    if (
        contact
        and contact.get("focus", {}).get("kind") == "ligand"
        and contact.get("diff", {}).get("lost_count", 0) >= THRESHOLDS["drug_contact_loss_count"]
    ):
        evidence.append(
            {
                "family": "active_site",
                "confidence": 0.85,
                "reason": (
                    f"{contact['diff']['lost_count']} drug-contacting protein residues lost "
                    "between WT and variant complex"
                ),
                "source_metric": "contact_diff",
            }
        )

    # Allosteric: pocket-shape change without direct ligand contact loss
    if pocket and pocket.get("delta", {}).get("pocket_shape_delta", 0) > THRESHOLDS["pocket_shape_delta"]:
        ligand_contact_lost = (
            contact
            and contact.get("focus", {}).get("kind") == "ligand"
            and contact.get("diff", {}).get("lost_count", 0) >= THRESHOLDS["drug_contact_loss_count"]
        )
        if not ligand_contact_lost:
            evidence.append(
                {
                    "family": "allosteric",
                    "confidence": 0.7,
                    "reason": (
                        f"pocket shape delta "
                        f"{pocket['delta']['pocket_shape_delta']:.3f} above threshold "
                        f"with no direct drug-contact residue loss"
                    ),
                    "source_metric": "pocket_geometry",
                }
            )

    # Stability: substantial hbond network loss
    if hbond and hbond.get("lost_count", 0) >= THRESHOLDS["hbond_loss_count"]:
        evidence.append(
            {
                "family": "stability",
                "confidence": 0.6,
                "reason": (
                    f"{hbond['lost_count']} h-bonds lost in focus region between WT and variant"
                ),
                "source_metric": "hbond_diff",
            }
        )

    # Default: compensatory if no evidence at all
    if not evidence:
        return {
            "mechanism": "compensatory",
            "confidence": 0.4,
            "rationale": "no direct structural effect detected by Tier A metrics",
            "evidence": [],
            "ambiguity_margin": None,
        }

    # Resolve top evidence, check for ambiguity
    evidence.sort(key=lambda e: e["confidence"], reverse=True)
    top = evidence[0]
    margin = None
    if len(evidence) >= 2 and evidence[1]["family"] != top["family"]:
        margin = top["confidence"] - evidence[1]["confidence"]
        if margin < THRESHOLDS["ambiguity_margin"]:
            return {
                "mechanism": "ambiguous",
                "confidence": top["confidence"],
                "rationale": (
                    f"top-2 evidence margin {margin:.2f} below threshold "
                    f"({THRESHOLDS['ambiguity_margin']:.2f}); "
                    f"competing families: {top['family']} vs {evidence[1]['family']}"
                ),
                "evidence": evidence,
                "ambiguity_margin": round(margin, 3),
            }
    return {
        "mechanism": top["family"],
        "confidence": top["confidence"],
        "rationale": top["reason"],
        "evidence": evidence,
        "ambiguity_margin": round(margin, 3) if margin is not None else None,
    }


def write_rationale(payload: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Mechanism classification, variant {payload['variant']}")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append("")
    lines.append(f"## Mechanism: **{payload['classification']['mechanism']}**")
    lines.append("")
    lines.append(f"Confidence: {payload['classification']['confidence']:.2f}")
    lines.append("")
    lines.append(f"Rationale: {payload['classification']['rationale']}")
    lines.append("")
    lines.append("## Evidence considered")
    lines.append("")
    if payload["classification"]["evidence"]:
        for e in payload["classification"]["evidence"]:
            lines.append(
                f"- **{e['family']}** ({e['confidence']:.2f}, source: `{e['source_metric']}`): {e['reason']}"
            )
    else:
        lines.append("- (none)")
    lines.append("")
    if payload["classification"]["ambiguity_margin"] is not None:
        lines.append(
            f"Top-2 evidence margin: {payload['classification']['ambiguity_margin']:.3f}"
        )
    lines.append("")
    lines.append("## Metric availability")
    lines.append("")
    for k, v in payload["metric_status"].items():
        lines.append(f"- {k}: {v}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="BioSymphony Wave 5 mechanism classifier.")
    parser.add_argument("--variant", required=True, help="Variant ID.")
    parser.add_argument("--metrics-dir", type=Path, required=True, help="Directory with Wave 4 metric JSON files.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory.")
    args = parser.parse_args()

    if not args.metrics_dir.is_dir():
        print(f"metrics directory not found: {args.metrics_dir}", file=sys.stderr)
        return 1

    metric_names = ["contact_diff", "gatekeeper_distance", "hbond_diff", "pocket_geometry"]
    metrics = {name: load_metric(args.metrics_dir, name) for name in metric_names}
    metric_status = {
        name: ("present" if m else "missing") for name, m in metrics.items()
    }

    classification = evaluate(metrics)

    payload = {
        "schema_version": 1,
        "campaign": "mechanistic-variant-atlas",
        "variant": args.variant,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "thresholds": THRESHOLDS,
        "metric_status": metric_status,
        "classification": classification,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / "classification.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_rationale(payload, args.out / "rationale.md")

    print(
        f"variant={args.variant} mechanism={classification['mechanism']} "
        f"confidence={classification['confidence']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
