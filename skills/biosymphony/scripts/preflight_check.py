#!/usr/bin/env python3
"""Validate a BioSymphony Linear issue contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = [
    "Summary",
    "Inputs",
    "Acceptance Criteria",
    "Validation Commands",
    "Touched Areas",
    "Risk Notes",
    "Orchestration Guardrails",
    "Resume / Recovery Contract",
    "Complexity",
]


def section_present(text: str, section: str) -> bool:
    pattern = r"(?m)^##\s+" + re.escape(section) + r"\s*$"
    return re.search(pattern, text) is not None


def section_body(text: str, section: str) -> str:
    match = re.search(r"(?m)^##\s+" + re.escape(section) + r"\s*$", text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"(?m)^##\s+", text[start:])
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def validate(text: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not text.strip():
        errors.append("issue body is empty")
        return {
            "ok": False,
            "errors": errors,
            "warnings": warnings,
        }

    if re.search(r"<issue_body>\s*</issue_body>", text, flags=re.IGNORECASE | re.DOTALL):
        errors.append("rendered prompt contains empty <issue_body> block")
    if re.search(r"<(One or two sentence|input id|path|exact command|issue_body)[^>]*>", text, flags=re.IGNORECASE):
        errors.append("issue body still contains unresolved template placeholder text")

    for section in REQUIRED_SECTIONS:
        if not section_present(text, section):
            errors.append(f"missing section: ## {section}")

    acceptance = section_body(text, "Acceptance Criteria")
    if acceptance and not re.search(r"(?m)^-\s+\[[ xX]\]\s+\S", acceptance):
        errors.append("Acceptance Criteria must contain checklist items")

    inputs = section_body(text, "Inputs")
    if inputs and not re.search(r"(?m)^-\s+`[^`]+`", inputs):
        errors.append("Inputs must list backticked input identifiers")

    validation = section_body(text, "Validation Commands")
    if validation and "```bash" not in validation:
        errors.append("Validation Commands must contain a bash code block")
    if validation and re.search(r"<[^>]+>", validation):
        errors.append("Validation Commands still contain placeholder text")

    touched = section_body(text, "Touched Areas")
    if touched and not re.search(r"(?m)^-\s+`[^`]+`", touched):
        errors.append("Touched Areas must list backticked paths")

    complexity = section_body(text, "Complexity")
    if complexity and not re.search(r"(?m)^tier:\s*(small|medium|large)\s*$", complexity):
        errors.append("Complexity must be tier: small, tier: medium, or tier: large")

    if "<!-- symphony:schema" not in text:
        errors.append("missing <!-- symphony:schema --> block")
    else:
        schema_block = text.split("<!-- symphony:schema", 1)[1].split("-->", 1)[0]
        for required in ["schema_version:", "touched_areas:", "complexity:"]:
            if required not in schema_block:
                errors.append(f"symphony schema missing {required}")

    if "Blocked by:" in text and not section_present(text, "Dependencies"):
        warnings.append("Blocked by appears outside a ## Dependencies section")

    if "private" not in text.lower() and "secret" not in text.lower():
        warnings.append("Risk Notes should explicitly mention private data or secrets")

    guardrails = section_body(text, "Orchestration Guardrails")
    if guardrails:
        required_terms = ["prompt", "payload", "snapshot"]
        for term in required_terms:
            if term not in guardrails.lower():
                warnings.append(f"Orchestration Guardrails should mention {term} checks")

    recovery = section_body(text, "Resume / Recovery Contract")
    if recovery:
        for term in ["checkpoint", "resume", "degraded"]:
            if term not in recovery.lower():
                warnings.append(f"Resume / Recovery Contract should mention {term}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a BioSymphony Linear issue contract.")
    parser.add_argument("issue", type=Path, help="Markdown issue body file.")
    parser.add_argument("--json", action="store_true", help="Emit JSON.")
    args = parser.parse_args()

    try:
        text = args.issue.read_text(encoding="utf-8")
    except OSError as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": []}
    else:
        result = validate(text)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        if result["ok"]:
            print("BioSymphony contract preflight: ok")
        else:
            print("BioSymphony contract preflight: failed")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
