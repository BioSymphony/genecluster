"""Minimal stdlib PDB parser for BioSymphony Wave 4 metrics.

Handles the columns the campaign needs (ATOM/HETATM records). Does not
attempt full PDB compliance. For mmCIF, callers should convert to PDB
first via PyMOL `save` or BioPython.

This parser is intentionally small and dependency-free so the metric
scripts run on any Python 3.x without bringing in BioPython.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Atom:
    """A single atom record from a PDB ATOM or HETATM line."""

    record: str            # "ATOM" or "HETATM"
    serial: int
    name: str              # atom name, e.g., "CA"
    alt_loc: str
    resname: str           # residue name, e.g., "LYS"
    chain: str
    resseq: int
    icode: str
    x: float
    y: float
    z: float
    occupancy: float
    bfactor: float
    element: str

    def distance_to(self, other: "Atom") -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    @property
    def is_protein(self) -> bool:
        return self.record == "ATOM"

    @property
    def is_hetero(self) -> bool:
        return self.record == "HETATM"

    @property
    def res_id(self) -> str:
        """Stable residue identifier: chain + resseq + icode."""
        return f"{self.chain}/{self.resseq}{self.icode.strip()}"


def parse_pdb(path: Path) -> list[Atom]:
    """Parse a PDB file into a list of Atom records.

    Skips MODEL/ENDMDL boundaries except for keeping only the first model.
    Skips non-ATOM/HETATM records. Returns atoms in file order.
    """
    atoms: list[Atom] = []
    in_model = True  # default true so files without MODEL records work

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            if raw.startswith("MODEL"):
                # If we have any atoms already, we are now past model 1
                if atoms:
                    in_model = False
                continue
            if raw.startswith("ENDMDL"):
                in_model = False
                continue
            if not in_model:
                continue
            if raw.startswith("ATOM  ") or raw.startswith("HETATM"):
                try:
                    atoms.append(_parse_atom_line(raw))
                except ValueError:
                    # Malformed line: skip rather than crash the whole campaign
                    continue
    return atoms


def _parse_atom_line(line: str) -> Atom:
    # PDB column spec (1-indexed):
    # 1-6   Record name
    # 7-11  Atom serial number
    # 13-16 Atom name
    # 17    Alt loc
    # 18-20 Residue name
    # 22    Chain
    # 23-26 Residue sequence number
    # 27    iCode
    # 31-38 X
    # 39-46 Y
    # 47-54 Z
    # 55-60 Occupancy
    # 61-66 B factor
    # 77-78 Element
    return Atom(
        record=line[0:6].strip(),
        serial=int(line[6:11].strip() or 0),
        name=line[12:16].strip(),
        alt_loc=line[16:17].strip(),
        resname=line[17:20].strip(),
        chain=line[21:22].strip() or "_",
        resseq=int(line[22:26].strip() or 0),
        icode=line[26:27].strip(),
        x=float(line[30:38].strip()),
        y=float(line[38:46].strip()),
        z=float(line[46:54].strip()),
        occupancy=float(line[54:60].strip() or "0"),
        bfactor=float(line[60:66].strip() or "0"),
        element=(line[76:78].strip() if len(line) >= 78 else line[12:14].strip())
        .lstrip("0123456789"),
    )


def filter_chain(atoms: Iterable[Atom], chain: str) -> list[Atom]:
    return [a for a in atoms if a.chain == chain]


def protein_atoms(atoms: Iterable[Atom]) -> list[Atom]:
    return [a for a in atoms if a.record == "ATOM"]


def hetero_atoms(atoms: Iterable[Atom]) -> list[Atom]:
    return [a for a in atoms if a.record == "HETATM" and a.resname not in {"HOH", "WAT"}]


def by_residue(atoms: Iterable[Atom]) -> dict[str, list[Atom]]:
    """Group atoms by chain/resseq/icode."""
    out: dict[str, list[Atom]] = {}
    for a in atoms:
        out.setdefault(a.res_id, []).append(a)
    return out


def residues_within(
    atoms: Iterable[Atom],
    target_atoms: list[Atom],
    cutoff: float,
) -> set[str]:
    """Return residue IDs that have any heavy atom within cutoff of any target atom.

    Skips hydrogens (element == 'H') in both sets.
    """
    targets = [a for a in target_atoms if a.element != "H"]
    hits: set[str] = set()
    for a in atoms:
        if a.element == "H":
            continue
        for t in targets:
            if a.distance_to(t) <= cutoff:
                hits.add(a.res_id)
                break
    return hits


def residue_pairs_within(
    chain_a: list[Atom],
    chain_b: list[Atom],
    cutoff: float,
) -> set[tuple[str, str]]:
    """Return the set of (res_id_a, res_id_b) pairs with at least one heavy-atom contact within cutoff."""
    pairs: set[tuple[str, str]] = set()
    a_heavy = [a for a in chain_a if a.element != "H"]
    b_heavy = [a for a in chain_b if a.element != "H"]
    for a in a_heavy:
        for b in b_heavy:
            if a.distance_to(b) <= cutoff:
                pairs.add((a.res_id, b.res_id))
    return pairs
