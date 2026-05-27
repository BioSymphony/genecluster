#!/usr/bin/env bash
# run-foldseek-prostt5.sh: structure-based homology via Foldseek + ProstT5
#                          (sequence-only; no AlphaFold step needed)
#
# STATUS: foundation, not yet tested in production
# Required tools: foldseek
# Required Python deps: torch, transformers, sentencepiece (Rostlab/ProstT5)
# Install: bash tools/recommended/install-heavy.sh
#       (downloads Foldseek prebuilt binary, caches Rostlab/ProstT5 from HF)
#
# Usage:
#   run-foldseek-prostt5.sh <species> [query.faa]
#
# <species> = coptis | houttuynia | stephania | phellodendron
# [query.faa] defaults to .runtime/<species>-summary/cluster-sequences.faa
#             (the canonical Coptis BIA cluster proteins; the proof-test asks
#              "what folds in <species> match Coptis BBE/CYP cluster fold-wise
#              that BLAST missed?")
#
# Manuscript-differentiator: catches convergent enzymes invisible to BLAST at
# <15% sequence identity. Output column `prob` >0.9 = same fold; `alntmscore`
# >0.5 = structural match.

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
  echo "  species: coptis | houttuynia | stephania | phellodendron" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/-summary"
PROTEOME="${SUMMARY_DIR}/proteome.faa"
QUERY_FASTA="${2:-${REPO_ROOT}/.runtime/<species>-summary/cluster-sequences.faa}"
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
  --format-output "query,target,evalue,bits,prob,alntmscore"

# --- Headline summary --------------------------------------------------------
echo
hits=$(wc -l < "${OUTPUT_DIR}/foldseek-hits.m8" | tr -d ' ')
echo "Foldseek hit rows: ${hits}"
if [[ "$hits" -gt 0 ]]; then
  high_conf=$(awk '$5 > 0.9 {n++} END {print n+0}' "${OUTPUT_DIR}/foldseek-hits.m8")
  echo "  high-confidence (prob > 0.9): ${high_conf}"
fi

echo
echo "DONE: Foldseek + ProstT5 on ${SPECIES}"
echo "  Output: ${OUTPUT_DIR}/foldseek-hits.m8"
echo "  Cross-tab against blastp_hits.tsv to find fold-only convergence cases."
