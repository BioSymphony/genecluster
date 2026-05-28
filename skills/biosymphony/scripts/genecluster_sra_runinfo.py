#!/usr/bin/env python3
"""Resolve SRA-style accessions to concrete runs and read layouts.

GeneCluster pipelines must not guess that an intake accession is the directory
to pass to fasterq-dump, and must not guess paired/single layout from platform
or filename. This script writes the small ledgers that provider-side pipelines
use before fetching large reads.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


SRA_PREFIXES = (
    "SRR",
    "SRX",
    "SRS",
    "SRA",
    "ERR",
    "ERX",
    "ERS",
    "DRR",
    "DRX",
    "DRS",
    "PRJ",
    "SRP",
    "ERP",
    "DRP",
    "SAMN",
    "BIOPROJECT",
)

READ_ACCESSION_FIELDS = [
    "source_id",
    "source_record_type",
    "source_provider",
    "source_accession",
    "source_accession_kind",
    "material_type",
    "acquisition_policy",
    "dataset_id",
    "organism",
    "data_role",
    "input_accession",
    "run_accession",
    "experiment_accession",
    "sample_accession",
    "study_accession",
    "bioproject",
    "library_layout",
    "layout_branch",
    "platform",
    "instrument_model",
    "spots",
    "bases",
    "size_bytes",
    "expected_fastq",
    "aligner_hint",
    "remote_path",
    "raw_artifact_policy",
    "status",
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def is_sra_like_accession(value: str) -> bool:
    value = (value or "").strip().upper()
    return value.startswith(SRA_PREFIXES)


def first_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    if node is None or node.text is None:
        return ""
    return node.text.strip()


def layout_from_experiment(exp: ET.Element | None) -> str:
    if exp is None:
        return "UNKNOWN"
    layout = exp.find(".//LIBRARY_LAYOUT")
    if layout is None:
        return "UNKNOWN"
    for child in list(layout):
        tag = child.tag.upper().split("}")[-1]
        if tag in {"SINGLE", "PAIRED"}:
            return tag
    return "UNKNOWN"


def platform_from_experiment(exp: ET.Element | None) -> tuple[str, str]:
    if exp is None:
        return "", ""
    platform = exp.find(".//PLATFORM")
    if platform is None or not list(platform):
        return "", ""
    child = list(platform)[0]
    return child.tag.upper().split("}")[-1], child.attrib.get("instrument_model", "")


def expected_fastq_pattern(run_accession: str, layout: str) -> str:
    if layout == "PAIRED":
        return f"{run_accession}_1.fastq + {run_accession}_2.fastq"
    if layout == "SINGLE":
        return f"{run_accession}.fastq or {run_accession}_1.fastq"
    return f"{run_accession}*.fastq (layout unresolved; review required)"


def aligner_hint(layout: str) -> str:
    if layout == "PAIRED":
        return "hisat2 -1 <mate1> -2 <mate2>"
    if layout == "SINGLE":
        return "hisat2 -U <reads>"
    return "review layout before alignment/assembly"


def branch_for_layout(layouts: set[str]) -> str:
    if layouts == {"SINGLE"}:
        return "single_end"
    if layouts == {"PAIRED"}:
        return "paired_end"
    if "UNKNOWN" in layouts or not layouts:
        return "review_required"
    return "mixed_layout_review_required"


def parse_sra_xml(
    xml_text: str,
    *,
    input_accession: str,
    dataset_id: str = "",
    source_role: str = "",
    organism: str = "",
    data_role: str = "",
    remote_path: str = "",
    raw_artifact_policy: str = "",
) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    exp = root.find(".//EXPERIMENT")
    exp_accession = exp.attrib.get("accession", "") if exp is not None else ""
    layout = layout_from_experiment(exp)
    platform, instrument = platform_from_experiment(exp)
    study_accession = ""
    if exp is not None:
        study_ref = exp.find(".//STUDY_REF")
        if study_ref is not None:
            study_accession = study_ref.attrib.get("accession", "")
    bioproject = first_text(root, ".//Bioproject")
    sample = root.find(".//SAMPLE")
    sample_accession = sample.attrib.get("accession", "") if sample is not None else ""

    runs: list[dict[str, Any]] = []
    for run in root.findall(".//RUN"):
        run_accession = run.attrib.get("accession", "")
        if not run_accession:
            continue
        runs.append(
            {
                "dataset_id": dataset_id,
                "input_accession": input_accession,
                "run_accession": run_accession,
                "experiment_accession": exp_accession,
                "sample_accession": sample_accession,
                "study_accession": study_accession,
                "bioproject": bioproject,
                "organism": organism,
                "data_role": data_role or source_role,
                "source_role": source_role,
                "library_layout": layout,
                "platform": platform,
                "instrument_model": instrument,
                "spots": run.attrib.get("total_spots", ""),
                "bases": run.attrib.get("total_bases", ""),
                "size_bytes": run.attrib.get("size", ""),
                "expected_fastq": expected_fastq_pattern(run_accession, layout),
                "aligner_hint": aligner_hint(layout),
                "remote_path": remote_path,
                "raw_artifact_policy": raw_artifact_policy,
                "status": "resolved",
            }
        )

    if not runs:
        runs.append(
            {
                "dataset_id": dataset_id,
                "input_accession": input_accession,
                "run_accession": "",
                "experiment_accession": exp_accession,
                "sample_accession": sample_accession,
                "study_accession": study_accession,
                "bioproject": bioproject,
                "organism": organism,
                "data_role": data_role or source_role,
                "source_role": source_role,
                "library_layout": layout,
                "platform": platform,
                "instrument_model": instrument,
                "spots": "",
                "bases": "",
                "size_bytes": "",
                "expected_fastq": "",
                "aligner_hint": aligner_hint(layout),
                "remote_path": remote_path,
                "raw_artifact_policy": raw_artifact_policy,
                "status": "no_run_resolved",
            }
        )

    layouts = {str(row["library_layout"]) for row in runs}
    layout_branch = branch_for_layout(layouts)
    for row in runs:
        row["layout_branch"] = layout_branch
    return {
        "input_accession": input_accession,
        "dataset_id": dataset_id,
        "runs": runs,
        "run_count": sum(1 for row in runs if row.get("run_accession")),
        "layout_branch": layout_branch,
        "status": "resolved" if any(row.get("run_accession") for row in runs) else "no_run_resolved",
    }


def fetch_sra_xml(accession: str, timeout: float = 30) -> str:
    url = "https://trace.ncbi.nlm.nih.gov/Traces/sra-db-be/run_new?acc=" + urllib.parse.quote(accession)
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - NCBI public metadata endpoint.
        return response.read().decode("utf-8", errors="replace")


def resolve_accessions(
    accessions: list[dict[str, str]],
    *,
    xml_cache_dir: Path | None = None,
    timeout: float = 30,
    sleep_seconds: float = 0.34,
) -> dict[str, Any]:
    resolved: list[dict[str, Any]] = []
    errors: list[str] = []
    summaries: list[dict[str, Any]] = []

    if xml_cache_dir:
        xml_cache_dir.mkdir(parents=True, exist_ok=True)

    for row in accessions:
        accession = str(row.get("accession", "")).strip()
        if not accession:
            continue
        try:
            cache_path = xml_cache_dir / f"{accession}.xml" if xml_cache_dir else None
            if cache_path and cache_path.exists():
                xml_text = cache_path.read_text(encoding="utf-8")
            else:
                xml_text = fetch_sra_xml(accession, timeout=timeout)
                if cache_path:
                    cache_path.write_text(xml_text, encoding="utf-8")
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            parsed = parse_sra_xml(
                xml_text,
                input_accession=accession,
                dataset_id=row.get("dataset_id", ""),
                source_role=row.get("role", "") or row.get("sample_type", ""),
                organism=row.get("organism", ""),
                data_role=row.get("data_role", ""),
                remote_path=row.get("remote_path", ""),
                raw_artifact_policy=row.get("raw_artifact_policy", ""),
            )
            resolved.extend(parsed["runs"])
            summaries.append({k: parsed[k] for k in ["input_accession", "dataset_id", "run_count", "layout_branch", "status"]})
        except Exception as exc:  # noqa: BLE001 - this is an operator preflight; record and continue.
            errors.append(f"{accession}: {exc}")
            summaries.append(
                {
                    "input_accession": accession,
                    "dataset_id": row.get("dataset_id", ""),
                    "run_count": 0,
                    "layout_branch": "resolution_failed",
                    "status": "resolution_failed",
                }
            )
    return {"rows": resolved, "summaries": summaries, "errors": errors}


def source_accession_kind(accession: str) -> str:
    value = accession.upper()
    if value.startswith(("SRR", "ERR", "DRR")):
        return "run_accession"
    if value.startswith(("SRX", "ERX", "DRX")):
        return "experiment_accession"
    if value.startswith(("SRS", "ERS", "DRS", "SAMN")):
        return "sample_accession"
    if value.startswith(("SRP", "ERP", "DRP", "PRJ", "BIOPROJECT")):
        return "study_or_project_accession"
    return "sra_like_accession"


def build_read_accession_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        run_accession = str(row.get("run_accession", ""))
        input_accession = str(row.get("input_accession", ""))
        dataset_id = str(row.get("dataset_id", ""))
        source_id_parts = [part for part in [dataset_id, run_accession or input_accession] if part]
        output.append(
            {
                "source_id": ":".join(source_id_parts) or input_accession or run_accession,
                "source_record_type": "read_acquisition",
                "source_provider": "NCBI SRA",
                "source_accession": run_accession or input_accession,
                "source_accession_kind": source_accession_kind(run_accession or input_accession),
                "material_type": row.get("data_role") or row.get("source_role", ""),
                "acquisition_policy": "metadata_resolved_raw_remote_only",
                **row,
            }
        )
    return output


def rows_from_args(data_ledger: Path | None, explicit_accessions: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if data_ledger:
        for row in read_tsv(data_ledger):
            accession = str(row.get("accession", "")).strip()
            if is_sra_like_accession(accession):
                rows.append(row)
    for accession in explicit_accessions:
        rows.append({"dataset_id": accession, "accession": accession, "role": "manual"})
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve SRA accessions to runs and read layouts.")
    parser.add_argument("--data-ledger", type=Path, help="data-ledger.tsv containing an accession column.")
    parser.add_argument("--accession", action="append", default=[], help="Additional accession to resolve.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--xml-cache-dir", type=Path, help="Optional cache for fetched XML metadata.")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--sleep-seconds", type=float, default=0.34)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    input_rows = rows_from_args(args.data_ledger, args.accession)
    result = resolve_accessions(
        input_rows,
        xml_cache_dir=args.xml_cache_dir,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
    )

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "dataset_id",
        "input_accession",
        "run_accession",
        "experiment_accession",
        "sample_accession",
        "study_accession",
        "bioproject",
        "source_role",
        "library_layout",
        "layout_branch",
        "platform",
        "instrument_model",
        "spots",
        "bases",
        "size_bytes",
        "expected_fastq",
        "aligner_hint",
        "organism",
        "data_role",
        "remote_path",
        "raw_artifact_policy",
        "status",
    ]
    write_tsv(out_dir / "resolved-accessions.tsv", result["rows"], fields)
    write_tsv(out_dir / "sra-layout.tsv", result["rows"], fields)
    read_accession_rows = build_read_accession_rows(result["rows"])
    write_tsv(out_dir / "read-accessions.tsv", read_accession_rows, READ_ACCESSION_FIELDS)
    summary = {
        "ok": not result["errors"],
        "input_count": len(input_rows),
        "resolved_run_count": sum(1 for row in result["rows"] if row.get("run_accession")),
        "accessions": result["summaries"],
        "errors": result["errors"],
        "outputs": {
            "resolved_accessions": str(out_dir / "resolved-accessions.tsv"),
            "sra_layout": str(out_dir / "sra-layout.tsv"),
            "read_accessions": str(out_dir / "read-accessions.tsv"),
        },
    }
    (out_dir / "sra-runinfo-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print("GeneCluster SRA runinfo:", "ok" if summary["ok"] else "failed")
        print(f"resolved runs: {summary['resolved_run_count']} from {summary['input_count']} inputs")
        for error in result["errors"]:
            print(f"ERROR: {error}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
