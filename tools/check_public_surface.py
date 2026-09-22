#!/usr/bin/env python3
"""Scan a checkout for files and content that cannot cross the public boundary."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_TREE_BYTES = 12 * 1024 * 1024
SMALL_DATA_BYTES = 4096
FORBIDDEN_DIR_NAMES = frozenset(
    {
        ".claude",
        ".codex",
        ".playwright-mcp",
        ".runtime",
        "artifacts",
        "build",
        "dist",
        "internal",
        "logs",
        "node_modules",
        "outputs",
        "private",
        "runtime",
        "workshop",
    }
)
RAW_DATA_SUFFIXES = frozenset(
    ".bam .cram .faa .faa.gz .fa .fa.gz .fasta .fasta.gz .fastq .fastq.gz .fna .fna.gz "
    ".fq .fq.gz .ffn .ffn.gz .frn .frn.gz .gb .gb.gz .gbk .gbk.gz .gff .gff.gz .gff3 .gff3.gz "
    ".gtf .gtf.gz .pdb .sra .vcf .vcf.gz".split()
)
BLOCKED_ARTIFACT_SUFFIXES = frozenset(
    ".db .dmnd .mmi .onnx .p12 .pfx .pickle .pkl .pth .pt .safetensors .sqlite .sqlite3 "
    ".tar .tar.gz .tgz .zip .7z .rar .weights .ckpt".split()
)
ALLOWED_SMALL_DATA_PATHS = frozenset(
    {
        "skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/query-with-controls.faa",
        "skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/fixture-proteome.faa",
        "skills/biosymphony/examples/genecluster-coptis-bia-public-v0/fixtures/fixture-genomic.gff",
    }
)
ENV_SUFFIXES = (".env", ".env.local", ".env.production", ".env.development")

# Build sensitive literals from pieces so code and tests do not contain complete credentials or private paths.
HOME_PATH = re.compile(
    rb"(?<![A-Za-z0-9._-])(?:"
    + rb"/" + rb"Users/" + rb"[A-Za-z0-9._-]+(?:[/\\][^\s\"'<>]+)*"
    + rb"|/" + rb"home/" + rb"[A-Za-z0-9._-]+(?:[/\\][^\s\"'<>]+)*"
    + rb"|[A-Za-z]:[/\\]+Users[/\\]+[A-Za-z0-9._-]+(?:[/\\][^\s\"'<>]+)*"
    + rb"|\\\\Users[/\\]+[A-Za-z0-9._-]+(?:[/\\][^\s\"'<>]+)*"
    + rb")"
)
SECRET_PATTERNS = (
    ("github_token", re.compile(rb"g" + rb"h[pousr]_" + rb"[A-Za-z0-9_]{20,}")),
    ("github_fine_grained_token", re.compile(rb"github" + rb"_pat_" + rb"[A-Za-z0-9_]{20,}")),
    ("huggingface_token", re.compile(rb"h" + rb"f_" + rb"[A-Za-z0-9]{20,}")),
    ("runpod_token", re.compile(rb"r" + rb"p_" + rb"[A-Za-z0-9_-]{20,}")),
    ("openai_token", re.compile(rb"s" + rb"k-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}")),
    ("google_api_key", re.compile(rb"A" + rb"Iza[0-9A-Za-z_-]{30,}")),
    ("aws_access_key", re.compile(rb"A" + rb"KIA[0-9A-Z]{16}")),
    ("aws_session_key", re.compile(rb"A" + rb"SIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(rb"x" + rb"ox[baprs]-[A-Za-z0-9-]{16,}")),
    ("basic_auth", re.compile(rb"Basic[ \t]+(?![$<{])[A-Za-z0-9+/]{24,}={0,2}")),
    (
        "private_key_header",
        re.compile(b"-" * 5 + rb"BEGIN (?:RSA |EC |OPENSSH |)?PRIVATE " + rb"KEY" + b"-" * 5),
    ),
    ("bearer_token", re.compile(rb"Bearer[ \t]+(?![$<{])[A-Za-z0-9._~+/=-]{20,}")),
    (
        "signed_url_credential",
        re.compile(
            rb"(?:X-Amz-" + rb"(?:Signature|Credential)|AWS" + rb"AccessKeyId|access" + rb"_token|refresh"
            + rb"_token|signature|sig|token)=[^&\s<>{}\"']{16,}",
            re.IGNORECASE,
        ),
    ),
)
CONTENT_PATTERNS = (
    ("home_path", HOME_PATH),
    *SECRET_PATTERNS,
    (
        "internal_style_reference",
        re.compile(
            rb"(?:references" + rb"[/\\]internal|writing" + rb"[-_]style\.md|style" + rb"[-_]samples?)",
            re.IGNORECASE,
        ),
    ),
    ("internal_only_marker", re.compile(rb"internal" + rb"[- ]only", re.IGNORECASE)),
    (
        "writing_skill_reference",
        re.compile(rb"write" + rb"[-_]better[/\\](?:SKILL|CORE)\.md", re.IGNORECASE),
    ),
    (
        "private_repository_reference",
        re.compile(rb"github\.com/[^\s/]+/(?:private|workshop|genecluster-private)\b", re.IGNORECASE),
    ),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _add(findings: set[Finding], root: Path, path: Path, rule: str, line: int = 1) -> None:
    findings.add(Finding(_relative(root, path), line, rule))


def _matches(name: str, suffixes: frozenset[str]) -> bool:
    return any(name.endswith(suffix) for suffix in suffixes)


def _scan_file(root: Path, path: Path, findings: set[Finding], max_file_bytes: int) -> None:
    relative = _relative(root, path)
    name = path.name.lower()
    try:
        size = path.stat().st_size
    except OSError:
        _add(findings, root, path, "unreadable_file")
        return
    if _matches(name, RAW_DATA_SUFFIXES) and (
        relative not in ALLOWED_SMALL_DATA_PATHS or size > SMALL_DATA_BYTES
    ):
        _add(findings, root, path, "raw_data_artifact")
    if _matches(name, BLOCKED_ARTIFACT_SUFFIXES):
        _add(findings, root, path, "blocked_artifact")
    if size > max_file_bytes:
        _add(findings, root, path, "large_artifact")
        return
    try:
        data = path.read_bytes()
    except OSError:
        _add(findings, root, path, "unreadable_file")
        return
    for rule, pattern in CONTENT_PATTERNS:
        for match in pattern.finditer(data):
            line = data.count(b"\n", 0, match.start()) + 1
            _add(findings, root, path, rule, line)


def scan_tree(
    root: Path | str = ".",
    *,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_tree_bytes: int = DEFAULT_MAX_TREE_BYTES,
) -> list[Finding]:
    """Return redacted findings for the complete working tree below *root*."""
    root = Path(root).resolve()
    if not root.is_dir():
        return [Finding(".", 1, "invalid_root")]
    findings: set[Finding] = set()
    total_bytes = 0

    def onerror(error: OSError) -> None:
        error_path = Path(os.fsdecode(error.filename)) if error.filename else root
        if not error_path.is_absolute():
            error_path = root / error_path
        try:
            error_path.relative_to(root)
        except ValueError:
            error_path = root
        _add(findings, root, error_path, "unreadable_directory")

    for current, dirnames, filenames in os.walk(
        root, onerror=onerror, followlinks=False
    ):
        current_path = Path(current)
        dirnames.sort()
        filenames.sort()
        for name in list(dirnames):
            path = current_path / name
            if path.is_symlink():
                _add(findings, root, path, "symlink")
                dirnames.remove(name)
            elif name == ".git" and current_path == root:
                dirnames.remove(name)
            elif name == ".git":
                _add(findings, root, path, "nested_git_directory")
                dirnames.remove(name)
            elif name in FORBIDDEN_DIR_NAMES:
                _add(findings, root, path, "forbidden_directory")
                dirnames.remove(name)
        for name in filenames:
            path = current_path / name
            if name == ".git" and current_path == root:
                continue
            if name == ".git":
                _add(findings, root, path, "nested_git_file")
                continue
            if path.is_symlink():
                _add(findings, root, path, "symlink")
                continue
            if not path.is_file():
                _add(findings, root, path, "non_regular_file")
                continue
            try:
                total_bytes += path.stat().st_size
            except OSError:
                pass
            if name == ".env" or name.startswith(".env.") or name.endswith(ENV_SUFFIXES):
                _add(findings, root, path, "environment_file")
            if path.suffix.lower() in {".pem", ".key", ".jks"}:
                _add(findings, root, path, "credential_file")
            _scan_file(root, path, findings, max_file_bytes)
    if total_bytes > max_tree_bytes:
        findings.add(Finding(".", 1, "tree_size_limit"))
    return sorted(findings, key=lambda item: (item.path, item.line, item.rule))


def format_findings(findings: list[Finding]) -> str:
    """Format findings without including matched values or source lines."""
    return "\n".join(f"{item.path}:{item.line}:{item.rule}" for item in findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a checkout before public release.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-tree-bytes", type=int, default=DEFAULT_MAX_TREE_BYTES)
    args = parser.parse_args(argv)
    findings = scan_tree(
        args.root,
        max_file_bytes=args.max_file_bytes,
        max_tree_bytes=args.max_tree_bytes,
    )
    if findings:
        print(format_findings(findings))
        print(f"public-surface-check: FAIL ({len(findings)} findings)")
        return 1
    print("public-surface-check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
