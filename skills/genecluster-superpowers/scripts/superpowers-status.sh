#!/usr/bin/env bash
# Report local commands and Python package metadata without loading models.
set -euo pipefail

case "${1:-}" in
  -h|--help)
    echo "Usage: superpowers-status.sh"
    echo "Report local tool availability; does not install tools or validate analyses."
    exit 0 ;;
  "") ;;
  *) echo "Unknown argument: $1 (use --help)" >&2; exit 64 ;;
esac

row() { printf ' %-20s %-10s %s\n' "$1" "$2" "$3"; }
probe() {
  local label="$1" command_name="$2" version
  shift 2
  if command -v "$command_name" >/dev/null 2>&1; then
    version="$("$command_name" "$@" 2>&1 | head -n 1 || true)"
    row "$label" "present" "${version:-version unavailable}"
  else
    row "$label" "missing" ""
  fi
}

printf '\nBioSymphony GeneCluster: local tool availability\n\n'
row "Tool" "Command" "Reported version"
probe MMseqs2 mmseqs version
probe BLAST blastp -version
probe DIAMOND diamond version
probe HMMER hmmsearch -h
probe InterProScan interproscan.sh --version
probe Foldseek foldseek version
probe cblaster cblaster --version
probe clinker clinker --version
probe LAST lastdb --version
probe antiSMASH antismash --version
probe plantiSMASH plantismash --version
probe Quarto quarto --version
probe Docker docker --version

if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PYTHON'
from importlib.metadata import PackageNotFoundError, version
for package in ("jcvi", "torch", "transformers"):
    try:
        print(f" {package:20} {'package':10} {version(package)}")
    except PackageNotFoundError:
        print(f" {package:20} {'missing':10}")
PYTHON
fi
printf '\nChecks commands on PATH and packages in the active Python environment.\n'
printf 'Model weights, databases, container services, and wrapper compatibility require separate checks.\n'
printf 'See docs/tooling/tool-chaining.md for calling instructions.\n'
