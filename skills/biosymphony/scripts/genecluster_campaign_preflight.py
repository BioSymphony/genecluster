#!/usr/bin/env python3
"""genecluster_campaign_preflight, mandatory Stage 0 wrapper for BioSymphony.

Every campaign launch must begin with this preflight. It orchestrates the
"early data research" step that decides whether the campaign is ready to enter
the maturity ladder (L0 → L1 → ...).

Two modes:

  user-supplied
    If the operator passes ``--comparative-species`` AND ``--seed-queries``,
    the preflight only *validates* those against the catalog and produces the
    readiness JSON. No agent dispatch required.

  auto-discover (default when comparators/queries are missing)
    Invokes ``genecluster_species_scout.py`` to fan out across the catalog +
    tax-walk. Then optionally hands off to a literature-audit agent for the
    novelty + importance sections.

Output contract, ``campaign-launch-readiness.json``, is consumed by all
downstream genecluster_* scripts. They MUST refuse to proceed unless this
file exists with ``preflight_status == "ready"``.

CLI

  ./genecluster_campaign_preflight.py \\
      --target "Coptis chinensis" \\
      --pathway BIA \\
      --campaign-id coptis-bia-example \\
      --out-dir .runtime/<campaign-id>-preflight \\
      [--comparative-species "Berberis vulgaris,Coptis teeta,Eschscholzia californica"] \\
      [--seed-queries-tsv path/to/queries.tsv] \\
      [--require-novelty-audit]            # forces lit-audit, even if catalog has rows
      [--catalog data/pathway-species-catalog.tsv]
      [--ncbi-api-key $NCBI_API_KEY]

Exit codes
  0  preflight passed, readiness JSON written
  1  argument error
  2  scout failed
  3  validation failed (operator-supplied data didn't pass)
  4  novelty audit required but agent dispatch not configured
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCOUT_NAME = "genecluster_species_scout.py"
DEFAULT_CATALOG = Path("data/pathway-species-catalog.tsv")
READINESS_SCHEMA_VERSION = "1.0"


def log(msg: str, *, level: str = "INFO") -> None:
    sys.stderr.write(f"[campaign-preflight {level}] {msg}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# Catalog helpers (mirrored from species_scout for self-contained validation)
# ---------------------------------------------------------------------------


def read_catalog(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            rows.append({(k or ""): (v or "").strip() for k, v in row.items()})
    return rows


def catalog_match_pathway(rows: list[dict[str, str]], pathway: str) -> list[dict[str, str]]:
    pathway_norm = pathway.strip().lower()
    return [
        row for row in rows
        if row.get("pathway_id", "").lower() == pathway_norm
        or pathway_norm in (row.get("pathway_name", "") or "").lower()
    ]


def find_catalog_row(rows: list[dict[str, str]], species: str) -> dict[str, str] | None:
    species_norm = species.strip().lower()
    for row in rows:
        if (row.get("species", "") or "").lower() == species_norm:
            return row
    return None


# ---------------------------------------------------------------------------
# Validation of operator-supplied comparators
# ---------------------------------------------------------------------------


def validate_user_comparators(
    comparators: list[str],
    pathway: str,
    catalog_rows: list[dict[str, str]],
) -> dict[str, Any]:
    """Cross-check supplied comparators against the catalog.

    Each row gets one of these verdicts:
        catalog_match, exact pathway-aligned species exists in catalog
        cross_pathway, species in catalog but different pathway (flag)
        unknown      , not in catalog (will need scout + audit)
    """
    verdicts: list[dict[str, Any]] = []
    pathway_matches = catalog_match_pathway(catalog_rows, pathway)
    pathway_species = {row.get("species", "") for row in pathway_matches}
    for sp in comparators:
        sp = sp.strip()
        if not sp:
            continue
        verdict: dict[str, Any] = {"species": sp}
        if sp in pathway_species:
            row = find_catalog_row(catalog_rows, sp)
            verdict["verdict"] = "catalog_match"
            verdict["catalog_row"] = row
        else:
            cross = find_catalog_row(catalog_rows, sp)
            if cross is not None:
                verdict["verdict"] = "cross_pathway"
                verdict["catalog_row"] = cross
                verdict["note"] = (
                    f"species in catalog under pathway "
                    f"{cross.get('pathway_id', '?')} (≠ {pathway})"
                )
            else:
                verdict["verdict"] = "unknown"
                verdict["note"] = "not in catalog; will be tax-walk-resolved"
        verdicts.append(verdict)
    return {
        "comparators": comparators,
        "pathway": pathway,
        "verdicts": verdicts,
        "all_known": all(v["verdict"] == "catalog_match" for v in verdicts) if verdicts else False,
    }


def validate_user_seed_queries(seed_tsv: Path) -> dict[str, Any]:
    """Light shape check on user-supplied seed-queries TSV."""
    if not seed_tsv.exists():
        return {"present": False, "error": "seed-queries file not found"}
    required_cols = {"query_id", "enzyme_name", "uniprot"}
    rows: list[dict[str, str]] = []
    with seed_tsv.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            return {"present": True, "error": f"missing columns: {sorted(missing)}"}
        for row in reader:
            rows.append({(k or ""): (v or "").strip() for k, v in row.items()})

    issues: list[str] = []
    seen_ids: set[str] = set()
    has_actin = has_gapdh = has_neg = False
    for row in rows:
        qid = row.get("query_id", "")
        if not qid:
            issues.append("empty query_id row")
            continue
        if qid in seen_ids:
            issues.append(f"duplicate query_id: {qid}")
        seen_ids.add(qid)
        role = (row.get("role", "") or "").lower()
        if not row.get("uniprot") and "control" not in role:
            issues.append(f"missing uniprot anchor: {qid}")
        # Detect control markers across multiple fields so users can either
        # encode controls in the query_id (POSCTRL_ACTIN), enzyme_name (Actin),
        # or role (positive control / negative control).
        haystack = " ".join([
            qid, row.get("enzyme_name", ""), row.get("notes", ""), role,
        ]).upper()
        if "ACTIN" in haystack or "ACT2" in haystack:
            has_actin = True
        if "GAPDH" in haystack:
            has_gapdh = True
        if any(token in haystack for token in ("NEGCTRL", "RANDOM", "SHUFFLE", "SHUFFLED", "NEGATIVE CONTROL")):
            has_neg = True

    if not has_actin:
        issues.append("missing positive control: ACTIN")
    if not has_gapdh:
        issues.append("missing positive control: GAPDH")
    if not has_neg:
        issues.append("missing negative control: shuffled sequence")

    return {
        "present": True,
        "row_count": len(rows),
        "issues": issues,
        "ok": not issues,
    }


# ---------------------------------------------------------------------------
# Scout dispatch
# ---------------------------------------------------------------------------


def run_scout(
    scout_path: Path,
    *,
    target: str,
    pathway: str,
    out_dir: Path,
    catalog: Path,
    related: list[str],
    max_candidates: int,
    api_key: str,
    dry_run: bool,
) -> int:
    """Invoke the species scout as a subprocess; return exit code."""
    cmd = [
        sys.executable,
        str(scout_path),
        "--target", target,
        "--pathway", pathway,
        "--out-dir", str(out_dir),
        "--catalog", str(catalog),
        "--max-candidates", str(max_candidates),
    ]
    if related:
        cmd += ["--related-species", ",".join(related)]
    if api_key:
        cmd += ["--ncbi-api-key", api_key]
    if dry_run:
        cmd += ["--dry-run"]
    log("dispatching scout: " + " ".join(cmd[:6] + ["..."]))
    result = subprocess.run(cmd, check=False)
    return result.returncode


# ---------------------------------------------------------------------------
# Composite preflight report
# ---------------------------------------------------------------------------


def load_scout_output(out_dir: Path) -> dict[str, Any]:
    scout_json = out_dir / "species_scout.json"
    if not scout_json.exists():
        return {}
    return json.loads(scout_json.read_text(encoding="utf-8"))


def compose_readiness(
    *,
    campaign_id: str,
    target: str,
    pathway: str,
    out_dir: Path,
    scout_data: dict[str, Any],
    user_comparators: dict[str, Any] | None,
    user_seed_validation: dict[str, Any] | None,
    novelty_audit_requested: bool,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = scout_data.get("candidates", []) or []
    ranked = sorted(candidates, key=lambda c: -c.get("composite_score", 0))
    top_three = [c["species"] for c in ranked if c.get("role") != "target"][:3]
    catalog_match_count = scout_data.get("catalog_pathway_matches", 0)
    seed_count = len(scout_data.get("seed_queries", []) or [])

    status_reasons: list[str] = []
    status = "ready"

    if not candidates:
        status = "blocked"
        status_reasons.append("scout produced no candidates")
    if user_seed_validation and user_seed_validation.get("present") and not user_seed_validation.get("ok"):
        status = "blocked"
        status_reasons.append("user-supplied seed queries failed validation")
    if novelty_audit_requested and not (out_dir / "novelty-audit.md").exists():
        status = "needs_audit"
        status_reasons.append("novelty audit requested but no novelty-audit.md present")

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "campaign_id": campaign_id,
        "target": target,
        "pathway": pathway,
        "preflight_status": status,
        "status_reasons": status_reasons,
        "out_dir": str(out_dir),
        "catalog_pathway_matches": catalog_match_count,
        "candidate_count": len(candidates),
        "top_three_comparators": top_three,
        "seed_query_candidates": seed_count,
        "user_comparators": user_comparators,
        "user_seed_validation": user_seed_validation,
        "kegg_map_id": scout_data.get("kegg_map_id", ""),
        "novelty_audit_requested": novelty_audit_requested,
        "scout_version": scout_data.get("scout_version", ""),
        "artifacts": {
            "species_scout_tsv": str(out_dir / "species_scout.tsv"),
            "species_scout_json": str(out_dir / "species_scout.json"),
            "relevance_novelty_summary": str(out_dir / "relevance-novelty-summary.md"),
            "seed_query_candidates": str(out_dir / "seed-query-candidates.tsv"),
        },
    }


def write_readiness(readiness: dict[str, Any], out_dir: Path) -> Path:
    path = out_dir / "campaign-launch-readiness.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(readiness, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_preflight_summary(readiness: dict[str, Any], out_dir: Path) -> Path:
    """Render a top-level Markdown report linking scout + validation outputs."""
    md: list[str] = []
    md.append(f"# Campaign preflight summary, {readiness['campaign_id']}")
    md.append("")
    md.append(f"_Generated by `genecluster_campaign_preflight.py` on {readiness['generated_at']}_")
    md.append("")
    md.append("| Field | Value |")
    md.append("|---|---|")
    md.append(f"| Target species | {readiness['target']} |")
    md.append(f"| Pathway | {readiness['pathway']} |")
    md.append(f"| Preflight status | **{readiness['preflight_status'].upper()}** |")
    md.append(f"| Catalog matches | {readiness['catalog_pathway_matches']} |")
    md.append(f"| Candidates evaluated | {readiness['candidate_count']} |")
    md.append(f"| Top 3 comparators | {', '.join(readiness['top_three_comparators']) or ', '} |")
    md.append(f"| KEGG map | {readiness['kegg_map_id'] or ', '} |")
    md.append(f"| Seed query candidates | {readiness['seed_query_candidates']} |")
    md.append("")
    if readiness["status_reasons"]:
        md.append("## Status reasons")
        md.append("")
        for reason in readiness["status_reasons"]:
            md.append(f"- {reason}")
        md.append("")
    if readiness.get("user_comparators"):
        md.append("## User-supplied comparators")
        md.append("")
        md.append("| Species | Verdict | Note |")
        md.append("|---|---|---|")
        for v in readiness["user_comparators"].get("verdicts", []):
            md.append(f"| {v.get('species', '')} | {v.get('verdict', '')} | {v.get('note', ', ')} |")
        md.append("")
    if readiness.get("user_seed_validation"):
        v = readiness["user_seed_validation"]
        md.append("## User-supplied seed queries")
        md.append("")
        md.append(f"- Rows: {v.get('row_count', 0)}")
        md.append(f"- Valid: {'yes' if v.get('ok') else 'no'}")
        for issue in v.get("issues", []) or []:
            md.append(f"  - {issue}")
        md.append("")
    md.append("## Cross-references")
    md.append("")
    md.append(f"- Species scout TSV: `{readiness['artifacts']['species_scout_tsv']}`")
    md.append(f"- Species scout JSON: `{readiness['artifacts']['species_scout_json']}`")
    md.append(f"- Relevance + novelty summary: `{readiness['artifacts']['relevance_novelty_summary']}`")
    md.append(f"- Seed query candidates: `{readiness['artifacts']['seed_query_candidates']}`")
    md.append("")
    md.append("---")
    md.append("")
    md.append("**Downstream contract:** all `genecluster_*` scripts must check this file before proceeding. ")
    md.append("If `preflight_status != \"ready\"`, the campaign is blocked.")
    path = out_dir / "campaign-preflight-summary.md"
    path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BioSymphony Stage 0 campaign preflight.")
    parser.add_argument("--target", required=True, help="Target species binomial.")
    parser.add_argument("--pathway", required=True, help="Pathway id (BIA / MIA / KEGG map id / full name).")
    parser.add_argument("--campaign-id", required=True, help="Campaign identifier, e.g. campaign-Coptis.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory for preflight artifacts.")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG,
                        help="Pathway-species catalog TSV.")
    parser.add_argument("--comparative-species", default="",
                        help="Comma-separated explicit comparators (skips auto-discovery).")
    parser.add_argument("--seed-queries-tsv", type=Path,
                        help="Operator-supplied seed-queries TSV (skips KEGG-derived candidates).")
    parser.add_argument("--max-candidates", type=int, default=12)
    parser.add_argument("--require-novelty-audit", action="store_true",
                        help="Block readiness until novelty-audit.md exists.")
    parser.add_argument("--ncbi-api-key", default=os.environ.get("NCBI_API_KEY", ""))
    parser.add_argument("--scout", type=Path,
                        help="Path to genecluster_species_scout.py (defaults to sibling script).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run scout in dry-run mode (no NCBI/SRA/NGDC fetches).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    target = args.target.strip()
    pathway = args.pathway.strip()
    if not target or not pathway:
        log("--target and --pathway are required", level="ERROR")
        return 1

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    scout_path = args.scout
    if not scout_path:
        scout_path = Path(__file__).parent / SCOUT_NAME
    if not scout_path.exists():
        # fallback: try PATH
        which = shutil.which(SCOUT_NAME)
        if which:
            scout_path = Path(which)
    if not scout_path.exists():
        log(f"cannot find {SCOUT_NAME}; expected sibling or on PATH", level="ERROR")
        return 1

    catalog_rows = read_catalog(args.catalog)
    log(f"loaded catalog with {len(catalog_rows)} rows from {args.catalog}")

    related = [s for s in (args.comparative_species.split(",") if args.comparative_species else []) if s.strip()]
    user_comparator_validation: dict[str, Any] | None = None
    if related:
        user_comparator_validation = validate_user_comparators(related, pathway, catalog_rows)
        log(f"validated {len(related)} user-supplied comparators "
            f"(all_known={user_comparator_validation['all_known']})")

    user_seed_validation: dict[str, Any] | None = None
    if args.seed_queries_tsv:
        user_seed_validation = validate_user_seed_queries(args.seed_queries_tsv)
        log(f"validated user-supplied seed queries: ok={user_seed_validation.get('ok')}")

    scout_rc = run_scout(
        scout_path,
        target=target,
        pathway=pathway,
        out_dir=out_dir,
        catalog=args.catalog,
        related=related,
        max_candidates=args.max_candidates,
        api_key=args.ncbi_api_key,
        dry_run=args.dry_run,
    )
    if scout_rc != 0:
        log(f"scout exited with code {scout_rc}", level="ERROR")
        return 2

    scout_data = load_scout_output(out_dir)
    readiness = compose_readiness(
        campaign_id=args.campaign_id,
        target=target,
        pathway=pathway,
        out_dir=out_dir,
        scout_data=scout_data,
        user_comparators=user_comparator_validation,
        user_seed_validation=user_seed_validation,
        novelty_audit_requested=args.require_novelty_audit,
    )
    readiness_path = write_readiness(readiness, out_dir)
    summary_path = render_preflight_summary(readiness, out_dir)
    log(f"wrote {readiness_path}")
    log(f"wrote {summary_path}")

    if readiness["preflight_status"] == "blocked":
        log("preflight BLOCKED, see status_reasons in the readiness JSON", level="ERROR")
        return 3
    if readiness["preflight_status"] == "needs_audit":
        log("preflight needs novelty audit before downstream stages can proceed", level="WARN")
        return 4
    log("preflight READY, downstream stages may proceed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
