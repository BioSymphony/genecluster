#!/usr/bin/env python3
"""Route-scout GeneCluster campaigns before dispatch.

This scout is intentionally local-light. It inspects compact metadata and small
FASTA/GFF fixtures, chooses the highest-confidence route available, and writes
the route card artifacts that downstream Symphony issues can treat as their
starting ledger.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Any


ROUTES = [
    "annotation_direct",
    "annotation_direct_then_context",
    "transcript_first",
    "genome_context",
    "transcriptome_only",
    "tblastn_rescue",
    "coexpression",
    "synteny",
    "next_experiment_design",
]

ANNOTATION_LEDGER_COLUMNS = [
    "source_id",
    "organism",
    "proteome_fasta",
    "gff",
    "genome_fasta",
    "transcriptome",
    "transcriptome_species",
    "proteome_count",
    "gff_protein_count",
    "protein_gff_join_count",
    "controls_ok",
    "recommended_route",
    "claim_ceiling",
    "blockers",
]

CONTROL_PATTERNS = {
    "ACT2": re.compile(r"(^|[^A-Z0-9])(?:ACT2|ACTIN(?:[-_ ]?2)?|AT3G18780)([^A-Z0-9]|$)", re.IGNORECASE),
    "GAPDH": re.compile(r"(^|[^A-Z0-9])(?:GAPDH|GAPC|GLYCERALDEHYDE[-_ ]?3[-_ ]?PHOSPHATE)([^A-Z0-9]|$)", re.IGNORECASE),
    "random_shuffle": re.compile(r"(random|shuffle|shuffled|decoy|negative)", re.IGNORECASE),
}


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "present", "available"}


def path_exists(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "none", "missing", "false"}:
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, flags=re.IGNORECASE):
        return True
    return Path(text).exists()


def read_fasta_records(path: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current_header: str | None = None
    chunks: list[str] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_header is not None:
                    records.append({"header": current_header, "id": current_header.split()[0], "sequence": "".join(chunks)})
                current_header = line[1:].strip()
                chunks = []
            else:
                chunks.append(line)
    if current_header is not None:
        records.append({"header": current_header, "id": current_header.split()[0], "sequence": "".join(chunks)})
    return records


def read_fasta_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {record["id"] for record in read_fasta_records(path)}


def parse_gff_attributes(attrs: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in attrs.split(";"):
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        elif " " in part:
            key, value = part.split(" ", 1)
        else:
            continue
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def read_gff_protein_ids(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    protein_ids: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9:
                continue
            attrs = parse_gff_attributes(parts[8])
            for key in ("protein_id", "Protein_Accession", "Parent_Accession", "Derives_from", "Name", "ID"):
                value = attrs.get(key)
                if value:
                    protein_ids.add(value)
                    break
    return protein_ids


def genus(name: str) -> str:
    return (name or "").strip().split()[0].lower()


def same_genus(left: str, right: str) -> bool:
    if not left or not right:
        return True
    return genus(left) == genus(right)


def validate_query_controls(query_fasta: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        records = read_fasta_records(query_fasta)
    except OSError as exc:
        return {
            "ok": False,
            "query_count": 0,
            "present_controls": [],
            "missing_controls": sorted(CONTROL_PATTERNS),
            "errors": [str(exc)],
        }

    if not records:
        errors.append("query FASTA is empty")

    header_text = "\n".join(record["header"] for record in records)
    present = sorted(name for name, pattern in CONTROL_PATTERNS.items() if pattern.search(header_text))
    missing = sorted(set(CONTROL_PATTERNS) - set(present))
    if missing:
        errors.append("query FASTA must include ACT2, GAPDH, and random-shuffle/negative controls")

    return {
        "ok": not errors,
        "query_count": len(records),
        "present_controls": present,
        "missing_controls": missing,
        "errors": errors,
    }


def normalize_source(row: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    normalized = {str(key).strip(): str(value).strip() for key, value in row.items() if key is not None}
    for key in ("proteome_fasta", "proteome", "gff", "genome_fasta", "genome", "transcriptome"):
        value = normalized.get(key, "")
        if value and base_dir and not re.match(r"^[a-z][a-z0-9+.-]*://", value, flags=re.IGNORECASE):
            candidate = Path(value)
            if not candidate.is_absolute():
                normalized[key] = str((base_dir / candidate).resolve())
    if "proteome_fasta" not in normalized and "proteome" in normalized:
        normalized["proteome_fasta"] = normalized["proteome"]
    if "genome_fasta" not in normalized and "genome" in normalized:
        normalized["genome_fasta"] = normalized["genome"]
    if "source_id" not in normalized:
        normalized["source_id"] = normalized.get("dataset_id") or normalized.get("organism") or "source-1"
    return normalized


def load_source_ledger(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [normalize_source(row, base_dir=path.parent) for row in reader]


def parse_source_arg(value: str) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for part in value.split(","):
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"source fragment lacks key=value: {part}")
        key, item = part.split("=", 1)
        row[key.strip()] = item.strip()
    return normalize_source(row)


def load_campaign(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}
    except json.JSONDecodeError:
        return {}


def infer_campaign_organism(campaign: dict[str, Any]) -> str:
    organism = campaign.get("organism", "")
    if isinstance(organism, dict):
        return str(organism.get("scientific_name") or organism.get("name") or "")
    return str(organism or "")


def evaluate_source(source: dict[str, Any], controls_ok: bool, campaign_organism: str = "") -> dict[str, Any]:
    proteome_value = source.get("proteome_fasta", "")
    gff_value = source.get("gff", "")
    genome_value = source.get("genome_fasta", "")
    transcriptome_value = source.get("transcriptome", "")

    proteome_path = Path(proteome_value) if proteome_value and not re.match(r"^[a-z][a-z0-9+.-]*://", proteome_value, re.I) else None
    gff_path = Path(gff_value) if gff_value and not re.match(r"^[a-z][a-z0-9+.-]*://", gff_value, re.I) else None
    proteome_ids = read_fasta_ids(proteome_path)
    gff_protein_ids = read_gff_protein_ids(gff_path)
    join_ids = proteome_ids & gff_protein_ids

    organism = str(source.get("organism") or campaign_organism or "")
    transcriptome_species = str(source.get("transcriptome_species") or organism)
    transcriptome_mismatch = bool(transcriptome_value or truthy(source.get("has_transcriptome"))) and not same_genus(organism, transcriptome_species)

    blockers: list[str] = []
    recommended = "next_experiment_design"
    claim_ceiling = "L0_route_only"

    has_proteome = path_exists(proteome_value) or truthy(source.get("has_proteome"))
    has_gff = path_exists(gff_value) or truthy(source.get("has_gff"))
    has_genome = path_exists(genome_value) or truthy(source.get("has_genome"))
    has_transcriptome = path_exists(transcriptome_value) or truthy(source.get("has_transcriptome"))

    if not controls_ok:
        blockers.append("missing_required_query_controls")
    if transcriptome_mismatch:
        blockers.append("transcriptome_species_mismatch")

    if controls_ok and proteome_ids and gff_protein_ids and join_ids:
        recommended = "annotation_direct"
        claim_ceiling = "L3_annotation_neighborhood_ready"
    elif controls_ok and has_proteome and has_gff:
        blockers.append("proteome_gff_join_failed")
        recommended = "annotation_direct_then_context"
        claim_ceiling = "L2_annotation_assets_need_join_repair"
    elif controls_ok and has_genome and has_gff:
        recommended = "genome_context"
        claim_ceiling = "L2_coordinate_context_ready"
    elif controls_ok and has_genome:
        recommended = "tblastn_rescue"
        claim_ceiling = "L1_sequence_rescue_only"
    elif controls_ok and has_transcriptome and not transcriptome_mismatch:
        recommended = "transcriptome_only"
        claim_ceiling = "L1_candidate_gene_only"
    elif transcriptome_mismatch:
        recommended = "next_experiment_design"
        claim_ceiling = "L0_route_only"
    elif controls_ok:
        blockers.append("no_annotation_or_sequence_source_available")

    return {
        "source_id": str(source.get("source_id") or "source-1"),
        "organism": organism,
        "proteome_fasta": str(proteome_value),
        "gff": str(gff_value),
        "genome_fasta": str(genome_value),
        "transcriptome": str(transcriptome_value),
        "transcriptome_species": transcriptome_species,
        "has_proteome": has_proteome,
        "has_gff": has_gff,
        "has_genome": has_genome,
        "has_transcriptome": has_transcriptome,
        "proteome_count": len(proteome_ids),
        "gff_protein_count": len(gff_protein_ids),
        "protein_gff_join_count": len(join_ids),
        "transcriptome_species_mismatch": transcriptome_mismatch,
        "controls_ok": controls_ok,
        "recommended_route": recommended,
        "claim_ceiling": claim_ceiling,
        "blockers": sorted(set(blockers)),
    }


def route_rank(route: str) -> int:
    ranking = {
        "annotation_direct": 90,
        "annotation_direct_then_context": 80,
        "genome_context": 70,
        "tblastn_rescue": 60,
        "transcriptome_only": 50,
        "transcript_first": 45,
        "coexpression": 30,
        "synteny": 30,
        "next_experiment_design": 0,
    }
    return ranking.get(route, 0)


def build_route_records(source_rows: list[dict[str, Any]], selected: dict[str, Any] | None, controls: dict[str, Any]) -> list[dict[str, Any]]:
    selected_route = selected["recommended_route"] if selected else "next_experiment_design"
    records: list[dict[str, Any]] = []
    for route in ROUTES:
        reason = ""
        status = "deferred"
        if route == selected_route:
            status = "selected"
            reason = "highest-confidence available route after source and control checks"
        elif route == "annotation_direct":
            if not controls["ok"]:
                status = "rejected"
                reason = "missing required query controls"
            elif not any(row["has_proteome"] and row["has_gff"] for row in source_rows):
                status = "rejected"
                reason = "no source has both proteome FASTA and GFF"
            elif not any(row["protein_gff_join_count"] > 0 for row in source_rows):
                status = "rejected"
                reason = "proteome FASTA IDs do not join to GFF protein_id attributes"
            else:
                reason = "available but not highest-ranked source"
        elif route == "annotation_direct_then_context":
            if not any(row["has_proteome"] and row["has_gff"] for row in source_rows):
                status = "rejected"
                reason = "no annotation pair to repair"
            else:
                reason = "use if direct protein-GFF join needs repair"
        elif route == "transcript_first":
            mismatches = [row for row in source_rows if row["transcriptome_species_mismatch"]]
            if mismatches:
                status = "rejected"
                reason = "same-species transcript-first route rejected because transcriptome species does not match target genus"
            elif not any(row["has_transcriptome"] for row in source_rows):
                status = "rejected"
                reason = "no transcriptome source available"
            else:
                reason = "available as lower-ceiling candidate route"
        elif route == "genome_context":
            if not any(row["has_genome"] or row["has_gff"] for row in source_rows):
                status = "rejected"
                reason = "no genome/GFF context available"
            else:
                reason = "available for coordinate-backed context and later synteny"
        elif route == "transcriptome_only":
            if not any(row["has_transcriptome"] for row in source_rows):
                status = "rejected"
                reason = "no transcriptome source available"
            elif any(row["transcriptome_species_mismatch"] for row in source_rows):
                status = "rejected"
                reason = "cross-genus transcriptome would overclaim same-species evidence"
            else:
                reason = "candidate-gene route only; no physical cluster claim"
        elif route == "tblastn_rescue":
            if not any(row["has_genome"] for row in source_rows):
                status = "rejected"
                reason = "no genome FASTA available for translated rescue"
            else:
                reason = "available when annotation is absent or broken"
        elif route == "coexpression":
            if not any(row["has_transcriptome"] for row in source_rows):
                status = "rejected"
                reason = "no expression/transcriptome source available"
            else:
                reason = "non-blocking support route; cannot create physical cluster truth alone"
        elif route == "synteny":
            if len([row for row in source_rows if row["has_genome"] or row["has_gff"]]) < 2:
                status = "rejected"
                reason = "requires at least two coordinate-capable species"
            else:
                reason = "non-blocking comparative route after coordinate ledgers exist"
        elif route == "next_experiment_design":
            reason = "fallback for missing controls, mismatched species, or insufficient public assets"

        records.append(
            {
                "route": route,
                "status": status,
                "reason": reason,
            }
        )
    return records


def build_route_decision(
    query_fasta: Path,
    sources: list[dict[str, Any]],
    campaign: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    campaign = campaign or {}
    controls = validate_query_controls(query_fasta)
    campaign_organism = infer_campaign_organism(campaign)
    source_rows = [evaluate_source(source, controls_ok=controls["ok"], campaign_organism=campaign_organism) for source in sources]
    if not source_rows:
        source_rows = [
            {
                "source_id": "no-source",
                "organism": campaign_organism,
                "proteome_fasta": "",
                "gff": "",
                "genome_fasta": "",
                "transcriptome": "",
                "transcriptome_species": "",
                "has_proteome": False,
                "has_gff": False,
                "has_genome": False,
                "has_transcriptome": False,
                "proteome_count": 0,
                "gff_protein_count": 0,
                "protein_gff_join_count": 0,
                "transcriptome_species_mismatch": False,
                "controls_ok": controls["ok"],
                "recommended_route": "next_experiment_design",
                "claim_ceiling": "L0_route_only",
                "blockers": ["no_source_ledger_rows"],
            }
        ]

    selected = max(source_rows, key=lambda row: (route_rank(row["recommended_route"]), row["protein_gff_join_count"], row["proteome_count"]))
    if not controls["ok"]:
        selected["recommended_route"] = "next_experiment_design"
        selected["claim_ceiling"] = "L0_route_only"
        selected["blockers"] = sorted(set(selected["blockers"] + ["missing_required_query_controls"]))

    blockers = sorted(set(selected["blockers"]) | set(controls["errors"]))
    decision = {
        "schema_version": "genecluster_route_decision.v1",
        "generated_at": timestamp(),
        "campaign_id": campaign.get("campaign_id", ""),
        "selected_route": selected["recommended_route"],
        "selected_source_id": selected["source_id"],
        "claim_ceiling": selected["claim_ceiling"],
        "blockers": blockers,
        "controls": controls,
        "source_availability": [
            {
                key: row[key]
                for key in (
                    "source_id",
                    "organism",
                    "has_proteome",
                    "has_gff",
                    "has_genome",
                    "has_transcriptome",
                    "protein_gff_join_count",
                    "transcriptome_species_mismatch",
                )
            }
            for row in source_rows
        ],
        "positive_controls": [name for name in controls["present_controls"] if name in {"ACT2", "GAPDH"}],
        "negative_controls": [name for name in controls["present_controls"] if name == "random_shuffle"],
        "routes": build_route_records(source_rows, selected, controls),
        "rejected_routes": [
            record for record in build_route_records(source_rows, selected, controls) if record["status"] == "rejected"
        ],
    }
    return decision, source_rows


def write_annotation_ledger(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=ANNOTATION_LEDGER_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "source_id": row["source_id"],
                    "organism": row["organism"],
                    "proteome_fasta": row["proteome_fasta"],
                    "gff": row["gff"],
                    "genome_fasta": row["genome_fasta"],
                    "transcriptome": row["transcriptome"],
                    "transcriptome_species": row["transcriptome_species"],
                    "proteome_count": row["proteome_count"],
                    "gff_protein_count": row["gff_protein_count"],
                    "protein_gff_join_count": row["protein_gff_join_count"],
                    "controls_ok": str(row["controls_ok"]).lower(),
                    "recommended_route": row["recommended_route"],
                    "claim_ceiling": row["claim_ceiling"],
                    "blockers": ",".join(row["blockers"]),
                }
            )


def write_route_outputs(decision: dict[str, Any], rows: list[dict[str, Any]], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    decision_path = out_dir / "route_decision.json"
    ledger_path = out_dir / "annotation-ledger.tsv"
    decision_path.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_annotation_ledger(rows, ledger_path)
    return {"route_decision": str(decision_path), "annotation_ledger": str(ledger_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scout GeneCluster source availability and choose a campaign route.")
    parser.add_argument("--campaign", type=Path, help="Optional campaign-manifest.json.")
    parser.add_argument("--query-fasta", type=Path, required=True, help="Query FASTA containing ACT2, GAPDH, and random-shuffle controls.")
    parser.add_argument("--source-ledger", type=Path, help="TSV ledger describing candidate annotation/transcriptome/genome sources.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Inline source as comma-separated key=value pairs, e.g. source_id=coptis,organism='Coptis chinensis',proteome_fasta=proteins.faa,gff=genomic.gff.",
    )
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for route_decision.json and annotation-ledger.tsv.")
    parser.add_argument("--json", action="store_true", help="Print the route decision JSON to stdout.")
    args = parser.parse_args()

    sources: list[dict[str, Any]] = []
    if args.source_ledger:
        sources.extend(load_source_ledger(args.source_ledger))
    try:
        sources.extend(parse_source_arg(value) for value in args.source)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    campaign = load_campaign(args.campaign)
    decision, rows = build_route_decision(args.query_fasta, sources, campaign=campaign)
    paths = write_route_outputs(decision, rows, args.out_dir)
    if args.json:
        print(json.dumps({"ok": True, "paths": paths, "decision": decision}, indent=2, sort_keys=True))
    else:
        print(f"selected_route={decision['selected_route']}")
        print(f"route_decision={paths['route_decision']}")
        print(f"annotation_ledger={paths['annotation_ledger']}")
        if decision["blockers"]:
            print("blockers=" + ",".join(decision["blockers"]))
    return 0 if decision["controls"]["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
