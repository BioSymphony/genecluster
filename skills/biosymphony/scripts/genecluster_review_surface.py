#!/usr/bin/env python3
"""Build a static, summary-only GeneCluster Atlas review surface."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
from pathlib import Path
from typing import Any


RAW_HEAVY_SUFFIXES = (
    ".fastq",
    ".fastq.gz",
    ".fq",
    ".fq.gz",
    ".sra",
    ".bam",
    ".sam",
    ".cram",
    ".fasta",
    ".fa",
    ".fna",
    ".faa",
    ".gff",
    ".gff3",
    ".gtf",
    ".dmnd",
    ".hmm",
    ".bt2",
    ".mmi",
    ".idx",
    ".sqlite",
)


CLAIM_COLUMNS = [
    "claim_id",
    "statement",
    "claim_level",
    "evidence_level",
    "caveat",
    "review_status",
]


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def is_raw_heavy(path: Path | str) -> bool:
    text = str(path).lower()
    return any(text.endswith(suffix) for suffix in RAW_HEAVY_SUFFIXES)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "item"


def title_from_species_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.replace("_", "-").split("-") if part)


def discover_species(final_deliverable: Path | None) -> list[dict[str, str]]:
    if final_deliverable is None or not final_deliverable.exists():
        return []
    records: dict[str, dict[str, str]] = {}
    for md in sorted(final_deliverable.glob("biology-*.md")):
        species_slug = md.stem.removeprefix("biology-")
        records.setdefault(species_slug, {"species_slug": species_slug, "name": title_from_species_slug(species_slug)})
        records[species_slug]["biology_md"] = str(md)
    for workbook in sorted(final_deliverable.glob("*.xlsx")):
        species_slug = workbook.stem.rsplit("-bia-pathway", 1)[0]
        records.setdefault(species_slug, {"species_slug": species_slug, "name": title_from_species_slug(species_slug)})
        records[species_slug]["workbook"] = str(workbook)
    return [records[key] for key in sorted(records)]


def default_claims(species: list[dict[str, str]]) -> list[dict[str, str]]:
    claims: list[dict[str, str]] = []
    for record in species:
        name = record["name"]
        slug = record["species_slug"]
        claims.append(
            {
                "claim_id": f"CLAIM_{slugify(slug).upper().replace('-', '_')}_ANNOTATION_CONTEXT",
                "statement": f"{name} has annotation-direct neighborhood evidence summarized in the Atlas review bundle.",
                "claim_level": "L3_annotation_neighborhood_ready",
                "evidence_level": "L3_annotation_neighborhood_ready",
                "caveat": "Summary review only; product chemistry and enzyme activity remain unvalidated.",
                "review_status": "accepted",
            }
        )
    if not claims:
        claims.append(
            {
                "claim_id": "CLAIM_ATLAS_REVIEW_SURFACE",
                "statement": "GeneCluster Atlas review surface was generated from compact summary inputs.",
                "claim_level": "L3_annotation_neighborhood_ready",
                "evidence_level": "L3_annotation_neighborhood_ready",
                "caveat": "No species-specific claim was provided.",
                "review_status": "accepted",
            }
        )
    return claims


def load_claims(path: Path | None, species: list[dict[str, str]]) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return default_claims(species)
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        rows = [{column: row.get(column, "") for column in CLAIM_COLUMNS} for row in reader]
    return rows or default_claims(species)


def write_claim_ledgers(out_dir: Path, claims: list[dict[str, str]]) -> tuple[Path, Path]:
    tsv = out_dir / "claim-ledger.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=CLAIM_COLUMNS)
        writer.writeheader()
        writer.writerows(claims)
    lines = ["# GeneCluster Atlas Claim Ledger", ""]
    for claim in claims:
        lines.extend(
            [
                f"## {claim['claim_id']}",
                "",
                claim["statement"],
                "",
                f"- Claim level: `{claim['claim_level']}`",
                f"- Evidence level: `{claim['evidence_level']}`",
                f"- Review status: `{claim['review_status']}`",
                f"- Caveat: {claim['caveat']}",
                "",
            ]
        )
    md = out_dir / "claim-ledger.md"
    write_text(md, "\n".join(lines))
    return tsv, md


def rel_link(target: str, from_dir: Path) -> str:
    if not target:
        return ""
    return os.path.relpath(target, start=from_dir)


def render_page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #20242a; line-height: 1.45; }}
    main {{ max-width: 1080px; margin: 0 auto; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #d8dde3; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f5f7; }}
    a {{ color: #1f5fbf; }}
    .claim {{ border-left: 4px solid #46737f; padding: 10px 14px; background: #f7fafb; margin: 12px 0; }}
    .muted {{ color: #66717d; }}
    pre {{ white-space: pre-wrap; background: #f6f8fa; padding: 12px; overflow-x: auto; }}
  </style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""


def markdown_excerpt(path: str, max_chars: int = 3200) -> str:
    text = read_text(Path(path))
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n\n[truncated in review surface]"
    return html.escape(text)


def write_species_pages(out_dir: Path, species: list[dict[str, str]]) -> list[Path]:
    generated: list[Path] = []
    species_dir = out_dir / "species"
    for record in species:
        page = species_dir / f"{record['species_slug']}.html"
        workbook_link = ""
        if record.get("workbook") and not is_raw_heavy(record["workbook"]):
            href = html.escape(rel_link(record["workbook"], page.parent))
            workbook_link = f'<p><a href="{href}">Open workbook</a></p>'
        body = f"""
