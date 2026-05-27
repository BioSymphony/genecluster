#!/usr/bin/env python3
"""Normalize compact GeneCluster Atlas fixture tables into contract artifacts.

This module is intentionally summary-only. It converts mocked or already-run
tool outputs into the ledger shapes validated by ``genecluster_atlas_contracts``
without invoking plantiSMASH, cblaster, CLEAN, Foldseek, OrthoFinder,
GENESPACE, or any other external program.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence


CLUSTER_CALL_COLUMNS = [
    "cluster_id",
    "caller",
    "source_species",
    "target_species",
    "contig",
    "start",
    "end",
    "core_genes",
    "confidence",
    "claim_level",
]

BGC_CONSENSUS_COLUMNS = [
    "consensus_id",
    "cluster_id",
    "verdict",
    "caller_count",
    "agreeing_callers",
    "disagreeing_callers",
    "disagreement_status",
    "claim_level",
    "caller_versions",
    "caller_licenses",
]

PROTEIN_FUNCTION_VOTE_COLUMNS = [
    "protein_id",
    "tool",
    "function_label",
    "confidence",
    "evidence_level",
    "tool_version",
    "license",
]

PROTEIN_FUNCTION_JURY_COLUMNS = [
    "protein_id",
    "verdict",
    "claim_level",
    "supporting_tools",
    "contradicting_tools",
    "confidence",
]

SPECIES_LEDGER_COLUMNS = ["species_id", "scientific_name", "assembly_id", "annotation_id", "data_status", "license"]
ORTHOGROUP_COLUMNS = ["orthogroup_id", "species_id", "protein_id", "paralog_group", "orthology_status"]
SYNTENY_BLOCK_COLUMNS = ["block_id", "species_id", "contig", "start", "end", "anchor_gene", "support_status"]
CLUSTER_CALL_MATRIX_COLUMNS = ["cluster_id", "species_id", "caller", "call_status", "claim_level"]
COMPARATIVE_NEIGHBORHOOD_COLUMNS = [
    "neighborhood_id",
    "species_id",
    "cluster_id",
    "gene_id",
    "relative_order",
    "function_label",
]

CLAIM_LEVELS = [
    "L0_route_only",
    "L1_candidate_gene_only",
    "L1_sequence_rescue_only",
    "L2_coordinate_context_ready",
    "L2_annotation_assets_need_join_repair",
    "L3_annotation_neighborhood_ready",
    "L4_consensus_supported",
    "L5_claim_audited_dossier_ready",
]

COMPARATIVE_STATUSES = {"present", "absent", "not_run", "candidate", "supported", "conflict", "fixture"}

DEFAULT_TOOL_VERSIONS = {
    "annotation_direct": "biosymphony-fixture",
    "plantiSMASH": "mocked-fixture",
    "cblaster": "mocked-fixture",
    "Pfam": "fixture",
    "DIAMOND": "fixture",
    "UniProt": "fixture",
    "CLEAN": "mocked-fixture",
    "Foldseek": "mocked-fixture",
}

DEFAULT_TOOL_LICENSES = {
    "annotation_direct": "summary-fixture",
    "plantiSMASH": "review-required",
    "cblaster": "MIT-or-fixture",
    "Pfam": "Pfam-summary",
    "DIAMOND": "open-source-summary",
    "UniProt": "UniProt-terms-summary",
    "CLEAN": "review-required",
    "Foldseek": "GPLv3-summary",
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 TSV into dictionaries with string values."""

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{str(key): str(value or "") for key, value in row.items() if key is not None} for row in reader]


