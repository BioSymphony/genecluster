#!/usr/bin/env python3
"""Wave 4 metric, gatekeeper-residue distance and VDW overlap to a bound ligand.

The gatekeeper residue (T790 in EGFR) is the canonical site that determines
whether a Type I TKI fits in the ATP cleft. This metric computes:

    - min heavy-atom distance from the gatekeeper residue sidechain to the ligand
    - VDW overlap = (rA + rB) - distance, summed over close pairs (positive = clash)
    - per-pair contacts within --close-cutoff for context

Usage:
    python3 gatekeeper_distance.py \\
        --structure 3UG2.pdb \\
        --gatekeeper A:790 \\
        --ligand-resname IRE \\
        --out metrics/T790M/gatekeeper_distance.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.pdb_parser import Atom, parse_pdb  # noqa: E402

# Simple Bondi-style VDW radii for common protein/ligand elements (Å).
VDW_RADIUS = {
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "F": 1.47,
    "CL": 1.75,
    "BR": 1.85,
    "I": 1.98,
    "H": 1.20,
}


def vdw_radius(element: str) -> float:
    return VDW_RADIUS.get(element.upper(), 1.7)


def parse_residue_spec(spec: str) -> tuple[str, int]:
    sep = ":" if ":" in spec else "/"
    chain, resseq = spec.split(sep, 1)
    return chain, int(resseq)


def sidechain_atoms(atoms: list[Atom], chain: str, resseq: int) -> list[Atom]:
    """Return non-backbone heavy atoms of the residue. If sidechain is absent (e.g., GLY), fall back to CB or CA."""
    backbone = {"N", "CA", "C", "O", "OXT"}
    residue = [a for a in atoms if a.chain == chain and a.resseq == resseq and a.element != "H"]
    sidechain = [a for a in residue if a.name not in backbone]
    if not sidechain:
        # GLY or stripped residue: fall back to CA
        ca = [a for a in residue if a.name == "CA"]
        return ca
    return sidechain


def ligand_heavy_atoms(atoms: list[Atom], resname: str) -> list[Atom]:
    return [
        a
        for a in atoms
        if a.record == "HETATM" and a.resname == resname.upper() and a.element != "H"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gatekeeper-to-ligand distance and VDW overlap."
    )
    parser.add_argument("--structure", type=Path, required=True, help="Holo structure (PDB).")
    parser.add_argument(
        "--gatekeeper",
        required=True,
        help="Gatekeeper residue (chain:resseq, e.g., A:790).",
    )
    parser.add_argument("--ligand-resname", required=True, help="HETATM residue name of the ligand.")
    parser.add_argument(
        "--close-cutoff",
        type=float,
        default=5.0,
        help="Distance cutoff for reporting per-pair contacts.",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path.")
    args = parser.parse_args()

    if not args.structure.is_file():
        print(f"structure not found: {args.structure}", file=sys.stderr)
        return 1

    atoms = parse_pdb(args.structure)
    chain, resseq = parse_residue_spec(args.gatekeeper)

    sc = sidechain_atoms(atoms, chain, resseq)
    lig = ligand_heavy_atoms(atoms, args.ligand_resname)

    payload: dict = {
        "schema_version": 1,
        "metric": "gatekeeper_distance",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "structure_path": str(args.structure),
        "gatekeeper": args.gatekeeper,
        "ligand_resname": args.ligand_resname.upper(),
        "diagnostics": {
            "gatekeeper_atoms_found": len(sc),
            "ligand_atoms_found": len(lig),
        },
    }

    if not sc:
        payload["error"] = f"gatekeeper residue {args.gatekeeper} not found"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} (gatekeeper not found)")
        return 0
    if not lig:
        payload["error"] = f"ligand {args.ligand_resname} not found in structure"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.out} (ligand not found)")
        return 0

    pair_records: list[dict] = []
    min_distance = float("inf")
    min_pair: tuple[Atom, Atom] | None = None
    total_overlap = 0.0
    overlapping_pairs = 0

    for s_atom in sc:
        for l_atom in lig:
            d = s_atom.distance_to(l_atom)
            r_sum = vdw_radius(s_atom.element) + vdw_radius(l_atom.element)
            overlap = r_sum - d
            if d < min_distance:
                min_distance = d
                min_pair = (s_atom, l_atom)
            if d <= args.close_cutoff:
                pair_records.append(
                    {
                        "sidechain_atom": s_atom.name,
                        "sidechain_element": s_atom.element,
                        "ligand_atom": l_atom.name,
                        "ligand_element": l_atom.element,
                        "distance_angstrom": round(d, 3),
                        "vdw_overlap_angstrom": round(overlap, 3),
                    }
                )
            if overlap > 0:
                overlapping_pairs += 1
                total_overlap += overlap

    payload["min_distance_angstrom"] = round(min_distance, 3)
    if min_pair:
        s_atom, l_atom = min_pair
        payload["min_distance_pair"] = {
            "sidechain_atom": s_atom.name,
            "ligand_atom": l_atom.name,
        }
    payload["max_vdw_overlap_angstrom"] = round(
        max((p["vdw_overlap_angstrom"] for p in pair_records), default=0.0), 3
    )
    payload["total_vdw_overlap_angstrom"] = round(total_overlap, 3)
    payload["overlapping_pair_count"] = overlapping_pairs
    payload["close_pairs"] = sorted(
        pair_records, key=lambda p: p["distance_angstrom"]
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote {args.out} min_dist={payload['min_distance_angstrom']} Å "
        f"max_overlap={payload['max_vdw_overlap_angstrom']} Å "
        f"close_pairs={len(pair_records)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