<h1>{html.escape(record['name'])}</h1>
{workbook_link}
<h2>Biology Summary</h2>
<pre>{markdown_excerpt(record.get('biology_md', ''))}</pre>
<p><a href="../index.html">Back to overview</a></p>
"""
        write_text(page, render_page(record["name"], body))
        generated.append(page)
    return generated


def write_cluster_pages(out_dir: Path, claims: list[dict[str, str]]) -> list[Path]:
    clusters_dir = out_dir / "clusters"
    generated: list[Path] = []
    for claim in claims:
        page = clusters_dir / f"{slugify(claim['claim_id'])}.html"
        body = f"""
<h1>{html.escape(claim['claim_id'])}</h1>
<div class="claim">
  <p>{html.escape(claim['statement'])}</p>
  <p><strong>Claim level:</strong> {html.escape(claim['claim_level'])}<br>
  <strong>Evidence level:</strong> {html.escape(claim['evidence_level'])}<br>
  <strong>Review status:</strong> {html.escape(claim['review_status'])}</p>
  <p><strong>Caveat:</strong> {html.escape(claim['caveat'])}</p>
</div>
<p><a href="../index.html">Back to overview</a></p>
"""
        write_text(page, render_page(claim["claim_id"], body))
        generated.append(page)
    return generated


def claim_count_rows(claims: list[dict[str, str]]) -> str:
    counts: dict[tuple[str, str], int] = {}
    for claim in claims:
        key = (claim.get("claim_level", ""), claim.get("review_status", ""))
        counts[key] = counts.get(key, 0) + 1
    rows = []
    for (claim_level, review_status), count in sorted(counts.items()):
        rows.append(
            "<tr>"
            f"<td>{html.escape(claim_level)}</td>"
            f"<td>{html.escape(review_status)}</td>"
            f"<td>{count}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def write_index(out_dir: Path, review_id: str, species: list[dict[str, str]], claims: list[dict[str, str]]) -> Path:
    if species:
        species_rows = "\n".join(
            f"<tr><td>{html.escape(record['name'])}</td><td><a href=\"species/{html.escape(record['species_slug'])}.html\">summary</a></td></tr>"
            for record in species
        )
        species_section = f"<h2>Species</h2>\n<table><thead><tr><th>Species</th><th>Review</th></tr></thead><tbody>{species_rows}</tbody></table>"
    else:
        species_section = '<h2>Species</h2>\n<p class="muted">No species pages were provided; this review is claim-ledger-only.</p>'
    claim_cards = "\n".join(
        f"<div class=\"claim\"><strong>{html.escape(claim['claim_id'])}</strong><p>{html.escape(claim['statement'])}</p><p class=\"muted\">Claim: {html.escape(claim['claim_level'])}; evidence: {html.escape(claim['evidence_level'])}; status: {html.escape(claim['review_status'])}</p><p class=\"muted\">{html.escape(claim['caveat'])}</p><a href=\"clusters/{slugify(claim['claim_id'])}.html\">claim card</a></div>"
        for claim in claims
    )
    claim_summary = claim_count_rows(claims)
    body = f"""
