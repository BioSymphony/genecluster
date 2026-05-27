#!/usr/bin/env python3
"""Audit BioSymphony skill files for public-export overfitting.

This check is intentionally narrow. It does not decide whether an example is
scientifically useful; it catches private/operator-specific tokens leaking into
public skill paths and warns when public docs drift toward one private campaign
or organism as the default.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIR_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "examples",
    "tests",
}

SKIP_RELATIVE_PREFIXES = {
    Path("references") / "internal",
}

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".tsv",
    ".txt",
    ".sh",
}

PRIVATE_GITHUB_REPO_TERMS = ("private", "workshop", "bio" + "-" + "symphony", "genecluster-private")

HARD_PRIVATE_PATTERNS = {
    "operator_home_path": re.compile(r"/Users/[A-Za-z0-9._-]+\b"),
    "private_github_default": re.compile(
        r"github\.com/[A-Za-z0-9_.-]*(?:" + "|".join(map(re.escape, PRIVATE_GITHUB_REPO_TERMS)) + r")\b",
        re.IGNORECASE,
    ),
    "personal_email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(gmail|icloud|me|hotmail|outlook|yahoo)\.com\b",
        re.IGNORECASE,
    ),
    "private_demo_slug": re.compile(r"\bdemo[_-]" r"1\b|\bgenecluster-demo-" r"1\b", re.IGNORECASE),
    "private_worker_stack": re.compile(r"\bsymphony-" r"claude\b"),
    "private_claude_plan": re.compile(r"(?:^|[`\s])~?/" r"\." r"claude\b"),
    "local_secret_store": re.compile(r"\.config/" r"codex" r"-" r"secrets"),
}

CAMPAIGN_SPECIFIC_WARNINGS = {}


@dataclass(frozen=True)
class Finding:
    severity: str
    rule_id: str
    path: str
    line: int
    text: str

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "rule_id": self.rule_id,
            "path": self.path,
            "line": self.line,
            "text": self.text,
        }


def is_skipped(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in SKIP_DIR_PARTS for part in rel.parts):
        return True
    return any(rel == prefix or rel.is_relative_to(prefix) for prefix in SKIP_RELATIVE_PREFIXES)


def iter_public_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if is_skipped(path, root):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


def scan_file(path: Path, root: Path, *, include_code_warnings: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    rel = str(path.relative_to(root))
    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule_id, pattern in HARD_PRIVATE_PATTERNS.items():
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        rule_id=rule_id,
                        path=rel,
                        line=line_no,
                        text=line.strip()[:220],
                    )
                )
        if include_code_warnings or path.suffix.lower() != ".py":
            for rule_id, pattern in CAMPAIGN_SPECIFIC_WARNINGS.items():
                if pattern.search(line):
                    findings.append(
                        Finding(
                            severity="warning",
                            rule_id=rule_id,
                            path=rel,
                            line=line_no,
                            text=line.strip()[:220],
                        )
                    )
    return findings


def audit_skill(skill_root: Path, *, include_code_warnings: bool = False) -> dict[str, object]:
    root = skill_root.resolve()
    findings: list[Finding] = []
    for path in iter_public_files(root):
        findings.extend(scan_file(path, root, include_code_warnings=include_code_warnings))
    errors = [finding.as_dict() for finding in findings if finding.severity == "error"]
    warnings = [finding.as_dict() for finding in findings if finding.severity == "warning"]
    return {
        "ok": not errors,
        "skill_root": str(root),
        "files_scanned": sum(1 for _ in iter_public_files(root)),
        "errors": errors,
        "warnings": warnings,
        "policy": {
            "include_code_warnings": include_code_warnings,
            "skipped_dirs": sorted(SKIP_DIR_PARTS),
            "skipped_prefixes": sorted(str(path) for path in SKIP_RELATIVE_PREFIXES),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit BioSymphony public skill export boundaries.")
    parser.add_argument("--skill-root", type=Path, default=Path("skills/biosymphony"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--include-code-warnings", action="store_true", help="Warn on campaign-specific compatibility aliases inside Python code.")
    parser.add_argument("--warnings-as-errors", action="store_true", help="Fail when campaign-specific warnings are present.")
    args = parser.parse_args(argv)

    result = audit_skill(args.skill_root, include_code_warnings=args.include_code_warnings)
    ok = bool(result["ok"]) and not (args.warnings_as_errors and result["warnings"])
    result["ok"] = ok
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("BioSymphony public skill audit:", "ok" if ok else "failed")
        print(f"Files scanned: {result['files_scanned']}")
        for error in result["errors"]:
            print(f"ERROR {error['path']}:{error['line']} {error['rule_id']}: {error['text']}")
        for warning in result["warnings"]:
            print(f"WARN {warning['path']}:{warning['line']} {warning['rule_id']}: {warning['text']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
