"""YAML loader with a clear, actionable error if PyYAML is missing.

PyYAML is a Tier A dependency for BioSymphony campaign scripts. It is in
the standard scientific Python toolchain. If the import fails, the loader
prints exactly what to install.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from typing import Any


def load_yaml(path: Path) -> Any:
    """Load a YAML file. Exits with an actionable message if PyYAML is missing."""
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        sys.stderr.write(
            "PyYAML is required for BioSymphony campaign scripts.\n"
            "JSON-compatible YAML can also be used without PyYAML.\n"
            "Install with one of:\n"
            "  python3 -m pip install --user pyyaml\n"
            "  conda install -n <env> pyyaml\n"
        )
        sys.exit(2)

    return yaml.safe_load(text)
