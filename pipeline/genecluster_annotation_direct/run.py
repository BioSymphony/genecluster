#!/usr/bin/env python3
"""Reusable GeneCluster annotation-direct entrypoint.

This wrapper promotes the delivered campaign engine without copying it. Existing
demo-specific launch scripts can keep using ``pipeline/genecluster_annotation_direct/run.py`` while new
Atlas campaigns call this stable entrypoint and receive the same workbook,
neighborhood, Pfam, SwissProt, controls-QC, summary, and interpretation outputs.
"""

from __future__ import annotations

import runpy
from pathlib import Path


DEMO3_ENGINE = Path(__file__).resolve().parents[1] / "demo3" / "run.py"


def main() -> None:
    runpy.run_path(str(DEMO3_ENGINE), run_name="__main__")


if __name__ == "__main__":
    main()
