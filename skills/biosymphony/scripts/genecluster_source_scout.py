#!/usr/bin/env python3
"""Deterministic local-light source scout for GeneCluster query intake.

The scout reads a registry TSV and writes source/query ledgers without making
network calls or downloading raw data. Probe statuses are derived only from
registry fields so the output is reproducible and safe to run before a campaign
is approved for heavier work.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


PROBE_ORDER = [
    "NCBI Datasets/API",
    "NCBI protein",
    "UniProt REST",
    "NGDC GWH/CNCB",
    "GSA/CNGB",
    "figshare",
    "paper supplement/manual-required",
]

MISSING_VALUES = {"", "-", "na", "n_a", "none", "null", "not_applicable", "missing"}
TRUTHY_VALUES = {"1", "true", "yes", "y", "required", "manual_required", "manual-required"}

POSITIVE_STATUSES = {
    "available",
    "candidate_source_available",
    "present",
    "registry_reference_present",
    "resolved",
    "source_available",
}

BLOCKED_STATUSES = {
    "blocked",
    "intake_blocked",
    "manual_required",
    "unresolved",
    "unresolved_intake_blocked",
}

PROBE_FIELDS = {
    "NCBI Datasets/API": {
        "value": ["ncbi_datasets_api", "ncbi_datasets_accession", "ncbi_assembly_accession", "ncbi_bioproject", "ncbi_genome"],
        "status": ["ncbi_datasets_api_status", "ncbi_datasets_status"],
    },
    "NCBI protein": {
        "value": ["ncbi_protein", "ncbi_protein_accession", "protein_accession"],
        "status": ["ncbi_protein_status", "protein_accession_status"],
    },
    "UniProt REST": {
        "value": ["uniprot_rest", "uniprot_accession", "uniprot_id"],
        "status": ["uniprot_rest_status", "uniprot_status"],
    },
    "NGDC GWH/CNCB": {
        "value": ["ngdc_gwh_cncb", "ngdc_gwh_accession", "cncb_accession", "gwh_accession"],
        "status": ["ngdc_gwh_cncb_status", "ngdc_status", "gwh_status"],
    },
    "GSA/CNGB": {
        "value": ["gsa_cngb", "gsa_accession", "cngb_accession"],
        "status": ["gsa_cngb_status", "gsa_status", "cngb_status"],
    },
    "figshare": {
        "value": ["figshare", "figshare_url", "figshare_doi"],
        "status": ["figshare_status"],
    },
    "paper supplement/manual-required": {
        "value": ["paper_supplement", "supplement_reference", "manual_reference"],
        "status": ["paper_supplement_status", "manual_status"],
    },
}

REQUIRED_QUERY_COLUMNS = {"query_id", "query_name", "claim_id", "claim_ceiling", "resolution_status"}

SOURCE_LEDGER_COLUMNS = [
    "source_id",
    "source_record_type",
    "source_provider",
    "source_accession",
    "source_accession_kind",
    "material_type",
    "acquisition_policy",
    "organism",
    "proteome_fasta",
    "gff",
    "genome_fasta",
    "transcriptome",
    "transcriptome_species",
    "source_class",
    "scout_status",
    "has_genome",
    "has_proteome",
    "has_gff",
    "query_id",
    "query_name",
    "claim_id",
    "probe_order_index",
    "source_name",
    "probe_status",
    "status_source_field",
    "source_field",
    "source_value",
    "raw_download_planned",
    "network_call_planned",
    "notes",
]

QUERY_RESOLUTION_COLUMNS = [
    "query_id",
    "query_name",
    "source_organism",
    "claim_id",
    "resolution_status",
    "claim_ceiling",
    "selected_source",
    "selected_reference",
    "blocking_reason",
    "probe_order",
    "manual_action",
    "notes",
]


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")


def is_missing(value: Any) -> bool:
    return slug(clean(value)) in MISSING_VALUES


def truthy(value: Any) -> bool:
    return slug(clean(value)) in TRUTHY_VALUES


def first_present(row: dict[str, str], fields: list[str]) -> tuple[str, str]:
    for field in fields:
        value = clean(row.get(field, ""))
        if not is_missing(value):
            return field, value
    return "", ""


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists():
        if path.suffix or len(path.parts) > 1:
            raise FileNotFoundError(path)
        return {"campaign_id": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def read_query_registry(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        headers = reader.fieldnames or []
        rows = [{key: clean(value) for key, value in row.items() if key is not None} for row in reader]
    return rows, headers


def validate_registry(rows: list[dict[str, str]], headers: list[str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_QUERY_COLUMNS - set(headers))
    if missing:
        errors.append(f"query registry missing columns: {', '.join(missing)}")
    if not rows:
        errors.append("query registry must contain at least one row")

    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        query_id = row.get("query_id", "")
        if not query_id:
            errors.append(f"row {index} missing query_id")
            continue
        if query_id in seen:
            errors.append(f"duplicate query_id: {query_id}")
        seen.add(query_id)
    return errors


def derive_probe(row: dict[str, str], source_name: str, index: int) -> dict[str, str]:
    fields = PROBE_FIELDS[source_name]
    status_field, status_value = first_present(row, fields["status"])
    source_field, source_value = first_present(row, fields["value"])

    if status_value:
        probe_status = slug(status_value)
        status_source_field = status_field
    elif source_value:
        probe_status = "registry_reference_present"
        status_source_field = source_field
    elif source_name == "paper supplement/manual-required" and (
        truthy(row.get("manual_required", "")) or slug(row.get("resolution_status", "")) == "unresolved_intake_blocked"
    ):
        probe_status = "manual_required"
        status_source_field = "manual_required" if truthy(row.get("manual_required", "")) else "resolution_status"
    else:
        probe_status = "not_recorded_in_registry"
        status_source_field = ""

    is_positive = probe_status in POSITIVE_STATUSES
    genome_source = source_name in {"NCBI Datasets/API", "NGDC GWH/CNCB", "GSA/CNGB", "figshare"}
    proteome_source = source_name in {"NCBI protein", "UniProt REST"}
    query_id = clean(row.get("query_id", ""))
    accession_kind = {
        "NCBI Datasets/API": "assembly_or_bioproject_accession",
        "NCBI protein": "protein_accession",
        "UniProt REST": "uniprot_accession",
        "NGDC GWH/CNCB": "assembly_or_project_accession",
        "GSA/CNGB": "read_or_project_accession",
        "figshare": "doi_or_url",
        "paper supplement/manual-required": "manual_reference",
    }.get(source_name, "registry_value")
    material_type = "genome" if genome_source else "proteome" if proteome_source else "manual_or_supplemental_reference"
    return {
        "source_id": f"{query_id}-{slug(source_name) or index}",
        "source_record_type": "source_scout_probe",
        "source_provider": source_name,
        "source_accession": source_value,
        "source_accession_kind": accession_kind,
        "material_type": material_type,
        "acquisition_policy": "metadata_only_no_network_no_raw_download",
        "organism": clean(row.get("source_organism", "")),
        "proteome_fasta": source_value if is_positive and proteome_source else "",
        "gff": "",
        "genome_fasta": source_value if is_positive and genome_source else "",
        "transcriptome": "",
        "transcriptome_species": clean(row.get("source_organism", "")),
        "source_class": source_name,
        "scout_status": probe_status,
        "has_genome": str(bool(is_positive and genome_source)).lower(),
        "has_proteome": str(bool(is_positive and proteome_source)).lower(),
        "has_gff": "false",
        "query_id": clean(row.get("query_id", "")),
        "query_name": clean(row.get("query_name", "")),
        "claim_id": clean(row.get("claim_id", "")),
        "probe_order_index": str(index),
        "source_name": source_name,
        "probe_status": probe_status,
        "status_source_field": status_source_field,
        "source_field": source_field,
        "source_value": source_value,
        "raw_download_planned": "false",
        "network_call_planned": "false",
        "notes": clean(row.get(f"{slug(source_name)}_notes", "")),
    }


def selected_probe(probes: list[dict[str, str]]) -> dict[str, str] | None:
    for probe in probes:
        if probe["probe_status"] in POSITIVE_STATUSES:
            return probe
    for probe in probes:
        if probe["probe_status"] in BLOCKED_STATUSES:
            return probe
    return None


def infer_resolution_status(row: dict[str, str], probes: list[dict[str, str]]) -> str:
    explicit = slug(row.get("resolution_status", ""))
    if explicit and explicit not in MISSING_VALUES:
        return explicit
    selected = selected_probe(probes)
    if selected and selected["probe_status"] in POSITIVE_STATUSES:
        return "registry_reference_present"
    if selected and selected["probe_status"] in BLOCKED_STATUSES:
        return selected["probe_status"]
    return "unresolved_no_registry_source"


def infer_claim_ceiling(row: dict[str, str], resolution_status: str) -> str:
    explicit = slug(row.get("claim_ceiling", ""))
    if explicit and explicit not in MISSING_VALUES:
        return explicit
    if resolution_status == "unresolved_intake_blocked":
        return "not_tested_intake_blocked"
    if resolution_status in POSITIVE_STATUSES:
        return "source_scout_only"
    return "source_scout_unresolved"


def selected_probe_for_resolution(resolution_status: str, probes: list[dict[str, str]]) -> dict[str, str] | None:
    if resolution_status in BLOCKED_STATUSES:
        for probe in probes:
            if probe["probe_status"] in BLOCKED_STATUSES:
                return probe
    return selected_probe(probes)


def build_query_record(row: dict[str, str]) -> dict[str, Any]:
    probes = [derive_probe(row, source_name, index) for index, source_name in enumerate(PROBE_ORDER, start=1)]
    resolution_status = infer_resolution_status(row, probes)
    claim_ceiling = infer_claim_ceiling(row, resolution_status)

    selected = selected_probe_for_resolution(resolution_status, probes)
    selected_source = selected["source_name"] if selected else ""
    selected_reference = selected["source_value"] if selected and selected["source_value"] else ""

    blocking_reason = clean(row.get("blocking_reason", ""))
    if not blocking_reason and resolution_status == "unresolved_intake_blocked":
        blocking_reason = "query sequence/accession is not resolved from approved public registry fields"
    elif not blocking_reason and resolution_status in {"manual_required", "unresolved_no_registry_source"}:
        blocking_reason = "manual source resolution required before sequence search"

    manual_action = clean(row.get("manual_action", ""))
    if not manual_action and resolution_status in {"unresolved_intake_blocked", "manual_required"}:
        manual_action = "resolve from paper supplement or curator-approved source; do not infer biology from missing query"

    return {
        "query_id": clean(row.get("query_id", "")),
        "query_name": clean(row.get("query_name", "")),
        "source_organism": clean(row.get("source_organism", "")),
        "claim_id": clean(row.get("claim_id", "")),
        "resolution_status": resolution_status,
        "claim_ceiling": claim_ceiling,
        "selected_source": selected_source,
        "selected_reference": selected_reference,
        "blocking_reason": blocking_reason,
        "probe_order": " > ".join(PROBE_ORDER),
        "manual_action": manual_action,
        "notes": clean(row.get("notes", "")),
        "probes": probes,
    }


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def campaign_summary(campaign: dict[str, Any]) -> dict[str, Any]:
    organism = campaign.get("organism", "")
    if isinstance(organism, dict):
        organism = organism.get("scientific_name") or organism.get("name") or ""
    return {
        "campaign_id": clean(campaign.get("campaign_id", "")),
        "target_pathway": clean(campaign.get("target_pathway", "")),
        "organism": clean(organism),
    }


def build_report(query_registry: Path, campaign_path: Path | None, out_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
    campaign = read_json(campaign_path)
    rows, headers = read_query_registry(query_registry)
    errors = validate_registry(rows, headers)

    records = [build_query_record(row) for row in rows] if not errors else []
    source_rows = [probe for record in records for probe in record["probes"]]

    counts: dict[str, int] = {
        "queries": len(records),
        "source_probe_rows": len(source_rows),
        "unresolved_intake_blocked": 0,
        "queries_with_manual_required_probe": 0,
        "registry_reference_present": 0,
    }
    for record in records:
        status = record["resolution_status"]
        if status in counts:
            counts[status] += 1
        if any(probe["probe_status"] == "manual_required" for probe in record["probes"]):
            counts["queries_with_manual_required_probe"] += 1

    output_paths = {
        "source_ledger": str(out_dir / "source-ledger.tsv"),
        "query_resolution_ledger": str(out_dir / "query-resolution-ledger.tsv"),
        "source_scout_report": str(out_dir / "source-scout-report.json"),
    }

    report = {
        "schema_version": "genecluster_source_scout.v1",
        "ok": not errors,
        "errors": errors,
        "campaign": campaign_summary(campaign),
        "inputs": {
            "campaign": str(campaign_path) if campaign_path else "",
            "query_registry": str(query_registry),
        },
        "outputs": output_paths,
        "probe_order": PROBE_ORDER,
        "policy": {
            "deterministic_registry_only": True,
            "network_calls": False,
            "raw_downloads": False,
            "probe_status_source": "query_registry_tsv_fields",
        },
        "counts": counts,
        "queries": [
            {
                key: value
                for key, value in record.items()
                if key in {"query_id", "query_name", "source_organism", "claim_id", "resolution_status", "claim_ceiling", "selected_source", "selected_reference", "blocking_reason", "manual_action", "notes"}
            }
            | {"probes": record["probes"]}
            for record in records
        ],
    }
    return report, records, source_rows


def write_outputs(report: dict[str, Any], records: list[dict[str, Any]], source_rows: list[dict[str, str]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    query_rows = [
        {key: record.get(key, "") for key in QUERY_RESOLUTION_COLUMNS}
        for record in records
    ]
    write_tsv(out_dir / "source-ledger.tsv", SOURCE_LEDGER_COLUMNS, source_rows)
    write_tsv(out_dir / "query-resolution-ledger.tsv", QUERY_RESOLUTION_COLUMNS, query_rows)
    (out_dir / "source-scout-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scout GeneCluster source/query resolution from a local registry TSV.")
    parser.add_argument("--campaign", type=Path, help="Optional campaign JSON. Used only for report metadata.")
    parser.add_argument("--query-registry", type=Path, required=True, help="Required TSV query/source registry.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Directory for source scout ledgers and JSON report.")
    parser.add_argument("--json", action="store_true", help="Print source-scout-report.json content to stdout.")
    args = parser.parse_args()

    try:
        report, records, source_rows = build_report(args.query_registry, args.campaign, args.out_dir)
        write_outputs(report, records, source_rows, args.out_dir)
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "ok" if report["ok"] else "failed"
        print(f"BioSymphony GeneCluster source scout: {status}")
        print(f"Queries: {report['counts']['queries']}")
        print(f"Unresolved intake blocked: {report['counts']['unresolved_intake_blocked']}")
        print(f"Manual required: {report['counts']['queries_with_manual_required_probe']}")
        for key, value in report["outputs"].items():
            print(f"{key}: {value}")
        for error in report["errors"]:
            print(f"ERROR: {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
