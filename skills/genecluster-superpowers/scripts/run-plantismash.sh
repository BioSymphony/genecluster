#!/usr/bin/env bash
# run-plantismash.sh: plantiSMASH 2.0.4 against one atlas species
#
# STATUS: adaptation required; wrapper not tested. A plantiSMASH 2.0.4 tool
#         baseline does not certify this wrapper.
# ADAPTATION REQUIRED:
#   Verify the input format, taxon option, CLI flags, and output files against
#   the pinned plantiSMASH release before use. This draft points at a GFF file;
#   use a supported input format or add an explicit conversion step. Candidate
#   regions require independent normalization and review.
# Required tools: plantiSMASH 2.0.4 command or conda env named plantismash
# Install: bash tools/recommended/install-medium.sh
#
# Usage:
#   run-plantismash.sh <species>
#
# <species> = a species slug used by the campaign directory layout
#
# What it does:
#   Runs plantiSMASH 2.0.4 against the species input after the input contract
#   is adapted. It writes candidate region records and report files.
#
# Output: .runtime/campaign-<species>-summary/superpowers/plantismash/

set -euo pipefail

# --- Tool availability -------------------------------------------------------
if command -v plantismash >/dev/null 2>&1; then
  PLANTISMASH_CMD=(plantismash)
elif command -v conda >/dev/null 2>&1 && conda env list | awk '{print $1}' | grep -qx plantismash; then
  PLANTISMASH_CMD=(conda run -n plantismash plantismash)
elif command -v mamba >/dev/null 2>&1 && mamba env list | awk '{print $1}' | grep -qx plantismash; then
  PLANTISMASH_CMD=(mamba run -n plantismash plantismash)
else
  echo "ERROR: plantiSMASH 2.0.4 is not available." >&2
  echo "       Run: bash tools/recommended/install-medium.sh" >&2
  exit 127
fi

# --- Args --------------------------------------------------------------------
SPECIES="${1:-}"
if [[ -z "$SPECIES" ]]; then
  echo "Usage: run-plantismash.sh <species>" >&2
  echo "  species: a species slug used by the campaign directory layout" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/campaign-${SPECIES}-summary"
INPUT_FILE="${SUMMARY_DIR}/genomic.gff"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/plantismash"

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "ERROR: plantiSMASH input not found: $INPUT_FILE" >&2
  exit 65
fi

mkdir -p "$OUTPUT_DIR"

# --- Run ---------------------------------------------------------------------
echo "[1/1] plantiSMASH 2.0.4 on ${SPECIES}..."
"${PLANTISMASH_CMD[@]}" \
  --taxon plants \
  --genefinding-tool none \
  --outputfolder "$OUTPUT_DIR" \
  "$INPUT_FILE"

echo
if compgen -G "${OUTPUT_DIR}/*.gbk" >/dev/null; then
  echo "plantiSMASH GenBank output: present"
else
  echo "WARN: no GenBank output found in ${OUTPUT_DIR}." >&2
fi

echo
echo "ADAPTATION REQUIRED: review plantiSMASH output before downstream use."
echo "  Output: ${OUTPUT_DIR}/"
echo "  Tip: open ${OUTPUT_DIR}/index.html"
