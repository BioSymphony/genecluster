#!/usr/bin/env python3
"""Wave 4 metric, residue-residue contact diff between WT and variant structures.

Computes the set of residue contacts (heavy-atom heavy-atom within cutoff)
in each structure, then reports gained / lost / retained contacts.

If --focus-residue is provided, restricts contacts to those involving the
focus residue. Useful for "what contacts does the mutated residue make in
WT vs variant?" or "what TKI contacts are lost?"

If --focus-ligand is provided, restricts contacts to those involving any
HETATM residue with the given residue name.

Usage:
    python3 contact_diff.py \\
        --wt 3UG2.pdb \\
        --variant 5EDQ.pdb \\
        --focus-ligand IRE \\
        --cutoff 4.0 \\
        --out metrics/T790M/contact_diff.json
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

from lib.pdb_parser import (  # noqa: E402
    Atom,
    by_residue,
    parse_pdb,
    protein_atoms,
    residue_pairs_within,
)


def parse_focus_residue(spec: str) -> tuple[str, int]:
    """Parse 'A:790' or 'A/790' into (chain, resseq)."""
    sep = ":" if ":" in spec else "/"
    chain, resseq = spec.split(sep, 1)
    return chain, int(resseq)


def contacts_to_focus_residue(
    atoms: list[Atom],
    chain: str,
    resseq: int,
    cutoff: float,
) -> set[str]:
    """Return residue IDs (excluding the focus residue itself) with any heavy atom within cutoff of the focus residue heavy atoms."""
    target = [a for a in atoms if a.chain == chain and a.resseq == resseq]
    if not target:
        return set()
    target_id = target[0].res_id
    out: set[str] = set()
    target_heavy = [a for a in target if a.element != "H"]
    for a in atoms:
        if a.element == "H":
            continue
        if a.res_id == target_id:
            continue
        for t in target_heavy:
            if a.distance_to(t) <= cutoff:
                out.add(a.res_id)
                break
    return out


def contacts_to_ligand(
    atoms: list[Atom],
    ligand_resname: str,
    cutoff: float,
) -> tuple[set[str], list[str]]:
    """Return (set of protein residue IDs in contact with the ligand, list of ligand residue IDs found)."""
    ligand_atoms = [
        a
        for a in atoms
        if a.record == "HETATM" and a.resname == ligand_resname.upper() and a.element != "H"
    ]
    if not ligand_atoms:
        return set(), []
    protein = [a for a in atoms if a.record == "ATOM" and a.element != "H"]
    out: set[str] = set()
    for p in protein:
        for lig in ligand_atoms:
            if p.distance_to(lig) <= cutoff:
                out.add(p.res_id)
                break
    ligand_ids = sorted({a.res_id for a in ligand_atoms})
    return out, ligand_ids


def diff_sets(a: set[str], b: set[str]) -> dict:
    """Return diff buckets for two sets of residue IDs."""
    a_only = sorted(a - b)
    b_only = sorted(b - a)
    both = sorted(a & b)
    return {
        "lost": a_only,
        "lost_count": len(a_only),
        "gained": b_only,
        "gained_count": len(b_only),
        "retained": both,
        "retained_count": len(both),
    }


def diff_pairs(a: set[tuple[str, str]], b: set[tuple[str, str]]) -> dict:
    a_only = sorted(a - b)
    b_only = sorted(b - a)
    both = sorted(a & b)
    return {
        "lost": [list(p) for p in a_only],
        "lost_count": len(a_only),
        "gained": [list(p) for p in b_only],
        "gained_count": len(b_only),
        "retained_count": len(both),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Residue-contact diff between two structures."
    )
    parser.add_argument("--wt", type=Path, required=True, help="WT structure (PDB).")
    parser.add_argument("--variant", type=Path, required=True, help="Variant structure (PDB).")
    parser.add_argument(
        "--focus-residue",
        help="Focus on contacts involving this residue (chain:resseq, e.g., A:790).",
    )
    parser.add_argument(
        "--focus-ligand",
        help="Focus on contacts involving this HETATM residue name (e.g., IRE for iressa/gefitinib).",
    )
    parser.add_argument("--cutoff", type=float, default=5.0, help="Heavy-atom contact cutoff in Å.")
    parser.add_argument("--out", type=Path, required=True, help="Output JSON path.")
    args = parser.parse_args()

    if not args.wt.is_file():
        print(f"WT structure not found: {args.wt}", file=sys.stderr)
        return 1
    if not args.variant.is_file():
        print(f"variant structure not found: {args.variant}", file=sys.stderr)
        return 1

    wt_atoms = parse_pdb(args.wt)
    var_atoms = parse_pdb(args.variant)

    diag = {
        "wt_atom_count": len(wt_atoms),
        "variant_atom_count": len(var_atoms),
    }

    payload: dict = {
        "schema_version": 1,
        "metric": "contact_diff",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wt_path": str(args.wt),
        "variant_path": str(args.variant),
        "cutoff_angstrom": args.cutoff,
        "diagnostics": diag,
    }

    if args.focus_residue:
        chain, resseq = parse_focus_residue(args.focus_residue)
        wt_contacts = contacts_to_focus_residue(wt_atoms, chain, resseq, args.cutoff)
        var_contacts = contacts_to_focus_residue(var_atoms, chain, resseq, args.cutoff)
        payload["focus"] = {"kind": "residue", "spec": args.focus_residue}
        payload["wt_contacts"] = sorted(wt_contacts)
        payload["variant_contacts"] = sorted(var_contacts)
        payload["diff"] = diff_sets(wt_contacts, var_contacts)
        diag["focus_residue_found_in_wt"] = bool(wt_contacts) or any(
            a.chain == chain and a.resseq == resseq for a in wt_atoms
        )
        diag["focus_residue_found_in_variant"] = bool(var_contacts) or any(
            a.chain == chain and a.resseq == resseq for a in var_atoms
        )
    elif args.focus_ligand:
        wt_contacts, wt_lig_ids = contacts_to_ligand(wt_atoms, args.focus_ligand, args.cutoff)
        var_contacts, var_lig_ids = contacts_to_ligand(var_atoms, args.focus_ligand, args.cutoff)
        payload["focus"] = {"kind": "ligand", "resname": args.focus_ligand.upper()}
        payload["wt_ligand_residues"] = wt_lig_ids
        payload["variant_ligand_residues"] = var_lig_ids
        payload["wt_contacts"] = sorted(wt_contacts)
        payload["variant_contacts"] = sorted(var_contacts)
        payload["diff"] = diff_sets(wt_contacts, var_contacts)
        diag["ligand_found_in_wt"] = bool(wt_lig_ids)
        diag["ligand_found_in_variant"] = bool(var_lig_ids)
    else:
        # Whole-structure protein-protein residue-pair diff (single-chain mode).
        wt_protein = protein_atoms(wt_atoms)
        var_protein = protein_atoms(var_atoms)
        wt_pairs = residue_pairs_within(wt_protein, wt_protein, args.cutoff)
        # remove self-pairs and (i,j)/(j,i) duplicates
        wt_pairs_unique = {tuple(sorted(p)) for p in wt_pairs if p[0] != p[1]}
        var_pairs = residue_pairs_within(var_protein, var_protein, args.cutoff)
        var_pairs_unique = {tuple(sorted(p)) for p in var_pairs if p[0] != p[1]}
        payload["focus"] = {"kind": "all_protein_pairs"}
        payload["diff"] = diff_pairs(wt_pairs_unique, var_pairs_unique)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")
    diff = payload["diff"]
    print(
        f"focus={payload['focus']['kind']} "
        f"lost={diff.get('lost_count')} gained={diff.get('gained_count')} retained={diff.get('retained_count')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
