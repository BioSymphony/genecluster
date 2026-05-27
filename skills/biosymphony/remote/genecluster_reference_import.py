#!/usr/bin/env python3
"""Provider-side GeneCluster reference import helper.

The helper resolves public reference rows from the launch manifest ledgers into
provider paths and commands. Dry-run is the default and only writes plans. Real
execution is limited to explicit provider-side reference commands, never local
repo downloads or public webserver uploads.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REFERENCE_HEADERS = [
    "dataset_id",
    "data_role",
    "organism",
    "accession",
    "run_id",
    "bioproject",
    "source_url",
    "remote_path",
    "reference_kind",
    "resource_hint",
    "license_url",
    "citation_doi",
    "status",
    "reason",
    "command",
]

OBJECT_STORE_PREFIXES = ("s3://", "r2://", "b2://", "gs://", "az://")


def is_object_store_uri(value: str) -> bool:
    return value.startswith(OBJECT_STORE_PREFIXES)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_tsv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    manifest_relative = manifest_path.parent / path
    if manifest_relative.exists():
        return manifest_relative
    return path


def manifest_value(manifest: dict[str, Any], key: str) -> Any:
    if key in manifest and manifest[key]:
        return manifest[key]
    payload = manifest.get("provider_payload")
    if isinstance(payload, dict) and payload.get(key):
        return payload[key]
    return ""


def resolve_ledger_path(manifest: dict[str, Any], key: str, manifest_path: Path) -> Path:
    value = str(manifest_value(manifest, key))
    if not value:
        raise KeyError(key)
    path = resolve_manifest_path(value, manifest_path)
    if path.exists():
        return path
    repo_root = manifest.get("local_repo_root")
    if repo_root:
        repo_path = Path(str(repo_root)) / value
        if repo_path.exists():
            return repo_path
    return path


def genecluster_root(heavy_workdir: Path) -> Path:
    heavy_str = str(heavy_workdir)
    if heavy_str.startswith("/workspace/"):
        return Path("/workspace/genecluster")
    if heavy_workdir.parent.name == "runs":
        return heavy_workdir.parent.parent
    return heavy_workdir.parent / "genecluster"


def resolve_remote_path(value: str, *, run_id: str, heavy_workdir: Path | None = None) -> Path | None:
    resolved = value.replace("<run_id>", run_id)
    if not resolved or is_object_store_uri(resolved):
        return None
    if heavy_workdir and not str(heavy_workdir).startswith("/workspace/") and resolved.startswith("/workspace/genecluster/runs/"):
        prefix = Path("/workspace/genecluster/runs") / run_id
        path = Path(resolved)
        try:
            return heavy_workdir / path.relative_to(prefix)
        except ValueError:
            return genecluster_root(heavy_workdir) / path.relative_to("/workspace/genecluster")
    if heavy_workdir and not str(heavy_workdir).startswith("/workspace/") and resolved.startswith("/workspace/genecluster/"):
        return genecluster_root(heavy_workdir) / Path(resolved).relative_to("/workspace/genecluster")
    return Path(resolved)


def resource_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("resource", "").lower()
        if key:
            lookup[key] = row
        resource_type = row.get("resource_type", "").lower()
        if resource_type and resource_type not in lookup:
            lookup[resource_type] = row
    return lookup


def approved_resource(resources: dict[str, dict[str, str]], *needles: str) -> dict[str, str]:
    for needle in needles:
        needle_lower = needle.lower()
        for key, row in resources.items():
            haystack = f"{key} {row.get('resource', '')} {row.get('resource_type', '')} {row.get('use_mode', '')}".lower()
            if needle_lower in haystack and row.get("approval_status", "approved") == "approved":
                return row
    return {}


def infer_reference_kind(row: dict[str, str]) -> str:
    data_role = row.get("data_role", "").lower()
    accession = row.get("accession", "")
    run_id = row.get("run_id", "")
    if "assembly" in data_role or accession.startswith(("GCA_", "GCF_")):
        return "assembly"
    if run_id.startswith(("SRR", "ERR", "DRR")) or accession.startswith(("SRX", "SRR", "ERX", "ERR", "DRX", "DRR")):
        return "sra_run"
    if "annotation" in data_role or "gff" in data_role:
        return "annotation"
    if "transcriptome" in data_role:
        return "transcriptome"
    if "genome" in data_role:
        return "genome"
    return "metadata_reference"


def existing_public_fields(row: dict[str, str]) -> dict[str, str]:
    fields = {}
    for key in ["accession", "run_id", "bioproject", "source_url", "license_url", "citation_doi", "md5_or_sha256"]:
        value = row.get(key, "")
        if value and value not in {"remote_pending", "not_applicable"}:
            fields[key] = value
    return fields


def command_for_reference(row: dict[str, str], *, remote_path: Path, reference_kind: str, resources: dict[str, dict[str, str]]) -> tuple[list[str], dict[str, str]]:
    accession = row.get("accession", "")
    run_id = row.get("run_id", "")
    if reference_kind == "assembly":
        resource = approved_resource(resources, "ncbi datasets", "reference_import")
        if not resource:
            return [], {}
        command = [
            "datasets",
            "download",
            "genome",
            "accession",
            accession,
            "--include",
            "genome,gff3,protein,rna,seq-report",
            "--filename",
            str(remote_path / "ncbi_dataset.zip"),
        ]
        return command, resource
    if reference_kind == "sra_run":
        resource = approved_resource(resources, "ffq", "metadata_import")
        if resource and run_id:
            return ["ffq", "--ftp", run_id], resource
        if resource and accession:
            return ["ffq", "--ftp", accession], resource
    return [], {}


def plan_reference(
    row: dict[str, str],
    *,
    run_id: str,
    heavy_workdir: Path,
    resources: dict[str, dict[str, str]],
    mock_tools: bool,
    allow_reference_downloads: bool = False,
) -> dict[str, Any]:
    reference_kind = infer_reference_kind(row)
    remote_path = resolve_remote_path(row.get("remote_path", ""), run_id=run_id, heavy_workdir=heavy_workdir)
    public_fields = existing_public_fields(row)
    command, resource = command_for_reference(row, remote_path=remote_path, reference_kind=reference_kind, resources=resources) if remote_path else ([], {})
    binary = command[0] if command else ""
    tool_found = bool(binary and shutil.which(binary))
    status = "metadata_resolved"
    reason = "existing public reference fields recorded; no provider import command required"
    if remote_path is None:
        status = "blocked_object_store_adapter_unimplemented"
        reason = "reference remote_path is not a mounted filesystem path"
    elif command and reference_kind == "assembly" and not allow_reference_downloads:
        status = "blocked_reference_download_requires_opt_in"
        reason = "genome/protein/GFF reference downloads require --allow-reference-downloads"
    elif command:
        if mock_tools:
            status = "planned_mock"
            reason = "provider command planned with mocked tool availability"
        elif tool_found:
            status = "planned_import"
            reason = "provider command available"
        else:
            status = "blocked_missing_tool"
            reason = f"required provider tool missing: {binary}"
    elif reference_kind in {"sra_run", "transcriptome", "genome"}:
        status = "metadata_only"
        reason = "raw or heavy sequence import intentionally deferred; use an explicit data-import lane"
    if not public_fields:
        status = "blocked_missing_public_reference"
        reason = "data-ledger row lacks accession/run/source public reference fields"

    return {
        "dataset_id": row.get("dataset_id", ""),
        "data_role": row.get("data_role", ""),
        "organism": row.get("organism", ""),
        "accession": row.get("accession", ""),
        "run_id": row.get("run_id", ""),
        "bioproject": row.get("bioproject", ""),
        "source_url": row.get("source_url", ""),
        "remote_path": str(remote_path) if remote_path else row.get("remote_path", ""),
        "reference_kind": reference_kind,
        "resource_hint": resource.get("resource", ""),
        "license_url": row.get("license_url", ""),
        "citation_doi": row.get("citation_doi", ""),
        "public_fields": public_fields,
        "command": command,
        "status": status,
        "reason": reason,
    }


def execute_imports(records: list[dict[str, Any]], *, dry_run: bool, mock_tools: bool) -> list[dict[str, Any]]:
    executed = []
    if dry_run or mock_tools:
        return executed
    for record in records:
        if record["status"] != "planned_import":
            continue
        command = [str(part) for part in record["command"]]
        Path(record["remote_path"]).mkdir(parents=True, exist_ok=True)
        try:
            proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60 * 60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["status"] = "failed"
            record["reason"] = f"import command failed to start or timed out: {exc}"
            executed.append({"dataset_id": record["dataset_id"], "command": command, "returncode": "", "error": str(exc)})
            continue
        record["status"] = "imported" if proc.returncode == 0 else "failed"
        record["reason"] = "import command completed" if proc.returncode == 0 else "import command returned non-zero"
        executed.append(
            {
                "dataset_id": record["dataset_id"],
                "command": command,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-2000:],
                "stderr_tail": proc.stderr[-2000:],
            }
        )
    return executed


def import_references(
    *,
    launch_manifest: Path,
    out_dir: Path,
    dry_run: bool,
    mock_tools: bool,
    allow_reference_downloads: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(launch_manifest.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id", "unknown_run"))
    heavy_workdir = Path(str(manifest.get("heavy_workdir") or out_dir.parent / "run"))
    data_ledger = resolve_ledger_path(manifest, "data_ledger", launch_manifest)
    resource_ledger = resolve_ledger_path(manifest, "resource_ledger", launch_manifest)
    data_rows = read_tsv(data_ledger)
    resources = resource_lookup(read_tsv(resource_ledger))
    records = [
        plan_reference(
            row,
            run_id=run_id,
            heavy_workdir=heavy_workdir,
            resources=resources,
            mock_tools=mock_tools,
            allow_reference_downloads=allow_reference_downloads,
        )
        for row in data_rows
    ]
    executed = execute_imports(records, dry_run=dry_run, mock_tools=mock_tools)
    blockers = [
        {"dataset_id": item["dataset_id"], "status": item["status"], "reason": item["reason"]}
        for item in records
        if item["status"].startswith("blocked") or item["status"] == "failed"
    ]
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(launch_manifest),
        "data_ledger": str(data_ledger),
        "resource_ledger": str(resource_ledger),
        "run_id": run_id,
        "run_scope": str(manifest.get("run_scope", "")),
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "allow_reference_downloads": allow_reference_downloads,
        "records": records,
        "executed": executed,
        "blockers": blockers,
        "ok": not blockers or mock_tools,
    }
    write_json(out_dir / "reference-import-summary.json", summary)
    tsv_rows = [{**record, "command": " ".join(str(part) for part in record.get("command", []))} for record in records]
    write_tsv(out_dir / "resolved-references.tsv", REFERENCE_HEADERS, tsv_rows)
    return summary


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    dry_run: bool = False,
    mock_tools: bool = False,
    allow_reference_downloads: bool = False,
) -> Path:
    out_dir = out or launch_manifest.parent / "summary"
    import_references(
        launch_manifest=launch_manifest,
        out_dir=out_dir,
        dry_run=dry_run,
        mock_tools=mock_tools,
        allow_reference_downloads=allow_reference_downloads,
    )
    return out_dir / "reference-import-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve and optionally import provider-side public GeneCluster references.")
    parser.add_argument("--launch-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not execute provider-side import commands.")
    parser.add_argument("--mock-tools", action="store_true", help="Plan with mocked tool availability; never executes commands.")
    parser.add_argument("--allow-reference-downloads", action="store_true", help="Permit provider-side genome/protein/GFF reference downloads.")
    args = parser.parse_args()

    summary_path = run(
        args.launch_manifest,
        args.out,
        dry_run=args.dry_run,
        mock_tools=args.mock_tools,
        allow_reference_downloads=args.allow_reference_downloads,
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(json.dumps({"ok": summary["ok"], "summary": str(summary_path)}, sort_keys=True))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
