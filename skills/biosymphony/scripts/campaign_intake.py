#!/usr/bin/env python3
"""Wave 1 worker, variant + claim intake for the Mechanistic Variant Atlas.

Reads the campaign's variants.yaml and claims.yaml, normalizes them into
intake/variant_table.json with cross-referenced claim IDs per variant,
and produces intake/intake_report.md summarizing what was loaded.

Usage:
    python3 campaign_intake.py \
        --variants examples/egfr-resistance-v1/variants.yaml \
        --claims   examples/egfr-resistance-v1/claims.yaml \
        --out      intake/

Exit codes:
    0 success
    1 usage / file error
    2 missing dependency
    3 cross-reference error
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Allow running as a script regardless of cwd
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.load_yaml import load_yaml  # noqa: E402


def normalize_variant(v: dict) -> dict:
    """Pull a stable subset of fields from a variants.yaml entry."""
    return {
        "id": v["id"],
        "hgvs_protein": v.get("hgvs_protein", ""),
        "hgvs_coding": v.get("hgvs_coding", ""),
        "cosmic_id": v.get("cosmic_id", ""),
        "exon": v.get("exon"),
        "residue": v.get("residue"),
        "residue_range": v.get("residue_range"),
        "type": v.get("type", ""),
        "drug_context": v.get("drug_context", {}),
        "phenotype": v.get("phenotype", {}),
        "expected_pdb": v.get("expected_pdb", []),
        "afdb_available": bool(v.get("afdb_available", False)),
        "frequency_in_egfr_mutant_nsclc": v.get("frequency_in_egfr_mutant_nsclc"),
        "frequency_in_resistance_to_first_gen_tki": v.get(
            "frequency_in_resistance_to_first_gen_tki"
        ),
        "frequency_in_osimertinib_resistance": v.get(
            "frequency_in_osimertinib_resistance"
        ),
        "notes_for_classifier": v.get("notes_for_classifier", "").strip() or None,
    }


def build_table(variants_doc: dict, claims_doc: dict) -> dict:
    """Build the canonical variant_table.json structure."""
    target = variants_doc.get("target", {})
    variants = variants_doc.get("variants", [])
    claims = claims_doc.get("claims", [])

    variant_ids = {v["id"] for v in variants}

    # Cross-reference claims into per-variant lists
    by_variant: dict[str, list[str]] = {vid: [] for vid in variant_ids}
    bad_refs: list[str] = []
    for c in claims:
        ref = c.get("variant_ref")
        if ref in variant_ids:
            by_variant[ref].append(c["id"])
        else:
            bad_refs.append(c["id"])

    rows = []
    for v in variants:
        row = normalize_variant(v)
        row["claim_ids"] = sorted(by_variant.get(v["id"], []))
        row["claim_count"] = len(row["claim_ids"])
        rows.append(row)

    table = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "campaign": claims_doc.get("campaign") or variants_doc.get("campaign", "unknown"),
        "target": target,
        "variants": rows,
        "claims": claims,
        "diagnostics": {
            "variant_count": len(rows),
            "claim_count": len(claims),
            "claims_with_bad_variant_ref": bad_refs,
        },
    }
    return table


def write_intake_report(table: dict, path: Path) -> None:
    """Human-readable summary of what was loaded."""
    diag = table["diagnostics"]
    type_counts = Counter(v["type"] for v in table["variants"])
    afdb = sum(1 for v in table["variants"] if v["afdb_available"])
    has_pdb = sum(1 for v in table["variants"] if v["expected_pdb"])
    no_struct = [v["id"] for v in table["variants"] if not v["expected_pdb"] and not v["afdb_available"]]
    expected_verdicts = Counter(c.get("expected_verdict", "unset") for c in table["claims"])

    lines: list[str] = []
    lines.append(f"# Intake report, {table['campaign']}")
    lines.append("")
    lines.append(f"Generated: {table['generated_at']}")
    target = table["target"]
    if target:
        lines.append(
            f"Target: {target.get('gene_symbol', '?')} "
            f"({target.get('uniprot', '?')})"
        )
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append(f"- variants: {diag['variant_count']}")
    lines.append(f"- claims: {diag['claim_count']}")
    lines.append(f"- variants with AFDB available: {afdb}")
    lines.append(f"- variants with at least one expected PDB: {has_pdb}")
    lines.append("")
    lines.append("## Variant types")
    lines.append("")
    for t, n in sorted(type_counts.items()):
        lines.append(f"- {t}: {n}")
    lines.append("")
    lines.append("## Expected verdict distribution (Wave 10 targets)")
    lines.append("")
    for verdict, n in sorted(expected_verdicts.items()):
        lines.append(f"- {verdict}: {n}")
    lines.append("")
    if no_struct:
        lines.append("## Variants with no PDB and no AFDB flag")
        lines.append("")
        lines.append(
            "These will require PyMOL `mutate` fallback in Wave 3 with explicit "
            "modeling caveats:"
        )
        lines.append("")
        for vid in no_struct:
            lines.append(f"- {vid}")
        lines.append("")
    if diag["claims_with_bad_variant_ref"]:
        lines.append("## Cross-reference errors")
        lines.append("")
        lines.append("Claims reference variant IDs not present in variants.yaml:")
        lines.append("")
        for cid in diag["claims_with_bad_variant_ref"]:
            lines.append(f"- {cid}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BioSymphony Mechanistic Variant Atlas Wave 1, intake."
    )
    parser.add_argument(
        "--variants", type=Path, required=True, help="Path to variants.yaml"
    )
    parser.add_argument(
        "--claims", type=Path, required=True, help="Path to claims.yaml"
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any claim references a non-existent variant.",
    )
    args = parser.parse_args()

    if not args.variants.is_file():
        print(f"variants file not found: {args.variants}", file=sys.stderr)
        return 1
    if not args.claims.is_file():
        print(f"claims file not found: {args.claims}", file=sys.stderr)
        return 1

    variants_doc = load_yaml(args.variants)
    claims_doc = load_yaml(args.claims)

    table = build_table(variants_doc, claims_doc)
    args.out.mkdir(parents=True, exist_ok=True)

    table_path = args.out / "variant_table.json"
    table_path.write_text(json.dumps(table, indent=2), encoding="utf-8")

    report_path = args.out / "intake_report.md"
    write_intake_report(table, report_path)

    print(f"wrote {table_path}")
    print(f"wrote {report_path}")
    print(
        f"variants={table['diagnostics']['variant_count']} "
        f"claims={table['diagnostics']['claim_count']}"
    )

    bad = table["diagnostics"]["claims_with_bad_variant_ref"]
    if bad:
        print(f"WARN: {len(bad)} claim(s) reference unknown variants: {bad}", file=sys.stderr)
        if args.strict:
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
