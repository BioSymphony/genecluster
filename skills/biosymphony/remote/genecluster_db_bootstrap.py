#!/usr/bin/env python3
"""Provider-side GeneCluster database bootstrap helper.

This script runs on the provider workdir, not in the local repo. It creates
cache directories, scope-gates database-ledger rows with the same run_gate
semantics used by the launch bundle and runner, and writes a small bootstrap
summary. Real execution is intentionally fail-closed: large/optional databases
are never downloaded here, and build commands only run for local provider-side
inputs that already exist.
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


TOOLCHECKS = {
    "blast": ["makeblastdb", "-version"],
    "blast_download": ["update_blastdb.pl", "--help"],
    "diamond": ["diamond", "version"],
    "hmmer": ["hmmpress", "-h"],
    "mmseqs": ["mmseqs", "version"],
}

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


def resolve_remote_path(value: str, *, run_id: str, heavy_workdir: Path | None = None) -> Path | None:
    resolved = value.replace("<run_id>", run_id)
    if not resolved or is_object_store_uri(resolved):
        return None
    if heavy_workdir and not str(heavy_workdir).startswith("/workspace/") and resolved.startswith("/workspace/genecluster/"):
        root = genecluster_root(heavy_workdir)
        return root / Path(resolved).relative_to("/workspace/genecluster")
    return Path(resolved)


def genecluster_root(heavy_workdir: Path) -> Path:
    heavy_str = str(heavy_workdir)
    if heavy_str.startswith("/workspace/"):
        return Path("/workspace/genecluster")
    if heavy_workdir.parent.name == "runs":
        return heavy_workdir.parent.parent
    return heavy_workdir.parent / "genecluster"


def ensure_provider_cache_dirs(heavy_workdir: Path, db_rows: list[dict[str, str]], *, run_id: str) -> dict[str, str]:
    root = genecluster_root(heavy_workdir)
    paths = {
        "root": root,
        "db_cache": root / "db-cache",
        "scratch": root / "scratch",
        "run": heavy_workdir,
        "inputs": heavy_workdir / "inputs",
        "databases": heavy_workdir / "databases",
        "logs": heavy_workdir / "logs",
        "summary": heavy_workdir / "summary",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    for row in db_rows:
        remote_path = resolve_remote_path(row.get("remote_path", ""), run_id=run_id, heavy_workdir=heavy_workdir)
        if remote_path is None:
            continue
        remote_path.parent.mkdir(parents=True, exist_ok=True)
    return {key: str(path) for key, path in paths.items()}


def database_row_enabled_for_scope(row: dict[str, str], run_scope: str) -> bool:
    gate = row.get("run_gate") or ("optional_max" if row.get("priority") == "optional_max" else "full_campaign")
    if run_scope == "full_campaign_24h":
        if gate == "candidate_search":
            return True
        if gate in {"full_campaign", "full_public_mining"}:
            return row.get("prep_roi") == "high" or (
                row.get("prep_roi") == "medium" and row.get("cost_class") in {"small", "medium"}
            )
        return False
    if gate == "candidate_search":
        return run_scope in {"candidate_search", "full_campaign", "full_public_mining", "full_campaign_24h"}
    if gate in {"full_campaign", "full_public_mining"}:
        return run_scope in {"full_campaign", "full_public_mining", "genome_context", "synteny", "coexpression"}
    return False


def db_present(db_path: Path, engine: str) -> bool:
    if engine == "blast":
        return db_path.exists() or any(db_path.parent.glob(f"{db_path.name}.*p*"))
    if engine == "diamond":
        return db_path.exists()
    if engine == "hmmer":
        return db_path.exists() and all(Path(f"{db_path}.{suffix}").exists() for suffix in ["h3f", "h3i", "h3m", "h3p"])
    if engine == "mmseqs":
        return db_path.exists() or Path(f"{db_path}.dbtype").exists()
    return db_path.exists()


def candidate_input_fasta(row: dict[str, str], seed_dir: Path) -> Path:
    db_id = row.get("db_id", "")
    sequence_type = row.get("sequence_type", "protein")
    suffix = ".fna" if sequence_type in {"nucleotide", "genome", "transcript"} else ".faa"
    return seed_dir / f"{db_id}{suffix}"


def tool_status(*, mock_tools: bool = False) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for engine, command in TOOLCHECKS.items():
        binary = command[0]
        found = shutil.which(binary)
        if mock_tools:
            records[engine] = {"status": "mocked", "binary": binary, "path": f"/mock/bin/{binary}"}
        elif found:
            records[engine] = {"status": "present", "binary": binary, "path": found}
        else:
            records[engine] = {"status": "missing", "binary": binary, "path": ""}
    return records


def build_command(row: dict[str, str], db_path: Path, input_fasta: Path) -> list[str]:
    engine = row.get("engine", "")
    sequence_type = row.get("sequence_type", "protein")
    dbtype = "nucl" if sequence_type in {"nucleotide", "genome", "transcript"} else "prot"
    if engine in {"blast", "custom", "mibig"}:
        return ["makeblastdb", "-in", str(input_fasta), "-dbtype", dbtype, "-out", str(db_path)]
    if engine == "diamond":
        return ["diamond", "makedb", "--in", str(input_fasta), "--db", str(db_path)]
    if engine == "mmseqs":
        return ["mmseqs", "createdb", str(input_fasta), str(db_path)]
    if engine == "hmmer":
        return ["hmmpress", str(db_path)]
    return []


def blast_preformatted_name(row: dict[str, str]) -> str:
    db_id = row.get("db_id", "")
    if db_id.startswith("blast_"):
        return db_id.replace("blast_", "", 1)
    source = row.get("source", "").lower()
    for name in ["swissprot", "refseq_protein", "taxdb", "nr", "nt"]:
        if name in source:
            return name
    return db_id


def build_preformatted_blast_command(row: dict[str, str], db_path: Path) -> list[str]:
    db_name = blast_preformatted_name(row)
    if not db_name:
        return []
    db_dir = db_path.parent
    return [
        "bash",
        "-lc",
        f"mkdir -p {sh_quote(str(db_dir))} && cd {sh_quote(str(db_dir))} && update_blastdb.pl --decompress {sh_quote(db_name)}",
    ]


def sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def plan_row(
    row: dict[str, str],
    *,
    run_scope: str,
    run_id: str,
    heavy_workdir: Path,
    seed_dir: Path,
    tools: dict[str, Any],
    allow_large_downloads: bool = False,
) -> dict[str, Any]:
    db_path = resolve_remote_path(row.get("remote_path", ""), run_id=run_id, heavy_workdir=heavy_workdir)
    engine = row.get("engine", "")
    priority = row.get("priority", "")
    cost_class = row.get("cost_class", "")
    enabled = database_row_enabled_for_scope(row, run_scope)
    present = bool(db_path and db_present(db_path, engine))
    input_fasta = candidate_input_fasta(row, seed_dir)
    command = build_command(row, db_path, input_fasta) if db_path else []
    tool_key = "blast" if engine in {"custom", "mibig"} else engine
    tool_ok = tools.get(tool_key, {}).get("status") in {"present", "mocked"}
    bootstrap_strategy = row.get("bootstrap_strategy", "")

    status = "skipped_scope"
    reason = "row not enabled for run_scope"
    if enabled and db_path is None:
        status = "blocked_object_store_adapter_unimplemented"
        reason = "database remote_path is not a mounted filesystem path"
    elif enabled and present:
        status = "present"
        reason = "database path already exists"
    elif enabled and priority == "optional_max":
        status = "blocked_optional_huge"
        reason = "optional maximum-tier databases require explicit external preload"
    elif enabled and cost_class == "huge":
        status = "blocked_huge"
        reason = "huge databases are fail-closed in bootstrap helper"
    elif enabled and cost_class == "large" and not allow_large_downloads:
        status = "blocked_large_download_requires_opt_in"
        reason = "large provider-side database downloads require --allow-large-downloads"
    elif enabled and bootstrap_strategy == "download_preformatted_blastdb":
        command = build_preformatted_blast_command(row, db_path)
        if not tools.get("blast_download", {}).get("status") in {"present", "mocked"}:
            status = "blocked_missing_tool"
            reason = "update_blastdb.pl is required for preformatted BLAST database download"
        elif command:
            status = "planned_download"
            reason = "safe provider-side preformatted BLAST database download command available"
        else:
            status = "blocked_preload_required"
            reason = "could not derive a preformatted BLAST database name"
    elif enabled and row.get("build_required", "").lower() == "true" and command:
        if not input_fasta.exists():
            status = "blocked_missing_provider_input"
            reason = f"provider-side seed FASTA not found: {input_fasta}"
        elif not tool_ok:
            status = "blocked_missing_tool"
            reason = f"required build tool missing for engine: {engine}"
        else:
            status = "planned_build"
            reason = "safe local provider-side build command available"
    elif enabled:
        status = "blocked_preload_required"
        reason = "ledger row requires provider preload; this helper does not download databases"

    return {
        "db_id": row.get("db_id", ""),
        "engine": engine,
        "sequence_type": row.get("sequence_type", ""),
        "priority": priority,
        "run_gate": row.get("run_gate", ""),
        "cost_class": cost_class,
        "prep_roi": row.get("prep_roi", ""),
        "bootstrap_strategy": row.get("bootstrap_strategy", ""),
        "enabled_for_scope": enabled,
        "remote_path": str(db_path) if db_path else row.get("remote_path", ""),
        "present": present,
        "input_fasta": str(input_fasta) if command else "",
        "command": command,
        "status": status,
        "reason": reason,
    }


def execute_builds(records: list[dict[str, Any]], *, dry_run: bool, mock_tools: bool) -> list[dict[str, Any]]:
    executed = []
    if dry_run or mock_tools:
        return executed
    for record in records:
        if record["status"] not in {"planned_build", "planned_download"}:
            continue
        command = [str(part) for part in record["command"]]
        try:
            proc = subprocess.run(command, check=False, capture_output=True, text=True, timeout=60 * 60)
        except (OSError, subprocess.TimeoutExpired) as exc:
            record["status"] = "failed"
            record["reason"] = f"build command failed to start or timed out: {exc}"
            executed.append({"db_id": record["db_id"], "command": command, "returncode": "", "error": str(exc)})
            continue
        completed_status = "downloaded" if record["status"] == "planned_download" else "built"
        record["status"] = completed_status if proc.returncode == 0 else "failed"
        record["reason"] = "provider command completed" if proc.returncode == 0 else "provider command returned non-zero"
        executed.append(
            {
                "db_id": record["db_id"],
                "command": command,
                "returncode": proc.returncode,
                "stdout_tail": proc.stdout[-2000:],
                "stderr_tail": proc.stderr[-2000:],
            }
        )
    return executed


def bootstrap_databases(
    *,
    launch_manifest: Path,
    out_dir: Path,
    seed_dir: Path | None,
    dry_run: bool,
    mock_tools: bool,
    allow_large_downloads: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(launch_manifest.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id", "unknown_run"))
    run_scope = str(manifest.get("run_scope", ""))
    heavy_workdir = Path(str(manifest.get("heavy_workdir") or out_dir.parent / "run"))
    database_ledger = resolve_ledger_path(manifest, "database_ledger", launch_manifest)
    db_rows = read_tsv(database_ledger)
    paths = ensure_provider_cache_dirs(heavy_workdir, db_rows, run_id=run_id)
    resolved_seed_dir = seed_dir or heavy_workdir / "inputs" / "db-seeds"
    tools = tool_status(mock_tools=mock_tools)
    records = [
        plan_row(
            row,
            run_scope=run_scope,
            run_id=run_id,
            heavy_workdir=heavy_workdir,
            seed_dir=resolved_seed_dir,
            tools=tools,
            allow_large_downloads=allow_large_downloads,
        )
        for row in db_rows
    ]
    executed = execute_builds(records, dry_run=dry_run, mock_tools=mock_tools)
    blocking = [
        item
        for item in records
        if item["enabled_for_scope"]
        and item["priority"] == "required"
        and item["status"] not in {"present", "built", "downloaded", "planned_build", "planned_download"}
    ]
    if not dry_run and not mock_tools:
        blocking = [
            item
            for item in records
            if item["enabled_for_scope"] and item["priority"] == "required" and item["status"] not in {"present", "built", "downloaded"}
        ]
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(launch_manifest),
        "database_ledger": str(database_ledger),
        "run_id": run_id,
        "run_scope": run_scope,
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "allow_large_downloads": allow_large_downloads,
        "created_paths": paths,
        "seed_dir": str(resolved_seed_dir),
        "tools": tools,
        "database_records": records,
        "executed": executed,
        "required_blockers": [{"db_id": item["db_id"], "status": item["status"], "reason": item["reason"]} for item in blocking],
        "ok": not blocking or mock_tools,
    }
    write_json(out_dir / "db-bootstrap-summary.json", summary)
    write_tsv(
        out_dir / "db-bootstrap-plan.tsv",
        ["db_id", "enabled_for_scope", "priority", "engine", "remote_path", "status", "reason"],
        records,
    )
    return summary


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    dry_run: bool = False,
    mock_tools: bool = False,
    allow_large_downloads: bool = False,
) -> Path:
    out_dir = out or launch_manifest.parent / "summary"
    bootstrap_databases(
        launch_manifest=launch_manifest,
        out_dir=out_dir,
        seed_dir=None,
        dry_run=dry_run,
        mock_tools=mock_tools,
        allow_large_downloads=allow_large_downloads,
    )
    return out_dir / "db-bootstrap-summary.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap provider-side GeneCluster database cache paths and safe local DB builds.")
    parser.add_argument("--launch-manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true", help="Plan only; do not execute provider-side build commands.")
    parser.add_argument("--mock-tools", action="store_true", help="Do not require real tools; never executes build commands.")
    parser.add_argument("--allow-large-downloads", action="store_true", help="Permit required large provider-side database downloads/builds.")
    args = parser.parse_args()

    summary_path = run(
        args.launch_manifest,
        args.out,
        dry_run=args.dry_run,
        mock_tools=args.mock_tools,
        allow_large_downloads=args.allow_large_downloads,
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    print(json.dumps({"ok": summary["ok"], "summary": str(summary_path)}, sort_keys=True))
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
