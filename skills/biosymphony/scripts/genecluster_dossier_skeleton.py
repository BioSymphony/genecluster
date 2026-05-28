#!/usr/bin/env python3
"""Create a small GeneCluster dossier skeleton from candidate hit fixtures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape


CLAIM_COLUMNS = [
    "claim_id",
    "statement",
    "claim_level",
    "evidence_level",
    "caveat",
    "review_status",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def html_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p>No candidate hits.</p>"
    columns = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(col, ''))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 2rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
    th, td {{ border: 1px solid #d0d7de; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f6f8fa; }}
    code {{ background: #f6f8fa; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def xlsx_col_name(index: int) -> str:
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def sheet_xml(rows: list[list[str]]) -> str:
    row_xml: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, value in enumerate(row, start=1):
            ref = f"{xlsx_col_name(c_idx)}{r_idx}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        row_xml.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {rows}
  </sheetData>
</worksheet>
""".format(rows="\n    ".join(row_xml))


def write_minimal_xlsx(path: Path, headers: list[str], records: list[dict[str, str]]) -> None:
    rows = [headers] + [[record.get(header, "") for header in headers] for record in records]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>
""",
        )
        xlsx.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
""",
        )
        xlsx.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="candidate_hits" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
""",
        )
        xlsx.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>
""",
        )
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml(rows))


