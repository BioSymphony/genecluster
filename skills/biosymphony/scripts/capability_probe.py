#!/usr/bin/env python3
"""Probe local BioSymphony capabilities without requiring third-party packages."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PYMOL_APP = Path("/Applications/PyMOL.app/Contents/bin/pymol")
CHIMERAX_APP = Path("/Applications/ChimeraX-1.11.1.app/Contents/bin/ChimeraX")

PATH_COMMANDS = [
    "pymol",
    "ChimeraX",
    "chimerax",
    "hf",
    "conda",
    "colabfold_batch",
    "boltz",
    "boltzgen",
    "mmseqs",
]

PYTHON_MODULES = [
    "torch",
    "transformers",
    "mlx",
    "esm",
    "boltz",
    "colabfold",
    "openmm",
    "MDAnalysis",
    "pyrosetta",
    "Bio",
    "mdtraj",
    "huggingface_hub",
]


def run_command(args: list[str], timeout: int = 8) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def probe_http(url: str, timeout: float = 1.5) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(500).decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status, "body": body}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


def conda_envs(conda_path: str | None) -> dict[str, Any]:
    if not conda_path:
        return {"ok": False, "envs": [], "error": "conda not found"}
    result = run_command([conda_path, "env", "list", "--json"])
    if not result["ok"]:
        return {"ok": False, "envs": [], "error": result.get("stderr") or result.get("stdout")}
    try:
        data = json.loads(result["stdout"])
    except json.JSONDecodeError as exc:
        return {"ok": False, "envs": [], "error": str(exc)}
    return {"ok": True, "envs": data.get("envs", [])}


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe local BioSymphony capability tiers.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help=(
            "Report-only: always exit 0 even when Tier A is not locally ready. "
            "Used by `make capability` so CI (which lacks local GUI apps / tooling / "
            "the ValarTTS server) does not fail. Direct invocation without this flag "
            "keeps the exit-1 signal for local readiness checks."
        ),
    )
    args = parser.parse_args()

    path_commands = {cmd: shutil.which(cmd) for cmd in PATH_COMMANDS}
    python_modules = {mod: importlib.util.find_spec(mod) is not None for mod in PYTHON_MODULES}

    chimerax_help = None
    if CHIMERAX_APP.exists():
        help_result = run_command([str(CHIMERAX_APP), "--help"], timeout=12)
        flags = ["--nogui", "--offscreen", "--silent", "--exit", "--script", "--cmd"]
        text = "\n".join([help_result.get("stdout", ""), help_result.get("stderr", "")])
        chimerax_help = {
            "ok": help_result["ok"] or bool(text),
            "flags": {flag: flag in text for flag in flags},
        }

    hf_version = None
    if path_commands.get("hf"):
        hf_version = run_command([path_commands["hf"], "--version"])

    valartts = {}
    for suffix in ["/health", "/status", "/"]:
        url = "http://127.0.0.1:8787" + suffix
        result = probe_http(url)
        valartts[suffix] = result
        if result["ok"]:
            break

    tier_a_ready = bool(PYMOL_APP.exists() and CHIMERAX_APP.exists())
    tier_b_ready = any(
        [
            bool(path_commands.get("colabfold_batch")),
            bool(path_commands.get("boltz")),
            bool(path_commands.get("mmseqs")),
            python_modules.get("torch", False),
            python_modules.get("openmm", False),
            python_modules.get("MDAnalysis", False),
        ]
    )

    report = {
        "schema_version": 1,
        "cwd": os.getcwd(),
        "python": sys.executable,
        "apps": {
            "pymol_app": {"path": str(PYMOL_APP), "exists": PYMOL_APP.exists()},
            "chimerax_app": {"path": str(CHIMERAX_APP), "exists": CHIMERAX_APP.exists()},
            "chimerax_help": chimerax_help,
        },
        "path_commands": path_commands,
        "python_modules": python_modules,
        "conda": conda_envs(path_commands.get("conda")),
        "hf": hf_version,
        "valartts": valartts,
        "tiers": {
            "tier_a_local_now": tier_a_ready,
            "tier_b_experimental_ready": tier_b_ready,
            "tier_c_manual_or_licensed_ready": python_modules.get("pyrosetta", False),
            "tier_d_cloud_required": True,
        },
        "notes": [
            "Tier A still requires campaign-specific check commands.",
            "ChimeraX GUI + REST is the default render path on macOS.",
            "Tier B claims require exact tool/env probes before dispatch.",
        ],
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("BioSymphony capability probe")
        print(f"PyMOL app: {'yes' if PYMOL_APP.exists() else 'no'} - {PYMOL_APP}")
        print(f"ChimeraX app: {'yes' if CHIMERAX_APP.exists() else 'no'} - {CHIMERAX_APP}")
        print(f"Tier A local-now: {'yes' if tier_a_ready else 'no'}")
        print(f"Tier B experimental ready: {'yes' if tier_b_ready else 'no'}")
        missing = [cmd for cmd, found in path_commands.items() if not found]
        if missing:
            print("Missing PATH commands: " + ", ".join(missing))
        missing_mods = [mod for mod, found in python_modules.items() if not found]
        if missing_mods:
            print("Missing Python modules: " + ", ".join(missing_mods))

    if args.no_fail:
        return 0
    return 0 if tier_a_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
