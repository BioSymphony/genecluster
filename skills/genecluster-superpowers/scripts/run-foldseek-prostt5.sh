#!/usr/bin/env bash
# run-foldseek-prostt5.sh: structure-based homology via Foldseek + ProstT5
#                          (sequence-only; no AlphaFold step needed)
#
# STATUS: adaptation required; wrapper not tested. A Foldseek/ProstT5 tool
#         baseline does not certify this wrapper.
# ADAPTATION REQUIRED:
#   Verify the target input type, ProstT5 model revision, CLI flags, and output
#   fields against the pinned Foldseek release before use. Hit scores require
#   independent functional and coordinate evidence.
# Required tools: foldseek
# Required Python deps: torch, transformers, sentencepiece (Rostlab/ProstT5)
# Install: bash tools/recommended/install-heavy.sh
#       (downloads Foldseek prebuilt binary, caches Rostlab/ProstT5 from HF)
#
# Usage:
#   run-foldseek-prostt5.sh <species> [query.faa]
#
# <species> = a species slug used by the campaign directory layout
# [query.faa] defaults to .runtime/campaign-<species>-summary/cluster-sequences.faa
#
# The output is a tabular structure-similarity result. This wrapper does not
# establish convergence, function, or a score threshold.

set -euo pipefail

# --- Tool availability -------------------------------------------------------
if ! command -v foldseek >/dev/null 2>&1; then
  echo "ERROR: 'foldseek' not installed." >&2
  echo "       Run: bash tools/recommended/install-heavy.sh" >&2
  exit 127
fi
if ! python3 -c "import torch, transformers" >/dev/null 2>&1; then
  echo "ERROR: ProstT5 dependencies (torch, transformers) missing." >&2
  echo "       Run: bash tools/recommended/install-heavy.sh" >&2
  exit 127
fi

# --- Args --------------------------------------------------------------------
SPECIES="${1:-}"
if [[ -z "$SPECIES" ]]; then
  echo "Usage: run-foldseek-prostt5.sh <species> [query.faa]" >&2
  echo "  species: a species slug used by the campaign directory layout" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/campaign-${SPECIES}-summary"
PROTEOME="${SUMMARY_DIR}/proteome.faa"
QUERY_FASTA="${2:-${SUMMARY_DIR}/cluster-sequences.faa}"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/foldseek"

if [[ ! -f "$PROTEOME" ]]; then
  echo "ERROR: proteome not found: $PROTEOME" >&2
  exit 65
fi
if [[ ! -f "$QUERY_FASTA" ]]; then
  echo "ERROR: query FASTA not found: $QUERY_FASTA" >&2
  exit 65
fi

THREADS="${THREADS:-8}"

mkdir -p "${OUTPUT_DIR}/tmp"

# --- Foldseek easy-search via ProstT5 ----------------------------------------
echo "[1/1] foldseek easy-search (ProstT5 sequence-only encoding)..."
foldseek easy-search \
  "$QUERY_FASTA" \
  "$PROTEOME" \
  "${OUTPUT_DIR}/foldseek-hits.m8" \
  "${OUTPUT_DIR}/tmp" \
  --prostt5-model "Rostlab/ProstT5" \
  --threads "$THREADS" \
  --format-output "query,target,evalue,bits,alntmscore"

# --- Result count ------------------------------------------------------------
echo
hits=$(wc -l < "${OUTPUT_DIR}/foldseek-hits.m8" | tr -d ' ')
echo "Foldseek hit rows: ${hits}"

echo
echo "ADAPTATION REQUIRED: inspect Foldseek output before downstream use."
echo "  Output: ${OUTPUT_DIR}/foldseek-hits.m8"
echo "  Compare with sequence, domain, and coordinate evidence."
