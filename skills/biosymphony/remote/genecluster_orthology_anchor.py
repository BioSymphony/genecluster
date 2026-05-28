#!/usr/bin/env python3
"""Summarize A-to-B orthology links and anchor confidence for GeneCluster."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ORTHOLOGY_HEADERS = [
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
]

ANCHOR_LADDER_HEADERS = [
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
]

RECIPROCAL_HEADERS = [
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


def safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_pathway_claim_limits(manifest: dict[str, Any], manifest_path: Path) -> dict[str, str]:
    path = resolve_manifest_path(str(manifest.get("pathway_steps", "")), manifest_path)
    if not path.exists():
        return {}
    return {row.get("pathway_step_id", ""): row.get("claim_limit", "") for row in read_tsv(path)}


def anchor_by_candidate(out_dir: Path) -> dict[str, dict[str, str]]:
    path = out_dir / "candidate_anchors.tsv"
    if not path.exists():
        return {}
    return {row.get("candidate_id", ""): row for row in read_tsv(path)}


def orthology_status(candidate: dict[str, str]) -> tuple[str, str]:
    reciprocal = candidate.get("reciprocal_best_hit", "")
    duplicate_class = candidate.get("duplicate_class", "")
    hit_type = candidate.get("hit_type", "")
    identity = safe_float(candidate.get("pct_identity", "0"))
    query_cov = safe_float(candidate.get("query_coverage", "0"))
    target_cov = safe_float(candidate.get("target_coverage", "0"))
    if reciprocal == "yes" and identity >= 45 and query_cov >= 0.5 and target_cov >= 0.5:
        return "supported", "0.18"
    if duplicate_class == "broad_family" or hit_type == "domain_hit":
        return "broad_family_limited", "-0.10"
    if identity >= 35 and (query_cov >= 0.4 or target_cov >= 0.4):
        return "candidate", "0.08"
    return "ambiguous", "0.00"


def ladder_from_candidate(candidate: dict[str, str], anchor: dict[str, str] | None) -> dict[str, str]:
    candidate_id = candidate.get("candidate_id", "")
    if anchor and anchor.get("anchor_status") in {"anchored", "mapped", "mock_mapped"}:
        method = "exact_gff_id" if anchor.get("matched_attribute") else "transcript_to_genome"
        confidence = "exact_gff_id" if method == "exact_gff_id" else "transcript_to_genome"
        coordinate_confidence = "high" if method == "exact_gff_id" else "medium"
        claim_gate = "coordinate_context_allowed_product_claim_still_review_gated"
        return {
            "candidate_id": candidate_id,
            "query_id": candidate.get("query_id", ""),
            "target_id": candidate.get("gene_or_transcript_id", ""),
            "source_species": candidate.get("source_species", ""),
            "target_species": candidate.get("target_species", ""),
            "anchor_method": method,
            "anchor_confidence": confidence,
            "coordinate_confidence": coordinate_confidence,
            "genome_locus": anchor.get("genome_locus", ""),
            "contig": anchor.get("contig", ""),
            "start": anchor.get("start", ""),
            "end": anchor.get("end", ""),
            "strand": anchor.get("strand", ""),
            "fallback_order": "exact_gff_id>reciprocal_best_hit>transcript_to_genome>protein_to_genome_miniprot>domain_only>unanchored",
            "evidence_basis": anchor.get("match_notes", ""),
            "claim_gate": claim_gate,
        }
    if candidate.get("reciprocal_best_hit") == "yes":
        method = confidence = "reciprocal_best_hit"
        basis = "reciprocal best hit supports orthology but no coordinate-bearing anchor is present"
    elif candidate.get("hit_type") == "protein_hit":
        method = "protein_to_genome"
        confidence = "protein_to_genome"
        basis = "protein hit should be anchored with miniprot or GFF/protein ID mapping"
    elif candidate.get("hit_type") == "domain_hit" or candidate.get("duplicate_class") == "broad_family":
        method = confidence = "domain_only"
        basis = "broad/domain-only evidence is claim-limited"
    else:
        method = "transcript_to_genome" if candidate.get("hit_type") == "transcript_hit" else "unanchored"
        confidence = method if method != "unanchored" else "unanchored"
        basis = "transcript hit requires genome mapping before cluster claims"
    return {
        "candidate_id": candidate_id,
        "query_id": candidate.get("query_id", ""),
        "target_id": candidate.get("gene_or_transcript_id", ""),
        "source_species": candidate.get("source_species", ""),
        "target_species": candidate.get("target_species", ""),
        "anchor_method": method,
        "anchor_confidence": confidence,
        "coordinate_confidence": "none" if confidence in {"domain_only", "unanchored", "reciprocal_best_hit"} else "low",
        "genome_locus": candidate.get("genome_locus", "not_applicable") or "not_applicable",
        "contig": "not_applicable",
        "start": "not_applicable",
        "end": "not_applicable",
        "strand": "not_applicable",
        "fallback_order": "exact_gff_id>reciprocal_best_hit>transcript_to_genome>protein_to_genome_miniprot>domain_only>unanchored",
        "evidence_basis": basis,
        "claim_gate": "cluster_claim_forbidden_until_coordinates" if confidence in {"domain_only", "unanchored", "reciprocal_best_hit"} else "coordinate_review_required",
    }


def run(launch_manifest: Path, out: Path | None = None, *, dry_run: bool = False, mock_tools: bool = False) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = out_dir / "candidate_hits.tsv"
    candidates = read_tsv(candidate_path) if candidate_path.exists() else []
    anchors = anchor_by_candidate(out_dir)
    claim_limits = load_pathway_claim_limits(manifest, manifest_path)

    orthology_rows: list[dict[str, Any]] = []
    reciprocal_rows: list[dict[str, Any]] = []
    ladder_rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates, start=1):
        status, delta = orthology_status(candidate)
        rank = candidate.get("reciprocal_rank") or ("1" if candidate.get("reciprocal_best_hit") == "yes" else "not_assessed")
        reciprocal_best = candidate.get("reciprocal_best_hit") or "not_assessed"
        if reciprocal_best == "reciprocal_pending":
            reciprocal_best = "remote_pending"
        orthology_rows.append(
            {
                "orthology_link_id": f"ORTHO_{index:05d}",
                "candidate_id": candidate.get("candidate_id", ""),
                "source_species": candidate.get("source_species", ""),
                "target_species": candidate.get("target_species", ""),
                "query_id": candidate.get("query_id", ""),
                "target_id": candidate.get("gene_or_transcript_id", ""),
                "search_direction": candidate.get("search_direction", "canonical_A_to_target_B"),
                "target_db_id": candidate.get("target_db_id", ""),
                "pct_identity": candidate.get("pct_identity", ""),
                "query_coverage": candidate.get("query_coverage", ""),
                "target_coverage": candidate.get("target_coverage", ""),
                "evalue": candidate.get("evalue", ""),
                "bitscore": candidate.get("bitscore", ""),
                "reciprocal_rank": rank,
                "reciprocal_best_hit": reciprocal_best,
                "orthology_status": status,
                "evidence_score_delta": delta,
                "claim_limit": claim_limits.get(candidate.get("pathway_step_id", ""), "review_required"),
            }
        )
        reciprocal_rows.append(
            {
                "reciprocal_hit_id": f"RBH_{index:05d}",
                "candidate_id": candidate.get("candidate_id", ""),
                "query_id": candidate.get("query_id", ""),
                "forward_target_id": candidate.get("gene_or_transcript_id", ""),
                "reverse_query_id": candidate.get("query_id", "") if reciprocal_best == "yes" else "not_assessed",
                "reciprocal_rank": rank,
                "reciprocal_best_hit": reciprocal_best,
                "forward_bitscore": candidate.get("bitscore", ""),
                "reverse_bitscore": candidate.get("bitscore", "") if reciprocal_best == "yes" else "not_assessed",
                "status": "supported" if reciprocal_best == "yes" else ("mock" if mock_tools else "not_assessed"),
            }
        )
        ladder_rows.append(ladder_from_candidate(candidate, anchors.get(candidate.get("candidate_id", ""))))

    blockers = [] if candidate_path.exists() else ["candidate_hits.tsv was not found"]
    write_tsv(out_dir / "orthology_links.tsv", ORTHOLOGY_HEADERS, orthology_rows)
    write_tsv(out_dir / "anchor_ladder.tsv", ANCHOR_LADDER_HEADERS, ladder_rows)
    write_tsv(out_dir / "reciprocal_hits.tsv", RECIPROCAL_HEADERS, reciprocal_rows)
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(manifest_path),
        "candidate_count": len(candidates),
        "orthology_link_count": len(orthology_rows),
        "anchor_ladder_count": len(ladder_rows),
        "reciprocal_hit_count": len(reciprocal_rows),
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "raw_sequence_emitted": False,
        "blockers": blockers,
        "ok": not blockers and bool(candidates),
    }
    write_json(out_dir / "orthology-anchor-summary.json", summary)
    write_json(
        out_dir / "reciprocal-search-summary.json",
        {
            "schema_version": 1,
            "checked_at": utc_now(),
            "reciprocal_hit_count": len(reciprocal_rows),
            "raw_outputs_remote_only": str(Path(str(manifest.get("heavy_workdir", ""))) / "work" / "reciprocal-search"),
            "ok": not blockers and bool(candidates),
        },
    )
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize GeneCluster orthology and anchor ladder evidence.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    args = parser.parse_args()
    run(args.launch_manifest, args.out, dry_run=args.dry_run, mock_tools=args.mock_tools)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
