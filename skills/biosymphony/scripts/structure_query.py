#!/usr/bin/env python3
"""Wave 2 worker, structure mapping for the Mechanistic Variant Atlas.

For a given variant, query RCSB PDB and AlphaFold DB to assemble a
candidate structure list with metadata: resolution, ligands, chain
mapping, deposition date, and source.

Usage:
    python3 structure_query.py \\
        --variant T790M \\
        --table   intake/variant_table.json \\
        --out     mapping/T790M/

Network behavior:
    - Reads RCSB PDB entry metadata for every PDB ID listed in
      `expected_pdb` for the variant.
    - Queries AlphaFold DB for the target's UniProt accession.
    - Network failures are recorded as warnings in mapping_report.md
      rather than crashing the worker. The candidate_structures.json
      always reflects what could be retrieved.
    - Use --offline to skip all HTTP calls (returns the expected_pdb
      hints with no live metadata).

Exit codes:
    0 success (even if some entries failed; check mapping_report.md)
    1 usage / file error
    4 fatal: variant not found in table
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RCSB_ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
RCSB_POLYMER_URL = (
    "https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"
)
AFDB_PREDICTION_URL = "https://alphafold.ebi.ac.uk/api/prediction/{uniprot}"

USER_AGENT = "BioSymphony/0.1 (mechanistic-variant-atlas; contact: local)"
HTTP_TIMEOUT_SECONDS = 30


def http_get_json(url: str) -> tuple[Any | None, str | None]:
    """Fetch URL and parse JSON. Returns (data, error_message)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset)
            return json.loads(body), None
    except urllib.error.HTTPError as e:
        return None, f"http {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return None, f"url error: {e.reason}"
    except (json.JSONDecodeError, ValueError) as e:
        return None, f"json parse: {e}"
    except OSError as e:
        return None, f"os error: {e}"


def fetch_rcsb_entry(pdb_id: str) -> tuple[dict | None, str | None]:
    return http_get_json(RCSB_ENTRY_URL.format(pdb_id=pdb_id.lower()))


def fetch_afdb_prediction(uniprot: str) -> tuple[Any | None, str | None]:
    return http_get_json(AFDB_PREDICTION_URL.format(uniprot=uniprot.upper()))


def summarize_rcsb_entry(entry: dict) -> dict:
    """Pull the campaign-relevant fields from a RCSB entry payload."""
    pdb_id = entry.get("rcsb_id", "").upper()
    rcsb_accession = entry.get("rcsb_accession_info", {}) or {}
    refine = (entry.get("refine") or [{}])[0]
    resolution = None
    if entry.get("rcsb_entry_info", {}).get("resolution_combined"):
        resolution = entry["rcsb_entry_info"]["resolution_combined"][0]
    elif refine.get("ls_d_res_high") is not None:
        resolution = refine.get("ls_d_res_high")

    method = entry.get("exptl", [{}])[0].get("method") if entry.get("exptl") else None
    title = entry.get("struct", {}).get("title", "")

    polymer_ids = entry.get("rcsb_entry_container_identifiers", {}).get(
        "polymer_entity_ids", []
    )
    ligand_ids = entry.get("rcsb_entry_container_identifiers", {}).get(
        "non_polymer_entity_ids", []
    )

    return {
        "pdb_id": pdb_id,
        "title": title,
        "method": method,
        "resolution_angstrom": resolution,
        "deposition_date": rcsb_accession.get("deposit_date"),
        "release_date": rcsb_accession.get("initial_release_date"),
        "polymer_entity_ids": polymer_ids,
        "non_polymer_entity_ids": ligand_ids,
    }


def summarize_afdb_prediction(payload: Any) -> dict | None:
    """Pull the campaign-relevant fields from the AFDB prediction payload."""
    if not payload:
        return None
    if isinstance(payload, list):
        if not payload:
            return None
        entry = payload[0]
    elif isinstance(payload, dict):
        entry = payload
    else:
        return None
    return {
        "uniprot": entry.get("uniprotAccession"),
        "model_url": entry.get("pdbUrl") or entry.get("cifUrl"),
        "model_format": "pdb" if entry.get("pdbUrl") else "cif",
        "version": entry.get("modelVersion") or entry.get("model_version"),
        "global_metric_value": entry.get("globalMetricValue"),
        "metric_type": entry.get("globalMetric") or "pLDDT",
    }


