#!/usr/bin/env python3
"""Validate a BioSymphony figure dossier manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_ROOT_KEYS = [
    "schema_version",
    "campaign",
    "created_at",
    "inputs",
    "artifacts",
    "software",
    "linear",
    "validation",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": []}

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["manifest root must be an object"], "warnings": []}

    for key in REQUIRED_ROOT_KEYS:
        if key not in data:
            errors.append(f"missing root key: {key}")

    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    root = manifest_path.parent

    for list_key in ["inputs", "artifacts", "software", "validation"]:
        if list_key in data and not isinstance(data[list_key], list):
            errors.append(f"{list_key} must be a list")

    for item in data.get("artifacts", []) if isinstance(data.get("artifacts"), list) else []:
        if not isinstance(item, dict):
            errors.append("artifact entries must be objects")
            continue
        rel = item.get("path")
        if not rel:
            errors.append("artifact missing path")
            continue
        artifact_path = (root / rel).resolve()
        if not artifact_path.exists():
            errors.append(f"artifact path missing: {rel}")
            continue
        expected = item.get("sha256")
        if expected:
            actual = sha256_file(artifact_path)
            if actual.lower() != str(expected).lower():
                errors.append(f"artifact sha256 mismatch: {rel}")
        else:
            warnings.append(f"artifact lacks sha256: {rel}")

    for item in data.get("inputs", []) if isinstance(data.get("inputs"), list) else []:
        if not isinstance(item, dict):
            errors.append("input entries must be objects")
            continue
        rel = item.get("path")
        if rel:
            input_path = (root / rel).resolve()
            if not input_path.exists():
                warnings.append(f"input path not present locally: {rel}")
            elif item.get("sha256"):
                actual = sha256_file(input_path)
                if actual.lower() != str(item["sha256"]).lower():
                    errors.append(f"input sha256 mismatch: {rel}")

    if not data.get("validation"):
        errors.append("validation list must not be empty")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a BioSymphony figure manifest.")
    parser.add_argument("manifest", type=Path, help="Path to figure_manifest.json.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    result = validate_manifest(args.manifest)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result["ok"]:
            print("BioSymphony figure manifest: ok")
        else:
            print("BioSymphony figure manifest: failed")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
