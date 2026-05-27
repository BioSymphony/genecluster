#!/usr/bin/env python3
"""Map GeneCluster candidate hits onto provider-side genome annotations.

This helper is intentionally small and provider-neutral. It reads a launch
manifest, finds the provider-side candidate table and optional GFF/mapping
resources, and writes summary-only coordinate artifacts. It does not read or
emit raw sequence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ANCHOR_HEADERS = [
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
]

MATCH_ATTRIBUTE_KEYS = [
    "ID",
    "Name",
    "Parent",
    "gene_id",
    "transcript_id",
    "protein_id",
    "locus_tag",
    "Dbxref",
    "Derives_from",
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


def candidate_hits_path(manifest: dict[str, Any], manifest_path: Path, out_dir: Path) -> Path | None:
    candidates = [
        out_dir / "candidate_hits.tsv",
        manifest_path.parent / "candidate_hits.tsv",
        manifest_path.parent / "summary" / "candidate_hits.tsv",
    ]
    heavy = str(manifest.get("heavy_workdir", "")).strip()
    if heavy:
        candidates.extend([Path(heavy) / "summary" / "candidate_hits.tsv", Path(heavy) / "work" / "candidate_hits.tsv"])
    for path in candidates:
        if path.exists():
            return path
    return None


def split_attr_value(value: str) -> list[str]:
    tokens = []
    for part in re.split(r"[,;| ]+", value):
        part = part.strip()
        if not part:
            continue
        tokens.append(part)
        if ":" in part:
            tokens.append(part.rsplit(":", 1)[-1])
    return tokens


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


def feature_tokens(attrs: dict[str, str]) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for key in MATCH_ATTRIBUTE_KEYS:
        value = attrs.get(key, "")
        for token in split_attr_value(value):
            tokens.setdefault(token, key)
    return tokens


def parse_gff(path: Path) -> list[dict[str, Any]]:
    features = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 9:
                continue
            contig, source, feature_type, start, end, _score, strand, _phase, raw_attrs = parts
            if feature_type not in COORDINATE_FEATURES:
                continue
            try:
                start_i = int(start)
                end_i = int(end)
            except ValueError:
                continue
            attrs = parse_gff_attributes(raw_attrs)
            tokens = feature_tokens(attrs)
            feature_id = attrs.get("ID") or attrs.get("Name") or attrs.get("gene_id") or attrs.get("locus_tag") or ""
            features.append(
                {
                    "contig": contig,
                    "source": source,
                    "feature_type": feature_type,
                    "start": min(start_i, end_i),
                    "end": max(start_i, end_i),
                    "strand": strand,
                    "attrs": attrs,
                    "tokens": tokens,
                    "feature_id": feature_id,
                    "source_gff": str(path),
                }
            )
    return features


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


def load_mapping_tables(paths: list[Path]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for path in paths:
        try:
            rows = read_tsv(path)
        except (OSError, csv.Error, UnicodeDecodeError):
            continue
        for row in rows:
            values = [value for value in row.values() if value]
            for value in values:
                mapping.setdefault(value, set()).update(values)
    return mapping


def candidate_identifiers(row: dict[str, str], mapping: dict[str, set[str]]) -> list[str]:
    seeds = [
        row.get("gene_or_transcript_id", ""),
        row.get("representative_id", ""),
        row.get("genome_locus", ""),
        row.get("candidate_id", ""),
    ]
    ids: list[str] = []
    for seed in seeds:
        if not seed or seed in {"remote_pending", "remote_coordinate_pending", "transcript_only"}:
            continue
        for token in split_attr_value(seed):
            if token and token not in ids:
                ids.append(token)
            for mapped in sorted(mapping.get(token, set())):
                if mapped and mapped not in ids:
                    ids.append(mapped)
    return ids


def build_feature_index(features: list[dict[str, Any]]) -> dict[str, list[tuple[dict[str, Any], str]]]:
    index: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for feature in features:
        for token, attr in feature["tokens"].items():
            index.setdefault(token, []).append((feature, attr))
    return index


def choose_feature(matches: list[tuple[dict[str, Any], str]]) -> tuple[dict[str, Any], str]:
    priority = {"gene": 0, "mRNA": 1, "transcript": 1, "CDS": 2}
    return sorted(matches, key=lambda item: (priority.get(item[0]["feature_type"], 9), item[0]["start"], item[0]["end"]))[0]


def anchor_rows(
    candidate_rows: list[dict[str, str]],
    features: list[dict[str, Any]],
    mapping: dict[str, set[str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index = build_feature_index(features)
    rows: list[dict[str, Any]] = []
    anchored = 0
    ambiguous = 0
    for candidate in candidate_rows:
        matches: list[tuple[dict[str, Any], str]] = []
        matched_id = ""
        for identifier in candidate_identifiers(candidate, mapping):
            if identifier in index:
                matches = index[identifier]
                matched_id = identifier
                break
        if matches:
            feature, matched_attr = choose_feature(matches)
            anchored += 1
            if len(matches) > 1:
                ambiguous += 1
            capped_claim = cap_product_claim_level(candidate.get("product_claim_level", ""))
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id", ""),
                    "query_id": candidate.get("query_id", ""),
                    "gene_or_transcript_id": candidate.get("gene_or_transcript_id", ""),
                    "dataset_id": candidate.get("dataset_id", ""),
                    "matched_feature_id": feature.get("feature_id", ""),
                    "matched_attribute": matched_attr,
                    "contig": feature["contig"],
                    "start": feature["start"],
                    "end": feature["end"],
                    "strand": feature["strand"],
                    "feature_type": feature["feature_type"],
                    "genome_locus": f"{feature['contig']}:{feature['start']}-{feature['end']}:{feature['strand']}",
                    "anchor_status": "anchored",
                    "anchor_confidence": "medium" if len(matches) == 1 else "low",
                    "source_gff": feature["source_gff"],
                    "pathway_step_id": candidate.get("pathway_step_id", ""),
                    "domain_calls": candidate.get("domain_calls", ""),
                    "evidence_score": candidate.get("evidence_score", ""),
                    "product_claim_level": capped_claim,
                    "context_claim_gate": "coordinate_only_product_claim_capped" if capped_claim != candidate.get("product_claim_level", "") else "coordinate_support_recorded",
                    "match_notes": f"matched {matched_id}; {len(matches)} GFF feature(s)",
                }
            )
            continue
        capped_claim = cap_product_claim_level(candidate.get("product_claim_level", ""))
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id", ""),
                "query_id": candidate.get("query_id", ""),
                "gene_or_transcript_id": candidate.get("gene_or_transcript_id", ""),
                "dataset_id": candidate.get("dataset_id", ""),
                "anchor_status": "unanchored",
                "anchor_confidence": "none",
                "pathway_step_id": candidate.get("pathway_step_id", ""),
                "domain_calls": candidate.get("domain_calls", ""),
                "evidence_score": candidate.get("evidence_score", ""),
                "product_claim_level": capped_claim,
                "context_claim_gate": "unanchored_product_claim_capped" if capped_claim != candidate.get("product_claim_level", "") else "unanchored",
                "match_notes": "no coordinate-bearing GFF feature matched candidate identifiers",
            }
        )
    return rows, {"anchored_count": anchored, "ambiguous_match_count": ambiguous}


def run(launch_manifest: Path, out: Path | None = None, *, dry_run: bool = False, mock_tools: bool = False) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    candidate_path = candidate_hits_path(manifest, manifest_path, out_dir)
    candidate_rows = read_tsv(candidate_path) if candidate_path else []
    gff_paths = discover_paths(manifest, manifest_path, (".gff", ".gff3", ".gtf"), ("gff", "annotation"))
    mapping_paths = discover_paths(manifest, manifest_path, (), ("protein-map", "protein_map", "id-map", "id_map", "mapping"))
    mapping = load_mapping_tables(mapping_paths)
    features: list[dict[str, Any]] = []
    for path in gff_paths:
        features.extend(parse_gff(path))
    rows, counts = anchor_rows(candidate_rows, features, mapping)
    coordinate_count = counts["anchored_count"]
    blockers = []
    if not candidate_path:
        blockers.append("candidate_hits.tsv was not found in provider summary paths")
    if not gff_paths:
        blockers.append("no provider-side GFF/GTF resource was found")
    if candidate_rows and gff_paths and coordinate_count == 0:
        blockers.append("no candidate identifiers matched coordinate-bearing GFF features")
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(manifest_path),
        "out_dir": str(out_dir),
        "candidate_hits": str(candidate_path) if candidate_path else "",
        "candidate_count": len(candidate_rows),
        "gff_resources": [str(path) for path in gff_paths],
        "mapping_resources": [str(path) for path in mapping_paths],
        "coordinate_feature_count": len(features),
        "anchored_count": coordinate_count,
        "unanchored_count": len(rows) - coordinate_count,
        "ambiguous_match_count": counts["ambiguous_match_count"],
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "raw_sequence_emitted": False,
        "blockers": blockers,
        "ok": not blockers and coordinate_count > 0,
    }
    write_tsv(out_dir / "candidate_anchors.tsv", ANCHOR_HEADERS, rows)
    write_json(out_dir / "anchor-map-summary.json", summary)
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Map GeneCluster candidates to provider-side GFF coordinates.")
    parser.add_argument("--launch-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    args = parser.parse_args()
    run(args.launch_manifest, args.out, dry_run=args.dry_run, mock_tools=args.mock_tools)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
