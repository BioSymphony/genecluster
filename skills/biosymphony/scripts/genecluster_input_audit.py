#!/usr/bin/env python3
"""Audit GeneCluster bundle inputs before asking the operator questions.

This is an operator-friction guardrail. A worker should read the campaign
bundle, summarize known data/query/resource inputs, and ask only for genuinely
missing items. It prevents the failure mode where an agent asks for accessions
or links that are already present in `ledgers/data-ledger.tsv`.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


INTERVIEW_MODES = {"quick", "standard", "strict", "skip"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def compact_row(row: dict[str, str], fields: list[str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in fields if row.get(field, "")}


def _short(value: Any) -> str:
    return str(value or "").strip()


def _add_question(
    questions: list[dict[str, Any]],
    *,
    question_id: str,
    question: str,
    why: str,
    default_if_skipped: str,
    blocking: bool,
    category: str,
    answered_by: str = "",
) -> None:
    questions.append(
        {
            "question_id": question_id,
            "category": category,
            "question": question,
            "why": why,
            "default_if_skipped": default_if_skipped,
            "blocking": blocking,
            "answered_by": answered_by,
        }
    )


def build_intake_interview(
    *,
    mode: str,
    manifest: dict[str, Any],
    campaign: dict[str, Any],
    data_rows: list[dict[str, str]],
    query_rows: list[dict[str, str]],
    query_resolution: dict[str, Any],
    candidate_route_plan: dict[str, Any],
    run_economics: dict[str, Any],
) -> dict[str, Any]:
    if mode not in INTERVIEW_MODES:
        raise ValueError(f"unknown interview mode: {mode}")

    known: list[dict[str, str]] = []
    assumptions: list[dict[str, str]] = []
    questions: list[dict[str, Any]] = []

    if campaign.get("target_pathway"):
        known.append({"topic": "biological_goal", "value": _short(campaign.get("target_pathway")), "source": "campaign-manifest.json"})
    else:
        _add_question(
            questions,
            question_id="goal_target_pathway",
            category="biology",
            question="What pathway, metabolite, gene family, or pathway interval is the campaign trying to resolve?",
            why="The route planner needs a biological target to score pathway completeness and claim boundaries.",
            default_if_skipped="Treat the pathway as user-provided free text and label completeness as review_required.",
            blocking=(mode == "strict"),
        )

    if data_rows:
        accessions = ", ".join(row.get("accession", "") for row in data_rows if row.get("accession")) or f"{len(data_rows)} data rows"
        known.append({"topic": "data_scope", "value": accessions, "source": "ledgers/data-ledger.tsv"})
    else:
        _add_question(
            questions,
            question_id="data_scope",
            category="data",
            question="Which target datasets are in scope, and which should be skipped?",
            why="No data rows were found, so the agent cannot infer target resources.",
            default_if_skipped="Do not launch heavy compute; generate a local-lite planning bundle only.",
            blocking=True,
        )

    if query_rows:
        known.append({"topic": "query_scope", "value": f"{len(query_rows)} query ledger rows", "source": "ledgers/query-ledger.tsv"})
    else:
        _add_question(
            questions,
            question_id="query_scope",
            category="queries",
            question="What canonical genes/proteins/domains should seed the search?",
            why="Candidate discovery needs at least one seed or domain model.",
            default_if_skipped="Create an empty query ledger and stop at intake/preflight.",
            blocking=True,
        )

    unresolved_high = [
        row
        for row in query_resolution.get("records", [])
        if (
            row.get("confidence") == "high"
            and row.get("curation_status") != "resolved"
            and row.get("resolution_action") != "use_embedded_query_fasta"
        )
    ]
    if unresolved_high:
        _add_question(
            questions,
            question_id="resolve_high_confidence_queries",
            category="queries",
            question="Should the unresolved high-confidence query seeds be resolved now, downgraded to context-only, or excluded?",
            why="High-confidence unresolved seeds can block execution-ready validation.",
            default_if_skipped="Keep them as blockers for strict/heavy launch; allow local-lite planning only.",
            blocking=(mode in {"standard", "strict"}),
            answered_by="query-resolution-plan.json",
        )

    provider = _short(manifest.get("provider_class"))
    run_scope = _short(manifest.get("run_scope"))
    if provider and run_scope:
        known.append({"topic": "compute_policy", "value": f"{provider} / {run_scope}", "source": "launch-manifest.json"})
    else:
        _add_question(
            questions,
            question_id="compute_policy",
            category="compute",
            question="Should this run local-lite, local-full, RunPod, SSH/HPC, or another cloud profile?",
            why="Heavy data and artifact boundaries depend on the provider.",
            default_if_skipped="Use local_lite planning only; no raw downloads.",
            blocking=True,
        )

    route = _short(candidate_route_plan.get("primary_route"))
    readiness = _short(candidate_route_plan.get("science_readiness"))
    if route:
        known.append({"topic": "scientific_route", "value": f"{route}; readiness={readiness}", "source": "candidate-route-plan.json"})
    else:
        _add_question(
            questions,
            question_id="scientific_route",
            category="route",
            question="Should transcript evidence be primary, or is direct genome rescue acceptable for this campaign?",
            why="Genome-first search can miss or fragment multi-exon genes when transcript evidence is available.",
            default_if_skipped="Use transcript-first when transcriptome evidence exists; direct genome search is rescue only.",
            blocking=(mode == "strict"),
        )

    strict_blockers = [str(item) for item in candidate_route_plan.get("strict_scientific_blockers", [])]
    missing_transcript_first = candidate_route_plan.get("missing_transcript_first_stages", [])
    if strict_blockers and mode != "skip":
        _add_question(
            questions,
            question_id="route_blocker_decision",
            category="route",
            question="The route audit says strict transcript-first readiness is blocked. Should the run be downgraded to candidate-smoke/rescue, or should the missing transcript-first stages be implemented first?",
            why="A technically launchable target-nucleotide search is not the same as a full transcript-first discovery workflow.",
            default_if_skipped="Downgrade language to candidate-smoke/rescue and keep strict full-route claims blocked.",
            blocking=(mode == "strict"),
            answered_by="candidate-route-plan.json",
        )
        assumptions.append(
            {
                "topic": "route_claim_level",
                "assumption": "Do not claim full transcript-first discovery until strict route audit passes.",
                "source": "candidate-route-plan.json",
            }
        )
        if missing_transcript_first:
            assumptions.append(
                {
                    "topic": "missing_transcript_first_stages",
                    "assumption": f"{len(missing_transcript_first)} stages remain before full transcript-first readiness.",
                    "source": "candidate-route-plan.json",
                }
            )

    runtime_budget = run_economics.get("runtime_budget") or manifest.get("runtime_policy") or {}
    if isinstance(runtime_budget, dict) and runtime_budget.get("target_runtime_hours"):
        known.append(
            {
                "topic": "runtime_budget",
                "value": f"{runtime_budget.get('target_runtime_hours')}h target; policy={runtime_budget.get('budget_policy', '')}",
                "source": "run-economics.json",
            }
        )
    elif mode in {"standard", "strict"}:
        _add_question(
            questions,
            question_id="runtime_budget",
            category="compute",
            question="What runtime or budget cap should govern optional lanes?",
            why="Workflow lanes need clear deferral rules when time or cost is constrained.",
            default_if_skipped="Use the scope default and record deferred_by_budget rows.",
            blocking=False,
        )

    if manifest.get("expected_artifacts"):
        known.append({"topic": "outputs", "value": f"{len(manifest.get('expected_artifacts', []))} expected summary artifacts", "source": "launch-manifest.json"})
    elif mode in {"standard", "strict"}:
        _add_question(
            questions,
            question_id="outputs",
            category="outputs",
            question="Which outputs are required: candidate table, cluster windows, Excel, interactive dossier, Linear issues, or all?",
            why="Output requirements drive summary artifact validation.",
            default_if_skipped="Use the default GeneCluster dossier plus TSV/JSONL/Excel summaries.",
            blocking=False,
        )

    if mode == "skip":
        questions = []
        assumptions.append(
            {
                "topic": "operator_interview",
                "assumption": "User skipped intake questions; use defaults and record all unresolved decisions in ledgers and claim audit.",
                "source": "operator_override",
            }
        )
    elif mode == "quick":
        questions = [question for question in questions if question.get("blocking")]

    return {
        "mode": mode,
        "policy": {
            "ask_only_if_not_answered": True,
            "read_ledgers_before_questions": True,
            "max_questions_guideline": 3 if mode == "quick" else 7,
            "skip_phrases": ["skip and go", "use defaults", "assume defaults", "no interview"],
        },
        "known": known,
        "assumptions": assumptions,
        "questions": questions,
        "blocking_questions": [question for question in questions if question.get("blocking")],
        "counts": {
            "known": len(known),
            "assumptions": len(assumptions),
            "questions": len(questions),
            "blocking_questions": len([question for question in questions if question.get("blocking")]),
        },
    }


def build_audit(launch_manifest: Path, *, interview_mode: str = "standard") -> dict[str, Any]:
    manifest_path = launch_manifest.resolve()
    manifest = read_json(manifest_path)
    campaign_path = resolve_manifest_path(str(manifest.get("campaign_manifest", "")), manifest_path)
    campaign = read_json(campaign_path) if campaign_path.exists() else {}
    data_rows = read_tsv(resolve_manifest_path(str(manifest.get("data_ledger", "")), manifest_path))
    query_rows = read_tsv(resolve_manifest_path(str(manifest.get("query_ledger", "")), manifest_path))
    resource_rows = read_tsv(resolve_manifest_path(str(manifest.get("resource_ledger", "")), manifest_path))
    database_rows = read_tsv(resolve_manifest_path(str(manifest.get("database_ledger", "")), manifest_path))

    query_resolution_path = resolve_manifest_path(str(manifest.get("query_resolution_plan", "")), manifest_path)
    query_resolution = read_json(query_resolution_path) if query_resolution_path.exists() else {}
    data_materialization_path = resolve_manifest_path(str(manifest.get("data_materialization_plan", "")), manifest_path)
    data_materialization = read_json(data_materialization_path) if data_materialization_path.exists() else {}
    candidate_route_path = resolve_manifest_path(str(manifest.get("candidate_route_plan", "")), manifest_path)
    candidate_route_plan = read_json(candidate_route_path) if candidate_route_path.exists() else {}
    run_economics_path = resolve_manifest_path(str(manifest.get("run_economics", "")), manifest_path)
    run_economics = read_json(run_economics_path) if run_economics_path.exists() else {}

    known_data_refs = [
        compact_row(
            row,
            [
                "dataset_id",
                "accession",
                "run_id",
                "data_role",
                "sample_type",
                "organism",
                "bioproject",
                "technology",
                "expected_size",
                "source_url",
                "remote_path",
                "raw_artifact_policy",
                "operator_approval_id",
            ],
        )
        for row in data_rows
    ]
    known_query_refs = [
        compact_row(
            row,
            [
                "query_id",
                "query_name",
                "source_organism",
                "sequence_source",
                "enzyme_class",
                "pathway_role",
                "confidence",
                "citation",
                "resolved_accession",
                "curation_status",
            ],
        )
        for row in query_rows
    ]
    approved_resources = [
        compact_row(row, ["resource", "resource_type", "version", "license_class", "use_mode", "approval_status"])
        for row in resource_rows
    ]
    database_contracts = [
        compact_row(row, ["db_id", "engine", "sequence_type", "remote_path", "version", "license_class", "build_required", "search_template"])
        for row in database_rows
    ]

    unresolved_high_confidence = [
        row
        for row in query_resolution.get("records", [])
        if (
            row.get("confidence") == "high"
            and row.get("curation_status") != "resolved"
            and row.get("resolution_action") != "use_embedded_query_fasta"
        )
    ]
    materialization_summary = data_materialization.get("summary", {})

    known_accessions = [row.get("accession", "") for row in data_rows if row.get("accession")]
    known_source_urls = [row.get("source_url", "") for row in data_rows if row.get("source_url")]
    missing_operator_items: list[dict[str, str]] = []
    if manifest.get("missing_credentials"):
        missing_operator_items.append(
            {
                "item": "provider credentials",
                "reason": "launch manifest has missing_credentials",
                "source": "launch-manifest.json",
            }
        )
    if unresolved_high_confidence:
        missing_operator_items.append(
            {
                "item": "high-confidence query seed resolution",
                "reason": ",".join(row.get("query_id", "") for row in unresolved_high_confidence),
                "source": "query-resolution-plan.json",
            }
        )

    do_not_ask_for: list[str] = []
    if known_accessions or known_source_urls:
        do_not_ask_for.append("data links/accessions already present in ledgers/data-ledger.tsv")
    if known_query_refs:
        do_not_ask_for.append("query list already present in ledgers/query-ledger.tsv")

    intake_interview = build_intake_interview(
        mode=interview_mode,
        manifest=manifest,
        campaign=campaign,
        data_rows=data_rows,
        query_rows=query_rows,
        query_resolution=query_resolution,
        candidate_route_plan=candidate_route_plan,
        run_economics=run_economics,
    )

    return {
        "schema_version": 1,
        "campaign_id": manifest.get("campaign_id", ""),
        "run_id": manifest.get("run_id", ""),
        "run_scope": manifest.get("run_scope", ""),
        "provider_class": manifest.get("provider_class", ""),
        "input_first_policy": {
            "read_before_asking": True,
            "operator_questions_allowed_only_for_missing_items": True,
            "do_not_ask_for": do_not_ask_for,
        },
        "known_data_refs": known_data_refs,
        "known_query_refs": known_query_refs,
        "approved_resources": approved_resources,
        "database_contracts": database_contracts,
        "materialization_summary": materialization_summary,
        "unresolved_high_confidence_queries": unresolved_high_confidence,
        "missing_operator_items": missing_operator_items,
        "intake_interview": intake_interview,
        "counts": {
            "data_rows": len(data_rows),
            "known_accessions": len(known_accessions),
            "known_source_urls": len(known_source_urls),
            "query_rows": len(query_rows),
            "resource_rows": len(resource_rows),
            "database_rows": len(database_rows),
            "missing_operator_items": len(missing_operator_items),
        },
    }


def render_markdown(audit: dict[str, Any]) -> str:
    interview = audit.get("intake_interview", {})
    lines = [
        "# GeneCluster Input Audit",
        "",
        f"Campaign: `{audit.get('campaign_id', '')}`",
        f"Run: `{audit.get('run_id', '')}`",
        f"Scope: `{audit.get('run_scope', '')}`",
        "",
        "## Known Data Inputs",
    ]
    if audit["known_data_refs"]:
        for row in audit["known_data_refs"]:
            parts = [row.get("dataset_id", "dataset"), row.get("accession", ""), row.get("data_role", ""), row.get("organism", "")]
            lines.append("- " + " | ".join(part for part in parts if part))
    else:
        lines.append("- none recorded")
    lines.extend(["", "## Known Query Inputs"])
    if audit["known_query_refs"]:
        for row in audit["known_query_refs"][:25]:
            parts = [row.get("query_id", ""), row.get("query_name", ""), row.get("source_organism", ""), row.get("confidence", "")]
            lines.append("- " + " | ".join(part for part in parts if part))
    else:
        lines.append("- none recorded")
    lines.extend(["", "## Missing Operator Items"])
    if audit["missing_operator_items"]:
        for row in audit["missing_operator_items"]:
            lines.append(f"- {row.get('item', '')}: {row.get('reason', '')}")
    else:
        lines.append("- none detected from bundle")
    lines.extend(["", "## Do Not Ask The Operator For"])
    for item in audit["input_first_policy"].get("do_not_ask_for", []) or ["none"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Intake Interview"])
    lines.append(f"Mode: `{interview.get('mode', '')}`")
    lines.extend(["", "### Known / Already Answered"])
    for row in interview.get("known", []) or [{"topic": "none", "value": "", "source": ""}]:
        lines.append(f"- `{row.get('topic', '')}`: {row.get('value', '')} ({row.get('source', '')})")
    lines.extend(["", "### Assumptions If Skipped"])
    for row in interview.get("assumptions", []) or [{"topic": "none", "assumption": "none", "source": ""}]:
        lines.append(f"- `{row.get('topic', '')}`: {row.get('assumption', '')}")
    lines.extend(["", "### Questions To Ask"])
    if interview.get("questions"):
        for row in interview["questions"]:
            prefix = "BLOCKING" if row.get("blocking") else "OPTIONAL"
            lines.append(f"- **{prefix} `{row.get('question_id', '')}`**: {row.get('question', '')}")
            lines.append(f"  - Default if skipped: {row.get('default_if_skipped', '')}")
    else:
        lines.append("- none; proceed with recorded defaults and assumptions")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a GeneCluster launch bundle before asking the operator for inputs.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    parser.add_argument("--markdown-out", type=Path, help="Optional Markdown output path.")
    parser.add_argument("--interview-mode", choices=sorted(INTERVIEW_MODES), default="standard", help="Question generation mode: quick, standard, strict, or skip.")
    parser.add_argument("--require-no-blocking-questions", action="store_true", help="Fail if generated intake interview still has blocking questions.")
    parser.add_argument("--require-known-data", action="store_true", help="Fail when the bundle has no data rows or accessions/source URLs.")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout.")
    args = parser.parse_args()

    audit = build_audit(args.launch_manifest, interview_mode=args.interview_mode)
    errors: list[str] = []
    if args.require_known_data and audit["counts"]["data_rows"] == 0:
        errors.append("no data rows found in bundle data ledger")
    if args.require_known_data and audit["counts"]["known_accessions"] == 0 and audit["counts"]["known_source_urls"] == 0:
        errors.append("no accessions or source URLs found in bundle data ledger")
    if args.require_no_blocking_questions and audit.get("intake_interview", {}).get("blocking_questions"):
        errors.append("intake interview still has blocking questions")
    audit["ok"] = not errors
    audit["errors"] = errors

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_out:
        args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_out.write_text(render_markdown(audit), encoding="utf-8")
    if args.json:
        print(json.dumps(audit, indent=2, sort_keys=True))
    else:
        print("BioSymphony GeneCluster input audit:", "ok" if audit["ok"] else "failed")
        print(f"Known data rows: {audit['counts']['data_rows']}")
        print(f"Known accessions: {audit['counts']['known_accessions']}")
        print(f"Known query rows: {audit['counts']['query_rows']}")
        print(f"Interview mode: {audit['intake_interview']['mode']}")
        print(f"Interview questions: {audit['intake_interview']['counts']['questions']}")
        print(f"Blocking questions: {audit['intake_interview']['counts']['blocking_questions']}")
        for item in audit["missing_operator_items"]:
            print(f"MISSING: {item['item']} - {item['reason']}")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if audit["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
