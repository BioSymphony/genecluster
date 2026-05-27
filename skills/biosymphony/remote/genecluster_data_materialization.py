#!/usr/bin/env python3
"""Materialize target datasets on provider storage for GeneCluster.

This helper is deliberately provider-side. It may fetch public SRA reads into
the configured heavy workdir/cache when explicitly allowed, converts
transcript-like FASTQ files into nucleotide FASTA, and leaves large artifacts on
the provider volume. It does not copy raw reads or large FASTA files into the
repo.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


MATERIALIZED_HEADERS = [
    "dataset_id",
    "accession",
    "run_id",
    "data_role",
    "organism",
    "materialization_status",
    "source_kind",
    "target_fasta",
    "fastq_dir",
    "read_count",
    "base_count",
    "command_summary",
    "review_status",
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


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def is_object_store_uri(value: str) -> bool:
    return value.startswith(OBJECT_STORE_PREFIXES)


def slug(value: str) -> str:
    keep = [char.lower() if char.isalnum() else "_" for char in value.strip()]
    return "_".join("".join(keep).split("_")).strip("_") or "dataset"


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    manifest_relative = manifest_path.parent / path
    if manifest_relative.exists():
        return manifest_relative
    return path


def resolve_ledger_path(manifest: dict[str, Any], key: str, manifest_path: Path) -> Path:
    value = str(manifest.get(key, ""))
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


def is_transcript_like(row: dict[str, str]) -> bool:
    lowered = f"{row.get('data_role', '')} {row.get('technology', '')}".lower()
    return any(token in lowered for token in ["transcript", "rna", "isoseq", "cdna"])


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def iter_fastq_records(path: Path) -> Iterable[tuple[str, str]]:
    with open_text(path) as handle:
        while True:
            name = handle.readline()
            if not name:
                break
            seq = handle.readline()
            plus = handle.readline()
            qual = handle.readline()
            if not qual:
                break
            if not name.startswith("@") or not plus.startswith("+"):
                continue
            yield name[1:].strip().split()[0], seq.strip()


def fastq_to_fasta(fastq_files: list[Path], fasta: Path, *, max_reads: int = 0) -> tuple[int, int]:
    fasta.parent.mkdir(parents=True, exist_ok=True)
    read_count = 0
    base_count = 0
    with fasta.open("w", encoding="utf-8") as out:
        for fastq in fastq_files:
            for name, seq in iter_fastq_records(fastq):
                if not seq:
                    continue
                read_count += 1
                base_count += len(seq)
                out.write(f">{fastq.stem}|{read_count}|{name}\n")
                for start in range(0, len(seq), 80):
                    out.write(seq[start:start + 80] + "\n")
                if max_reads and read_count >= max_reads:
                    return read_count, base_count
    return read_count, base_count


def run_command(command: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": "failed_to_start_or_timeout", "stderr_tail": str(exc)[-2000:]}
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def materialize_sra_row(
    row: dict[str, str],
    *,
    run_id: str,
    heavy_workdir: Path,
    allow_large_downloads: bool,
    dry_run: bool,
    mock_tools: bool,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    accession = row.get("run_id") or row.get("accession")
    dataset_id = row.get("dataset_id", "")
    dataset_slug = slug(dataset_id)
    sra_dir = heavy_workdir / "inputs" / "sra" / accession
    fastq_dir = heavy_workdir / "inputs" / "fastq" / dataset_slug
    target_dir = heavy_workdir / "inputs" / "target-sequences" / dataset_slug
    target_fasta = target_dir / "target_sequences.fasta"
    commands: list[dict[str, Any]] = []

    if not is_transcript_like(row):
        return (
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "run_id": row.get("run_id", ""),
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "materialization_status": "deferred_requires_assembly_or_existing_reference",
                "source_kind": "raw_non_transcript_or_genome",
                "target_fasta": "",
                "fastq_dir": str(fastq_dir),
                "read_count": "",
                "base_count": "",
                "command_summary": "genome/mixed raw reads are deferred from the first provider materializer",
                "review_status": "needs-human-review",
            },
            commands,
        )

    if target_fasta.exists():
        return (
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "run_id": row.get("run_id", ""),
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "materialization_status": "present",
                "source_kind": "provider_existing_target_fasta",
                "target_fasta": str(target_fasta),
                "fastq_dir": str(fastq_dir),
                "read_count": "",
                "base_count": "",
                "command_summary": "target FASTA already present",
                "review_status": "needs-human-review",
            },
            commands,
        )

    if dry_run or mock_tools:
        target_dir.mkdir(parents=True, exist_ok=True)
        write_text(target_fasta, f">{dataset_slug}_mock_read\nATGGCGGCGGCGTAA\n")
        return (
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "run_id": row.get("run_id", ""),
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "materialization_status": "mocked",
                "source_kind": "mock_target_fasta",
                "target_fasta": str(target_fasta),
                "fastq_dir": str(fastq_dir),
                "read_count": "1",
                "base_count": "15",
                "command_summary": "mock materialization",
                "review_status": "needs-human-review",
            },
            commands,
        )

    if not allow_large_downloads:
        return (
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "run_id": row.get("run_id", ""),
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "materialization_status": "blocked_requires_allow_large_downloads",
                "source_kind": "sra",
                "target_fasta": str(target_fasta),
                "fastq_dir": str(fastq_dir),
                "read_count": "",
                "base_count": "",
                "command_summary": "--allow-large-downloads is required for provider-side SRA materialization",
                "review_status": "needs-rerun",
            },
            commands,
        )

    for tool in ["prefetch", "fasterq-dump"]:
        if shutil.which(tool) is None:
            return (
                {
                    "dataset_id": dataset_id,
                    "accession": row.get("accession", ""),
                    "run_id": row.get("run_id", ""),
                    "data_role": row.get("data_role", ""),
                    "organism": row.get("organism", ""),
                    "materialization_status": "blocked_missing_tool",
                    "source_kind": "sra",
                    "target_fasta": str(target_fasta),
                    "fastq_dir": str(fastq_dir),
                    "read_count": "",
                    "base_count": "",
                    "command_summary": f"missing provider tool: {tool}",
                    "review_status": "needs-rerun",
                },
                commands,
            )

    sra_dir.mkdir(parents=True, exist_ok=True)
    fastq_dir.mkdir(parents=True, exist_ok=True)
    prefetch_result = run_command(["prefetch", accession, "-O", str(sra_dir)], timeout_seconds=timeout_seconds)
    commands.append(prefetch_result)
    if prefetch_result["returncode"] != 0:
        status = "failed_prefetch"
    else:
        sra_files = sorted(sra_dir.rglob("*.sra"))
        dump_input = str(sra_files[0]) if sra_files else accession
        threads = os.environ.get("GENECLUSTER_FASTQ_THREADS", "4")
        fasterq_result = run_command(["fasterq-dump", dump_input, "-O", str(fastq_dir), "--split-files", "--threads", threads], timeout_seconds=timeout_seconds)
        commands.append(fasterq_result)
        status = "failed_fasterq_dump" if fasterq_result["returncode"] != 0 else "fastq_materialized"

    if status != "fastq_materialized":
        return (
            {
                "dataset_id": dataset_id,
                "accession": row.get("accession", ""),
                "run_id": row.get("run_id", ""),
                "data_role": row.get("data_role", ""),
                "organism": row.get("organism", ""),
                "materialization_status": status,
                "source_kind": "sra",
                "target_fasta": str(target_fasta),
                "fastq_dir": str(fastq_dir),
                "read_count": "",
                "base_count": "",
                "command_summary": ";".join(str(item.get("returncode")) for item in commands),
                "review_status": "needs-rerun",
            },
            commands,
        )

    fastq_files = sorted(list(fastq_dir.glob("*.fastq")) + list(fastq_dir.glob("*.fastq.gz")))
    max_reads = int(os.environ.get("GENECLUSTER_FASTQ_TO_FASTA_MAX_READS", "0") or "0")
    read_count, base_count = fastq_to_fasta(fastq_files, target_fasta, max_reads=max_reads)
    status = "target_fasta_materialized" if read_count else "failed_no_fastq_records"
    return (
        {
            "dataset_id": dataset_id,
            "accession": row.get("accession", ""),
            "run_id": row.get("run_id", ""),
            "data_role": row.get("data_role", ""),
            "organism": row.get("organism", ""),
            "materialization_status": status,
            "source_kind": "sra_transcript_reads",
            "target_fasta": str(target_fasta) if read_count else "",
            "fastq_dir": str(fastq_dir),
            "read_count": str(read_count),
            "base_count": str(base_count),
            "command_summary": ";".join(str(item.get("returncode")) for item in commands),
            "review_status": "needs-human-review" if read_count else "needs-rerun",
        },
        commands,
    )


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    dry_run: bool = False,
    mock_tools: bool = False,
    allow_large_downloads: bool = False,
    timeout_seconds: int = 21600,
) -> Path:
    manifest_path = launch_manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id", "unknown_run"))
    heavy_workdir = Path(str(manifest.get("heavy_workdir") or manifest_path.parent / "genecluster-run"))
    out_dir = output_dir_for_manifest(manifest, manifest_path, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_ledger = resolve_ledger_path(manifest, "data_ledger", manifest_path)
    data_rows = read_tsv(data_ledger)

    rows: list[dict[str, Any]] = []
    command_log: list[dict[str, Any]] = []
    blockers: list[str] = []
    for row in data_rows:
        accession = row.get("accession", "")
        if not accession.startswith(("SRX", "SRR", "ERR", "ERX", "DRR", "DRX")):
            continue
        materialized, commands = materialize_sra_row(
            row,
            run_id=run_id,
            heavy_workdir=heavy_workdir,
            allow_large_downloads=allow_large_downloads,
            dry_run=dry_run,
            mock_tools=mock_tools,
            timeout_seconds=timeout_seconds,
        )
        rows.append(materialized)
        command_log.extend({"dataset_id": row.get("dataset_id", ""), **item} for item in commands)
        if str(materialized["materialization_status"]).startswith(("blocked", "failed")):
            blockers.append(f"{materialized['dataset_id']}:{materialized['materialization_status']}")

    write_tsv(out_dir / "materialized-targets.tsv", MATERIALIZED_HEADERS, rows)
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "launch_manifest": str(manifest_path),
        "data_ledger": str(data_ledger),
        "run_id": run_id,
        "dry_run": dry_run,
        "mock_tools": mock_tools,
        "allow_large_downloads": allow_large_downloads,
        "materialized_count": sum(1 for row in rows if row["materialization_status"] in {"present", "mocked", "target_fasta_materialized"}),
        "deferred_count": sum(1 for row in rows if str(row["materialization_status"]).startswith("deferred")),
        "blockers": blockers,
        "commands": command_log,
        "raw_artifacts_policy": "provider_workdir_only",
        "local_copy": False,
        "ok": not blockers and any(row["target_fasta"] for row in rows),
    }
    write_json(out_dir / "data-materialization-summary.json", summary)
    if blockers and not (dry_run or mock_tools):
        raise SystemExit(2)
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize provider-side target datasets for GeneCluster.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock-tools", action="store_true")
    parser.add_argument("--allow-large-downloads", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=21600)
    args = parser.parse_args()
    run(
        args.launch_manifest,
        args.out,
        dry_run=args.dry_run,
        mock_tools=args.mock_tools,
        allow_large_downloads=args.allow_large_downloads,
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
