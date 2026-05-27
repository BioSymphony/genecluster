#!/usr/bin/env python3
"""Wave 4 metric, pocket geometry comparison between WT and variant structures.

Computes simple geometric descriptors of a pocket defined by a set of residues:

    - bounding-box volume of pocket Cα atoms
    - radius of gyration of pocket Cα atoms
    - mean pairwise distance of pocket Cα atoms
    - per-residue Cα coordinates (so downstream tools can render or align)

Reports both WT and variant values plus their delta. The deltas are useful
as inputs to the Wave 5 mechanism classifier (pocket_shape_delta).

This avoids the dependency on fpocket or any external pocket-detection
tool. For higher-fidelity pocket volumes, install fpocket and run a
secondary metric script.

Usage:
    python3 pocket_geometry.py \\
        --wt 3UG2.pdb \\
        --variant 5EDQ.pdb \\
        --pocket-residues A:719,A:721,A:722,A:743,A:745,A:790,A:854,A:855,A:856 \\
        --out metrics/T790M/pocket_geometry.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.pdb_parser import Atom, parse_pdb  # noqa: E402


def parse_residue_list(spec: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        sep = ":" if ":" in token else "/"
        chain, resseq = token.split(sep, 1)
        out.append((chain, int(resseq)))
    return out


def collect_cas(atoms: list[Atom], residues: list[tuple[str, int]]) -> list[Atom]:
    out: list[Atom] = []
    missing: list[str] = []
    for chain, resseq in residues:
        ca = next(
            (
                a
                for a in atoms
                if a.chain == chain and a.resseq == resseq and a.name == "CA"
            ),
            None,
        )
        if ca is None:
            missing.append(f"{chain}:{resseq}")
        else:
            out.append(ca)
    if missing:
        # Print a warning but still return what we found
        print(
            f"WARN: missing CA atoms for residues: {missing}", file=sys.stderr
        )
    return out


def bounding_box_volume(atoms: list[Atom]) -> float:
    if not atoms:
        return 0.0
    xs = [a.x for a in atoms]
    ys = [a.y for a in atoms]
    zs = [a.z for a in atoms]
    return (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))


def radius_of_gyration(atoms: list[Atom]) -> float:
    if not atoms:
        return 0.0
    cx = sum(a.x for a in atoms) / len(atoms)
    cy = sum(a.y for a in atoms) / len(atoms)
    cz = sum(a.z for a in atoms) / len(atoms)
    sq = sum((a.x - cx) ** 2 + (a.y - cy) ** 2 + (a.z - cz) ** 2 for a in atoms)
    return math.sqrt(sq / len(atoms))


def mean_pairwise_distance(atoms: list[Atom]) -> float:
    if len(atoms) < 2:
        return 0.0
    dists = [
        a.distance_to(b)
        for a, b in itertools.combinations(atoms, 2)
    ]
    return statistics.fmean(dists)


def describe_pocket(atoms: list[Atom], residues: list[tuple[str, int]]) -> dict:
    cas = collect_cas(atoms, residues)
    return {
        "residue_count_requested": len(residues),
        "residue_count_found": len(cas),
        "bounding_box_volume_angstrom_cubed": round(bounding_box_volume(cas), 2),
        "radius_of_gyration_angstrom": round(radius_of_gyration(cas), 3),
        "mean_pairwise_distance_angstrom": round(mean_pairwise_distance(cas), 3),
        "ca_coordinates": [
            {
                "res_id": a.res_id,
                "x": round(a.x, 3),
                "y": round(a.y, 3),
                "z": round(a.z, 3),
            }
            for a in cas
        ],
    }


def relative_delta(a: float, b: float) -> float:
    if a == 0 and b == 0:
        return 0.0
    base = max(abs(a), abs(b))
    return abs(a - b) / base if base else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pocket geometry comparison between WT and variant structures."
    )
    parser.add_argument("--wt", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument(
        "--pocket-residues",
        required=True,
        help="Comma-separated residues defining the pocket (chain:resseq).",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.wt.is_file():
        print(f"WT structure not found: {args.wt}", file=sys.stderr)
        return 1
    if not args.variant.is_file():
        print(f"variant structure not found: {args.variant}", file=sys.stderr)
        return 1

    residues = parse_residue_list(args.pocket_residues)

    wt_atoms = parse_pdb(args.wt)
    var_atoms = parse_pdb(args.variant)

    wt = describe_pocket(wt_atoms, residues)
    variant = describe_pocket(var_atoms, residues)

    payload = {
        "schema_version": 1,
        "metric": "pocket_geometry",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wt_path": str(args.wt),
        "variant_path": str(args.variant),
        "pocket_residues": args.pocket_residues,
        "wt": wt,
        "variant": variant,
        "delta": {
            "bounding_box_volume": round(
                variant["bounding_box_volume_angstrom_cubed"]
                - wt["bounding_box_volume_angstrom_cubed"],
                2,
            ),
            "radius_of_gyration": round(
                variant["radius_of_gyration_angstrom"]
                - wt["radius_of_gyration_angstrom"],
                3,
            ),
            "mean_pairwise_distance": round(
                variant["mean_pairwise_distance_angstrom"]
                - wt["mean_pairwise_distance_angstrom"],
                3,
            ),
            "pocket_shape_delta": round(
                relative_delta(
                    wt["mean_pairwise_distance_angstrom"],
                    variant["mean_pairwise_distance_angstrom"],
                ),
                4,
            ),
        },
        "diagnostics": {
            "method": (
                "Cα-only geometric descriptors. For higher-fidelity pocket "
                "volume, install fpocket and run a secondary metric."
            ),
            "wt_residues_found": wt["residue_count_found"],
            "variant_residues_found": variant["residue_count_found"],
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote {args.out} "
        f"Δrg={payload['delta']['radius_of_gyration']} "
        f"Δmean_d={payload['delta']['mean_pairwise_distance']} "
        f"shape_Δ={payload['delta']['pocket_shape_delta']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
