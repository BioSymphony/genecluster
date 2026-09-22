#!/usr/bin/env python3
"""Compatibility entry point for a separately supplied annotation-direct engine."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


DEMO3_ENGINE = Path(__file__).resolve().parents[1] / "demo3" / "run.py"


def main() -> None:
    if not DEMO3_ENGINE.is_file():
        message = (
            "The annotation-direct engine (pipeline/demo3/run.py) is not bundled. "
            "Use the tool-specific entry points in docs/tooling/tool-chaining.md."
        )
        if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
            print(message)
            return
        print(message, file=sys.stderr)
        raise SystemExit(2)
    runpy.run_path(str(DEMO3_ENGINE), run_name="__main__")


if __name__ == "__main__":
    main()
