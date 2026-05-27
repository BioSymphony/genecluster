#!/usr/bin/env python3
"""Extract summary-only GeneCluster neighborhoods from anchored candidates."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NEIGHBORHOOD_HEADERS = [
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
]

ANNOTATION_HEADERS = [
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
]

DOMAIN_HEADERS = [
    "neighborhood_id",
    "candidate_id",
    "feature_id",
    "domain_label",
    "label_source",
    "pathway_step_id",
    "product_claim_level",
]

COORDINATE_FEATURES = {"gene", "mRNA", "transcript", "CDS"}


def cap_product_claim_level(value: str) -> str:
    if value in {"none", "candidate", "validated_elsewhere"}:
        return value
    return "candidate"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


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


def discover_paths(manifest: dict[str, Any], manifest_path: Path, suffixes: tuple[str, ...], names: tuple[str, ...]) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []

    def add(path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved.exists() and resolved.is_file() and resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)

    def walk_values(value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                walk_values(nested, str(key).lower())
        elif isinstance(value, list):
            for nested in value:
                walk_values(nested, key_hint)
        elif isinstance(value, str):
            lower = value.lower()
            if (
                any(lower.endswith(suffix) for suffix in suffixes)
                or any(name in lower for name in names)
                or any(name in key_hint for name in names)
            ):
                add(resolve_manifest_path(value, manifest_path))

    walk_values(manifest)
    roots = [manifest_path.parent]
    heavy = str(manifest.get("heavy_workdir", "")).strip()
    if heavy:
        roots.extend([Path(heavy) / "inputs", Path(heavy) / "work", Path(heavy) / "databases"])
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in root.rglob("*"):
            lower = path.name.lower()
            if path.is_file() and (any(lower.endswith(suffix) for suffix in suffixes) or any(name in lower for name in names)):
                add(path)
    return paths


def parse_gff_attributes(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for item in raw.strip().split(";"):
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        elif " " in item:
            key, value = item.split(" ", 1)
        else:
            key, value = item, ""
        attrs[key.strip()] = value.strip().strip('"')
    return attrs


def parse_gff(path: Path) -> list[dict[str, Any]]:
    features = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 9:
                continue
            contig, _source, feature_type, start, end, _score, strand, _phase, raw_attrs = parts
            if feature_type not in COORDINATE_FEATURES:
                continue
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue
            attrs = parse_gff_attributes(raw_attrs)
            feature_id = attrs.get("ID") or attrs.get("Name") or attrs.get("gene_id") or attrs.get("locus_tag") or ""
            product = attrs.get("product") or attrs.get("Name") or attrs.get("Note") or ""
            features.append(
                {
                    "contig": contig,
                    "feature_type": feature_type,
                    "start": min(start_i, end_i),
                    "end": max(start_i, end_i),
                    "strand": strand,
                    "feature_id": feature_id,
                    "product": product,
                    "source_gff": str(path),
                }
            )
    return features


def load_candidate_info(out_dir: Path) -> dict[str, dict[str, str]]:
    path = out_dir / "candidate_hits.tsv"
    if not path.exists():
        return {}
    return {row.get("candidate_id", ""): row for row in read_tsv(path)}


def load_domain_info(paths: list[Path]) -> dict[str, list[str]]:
    domains: dict[str, list[str]] = {}
    for path in paths:
        try:
            rows = read_tsv(path)
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
        for row in rows:
            feature_id = row.get("candidate_id") or row.get("gene_id") or row.get("transcript_id") or row.get("protein_id") or row.get("feature_id") or ""
            label = row.get("domain_label") or row.get("domain_calls") or row.get("domain") or row.get("annotation") or ""
            if feature_id and label:
                domains.setdefault(feature_id, [])
                for part in re.split(r"[;,|]+", label):
                    clean = part.strip()
                    if clean and clean not in domains[feature_id]:
                        domains[feature_id].append(clean)
    return domains


def distance_bp(feature: dict[str, Any], start: int, end: int) -> int:
    if feature["end"] < start:
        return int(feature["end"]) - start
    if feature["start"] > end:
        return int(feature["start"]) - end
    return 0


def select_neighbors(features: list[dict[str, Any]], contig: str, start: int, end: int, window_bp: int, window_genes: int) -> list[dict[str, Any]]:
    same_contig = sorted([feature for feature in features if feature["contig"] == contig], key=lambda item: (item["start"], item["end"]))
    window_start = max(1, start - window_bp)
    window_end = end + window_bp
    in_window = [feature for feature in same_contig if feature["end"] >= window_start and feature["start"] <= window_end]
    candidate_center = (start + end) / 2
    ranked = sorted(same_contig, key=lambda item: (abs(((item["start"] + item["end"]) / 2) - candidate_center), item["start"]))
    gene_limited = ranked[: max(1, window_genes * 2 + 1)]
    combined = {(item["feature_id"], item["start"], item["end"]): item for item in in_window + gene_limited}
    return sorted(combined.values(), key=lambda item: (item["start"], item["end"]))


def anchor_path_for_out(out_dir: Path) -> Path:
    return out_dir / "candidate_anchors.tsv"


def build_outputs(
    anchors: list[dict[str, str]],
    features: list[dict[str, Any]],
    candidate_info: dict[str, dict[str, str]],
    domain_info: dict[str, list[str]],
    *,
    window_kb: int,
    window_genes: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    neighborhoods: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    domains: list[dict[str, Any]] = []
    window_bp = window_kb * 1000
    anchored = [row for row in anchors if row.get("anchor_status") == "anchored" and row.get("contig") and row.get("start") and row.get("end")]
    for index, anchor in enumerate(anchored, start=1):
        candidate_id = anchor.get("candidate_id", "")
        info = candidate_info.get(candidate_id, {})
        start = int(anchor["start"])
        end = int(anchor["end"])
        neighborhood_id = f"NBR_{index:05d}"
        window_start = max(1, start - window_bp)
        window_end = end + window_bp
        neighbors = select_neighbors(features, anchor["contig"], start, end, window_bp, window_genes)
        claim_gate = "coordinate_supported_neighborhood_summary" if neighbors else "coordinate_only_no_neighbors_found"
        source_claim = anchor.get("product_claim_level") or info.get("product_claim_level", "")
        capped_claim = cap_product_claim_level(source_claim)
        neighborhoods.append(
            {
                "neighborhood_id": neighborhood_id,
                "candidate_id": candidate_id,
                "query_id": anchor.get("query_id", ""),
                "contig": anchor.get("contig", ""),
                "candidate_start": start,
                "candidate_end": end,
                "window_start": window_start,
                "window_end": window_end,
                "window_kb": window_kb,
                "window_genes": window_genes,
                "neighbor_count": len(neighbors),
                "candidate_domain_calls": anchor.get("domain_calls") or info.get("domain_calls", ""),
                "pathway_step_id": anchor.get("pathway_step_id") or info.get("pathway_step_id", ""),
                "product_claim_level": capped_claim,
                "claim_gate": claim_gate,
                "context_claim_gate": "neighborhood_summary_product_claim_capped" if capped_claim != source_claim else "neighborhood_summary_only",
            }
        )
        for rank, feature in enumerate(neighbors, start=1):
            is_candidate = feature.get("feature_id") == anchor.get("matched_feature_id") or (
                feature["start"] == start and feature["end"] == end and feature["contig"] == anchor.get("contig")
            )
            feature_id = feature.get("feature_id", "")
            annotations.append(
                {
                    "neighborhood_id": neighborhood_id,
                    "candidate_id": candidate_id,
                    "neighbor_rank": rank,
                    "feature_id": feature_id,
                    "feature_type": feature.get("feature_type", ""),
                    "contig": feature.get("contig", ""),
                    "start": feature.get("start", ""),
                    "end": feature.get("end", ""),
                    "strand": feature.get("strand", ""),
                    "distance_bp": distance_bp(feature, start, end),
                    "overlaps_window": str(feature["end"] >= window_start and feature["start"] <= window_end).lower(),
                    "is_candidate": str(is_candidate).lower(),
                    "product": feature.get("product", ""),
                    "source_gff": feature.get("source_gff", ""),
                }
            )
            labels = domain_info.get(feature_id, [])
            if is_candidate and not labels and (anchor.get("domain_calls") or info.get("domain_calls")):
                labels = [part.strip() for part in re.split(r"[;,|]+", anchor.get("domain_calls") or info.get("domain_calls", "")) if part.strip()]
            for label in labels:
                domains.append(
                    {
                        "neighborhood_id": neighborhood_id,
                        "candidate_id": candidate_id,
                        "feature_id": feature_id,
                        "domain_label": label,
                        "label_source": "domain_table_or_candidate_hits",
                        "pathway_step_id": anchor.get("pathway_step_id") or info.get("pathway_step_id", ""),
                        "product_claim_level": capped_claim,
                    }
                )
    return neighborhoods, annotations, domains


def render_html(summary: dict[str, Any], neighborhoods: list[dict[str, Any]]) -> str:
    width = 760
    bar_height = 18
    rows = max(1, min(len(neighborhoods), 12))
    height = 80 + rows * 34
    svg_rows = []
    for idx, row in enumerate(neighborhoods[:12], start=0):
        y = 46 + idx * 34
        count = int(row.get("neighbor_count", 0) or 0)
        span = max(60, min(620, count * 28))
        label = html.escape(str(row.get("candidate_id", "")))
        svg_rows.append(f'<text x="20" y="{y + 14}" font-size="12">{label}</text>')
        svg_rows.append(f'<rect x="180" y="{y}" width="{span}" height="{bar_height}" fill="#5b8def" opacity="0.24"/>')
        svg_rows.append(f'<rect x="{180 + span // 2 - 4}" y="{y - 4}" width="8" height="{bar_height + 8}" fill="#2454a6"/>')
        svg_rows.append(f'<text x="{190 + span}" y="{y + 14}" font-size="12">{count} features</text>')
    svg = (
        f'<svg role="img" aria-label="GeneCluster neighborhood summary" width="{width}" height="{height}" '
        'viewBox="0 0 760 {height}" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="760" height="{height}" fill="#ffffff"/>'
        '<text x="20" y="26" font-size="16" font-weight="700">GeneCluster neighborhood summary</text>'
        + "".join(svg_rows)
        + "</svg>"
    ).replace("{height}", str(height))
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        "<title>GeneCluster neighborhood summary</title></head>"
        "<body>"
        f"<p>Anchored candidates: {summary['anchored_candidate_count']}; neighborhoods: {summary['neighborhood_count']}; "
        f"window: {summary['window_kb']} kb / {summary['window_genes']} genes. No raw sequence is included.</p>"
        f"{svg}</body></html>\n"
    )


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    dry_run: bool = False,
    mock_tools: bool = False,
    window_kb: int = 100,
    window_genes: int = 10,
) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    anchors_path = anchor_path_for_out(out_dir)
    anchors = read_tsv(anchors_path) if anchors_path.exists() else []
    gff_paths = discover_paths(manifest, manifest_path, (".gff", ".gff3", ".gtf"), ("gff", "annotation"))
    features: list[dict[str, Any]] = []
    for path in gff_paths:
        features.extend(parse_gff(path))
    domain_paths = discover_paths(manifest, manifest_path, (), ("domain", "interpro", "pfam"))
    neighborhoods, annotations, domains = build_outputs(
        anchors,
        features,
        load_candidate_info(out_dir),
        load_domain_info(domain_paths),
        window_kb=window_kb,
        window_genes=window_genes,
    )
    anchored_count = len([row for row in anchors if row.get("anchor_status") == "anchored"])
    blockers = []
    if not anchors_path.exists():
        blockers.append("candidate_anchors.tsv was not found; run genecluster_anchor_map.py first")
    if anchored_count and not gff_paths:
        blockers.append("no provider-side GFF/GTF resource was found for neighborhood extraction")
    if anchors and anchored_count == 0:
        blockers.append("candidate_anchors.tsv contains no anchored coordinates")
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(manifest_path),
        "out_dir": str(out_dir),
        "candidate_anchors": str(anchors_path) if anchors_path.exists() else "",
        "gff_resources": [str(path) for path in gff_paths],
        "domain_resources": [str(path) for path in domain_paths],
        "anchor_count": len(anchors),
        "anchored_candidate_count": anchored_count,
        "neighborhood_count": len(neighborhoods),
        "neighbor_annotation_count": len(annotations),
        "domain_label_count": len(domains),
        "window_kb": window_kb,
        "window_genes": window_genes,
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "raw_sequence_emitted": False,
        "blockers": blockers,
        "ok": not blockers and bool(neighborhoods),
    }
    write_tsv(out_dir / "cluster_neighborhoods.tsv", NEIGHBORHOOD_HEADERS, neighborhoods)
    write_tsv(out_dir / "neighbor_annotations.tsv", ANNOTATION_HEADERS, annotations)
    write_tsv(out_dir / "domain_labels.tsv", DOMAIN_HEADERS, domains)
    write_json(out_dir / "neighborhood-extract-summary.json", summary)
    write_text(out_dir / "neighborhood-visualization.html", render_html(summary, neighborhoods))
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract GeneCluster neighborhoods from anchored candidate coordinates.")
    parser.add_argument("--launch-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    parser.add_argument("--window-kb", type=int, default=100)
    parser.add_argument("--window-genes", type=int, default=10)
    args = parser.parse_args()
    run(
        args.launch_manifest,
        args.out,
        dry_run=args.dry_run,
        mock_tools=args.mock_tools,
        window_kb=args.window_kb,
        window_genes=args.window_genes,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