<h1>GeneCluster Atlas Review Surface</h1>
<p class="muted">Review ID: {html.escape(review_id)}. Generated {timestamp()}.</p>
{species_section}
<h2>Claim Summary</h2>
<table><thead><tr><th>Claim level</th><th>Review status</th><th>Count</th></tr></thead><tbody>{claim_summary}</tbody></table>
<h2>Claims</h2>
{claim_cards}
<h2>Ledgers</h2>
<ul>
  <li><a href="claim-ledger.tsv">claim-ledger.tsv</a></li>
  <li><a href="claim-ledger.md">claim-ledger.md</a></li>
</ul>
"""
    page = out_dir / "index.html"
    write_text(page, render_page("GeneCluster Atlas Review", body))
    return page


def build_review_surface(
    out_dir: Path,
    *,
    review_id: str,
    final_deliverable: Path | None = None,
    claim_ledger: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    species = discover_species(final_deliverable)
    claims = load_claims(claim_ledger, species)
    claim_tsv, claim_md = write_claim_ledgers(out_dir, claims)
    generated = [write_index(out_dir, review_id, species, claims)]
    generated.extend(write_species_pages(out_dir, species))
    generated.extend(write_cluster_pages(out_dir, claims))

    source_tables: list[dict[str, str]] = [
        {"path": str(claim_tsv.relative_to(out_dir)), "artifact_type": "summary_table", "sensitivity": "summary"}
    ]
    if final_deliverable:
        for path in sorted(final_deliverable.glob("biology-*.md")) + sorted(final_deliverable.glob("*.xlsx")):
            if not is_raw_heavy(path):
                source_tables.append({"path": str(path), "artifact_type": "summary_document", "sensitivity": "summary"})

    manifest = {
        "schema_version": "genecluster_review_surface.v1",
        "review_id": review_id,
        "generated_at": timestamp(),
        "source_tables": source_tables,
        "generated_files": [
            {"path": str(path.relative_to(out_dir)), "artifact_type": "review_html" if path.suffix == ".html" else "summary_table", "sensitivity": "summary"}
            for path in generated + [claim_tsv, claim_md]
        ],
        "claims": claims,
    }
    manifest_path = out_dir / "review_surface_manifest.json"
    write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {
        "ok": True,
        "review_id": review_id,
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "generated_files": [str(path) for path in generated + [claim_tsv, claim_md, manifest_path]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a static summary-only GeneCluster Atlas review surface.")
    parser.add_argument("--atlas-dir", type=Path, help="Reserved for future Atlas summary directory input.")
    parser.add_argument("--final-deliverable", type=Path, help="Directory containing compact workbooks and biology markdown.")
    parser.add_argument("--claim-ledger", type=Path, help="Optional claim-ledger.tsv to reuse.")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--review-id", default="genecluster-atlas-review")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = build_review_surface(
        args.out_dir,
        review_id=args.review_id,
        final_deliverable=args.final_deliverable or args.atlas_dir,
        claim_ledger=args.claim_ledger,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"review_surface={result['out_dir']}")
        print(f"manifest={result['manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
