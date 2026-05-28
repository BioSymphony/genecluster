#!/usr/bin/env python3
"""Lightweight claim auditor for GeneCluster candidate summaries."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BROAD_FAMILIES = ("CYP", "p450", "OMT", "Methyltransf", "MDR", "reductase", "GH1")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle, delimiter="\t")]


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def is_broad_family(row: dict[str, str]) -> bool:
    combined = " ".join(
        [
            row.get("query_id", ""),
            row.get("domain_calls", ""),
            row.get("domain_architecture", ""),
            row.get("paralog_flag", ""),
            row.get("duplicate_class", ""),
            row.get("pathway_role", ""),
        ]
    )
    return row.get("duplicate_class") == "broad_family" or any(term.lower() in combined.lower() for term in BROAD_FAMILIES)


def audit_candidates(rows: list[dict[str, str]], *, campaign_id: str = "genecluster") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    created_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        candidate_id = row.get("candidate_id", "unknown")
        hit_type = row.get("hit_type", "")
        product_claim = row.get("product_claim_level", "")
        genome_locus = row.get("genome_locus", "")
        neighborhood = row.get("neighborhood_cluster_id", "")

        if hit_type == "transcript_hit" and product_claim == "cluster_hypothesis":
            records.append(
                {
                    "audit_id": f"audit.{candidate_id}.transcriptome_cluster",
                    "campaign_id": campaign_id,
                    "mode": "overclaim",
                    "subject_id": candidate_id,
                    "rule_id": "transcriptome_only_does_not_prove_physical_cluster",
                    "verdict": "not_supported",
                    "review_status": "needs-rerun",
                    "created_at": created_at,
                    "detail": "Transcript evidence can support a candidate gene, not a physical cluster claim.",
                }
            )
        elif hit_type == "transcript_hit":
            records.append(
                {
                    "audit_id": f"audit.{candidate_id}.transcript_candidate",
                    "campaign_id": campaign_id,
                    "mode": "overclaim",
                    "subject_id": candidate_id,
                    "rule_id": "transcript_candidate_claim_boundary",
                    "verdict": "qualified",
                    "review_status": row.get("review_status", "needs-human-review"),
                    "created_at": created_at,
                    "detail": "Transcript evidence is limited to candidate-gene support until genome coordinates are available.",
                }
            )

        if product_claim in {"pathway_hypothesis", "cluster_hypothesis"} and is_broad_family(row):
            try:
                score = float(row.get("evidence_score") or 0)
            except ValueError:
                score = 0.0
            records.append(
                {
                    "audit_id": f"audit.{candidate_id}.broad_family_product",
                    "campaign_id": campaign_id,
                    "mode": "overclaim",
                    "subject_id": candidate_id,
                    "rule_id": "broad_family_hit_does_not_prove_product_chemistry",
                    "verdict": "qualified" if score >= 0.70 else "not_supported",
                    "review_status": "needs-human-review",
                    "created_at": created_at,
                    "detail": "Broad CYP/OMT/reductase/GH-family evidence requires phylogeny, motif, context, or validation before product claims.",
                }
            )

        if product_claim == "cluster_hypothesis":
            has_coordinate = genome_locus and genome_locus not in {"transcript_only", "remote_pending", "unknown"}
            has_neighborhood = neighborhood and neighborhood not in {"remote_pending", "remote_neighborhood_pending", "unknown"}
            records.append(
                {
                    "audit_id": f"audit.{candidate_id}.cluster_coordinates",
                    "campaign_id": campaign_id,
                    "mode": "overclaim",
                    "subject_id": candidate_id,
                    "rule_id": "cluster_claim_requires_coordinates_and_neighborhood",
                    "verdict": "supported" if has_coordinate and has_neighborhood else "not_supported",
                    "review_status": "needs-human-review",
                    "created_at": created_at,
                    "detail": "Physical cluster claims require genome coordinates plus neighboring-gene evidence.",
                }
            )

        if product_claim not in {"none", "candidate", "validated_elsewhere"}:
            records.append(
                {
                    "audit_id": f"audit.{candidate_id}.product_validation",
                    "campaign_id": campaign_id,
                    "mode": "overclaim",
                    "subject_id": candidate_id,
                    "rule_id": "product_claim_requires_external_validation",
                    "verdict": "qualified",
                    "review_status": "needs-human-review",
                    "created_at": created_at,
                    "detail": "Pathway/product claims remain hypotheses unless backed by functional assays, LC-MS/MS, or direct validated literature support.",
                }
            )

    step_ids = sorted({row.get("pathway_step_id", "") for row in rows if row.get("pathway_step_id")})
    for step_id in step_ids:
        candidates = [row for row in rows if row.get("pathway_step_id") == step_id]
        accepted = [row for row in candidates if float(row.get("evidence_score") or 0) >= 0.7]
        records.append(
            {
                "audit_id": f"audit.{step_id}.pathway_completeness",
                "campaign_id": campaign_id,
                "mode": "pathway_completeness",
                "subject_id": step_id,
                "rule_id": "step_requires_ranked_candidate",
                "verdict": "qualified" if accepted else "needs_more_data",
                "review_status": "needs-human-review",
                "created_at": created_at,
                "detail": f"{len(accepted)} candidate(s) above evidence_score 0.7 for {step_id}.",
            }
        )

    if not records:
        records.append(
            {
                "audit_id": "audit.empty.no_candidates",
                "campaign_id": campaign_id,
                "mode": "pathway_completeness",
                "subject_id": "candidate_hits",
                "rule_id": "candidate_table_nonempty",
                "verdict": "needs_more_data",
                "review_status": "needs-rerun",
                "created_at": created_at,
                "detail": "No candidates were available for audit.",
            }
        )
    return records


def write_claim_ledger(path: Path, records: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["verdict"]] = counts.get(record["verdict"], 0) + 1
    lines = [
        "# GeneCluster Claim Ledger",
        "",
        "## Allowed claims",
        "",
        "- Candidate genes may be prioritized by homology, domain architecture, genome context, and coexpression when those evidence rows exist.",
        "- Genome-localized candidates may support neighborhood hypotheses only when coordinates and neighboring-gene evidence are present.",
        "",
        "## Forbidden overclaims",
        "",
        "- Transcriptome-only evidence proves a physical gene cluster.",
        "- Broad CYP/OMT/reductase homology proves product chemistry.",
        "- Candidate discovery is experimental validation.",
        "",
        "## Validation caveats",
        "",
        "- Product-level BIA or an alkaloid claims require LC-MS/MS, functional assays, or direct validated literature support.",
        "- Deduplication, tetraploid copy ambiguity, splice variants, and incomplete ORFs require human review.",
        "",
        "## Audit summary",
        "",
    ]
    lines.extend(f"- {verdict}: {count}" for verdict, count in sorted(counts.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit GeneCluster candidate claims.")
    parser.add_argument("--candidate-hits", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="Output claim-audit.jsonl.")
    parser.add_argument("--claim-ledger", type=Path, help="Optional claim-ledger.md output.")
    parser.add_argument("--campaign-id", default="genecluster")
    args = parser.parse_args()

    records = audit_candidates(read_tsv(args.candidate_hits), campaign_id=args.campaign_id)
    write_jsonl(args.out, records)
    if args.claim_ledger:
        write_claim_ledger(args.claim_ledger, records)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
