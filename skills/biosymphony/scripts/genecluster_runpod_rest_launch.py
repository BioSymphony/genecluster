#!/usr/bin/env python3
"""Launch a GeneCluster RunPod Pod through the REST API.

The RunPod MCP create-pod schema available to some agents does not expose
`networkVolumeId` or `dockerStartCmd`. This launcher reads the validated
GeneCluster provider payload and uses RunPod REST directly. It does not store
secrets in the bundle or repo; credentials must come from the shell environment
or a sourced local secret file.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PAYLOAD_WARN_BYTES = 50 * 1024
DEFAULT_PAYLOAD_MAX_BYTES = 60 * 1024
DEFAULT_MIN_CONTAINER_DISK_GB = 80
BOOT_INSTALL_MARKERS = [
    "mamba install",
    "conda install",
    "apt-get install",
    "apt install",
    "pip install",
]
RUNPOD_REGISTRY_AUTH_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "RUNPOD_CONTAINER_REGISTRY_AUTH_ID",
    "GENECLUSTER_CONTAINER_REGISTRY_AUTH_ID",
]
RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES = [
    "GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL",
    "GENECLUSTER_IMAGE_PUBLIC_PULL",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_manifest_path(value: str, manifest_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def need_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"ERROR: {name} is not set")
    return value


def first_present_env(names: list[str]) -> tuple[str, str]:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return name, value
    return "", ""


def env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def registry_auth_error(provider: dict[str, Any]) -> str:
    policy = provider.get("registry_auth_policy", {})
    if not isinstance(policy, dict) or not policy:
        return "provider payload is missing registry_auth_policy; regenerate the launch bundle before RunPod launch"
    auth_names = policy.get("container_registry_auth_id_env_names", RUNPOD_REGISTRY_AUTH_ENV_NAMES)
    public_names = policy.get("public_image_assertion_env_names", RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES)
    if not isinstance(auth_names, list):
        auth_names = RUNPOD_REGISTRY_AUTH_ENV_NAMES
    if not isinstance(public_names, list):
        public_names = RUNPOD_IMAGE_PUBLIC_ASSERTION_ENV_NAMES
    auth_present = bool(first_present_env([str(name) for name in auth_names])[0])
    public_asserted = bool(policy.get("public_image_asserted")) or any(env_truthy(str(name)) for name in public_names)
    auth_needed = bool(policy.get("auth_likely_required") or policy.get("launch_blocker_if_missing"))
    if auth_needed and not auth_present and not public_asserted:
        return (
            "image registry likely requires auth but no RunPod container registry auth id is configured. "
            "Set GENECLUSTER_RUNPOD_CONTAINER_REGISTRY_AUTH_ID/RUNPOD_CONTAINER_REGISTRY_AUTH_ID, "
            "or set GENECLUSTER_RUNPOD_IMAGE_PUBLIC_PULL=1 only after proving the digest-pinned image is public-pullable."
        )
    return ""


def registry_auth_id_for_payload(provider: dict[str, Any]) -> tuple[str, str]:
    policy = provider.get("registry_auth_policy", {})
    names = RUNPOD_REGISTRY_AUTH_ENV_NAMES
    if isinstance(policy, dict) and isinstance(policy.get("container_registry_auth_id_env_names"), list):
        names = [str(name) for name in policy["container_registry_auth_id_env_names"]]
    return first_present_env(names)


def git_ref_has_bundle(git_ref: str, bundle_path: str) -> bool:
    target = f"{git_ref}:{bundle_path.strip('/')}/launch-manifest.json"
    return subprocess.run(["git", "cat-file", "-e", target], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def env_or_payload(value: str, env_name: str) -> str:
    if value.startswith("env:"):
        return need_env(value.split(":", 1)[1])
    return os.environ.get(env_name, "").strip() or value


def redact_payload(data: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(data))
    if redacted.get("containerRegistryAuthId"):
        redacted["containerRegistryAuthId"] = "REDACTED"
    for key in list(redacted.get("env", {})):
        if key.endswith("KEY") or key.endswith("TOKEN") or key in {"RUNPOD_API_KEY", "GITHUB_TOKEN"}:
            redacted["env"][key] = "REDACTED"
    return redacted


def provider_runtime_env(provider: dict[str, Any], *, run_id: str) -> dict[str, str]:
    env = {
        "GENECLUSTER_RUN_ID": run_id,
        "GENECLUSTER_DB_CACHE_ROOT": str(provider.get("db_cache_root", "/workspace/genecluster/db-cache")),
        "GENECLUSTER_SEARCH_CACHE_ROOT": "/workspace/genecluster/search-cache",
        "NXF_HOME": "/workspace/genecluster/nextflow-cache",
        "GENECLUSTER_RUNPOD_IDLE_SECONDS": str(provider.get("pod_lifecycle_policy", {}).get("idle_after_completion_seconds", 900)),
    }
    for name in ["GENECLUSTER_FASTQ_THREADS", "GENECLUSTER_FASTQ_TO_FASTA_MAX_READS"]:
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


def payload_size(data: dict[str, Any]) -> int:
    return len(json.dumps(data, sort_keys=True).encode("utf-8"))


def docker_start_size(data: dict[str, Any]) -> int:
    command = data.get("dockerStartCmd", "")
    if isinstance(command, list):
        return len(" ".join(map(str, command)).encode("utf-8"))
    return len(str(command).encode("utf-8"))


def docker_start_text(data: dict[str, Any]) -> str:
    command = data.get("dockerStartCmd", "")
    if isinstance(command, list):
        return " ".join(map(str, command))
    return str(command)


def payload_preflight(
    data: dict[str, Any],
    *,
    warn_bytes: int,
    max_bytes: int,
    allow_boot_installs: bool = False,
) -> dict[str, Any]:
    total = payload_size(data)
    start = docker_start_size(data)
    start_text = docker_start_text(data).lower()
    errors: list[str] = []
    warnings: list[str] = []
    env = data.get("env", {})
    if isinstance(env, dict):
        for key, value in env.items():
            key_text = str(key)
            if key_text.endswith(("KEY", "TOKEN")) or key_text in {"RUNPOD_API_KEY", "GITHUB_TOKEN", "GH_TOKEN"}:
                errors.append(f"RunPod REST payload must not pass secret-like env var into pod: {key_text}")
            elif key_text.endswith("_ID") and key_text in {"RUNPOD_POD_ID", "RUNPOD_PODID"}:
                errors.append(f"RunPod REST payload must not pass provider runtime id into pod env: {key_text}")
            elif isinstance(value, str) and ("Authorization: Bearer " in value or ("x-" + "access-token") in value):
                errors.append(f"RunPod REST payload env value looks credential-bearing: {key_text}")
    if total > max_bytes:
        errors.append(f"RunPod REST payload too large: {total} bytes > {max_bytes}")
    elif total > warn_bytes:
        warnings.append(f"RunPod REST payload near limit: {total} bytes > {warn_bytes}")
    if start > max_bytes:
        errors.append(f"dockerStartCmd too large: {start} bytes > {max_bytes}")
    elif start > warn_bytes:
        warnings.append(f"dockerStartCmd near limit: {start} bytes > {warn_bytes}")
    boot_markers = [marker for marker in BOOT_INSTALL_MARKERS if marker in start_text]
    if boot_markers:
        message = (
            "dockerStartCmd performs first-boot package installation "
            f"({', '.join(boot_markers)}); use a baked image for standard GeneCluster launches"
        )
        if allow_boot_installs:
            warnings.append(message)
        else:
            errors.append(message)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "payload_bytes": total,
        "docker_start_bytes": start,
        "warn_bytes": warn_bytes,
        "max_bytes": max_bytes,
        "boot_install_markers": boot_markers,
    }


def build_docker_start(
    *,
    repo_url: str,
    git_ref: str,
    bundle_path: str,
    run_id: str,
) -> str:
    return f"""set -euo pipefail
