#!/usr/bin/env python3
"""Score neighboring genes as claim-safe pathway hypotheses."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HYPOTHESIS_HEADERS = [
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
]

PROFILE_PATTERNS: list[tuple[str, str, float]] = [
    ("methyltransferase", r"\b(omt|o-methyl|methyltransferase|methyltransf|sabath)\b", 0.86),
    ("cytochrome_p450", r"\b(cyp|p450|monooxygenase|hydroxylase)\b", 0.76),
    ("reductase", r"\b(reductase|dehydrogenase|mdr|adh_n|nad)\b", 0.72),
    ("glycosidase", r"\b(glycosidase|glucosidase|gh1|beta-glucosidase)\b", 0.68),
    ("oxidase", r"\b(oxidase|bbe|fad|oxygenase)\b", 0.64),
    ("transporter", r"\b(mate|abc transporter|transporter|npf|mfs)\b", 0.50),
    ("regulator", r"\b(transcription factor|bhlh|myb|wrky|ap2|erf|jasmonate)\b", 0.42),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_tsv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def output_dir_for_manifest(manifest: dict[str, Any], manifest_path: Path, out: Path | None) -> Path:
    if out is not None:
        return out
    summary = str(manifest.get("summary_outdir", "")).strip()
    if summary and summary != "summary":
        return resolve_manifest_path(summary, manifest_path)
    heavy = str(manifest.get("heavy_workdir", "")).strip()
    if heavy:
        return Path(heavy) / "summary"
    return manifest_path.parent / "summary"


def safe_distance(value: str) -> int:
    try:
        return abs(int(value))
    except (TypeError, ValueError):
        return 10**9


def classify_relevance(text: str) -> tuple[str, float]:
    lowered = text.lower()
    for label, pattern, base_score in PROFILE_PATTERNS:
        if re.search(pattern, lowered):
            return label, base_score
    if lowered.strip():
        return "scaffold_or_unknown_protein", 0.22
    return "unknown", 0.10


def build_domain_map(out_dir: Path) -> dict[str, list[str]]:
    path = out_dir / "domain_labels.tsv"
    if not path.exists():
        return {}
    domain_map: dict[str, list[str]] = {}
    for row in read_tsv(path):
        feature_id = row.get("feature_id", "")
        label = row.get("domain_label", "")
        if feature_id and label:
            domain_map.setdefault(feature_id, []).append(label)
    return domain_map


def run(launch_manifest: Path, out: Path | None = None, *, dry_run: bool = False, mock_tools: bool = False) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    out_dir.mkdir(parents=True, exist_ok=True)

    annotations_path = out_dir / "neighbor_annotations.tsv"
    neighborhoods_path = out_dir / "cluster_neighborhoods.tsv"
    annotations = read_tsv(annotations_path) if annotations_path.exists() else []
    neighborhoods = {row.get("neighborhood_id", ""): row for row in read_tsv(neighborhoods_path)} if neighborhoods_path.exists() else {}
    domains = build_domain_map(out_dir)

    rows: list[dict[str, Any]] = []
    for index, annotation in enumerate(annotations, start=1):
        if annotation.get("is_candidate") == "true":
            continue
        feature_id = annotation.get("feature_id", "")
        domain_text = ";".join(domains.get(feature_id, []))
        evidence_text = " ".join([annotation.get("product", ""), domain_text])
        family, base_score = classify_relevance(evidence_text)
        if family == "unknown":
            continue
        distance = safe_distance(annotation.get("distance_bp", ""))
        distance_bonus = 0.10 if distance <= 50_000 else (0.05 if distance <= 200_000 else 0.0)
        score = min(1.0, base_score + distance_bonus)
        neighborhood = neighborhoods.get(annotation.get("neighborhood_id", ""), {})
        anchor_gene_id = neighborhood.get("candidate_id", annotation.get("candidate_id", ""))
        rows.append(
            {
                "hypothesis_id": f"NHYP_{index:05d}",
                "neighborhood_id": annotation.get("neighborhood_id", ""),
                "candidate_id": annotation.get("candidate_id", ""),
                "anchor_gene_id": anchor_gene_id,
                "neighbor_feature_id": feature_id,
                "distance_bp": annotation.get("distance_bp", ""),
                "domain_relevance": family,
                "enzyme_family_label": family,
                "hypothesis_score": f"{score:.2f}",
                "claim_safe_label": f"{family}_candidate_neighbor",
                "claim_gate": "neighborhood_context_not_product_validated",
                "evidence_basis": evidence_text or "neighboring feature without domain annotation",
                "review_status": "needs-human-review",
            }
        )

    blockers = []
    if not annotations_path.exists():
        blockers.append("neighbor_annotations.tsv was not found; run neighborhood extraction first")
    write_tsv(out_dir / "neighborhood_hypotheses.tsv", HYPOTHESIS_HEADERS, rows)
    write_json(
        out_dir / "neighborhood-score-summary.json",
        {
            "schema_version": 1,
            "checked_at": utc_now(),
            "launch_manifest": str(manifest_path),
            "neighbor_annotation_count": len(annotations),
            "hypothesis_count": len(rows),
            "dry_run": dry_run,
            "mock_tools": mock_tools,
            "raw_sequence_emitted": False,
            "blockers": blockers,
            "ok": not blockers,
        },
    )
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Score GeneCluster neighboring-gene hypotheses.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    args = parser.parse_args()
    run(args.launch_manifest, args.out, dry_run=args.dry_run, mock_tools=args.mock_tools)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