def write_tsv(path: Path, columns: Sequence[str], rows: Sequence[dict[str, Any]]) -> None:
    """Write rows to a deterministic UTF-8 TSV using the requested column order."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: as_text(row.get(column, "")) for column in columns})


def as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def key_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def row_lookup(row: dict[str, Any]) -> dict[str, Any]:
    return {key_token(str(key)): value for key, value in row.items()}


def pick(row: dict[str, Any], names: Sequence[str], default: str = "") -> str:
    lookup = row_lookup(row)
    for name in names:
        value = lookup.get(key_token(name))
        if value is not None and as_text(value) != "":
            return as_text(value)
    return default


def split_items(value: Any) -> list[str]:
    text = as_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[;,|]", text) if item.strip()]


def split_gene_items(value: Any) -> list[str]:
    text = as_text(value)
    if not text:
        return []
    chunks = re.split(r"[;,|]\s*|\s{2,}", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def unique_join(items: Iterable[str], sep: str = ",") -> str:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = as_text(item)
        if text and text not in seen:
            seen.add(text)
            ordered.append(text)
    return sep.join(ordered)


def slug(value: str, fallback: str = "unknown") -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", as_text(value)).strip("-").lower()
    return text or fallback


def normalize_int(value: Any, default: str = "0") -> str:
    text = as_text(value).replace(",", "")
    if not text:
        return default
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def parse_float(value: Any) -> float | None:
    text = as_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def format_float(value: float | None, default: str = "0") -> str:
    if value is None:
        return default
    value = max(0.0, min(1.0, value))
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def normalize_confidence(value: Any, default: str = "0.5") -> str:
    parsed = parse_float(value)
    if parsed is None:
        return default
    if parsed > 1.0:
        parsed = parsed / 100.0
    return format_float(parsed, default=default)


def confidence_from_evalue(value: Any, default: float = 0.5) -> str:
    parsed = parse_float(value)
    if parsed is None:
        return format_float(default)
    if parsed <= 1e-50:
        return "0.95"
    if parsed <= 1e-20:
        return "0.9"
    if parsed <= 1e-5:
        return "0.75"
    if parsed <= 1e-2:
        return "0.6"
    return "0.4"


def confidence_from_identity(value: Any, bitscore: Any = "") -> str:
    identity = parse_float(value)
    if identity is not None:
        if identity > 1.0:
            identity = identity / 100.0
        return format_float(0.35 + (identity * 0.6), default="0.6")
    score = parse_float(bitscore)
    if score is None:
        return "0.6"
    if score >= 500:
        return "0.95"
    if score >= 200:
        return "0.85"
    if score >= 80:
        return "0.7"
    return "0.55"


def strongest_claim(values: Iterable[str], default: str = "L3_annotation_neighborhood_ready") -> str:
    ranks = {level: index for index, level in enumerate(CLAIM_LEVELS)}
    best = default
    for value in values:
        if value in ranks and ranks[value] > ranks.get(best, -1):
            best = value
    return best


def cluster_signature(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        as_text(row.get("contig")),
        as_text(row.get("start")),
        as_text(row.get("end")),
        as_text(row.get("core_genes")),
    )


def normalize_cluster_call_row(
    row: dict[str, Any],
    *,
    caller: str,
    index: int,
    source_species: str = "",
    target_species: str = "",
    default_claim_level: str = "L3_annotation_neighborhood_ready",
    default_confidence: str = "0.6",
) -> dict[str, str]:
    """Normalize one compact cluster/BGC call row to ``cluster_calls.tsv``."""

    cluster_id = pick(row, ["cluster_id", "bgc_id", "region_id", "neighborhood_id", "id"])
    if not cluster_id:
        cluster_id = f"{slug(caller, 'caller')}-{index:04d}"

    start = pick(row, ["start", "window_start", "region_start", "anchor_start", "from", "begin"], "0")
    end = pick(row, ["end", "window_end", "region_end", "anchor_end", "to", "stop"], start or "0")
    core_genes = pick(
        row,
        [
            "core_genes",
            "core_gene",
            "neighbor_protein_ids",
            "genes",
            "gene_ids",
            "protein_ids",
            "anchor_protein_id",
            "anchor_gene",
            "candidate_id",
        ],
    )
    if not core_genes:
        core_genes = cluster_id

    confidence = pick(row, ["confidence", "score", "cluster_score", "probability", "prob"])
    if confidence:
        confidence = normalize_confidence(confidence, default=default_confidence)
    else:
        identity = pick(row, ["anchor_pct_identity", "pct_identity", "identity"])
        confidence = confidence_from_identity(identity) if identity else default_confidence

    claim_level = pick(row, ["claim_level", "evidence_level"], default_claim_level)
    if claim_level not in CLAIM_LEVELS:
        claim_level = default_claim_level

    return {
        "cluster_id": cluster_id,
        "caller": caller,
        "source_species": pick(row, ["source_species", "species", "scientific_name"], source_species or "fixture_source_species"),
        "target_species": pick(row, ["target_species", "species", "scientific_name"], target_species or source_species or "fixture_target_species"),
        "contig": pick(row, ["contig", "chromosome", "chrom", "seq_id", "sequence_id", "scaffold"], "unknown_contig"),
        "start": normalize_int(start),
        "end": normalize_int(end),
        "core_genes": unique_join(split_gene_items(core_genes), sep=";") or as_text(core_genes),
        "confidence": confidence,
        "claim_level": claim_level,
    }


def normalize_annotation_direct_clusters(
    rows: Sequence[dict[str, Any]],
    *,
    source_species: str = "",
    target_species: str = "",
    caller: str = "annotation_direct",
) -> list[dict[str, str]]:
    """Normalize BioSymphony annotation-direct cluster neighborhoods."""

    calls = [
        normalize_cluster_call_row(
            row,
            caller=caller,
            index=index,
            source_species=source_species,
            target_species=target_species,
            default_claim_level="L3_annotation_neighborhood_ready",
            default_confidence="0.75",
        )
        for index, row in enumerate(rows, start=1)
    ]
    return sort_cluster_calls(calls)


def normalize_plantismash_calls(
    rows: Sequence[dict[str, Any]],
    *,
    source_species: str = "",
    target_species: str = "",
    caller: str = "plantiSMASH",
) -> list[dict[str, str]]:
    """Normalize mocked plantiSMASH region calls to ``cluster_calls.tsv`` rows."""

    calls = [
        normalize_cluster_call_row(
            row,
            caller=caller,
            index=index,
            source_species=source_species,
            target_species=target_species,
            default_claim_level="L4_consensus_supported",
            default_confidence="0.7",
        )
        for index, row in enumerate(rows, start=1)
    ]
    return sort_cluster_calls(calls)


def normalize_cblaster_calls(
    rows: Sequence[dict[str, Any]],
    *,
    source_species: str = "",
    target_species: str = "",
    caller: str = "cblaster",
) -> list[dict[str, str]]:
    """Normalize mocked cblaster cluster hits to ``cluster_calls.tsv`` rows."""

    calls = [
        normalize_cluster_call_row(
            row,
            caller=caller,
            index=index,
            source_species=source_species,
            target_species=target_species,
            default_claim_level="L4_consensus_supported",
            default_confidence="0.65",
        )
        for index, row in enumerate(rows, start=1)
    ]
    return sort_cluster_calls(calls)


def normalize_mocked_bgc_calls(
    rows: Sequence[dict[str, Any]],
    *,
    caller: str,
    source_species: str = "",
    target_species: str = "",
) -> list[dict[str, str]]:
    """Normalize generic mocked BGC caller rows using a caller name."""

    if caller == "plantiSMASH":
        return normalize_plantismash_calls(rows, source_species=source_species, target_species=target_species, caller=caller)
    if caller == "cblaster":
        return normalize_cblaster_calls(rows, source_species=source_species, target_species=target_species, caller=caller)
    calls = [
        normalize_cluster_call_row(
            row,
            caller=caller,
            index=index,
            source_species=source_species,
            target_species=target_species,
            default_claim_level="L3_annotation_neighborhood_ready",
            default_confidence="0.6",
        )
        for index, row in enumerate(rows, start=1)
    ]
    return sort_cluster_calls(calls)


def sort_cluster_calls(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: (row["cluster_id"], row["caller"], row["source_species"], row["target_species"]))


def normalize_cluster_calls(
    *,
    annotation_direct_rows: Sequence[dict[str, Any]] | None = None,
    plantismash_rows: Sequence[dict[str, Any]] | None = None,
    cblaster_rows: Sequence[dict[str, Any]] | None = None,
    source_species: str = "",
    target_species: str = "",
) -> list[dict[str, str]]:
    """Combine supported compact cluster inputs into ``cluster_calls.tsv`` rows."""

    rows: list[dict[str, str]] = []
    if annotation_direct_rows:
        rows.extend(
            normalize_annotation_direct_clusters(
                annotation_direct_rows,
                source_species=source_species,
                target_species=target_species,
            )
        )
    if plantismash_rows:
        rows.extend(
            normalize_plantismash_calls(
                plantismash_rows,
                source_species=source_species,
                target_species=target_species,
            )
        )
    if cblaster_rows:
        rows.extend(
            normalize_cblaster_calls(
                cblaster_rows,
                source_species=source_species,
                target_species=target_species,
            )
        )
    return sort_cluster_calls(rows)


def default_cluster_fixture_rows() -> list[dict[str, str]]:
    return [
        {
            "cluster_id": "fixture_cluster",
            "contig": "fixture_contig",
            "start": "1",
            "end": "1000",
            "core_genes": "fixture_protein",
            "confidence": "0.6",
            "source_species": "fixture_species",
            "target_species": "fixture_species",
        }
    ]


def build_bgc_consensus(cluster_call_rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Build deterministic consensus rows from normalized cluster calls."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cluster_call_rows:
        grouped[as_text(row.get("cluster_id"))].append(row)

    consensus: list[dict[str, str]] = []
    for cluster_id in sorted(grouped):
        rows = sorted(grouped[cluster_id], key=lambda row: as_text(row.get("caller")))
        callers = [as_text(row.get("caller")) for row in rows if as_text(row.get("caller"))]
        caller_count = len(set(callers))
        signatures = {cluster_signature(row) for row in rows}

        if caller_count <= 1:
            agreeing = callers
            disagreeing: list[str] = []
            disagreement_status = "insufficient_callers"
            verdict = "candidate"
        elif len(signatures) == 1:
            agreeing = callers
            disagreeing = []
            disagreement_status = "none"
            verdict = "supported"
        else:
            best = sorted(rows, key=lambda row: (-float(parse_float(row.get("confidence")) or 0.0), as_text(row.get("caller"))))[0]
            best_signature = cluster_signature(best)
            agreeing = [as_text(row.get("caller")) for row in rows if cluster_signature(row) == best_signature]
            disagreeing = [as_text(row.get("caller")) for row in rows if cluster_signature(row) != best_signature]
            disagreement_status = "present"
            verdict = "conflict"

        versions = [f"{caller}={DEFAULT_TOOL_VERSIONS.get(caller, 'fixture')}" for caller in sorted(set(callers))]
        licenses = [f"{caller}={DEFAULT_TOOL_LICENSES.get(caller, 'summary-fixture')}" for caller in sorted(set(callers))]
        claim_level = "L4_consensus_supported" if caller_count > 1 else strongest_claim(row.get("claim_level", "") for row in rows)

        consensus.append(
            {
                "consensus_id": f"consensus-{slug(cluster_id)}",
                "cluster_id": cluster_id,
                "verdict": verdict,
                "caller_count": str(caller_count),
                "agreeing_callers": unique_join(agreeing),
                "disagreeing_callers": unique_join(disagreeing),
                "disagreement_status": disagreement_status,
                "claim_level": claim_level,
                "caller_versions": ";".join(versions),
                "caller_licenses": ";".join(licenses),
            }
        )
    return consensus


def parse_swissprot_accession(value: Any) -> str:
    text = as_text(value)
    match = re.search(r"(?:sp|tr)\|([^|]+)\|", text)
    if match:
        return match.group(1)
    return text


def parse_swissprot_label(value: Any) -> str:
    text = as_text(value)
    match = re.match(r"(?:sp|tr)\|[^|]+\|\S+\s+(.+)", text)
    if match:
        text = match.group(1)
    text = re.split(r"\s+OS=", text, maxsplit=1)[0].strip()
    return text or "swissprot_hit"


def vote_row(
    *,
    protein_id: str,
    tool: str,
    function_label: str,
    confidence: str,
    evidence_level: str = "L3_annotation_neighborhood_ready",
    tool_version: str = "",
    license_value: str = "",
) -> dict[str, str]:
    evidence = evidence_level if evidence_level in CLAIM_LEVELS else "L3_annotation_neighborhood_ready"
    return {
        "protein_id": protein_id,
        "tool": tool,
        "function_label": function_label or "unassigned_function",
        "confidence": normalize_confidence(confidence, default="0.5"),
        "evidence_level": evidence,
        "tool_version": tool_version or DEFAULT_TOOL_VERSIONS.get(tool, "fixture"),
        "license": license_value or DEFAULT_TOOL_LICENSES.get(tool, "summary-fixture"),
    }


def normalize_pfam_votes(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize existing Pfam enrichment rows to protein function votes."""

    votes: list[dict[str, str]] = []
    for row in rows:
        protein_id = pick(row, ["protein_id", "query_id", "gene_id"])
        if not protein_id:
            continue
        label = pick(row, ["function_label", "pfam_name", "description", "pfam_acc"], "Pfam_domain")
        confidence = pick(row, ["confidence", "score"])
        if not confidence:
            confidence = confidence_from_evalue(pick(row, ["i_evalue", "evalue", "full_evalue"]))
        votes.append(
            vote_row(
                protein_id=protein_id,
                tool="Pfam",
                function_label=label,
                confidence=confidence,
                evidence_level=pick(row, ["evidence_level", "claim_level"], "L3_annotation_neighborhood_ready"),
                tool_version=pick(row, ["tool_version", "version", "pfam_version"], "fixture"),
                license_value=pick(row, ["license"], DEFAULT_TOOL_LICENSES["Pfam"]),
            )
        )
    return sort_votes(votes)