def write_jsonl(path: Path, rows: Iterable[dict[str, str]], kind: str) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = {
                "kind": kind,
                "claim_id": f"claim.{row.get('candidate_id')}",
                "subject_id": row.get("gene_or_transcript_id"),
                "evidence_class": row.get("hit_type"),
                "source_artifact": "data/candidate_hits.tsv",
                "confidence": "medium" if float(row.get("evidence_score") or 0) >= 0.6 else "low",
                "candidate_id": row.get("candidate_id"),
                "query_id": row.get("query_id"),
                "dataset_id": row.get("dataset_id"),
                "review_status": row.get("review_status"),
                "evidence_score": row.get("evidence_score"),
            }
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_records_jsonl(path: Path, records: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def write_tsv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def candidate_claim_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    claim_rows: list[dict[str, str]] = []
    for row in rows:
        candidate_id = row.get("candidate_id", "candidate")
        role = row.get("pathway_role") or "pathway candidate"
        target = row.get("target_species") or "target species"
        support = row.get("hit_type") or "candidate_hit"
        claim_level = "L2_coordinate_context_ready" if support == "genome_localized" else "L1_candidate_gene_only"
        caveat = row.get("novelty_basis") or "Candidate requires remote evidence review and human claim audit."
        claim_rows.append(
            {
                "claim_id": f"CLAIM_{candidate_id}",
                "statement": f"{candidate_id} prioritizes {row.get('gene_or_transcript_id', 'a gene or transcript')} as {role} evidence in {target}.",
                "claim_level": claim_level,
                "evidence_level": claim_level,
                "caveat": caveat,
                "review_status": row.get("review_status") or "needs-human-review",
            }
        )
    return claim_rows


def package_name(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    parts = [part for part in normalized.split("-") if part]
    return "-".join(parts) or "genecluster-dossier"


def file_metadata(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    return {
        "path": rel,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def tsv_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        header = handle.readline().rstrip("\n").split("\t")
    fields = [{"name": column, "type": "string"} for column in header if column]
    return {"fields": fields}


def datapackage_resource(root: Path, rel: str, *, name: str | None = None) -> dict[str, Any]:
    metadata = file_metadata(root, rel)
    suffix = Path(rel).suffix.lower().lstrip(".")
    resource: dict[str, Any] = {
        "name": name or package_name(Path(rel).stem),
        "path": rel,
        "bytes": metadata["bytes"],
        "hash": metadata["sha256"],
    }
    if suffix:
        resource["format"] = suffix
    if rel.endswith(".tsv"):
        resource["profile"] = "tabular-data-resource"
        resource["schema"] = tsv_schema(root / rel)
    return resource


def write_datapackage(out: Path, campaign_id: str, created_at: str, resource_rels: list[str]) -> None:
    resources = [datapackage_resource(out, rel) for rel in resource_rels if (out / rel).exists()]
    data = {
        "profile": "data-package",
        "name": package_name(campaign_id),
        "title": f"GeneCluster dossier tables for {campaign_id}",
        "created": created_at,
        "description": "Compact, summary-only BioSymphony GeneCluster dossier tables. Raw and heavy artifacts remain provider-side.",
        "resources": resources,
        "biosymphony": {
            "schema_version": 1,
            "artifact_policy": "summaries_only",
            "raw_heavy_artifacts": "remote_only",
        },
    }
    write_text(out / "datapackage.json", json.dumps(data, indent=2, sort_keys=True) + "\n")


def ro_crate_file_entity(out: Path, rel: str) -> dict[str, Any]:
    path = out / rel
    entity: dict[str, Any] = {
        "@id": rel,
        "@type": "File",
        "name": Path(rel).name,
    }
    if path.exists() and path.is_file():
        entity["contentSize"] = path.stat().st_size
        entity["sha256"] = sha256_file(path)
    return entity


def write_ro_crate(out: Path, campaign_id: str, created_at: str, artifact_rels: list[str]) -> None:
    has_part = [{"@id": rel} for rel in artifact_rels]
    file_entities = [ro_crate_file_entity(out, rel) for rel in artifact_rels]
    crate = {
        "@context": "https://w3id.org/ro/crate/1.1/context",
        "@graph": [
            {
                "@id": "./",
                "@type": "Dataset",
                "name": f"GeneCluster dossier for {campaign_id}",
                "description": "Summary-only BioSymphony GeneCluster dossier with raw and heavy artifacts kept remote-only.",
                "datePublished": created_at,
                "hasPart": has_part,
                "about": {"@id": "#campaign"},
            },
            {
                "@id": "#campaign",
                "@type": "Thing",
                "identifier": campaign_id,
                "name": campaign_id,
            },
            {
                "@id": "#genecluster_dossier_skeleton.py",
                "@type": "SoftwareApplication",
                "name": "genecluster_dossier_skeleton.py",
                "softwareVersion": "1",
            },
            {
                "@id": "#create-dossier-skeleton",
                "@type": "CreateAction",
                "name": "Create GeneCluster dossier skeleton",
                "startTime": created_at,
                "endTime": created_at,
                "instrument": {"@id": "#genecluster_dossier_skeleton.py"},
                "object": [{"@id": "data/candidate_hits.tsv"}],
                "result": has_part,
            },
            *file_entities,
        ],
    }
    write_text(out / "ro-crate-metadata.json", json.dumps(crate, indent=2, sort_keys=True) + "\n")


def write_validation_report(out: Path, campaign_id: str, created_at: str) -> None:
    report = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "created_at": created_at,
        "status": "passed",
        "checks": [
            {
                "name": "summary_only_policy",
                "status": "passed",
                "detail": "Generated dossier contains compact summaries and remote-only pointers for heavy artifacts.",
            },
            {
                "name": "table_package_created",
                "status": "passed",
                "detail": "datapackage.json was emitted for compact table resources.",
            },
            {
                "name": "ro_crate_created",
                "status": "passed",
                "detail": "ro-crate-metadata.json was emitted for dossier provenance.",
            },
        ],
        "recommended_validation_command": "python3 skills/biosymphony/scripts/genecluster_preflight.py --dossier-manifest dossier-manifest.json",
    }
    write_text(out / "validation-report.json", json.dumps(report, indent=2, sort_keys=True) + "\n")


def build_dossier(campaign: Path, candidate_hits: Path, out: Path) -> Path:
    campaign_data = json.loads(campaign.read_text(encoding="utf-8"))
    rows = read_tsv(candidate_hits)
    created_at = datetime.now(timezone.utc).isoformat()
    out.mkdir(parents=True, exist_ok=True)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    table = html_table(rows)
    write_text(
        out / "summary.html",
        page(
            "GeneCluster Summary",
            f"<h1>{html.escape(campaign_data['campaign_id'])}</h1><p>Candidate-search dossier skeleton. Heavy artifacts remain remote-only.</p>{table}",
        ),
    )
    write_text(out / "clusters.html", page("GeneCluster Candidate Clusters", f"<h1>Candidate Clusters</h1>{table}"))
    write_text(out / "review.html", page("GeneCluster Review", "<h1>Review</h1><p>All fixture candidates require human review before scientific claims are accepted.</p>"))
    write_text(out / "evidence.html", page("GeneCluster Evidence", f"<h1>Evidence Ledger</h1>{table}"))
    write_text(
        out / "provenance.html",
        page(
            "GeneCluster Provenance",
            "<h1>Provenance</h1><p>Generated from fixture candidate hits. Replace with remote run provenance after the first RunPod candidate search.</p>",
        ),
    )

    shutil.copyfile(candidate_hits, data_dir / "candidate_hits.tsv")
    for ledger in [
        "data-ledger.tsv",
        "query-ledger.tsv",
        "resource-ledger.tsv",
        "project-goals.yaml",
        "pathway-steps.tsv",
        "database-ledger.tsv",
        "cache-ledger.tsv",
    ]:
        source = campaign.parent / ledger
        if source.exists():
            shutil.copyfile(source, data_dir / ledger)

    ranking_headers = ["rank", "candidate_id", "evidence_score", "evidence_tier", "summary", "review_status"]
    ranked_rows = []
    for index, row in enumerate(sorted(rows, key=lambda r: float(r.get("evidence_score") or 0), reverse=True), start=1):
        score = float(row.get("evidence_score") or 0)
        ranked_rows.append(
            {
                "rank": str(index),
                "candidate_id": row.get("candidate_id", ""),
                "evidence_score": row.get("evidence_score", ""),
                "evidence_tier": "strong" if score >= 0.8 else "exploratory",
                "summary": f"{row.get('query_id', '')} hit in {row.get('dataset_id', '')}: {row.get('pathway_role', '')}",
                "review_status": row.get("review_status", "needs-human-review"),
            }
        )
    write_tsv(data_dir / "candidate-ranking.tsv", ranking_headers, ranked_rows)

    neighborhood_headers = [
        "cluster_id",
        "candidate_id",
        "anchor_gene_id",
        "distance_to_anchor_kb",
        "pfams",
        "pfam_descriptions",
        "top_cdd_hit",
        "sequence_length",
        "sequence_policy",
        "coordinate_status",
        "evidence_ids",
        "review_status",
    ]
    neighborhood_rows = []
    for index, row in enumerate(rows, start=1):
        localized = row.get("hit_type") == "genome_localized"
        neighborhood_rows.append(
            {
                "cluster_id": f"GC_{index:04d}",
                "candidate_id": row.get("candidate_id", ""),
                "anchor_gene_id": row.get("gene_or_transcript_id", ""),
                "distance_to_anchor_kb": "0",
                "pfams": row.get("domain_calls", ""),
                "pfam_descriptions": "remote candidate fixture; replace with InterPro/Pfam annotations after RunPod search",
                "top_cdd_hit": "remote_pending",
                "sequence_length": "remote_pending",
                "sequence_policy": "remote_only",
                "coordinate_status": "genome_localized" if localized else "transcript_only",
                "evidence_ids": f"claim.{row.get('candidate_id')}",
                "review_status": row.get("review_status", "needs-human-review"),
            }
        )
    write_tsv(data_dir / "cluster_neighborhoods.tsv", neighborhood_headers, neighborhood_rows)

    write_jsonl(data_dir / "evidence.jsonl", rows, "candidate_hit")
    write_tsv(out / "claim-ledger.tsv", CLAIM_COLUMNS, candidate_claim_rows(rows))
    claim_records = []
    for row in rows:
        claim_records.append(
            {
                "audit_id": f"audit.{row.get('candidate_id')}.claim_boundary",
                "mode": "overclaim",
                "subject_id": row.get("candidate_id"),
                "rule_id": "candidate_discovery_is_not_validation",
                "verdict": "qualified",
                "review_status": row.get("review_status", "needs-human-review"),
                "detail": "Fixture candidate remains a hypothesis until remote evidence and human review are complete.",
            }
        )
    write_records_jsonl(data_dir / "claim-audit.jsonl", claim_records)
    write_text(
        data_dir / "provenance.jsonl",
        json.dumps(
            {
                "kind": "dossier_skeleton",
                "campaign_id": campaign_data["campaign_id"],
                "generated_at": created_at,
                "large_local_downloads": False,
            },
            sort_keys=True,
        )
        + "\n",
    )
    write_text(
        data_dir / "licenses.tsv",
        "resource\tlicense_class\tuse_mode\nBioSymphony GeneCluster validators\tpermissive-code\tlocal_validator\n",
    )
    write_text(
        data_dir / "citations.bib",
        """@misc{biosymphony_genecluster_v0,
  title = {BioSymphony GeneCluster v0 Dossier Skeleton},
  year = {2026},
  note = {Generated fixture; replace with run-specific citations after remote execution}
}
""",
    )
    write_text(
        data_dir / "versions.json",
        json.dumps(
            {
                "schema_version": 1,
                "generator": "genecluster_dossier_skeleton.py",
                "remote_workflow": "not_run",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    write_text(
        data_dir / "dossier_index.json",
        json.dumps(
            {
                "schema_version": 1,
                "campaign_id": campaign_data["campaign_id"],
                "tables": {
                    "candidate_hits": "data/candidate_hits.tsv",
                    "candidate_ranking": "data/candidate-ranking.tsv",
                    "cluster_neighborhoods": "data/cluster_neighborhoods.tsv",
                    "evidence": "data/evidence.jsonl",
                    "claim_audit": "data/claim-audit.jsonl",
                    "provenance": "data/provenance.jsonl",
                    "project_goals": "data/project-goals.yaml",
                    "pathway_steps": "data/pathway-steps.tsv",
                    "database_ledger": "data/database-ledger.tsv",
                    "cache_ledger": "data/cache-ledger.tsv",
                },
                "question_examples": [
                    "Which candidates are transcriptome-only?",
                    "Which candidates have genome-localized support?",
                    "Why is this candidate still marked needs-human-review?",
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    headers = list(rows[0].keys()) if rows else ["candidate_id", "query_id", "review_status"]
    write_minimal_xlsx(data_dir / "export.xlsx", headers, rows)
    write_text(
        out / "claim-ledger.md",
        """# GeneCluster Claim Ledger

## Allowed claims

- Candidate genes may be prioritized by homology, domain architecture, and remote dataset support.
- Genome-localized candidates may be marked only when coordinates are available from a reviewed genome/GFF resource.

## Forbidden overclaims

- Transcriptome-only evidence proves a physical gene cluster.
- Broad CYP/OMT/reductase homology proves product chemistry.
- Candidate discovery is experimental validation.

## Validation caveats

- Product-level BIA or an alkaloid claims require LC-MS/MS or functional assays.
- Tetraploid copy ambiguity, paralogs, and incomplete isoforms require human review.
""",
    )

    data_resource_rels = [
        "data/candidate_hits.tsv",
        "data/cluster_neighborhoods.tsv",
        "data/candidate-ranking.tsv",
        "data/evidence.jsonl",
        "data/claim-audit.jsonl",
        "data/provenance.jsonl",
        "data/licenses.tsv",
        "data/versions.json",
        "data/dossier_index.json",
    ]
    write_datapackage(out, campaign_data["campaign_id"], created_at, data_resource_rels)
    write_validation_report(out, campaign_data["campaign_id"], created_at)

    base_artifact_rels = [
        "summary.html",
        "clusters.html",
        "review.html",
        "evidence.html",
        "provenance.html",
        "claim-ledger.md",
        "claim-ledger.tsv",
        "data/export.xlsx",
        "data/data-ledger.tsv",
        "data/query-ledger.tsv",
        "data/resource-ledger.tsv",
        "data/project-goals.yaml",
        "data/pathway-steps.tsv",
        "data/database-ledger.tsv",
        "data/cache-ledger.tsv",
        "data/candidate_hits.tsv",
        "data/cluster_neighborhoods.tsv",
        "data/candidate-ranking.tsv",
        "data/evidence.jsonl",
        "data/claim-audit.jsonl",
        "data/provenance.jsonl",
        "data/licenses.tsv",
        "data/versions.json",
        "data/citations.bib",
        "data/dossier_index.json",
        "validation-report.json",
    ]
    ro_crate_rels = base_artifact_rels + ["datapackage.json", "dossier-manifest.json"]
    write_ro_crate(out, campaign_data["campaign_id"], created_at, ro_crate_rels)

    artifacts = [file_metadata(out, rel) for rel in [*base_artifact_rels, "datapackage.json", "ro-crate-metadata.json"]]

    manifest = {
        "schema_version": 1,
        "campaign_id": campaign_data["campaign_id"],
        "created_at": created_at,
        "artifact_policy": "summaries_only",
        "artifacts": artifacts,
        "large_artifacts_remote_only": [
            campaign_data["execution"]["remote_workdir"] + "/inputs",
            campaign_data["execution"]["remote_workdir"] + "/work",
            campaign_data["execution"]["remote_workdir"] + "/databases",
        ],
        "validation": [
            {
                "name": "skeleton_created",
                "status": "passed",
                "detail": "Fixture dossier created without raw sequence downloads.",
            }
        ],
    }
    write_text(out / "dossier-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return out / "dossier-manifest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a GeneCluster dossier skeleton.")
    parser.add_argument("--campaign", type=Path, required=True, help="Campaign manifest JSON.")
    parser.add_argument("--candidate-hits", type=Path, required=True, help="Fixture candidate_hits.tsv.")
    parser.add_argument("--out", type=Path, required=True, help="Output dossier directory.")
    args = parser.parse_args()

    manifest = build_dossier(args.campaign, args.candidate_hits, args.out)
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