def build_candidate_structures(
    variant: dict,
    target: dict,
    *,
    offline: bool = False,
) -> tuple[dict, list[str]]:
    """Build the candidate_structures.json payload for one variant."""
    notes: list[str] = []
    candidates: list[dict] = []

    # 1. Expected-PDB hints from variants.yaml: fetched live
    for expected in variant.get("expected_pdb", []):
        pdb_id = expected["id"]
        entry: dict[str, Any] = {
            "source": "rcsb",
            "pdb_id": pdb_id,
            "expected_ligand": expected.get("ligand"),
            "expected_notes": expected.get("notes"),
            "kind": "experimental",
        }
        if offline:
            entry["live_metadata"] = None
            entry["fetch_error"] = "offline mode"
            candidates.append(entry)
            continue
        data, err = fetch_rcsb_entry(pdb_id)
        if err:
            entry["live_metadata"] = None
            entry["fetch_error"] = err
            notes.append(f"RCSB fetch failed for {pdb_id}: {err}")
        else:
            entry["live_metadata"] = summarize_rcsb_entry(data or {})
            entry["fetch_error"] = None
        candidates.append(entry)

    # 2. AlphaFold DB lookup for the target's WT
    uniprot = target.get("uniprot")
    afdb_record: dict | None = None
    if uniprot:
        if offline:
            notes.append("AFDB lookup skipped (offline)")
        elif variant.get("afdb_available"):
            data, err = fetch_afdb_prediction(uniprot)
            if err:
                notes.append(f"AFDB fetch failed for {uniprot}: {err}")
            else:
                afdb_record = summarize_afdb_prediction(data)
                if afdb_record:
                    afdb_record.update(
                        {
                            "source": "afdb",
                            "kind": "predicted",
                            "represents": "wild-type",
                            "note": (
                                "AFDB hosts a single canonical prediction per UniProt. "
                                "Variant-specific fold for this position is not in AFDB; "
                                "use this as the WT reference and consider PyMOL `mutate` "
                                "or a Tier B predictor for the variant fold."
                            ),
                        }
                    )

    # 3. Mutagenesis fallback decision
    has_holo_experimental = any(
        c.get("kind") == "experimental" and c.get("expected_ligand") for c in candidates
    )
    has_any_experimental = any(c.get("kind") == "experimental" for c in candidates)
    needs_mutagenesis_fallback = (
        not has_holo_experimental
        and variant.get("type", "").endswith("resistance")
    )

    payload = {
        "schema_version": 1,
        "campaign": "mechanistic-variant-atlas",
        "variant_id": variant["id"],
        "uniprot": uniprot,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experimental_candidates": [c for c in candidates if c.get("kind") == "experimental"],
        "afdb_reference": afdb_record,
        "needs_mutagenesis_fallback": needs_mutagenesis_fallback,
        "fallback_strategy": (
            "PyMOL mutate against the closest WT holo structure when no variant "
            "structure is deposited and a TKI-bound complex is required for Wave 4 metrics."
        )
        if needs_mutagenesis_fallback
        else None,
        "diagnostics": {
            "experimental_count": sum(1 for c in candidates if c.get("kind") == "experimental"),
            "experimental_with_ligand_count": sum(
                1 for c in candidates if c.get("kind") == "experimental" and c.get("expected_ligand")
            ),
            "fetch_warnings": notes,
            "any_experimental_found": has_any_experimental,
        },
    }
    return payload, notes


def write_mapping_report(payload: dict, path: Path) -> None:
    diag = payload["diagnostics"]
    lines: list[str] = []
    lines.append(f"# Mapping report, variant {payload['variant_id']}")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append(f"Target UniProt: {payload['uniprot']}")
    lines.append("")
    lines.append("## Experimental candidates")
    lines.append("")
    if not payload["experimental_candidates"]:
        lines.append("- (none)")
    for c in payload["experimental_candidates"]:
        meta = c.get("live_metadata") or {}
        res = meta.get("resolution_angstrom")
        line = f"- `{c['pdb_id']}`"
        if c.get("expected_ligand"):
            line += f" with {c['expected_ligand']}"
        if res is not None:
            line += f", {res} Å"
        if meta.get("method"):
            line += f", {meta['method']}"
        if meta.get("deposition_date"):
            line += f", deposited {meta['deposition_date']}"
        lines.append(line)
        if c.get("fetch_error"):
            lines.append(f"  - fetch_error: {c['fetch_error']}")
        if c.get("expected_notes"):
            lines.append(f"  - notes: {c['expected_notes']}")
    lines.append("")
    lines.append("## AFDB reference")
    lines.append("")
    if payload["afdb_reference"]:
        a = payload["afdb_reference"]
        lines.append(f"- UniProt {a.get('uniprot')}: {a.get('model_format')} model v{a.get('version')}")
        if a.get("global_metric_value") is not None:
            lines.append(f"  - {a.get('metric_type')}: {a['global_metric_value']}")
    else:
        lines.append("- (no AFDB record retrieved or AFDB lookup skipped)")
    lines.append("")
    if payload["needs_mutagenesis_fallback"]:
        lines.append("## Mutagenesis fallback")
        lines.append("")
        lines.append(payload["fallback_strategy"] or "")
        lines.append("")
    if diag["fetch_warnings"]:
        lines.append("## Fetch warnings")
        lines.append("")
        for w in diag["fetch_warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BioSymphony Mechanistic Variant Atlas Wave 2, structure mapping."
    )
    parser.add_argument("--variant", required=True, help="Variant ID (e.g., T790M).")
    parser.add_argument("--table", type=Path, required=True, help="Path to intake/variant_table.json.")
    parser.add_argument("--out", type=Path, required=True, help="Output directory.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip all HTTP calls; emit only the expected_pdb hints.",
    )
    args = parser.parse_args()

    if not args.table.is_file():
        print(f"variant table not found: {args.table}", file=sys.stderr)
        return 1

    table = json.loads(args.table.read_text(encoding="utf-8"))
    target = table.get("target", {})
    variant = next((v for v in table["variants"] if v["id"] == args.variant), None)
    if variant is None:
        print(f"variant not found in table: {args.variant}", file=sys.stderr)
        return 4

    payload, notes = build_candidate_structures(variant, target, offline=args.offline)

    args.out.mkdir(parents=True, exist_ok=True)
    cs_path = args.out / "candidate_structures.json"
    cs_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_mapping_report(payload, args.out / "mapping_report.md")

    print(f"wrote {cs_path}")
    print(
        f"variant={args.variant} "
        f"experimental_found={payload['diagnostics']['experimental_count']} "
        f"with_ligand={payload['diagnostics']['experimental_with_ligand_count']} "
        f"fallback_needed={payload['needs_mutagenesis_fallback']}"
    )
    if notes:
        print(f"WARN: {len(notes)} fetch warning(s); see mapping_report.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
