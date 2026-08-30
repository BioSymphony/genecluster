#!/usr/bin/env python3
"""Check that relative Markdown links resolve inside the public tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_PREFIXES = ("#", "http://", "https://", "mailto:", "data:")
SKIP_DIRS = {".git", ".runtime", ".demo-output", "__pycache__", ".pytest_cache"}


def link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split(maxsplit=1)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    root = args.repo_root.resolve()
    missing: list[tuple[Path, str]] = []

    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for raw in LINK_RE.findall(text):
            target = link_target(raw)
            if not target or target.startswith(SKIP_PREFIXES):
                continue
            target = target.split("#", 1)[0]
            if not target or any(marker in target for marker in ("<", ">", "{", "}")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                missing.append((path, raw))
                continue
            if not resolved.exists():
                missing.append((path, raw))

    for path, raw in missing:
        print(f"{path.relative_to(root)}: missing relative link: {raw}")
    print(f"markdown-link-check: {'FAIL' if missing else 'OK'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
