#!/usr/bin/env bash
# run-clean-hit-ec.sh: predict EC numbers for cluster-neighbor proteins via CLEAN
#
# STATUS: foundation, not yet tested in production. HIT-EC stub omitted until
#         the Nat Commun 2026 reference repo is publicly released.
# Required tools: python3 with CLEAN deps + ESM
# Install: bash tools/recommended/install-heavy.sh
#       (clones tttianhao/CLEAN, installs ESM, caches embedding model)
#
# Usage:
#   run-clean-hit-ec.sh <species>
#
# <species> = coptis | houttuynia | stephania | phellodendron
#
# What it does:
#   Runs CLEAN inference on the per-species cluster-sequences.faa (~500
#   neighbor proteins). Output per-protein EC labels are joinable to the
#   `clusters-diamond` xlsx sheet via protein_id.
#
# Output: .runtime/campaign-<species>-summary/superpowers/clean-hit-ec/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CLEAN_DIR="${REPO_ROOT}/tools/recommended/clean-hit-ec/src/CLEAN"

# --- Tool availability -------------------------------------------------------
if [[ ! -d "$CLEAN_DIR" ]]; then
  echo "ERROR: CLEAN clone not found at: $CLEAN_DIR" >&2
  echo "       Run: bash tools/recommended/install-heavy.sh" >&2
  exit 127
fi
if [[ ! -f "${CLEAN_DIR}/CLEAN_infer_fasta.py" ]]; then
  echo "ERROR: CLEAN clone is incomplete (CLEAN_infer_fasta.py missing)." >&2
  echo "       Re-run: bash tools/recommended/install-heavy.sh" >&2
  exit 127
fi

# --- Args --------------------------------------------------------------------
SPECIES="${1:-}"
if [[ -z "$SPECIES" ]]; then
  echo "Usage: run-clean-hit-ec.sh <species>" >&2
  echo "  species: coptis | houttuynia | stephania | phellodendron" >&2
  exit 64
fi

SUMMARY_DIR="${REPO_ROOT}/.runtime/-summary"
QUERY_FASTA="${SUMMARY_DIR}/cluster-sequences.faa"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/clean-hit-ec"
SPLIT="${SPLIT:-70}"   # 70%-identity clustering split (better generalization)

if [[ ! -f "$QUERY_FASTA" ]]; then
  echo "ERROR: cluster sequences not found: $QUERY_FASTA" >&2
  exit 65
fi

mkdir -p "$OUTPUT_DIR"

# --- CLEAN inference ---------------------------------------------------------
# CLEAN expects to run from inside its own directory; restore cwd via subshell.
echo "[1/1] CLEAN inference on ${SPECIES} cluster sequences (split=${SPLIT})..."
(
  cd "$CLEAN_DIR"
  python3 CLEAN_infer_fasta.py \
    --fasta_data "$QUERY_FASTA" \
    --pretrained "$SPLIT"

  # Move outputs to the species summary
  shopt -s nullglob
  for f in results/*_maxsep.csv; do
    cp -f "$f" "${OUTPUT_DIR}/"
  done
)

echo
shopt -s nullglob
csvs=( "${OUTPUT_DIR}"/*.csv )
if (( ${#csvs[@]} == 0 )); then
  echo "WARN: CLEAN produced no *_maxsep.csv files." >&2
else
  for f in "${csvs[@]}"; do
    rows=$(wc -l < "$f" | tr -d ' ')
    echo "  $(basename "$f"): ${rows} rows"
  done
fi

echo
echo "DONE: CLEAN EC prediction on ${SPECIES}"
echo "  Output: ${OUTPUT_DIR}/"
echo "  HIT-EC stub omitted (pending public release)."
