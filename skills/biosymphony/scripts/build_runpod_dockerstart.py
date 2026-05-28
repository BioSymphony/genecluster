#!/usr/bin/env python3
"""Build a size-checked RunPod dockerStartCmd script.

This helper packages small launch-time files into a shell wrapper by gzipping
and base64-encoding them before substitution. It exists because RunPod pod
creation can fail with misleading capacity errors when the REST payload is too
large; GeneCluster launch artifacts should catch that locally before a paid pod
mutation.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re
from pathlib import Path
from typing import Any


PLACEHOLDER_RE = re.compile(r"__[A-Z0-9_]+_B64__")


def gzip_b64(path: Path) -> str:
    return base64.b64encode(gzip.compress(path.read_bytes())).decode("ascii")


def parse_input_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise ValueError(f"input spec must be TOKEN=PATH, got: {spec}")
    token, raw_path = spec.split("=", 1)
    token = token.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_]+", token):
        raise ValueError(f"input token must be uppercase-safe [A-Z0-9_]+, got: {token!r}")
    return token, Path(raw_path).expanduser()


def build_dockerstart(
    *,
    template: Path,
    pipeline: Path,
    inputs: list[tuple[str, Path]] | None = None,
    out: Path,
    max_bytes: int = 50 * 1024,
) -> dict[str, Any]:
    inputs = inputs or []
    template_text = template.read_text(encoding="utf-8")

    replacements: dict[str, dict[str, Any]] = {}

    pipeline_marker = "__PIPELINE_B64__"
    if pipeline_marker not in template_text:
        raise ValueError(f"template missing required marker {pipeline_marker}")
    encoded_pipeline = gzip_b64(pipeline)
    template_text = template_text.replace(pipeline_marker, encoded_pipeline)
    replacements[pipeline_marker] = {
        "path": str(pipeline),
        "source_bytes": pipeline.stat().st_size,
        "encoded_bytes": len(encoded_pipeline.encode("ascii")),
    }

    for token, path in inputs:
        marker = f"__{token}_B64__"
        if marker not in template_text:
            raise ValueError(f"template missing input marker {marker}")
        encoded = gzip_b64(path)
        template_text = template_text.replace(marker, encoded)
        replacements[marker] = {
            "path": str(path),
            "source_bytes": path.stat().st_size,
            "encoded_bytes": len(encoded.encode("ascii")),
        }

    unresolved = sorted(set(PLACEHOLDER_RE.findall(template_text)))
    if unresolved:
        raise ValueError("template still has unresolved base64 placeholders: " + ", ".join(unresolved))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(template_text, encoding="utf-8")
    output_bytes = out.stat().st_size
    ok = output_bytes <= max_bytes
    result = {
        "ok": ok,
        "template": str(template),
        "output": str(out),
        "output_bytes": output_bytes,
        "max_bytes": max_bytes,
        "replacements": replacements,
        "errors": [] if ok else [f"dockerStartCmd script too large: {output_bytes} bytes > {max_bytes} bytes"],
    }
    if not ok:
        raise ValueError(result["errors"][0])
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a gzip+base64 RunPod dockerStartCmd wrapper.")
    parser.add_argument("--template", type=Path, required=True, help="Shell template containing __PIPELINE_B64__.")
    parser.add_argument("--pipeline", type=Path, required=True, help="Pipeline script to embed.")
    parser.add_argument("--input", action="append", default=[], help="Additional TOKEN=PATH embed; template marker is __TOKEN_B64__.")
    parser.add_argument("--out", type=Path, required=True, help="Output dockerstart shell script.")
    parser.add_argument("--manifest-out", type=Path, help="Optional JSON manifest path.")
    parser.add_argument("--max-bytes", type=int, default=50 * 1024, help="Fail if output exceeds this byte count.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        input_specs = [parse_input_spec(spec) for spec in args.input]
        result = build_dockerstart(
            template=args.template,
            pipeline=args.pipeline,
            inputs=input_specs,
            out=args.out,
            max_bytes=args.max_bytes,
        )
    except (OSError, ValueError) as exc:
        result = {"ok": False, "errors": [str(exc)]}
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 1

    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.out} ({result['output_bytes']} bytes; ceiling {args.max_bytes})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