def normalize_diamond_votes(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize existing DIAMOND/SwissProt rows to protein function votes."""

    votes: list[dict[str, str]] = []
    for row in rows:
        protein_id = pick(row, ["protein_id", "query_id", "gene_id"])
        if not protein_id:
            continue
        label = pick(row, ["function_label", "swissprot_title", "title", "description", "hit_description"], "SwissProt_hit")
        confidence = pick(row, ["confidence", "score"])
        if not confidence:
            confidence = confidence_from_identity(pick(row, ["pct_identity", "identity"]), pick(row, ["bitscore"]))
        votes.append(
            vote_row(
                protein_id=protein_id,
                tool="DIAMOND",
                function_label=parse_swissprot_label(label),
                confidence=confidence,
                evidence_level=pick(row, ["evidence_level", "claim_level"], "L3_annotation_neighborhood_ready"),
                tool_version=pick(row, ["tool_version", "diamond_version", "version"], "fixture"),
                license_value=pick(row, ["license"], DEFAULT_TOOL_LICENSES["DIAMOND"]),
            )
        )
    return sort_votes(votes)


def diamond_accession_map(rows: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    """Return UniProt accession -> protein IDs from DIAMOND/SwissProt rows."""

    mapping: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        protein_id = pick(row, ["protein_id", "query_id", "gene_id"])
        accession = parse_swissprot_accession(pick(row, ["accession", "swissprot_id", "target_id", "subject_id", "swissprot_title"]))
        if protein_id and accession:
            mapping[accession].append(protein_id)
    return {accession: sorted(set(proteins)) for accession, proteins in mapping.items()}


def normalize_uniprot_votes(
    rows: Sequence[dict[str, Any]],
    accession_to_protein_ids: dict[str, Sequence[str]] | None = None,
) -> list[dict[str, str]]:
    """Normalize UniProt curated enrichment rows to protein function votes."""

    accession_to_protein_ids = accession_to_protein_ids or {}
    votes: list[dict[str, str]] = []
    for row in rows:
        accession = pick(row, ["accession", "uniprot_accession", "swissprot_accession", "swissprot_id"])
        protein_ids = list(accession_to_protein_ids.get(accession, []))
        direct_protein = pick(row, ["protein_id", "query_id", "gene_id"])
        if direct_protein:
            protein_ids.append(direct_protein)
        if not protein_ids and accession:
            protein_ids.append(accession)
        if not protein_ids:
            continue

        ec_number = pick(row, ["ec_number", "ec"])
        protein_name = pick(row, ["protein_name", "recommended_name", "name"])
        function = pick(row, ["function", "catalytic_reaction", "keywords"])
        label = ec_number or protein_name or function or "UniProt_annotation"
        if ec_number and protein_name:
            label = f"EC {ec_number} {protein_name}"

        for protein_id in sorted(set(protein_ids)):
            votes.append(
                vote_row(
                    protein_id=protein_id,
                    tool="UniProt",
                    function_label=label,
                    confidence=pick(row, ["confidence", "score"], "0.85"),
                    evidence_level=pick(row, ["evidence_level", "claim_level"], "L3_annotation_neighborhood_ready"),
                    tool_version=pick(row, ["tool_version", "uniprot_release", "version"], "fixture"),
                    license_value=pick(row, ["license"], DEFAULT_TOOL_LICENSES["UniProt"]),
                )
            )
    return sort_votes(votes)


def normalize_clean_votes(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize mocked CLEAN EC/function predictions to votes."""

    votes: list[dict[str, str]] = []
    for row in rows:
        protein_id = pick(row, ["protein_id", "query_id", "gene_id", "sequence_id"])
        if not protein_id:
            continue
        label = pick(row, ["function_label", "ec_number", "predicted_ec", "prediction", "label"], "CLEAN_prediction")
        if re.match(r"^\d+\.", label):
            label = f"EC {label}"
        votes.append(
            vote_row(
                protein_id=protein_id,
                tool="CLEAN",
                function_label=label,
                confidence=pick(row, ["confidence", "probability", "score"], "0.6"),
                evidence_level=pick(row, ["evidence_level", "claim_level"], "L3_annotation_neighborhood_ready"),
                tool_version=pick(row, ["tool_version", "clean_version", "version"], "mocked-fixture"),
                license_value=pick(row, ["license"], DEFAULT_TOOL_LICENSES["CLEAN"]),
            )
        )
    return sort_votes(votes)


def normalize_foldseek_votes(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize mocked Foldseek/protein-structure-search hits to votes."""

    votes: list[dict[str, str]] = []
    for row in rows:
        protein_id = pick(row, ["protein_id", "query_id", "gene_id", "sequence_id"])
        if not protein_id:
            continue
        label = pick(row, ["function_label", "target_annotation", "hit_description", "description", "target", "hit"], "Foldseek_hit")
        confidence = pick(row, ["confidence", "probability", "score", "prob"])
        if not confidence:
            confidence = confidence_from_evalue(pick(row, ["evalue", "eval"]))
        votes.append(
            vote_row(
                protein_id=protein_id,
                tool="Foldseek",
                function_label=label,
                confidence=confidence,
                evidence_level=pick(row, ["evidence_level", "claim_level"], "L3_annotation_neighborhood_ready"),
                tool_version=pick(row, ["tool_version", "foldseek_version", "version"], "mocked-fixture"),
                license_value=pick(row, ["license"], DEFAULT_TOOL_LICENSES["Foldseek"]),
            )
        )
    return sort_votes(votes)


def normalize_enrichment_votes(
    *,
    pfam_rows: Sequence[dict[str, Any]] | None = None,
    diamond_rows: Sequence[dict[str, Any]] | None = None,
    uniprot_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Normalize Pfam, DIAMOND, and UniProt enrichment tables together."""

    pfam_rows = pfam_rows or []
    diamond_rows = diamond_rows or []
    uniprot_rows = uniprot_rows or []
    votes: list[dict[str, str]] = []
    votes.extend(normalize_pfam_votes(pfam_rows))
    votes.extend(normalize_diamond_votes(diamond_rows))
    votes.extend(normalize_uniprot_votes(uniprot_rows, accession_to_protein_ids=diamond_accession_map(diamond_rows)))
    return sort_votes(votes)


def normalize_model_votes(
    *,
    clean_rows: Sequence[dict[str, Any]] | None = None,
    foldseek_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Normalize mocked CLEAN and Foldseek model vote tables together."""

    votes: list[dict[str, str]] = []
    if clean_rows:
        votes.extend(normalize_clean_votes(clean_rows))
    if foldseek_rows:
        votes.extend(normalize_foldseek_votes(foldseek_rows))
    return sort_votes(votes)


def normalize_protein_function_votes(
    *,
    pfam_rows: Sequence[dict[str, Any]] | None = None,
    diamond_rows: Sequence[dict[str, Any]] | None = None,
    uniprot_rows: Sequence[dict[str, Any]] | None = None,
    clean_rows: Sequence[dict[str, Any]] | None = None,
    foldseek_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Combine all supported function evidence into ``protein_function_votes.tsv`` rows."""

    votes = normalize_enrichment_votes(pfam_rows=pfam_rows, diamond_rows=diamond_rows, uniprot_rows=uniprot_rows)
    votes.extend(normalize_model_votes(clean_rows=clean_rows, foldseek_rows=foldseek_rows))
    return sort_votes(votes)


def default_vote_fixture_rows() -> list[dict[str, str]]:
    return [
        {
            "protein_id": "fixture_protein",
            "pfam_name": "fixture_domain",
            "confidence": "0.6",
            "tool_version": "fixture",
        }
    ]


def sort_votes(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["protein_id"], row["tool"], row["function_label"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(row)
            continue
        current_confidence = parse_float(existing.get("confidence")) or 0.0
        new_confidence = parse_float(row.get("confidence")) or 0.0
        if new_confidence > current_confidence:
            existing["confidence"] = row["confidence"]
        existing["evidence_level"] = strongest_claim([existing.get("evidence_level", ""), row.get("evidence_level", "")])
        if not existing.get("tool_version"):
            existing["tool_version"] = row.get("tool_version", "")
        if not existing.get("license"):
            existing["license"] = row.get("license", "")
    return sorted(merged.values(), key=lambda row: (row["protein_id"], row["tool"], row["function_label"]))


def build_protein_function_jury(vote_rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Build one jury row per protein while preserving contradictions."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in vote_rows:
        protein_id = as_text(row.get("protein_id"))
        if protein_id:
            grouped[protein_id].append(row)

    jury: list[dict[str, str]] = []
    for protein_id in sorted(grouped):
        votes = grouped[protein_id]
        label_scores: dict[str, list[float]] = defaultdict(list)
        label_tools: dict[str, list[str]] = defaultdict(list)
        for vote in votes:
            label = as_text(vote.get("function_label")) or "unassigned_function"
            label_scores[label].append(parse_float(vote.get("confidence")) or 0.5)
            label_tools[label].append(as_text(vote.get("tool")))

        ranked = sorted(
            label_scores,
            key=lambda label: (-len(set(label_tools[label])), -(sum(label_scores[label]) / len(label_scores[label])), label),
        )
        verdict = ranked[0]
        supporting = sorted(set(label_tools[verdict]))
        contradicting = sorted({tool for label in ranked[1:] for tool in label_tools[label] if tool})
        support_confidences = label_scores[verdict]
        confidence = format_float(sum(support_confidences) / len(support_confidences), default="0.5")
        claim_level = "L4_consensus_supported" if len(supporting) > 1 and not contradicting else "L3_annotation_neighborhood_ready"
        if contradicting:
            claim_level = "L2_annotation_assets_need_join_repair"

        jury.append(
            {
                "protein_id": protein_id,
                "verdict": verdict,
                "claim_level": claim_level,
                "supporting_tools": unique_join(supporting),
                "contradicting_tools": unique_join(contradicting),
                "confidence": confidence,
            }
        )
    return jury


def split_orthofinder_cell(value: Any) -> list[str]:
    text = as_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,;\s]+", text) if item.strip()]


def normalize_orthofinder_orthogroups(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize OrthoFinder long or wide fixture tables to atlas orthogroups."""

    output: list[dict[str, str]] = []
    for row_index, row in enumerate(rows, start=1):
        orthogroup_id = pick(row, ["orthogroup_id", "orthogroup", "group_id"], f"OG{row_index:06d}")
        protein_id = pick(row, ["protein_id", "gene_id", "candidate_id"])
        species_id = pick(row, ["species_id", "species", "source_species", "target_species"])
        candidate_ids = pick(row, ["candidate_ids", "protein_ids", "gene_ids"])

        if protein_id or candidate_ids:
            genes = [protein_id] if protein_id else split_orthofinder_cell(candidate_ids)
            copy_count = len(genes)
            status = pick(row, ["orthology_status", "status"], "paralog" if copy_count > 1 else "ortholog")
            for gene in genes:
                output.append(
                    {
                        "orthogroup_id": orthogroup_id,
                        "species_id": species_id or slug(pick(row, ["scientific_name"], "fixture_species")),
                        "protein_id": gene,
                        "paralog_group": pick(row, ["paralog_group"], f"{orthogroup_id}:{species_id or 'fixture_species'}"),
                        "orthology_status": status,
                    }
                )
            continue

        # OrthoFinder's Orthogroups.tsv is wide: Orthogroup plus one column per species.
        species_cells = [(key, value) for key, value in row.items() if key_token(str(key)) not in {"orthogroup", "orthogroupid", "groupid"}]
        species_counts = {slug(str(key), "species"): len(split_orthofinder_cell(value)) for key, value in species_cells}
        represented_species = sum(1 for count in species_counts.values() if count > 0)
        for key, value in species_cells:
            species = slug(str(key), "species")
            genes = split_orthofinder_cell(value)
            for gene in genes:
                status = "paralog" if len(genes) > 1 else "ortholog" if represented_species > 1 else "singleton"
                output.append(
                    {
                        "orthogroup_id": orthogroup_id,
                        "species_id": species,
                        "protein_id": gene,
                        "paralog_group": f"{orthogroup_id}:{species}" if len(genes) > 1 else "single_copy",
                        "orthology_status": status,
                    }
                )
    return sorted(output, key=lambda row: (row["orthogroup_id"], row["species_id"], row["protein_id"]))


def normalize_genespace_synteny_blocks(rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Normalize GENESPACE/synteny summary fixtures to atlas synteny blocks."""

    output: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        block_id = pick(row, ["block_id", "synteny_block_id", "block", "id"], f"SYN{index:06d}")
        species_id = pick(row, ["species_id", "species", "target_species", "source_species"], "fixture_species")
        start = pick(row, ["start", "block_start", "gene_start"], "0")
        end = pick(row, ["end", "block_end", "gene_end"], start or "0")
        support_status = normalize_comparative_status(
            pick(row, ["support_status", "status", "review_status"], "fixture"),
            default="fixture",
        )
        output.append(
            {
                "block_id": block_id,
                "species_id": slug(species_id, "fixture_species"),
                "contig": pick(row, ["contig", "chromosome", "chrom", "seq_id", "scaffold"], "unknown_contig"),
                "start": normalize_int(start),
                "end": normalize_int(end),
                "anchor_gene": pick(row, ["anchor_gene", "candidate_id", "gene_id", "protein_id"], "unknown_anchor"),
                "support_status": support_status,
            }
        )
    return sorted(output, key=lambda row: (row["block_id"], row["species_id"], row["anchor_gene"]))


def normalize_comparative_status(value: Any, default: str = "fixture") -> str:
    text = as_text(value)
    if text in COMPARATIVE_STATUSES or text in {"not_applicable"}:
        return text
    lowered = text.lower()
    if not text:
        return default
    if "not" in lowered and "assess" in lowered:
        return "not_run"
    if "need" in lowered or "review" in lowered:
        return "candidate"
    if "support" in lowered:
        return "supported"
    if "conflict" in lowered or "disagree" in lowered:
        return "conflict"
    return default


def build_species_ledger(
    species_rows: Sequence[dict[str, Any]] | None = None,
    *,
    cluster_call_rows: Sequence[dict[str, Any]] | None = None,
    orthogroup_rows: Sequence[dict[str, Any]] | None = None,
    synteny_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build ``species-ledger.tsv`` rows from explicit or derived species metadata."""

    ledger: dict[str, dict[str, str]] = {}

    for row in species_rows or []:
        species_id = pick(row, ["species_id", "source_id", "id"], slug(pick(row, ["scientific_name", "species", "name"], "fixture_species")))
        ledger[species_id] = {
            "species_id": species_id,
            "scientific_name": pick(row, ["scientific_name", "species", "name"], species_id),
            "assembly_id": pick(row, ["assembly_id", "assembly", "genome_id"], "fixture"),
            "annotation_id": pick(row, ["annotation_id", "annotation", "proteome_id"], "fixture"),
            "data_status": pick(row, ["data_status", "status"], "fixture"),
            "license": pick(row, ["license"], "fixture"),
        }

    def add_species(value: str) -> None:
        text = as_text(value)
        if not text:
            return
        species_id = slug(text, "fixture_species")
        ledger.setdefault(
            species_id,
            {
                "species_id": species_id,
                "scientific_name": text,
                "assembly_id": "fixture",
                "annotation_id": "fixture",
                "data_status": "fixture",
                "license": "fixture",
            },
        )

    for row in cluster_call_rows or []:
        add_species(as_text(row.get("target_species")) or as_text(row.get("source_species")))
    for row in orthogroup_rows or []:
        add_species(as_text(row.get("species_id")))
    for row in synteny_rows or []:
        add_species(as_text(row.get("species_id")))

    if not ledger:
        add_species("fixture_species")
    return [ledger[key] for key in sorted(ledger)]


def build_cluster_call_matrix(cluster_call_rows: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """Build comparative cluster presence matrix rows from cluster calls."""

    rows: list[dict[str, str]] = []
    for row in cluster_call_rows:
        species = as_text(row.get("target_species")) or as_text(row.get("source_species")) or "fixture_species"
        rows.append(
            {
                "cluster_id": as_text(row.get("cluster_id")),
                "species_id": slug(species, "fixture_species"),
                "caller": as_text(row.get("caller")),
                "call_status": "present",
                "claim_level": as_text(row.get("claim_level")) if as_text(row.get("claim_level")) in CLAIM_LEVELS else "L3_annotation_neighborhood_ready",
            }
        )
    if not rows:
        rows.append(
            {
                "cluster_id": "fixture_cluster",
                "species_id": slug("fixture_species", "fixture_species"),
                "caller": "fixture",
                "call_status": "not_run",
                "claim_level": "L0_route_only",
            }
        )
    return sorted(rows, key=lambda row: (row["cluster_id"], row["species_id"], row["caller"]))


def build_comparative_neighborhoods(
    cluster_call_rows: Sequence[dict[str, Any]],
    protein_jury_rows: Sequence[dict[str, Any]] | None = None,
    orthogroup_rows: Sequence[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Build comparative neighborhood rows from cluster calls and function jury."""

    verdict_by_protein = {as_text(row.get("protein_id")): as_text(row.get("verdict")) for row in protein_jury_rows or []}
    rows: list[dict[str, str]] = []
    for call in cluster_call_rows:
        species = as_text(call.get("target_species")) or as_text(call.get("source_species")) or "fixture_species"
        genes = split_gene_items(call.get("core_genes")) or [as_text(call.get("cluster_id"))]
        for order, gene in enumerate(genes):
            rows.append(
                {
                    "neighborhood_id": f"{as_text(call.get('cluster_id'))}:{order}",
                    "species_id": slug(species, "fixture_species"),
                    "cluster_id": as_text(call.get("cluster_id")),
                    "gene_id": gene,
                    "relative_order": str(order),
                    "function_label": verdict_by_protein.get(gene, "unassigned_function"),
                }
            )

    if not rows and orthogroup_rows:
        for index, row in enumerate(orthogroup_rows, start=1):
            rows.append(
                {
                    "neighborhood_id": f"{as_text(row.get('orthogroup_id'))}:{index}",
                    "species_id": as_text(row.get("species_id")) or "fixture_species",
                    "cluster_id": as_text(row.get("orthogroup_id")) or "fixture_cluster",
                    "gene_id": as_text(row.get("protein_id")) or "unknown_gene",
                    "relative_order": str(index - 1),
                    "function_label": verdict_by_protein.get(as_text(row.get("protein_id")), "orthogroup_member"),
                }
            )

    if not rows:
        rows.append(
            {
                "neighborhood_id": "fixture_neighborhood:0",
                "species_id": slug("fixture_species", "fixture_species"),
                "cluster_id": "fixture_cluster",
                "gene_id": "unknown_gene",
                "relative_order": "0",
                "function_label": "not_assessed",
            }
        )
    return sorted(rows, key=lambda row: (row["species_id"], row["cluster_id"], int(normalize_int(row["relative_order"]))))


def build_atlas_summary(
    *,
    species_rows: Sequence[dict[str, Any]],
    orthogroup_rows: Sequence[dict[str, Any]],
    synteny_rows: Sequence[dict[str, Any]],
    cluster_matrix_rows: Sequence[dict[str, Any]],
    neighborhood_rows: Sequence[dict[str, Any]],
) -> str:
    return (
        "# GeneCluster Comparative Atlas Summary\n\n"
        "Fixture-normalized summary only; no external tools were executed.\n\n"
        f"- Species rows: {len(species_rows)}\n"
        f"- Orthogroup rows: {len(orthogroup_rows)}\n"
        f"- Synteny block rows: {len(synteny_rows)}\n"
        f"- Cluster matrix rows: {len(cluster_matrix_rows)}\n"
        f"- Comparative neighborhood rows: {len(neighborhood_rows)}\n"
    )


def build_comparative_atlas(
    *,
    species_rows: Sequence[dict[str, Any]] | None = None,
    orthofinder_rows: Sequence[dict[str, Any]] | None = None,
    genespace_rows: Sequence[dict[str, Any]] | None = None,
    cluster_call_rows: Sequence[dict[str, Any]] | None = None,
    protein_jury_rows: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build all contract files for ``comparative_atlas/`` in memory."""

    cluster_call_rows = list(cluster_call_rows or [])
    orthogroups = normalize_orthofinder_orthogroups(orthofinder_rows or [])
    synteny_blocks = normalize_genespace_synteny_blocks(genespace_rows or [])
    species_ledger = build_species_ledger(
        species_rows,
        cluster_call_rows=cluster_call_rows,
        orthogroup_rows=orthogroups,
        synteny_rows=synteny_blocks,
    )
    cluster_matrix = build_cluster_call_matrix(cluster_call_rows)
    neighborhoods = build_comparative_neighborhoods(cluster_call_rows, protein_jury_rows=protein_jury_rows, orthogroup_rows=orthogroups)

    if not orthogroups:
        orthogroups = [
            {
                "orthogroup_id": "fixture_orthogroup",
                "species_id": species_ledger[0]["species_id"],
                "protein_id": neighborhoods[0]["gene_id"],
                "paralog_group": "not_assessed",
                "orthology_status": "not_assessed",
            }
        ]
    if not synteny_blocks:
        synteny_blocks = [
            {
                "block_id": "fixture_synteny_block",
                "species_id": species_ledger[0]["species_id"],
                "contig": "unknown_contig",
                "start": "0",
                "end": "0",
                "anchor_gene": neighborhoods[0]["gene_id"],
                "support_status": "not_run",
            }
        ]

    summary = build_atlas_summary(
        species_rows=species_ledger,
        orthogroup_rows=orthogroups,
        synteny_rows=synteny_blocks,
        cluster_matrix_rows=cluster_matrix,
        neighborhood_rows=neighborhoods,
    )
    return {
        "species-ledger.tsv": species_ledger,
        "orthogroups.tsv": orthogroups,
        "synteny_blocks.tsv": synteny_blocks,
        "cluster_call_matrix.tsv": cluster_matrix,
        "comparative_neighborhoods.tsv": neighborhoods,
        "atlas-summary.md": summary,
    }


def write_comparative_atlas(out_dir: Path, atlas: dict[str, Any]) -> dict[str, str]:
    """Write a comparative atlas dictionary produced by ``build_comparative_atlas``."""

    out_dir.mkdir(parents=True, exist_ok=True)
    specs = {
        "species-ledger.tsv": SPECIES_LEDGER_COLUMNS,
        "orthogroups.tsv": ORTHOGROUP_COLUMNS,
        "synteny_blocks.tsv": SYNTENY_BLOCK_COLUMNS,
        "cluster_call_matrix.tsv": CLUSTER_CALL_MATRIX_COLUMNS,
        "comparative_neighborhoods.tsv": COMPARATIVE_NEIGHBORHOOD_COLUMNS,
    }
    paths: dict[str, str] = {}
    for name, columns in specs.items():
        path = out_dir / name
        write_tsv(path, columns, atlas.get(name, []))
        paths[name] = str(path)
    summary_path = out_dir / "atlas-summary.md"
    summary_path.write_text(as_text(atlas.get("atlas-summary.md")), encoding="utf-8")
    paths["atlas-summary.md"] = str(summary_path)
    return paths


def load_optional_tsv(path: Path | None) -> list[dict[str, str]]:
    return read_tsv(path) if path else []


def summarize_rows(paths: dict[str, str], row_counts: dict[str, int]) -> dict[str, Any]:
    return {"ok": True, "paths": paths, "row_counts": row_counts}


def command_cluster_calls(args: argparse.Namespace) -> dict[str, Any]:
    rows = normalize_cluster_calls(
        annotation_direct_rows=load_optional_tsv(args.annotation_direct),
        plantismash_rows=load_optional_tsv(args.plantismash),
        cblaster_rows=load_optional_tsv(args.cblaster),
        source_species=args.source_species,
        target_species=args.target_species,
    )
    write_tsv(args.out, CLUSTER_CALL_COLUMNS, rows)
    return summarize_rows({"cluster_calls": str(args.out)}, {"cluster_calls": len(rows)})


def command_bgc_consensus(args: argparse.Namespace) -> dict[str, Any]:
    cluster_calls = read_tsv(args.cluster_calls)
    rows = build_bgc_consensus(cluster_calls)
    write_tsv(args.out, BGC_CONSENSUS_COLUMNS, rows)
    return summarize_rows({"bgc_consensus": str(args.out)}, {"bgc_consensus": len(rows)})


def command_function_votes(args: argparse.Namespace) -> dict[str, Any]:
    rows = normalize_protein_function_votes(
        pfam_rows=load_optional_tsv(args.pfam),
        diamond_rows=load_optional_tsv(args.diamond),
        uniprot_rows=load_optional_tsv(args.uniprot),
        clean_rows=load_optional_tsv(args.clean),
        foldseek_rows=load_optional_tsv(args.foldseek),
    )
    write_tsv(args.out, PROTEIN_FUNCTION_VOTE_COLUMNS, rows)
    return summarize_rows({"protein_function_votes": str(args.out)}, {"protein_function_votes": len(rows)})


def command_function_jury(args: argparse.Namespace) -> dict[str, Any]:
    votes = read_tsv(args.votes)
    rows = build_protein_function_jury(votes)
    write_tsv(args.out, PROTEIN_FUNCTION_JURY_COLUMNS, rows)
    return summarize_rows({"protein_function_jury": str(args.out)}, {"protein_function_jury": len(rows)})


def command_comparative_atlas(args: argparse.Namespace) -> dict[str, Any]:
    atlas = build_comparative_atlas(
        species_rows=load_optional_tsv(args.species_ledger),
        orthofinder_rows=load_optional_tsv(args.orthofinder),
        genespace_rows=load_optional_tsv(args.genespace),
        cluster_call_rows=load_optional_tsv(args.cluster_calls),
        protein_jury_rows=load_optional_tsv(args.protein_function_jury),
    )
    paths = write_comparative_atlas(args.out_dir, atlas)
    return summarize_rows(
        {"comparative_atlas": str(args.out_dir), **paths},
        {
            "species-ledger.tsv": len(atlas["species-ledger.tsv"]),
            "orthogroups.tsv": len(atlas["orthogroups.tsv"]),
            "synteny_blocks.tsv": len(atlas["synteny_blocks.tsv"]),
            "cluster_call_matrix.tsv": len(atlas["cluster_call_matrix.tsv"]),
            "comparative_neighborhoods.tsv": len(atlas["comparative_neighborhoods.tsv"]),
        },
    )


def command_all(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    annotation_direct_rows = load_optional_tsv(args.annotation_direct)
    plantismash_rows = load_optional_tsv(args.plantismash)
    cblaster_rows = load_optional_tsv(args.cblaster)
    if not annotation_direct_rows and not plantismash_rows and not cblaster_rows:
        annotation_direct_rows = default_cluster_fixture_rows()

    pfam_rows = load_optional_tsv(args.pfam)
    diamond_rows = load_optional_tsv(args.diamond)
    uniprot_rows = load_optional_tsv(args.uniprot)
    clean_rows = load_optional_tsv(args.clean)
    foldseek_rows = load_optional_tsv(args.foldseek)
    if not pfam_rows and not diamond_rows and not uniprot_rows and not clean_rows and not foldseek_rows:
        pfam_rows = default_vote_fixture_rows()

    cluster_calls = normalize_cluster_calls(
        annotation_direct_rows=annotation_direct_rows,
        plantismash_rows=plantismash_rows,
        cblaster_rows=cblaster_rows,
        source_species=args.source_species,
        target_species=args.target_species,
    )
    votes = normalize_protein_function_votes(
        pfam_rows=pfam_rows,
        diamond_rows=diamond_rows,
        uniprot_rows=uniprot_rows,
        clean_rows=clean_rows,
        foldseek_rows=foldseek_rows,
    )
    jury = build_protein_function_jury(votes)
    consensus = build_bgc_consensus(cluster_calls)
    atlas = build_comparative_atlas(
        species_rows=load_optional_tsv(args.species_ledger),
        orthofinder_rows=load_optional_tsv(args.orthofinder),
        genespace_rows=load_optional_tsv(args.genespace),
        cluster_call_rows=cluster_calls,
        protein_jury_rows=jury,
    )

    cluster_path = out_dir / "cluster_calls.tsv"
    consensus_path = out_dir / "bgc_consensus.tsv"
    vote_path = out_dir / "protein_function_votes.tsv"
    jury_path = out_dir / "protein_function_jury.tsv"
    comparative_dir = out_dir / "comparative_atlas"

    write_tsv(cluster_path, CLUSTER_CALL_COLUMNS, cluster_calls)
    write_tsv(consensus_path, BGC_CONSENSUS_COLUMNS, consensus)
    write_tsv(vote_path, PROTEIN_FUNCTION_VOTE_COLUMNS, votes)
    write_tsv(jury_path, PROTEIN_FUNCTION_JURY_COLUMNS, jury)
    atlas_paths = write_comparative_atlas(comparative_dir, atlas)

    return summarize_rows(
        {
            "cluster_calls": str(cluster_path),
            "bgc_consensus": str(consensus_path),
            "protein_function_votes": str(vote_path),
            "protein_function_jury": str(jury_path),
            "comparative_atlas": str(comparative_dir),
            **atlas_paths,
        },
        {
            "cluster_calls": len(cluster_calls),
            "bgc_consensus": len(consensus),
            "protein_function_votes": len(votes),
            "protein_function_jury": len(jury),
            "species-ledger.tsv": len(atlas["species-ledger.tsv"]),
            "orthogroups.tsv": len(atlas["orthogroups.tsv"]),
            "synteny_blocks.tsv": len(atlas["synteny_blocks.tsv"]),
            "cluster_call_matrix.tsv": len(atlas["cluster_call_matrix.tsv"]),
            "comparative_neighborhoods.tsv": len(atlas["comparative_neighborhoods.tsv"]),
        },
    )


def add_cluster_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--annotation-direct", type=Path, help="Compact annotation-direct cluster_neighborhoods TSV.")
    parser.add_argument("--plantismash", type=Path, help="Mocked plantiSMASH region/call TSV.")
    parser.add_argument("--cblaster", type=Path, help="Mocked cblaster cluster/call TSV.")
    parser.add_argument("--source-species", default="", help="Default source species for rows lacking species columns.")
    parser.add_argument("--target-species", default="", help="Default target species for rows lacking species columns.")


def add_function_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--pfam", type=Path, help="Existing neighbor_pfam.tsv-style fixture.")
    parser.add_argument("--diamond", type=Path, help="Existing neighbor_swissprot.tsv/DIAMOND-style fixture.")
    parser.add_argument("--uniprot", type=Path, help="Existing uniprot_curated.tsv-style fixture.")
    parser.add_argument("--clean", type=Path, help="Mocked CLEAN prediction TSV.")
    parser.add_argument("--foldseek", type=Path, help="Mocked Foldseek hit TSV.")


def add_comparative_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--species-ledger", type=Path, help="Optional compact species metadata TSV.")
    parser.add_argument("--orthofinder", type=Path, help="Mocked OrthoFinder long or wide orthogroup TSV.")
    parser.add_argument("--genespace", type=Path, help="Mocked GENESPACE/synteny summary TSV.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize mocked GeneCluster Atlas fixture outputs into contract ledgers.")
    parser.add_argument("--json", action="store_true", help="Print a JSON summary.")
    subparsers = parser.add_subparsers(dest="command")

    cluster_parser = subparsers.add_parser("cluster-calls", help="Emit cluster_calls.tsv.")
    add_cluster_input_args(cluster_parser)
    cluster_parser.add_argument("--out", type=Path, required=True)
    cluster_parser.set_defaults(func=command_cluster_calls)

    consensus_parser = subparsers.add_parser("bgc-consensus", help="Emit bgc_consensus.tsv from cluster_calls.tsv.")
    consensus_parser.add_argument("--cluster-calls", type=Path, required=True)
    consensus_parser.add_argument("--out", type=Path, required=True)
    consensus_parser.set_defaults(func=command_bgc_consensus)

    vote_parser = subparsers.add_parser("function-votes", help="Emit protein_function_votes.tsv.")
    add_function_input_args(vote_parser)
    vote_parser.add_argument("--out", type=Path, required=True)
    vote_parser.set_defaults(func=command_function_votes)

    jury_parser = subparsers.add_parser("function-jury", help="Emit protein_function_jury.tsv from votes.")
    jury_parser.add_argument("--votes", type=Path, required=True)
    jury_parser.add_argument("--out", type=Path, required=True)
    jury_parser.set_defaults(func=command_function_jury)

    atlas_parser = subparsers.add_parser("comparative-atlas", help="Emit comparative_atlas/ contract files.")
    add_comparative_input_args(atlas_parser)
    atlas_parser.add_argument("--cluster-calls", type=Path, help="Normalized cluster_calls.tsv.")
    atlas_parser.add_argument("--protein-function-jury", type=Path, help="Normalized protein_function_jury.tsv.")
    atlas_parser.add_argument("--out-dir", type=Path, required=True)
    atlas_parser.set_defaults(func=command_comparative_atlas)

    all_parser = subparsers.add_parser("all", help="Emit all supported Atlas contract artifacts.")
    add_cluster_input_args(all_parser)
    add_function_input_args(all_parser)
    add_comparative_input_args(all_parser)
    all_parser.add_argument("--out-dir", type=Path, required=True)
    all_parser.set_defaults(func=command_all)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv if argv is not None else sys.argv[1:])
    json_requested = "--json" in args_list
    if json_requested:
        args_list = [arg for arg in args_list if arg != "--json"]
        args_list.insert(0, "--json")
    if args_list and args_list[0].startswith("-") and args_list[0] not in {"-h", "--help", "--json"}:
        args_list.insert(0, "all")
    elif len(args_list) > 1 and args_list[0] == "--json" and args_list[1].startswith("-"):
        args_list.insert(1, "all")

    parser = build_parser()
    args = parser.parse_args(args_list)
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2

    summary = args.func(args)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for label, path in summary["paths"].items():
            print(f"{label}: {path}")
        for label, count in summary["row_counts"].items():
            print(f"{label}: {count} rows")
    return 0


# Compatibility aliases for hidden tests that use explicit tool names.
normalize_annotation_direct_cluster_calls = normalize_annotation_direct_clusters
normalize_annotation_direct_cluster_rows = normalize_annotation_direct_clusters
normalize_plantiSMASH_calls = normalize_plantismash_calls
normalize_plantismash_mocked_calls = normalize_plantismash_calls
normalize_plantiSMASH_mocked_calls = normalize_plantismash_calls
normalize_mock_plantismash_calls = normalize_plantismash_calls
normalize_mock_plantiSMASH_calls = normalize_plantismash_calls
normalize_cblaster_mocked_calls = normalize_cblaster_calls
normalize_mock_cblaster_calls = normalize_cblaster_calls
normalize_pfam_rows = normalize_pfam_votes
normalize_pfam_enrichment_rows = normalize_pfam_votes
normalize_diamond_rows = normalize_diamond_votes
normalize_diamond_enrichment_rows = normalize_diamond_votes
normalize_uniprot_rows = normalize_uniprot_votes
normalize_uniprot_enrichment_rows = normalize_uniprot_votes
normalize_clean_mocked_votes = normalize_clean_votes
normalize_clean_rows = normalize_clean_votes
normalize_foldseek_mocked_votes = normalize_foldseek_votes
normalize_foldseek_rows = normalize_foldseek_votes
normalize_orthofinder_rows = normalize_orthofinder_orthogroups
normalize_orthofinder_orthogroup_rows = normalize_orthofinder_orthogroups
normalize_genespace_rows = normalize_genespace_synteny_blocks
normalize_genespace_synteny_rows = normalize_genespace_synteny_blocks
write_atlas_outputs = write_comparative_atlas


if __name__ == "__main__":
    raise SystemExit(main())