ts() {{ date -u +%Y-%m-%dT%H:%M:%SZ; }}
mkdir -p /workspace/genecluster/runs/{run_id}/logs
exec > >(tee -a /workspace/genecluster/runs/{run_id}/logs/dockerstart-rest-launch.log) 2>&1
echo "[$(ts)] GeneCluster REST launch boot"
rm -rf /opt/biosymphony-genecluster
git clone --depth 1 --branch "{git_ref}" "https://{repo_url}" /opt/biosymphony-genecluster
cd "/opt/biosymphony-genecluster/{bundle_path}"
export GENECLUSTER_BUNDLE_DIR="$PWD"
export GENECLUSTER_DB_CACHE_ROOT="${{GENECLUSTER_DB_CACHE_ROOT:-/workspace/genecluster/db-cache}}"
export GENECLUSTER_SEARCH_CACHE_ROOT="${{GENECLUSTER_SEARCH_CACHE_ROOT:-/workspace/genecluster/search-cache}}"
export NXF_HOME="${{NXF_HOME:-/workspace/genecluster/nextflow-cache}}"
echo "[$(ts)] Starting provider/runpod-docker-start.sh from $PWD"
bash provider/runpod-docker-start.sh
"""


def create_pod(api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://rest.runpod.io/v1/pods",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        return json.loads(urllib.request.urlopen(req, timeout=45).read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"ERROR: RunPod REST HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a GeneCluster bundle on RunPod via REST.")
    parser.add_argument("--launch-manifest", type=Path, required=True)
    parser.add_argument(
        "--git-repo",
        default=os.environ.get("GENECLUSTER_GIT_REPO", ""),
        help="Git repo host/path without protocol. The pod must be able to clone it without embedding credentials in the payload.",
    )
    parser.add_argument("--git-ref", required=True, help="Branch/tag/commit containing the launch bundle.")
    parser.add_argument("--bundle-path", required=True, help="Path to bundle within the cloned repo, e.g. .runtime/genecluster-launch-full-public-mining.")
    parser.add_argument("--pod-id-out", type=Path, help="Where to write created pod id.")
    parser.add_argument("--name", help="RunPod pod name override.")
    parser.add_argument("--vcpu-count", type=int, default=16)
    parser.add_argument("--container-disk-gb", type=int, default=80)
    parser.add_argument("--min-container-disk-gb", type=int, default=DEFAULT_MIN_CONTAINER_DISK_GB)
    parser.add_argument("--allow-small-container-disk", action="store_true", help="Allow container disk below the GeneCluster safety default. Use only for smoke/debug runs.")
    parser.add_argument("--allow-first-boot-install", action="store_true", help="Allow package installation inside dockerStartCmd. Emergency/debug only; baked images are required for normal runs.")
    parser.add_argument("--payload-warn-bytes", type=int, default=DEFAULT_PAYLOAD_WARN_BYTES)
    parser.add_argument("--payload-max-bytes", type=int, default=DEFAULT_PAYLOAD_MAX_BYTES)
    parser.add_argument("--skip-git-ref-check", action="store_true", help="Do not verify that the bundle path exists in the local Git ref before launching.")
    parser.add_argument("--dry-run", action="store_true", help="Print redacted REST payload and do not launch.")
    args = parser.parse_args()

    manifest_path = args.launch_manifest.resolve()
    if not args.git_repo:
        raise SystemExit("ERROR: --git-repo or GENECLUSTER_GIT_REPO is required")
    manifest = read_json(manifest_path)
    provider_payload_path = resolve_manifest_path(str(manifest.get("provider_payload", "provider/runpod-pod.json")), manifest_path)
    provider = read_json(provider_payload_path)
    if provider.get("provider_class") != "runpod_pod":
        raise SystemExit("ERROR: provider payload is not runpod_pod")
    if args.container_disk_gb < args.min_container_disk_gb and not args.allow_small_container_disk:
        raise SystemExit(
            f"ERROR: --container-disk-gb {args.container_disk_gb} is below the safety minimum "
            f"{args.min_container_disk_gb}. Use a baked image or pass --allow-small-container-disk only for deliberate smoke/debug runs."
        )

    api_key = need_env("RUNPOD_API_KEY")
    volume_id = env_or_payload(str(provider.get("network_volume_id", "")), "GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID")
    datacenter = env_or_payload(str(provider.get("datacenter", "")), "GENECLUSTER_RUNPOD_DATACENTER")
    if not volume_id or volume_id.startswith("env:"):
        raise SystemExit("ERROR: RunPod network volume id is unresolved")
    if not datacenter or datacenter.startswith("env:"):
        raise SystemExit("ERROR: RunPod datacenter is unresolved")
    image = str(provider.get("image") or manifest.get("runner", {}).get("image") or "")
    if not image or image == "genecluster-runner:unbuilt" or "@sha256:" not in image:
        raise SystemExit("ERROR: execution requires a digest-pinned image")
    registry_error = registry_auth_error(provider)
    if registry_error:
        raise SystemExit(f"ERROR: {registry_error}")
    if not args.skip_git_ref_check and not git_ref_has_bundle(args.git_ref, args.bundle_path):
        raise SystemExit(
            "ERROR: bundle path is not present in the requested Git ref. "
            f"Missing `{args.git_ref}:{args.bundle_path.strip('/')}/launch-manifest.json`. "
            "Commit/force-add the bundle to a private run branch or pass --skip-git-ref-check only if another delivery path guarantees it."
        )

    run_id = str(manifest.get("run_id", provider.get("run_id", "genecluster-run")))
    docker_start = build_docker_start(
        repo_url=args.git_repo,
        git_ref=args.git_ref,
        bundle_path=args.bundle_path.strip("/"),
        run_id=run_id,
    )
    env = provider_runtime_env(provider, run_id=run_id)

    body = {
        "name": args.name or f"genecluster-{run_id}",
        "imageName": image,
        "computeType": "CPU",
        "vcpuCount": args.vcpu_count,
        "dataCenterIds": [datacenter],
        "networkVolumeId": volume_id,
        "volumeMountPath": provider.get("mount_path", "/workspace"),
        "containerDiskInGb": args.container_disk_gb,
        "env": env,
        "dockerStartCmd": ["bash", "-lc", docker_start],
    }
    registry_auth_env, registry_auth_id = registry_auth_id_for_payload(provider)
    if registry_auth_id:
        body["containerRegistryAuthId"] = registry_auth_id
    payload_check = payload_preflight(
        body,
        warn_bytes=args.payload_warn_bytes,
        max_bytes=args.payload_max_bytes,
        allow_boot_installs=args.allow_first_boot_install,
    )
    if not payload_check["ok"]:
        for error in payload_check["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
    if args.dry_run:
        redacted = redact_payload(body)
        redacted["_preflight"] = payload_check
        print(json.dumps(redacted, indent=2, sort_keys=True))
        return 0

    response = create_pod(api_key, body)
    pod_id = response.get("id")
    if not pod_id:
        raise SystemExit(f"ERROR: no pod id returned: {json.dumps(response)[:1000]}")
    if args.pod_id_out:
        args.pod_id_out.parent.mkdir(parents=True, exist_ok=True)
        args.pod_id_out.write_text(str(pod_id) + "\n", encoding="utf-8")
    print(f"RunPod pod created: {pod_id}")
    print(f"name={response.get('name', body['name'])} datacenter={datacenter} image={image}")
    if registry_auth_id:
        print(f"containerRegistryAuthId supplied from {registry_auth_env}")
    print(f"payload_bytes={payload_check['payload_bytes']} docker_start_bytes={payload_check['docker_start_bytes']}")
    for warning in payload_check["warnings"]:
        print(f"WARN: {warning}")
    print("Provider credentials were used only by the local launcher and were not placed in the pod environment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
