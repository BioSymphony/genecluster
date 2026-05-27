#!/usr/bin/env python3
"""Build or validate provider-side target datasets and search indexes.

This helper never downloads public data by itself. It consumes target resources
that are already present in the provider workdir/cache, then builds small search
indexes under provider storage only. In dry-run/mock mode it writes compact
summary ledgers so control-plane tests can validate the contract without raw
biological data.
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


RESOLVED_HEADERS = [
    "target_db_id",
    "dataset_id",
    "species",
    "resource_kind",
    "sequence_type",
    "source_path",
    "provider_path",
    "index_policy",
    "build_status",
    "checksum_status",
    "local_copy",
    "notes",
]

INDEX_HEADERS = [
    "target_db_id",
    "dataset_id",
    "engine",
    "sequence_type",
    "index_path",
    "source_path",
    "build_status",
    "command",
    "checksum_status",
]

OBJECT_STORE_PREFIXES = ("s3://", "r2://", "b2://", "gs://", "az://")


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


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def is_object_store_uri(value: str) -> bool:
    return value.startswith(OBJECT_STORE_PREFIXES)


def genecluster_root(heavy_workdir: Path) -> Path:
    heavy_str = str(heavy_workdir)
    if heavy_str.startswith("/workspace/"):
        return Path("/workspace/genecluster")
    if heavy_workdir.parent.name == "runs":
        return heavy_workdir.parent.parent
    return heavy_workdir.parent / "genecluster"


def resolve_provider_path(value: str, *, run_id: str, heavy_workdir: Path) -> Path | None:
    resolved = value.replace("<run_id>", run_id)
    if not resolved or is_object_store_uri(resolved):
        return None
    if not str(heavy_workdir).startswith("/workspace/") and resolved.startswith("/workspace/genecluster/runs/"):
        prefix = Path("/workspace/genecluster/runs") / run_id
        path = Path(resolved)
        try:
            return heavy_workdir / path.relative_to(prefix)
        except ValueError:
            return genecluster_root(heavy_workdir) / path.relative_to("/workspace/genecluster")
    if not str(heavy_workdir).startswith("/workspace/") and resolved.startswith("/workspace/genecluster/"):
        return genecluster_root(heavy_workdir) / Path(resolved).relative_to("/workspace/genecluster")
    return Path(resolved)


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


def load_plan(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    plan_path = resolve_manifest_path(str(manifest.get("target_db_plan", "target-db-plan.json")), manifest_path)
    if not plan_path.exists():
        return {"records": [], "index_targets": [], "missing_plan": str(plan_path)}
    return json.loads(plan_path.read_text(encoding="utf-8"))


def build_command(engine: str, sequence_type: str, source: Path, index_path: Path) -> list[str]:
    if engine == "blast":
        dbtype = "prot" if sequence_type == "protein" else "nucl"
        return ["makeblastdb", "-in", str(source), "-dbtype", dbtype, "-out", str(index_path)]
    if engine == "diamond":
        return ["diamond", "makedb", "--in", str(source), "--db", str(index_path)]
    if engine == "mmseqs":
        return ["mmseqs", "createdb", str(source), str(index_path)]
    if engine == "miniprot":
        return ["miniprot", "-d", str(index_path), str(source)]
    return []


def run_command(command: list[str]) -> tuple[str, str]:
    if not command:
        return "skipped_no_command", ""
    if shutil.which(command[0]) is None:
        return "blocked_missing_tool", command[0]
    proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=3600)
    if proc.returncode == 0:
        return "built", ""
    return "failed", (proc.stderr or proc.stdout).splitlines()[0][:240] if (proc.stderr or proc.stdout) else f"returncode={proc.returncode}"


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    dry_run: bool = False,
    mock_tools: bool = False,
) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id", "unknown_run"))
    heavy_workdir = Path(str(manifest.get("heavy_workdir") or manifest_path.parent / "genecluster-run"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = load_plan(manifest, manifest_path)

    resolved_rows: list[dict[str, Any]] = []
    index_rows: list[dict[str, Any]] = []
    blockers: list[str] = []

    for record in plan.get("records", []):
        provider_path = resolve_provider_path(str(record.get("provider_path", "")), run_id=run_id, heavy_workdir=heavy_workdir)
        source_path = resolve_provider_path(str(record.get("source_path", "")), run_id=run_id, heavy_workdir=heavy_workdir)
        if provider_path is not None:
            provider_path.mkdir(parents=True, exist_ok=True)
        source_present = bool(source_path and source_path.exists())
        build_required = str(record.get("build_required", "")).lower() == "true"
        build_status = "present" if source_present else ("mocked" if (dry_run or mock_tools) else "missing_source")
        if build_status == "missing_source" and not build_required:
            build_status = "deferred_source_not_required_for_this_scope"
        if build_status == "missing_source" and build_required:
            blockers.append(f"target source missing for {record.get('target_db_id')}: {source_path or record.get('source_path')}")
        resolved_rows.append(
            {
                "target_db_id": record.get("target_db_id", ""),
                "dataset_id": record.get("dataset_id", ""),
                "species": record.get("species", ""),
                "resource_kind": record.get("resource_kind", ""),
                "sequence_type": record.get("sequence_type", ""),
                "source_path": str(source_path) if source_path else record.get("source_path", ""),
                "provider_path": str(provider_path) if provider_path else record.get("provider_path", ""),
                "index_policy": record.get("index_policy", ""),
                "build_status": build_status,
                "checksum_status": record.get("checksum_status", "remote_pending"),
                "local_copy": "false",
                "notes": record.get("notes", ""),
            }
        )

    for item in plan.get("index_targets", []):
        index_path = resolve_provider_path(str(item.get("index_path", "")), run_id=run_id, heavy_workdir=heavy_workdir)
        source_path = resolve_provider_path(str(item.get("source_path", "")), run_id=run_id, heavy_workdir=heavy_workdir)
        if index_path is not None:
            index_path.parent.mkdir(parents=True, exist_ok=True)
        engine = str(item.get("engine", ""))
        sequence_type = str(item.get("sequence_type", ""))
        command = build_command(engine, sequence_type, source_path or Path("missing_source"), index_path or Path("missing_index"))
        if dry_run or mock_tools:
            build_status = "mocked"
            detail = ""
            if index_path is not None:
                write_text(index_path.with_suffix(index_path.suffix + ".mock" if index_path.suffix else ".mock"), "mock index marker\n")
        elif not source_path or not source_path.exists():
            build_status = "missing_source"
            detail = str(source_path or item.get("source_path", ""))
        else:
            build_status, detail = run_command(command)
        if build_status in {"missing_source", "blocked_missing_tool", "failed"}:
            blockers.append(f"{item.get('target_db_id')}:{engine}:{build_status}:{detail}")
        index_rows.append(
            {
                "target_db_id": item.get("target_db_id", ""),
                "dataset_id": item.get("dataset_id", ""),
                "engine": engine,
                "sequence_type": sequence_type,
                "index_path": str(index_path) if index_path else item.get("index_path", ""),
                "source_path": str(source_path) if source_path else item.get("source_path", ""),
                "build_status": build_status,
                "command": " ".join(command),
                "checksum_status": "remote_pending" if build_status not in {"built", "present"} else "not_applicable",
            }
        )

    write_tsv(out_dir / "target-db-ledger.resolved.tsv", RESOLVED_HEADERS, resolved_rows)
    write_tsv(out_dir / "target-db-indexes.tsv", INDEX_HEADERS, index_rows)
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(manifest_path),
        "target_db_plan": str(resolve_manifest_path(str(manifest.get("target_db_plan", "target-db-plan.json")), manifest_path)),
        "target_record_count": len(resolved_rows),
        "index_record_count": len(index_rows),
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "raw_sequence_emitted": False,
        "local_copy": False,
        "blockers": blockers,
        "ok": not blockers or dry_run or mock_tools,
    }
    write_json(out_dir / "target-db-build-summary.json", summary)
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build provider-side target DB indexes for GeneCluster.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    args = parser.parse_args()
    run(args.launch_manifest, args.out, dry_run=args.dry_run, mock_tools=args.mock_tools)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
