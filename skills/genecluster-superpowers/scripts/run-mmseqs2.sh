#!/usr/bin/env bash
# run-mmseqs2.sh: MMseqs2 iterative-profile search vs one species
#
# STATUS: foundation, not yet tested in production
# Required tools: mmseqs
# Install: brew install mmseqs2  (macOS)
#          mamba install -c conda-forge -c bioconda "mmseqs2>=18"
#       (or run tools/recommended/install-cheap.sh)
#
# Usage:
#   run-mmseqs2.sh <species> [query.faa]
#
# <species> = coptis | houttuynia | stephania | phellodendron
# [query.faa] defaults to .runtime/<species>-launch/queries-with-controls.faa
#
# What it does:
#   1. mmseqs createdb on query + species proteome
#   2. mmseqs search --num-iterations 3 --sensitivity 7.5
#   3. mmseqs convertalis → BLAST tabular outfmt6
#   4. Prints row-count delta vs the existing blastp_hits.tsv (sensitivity gain)
#
# Output: .runtime/campaign-<species>-summary/superpowers/mmseqs2/

set -euo pipefail

# --- Tool availability -------------------------------------------------------
if ! command -v mmseqs >/dev/null 2>&1; then
  echo "ERROR: 'mmseqs' not installed." >&2
  echo "       Run: bash tools/recommended/install-cheap.sh" >&2
  echo "       Or (macOS):  brew install mmseqs2" >&2
  echo "       Or (conda):  mamba install -c conda-forge -c bioconda \"mmseqs2>=18\"" >&2
  exit 127
fi

# --- Args --------------------------------------------------------------------
SPECIES="${1:-}"
if [[ -z "$SPECIES" ]]; then
  echo "Usage: run-mmseqs2.sh <species> [query.faa]" >&2
  echo "  species: coptis | houttuynia | stephania | phellodendron" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/-summary"
PROTEOME="${SUMMARY_DIR}/proteome.faa"
EXISTING_BLASTP="${SUMMARY_DIR}/blastp_hits.tsv"
QUERY_FASTA="${2:-${REPO_ROOT}/.runtime/<species>-launch/queries-with-controls.faa}"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/mmseqs2"

if [[ ! -f "$PROTEOME" ]]; then
  echo "ERROR: proteome not found: $PROTEOME" >&2
  exit 65
fi
if [[ ! -f "$QUERY_FASTA" ]]; then
  echo "ERROR: query FASTA not found: $QUERY_FASTA" >&2
  exit 65
fi

THREADS="${THREADS:-8}"
SENSITIVITY="${SENSITIVITY:-7.5}"

mkdir -p "${OUTPUT_DIR}/tmp"

# --- 1. Build DBs ------------------------------------------------------------
echo "[1/3] mmseqs createdb (queries + ${SPECIES} proteome)..."
mmseqs createdb "$QUERY_FASTA" "${OUTPUT_DIR}/queries.db"
mmseqs createdb "$PROTEOME" "${OUTPUT_DIR}/target.db"

# --- 2. Iterative-profile search ---------------------------------------------
echo "[2/3] mmseqs search --num-iterations 3 --sensitivity ${SENSITIVITY} --threads ${THREADS}..."
mmseqs search \
  "${OUTPUT_DIR}/queries.db" \
  "${OUTPUT_DIR}/target.db" \
  "${OUTPUT_DIR}/result" \
  "${OUTPUT_DIR}/tmp" \
  --num-iterations 3 \
  --sensitivity "$SENSITIVITY" \
  --threads "$THREADS"

# --- 3. Convert to BLAST tabular ---------------------------------------------
echo "[3/3] mmseqs convertalis → BLAST tabular..."
mmseqs convertalis \
  "${OUTPUT_DIR}/queries.db" \
  "${OUTPUT_DIR}/target.db" \
  "${OUTPUT_DIR}/result" \
  "${OUTPUT_DIR}/queries-vs-target.outfmt6" \
  --format-mode 0

# --- Sensitivity gain report -------------------------------------------------
echo
mmseqs_rows=$(wc -l < "${OUTPUT_DIR}/queries-vs-target.outfmt6" | tr -d ' ')
if [[ -f "$EXISTING_BLASTP" ]]; then
  blastp_rows=$(wc -l < "$EXISTING_BLASTP" | tr -d ' ')
  echo "Sensitivity gain (rows):"
  echo "  blastp_hits.tsv:       ${blastp_rows}"
  echo "  mmseqs2 outfmt6:       ${mmseqs_rows}"
  echo "  delta:                 $((mmseqs_rows - blastp_rows))"
else
  echo "No existing blastp_hits.tsv found; mmseqs2 rows = ${mmseqs_rows}"
fi

echo
echo "DONE: mmseqs2 iterative-profile on ${SPECIES}"
echo "  Output: ${OUTPUT_DIR}/queries-vs-target.outfmt6"
