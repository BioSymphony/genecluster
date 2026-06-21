#!/usr/bin/env python3
"""Preflight boring orchestration boundaries before Symphony/RunPod actions.

This script is deliberately non-biological. It catches plumbing failures that
can make a scientifically correct workflow fail silently: empty rendered
prompts, oversized provider payloads, missing files in a snapshot/ref, and
missing recovery checkpoints.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from preflight_check import validate as validate_issue_body  # noqa: E402


DEFAULT_PAYLOAD_WARN_BYTES = 50 * 1024
DEFAULT_PAYLOAD_MAX_BYTES = 60 * 1024
BOOT_INSTALL_MARKERS = [
    "mamba install",
    "conda install",
    "apt-get install",
    "apt install",
    "pip install",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json_or_text(path: Path) -> Any:
    text = read_text(path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def payload_size_bytes(value: Any) -> int:
    if isinstance(value, str):
        return len(value.encode("utf-8"))
    return len(json.dumps(value, sort_keys=True).encode("utf-8"))


def validate_rendered_prompt(path: Path, *, min_issue_body_bytes: int = 200) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    text = read_text(path)
    if not text.strip():
        errors.append("rendered prompt is empty")
    if re.search(r"<issue_body>\s*</issue_body>", text, flags=re.IGNORECASE | re.DOTALL):
        errors.append("rendered prompt has empty <issue_body> block")
    unresolved = re.findall(r"<(?:One or two sentence|input id|path|exact command)[^>]*>", text, flags=re.IGNORECASE)
    if unresolved:
        errors.append("rendered prompt contains unresolved template placeholders: " + ", ".join(sorted(set(unresolved))[:10]))

    issue_body_text = ""
    issue_match = re.search(r"<issue_body>(.*?)</issue_body>", text, flags=re.IGNORECASE | re.DOTALL)
    if issue_match:
        issue_body_text = issue_match.group(1).strip()
    elif "## Summary" in text:
        issue_body_text = text
        warnings.append("rendered prompt does not contain <issue_body> tags; validating whole prompt as issue body")

    issue_body_bytes = len(issue_body_text.encode("utf-8"))
    if issue_body_text and issue_body_bytes < min_issue_body_bytes:
        errors.append(f"issue body is too short ({issue_body_bytes} bytes)")
    if issue_body_text:
        issue_result = validate_issue_body(issue_body_text)
        errors.extend(f"issue_body: {error}" for error in issue_result["errors"])
        warnings.extend(f"issue_body: {warning}" for warning in issue_result["warnings"])
    else:
        errors.append("rendered prompt does not expose a non-empty issue body")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path": str(path),
        "prompt_bytes": len(text.encode("utf-8")),
        "issue_body_bytes": issue_body_bytes,
    }


def validate_payload(path: Path, *, warn_bytes: int, max_bytes: int, allow_boot_installs: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    value = read_json_or_text(path)
    total_bytes = payload_size_bytes(value)
    docker_start_bytes = 0
    if isinstance(value, dict):
        docker_cmd = value.get("dockerStartCmd")
        if isinstance(docker_cmd, list):
            docker_start_bytes = len(" ".join(map(str, docker_cmd)).encode("utf-8"))
            docker_start_text = " ".join(map(str, docker_cmd)).lower()
        elif isinstance(docker_cmd, str):
            docker_start_bytes = len(docker_cmd.encode("utf-8"))
            docker_start_text = docker_cmd.lower()
        else:
            docker_start_text = ""
    else:
        docker_start_text = str(value).lower()
    if total_bytes > max_bytes:
        errors.append(f"provider payload is too large ({total_bytes} bytes > {max_bytes})")
    elif total_bytes > warn_bytes:
        warnings.append(f"provider payload is near provider limit ({total_bytes} bytes > {warn_bytes})")
    if docker_start_bytes > max_bytes:
        errors.append(f"dockerStartCmd is too large ({docker_start_bytes} bytes > {max_bytes})")
    elif docker_start_bytes > warn_bytes:
        warnings.append(f"dockerStartCmd is near provider limit ({docker_start_bytes} bytes > {warn_bytes})")
    boot_markers = [marker for marker in BOOT_INSTALL_MARKERS if marker in docker_start_text]
    if boot_markers:
        message = (
            "dockerStartCmd performs first-boot package installation "
            f"({', '.join(boot_markers)}); use a baked image for standard provider launches"
        )
        if allow_boot_installs:
            warnings.append(message)
        else:
            errors.append(message)
    if isinstance(value, dict):
        env = value.get("env", {})
        if isinstance(env, dict):
            leaked = [key for key, val in env.items() if key.endswith(("KEY", "TOKEN")) and val and val != "MASKED"]
            if leaked:
                warnings.append("payload contains unmasked secret-like env values: " + ", ".join(sorted(leaked)))
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "path": str(path),
        "payload_bytes": total_bytes,
        "docker_start_bytes": docker_start_bytes,
        "warn_bytes": warn_bytes,
        "max_bytes": max_bytes,
        "boot_install_markers": boot_markers,
    }


def git_ref_has_path(git_ref: str, required_path: str) -> bool:
    target = f"{git_ref}:{required_path.strip('/')}"
    return subprocess.run(["git", "cat-file", "-e", target], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def validate_snapshot_paths(git_ref: str, required_paths: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    present = []
    missing = []
    for item in required_paths:
        if git_ref_has_path(git_ref, item):
            present.append(item)
        else:
            missing.append(item)
            errors.append(f"required path missing from git ref {git_ref}: {item}")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": [],
        "git_ref": git_ref,
        "present_paths": present,
        "missing_paths": missing,
    }


def validate_recovery_ledger(path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "errors": [str(exc)], "warnings": [], "path": str(path)}
    for key in ["issue_id", "last_confirmed_state", "checkpoint_artifacts", "resume_command", "degraded_recovery"]:
        if key not in data:
            errors.append(f"recovery ledger missing {key}")
    if not isinstance(data.get("checkpoint_artifacts", []), list) or not data.get("checkpoint_artifacts"):
        errors.append("recovery ledger checkpoint_artifacts must be a non-empty list")
    if data.get("degraded_recovery") is True and not data.get("degraded_reason"):
        errors.append("degraded recovery requires degraded_reason")
    if data.get("degraded_recovery") is False:
        warnings.append("recovery ledger reports no degraded recovery")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "path": str(path)}


def merge(results: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    for name, result in results:
        details[name] = result
        errors.extend(f"{name}: {error}" for error in result["errors"])
        warnings.extend(f"{name}: {warning}" for warning in result["warnings"])
    return {"ok": not errors, "errors": errors, "warnings": warnings, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Symphony/RunPod orchestration boundaries.")
    parser.add_argument("--issue-body", type=Path, help="Linear issue body Markdown file.")
    parser.add_argument("--rendered-prompt", type=Path, help="Rendered worker prompt file.")
    parser.add_argument("--provider-payload", type=Path, help="Provider API payload JSON/text to size-check.")
    parser.add_argument("--payload-warn-bytes", type=int, default=DEFAULT_PAYLOAD_WARN_BYTES)
    parser.add_argument("--payload-max-bytes", type=int, default=DEFAULT_PAYLOAD_MAX_BYTES)
    parser.add_argument("--allow-boot-installs", action="store_true", help="Allow package installs in dockerStartCmd. Emergency/debug only.")
    parser.add_argument("--git-ref", help="Git ref containing required paths.")
    parser.add_argument("--required-path", action="append", default=[], help="Path required in --git-ref. May be repeated.")
    parser.add_argument("--recovery-ledger", type=Path, help="Worker resume/degraded recovery JSON ledger.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results: list[tuple[str, dict[str, Any]]] = []
    if args.issue_body:
        text = read_text(args.issue_body)
        result = validate_issue_body(text)
        result["path"] = str(args.issue_body)
        result["issue_body_bytes"] = len(text.encode("utf-8"))
        results.append(("issue_body", result))
    if args.rendered_prompt:
        results.append(("rendered_prompt", validate_rendered_prompt(args.rendered_prompt)))
    if args.provider_payload:
        results.append(
            (
                "provider_payload",
                validate_payload(
                    args.provider_payload,
                    warn_bytes=args.payload_warn_bytes,
                    max_bytes=args.payload_max_bytes,
                    allow_boot_installs=args.allow_boot_installs,
                ),
            )
        )
    if args.git_ref or args.required_path:
        if not args.git_ref:
            results.append(("snapshot", {"ok": False, "errors": ["--git-ref is required with --required-path"], "warnings": []}))
        elif not args.required_path:
            results.append(("snapshot", {"ok": False, "errors": ["at least one --required-path is required with --git-ref"], "warnings": []}))
        else:
            results.append(("snapshot", validate_snapshot_paths(args.git_ref, args.required_path)))
    if args.recovery_ledger:
        results.append(("recovery_ledger", validate_recovery_ledger(args.recovery_ledger)))
    if not results:
        results.append(("usage", {"ok": False, "errors": ["no preflight target supplied"], "warnings": []}))

    result = merge(results)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("BioSymphony orchestration preflight:", "ok" if result["ok"] else "failed")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
