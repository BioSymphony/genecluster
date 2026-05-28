#!/usr/bin/env python3
"""Wave 4 metric, heavy-atom h-bond diff between WT and variant structures.

Detects candidate hydrogen bonds using a heavy-atom geometric criterion:
N/O donor → N/O acceptor distance <= --donor-acceptor-cutoff (default 3.5 Å).

This is a simplified detection that does not require explicit hydrogens
(most PDBs lack them). It is intended for comparative diff (gained / lost
hbonds between WT and variant), not absolute hbond counting.

Usage:
    python3 hbond_diff.py \\
        --wt 3UG2.pdb \\
        --variant 5EDQ.pdb \\
        --focus-residues A:790,A:858 \\
        --out metrics/T790M/hbond_diff.json
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


def candidate_hbond_atoms(atoms: list[Atom]) -> list[Atom]:
    """Return non-hydrogen N and O atoms that could be donors or acceptors."""
    return [a for a in atoms if a.element in {"N", "O"}]


def find_hbonds(atoms: list[Atom], cutoff: float) -> set[tuple[str, str, str, str]]:
    """Return heavy-atom-only candidate hbonds.

    Each tuple is (res_id_a, atom_a, res_id_b, atom_b) sorted so the lower
    res_id is first to avoid double counting. Only counts pairs in different
    residues.
    """
    candidates = candidate_hbond_atoms(atoms)
    pairs: set[tuple[str, str, str, str]] = set()
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            if a.res_id == b.res_id:
                continue
            d = a.distance_to(b)
            if d <= cutoff:
                key = tuple(
                    sorted(
                        [(a.res_id, a.name), (b.res_id, b.name)],
                        key=lambda p: p[0],
                    )
                )
                pairs.add((key[0][0], key[0][1], key[1][0], key[1][1]))
    return pairs


def filter_to_focus(
    pairs: set[tuple[str, str, str, str]],
    focus_residues: set[str],
) -> set[tuple[str, str, str, str]]:
    if not focus_residues:
        return pairs
    return {p for p in pairs if p[0] in focus_residues or p[2] in focus_residues}


def parse_focus_list(spec: str) -> set[str]:
    """Parse 'A:790,A:858' into {'A/790', 'A/858'} matching res_id format."""
    out: set[str] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        sep = ":" if ":" in token else "/"
        chain, resseq = token.split(sep, 1)
        out.add(f"{chain}/{int(resseq)}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Heavy-atom h-bond diff between WT and variant structures."
    )
    parser.add_argument("--wt", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument(
        "--donor-acceptor-cutoff",
        type=float,
        default=3.5,
        help="Donor-acceptor heavy-atom distance cutoff (Å).",
    )
    parser.add_argument(
        "--focus-residues",
        default="",
        help="Comma-separated residues (chain:resseq) to restrict to.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.wt.is_file():
        print(f"WT structure not found: {args.wt}", file=sys.stderr)
        return 1
    if not args.variant.is_file():
        print(f"variant structure not found: {args.variant}", file=sys.stderr)
        return 1

    wt_atoms = parse_pdb(args.wt)
    var_atoms = parse_pdb(args.variant)

    focus = parse_focus_list(args.focus_residues) if args.focus_residues else set()

    wt_hbonds = filter_to_focus(find_hbonds(wt_atoms, args.donor_acceptor_cutoff), focus)
    var_hbonds = filter_to_focus(find_hbonds(var_atoms, args.donor_acceptor_cutoff), focus)

    lost = sorted(wt_hbonds - var_hbonds)
    gained = sorted(var_hbonds - wt_hbonds)
    retained_count = len(wt_hbonds & var_hbonds)

    def fmt(t: tuple[str, str, str, str]) -> dict:
        return {
            "res_a": t[0],
            "atom_a": t[1],
            "res_b": t[2],
            "atom_b": t[3],
        }

    payload = {
        "schema_version": 1,
        "metric": "hbond_diff",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wt_path": str(args.wt),
        "variant_path": str(args.variant),
        "donor_acceptor_cutoff_angstrom": args.donor_acceptor_cutoff,
        "focus_residues": sorted(focus),
        "wt_hbond_count": len(wt_hbonds),
        "variant_hbond_count": len(var_hbonds),
        "lost_count": len(lost),
        "gained_count": len(gained),
        "retained_count": retained_count,
        "lost": [fmt(t) for t in lost],
        "gained": [fmt(t) for t in gained],
        "diagnostics": {
            "wt_atom_count": len(wt_atoms),
            "variant_atom_count": len(var_atoms),
            "method": (
                "Heavy-atom geometric criterion only (no hydrogens). "
                "Use as a comparative metric, not absolute counts."
            ),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(
        f"wrote {args.out} wt={len(wt_hbonds)} variant={len(var_hbonds)} "
        f"lost={len(lost)} gained={len(gained)} retained={retained_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
