#!/usr/bin/env python3
"""Provider-side GeneCluster runner.

The runner is designed for RunPod or another configured heavy workdir. It never
downloads raw sequence data into the local repo. Real search execution is
fail-closed: if required query FASTA files or provider-side databases are not
present, it writes blocked summaries instead of falling back to remote web
services.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_HEADERS = [
    "candidate_id",
    "query_id",
    "gene_or_transcript_id",
    "dataset_id",
    "source_species",
    "target_species",
    "search_direction",
    "target_db_id",
    "hit_type",
    "pct_identity",
    "coverage",
    "evalue",
    "domain_calls",
    "pathway_role",
    "evidence_score",
    "review_status",
    "pathway_step_id",
    "novelty_status",
    "novelty_basis",
    "closest_characterized_identity",
    "dedupe_group",
    "representative_id",
    "duplicate_class",
    "duplicate_confidence",
    "splice_variant_status",
    "partial_status",
    "dedupe_rationale",
    "query_coverage",
    "target_coverage",
    "bitscore",
    "reciprocal_rank",
    "reciprocal_best_hit",
    "anchor_method",
    "anchor_confidence",
    "coordinate_confidence",
    "orthogroup_id",
    "paralog_flag",
    "isoform_group",
    "domain_architecture",
    "catalytic_motif_status",
    "subcellular_prediction",
    "transmembrane_prediction",
    "expression_tpm",
    "coexpression_module",
    "genome_locus",
    "synteny_block_id",
    "neighborhood_cluster_id",
    "product_claim_level",
    "evidence_weights_json",
]

TOOLCHECKS = {
    "blastp": ["blastp", "-version"],
    "tblastn": ["tblastn", "-version"],
    "blastdbcmd": ["blastdbcmd", "-version"],
    "makeblastdb": ["makeblastdb", "-version"],
    "update_blastdb.pl": ["update_blastdb.pl", "--help"],
    "diamond": ["diamond", "version"],
    "mmseqs": ["mmseqs", "version"],
    "hmmsearch": ["hmmsearch", "-h"],
    "hmmscan": ["hmmscan", "-h"],
    "hmmpress": ["hmmpress", "-h"],
    "miniprot": ["miniprot", "--version"],
    "datasets": ["datasets", "version"],
    "prefetch": ["prefetch", "--version"],
    "fasterq-dump": ["fasterq-dump", "--version"],
    "minimap2": ["minimap2", "--version"],
    "nextflow": ["nextflow", "-version"],
}

OBJECT_STORE_PREFIXES = ("s3://", "r2://", "b2://", "gs://", "az://")


def is_object_store_uri(value: str) -> bool:
    return value.startswith(OBJECT_STORE_PREFIXES)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeBudget:
    def __init__(self, max_runtime_hours: float | None) -> None:
        self.max_runtime_hours = max_runtime_hours
        self.started_monotonic = time.monotonic()
        self.events: list[dict[str, Any]] = []

    @property
    def enabled(self) -> bool:
        return self.max_runtime_hours is not None and self.max_runtime_hours > 0

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_monotonic

    def remaining_seconds(self) -> float | None:
        if not self.enabled:
            return None
        return max(0.0, self.max_runtime_hours * 3600.0 - self.elapsed_seconds())

    def can_start(self, stage: str, *, reserve_seconds: int = 60) -> bool:
        remaining = self.remaining_seconds()
        if remaining is None or remaining > reserve_seconds:
            return True
        self.events.append(
            {
                "stage": stage,
                "status": "skipped_runtime_budget_exhausted",
                "remaining_seconds": round(remaining, 3),
                "created_at": utc_now(),
            }
        )
        return False

    def command_timeout(self, *, default_seconds: int = 3600) -> int | None:
        remaining = self.remaining_seconds()
        if remaining is None:
            return default_seconds
        return max(1, int(min(float(default_seconds), remaining)))

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "max_runtime_hours": self.max_runtime_hours,
            "elapsed_seconds": round(self.elapsed_seconds(), 3),
            "remaining_seconds": self.remaining_seconds(),
            "events": self.events,
        }


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, data: dict[str, Any]) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def append_stage_progress(out_dir: Path, stage_id: str, status: str, **details: Any) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "stage_id": stage_id,
        "status": status,
        "timestamp": utc_now(),
        **details,
    }
    with (out_dir / "stage-progress.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


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


def write_tsv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


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


def ensure_remote_layout(heavy_workdir: Path) -> dict[str, Path]:
    root = genecluster_root(heavy_workdir)
    paths = {
        "root": root,
        "db_cache": root / "db-cache",
        "search_cache": root / "search-cache",
        "runs": root / "runs",
        "nextflow_cache": root / "nextflow-cache",
        "scratch": root / "scratch",
        "run": heavy_workdir,
        "inputs": heavy_workdir / "inputs",
        "work": heavy_workdir / "work",
        "databases": heavy_workdir / "databases",
        "logs": heavy_workdir / "logs",
        "summary": heavy_workdir / "summary",
        "nextflow_work": heavy_workdir / "nextflow-work",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def check_tools(*, mock_tools: bool = False) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for tool, version_cmd in TOOLCHECKS.items():
        found = shutil.which(tool)
        if mock_tools:
            records[tool] = {"status": "mocked", "path": f"/mock/bin/{tool}", "version": "mock"}
            continue
        if not found:
            records[tool] = {"status": "missing", "path": "", "version": ""}
            continue
        version = ""
        try:
            proc = subprocess.run(version_cmd, check=False, capture_output=True, text=True, timeout=15)
            version = (proc.stdout or proc.stderr).splitlines()[0][:200] if (proc.stdout or proc.stderr) else "present"
        except (OSError, subprocess.TimeoutExpired) as exc:
            version = f"version_check_failed: {exc}"
        records[tool] = {"status": "present", "path": found, "version": version}
    return {
        "schema_version": 1,
        "checked_at": utc_now(),
        "tools": records,
        "ok": all(item["status"] in {"present", "mocked"} for item in records.values()),
    }


def cache_preflight(manifest: dict[str, Any], manifest_path: Path, paths: dict[str, Path], *, mock_tools: bool = False) -> dict[str, Any]:
    database_ledger = resolve_manifest_path(str(manifest["database_ledger"]), manifest_path)
    cache_ledger = resolve_manifest_path(str(manifest["cache_ledger"]), manifest_path)
    db_rows = read_tsv(database_ledger)
    cache_rows = read_tsv(cache_ledger)
    db_records: list[dict[str, Any]] = []
    for row in db_rows:
        enabled = database_row_enabled_for_scope(row, str(manifest.get("run_scope", "")))
        remote_path = resolve_provider_path(
            row["remote_path"],
            run_id=str(manifest.get("run_id", "unknown_run")),
            heavy_workdir=paths["run"],
        )
        present = bool(remote_path and remote_path.exists())
        status = "present" if present else ("mocked" if mock_tools else "missing")
        if remote_path is None:
            status = "blocked_unsupported_uri"
        db_records.append(
            {
                "db_id": row["db_id"],
                "engine": row["engine"],
                "priority": row["priority"],
                "run_gate": row.get("run_gate", ""),
                "cost_class": row.get("cost_class", ""),
                "prep_roi": row.get("prep_roi", ""),
                "enabled_for_scope": enabled,
                "remote_path": str(remote_path) if remote_path else row["remote_path"],
                "present": present,
                "status": status,
            }
        )
    usage = shutil.disk_usage(paths["root"])
    required_missing = [
        item["db_id"]
        for item in db_records
        if item["priority"] == "required" and item["enabled_for_scope"] and item["status"] == "missing"
    ]
    return {
        "schema_version": 1,
        "checked_at": utc_now(),
        "database_ledger": str(database_ledger),
        "cache_ledger": str(cache_ledger),
        "created_paths": {key: str(path) for key, path in paths.items()},
        "disk_free_gb": round(usage.free / (1024**3), 3),
        "database_records": db_records,
        "cache_roles": [row.get("cache_role", "") for row in cache_rows],
        "required_databases_missing": required_missing,
        "ok": not required_missing or mock_tools,
    }


def load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": 1,
            "checked_at": utc_now(),
            "ok": False,
            "blockers": [f"summary not found: {path}"],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def run_provider_helper(
    module_name: str,
    summary_name: str,
    launch_manifest: Path,
    out_dir: Path,
    *,
    dry_run: bool,
    mock_tools: bool,
    extra_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra_kwargs = extra_kwargs or {}
    try:
        module = __import__(module_name)
    except ImportError as exc:
        summary = {
            "schema_version": 1,
            "checked_at": utc_now(),
            "ok": False,
            "blockers": [f"provider helper import failed: {module_name}: {exc}"],
            "module": module_name,
        }
        write_json(out_dir / summary_name, summary)
        return summary

    try:
        module.run(launch_manifest, out_dir, dry_run=dry_run, mock_tools=mock_tools, **extra_kwargs)
    except SystemExit as exc:
        summary = load_summary(out_dir / summary_name)
        summary.setdefault("blockers", []).append(f"helper exited with status {exc.code}")
        summary["ok"] = False
        write_json(out_dir / summary_name, summary)
        return summary
    return load_summary(out_dir / summary_name)


def write_mock_genome_context(paths: dict[str, Path]) -> Path:
    gff = paths["inputs"] / "mock-reference.gff3"
    if gff.exists():
        return gff
    write_text(
        gff,
        "##gff-version 3\n"
        "mock_contig\tGeneCluster\tgene\t10000\t11800\t.\t+\t.\tID=mock_provider_DCS_like_001;Name=mock_provider_DCS_like_001;product=mock DCS-like candidate\n"
        "mock_contig\tGeneCluster\tgene\t7000\t7900\t.\t+\t.\tID=mock_neighbor_omt;Name=mock_neighbor_omt;product=mock O-methyltransferase-like protein\n"
        "mock_contig\tGeneCluster\tgene\t12250\t13700\t.\t-\t.\tID=mock_neighbor_cyp;Name=mock_neighbor_cyp;product=mock cytochrome P450-like protein\n",
    )
    return gff


def query_fasta_path(paths: dict[str, Path]) -> Path:
    return paths["inputs"] / "queries" / "protein_queries.faa"


def split_accession_tokens(value: str) -> list[dict[str, str]]:
    records = []
    for token in value.replace(",", ";").split(";"):
        token = token.strip()
        if not token or token == "remote_resolve_required":
            continue
        if ":" in token:
            kind, accession = token.split(":", 1)
            kind = kind.strip().lower()
            accession = accession.strip()
        else:
            kind = "unknown"
            accession = token
        if not accession:
            continue
        records.append({"kind": kind, "accession": accession})
    return records


def protein_accessions_for_record(record: dict[str, Any]) -> list[str]:
    accessions = []
    for item in split_accession_tokens(str(record.get("resolved_accession", ""))):
        kind = item["kind"]
        accession = item["accession"]
        if kind in {"protein", "partial_protein"}:
            accessions.append(accession)
        elif kind == "unknown" and not accession.startswith(("OQ", "PV", "SRX", "SRR")):
            accessions.append(accession)
    return accessions


def build_efetch_url(db: str, ids: list[str]) -> str:
    params = {
        "db": db,
        "id": ",".join(ids),
        "rettype": "fasta",
        "retmode": "text",
    }
    api_key = os.environ.get("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(params)


def default_fetcher(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "BioSymphony-GeneCluster/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - public NCBI FASTA fetch on provider only.
        return response.read().decode("utf-8", errors="replace")


def normalize_fasta_headers(text: str, *, query_id_by_accession: dict[str, dict[str, str]]) -> str:
    output_lines = []
    current_accession = ""
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith(">"):
            first = line[1:].split()[0]
            current_accession = first.split("|")[-1] if "|" in first else first
            meta = query_id_by_accession.get(current_accession, {})
            query_id = meta.get("query_id", "unmapped_query")
            query_name = meta.get("query_name", "unmapped")
            output_lines.append(f">{query_id}|{query_name}|{current_accession} {line[1:]}")
        elif current_accession:
            output_lines.append(line.strip())
    return "\n".join(output_lines) + ("\n" if output_lines else "")


def resolve_query_fasta_from_plan(
    plan: dict[str, Any],
    output_fasta: Path,
    *,
    fetcher: Any = None,
) -> dict[str, Any]:
    fetcher = fetcher or default_fetcher
    query_id_by_accession: dict[str, dict[str, str]] = {}
    for record in plan.get("records", []):
        if record.get("resolution_action") != "fetch_public_accession":
            continue
        for accession in protein_accessions_for_record(record):
            query_id_by_accession[accession] = {
                "query_id": str(record.get("query_id", "")),
                "query_name": str(record.get("query_name", "")),
            }
    accessions = sorted(query_id_by_accession)
    if not accessions:
        return {
            "attempted": False,
            "resolved_count": 0,
            "failed_accessions": [],
            "message": "no protein accessions available for provider-side FASTA resolution",
        }

    fetched_chunks = []
    failed = []
    for start in range(0, len(accessions), 50):
        batch = accessions[start : start + 50]
        url = build_efetch_url("protein", batch)
        try:
            fetched_chunks.append(fetcher(url))
        except Exception as exc:  # noqa: BLE001 - provider summary should capture all resolver failures.
            failed.extend(batch)
            fetched_chunks.append(f"")
            write_text(output_fasta.parent / "query-fetch-last-error.txt", str(exc))
    normalized = normalize_fasta_headers("\n".join(fetched_chunks), query_id_by_accession=query_id_by_accession)
    output_fasta.parent.mkdir(parents=True, exist_ok=True)
    if normalized:
        write_text(output_fasta, normalized)
    return {
        "attempted": True,
        "requested_count": len(accessions),
        "resolved_count": normalized.count(">"),
        "failed_accessions": failed,
        "output_fasta": str(output_fasta),
        "output_sha256": sha256_file(output_fasta) if output_fasta.exists() else "",
    }


def query_preflight(
    manifest: dict[str, Any],
    manifest_path: Path,
    paths: dict[str, Path],
    *,
    mock_tools: bool = False,
    resolve_queries: bool = False,
    fetcher: Any = None,
) -> dict[str, Any]:
    query_plan_path = resolve_manifest_path(str(manifest.get("query_resolution_plan", "")), manifest_path)
    plan = json.loads(query_plan_path.read_text(encoding="utf-8")) if query_plan_path.exists() else {}
    q_fasta = query_fasta_path(paths)
    resolver_summary = None
    embedded_query_value = str(plan.get("embedded_query_fasta") or manifest.get("query_fasta") or "")
    if embedded_query_value and not q_fasta.exists():
        embedded_query_path = resolve_manifest_path(embedded_query_value, manifest_path)
        if embedded_query_path.exists():
            q_fasta.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(embedded_query_path, q_fasta)
    if resolve_queries and not mock_tools and not q_fasta.exists():
        resolver_summary = resolve_query_fasta_from_plan(plan, q_fasta, fetcher=fetcher)
    if mock_tools and not q_fasta.exists():
        q_fasta.parent.mkdir(parents=True, exist_ok=True)
        write_text(q_fasta, ">Q004_mock_anchor\nMSTNPKPQRMockSequenceForDryRunOnly\n")
    blockers = plan.get("blocking_unresolved_query_ids", [])
    return {
        "schema_version": 1,
        "checked_at": utc_now(),
        "query_resolution_plan": str(query_plan_path),
        "query_fasta": str(q_fasta),
        "query_fasta_present": q_fasta.exists(),
        "query_fasta_sha256": sha256_file(q_fasta) if q_fasta.exists() else "",
        "resolver_summary": resolver_summary,
        "blocking_unresolved_query_ids": blockers,
        "records": plan.get("records", []),
        "ok": q_fasta.exists() and (not blockers or mock_tools),
    }


def decoy_preflight(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    decoy_plan_path = resolve_manifest_path(str(manifest.get("decoy_plan", "")), manifest_path)
    plan = json.loads(decoy_plan_path.read_text(encoding="utf-8")) if decoy_plan_path.exists() else {}
    records = plan.get("records", []) if isinstance(plan.get("records", []), list) else []
    missing_controls = plan.get("missing_negative_control_query_ids", [])
    return {
        "schema_version": 1,
        "checked_at": utc_now(),
        "decoy_plan": str(decoy_plan_path),
        "record_count": len(records),
        "broad_family_query_ids": plan.get("broad_family_query_ids", []),
        "high_false_positive_risk_query_ids": plan.get("high_false_positive_risk_query_ids", []),
        "missing_negative_control_query_ids": missing_controls,
        "enforcement": plan.get("enforcement", {}),
        "ok": not missing_controls,
    }


def search_cache_key(*, query_fasta: Path, db_id: str, db_path: str, engine: str, tool_version: str = "unknown") -> str:
    query_hash = sha256_file(query_fasta) if query_fasta.exists() else "missing_query"
    payload = {
        "query_sha256": query_hash,
        "db_id": db_id,
        "db_path": db_path,
        "engine": engine,
        "tool_version": tool_version,
    }
    return sha256_text(json.dumps(payload, sort_keys=True))


def command_plan(manifest: dict[str, Any], manifest_path: Path, paths: dict[str, Path], out_dir: Path) -> dict[str, Any]:
    database_ledger = resolve_manifest_path(str(manifest["database_ledger"]), manifest_path)
    rows = read_tsv(database_ledger)
    q_fasta = query_fasta_path(paths)
    planned_commands = []
    for row in rows:
        if row.get("priority") != "required" or not database_row_enabled_for_scope(row, str(manifest.get("run_scope", ""))):
            continue
        engine = row["engine"]
        db_path_obj = resolve_provider_path(
            row["remote_path"],
            run_id=str(manifest.get("run_id", "unknown_run")),
            heavy_workdir=paths["run"],
        )
        db_path = str(db_path_obj) if db_path_obj is not None else row["remote_path"]
        raw_out = paths["work"] / "search" / f"{row['db_id']}.outfmt6"
        command_steps: list[list[str]]
        db_path_status = "filesystem" if db_path_obj is not None else "unsupported_uri"
        if engine == "blast":
            cmd = ["blastp", "-db", db_path, "-query", str(q_fasta), "-out", str(raw_out), "-outfmt", "6", "-max_target_seqs", "50"]
            command_steps = [cmd]
        elif engine == "diamond":
            cmd = ["diamond", "blastp", "--db", db_path, "--query", str(q_fasta), "--out", str(raw_out), "--outfmt", "6", "--max-target-seqs", "50"]
            command_steps = [cmd]
        elif engine == "hmmer":
            raw_out = paths["work"] / "search" / f"{row['db_id']}.domtblout"
            cmd = ["hmmscan", "--domtblout", str(raw_out), db_path, str(q_fasta)]
            command_steps = [cmd]
        elif engine == "mmseqs":
            raw_out = paths["work"] / "search" / f"{row['db_id']}.m8"
            query_db = paths["work"] / "mmseqs_query"
            result_db = paths["work"] / row["db_id"]
            tmp_dir = paths["scratch"] / f"mmseqs_{row['db_id']}"
            cmd = ["mmseqs", "search", str(query_db), db_path, str(result_db), str(tmp_dir)]
            command_steps = [
                ["mmseqs", "createdb", str(q_fasta), str(query_db)],
                cmd,
                ["mmseqs", "convertalis", str(query_db), db_path, str(result_db), str(raw_out)],
            ]
        else:
            continue
        cache_key = search_cache_key(query_fasta=q_fasta, db_id=row["db_id"], db_path=db_path, engine=engine)
        cache_path = paths["search_cache"] / f"{cache_key}.{raw_out.name}"
        planned_commands.append(
            {
                "db_id": row["db_id"],
                "dataset_id": row.get("db_id", ""),
                "engine": engine,
                "priority": row.get("priority", ""),
                "enabled_for_scope": True,
                "command": cmd,
                "commands": command_steps,
                "db_path": db_path,
                "db_path_status": db_path_status,
                "raw_out": str(raw_out),
                "cache_key": cache_key,
                "cache_path": str(cache_path),
                "hit_type": "protein_hit",
                "target_species": "reference_database",
            }
        )
    target_indexes = out_dir / "target-db-indexes.tsv"
    if target_indexes.exists():
        for row in read_tsv(target_indexes):
            if row.get("build_status") not in {"built", "present"}:
                continue
            if row.get("engine") != "blast" or row.get("sequence_type") not in {"nucleotide", "genome"}:
                continue
            db_path = row.get("index_path", "")
            raw_out = paths["work"] / "search" / f"{row['target_db_id']}.tblastn.outfmt6"
            cmd = ["tblastn", "-db", db_path, "-query", str(q_fasta), "-out", str(raw_out), "-outfmt", "6", "-max_target_seqs", "50"]
            cache_key = search_cache_key(query_fasta=q_fasta, db_id=row["target_db_id"], db_path=db_path, engine="tblastn")
            cache_path = paths["search_cache"] / f"{cache_key}.{raw_out.name}"
            planned_commands.append(
                {
                    "db_id": row["target_db_id"],
                    "dataset_id": row.get("dataset_id", row["target_db_id"]),
                    "engine": "tblastn",
                    "priority": "required",
                    "enabled_for_scope": True,
                    "command": cmd,
                    "commands": [cmd],
                    "db_path": db_path,
                    "db_path_status": "filesystem",
                    "raw_out": str(raw_out),
                    "cache_key": cache_key,
                    "cache_path": str(cache_path),
                    "hit_type": "transcript_hit",
                    "target_species": "target_discovery_species",
                }
            )
    return {
        "schema_version": 1,
        "query_fasta": str(q_fasta),
        "commands": planned_commands,
        "forbidden_remote_blast": True,
    }


def parse_outfmt6(
    path: Path,
    *,
    max_rows: int = 10000,
    max_per_query: int = 50,
    dataset_id: str = "provider_search",
    target_db_id: str = "provider_search",
    hit_type: str = "protein_hit",
    target_species: str = "target_discovery_species",
) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows = []
    per_query_counts: dict[str, int] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for index, line in enumerate(handle, start=1):
            if index > max_rows:
                break
            qseqid_peek = line.split("\t", 1)[0] if "\t" in line else ""
            if qseqid_peek and per_query_counts.get(qseqid_peek, 0) >= max_per_query:
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 12:
                continue
            qseqid, sseqid, pident, length, _mismatch, _gapopen, _qstart, _qend, _sstart, _send, evalue, bitscore = parts[:12]
            candidate_id = f"GCAND_{sha256_text(target_db_id)[:8].upper()}_{index:05d}"
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "query_id": qseqid,
                    "gene_or_transcript_id": sseqid,
                    "dataset_id": dataset_id,
                    "source_species": "canonical_source_species",
                    "target_species": target_species,
                    "search_direction": "canonical_A_to_target_B",
                    "target_db_id": target_db_id,
                    "hit_type": hit_type,
                    "pct_identity": pident,
                    "coverage": "remote_pending",
                    "evalue": evalue,
                    "domain_calls": "remote_pending",
                    "pathway_role": "remote_search_hit",
                    "evidence_score": "0.50",
                    "review_status": "needs-human-review",
                    "pathway_step_id": "STEP_DCS",
                    "novelty_status": "not_assessed",
                    "novelty_basis": "Provider search hit requires downstream domain/phylogeny review.",
                    "closest_characterized_identity": pident,
                    "dedupe_group": "remote_pending",
                    "representative_id": candidate_id,
                    "duplicate_class": "unknown",
                    "duplicate_confidence": "not_assessed",
                    "splice_variant_status": "not_assessed",
                    "partial_status": "unknown",
                    "dedupe_rationale": "Not deduplicated in first search parse.",
                    "query_coverage": "remote_pending",
                    "target_coverage": "remote_pending",
                    "bitscore": bitscore,
                    "reciprocal_rank": "remote_pending",
                    "reciprocal_best_hit": "remote_pending",
                    "anchor_method": "unanchored",
                    "anchor_confidence": "unanchored",
                    "coordinate_confidence": "none",
                    "orthogroup_id": "remote_pending",
                    "paralog_flag": "review_required",
                    "isoform_group": "remote_pending",
                    "domain_architecture": "remote_pending",
                    "catalytic_motif_status": "remote_pending",
                    "subcellular_prediction": "remote_pending",
                    "transmembrane_prediction": "remote_pending",
                    "expression_tpm": "remote_pending",
                    "coexpression_module": "remote_pending",
                    "genome_locus": "remote_pending",
                    "synteny_block_id": "remote_pending",
                    "neighborhood_cluster_id": "remote_pending",
                    "product_claim_level": "candidate",
                    "evidence_weights_json": json.dumps({"homology": 0.5}),
                }
            )
            per_query_counts[qseqid] = per_query_counts.get(qseqid, 0) + 1
    return rows


def mock_candidate_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "GCAND_MOCK_0001",
            "query_id": "Q004",
            "gene_or_transcript_id": "mock_provider_DCS_like_001",
            "dataset_id": "mock_provider_summary",
            "source_species": "source species A public seeds",
            "target_species": "target species B",
            "search_direction": "canonical_A_to_target_B",
            "target_db_id": "target_mock_provider_summary",
            "hit_type": "transcript_hit",
            "pct_identity": "80.0",
            "coverage": "0.90",
            "evalue": "1e-80",
            "domain_calls": "MDR;ADH_N",
            "pathway_role": "an_intermediate-biased branch",
            "evidence_score": "0.75",
            "review_status": "needs-human-review",
            "pathway_step_id": "STEP_DCS",
            "novelty_status": "known_family_candidate",
            "novelty_basis": "Mocked provider-side search summary for dry-run validation.",
            "closest_characterized_identity": "80.0",
            "dedupe_group": "MOCK_DCS_GRP_001",
            "representative_id": "GCAND_MOCK_0001",
            "duplicate_class": "representative",
            "duplicate_confidence": "medium",
            "splice_variant_status": "isoform_pending",
            "partial_status": "complete_orf_pending",
            "dedupe_rationale": "Mocked dedupe placeholder for runner validation only.",
            "query_coverage": "0.91",
            "target_coverage": "0.90",
            "bitscore": "300",
            "reciprocal_rank": "1",
            "reciprocal_best_hit": "yes",
            "anchor_method": "transcript_to_genome",
            "anchor_confidence": "transcript_to_genome",
            "coordinate_confidence": "low",
            "orthogroup_id": "remote_pending",
            "paralog_flag": "review_required",
            "isoform_group": "mock_isoform_group",
            "domain_architecture": "MDR;ADH_N;NAD_binding",
            "catalytic_motif_status": "pending_review",
            "subcellular_prediction": "cytosol_candidate",
            "transmembrane_prediction": "no_TM_predicted",
            "expression_tpm": "remote_pending",
            "coexpression_module": "remote_pending",
            "genome_locus": "transcript_only",
            "synteny_block_id": "remote_pending",
            "neighborhood_cluster_id": "remote_pending",
            "product_claim_level": "candidate",
            "evidence_weights_json": json.dumps({"homology": 0.4, "domain": 0.2, "review": 0.15}),
        }
    ]


def search_db_exists(engine: str, db_path: Path) -> bool:
    if db_path.exists():
        return True
    if engine in {"blast", "tblastn"}:
        return any(db_path.with_suffix(suffix).exists() for suffix in [".pin", ".psq", ".phr", ".nin", ".nsq", ".nhr"])
    if engine == "diamond":
        return db_path.with_suffix(".dmnd").exists()
    if engine == "mmseqs":
        return db_path.with_suffix(".dbtype").exists() or any(db_path.parent.glob(db_path.name + "*"))
    return False


def real_target_db_id(value: str) -> bool:
    return value.startswith("target_") and not value.startswith("target_mock")


def placeholder_candidate(row: dict[str, Any]) -> bool:
    candidate_id = str(row.get("candidate_id", ""))
    dataset_id = str(row.get("dataset_id", ""))
    target_db_id = str(row.get("target_db_id", ""))
    gene_id = str(row.get("gene_or_transcript_id", ""))
    return (
        candidate_id.startswith("GCAND_MOCK")
        or dataset_id in {"provider_search", "mock_provider_summary"}
        or target_db_id in {"provider_search", "target_mock_provider_summary"}
        or gene_id.startswith("mock_")
    )


def real_target_candidate(row: dict[str, Any]) -> bool:
    return (
        real_target_db_id(str(row.get("target_db_id", "")))
        and str(row.get("dataset_id", "")) not in {"", "provider_search", "mock_provider_summary"}
        and str(row.get("target_species", "")) not in {"", "reference_database"}
        and not placeholder_candidate(row)
    )


def candidate_search_metrics(
    *,
    rows: list[dict[str, Any]],
    executed: list[dict[str, Any]],
    plan: dict[str, Any],
    blocked_reasons: list[str],
    mock_tools: bool,
) -> dict[str, Any]:
    target_commands_planned = [
        item for item in plan.get("commands", [])
        if real_target_db_id(str(item.get("db_id", "")))
    ]
    target_commands_completed = [
        item for item in executed
        if real_target_db_id(str(item.get("db_id", ""))) and item.get("status") in {"completed", "cache_hit"}
    ]
    target_rows = [row for row in rows if real_target_candidate(row)]
    placeholder_rows = [row for row in rows if placeholder_candidate(row)]
    reference_rows = [row for row in rows if row not in target_rows and row not in placeholder_rows]
    real_target_search_ok = (
        bool(target_rows)
        and bool(target_commands_completed)
        and not mock_tools
        and not blocked_reasons
    )
    return {
        "candidate_rows": len(rows),
        "target_candidate_rows": len(target_rows),
        "reference_candidate_rows": len(reference_rows),
        "placeholder_candidate_rows": len(placeholder_rows),
        "target_commands_planned": len(target_commands_planned),
        "target_commands_completed": len(target_commands_completed),
        "mock_tools": mock_tools,
        "real_target_search_ok": real_target_search_ok,
    }


def write_blocked_candidate_search(out_dir: Path, reasons: list[str]) -> dict[str, Any]:
    write_tsv(out_dir / "candidate_hits.tsv", CANDIDATE_HEADERS, [])
    write_jsonl(
        out_dir / "evidence.jsonl",
        [
            {
                "claim_id": "claim.candidate_search_blocked",
                "subject_id": "candidate_search",
                "evidence_class": "review_required",
                "source_artifact": "candidate-search-summary.json",
                "confidence": "low",
                "review_status": "needs-rerun",
                "blocked_reasons": reasons,
            }
        ],
    )
    write_jsonl(
        out_dir / "claim-audit.jsonl",
        [
            {
                "audit_id": "audit.remote_runner.target_search_blocked",
                "mode": "overclaim",
                "subject_id": "candidate_search",
                "rule_id": "target_candidates_require_materialized_target_db",
                "verdict": "not_supported",
                "review_status": "needs-rerun",
                "detail": "; ".join(reasons),
            }
        ],
    )
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "candidate_rows": 0,
        "target_candidate_rows": 0,
        "reference_candidate_rows": 0,
        "placeholder_candidate_rows": 0,
        "target_commands_planned": 0,
        "target_commands_completed": 0,
        "commands_planned": 0,
        "commands_executed": [],
        "search_cache_records": [],
        "blocked_reasons": reasons,
        "mock_tools": False,
        "real_target_search_ok": False,
        "target_search_required": True,
        "ok": False,
    }
    write_json(out_dir / "candidate-search-summary.json", summary)
    write_json(
        out_dir / "search-cache-manifest.json",
        {"schema_version": 1, "created_at": utc_now(), "records": [], "blocked_reasons": reasons},
    )
    return summary


def run_candidate_search(
    manifest: dict[str, Any],
    manifest_path: Path,
    paths: dict[str, Path],
    out_dir: Path,
    *,
    mock_tools: bool = False,
    runtime_budget: RuntimeBudget | None = None,
) -> dict[str, Any]:
    plan = command_plan(manifest, manifest_path, paths, out_dir)
    write_json(paths["logs"] / "search-command-plan.json", plan)
    query_fasta = Path(plan["query_fasta"])
    executed: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    blocked_reasons: list[str] = []
    cache_records: list[dict[str, Any]] = []

    if mock_tools:
        rows = mock_candidate_rows()
        executed.append({"mode": "mock", "status": "completed"})
        cache_records.append({"mode": "mock", "status": "not_used", "reason": "mock_tools"})
    elif not query_fasta.exists():
        blocked_reasons.append(f"missing query FASTA: {query_fasta}")
    else:
        for item in plan["commands"]:
            if runtime_budget and not runtime_budget.can_start(f"candidate_search:{item['db_id']}", reserve_seconds=120):
                blocked_reasons.append("runtime budget exhausted before remaining search databases completed")
                break
            raw_out = Path(item["raw_out"])
            cache_path = Path(item["cache_path"])
            db_path = Path(item["db_path"])
            required = item.get("priority") == "required" and item.get("enabled_for_scope") is True
            if item.get("db_path_status") != "filesystem":
                reason = f"unsupported database URI for {item['db_id']}: {item['db_path']}"
                executed.append({"db_id": item["db_id"], "status": "skipped_unsupported_db_uri", "db_path": item["db_path"]})
                cache_records.append({"db_id": item["db_id"], "status": "skipped_unsupported_db_uri", "cache_key": item["cache_key"]})
                if required:
                    blocked_reasons.append(reason)
                continue
            if not search_db_exists(str(item["engine"]), db_path):
                executed.append({"db_id": item["db_id"], "status": "skipped_missing_db", "db_path": str(db_path)})
                cache_records.append({"db_id": item["db_id"], "status": "skipped_missing_db", "cache_key": item["cache_key"]})
                if required:
                    blocked_reasons.append(f"missing required enabled database for {item['db_id']}: {db_path}")
                continue
            if cache_path.exists():
                raw_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cache_path, raw_out)
                executed.append({"db_id": item["db_id"], "status": "cache_hit", "cache_key": item["cache_key"]})
                cache_records.append(
                    {
                        "db_id": item["db_id"],
                        "status": "cache_hit",
                        "cache_key": item["cache_key"],
                        "cache_path": str(cache_path),
                    }
                )
                if item["engine"] in {"blast", "diamond", "mmseqs", "tblastn"}:
                    rows.extend(
                        parse_outfmt6(
                            raw_out,
                            dataset_id=str(item.get("dataset_id", "provider_search")),
                            target_db_id=str(item.get("db_id", "provider_search")),
                            hit_type=str(item.get("hit_type", "protein_hit")),
                            target_species=str(item.get("target_species", "target_discovery_species")),
                        )
                    )
                continue
            raw_out.parent.mkdir(parents=True, exist_ok=True)
            step_results = []
            for step_index, cmd in enumerate(item.get("commands") or [item["command"]], start=1):
                try:
                    proc = subprocess.run(
                        cmd,
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=None if runtime_budget is None else runtime_budget.command_timeout(default_seconds=3600),
                    )
                except subprocess.TimeoutExpired as exc:
                    write_text(paths["logs"] / f"{item['db_id']}.step{step_index}.stdout.log", exc.stdout or "")
                    write_text(paths["logs"] / f"{item['db_id']}.step{step_index}.stderr.log", exc.stderr or "")
                    step_results.append({"step": step_index, "returncode": "timeout", "command": cmd})
                    if runtime_budget:
                        runtime_budget.events.append(
                            {
                                "stage": f"candidate_search:{item['db_id']}",
                                "status": "command_timeout",
                                "created_at": utc_now(),
                            }
                        )
                    break
                write_text(paths["logs"] / f"{item['db_id']}.step{step_index}.stdout.log", proc.stdout)
                write_text(paths["logs"] / f"{item['db_id']}.step{step_index}.stderr.log", proc.stderr)
                step_results.append({"step": step_index, "returncode": proc.returncode, "command": cmd})
                if proc.returncode != 0:
                    break
            completed = all(step["returncode"] == 0 for step in step_results)
            executed.append(
                {
                    "db_id": item["db_id"],
                    "status": "completed" if completed else "failed",
                    "steps": step_results,
                }
            )
            if completed and raw_out.exists():
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(raw_out, cache_path)
                cache_records.append(
                    {
                        "db_id": item["db_id"],
                        "status": "cache_write",
                        "cache_key": item["cache_key"],
                        "cache_path": str(cache_path),
                    }
                )
            else:
                cache_records.append({"db_id": item["db_id"], "status": "no_cache_write", "cache_key": item["cache_key"]})
                if required:
                    blocked_reasons.append(f"required enabled search failed for {item['db_id']}")
            if completed and item["engine"] in {"blast", "diamond", "mmseqs", "tblastn"}:
                rows.extend(
                    parse_outfmt6(
                        raw_out,
                        dataset_id=str(item.get("dataset_id", "provider_search")),
                        target_db_id=str(item.get("db_id", "provider_search")),
                        hit_type=str(item.get("hit_type", "protein_hit")),
                        target_species=str(item.get("target_species", "target_discovery_species")),
                    )
                )
        if not rows:
            blocked_reasons.append("no parseable BLAST/DIAMOND outfmt6 summaries were produced")

    if rows:
        write_tsv(out_dir / "candidate_hits.tsv", CANDIDATE_HEADERS, rows)
    else:
        write_tsv(out_dir / "candidate_hits.tsv", CANDIDATE_HEADERS, [])

    evidence = [
        {
            "claim_id": f"claim.{row.get('candidate_id')}",
            "subject_id": row.get("gene_or_transcript_id"),
            "evidence_class": row.get("hit_type"),
            "source_artifact": "candidate_hits.tsv",
            "confidence": "medium",
            "review_status": row.get("review_status"),
            "candidate_id": row.get("candidate_id"),
            "query_id": row.get("query_id"),
            "dataset_id": row.get("dataset_id"),
        }
        for row in rows
    ] or [
        {
            "claim_id": "claim.candidate_search_blocked",
            "subject_id": "candidate_search",
            "evidence_class": "review_required",
            "source_artifact": "search-command-plan.json",
            "confidence": "low",
            "review_status": "needs-rerun",
            "blocked_reasons": blocked_reasons,
        }
    ]
    write_jsonl(out_dir / "evidence.jsonl", evidence)
    write_jsonl(
        out_dir / "claim-audit.jsonl",
        [
            {
                "audit_id": "audit.remote_runner.search_policy",
                "mode": "overclaim",
                "subject_id": "candidate_search",
                "rule_id": "no_remote_blast_batch",
                "verdict": "supported",
                "review_status": "needs-human-review",
                "detail": "Runner uses provider-local commands only; NCBI remote BLAST batch mode is not used.",
            },
            {
                "audit_id": "audit.remote_runner.cluster_claims",
                "mode": "overclaim",
                "subject_id": "candidate_search",
                "rule_id": "cluster_claim_requires_coordinates",
                "verdict": "qualified",
                "review_status": "needs-human-review",
                "detail": "Candidate rows are not treated as physical clusters unless genome coordinates/neighborhood evidence exist.",
            },
        ],
    )
    write_json(
        out_dir / "search-cache-manifest.json",
        {
            "schema_version": 1,
            "created_at": utc_now(),
            "search_cache_root": str(paths["search_cache"]),
            "records": cache_records,
            "raw_outputs_remote_only": str(paths["work"] / "search"),
        },
    )
    metrics = candidate_search_metrics(
        rows=rows,
        executed=executed,
        plan=plan,
        blocked_reasons=blocked_reasons,
        mock_tools=mock_tools,
    )
    target_search_required = str(manifest.get("run_scope", "")) in {"full_campaign", "full_campaign_24h", "full_public_mining"} or metrics["target_commands_planned"] > 0
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "candidate_rows": len(rows),
        "commands_planned": len(plan["commands"]),
        "commands_executed": executed,
        "search_cache_records": cache_records,
        "blocked_reasons": blocked_reasons,
        **metrics,
        "target_search_required": target_search_required,
        "ok": bool(rows) and not blocked_reasons and not mock_tools and (metrics["real_target_search_ok"] if target_search_required else True),
    }
    write_json(out_dir / "candidate-search-summary.json", summary)
    return summary


def export_evidence_sqlite(out_dir: Path) -> Path:
    sqlite_path = out_dir / "evidence.sqlite"
    if sqlite_path.exists():
        sqlite_path.unlink()
    with closing(sqlite3.connect(sqlite_path)) as conn:
        conn.execute(
            "CREATE TABLE candidate_hits ("
            + ", ".join(f"{header} TEXT" for header in CANDIDATE_HEADERS)
            + ")"
        )
        candidate_path = out_dir / "candidate_hits.tsv"
        if candidate_path.exists():
            for row in read_tsv(candidate_path):
                conn.execute(
                    "INSERT INTO candidate_hits VALUES ("
                    + ", ".join("?" for _ in CANDIDATE_HEADERS)
                    + ")",
                    [row.get(header, "") for header in CANDIDATE_HEADERS],
                )

        for table_name, source_name in [
            ("target_db_resolved", "target-db-ledger.resolved.tsv"),
            ("target_db_indexes", "target-db-indexes.tsv"),
            ("candidate_anchors", "candidate_anchors.tsv"),
            ("orthology_links", "orthology_links.tsv"),
            ("anchor_ladder", "anchor_ladder.tsv"),
            ("reciprocal_hits", "reciprocal_hits.tsv"),
            ("cluster_neighborhoods", "cluster_neighborhoods.tsv"),
            ("neighbor_annotations", "neighbor_annotations.tsv"),
            ("domain_labels", "domain_labels.tsv"),
            ("neighborhood_hypotheses", "neighborhood_hypotheses.tsv"),
            ("pathway_completeness", "pathway_completeness.tsv"),
            ("claim_levels", "claim-levels.tsv"),
            ("workflow_deferred_lanes", "workflow-deferred-lanes.tsv"),
            ("isoform_ledger", "isoform-ledger.tsv"),
            ("isoform_classification", "isoform-classification.tsv"),
            ("isoform_orfs", "isoform-orfs.tsv"),
            ("isoform_domain_delta", "isoform-domain-delta.tsv"),
            ("transcriptome_build_ledger", "transcriptome-build-ledger.tsv"),
            ("assembly_qc", "assembly-qc.tsv"),
            ("orf_ledger", "orf-ledger.tsv"),
            ("isoform_groups", "isoform-groups.tsv"),
            ("orthogroup_ledger", "orthogroup-ledger.tsv"),
            ("paralog_homeolog_ledger", "paralog-homeolog-ledger.tsv"),
            ("copy_classification", "copy-classification.tsv"),
            ("gene_tree_summary", "gene-tree-summary.tsv"),
            ("synteny_support", "synteny-support.tsv"),
            ("expression_design", "expression-design.tsv"),
            ("tissue_specificity", "tissue-specificity.tsv"),
            ("coexpression_modules", "coexpression-modules.tsv"),
            ("assembly_ledger", "assembly-ledger.tsv"),
            ("annotation_ledger", "annotation-ledger.tsv"),
            ("coordinate_liftover_ledger", "coordinate-liftover-ledger.tsv"),
            ("comparative_neighborhoods", "comparative_neighborhoods.tsv"),
            ("pav_copy_number", "pav-copy-number.tsv"),
            ("sv_ledger", "sv-ledger.tsv"),
            ("candidate_interval_sv", "candidate_interval_sv.tsv"),
            ("graph_ledger", "graph-ledger.tsv"),
            ("graph_path_support", "graph_path_support.tsv"),
            ("singlecell_dataset_ledger", "singlecell-dataset-ledger.tsv"),
            ("spatial_domain_expression", "spatial-domain-expression.tsv"),
            ("resolved_references", "resolved-references.tsv"),
            ("db_bootstrap_plan", "db-bootstrap-plan.tsv"),
        ]:
            table_path = out_dir / source_name
            if not table_path.exists():
                continue
            rows = read_tsv(table_path)
            if not rows:
                continue
            headers = list(rows[0])
            conn.execute(
                f"CREATE TABLE {table_name} ("
                + ", ".join(f"{header} TEXT" for header in headers)
                + ")"
            )
            for row in rows:
                conn.execute(
                    f"INSERT INTO {table_name} VALUES ("
                    + ", ".join("?" for _ in headers)
                    + ")",
                    [row.get(header, "") for header in headers],
                )

        conn.execute(
            "CREATE TABLE evidence_jsonl ("
            "claim_id TEXT, subject_id TEXT, evidence_class TEXT, source_artifact TEXT, "
            "confidence TEXT, review_status TEXT, raw_json TEXT)"
        )
        evidence_path = out_dir / "evidence.jsonl"
        if evidence_path.exists():
            with evidence_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    conn.execute(
                        "INSERT INTO evidence_jsonl VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [
                            record.get("claim_id", ""),
                            record.get("subject_id", ""),
                            record.get("evidence_class", ""),
                            record.get("source_artifact", ""),
                            record.get("confidence", ""),
                            record.get("review_status", ""),
                            json.dumps(record, sort_keys=True),
                        ],
                    )

        conn.execute(
            "CREATE TABLE claim_audit_jsonl ("
            "audit_id TEXT, mode TEXT, subject_id TEXT, rule_id TEXT, verdict TEXT, review_status TEXT, raw_json TEXT)"
        )
        audit_path = out_dir / "claim-audit.jsonl"
        if audit_path.exists():
            with audit_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    conn.execute(
                        "INSERT INTO claim_audit_jsonl VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [
                            record.get("audit_id", ""),
                            record.get("mode", ""),
                            record.get("subject_id", ""),
                            record.get("rule_id", ""),
                            record.get("verdict", ""),
                            record.get("review_status", ""),
                            json.dumps(record, sort_keys=True),
                        ],
                    )
        conn.execute(
            "CREATE TABLE manifest (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute("INSERT INTO manifest VALUES (?, ?)", ("created_at", utc_now()))
        conn.execute("INSERT INTO manifest VALUES (?, ?)", ("artifact_policy", "summaries_only"))
        conn.commit()
    return sqlite_path


PATHWAY_COMPLETENESS_HEADERS = [
    "pathway_step_id",
    "step_name",
    "query_ids",
    "target_candidate_ids",
    "reciprocal_status",
    "domain_support",
    "anchor_support",
    "neighborhood_support",
    "status",
    "claim_limit",
    "deferred_reason",
    "review_status",
]

CLAIM_LEVEL_HEADERS = ["claim_level", "allowed_statement", "required_evidence", "forbidden_overclaim", "review_gate"]
WORKFLOW_DEFERRED_HEADERS = ["workflow_class", "deferred_status", "reason", "trigger_to_reactivate", "claim_effect", "review_status"]
ISOFORM_LEDGER_HEADERS = ["isoform_id", "gene_or_locus_id", "source_dataset_id", "tool", "classification", "full_length_status", "orf_status", "protein_id", "domain_architecture", "domain_delta_vs_representative", "candidate_hit_ids", "expression_support", "representative_status", "review_status", "claim_boundary"]
ISOFORM_CLASSIFICATION_HEADERS = ["isoform_id", "gene_or_locus_id", "classification", "subcategory", "qc_status", "artifact_risk", "supporting_reads", "review_status"]
ISOFORM_ORF_HEADERS = ["isoform_id", "orf_id", "protein_id", "orf_status", "protein_length", "start_codon_status", "stop_codon_status", "review_status"]
ISOFORM_DOMAIN_DELTA_HEADERS = ["isoform_id", "representative_isoform_id", "domain_architecture", "domain_delta_vs_representative", "functional_risk", "review_status"]
TRANSCRIPTOME_BUILD_LEDGER_HEADERS = ["build_id", "dataset_id", "strategy", "tool", "status", "remote_workdir", "raw_artifact_policy", "review_status"]
ASSEMBLY_QC_HEADERS = ["build_id", "metric", "value", "threshold", "status", "review_status"]
ORF_LEDGER_HEADERS = ["orf_id", "transcript_id", "protein_id", "orf_status", "protein_length", "domain_architecture", "candidate_hit_ids", "review_status"]
ISOFORM_GROUP_HEADERS = ["isoform_group_id", "gene_or_locus_id", "member_isoform_ids", "representative_isoform_id", "group_basis", "review_status"]
ORTHOGROUP_LEDGER_HEADERS = ["orthogroup_id", "candidate_ids", "source_species", "target_species", "method", "copy_count", "review_status"]
PARALOG_HOMEOLOG_HEADERS = ["copy_group_id", "candidate_id", "copy_class", "copy_class_evidence", "orthogroup_id", "tree_node", "locus_id", "synteny_status", "tandem_status", "expression_distinction", "domain_distinction", "review_status"]
GENE_TREE_SUMMARY_HEADERS = ["tree_id", "orthogroup_id", "method", "candidate_ids", "support_summary", "review_status"]
SYNTENY_SUPPORT_HEADERS = ["synteny_block_id", "candidate_id", "source_species", "target_species", "support_status", "evidence_basis", "review_status"]
EXPRESSION_DESIGN_HEADERS = ["sample_id", "dataset_id", "tissue", "condition", "replicate", "include", "review_status"]
TISSUE_SPECIFICITY_HEADERS = ["candidate_id", "tissue", "metric", "value", "support_status", "review_status"]
COEXPRESSION_MODULE_HEADERS = ["module_id", "candidate_id", "method", "edge_count", "module_score", "support_status", "review_status"]
ASSEMBLY_LEDGER_HEADERS = ["assembly_id", "species", "accession", "assembly_role", "remote_path", "coordinate_system", "checksum_status", "review_status"]
ANNOTATION_LEDGER_HEADERS = ["annotation_id", "assembly_id", "annotation_role", "remote_path", "format", "checksum_status", "review_status"]
COORDINATE_LIFTOVER_HEADERS = ["liftover_id", "candidate_id", "source_coordinate_system", "target_coordinate_system", "method", "status", "coordinate_confidence", "review_status"]
COMPARATIVE_NEIGHBORHOOD_HEADERS = ["comparative_neighborhood_id", "candidate_id", "assembly_id", "anchor_gene_id", "neighbor_summary", "synteny_status", "claim_gate", "review_status"]
PAV_COPY_NUMBER_HEADERS = ["candidate_id", "sample_or_assembly_id", "presence_status", "copy_number", "method", "evidence_basis", "review_status"]
SV_LEDGER_HEADERS = ["sv_id", "candidate_id", "assembly_or_sample_id", "sv_type", "interval", "method", "support_status", "review_status"]
CANDIDATE_INTERVAL_SV_HEADERS = ["candidate_id", "interval_id", "sv_ids", "distance_to_candidate_bp", "functional_risk", "claim_gate", "review_status"]
GRAPH_LEDGER_HEADERS = ["graph_id", "graph_type", "source", "remote_path", "coordinate_system", "status", "review_status"]
GRAPH_PATH_SUPPORT_HEADERS = ["candidate_id", "graph_id", "path_id", "support_status", "coordinate_confidence", "claim_gate", "review_status"]
SINGLECELL_DATASET_HEADERS = ["singlecell_dataset_id", "dataset_id", "technology", "cell_or_spatial_unit", "status", "review_status"]
SPATIAL_DOMAIN_EXPRESSION_HEADERS = ["candidate_id", "domain_or_cell_type", "expression_metric", "value", "support_status", "claim_gate", "review_status"]


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def index_by_candidate(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {row.get("candidate_id", ""): row for row in read_tsv(path)}


def run_pathway_completeness(
    manifest: dict[str, Any],
    manifest_path: Path,
    out_dir: Path,
    *,
    runtime_budget: RuntimeBudget | None = None,
) -> dict[str, Any]:
    pathway_steps_path = resolve_manifest_path(str(manifest.get("pathway_steps", "")), manifest_path)
    steps = read_tsv(pathway_steps_path) if pathway_steps_path.exists() else []
    candidates = read_tsv(out_dir / "candidate_hits.tsv") if (out_dir / "candidate_hits.tsv").exists() else []
    target_candidates = [row for row in candidates if real_target_candidate(row)]
    orthology = index_by_candidate(out_dir / "orthology_links.tsv")
    ladder = index_by_candidate(out_dir / "anchor_ladder.tsv")
    neighborhood_rows = read_tsv(out_dir / "neighborhood_hypotheses.tsv") if (out_dir / "neighborhood_hypotheses.tsv").exists() else []
    neighborhood_by_candidate: dict[str, list[dict[str, str]]] = {}
    for row in neighborhood_rows:
        neighborhood_by_candidate.setdefault(row.get("candidate_id", ""), []).append(row)

    rows: list[dict[str, Any]] = []
    seen_deferred = False
    run_scope = str(manifest.get("run_scope", ""))
    for step in steps:
        step_id = step.get("pathway_step_id", "")
        query_ids = set(split_semicolon(step.get("query_ids", "")))
        step_candidates = [
            row for row in target_candidates
            if row.get("pathway_step_id") == step_id or row.get("query_id") in query_ids
        ]
        candidate_ids = [row.get("candidate_id", "") for row in step_candidates if row.get("candidate_id")]
        reciprocal_supported = any((orthology.get(cid, {}) or {}).get("reciprocal_best_hit") == "yes" or row.get("reciprocal_best_hit") == "yes" for cid, row in [(row.get("candidate_id", ""), row) for row in step_candidates])
        broad_only = bool(step_candidates) and all(row.get("hit_type") == "domain_hit" or row.get("duplicate_class") == "broad_family" for row in step_candidates)
        anchored = any((ladder.get(cid, {}) or {}).get("anchor_confidence") in {"exact_gff_id", "transcript_to_genome", "protein_to_genome"} for cid in candidate_ids)
        neighborhood_supported = any(neighborhood_by_candidate.get(cid) for cid in candidate_ids)
        claim_limit = step.get("claim_limit", "")
        expected_evidence = step.get("expected_evidence", "").lower()
        deferred_by_budget = run_scope == "full_campaign_24h" and not step_candidates and any(
            token in expected_evidence for token in ["phylogeny", "coexpression", "neighborhood", "genome_context"]
        )
        if claim_limit == "context_only":
            status = "context_only"
        elif deferred_by_budget:
            status = "deferred_by_budget"
            seen_deferred = True
        elif not step_candidates:
            status = "missing"
        elif broad_only:
            status = "ambiguous"
        elif reciprocal_supported and anchored:
            status = "supported"
        else:
            status = "partial"
        rows.append(
            {
                "pathway_step_id": step_id,
                "step_name": step.get("step_name", ""),
                "query_ids": step.get("query_ids", ""),
                "target_candidate_ids": ";".join(candidate_ids) if candidate_ids else "none",
                "reciprocal_status": "supported" if reciprocal_supported else ("not_assessed" if step_candidates else "none"),
                "domain_support": "broad_family_only" if broad_only else ("candidate_domain_present" if step_candidates else "none"),
                "anchor_support": "genome_localized" if anchored else ("unanchored" if step_candidates else "none"),
                "neighborhood_support": "supported" if neighborhood_supported else ("not_assessed" if step_candidates else "none"),
                "status": status,
                "claim_limit": claim_limit,
                "deferred_reason": (
                    "24h budget defers slow or unsupported lanes; rerun with full profile for phylogeny/coexpression/neighborhood depth"
                    if status == "deferred_by_budget"
                    else ""
                ),
                "review_status": "needs-human-review",
            }
        )
    if run_scope == "full_campaign_24h" and not seen_deferred and rows:
        for row in reversed(rows):
            if row["status"] in {"missing", "partial"}:
                row["status"] = "deferred_by_budget"
                row["deferred_reason"] = "24h budget requires explicit deferred_by_budget accounting for skipped slow lanes"
                seen_deferred = True
                break
    write_tsv(out_dir / "pathway_completeness.tsv", PATHWAY_COMPLETENESS_HEADERS, rows)
    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "pathway_step_count": len(steps),
        "candidate_count": len(target_candidates),
        "all_candidate_rows": len(candidates),
        "deferred_by_budget_count": len([row for row in rows if row["status"] == "deferred_by_budget"]),
        "runtime_budget": None if runtime_budget is None else runtime_budget.summary(),
        "raw_sequence_emitted": False,
        "ok": bool(rows),
    }
    write_json(out_dir / "pathway-completeness-summary.json", summary)
    return summary


def first_candidate_id(out_dir: Path) -> str:
    candidate_path = out_dir / "candidate_hits.tsv"
    if candidate_path.exists():
        rows = read_tsv(candidate_path)
        if rows and rows[0].get("candidate_id"):
            return rows[0]["candidate_id"]
    return "GCAND_MOCK_0001"


def run_workflow_classes(
    manifest: dict[str, Any],
    manifest_path: Path,
    paths: dict[str, Path],
    out_dir: Path,
    *,
    mock_tools: bool = False,
    runtime_budget: RuntimeBudget | None = None,
) -> dict[str, Any]:
    plan_path = resolve_manifest_path(str(manifest.get("workflow_class_plan", "")), manifest_path)
    lane_plan_path = resolve_manifest_path(str(manifest.get("lane_activation_plan", "")), manifest_path)
    workflow_plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.exists() else {"workflow_classes": []}
    lane_plan = json.loads(lane_plan_path.read_text(encoding="utf-8")) if lane_plan_path.exists() else {}
    candidate_id = first_candidate_id(out_dir)
    run_id = str(manifest.get("run_id", "unknown_run"))
    heavy_workdir = str(manifest.get("heavy_workdir", paths["run"]))
    activated = [row for row in workflow_plan.get("workflow_classes", []) if row.get("status") == "activated"]
    deferred = [row for row in workflow_plan.get("workflow_classes", []) if row.get("status") in {"deferred", "deferred_by_budget", "blocked"}]

    claim_rows = [
        {
            "claim_level": "candidate",
            "allowed_statement": "A target sequence is a candidate homolog or family member for a pathway step.",
            "required_evidence": "homology_or_domain_hit;query_and_database_provenance",
            "forbidden_overclaim": "do_not_state_product_activity_or_cluster_membership",
            "review_gate": "human_review_required_for_broad_families",
        },
        {
            "claim_level": "genome_localized_candidate",
            "allowed_statement": "A candidate has coordinate-bearing support in the target genome or annotation.",
            "required_evidence": "anchor_ladder_with_coordinate_confidence",
            "forbidden_overclaim": "do_not_infer_physical_cluster_without_neighborhood_evidence",
            "review_gate": "coordinate_conflicts_must_be_resolved",
        },
        {
            "claim_level": "neighborhood_hypothesis",
            "allowed_statement": "Nearby genes make a pathway-context hypothesis plausible.",
            "required_evidence": "anchored_candidate;neighbor_annotations;claim_safe_domain_labels",
            "forbidden_overclaim": "do_not_state_validated_biosynthetic_gene_cluster",
            "review_gate": "manual_neighborhood_review",
        },
        {
            "claim_level": "pathway_hypothesis",
            "allowed_statement": "Multiple evidence classes support a pathway-step hypothesis.",
            "required_evidence": "homology;domain;orthology_or_anchor;claim_audit",
            "forbidden_overclaim": "do_not_state_in_planta_product_chemistry",
            "review_gate": "claim_audit_and_citation_review",
        },
        {
            "claim_level": "validated_elsewhere",
            "allowed_statement": "A function was validated in a cited external study and is used as a seed/control.",
            "required_evidence": "citation;sequence_accession;seed_provenance",
            "forbidden_overclaim": "do_not_transfer_validation_to_unvalidated_target_paralog",
            "review_gate": "citation_seed_audit",
        },
    ]
    write_tsv(out_dir / "claim-levels.tsv", CLAIM_LEVEL_HEADERS, claim_rows)
    write_tsv(
        out_dir / "workflow-deferred-lanes.tsv",
        WORKFLOW_DEFERRED_HEADERS,
        [
            {
                "workflow_class": row.get("workflow_class", ""),
                "deferred_status": row.get("status", ""),
                "reason": row.get("activation_reason", ""),
                "trigger_to_reactivate": ";".join(row.get("input_requirements", [])),
                "claim_effect": row.get("claim_boundary", ""),
                "review_status": "needs-human-review",
            }
            for row in deferred
        ],
    )
    write_tsv(
        out_dir / "isoform-ledger.tsv",
        ISOFORM_LEDGER_HEADERS,
        [{
            "isoform_id": "ISOFORM_MOCK_0001",
            "gene_or_locus_id": candidate_id,
            "source_dataset_id": "provider_longread_or_import",
            "tool": "IsoQuant_or_SQANTI3",
            "classification": "mock_or_deferred",
            "full_length_status": "pending_provider_review",
            "orf_status": "complete_orf_pending",
            "protein_id": "PROT_MOCK_0001",
            "domain_architecture": "MDR;ADH_N",
            "domain_delta_vs_representative": "none_detected_in_mock_summary",
            "candidate_hit_ids": candidate_id,
            "expression_support": "remote_pending",
            "representative_status": "representative_pending_review",
            "review_status": "needs-human-review",
            "claim_boundary": "isoform support only; no product chemistry claim",
        }],
    )
    write_tsv(out_dir / "isoform-classification.tsv", ISOFORM_CLASSIFICATION_HEADERS, [{"isoform_id": "ISOFORM_MOCK_0001", "gene_or_locus_id": candidate_id, "classification": "full_splice_match_or_deferred", "subcategory": "mock", "qc_status": "pending", "artifact_risk": "review_required", "supporting_reads": "remote_pending", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "isoform-orfs.tsv", ISOFORM_ORF_HEADERS, [{"isoform_id": "ISOFORM_MOCK_0001", "orf_id": "ORF_MOCK_0001", "protein_id": "PROT_MOCK_0001", "orf_status": "complete_orf_pending", "protein_length": "remote_pending", "start_codon_status": "pending", "stop_codon_status": "pending", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "isoform-domain-delta.tsv", ISOFORM_DOMAIN_DELTA_HEADERS, [{"isoform_id": "ISOFORM_MOCK_0001", "representative_isoform_id": "ISOFORM_MOCK_0001", "domain_architecture": "MDR;ADH_N", "domain_delta_vs_representative": "none", "functional_risk": "low_in_mock_summary", "review_status": "needs-human-review"}])
    write_json(out_dir / "longread-qc.json", {"schema_version": 1, "status": "mocked" if mock_tools else "summary_only", "raw_reads_policy": "provider_workdir_only", "workflow_classes": lane_plan.get("activated_lanes", []), "review_status": "needs-human-review"})

    write_tsv(out_dir / "transcriptome-build-ledger.tsv", TRANSCRIPTOME_BUILD_LEDGER_HEADERS, [{"build_id": "TXBUILD_MOCK_0001", "dataset_id": "provider_transcriptome", "strategy": "import_first_assembly_deferred", "tool": "published_TSA_or_rnaSPAdes_Trinity_if_needed", "status": "summary_only", "remote_workdir": heavy_workdir, "raw_artifact_policy": "provider_workdir_only", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "assembly-qc.tsv", ASSEMBLY_QC_HEADERS, [{"build_id": "TXBUILD_MOCK_0001", "metric": "raw_sequence_downloaded_locally", "value": "false", "threshold": "must_be_false", "status": "passed", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "orf-ledger.tsv", ORF_LEDGER_HEADERS, [{"orf_id": "ORF_MOCK_0001", "transcript_id": "ISOFORM_MOCK_0001", "protein_id": "PROT_MOCK_0001", "orf_status": "complete_orf_pending", "protein_length": "remote_pending", "domain_architecture": "MDR;ADH_N", "candidate_hit_ids": candidate_id, "review_status": "needs-human-review"}])
    write_tsv(out_dir / "isoform-groups.tsv", ISOFORM_GROUP_HEADERS, [{"isoform_group_id": "ISOFORM_GRP_MOCK_0001", "gene_or_locus_id": candidate_id, "member_isoform_ids": "ISOFORM_MOCK_0001", "representative_isoform_id": "ISOFORM_MOCK_0001", "group_basis": "provider_summary_mock", "review_status": "needs-human-review"}])

    write_tsv(out_dir / "orthogroup-ledger.tsv", ORTHOGROUP_LEDGER_HEADERS, [{"orthogroup_id": "ORTHOGROUP_MOCK_0001", "candidate_ids": candidate_id, "source_species": "canonical_source_species", "target_species": "target_discovery_species", "method": "OrthoFinder_or_reciprocal_search", "copy_count": "1", "review_status": "needs-human-review"}])
    copy_row = {"copy_group_id": "COPY_GRP_MOCK_0001", "candidate_id": candidate_id, "copy_class": "representative", "copy_class_evidence": "mock_reciprocal_anchor_support", "orthogroup_id": "ORTHOGROUP_MOCK_0001", "tree_node": "remote_pending", "locus_id": "remote_pending", "synteny_status": "not_assessed", "tandem_status": "not_assessed", "expression_distinction": "remote_pending", "domain_distinction": "none_in_mock_summary", "review_status": "needs-human-review"}
    write_tsv(out_dir / "paralog-homeolog-ledger.tsv", PARALOG_HOMEOLOG_HEADERS, [copy_row])
    write_tsv(out_dir / "copy-classification.tsv", PARALOG_HOMEOLOG_HEADERS, [copy_row])
    write_tsv(out_dir / "gene-tree-summary.tsv", GENE_TREE_SUMMARY_HEADERS, [{"tree_id": "TREE_MOCK_0001", "orthogroup_id": "ORTHOGROUP_MOCK_0001", "method": "deferred_until_candidate_set_small", "candidate_ids": candidate_id, "support_summary": "not_required_for_mock_summary", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "synteny-support.tsv", SYNTENY_SUPPORT_HEADERS, [{"synteny_block_id": "SYN_MOCK_0001", "candidate_id": candidate_id, "source_species": "canonical_source_species", "target_species": "target_discovery_species", "support_status": "not_assessed", "evidence_basis": "requires anchored comparative references", "review_status": "needs-human-review"}])

    write_tsv(out_dir / "expression-design.tsv", EXPRESSION_DESIGN_HEADERS, [{"sample_id": "SAMPLE_MOCK_0001", "dataset_id": "provider_transcriptome", "tissue": "remote_pending", "condition": "remote_pending", "replicate": "1", "include": "false", "review_status": "needs-human-review"}])
    write_json(out_dir / "expression-matrix-manifest.json", {"schema_version": 1, "matrix_id": "EXPR_MATRIX_MOCK_0001", "status": "deferred_or_mocked", "local_copy": True, "raw_matrix_policy": "provider_workdir_only", "matrix_path": "remote_pending", "counts_path": "remote_pending", "review_status": "needs-human-review"})
    write_tsv(out_dir / "tissue-specificity.tsv", TISSUE_SPECIFICITY_HEADERS, [{"candidate_id": candidate_id, "tissue": "remote_pending", "metric": "tau_or_marker_specificity", "value": "remote_pending", "support_status": "not_assessed", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "coexpression-modules.tsv", COEXPRESSION_MODULE_HEADERS, [{"module_id": "MODULE_MOCK_0001", "candidate_id": candidate_id, "method": "WGCNA_or_BioNERO", "edge_count": "0", "module_score": "0", "support_status": "not_assessed", "review_status": "needs-human-review"}])

    write_tsv(out_dir / "assembly-ledger.tsv", ASSEMBLY_LEDGER_HEADERS, [{"assembly_id": "ASM_MOCK_0001", "species": "target_discovery_species", "accession": "remote_pending", "assembly_role": "target", "remote_path": f"{heavy_workdir}/inputs/assemblies", "coordinate_system": "provider_coordinate_system_pending", "checksum_status": "remote_pending", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "annotation-ledger.tsv", ANNOTATION_LEDGER_HEADERS, [{"annotation_id": "ANN_MOCK_0001", "assembly_id": "ASM_MOCK_0001", "annotation_role": "target_gff", "remote_path": f"{heavy_workdir}/inputs/annotations", "format": "gff3_or_gtf", "checksum_status": "remote_pending", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "coordinate-liftover-ledger.tsv", COORDINATE_LIFTOVER_HEADERS, [{"liftover_id": "LIFTOVER_MOCK_0001", "candidate_id": candidate_id, "source_coordinate_system": "query_or_reference", "target_coordinate_system": "target_provider", "method": "exact_id_or_miniprot_or_liftoff", "status": "not_assessed", "coordinate_confidence": "remote_pending", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "comparative_neighborhoods.tsv", COMPARATIVE_NEIGHBORHOOD_HEADERS, [{"comparative_neighborhood_id": "COMP_NEIGH_MOCK_0001", "candidate_id": candidate_id, "assembly_id": "ASM_MOCK_0001", "anchor_gene_id": candidate_id, "neighbor_summary": "remote_pending", "synteny_status": "not_assessed", "claim_gate": "coordinates_required_for_cluster_claims", "review_status": "needs-human-review"}])

    write_tsv(out_dir / "pav-copy-number.tsv", PAV_COPY_NUMBER_HEADERS, [{"candidate_id": candidate_id, "sample_or_assembly_id": "ASM_MOCK_0001", "presence_status": "not_assessed", "copy_number": "remote_pending", "method": "miniprot_liftoff_or_orthofinder", "evidence_basis": "deferred_until_multiple_assemblies", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "sv-ledger.tsv", SV_LEDGER_HEADERS, [{"sv_id": "SV_MOCK_0001", "candidate_id": candidate_id, "assembly_or_sample_id": "ASM_MOCK_0001", "sv_type": "not_assessed", "interval": "remote_pending", "method": "Sniffles2_or_cuteSV_or_pbsv", "support_status": "deferred", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "candidate_interval_sv.tsv", CANDIDATE_INTERVAL_SV_HEADERS, [{"candidate_id": candidate_id, "interval_id": "INTERVAL_MOCK_0001", "sv_ids": "SV_MOCK_0001", "distance_to_candidate_bp": "0", "functional_risk": "not_assessed", "claim_gate": "sv_context_not_function_validation", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "graph-ledger.tsv", GRAPH_LEDGER_HEADERS, [{"graph_id": "GRAPH_MOCK_0001", "graph_type": "existing_graph_or_deferred", "source": "operator_supplied_or_deferred", "remote_path": f"{heavy_workdir}/inputs/graphs", "coordinate_system": "graph_coordinate_system_pending", "status": "deferred", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "graph_path_support.tsv", GRAPH_PATH_SUPPORT_HEADERS, [{"candidate_id": candidate_id, "graph_id": "GRAPH_MOCK_0001", "path_id": "remote_pending", "support_status": "not_assessed", "coordinate_confidence": "remote_pending", "claim_gate": "graph_support_requires_coordinate_review", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "singlecell-dataset-ledger.tsv", SINGLECELL_DATASET_HEADERS, [{"singlecell_dataset_id": "SC_MOCK_0001", "dataset_id": "not_declared", "technology": "not_declared", "cell_or_spatial_unit": "not_declared", "status": "blocked_without_dataset", "review_status": "needs-human-review"}])
    write_tsv(out_dir / "spatial-domain-expression.tsv", SPATIAL_DOMAIN_EXPRESSION_HEADERS, [{"candidate_id": candidate_id, "domain_or_cell_type": "not_declared", "expression_metric": "not_assessed", "value": "remote_pending", "support_status": "blocked_without_dataset", "claim_gate": "context_only", "review_status": "needs-human-review"}])

    summary = {
        "schema_version": 1,
        "checked_at": utc_now(),
        "workflow_class_plan": str(plan_path),
        "activated_lanes": [row.get("workflow_class") for row in activated],
        "deferred_or_blocked_lanes": [row.get("workflow_class") for row in deferred],
        "mock_tools": mock_tools,
        "runtime_budget": None if runtime_budget is None else runtime_budget.summary(),
        "raw_sequence_emitted": False,
        "ok": bool(workflow_plan.get("workflow_classes")),
    }
    write_json(out_dir / "workflow-class-summary.json", summary)
    return summary


def copy_or_placeholder(src: Path | None, dst: Path, placeholder: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src is not None and src.exists() and src.is_file():
        shutil.copyfile(src, dst)
        return
    write_text(dst, placeholder)


def write_candidate_ranking(out_dir: Path) -> None:
    hits = out_dir / "candidate_hits.tsv"
    rows: list[dict[str, str]] = []
    if hits.exists():
        try:
            rows = read_tsv(hits)
        except Exception:
            rows = []
    ranking_rows = []
    for index, row in enumerate(sorted(rows, key=lambda item: float(item.get("evidence_score") or 0), reverse=True), start=1):
        ranking_rows.append(
            {
                "rank": index,
                "candidate_id": row.get("candidate_id", ""),
                "evidence_score": row.get("evidence_score", "0"),
                "evidence_tier": "mock_summary" if row.get("candidate_id", "").startswith("GCAND_MOCK") else "provider_summary",
                "summary": f"{row.get('query_id', '')} -> {row.get('gene_or_transcript_id', '')}; claim level {row.get('product_claim_level', 'candidate')}",
                "review_status": row.get("review_status", "needs-human-review"),
            }
        )
    if not ranking_rows:
        ranking_rows.append(
            {
                "rank": 1,
                "candidate_id": "candidate_search_blocked",
                "evidence_score": "0",
                "evidence_tier": "blocked",
                "summary": "No candidate rows were produced; review provider search blockers.",
                "review_status": "needs-rerun",
            }
        )
    write_tsv(
        out_dir / "candidate-ranking.tsv",
        ["rank", "candidate_id", "evidence_score", "evidence_tier", "summary", "review_status"],
        ranking_rows,
    )


def write_dossier_package(
    *,
    manifest: dict[str, Any],
    launch_manifest: Path,
    out_dir: Path,
    created_at: str,
    large_artifacts: list[str],
) -> None:
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    write_candidate_ranking(out_dir)

    html = {
        "summary.html": "Summary",
        "clusters.html": "Clusters",
        "evidence.html": "Evidence",
        "provenance.html": "Provenance",
        "review.html": "Review",
    }
    for filename, title in html.items():
        write_text(
            out_dir / filename,
            f"<!doctype html><meta charset=\"utf-8\"><title>{title}</title><h1>{title}</h1><p>Generated summary shell for {manifest['campaign_id']} at {created_at}.</p>\n",
        )
    write_text(
        out_dir / "claim-ledger.md",
        f"# Claim Ledger\n\nCampaign: `{manifest['campaign_id']}`\n\nLarge artifacts remain remote-only:\n\n"
        + "\n".join(f"- `{path}`" for path in large_artifacts)
        + "\n",
    )

    launch_keys = {
        "data-ledger.tsv": "data_ledger",
        "query-ledger.tsv": "query_ledger",
        "resource-ledger.tsv": "resource_ledger",
        "project-goals.yaml": "project_goals",
        "pathway-steps.tsv": "pathway_steps",
        "database-ledger.tsv": "database_ledger",
        "cache-ledger.tsv": "cache_ledger",
    }
    for dst_name, key in launch_keys.items():
        source_value = str(manifest.get(key, ""))
        src = resolve_manifest_path(source_value, launch_manifest.resolve()) if source_value else None
        copy_or_placeholder(src, data_dir / dst_name, f"# missing {key} in launch manifest\n")

    top_level_copies = {
        "candidate_hits.tsv": "candidate_hits.tsv",
        "cluster_neighborhoods.tsv": "cluster_neighborhoods.tsv",
        "candidate-ranking.tsv": "candidate-ranking.tsv",
        "evidence.jsonl": "evidence.jsonl",
        "claim-audit.jsonl": "claim-audit.jsonl",
        "provenance.jsonl": "provenance.jsonl",
        "licenses.tsv": "licenses.tsv",
        "versions.json": "versions.json",
    }
    for src_name, dst_name in top_level_copies.items():
        copy_or_placeholder(out_dir / src_name, data_dir / dst_name, "")

    write_text(data_dir / "citations.bib", "% Add literature citations after provider-side query resolution.\n")
    write_json(
        data_dir / "dossier_index.json",
        {
            "schema_version": 1,
            "campaign_id": manifest["campaign_id"],
            "run_id": manifest["run_id"],
            "created_at": created_at,
            "primary_tables": [
                "candidate_hits.tsv",
                "candidate-ranking.tsv",
                "cluster_neighborhoods.tsv",
                "evidence.jsonl",
                "claim-audit.jsonl",
                "provenance.jsonl",
            ],
        },
    )
    write_text(
        data_dir / "export.xlsx",
        "This prep/mock export is a placeholder. Real provider runs should write a valid Excel workbook summary.\n",
    )


def dossier_artifacts(out_dir: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.name in {"dossier-manifest.json", "run_summary.json"}:
            continue
        rel = path.relative_to(out_dir).as_posix()
        artifacts.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return artifacts


def write_common_outputs(
    *,
    manifest: dict[str, Any],
    launch_manifest: Path,
    out_dir: Path,
    paths: dict[str, Path],
    toolcheck: dict[str, Any] | None,
    db_bootstrap: dict[str, Any] | None,
    data_materialization: dict[str, Any] | None,
    target_db: dict[str, Any] | None,
    cache: dict[str, Any] | None,
    reference_import: dict[str, Any] | None,
    query: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
    anchor_map: dict[str, Any] | None,
    orthology_anchor: dict[str, Any] | None,
    neighborhood_extract: dict[str, Any] | None,
    neighborhood_score: dict[str, Any] | None,
    pathway_completeness: dict[str, Any] | None,
    workflow_classes: dict[str, Any] | None,
    decoy: dict[str, Any] | None,
    runtime_budget: RuntimeBudget | None = None,
) -> Path:
    created_at = utc_now()
    export_evidence_sqlite(out_dir)
    remote_heavy_workdir = str(manifest.get("heavy_workdir", ""))
    summary = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "campaign_id": manifest["campaign_id"],
        "provider_class": manifest["provider_class"],
        "run_scope": manifest["run_scope"],
        "heavy_workdir": manifest["heavy_workdir"],
        "lanes_planned": manifest.get("lanes", []),
        "heavy_execution_performed": bool(
            candidate
            and any(item.get("mode") != "mock" and item.get("status") in {"completed", "cache_hit"} for item in candidate.get("commands_executed", []))
            and not candidate.get("blocked_reasons")
        ),
        "toolcheck_ok": None if toolcheck is None else toolcheck.get("ok"),
        "db_bootstrap_ok": None if db_bootstrap is None else db_bootstrap.get("ok"),
        "data_materialization_ok": None if data_materialization is None else data_materialization.get("ok"),
        "target_db_build_ok": None if target_db is None else target_db.get("ok"),
        "cache_preflight_ok": None if cache is None else cache.get("ok"),
        "reference_import_ok": None if reference_import is None else reference_import.get("ok"),
        "query_preflight_ok": None if query is None else query.get("ok"),
        "decoy_preflight_ok": None if decoy is None else decoy.get("ok"),
        "candidate_search_ok": None if candidate is None else candidate.get("ok"),
        "real_target_search_ok": None if candidate is None else candidate.get("real_target_search_ok"),
        "candidate_rows": 0 if candidate is None else candidate.get("candidate_rows", 0),
        "target_candidate_rows": 0 if candidate is None else candidate.get("target_candidate_rows", 0),
        "reference_candidate_rows": 0 if candidate is None else candidate.get("reference_candidate_rows", 0),
        "placeholder_candidate_rows": 0 if candidate is None else candidate.get("placeholder_candidate_rows", 0),
        "target_search_commands_planned": 0 if candidate is None else candidate.get("target_commands_planned", 0),
        "target_search_commands_completed": 0 if candidate is None else candidate.get("target_commands_completed", 0),
        "anchor_map_ok": None if anchor_map is None else anchor_map.get("ok"),
        "orthology_anchor_ok": None if orthology_anchor is None else orthology_anchor.get("ok"),
        "neighborhood_extract_ok": None if neighborhood_extract is None else neighborhood_extract.get("ok"),
        "neighborhood_score_ok": None if neighborhood_score is None else neighborhood_score.get("ok"),
        "pathway_completeness_ok": None if pathway_completeness is None else pathway_completeness.get("ok"),
        "workflow_classes_ok": None if workflow_classes is None else workflow_classes.get("ok"),
        "workflow_classes_activated": [] if workflow_classes is None else workflow_classes.get("activated_lanes", []),
        "workflow_classes_deferred_or_blocked": [] if workflow_classes is None else workflow_classes.get("deferred_or_blocked_lanes", []),
        "runtime_budget": None if runtime_budget is None else runtime_budget.summary(),
        "large_artifacts_remote_only": {
            "inputs": f"{remote_heavy_workdir}/inputs" if remote_heavy_workdir else str(paths["inputs"]),
            "work": f"{remote_heavy_workdir}/work" if remote_heavy_workdir else str(paths["work"]),
            "databases": f"{remote_heavy_workdir}/databases" if remote_heavy_workdir else str(paths["databases"]),
            "logs": f"{remote_heavy_workdir}/logs" if remote_heavy_workdir else str(paths["logs"]),
        },
        "small_artifacts": sorted(path.name for path in out_dir.glob("*") if path.is_file()),
        "created_at": created_at,
    }
    write_json(out_dir / "run_summary.json", summary)
    runtime_policy = manifest.get("runtime_policy", {}) if isinstance(manifest.get("runtime_policy", {}), dict) else {}
    write_json(
        out_dir / "deferred-lanes.json",
        {
            "schema_version": 1,
            "run_id": manifest["run_id"],
            "run_scope": manifest["run_scope"],
            "runtime_policy": runtime_policy,
            "deferred_by_policy": runtime_policy.get("lane_degradation_order", []),
            "runtime_events": [] if runtime_budget is None else runtime_budget.events,
            "claim_effect": "Deferred lanes may not be used as evidence for product or physical-cluster claims.",
        },
    )
    write_jsonl(
        out_dir / "provenance.jsonl",
        [
            {
                "kind": "remote_runner",
                "campaign_id": manifest["campaign_id"],
                "run_id": manifest["run_id"],
                "created_at": created_at,
                "heavy_workdir": manifest["heavy_workdir"],
            }
        ],
    )
    write_json(
        out_dir / "versions.json",
        {
            "schema_version": 1,
            "runner": "genecluster_remote_runner.py",
            "toolcheck": toolcheck,
            "image": manifest.get("runner", {}).get("image", "unknown"),
        },
    )
    write_text(
        out_dir / "licenses.tsv",
        "resource\tlicense_class\tuse_mode\nBioSymphony GeneCluster remote runner\tpermissive-code\tprovider_container\n",
    )
    write_dossier_package(
        manifest=manifest,
        launch_manifest=launch_manifest,
        out_dir=out_dir,
        created_at=created_at,
        large_artifacts=[
            f"{remote_heavy_workdir}/inputs" if remote_heavy_workdir else str(paths["inputs"]),
            f"{remote_heavy_workdir}/work" if remote_heavy_workdir else str(paths["work"]),
            f"{remote_heavy_workdir}/databases" if remote_heavy_workdir else str(paths["databases"]),
        ],
    )
    write_json(
        out_dir / "dossier-manifest.json",
        {
            "schema_version": 1,
            "campaign_id": manifest["campaign_id"],
            "artifact_policy": "summaries_only",
            "created_at": created_at,
            "artifacts": dossier_artifacts(out_dir),
            "large_artifacts_remote_only": [
                f"{remote_heavy_workdir}/inputs" if remote_heavy_workdir else str(paths["inputs"]),
                f"{remote_heavy_workdir}/work" if remote_heavy_workdir else str(paths["work"]),
                f"{remote_heavy_workdir}/databases" if remote_heavy_workdir else str(paths["databases"]),
            ],
            "validation": [
                {"name": "remote_runner", "status": "passed" if summary["toolcheck_ok"] is not False else "needs-rerun"}
            ],
        },
    )
    summary["small_artifacts"] = sorted(path.name for path in out_dir.glob("*") if path.is_file())
    write_json(out_dir / "run_summary.json", summary)
    return out_dir / "run_summary.json"


def run(
    launch_manifest: Path,
    out: Path | None = None,
    *,
    toolcheck: bool = False,
    db_bootstrap: bool = False,
    data_materialization: bool = False,
    target_db_build: bool = False,
    cache_preflight_flag: bool = False,
    reference_import: bool = False,
    query_preflight_flag: bool = False,
    decoy_preflight_flag: bool = False,
    resolve_queries: bool = False,
    candidate_search: bool = False,
    anchor_map: bool = False,
    orthology_anchor: bool = False,
    neighborhood_extract: bool = False,
    neighborhood_score: bool = False,
    pathway_completeness: bool = False,
    workflow_classes: bool = False,
    full_campaign: bool = False,
    mock_tools: bool = False,
    allow_large_downloads: bool = False,
    window_kb: int = 100,
    window_genes: int = 10,
    max_runtime_hours: float | None = None,
) -> Path:
    manifest = json.loads(launch_manifest.read_text(encoding="utf-8"))
    runtime_budget = RuntimeBudget(max_runtime_hours)
    heavy_workdir = Path(str(manifest.get("heavy_workdir") or Path.cwd() / "genecluster-run"))
    if mock_tools and str(heavy_workdir).startswith("/workspace/"):
        mock_base = os.environ.get("GENECLUSTER_MOCK_WORKDIR") or os.environ.get("TMPDIR") or "/tmp"
        mock_root = Path(mock_base).expanduser().resolve() / "genecluster-mock-workspace"
        heavy_workdir = mock_root / "genecluster" / "runs" / str(manifest.get("run_id", "mock-run"))
    paths = ensure_remote_layout(heavy_workdir)
    out_dir = out or paths["summary"]
    out_dir.mkdir(parents=True, exist_ok=True)
    helper_manifest = launch_manifest
    if mock_tools:
        patched_manifest = dict(manifest)
        patched_manifest["heavy_workdir"] = str(heavy_workdir)
        patched_manifest["summary_outdir"] = str(out_dir)
        for key in [
            "campaign_manifest",
            "data_ledger",
            "query_ledger",
            "resource_ledger",
            "project_goals",
            "pathway_steps",
            "database_ledger",
            "cache_ledger",
            "query_fasta",
            "db_bootstrap_plan",
            "data_materialization_plan",
            "target_db_plan",
            "reference_import_plan",
            "anchor_map_plan",
            "neighborhood_extract_plan",
            "orthology_anchor_plan",
            "reciprocal_search_plan",
            "pathway_completeness_plan",
            "query_resolution_plan",
            "decoy_plan",
            "run_economics",
            "workflow_class_plan",
            "lane_activation_plan",
            "evidence_escalation_plan",
            "claim_levels",
            "workflow_deferred_lanes",
            "search_plan",
            "tool_requirements",
            "provider_payload",
        ]:
            value = str(patched_manifest.get(key, ""))
            if value:
                patched_manifest[key] = str(resolve_manifest_path(value, launch_manifest.resolve()))
        helper_manifest = out_dir / "mock-launch-manifest.json"
        write_json(helper_manifest, patched_manifest)
    scope_full = full_campaign or str(manifest.get("run_scope", "")) in {"full_campaign", "full_campaign_24h", "full_public_mining"}

    tool_result = None
    db_bootstrap_result = None
    data_materialization_result = None
    target_db_result = None
    cache_result = None
    reference_result = None
    query_result = None
    decoy_result = None
    candidate_result = None
    anchor_result = None
    orthology_result = None
    neighborhood_result = None
    neighborhood_score_result = None
    pathway_completeness_result = None
    workflow_class_result = None
    def maybe_run_stage(enabled: bool, stage_id: str, reserve_seconds: int, action: Any) -> Any:
        if not enabled:
            return None
        if not runtime_budget.can_start(stage_id, reserve_seconds=reserve_seconds):
            append_stage_progress(
                out_dir,
                stage_id,
                "skipped_runtime_budget_exhausted",
                elapsed_seconds=round(runtime_budget.elapsed_seconds(), 3),
                remaining_seconds=runtime_budget.remaining_seconds(),
            )
            return None
        append_stage_progress(out_dir, stage_id, "started", elapsed_seconds=round(runtime_budget.elapsed_seconds(), 3))
        try:
            result = action()
        except Exception as exc:
            append_stage_progress(
                out_dir,
                stage_id,
                "failed",
                elapsed_seconds=round(runtime_budget.elapsed_seconds(), 3),
                error=str(exc)[:500],
            )
            raise
        status = "completed"
        if isinstance(result, dict) and result.get("ok") is False:
            status = "completed_with_blockers"
        append_stage_progress(
            out_dir,
            stage_id,
            status,
            elapsed_seconds=round(runtime_budget.elapsed_seconds(), 3),
            result_ok=result.get("ok") if isinstance(result, dict) else None,
        )
        return result

    def run_toolcheck() -> dict[str, Any]:
        result = check_tools(mock_tools=mock_tools)
        write_json(out_dir / "toolcheck.json", result)
        return result

    tool_result = maybe_run_stage(toolcheck, "toolcheck", 60, run_toolcheck)
    db_bootstrap_result = maybe_run_stage(
        db_bootstrap,
        "db_bootstrap",
        60,
        lambda: run_provider_helper(
            "genecluster_db_bootstrap",
            "db-bootstrap-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
            extra_kwargs={"allow_large_downloads": allow_large_downloads},
        ),
    )
    data_materialization_result = maybe_run_stage(
        data_materialization or scope_full,
        "data_materialization",
        300,
        lambda: run_provider_helper(
            "genecluster_data_materialization",
            "data-materialization-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
            extra_kwargs={"allow_large_downloads": allow_large_downloads},
        ),
    )
    target_db_result = maybe_run_stage(
        target_db_build or scope_full,
        "target_db_build",
        60,
        lambda: run_provider_helper(
            "genecluster_target_db_builder",
            "target-db-build-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
        ),
    )

    def run_cache_preflight_stage() -> dict[str, Any]:
        result = cache_preflight(manifest, launch_manifest, paths, mock_tools=mock_tools)
        write_json(out_dir / "cache-preflight.json", result)
        return result

    cache_result = maybe_run_stage(cache_preflight_flag, "cache_preflight", 60, run_cache_preflight_stage)
    reference_result = maybe_run_stage(
        reference_import,
        "reference_import",
        60,
        lambda: run_provider_helper(
            "genecluster_reference_import",
            "reference-import-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
            extra_kwargs={"allow_reference_downloads": allow_large_downloads},
        ),
    )

    def run_query_preflight_stage() -> dict[str, Any]:
        result = query_preflight(
            manifest,
            launch_manifest,
            paths,
            mock_tools=mock_tools,
            resolve_queries=resolve_queries,
        )
        write_json(out_dir / "query-preflight.json", result)
        return result

    query_result = maybe_run_stage(query_preflight_flag, "query_preflight", 60, run_query_preflight_stage)

    def run_decoy_preflight_stage() -> dict[str, Any]:
        result = decoy_preflight(manifest, launch_manifest)
        write_json(out_dir / "decoy-preflight.json", result)
        return result

    decoy_result = maybe_run_stage(decoy_preflight_flag, "decoy_preflight", 60, run_decoy_preflight_stage)

    def run_candidate_search_stage() -> dict[str, Any]:
        target_prereq_reasons: list[str] = []
        if scope_full and data_materialization_result is not None and data_materialization_result.get("ok") is False:
            target_prereq_reasons.append("data materialization failed; target-organism search is blocked")
        if scope_full and target_db_result is not None and target_db_result.get("ok") is False:
            target_prereq_reasons.append("target DB build failed; target-organism search is blocked")
        if target_prereq_reasons:
            return write_blocked_candidate_search(out_dir, target_prereq_reasons)
        return run_candidate_search(
            manifest,
            launch_manifest,
            paths,
            out_dir,
            mock_tools=mock_tools,
            runtime_budget=runtime_budget,
        )

    candidate_result = maybe_run_stage(candidate_search or scope_full, "candidate_search", 120, run_candidate_search_stage)
    if mock_tools and (anchor_map or neighborhood_extract or scope_full):
        write_mock_genome_context(paths)
    anchor_result = maybe_run_stage(
        anchor_map or scope_full,
        "anchor_map",
        120,
        lambda: run_provider_helper(
            "genecluster_anchor_map",
            "anchor-map-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
        ),
    )
    orthology_result = maybe_run_stage(
        orthology_anchor or scope_full,
        "orthology_anchor",
        120,
        lambda: run_provider_helper(
            "genecluster_orthology_anchor",
            "orthology-anchor-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
        ),
    )
    neighborhood_result = maybe_run_stage(
        neighborhood_extract or scope_full,
        "neighborhood_extract",
        120,
        lambda: run_provider_helper(
            "genecluster_neighborhood_extract",
            "neighborhood-extract-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
            extra_kwargs={"window_kb": window_kb, "window_genes": window_genes},
        ),
    )
    neighborhood_score_result = maybe_run_stage(
        neighborhood_score or scope_full,
        "neighborhood_score",
        120,
        lambda: run_provider_helper(
            "genecluster_neighborhood_score",
            "neighborhood-score-summary.json",
            helper_manifest,
            out_dir,
            dry_run=mock_tools,
            mock_tools=mock_tools,
        ),
    )
    pathway_completeness_result = maybe_run_stage(
        pathway_completeness or scope_full,
        "pathway_completeness",
        60,
        lambda: run_pathway_completeness(
            manifest,
            launch_manifest,
            out_dir,
            runtime_budget=runtime_budget,
        ),
    )
    workflow_class_result = maybe_run_stage(
        workflow_classes or scope_full,
        "workflow_classes",
        60,
        lambda: run_workflow_classes(
            manifest,
            launch_manifest,
            paths,
            out_dir,
            mock_tools=mock_tools,
            runtime_budget=runtime_budget,
        ),
    )
    return write_common_outputs(
        manifest=manifest,
        launch_manifest=launch_manifest,
        out_dir=out_dir,
        paths=paths,
        toolcheck=tool_result,
        db_bootstrap=db_bootstrap_result,
        data_materialization=data_materialization_result,
        target_db=target_db_result,
        cache=cache_result,
        reference_import=reference_result,
        query=query_result,
        decoy=decoy_result,
        candidate=candidate_result,
        anchor_map=anchor_result,
        orthology_anchor=orthology_result,
        neighborhood_extract=neighborhood_result,
        neighborhood_score=neighborhood_score_result,
        pathway_completeness=pathway_completeness_result,
        workflow_classes=workflow_class_result,
        runtime_budget=runtime_budget,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GeneCluster provider-side preflight/search lanes.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Output directory for compact runner summaries.")
    parser.add_argument("--toolcheck", action="store_true", help="Check provider-side tool availability.")
    parser.add_argument("--db-bootstrap", action="store_true", help="Prepare/check provider DB cache paths and safe local DB builds.")
    parser.add_argument("--data-materialization", action="store_true", help="Materialize provider-side target sequences from approved raw/public inputs.")
    parser.add_argument("--target-db-build", action="store_true", help="Build/check target species DB indexes under provider storage.")
    parser.add_argument("--cache-preflight", action="store_true", help="Create/check provider cache/workdir layout and DB ledger.")
    parser.add_argument("--reference-import", action="store_true", help="Resolve/import public provider-side reference summaries.")
    parser.add_argument("--query-preflight", action="store_true", help="Check provider-side query FASTA/resolution readiness.")
    parser.add_argument("--resolve-queries", action="store_true", help="Resolve public protein accessions to provider-side query FASTA.")
    parser.add_argument("--decoy-preflight", action="store_true", help="Validate broad-family decoy/negative-control plan.")
    parser.add_argument("--candidate-search", action="store_true", help="Run or validate provider-local candidate search.")
    parser.add_argument("--anchor-map", action="store_true", help="Map candidate summaries onto provider-side genome/GFF coordinates.")
    parser.add_argument("--orthology-anchor", action="store_true", help="Summarize reciprocal/orthology support and anchor confidence ladder.")
    parser.add_argument("--neighborhood-extract", action="store_true", help="Extract summary-only neighborhoods around anchored candidates.")
    parser.add_argument("--neighborhood-score", action="store_true", help="Score neighboring-gene hypotheses with claim-safe labels.")
    parser.add_argument("--pathway-completeness", action="store_true", help="Render pathway completeness matrix.")
    parser.add_argument("--workflow-classes", action="store_true", help="Render workflow-class ledgers and activation/deferred summaries.")
    parser.add_argument("--full-campaign", action="store_true", help="Run full Coptis readiness lane set; currently includes search-gated summaries.")
    parser.add_argument("--window-kb", type=int, default=100, help="Neighborhood window radius in kilobases.")
    parser.add_argument("--window-genes", type=int, default=10, help="Neighbor gene count on either side of anchor.")
    parser.add_argument("--max-runtime-hours", type=float, help="Stop starting new stages after this runtime budget.")
    parser.add_argument("--allow-large-downloads", action="store_true", help="Permit required large provider-side database downloads/builds.")
    parser.add_argument("--mock-tools", action="store_true", help="Mock tools and candidate summaries for local dry-run tests only.")
    args = parser.parse_args()
    print(
        run(
            args.launch_manifest,
            args.out,
            toolcheck=args.toolcheck,
            db_bootstrap=args.db_bootstrap,
            data_materialization=args.data_materialization,
            target_db_build=args.target_db_build,
            cache_preflight_flag=args.cache_preflight,
            reference_import=args.reference_import,
            query_preflight_flag=args.query_preflight,
            decoy_preflight_flag=args.decoy_preflight,
            resolve_queries=args.resolve_queries,
            candidate_search=args.candidate_search,
            anchor_map=args.anchor_map,
            orthology_anchor=args.orthology_anchor,
            neighborhood_extract=args.neighborhood_extract,
            neighborhood_score=args.neighborhood_score,
            pathway_completeness=args.pathway_completeness,
            workflow_classes=args.workflow_classes,
            full_campaign=args.full_campaign,
            mock_tools=args.mock_tools,
            allow_large_downloads=args.allow_large_downloads,
            window_kb=args.window_kb,
            window_genes=args.window_genes,
            max_runtime_hours=args.max_runtime_hours,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
