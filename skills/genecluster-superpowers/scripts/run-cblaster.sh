#!/usr/bin/env bash
# run-cblaster.sh: wrap cblaster + clinker for one atlas species
#
# STATUS: foundation, not yet tested in production
# Required tools: cblaster, clinker, diamond
# Install: pip install "cblaster>=1.4.0" "clinker>=0.0.32"
#          conda install -c bioconda "diamond>=2.1"
#       (or run tools/recommended/install-cheap.sh)
#
# Usage:
#   run-cblaster.sh <species> [query.faa]
#
# <species> = coptis | houttuynia | stephania | phellodendron
# [query.faa] defaults to .runtime/<species>-launch/queries-with-controls.faa
#
# What it does:
#   1. Builds (or reuses) a DIAMOND DB from the species proteome
#   2. cblaster search: query enzyme set vs the DB; --max_distance 50000 / --min_hits 3
#   3. cblaster extract: per-cluster GenBank slices
#   4. clinker: synteny SVG + interactive HTML
#
# Output: .runtime/campaign-<species>-summary/superpowers/cblaster/

set -euo pipefail

# --- Tool availability -------------------------------------------------------
for tool in cblaster clinker; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: '$tool' not installed." >&2
    echo "       Run: bash tools/recommended/install-cheap.sh" >&2
    echo "       Or:  pip install \"cblaster>=1.4.0\" \"clinker>=0.0.32\"" >&2
    exit 127
  fi
done

# --- Args --------------------------------------------------------------------
SPECIES="${1:-}"
if [[ -z "$SPECIES" ]]; then
  echo "Usage: run-cblaster.sh <species> [query.faa]" >&2
  echo "  species: coptis | houttuynia | stephania | phellodendron" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/-summary"
PROTEOME="${SUMMARY_DIR}/proteome.faa"
QUERY_FASTA="${2:-${REPO_ROOT}/.runtime/<species>-launch/queries-with-controls.faa}"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/cblaster"

if [[ ! -f "$PROTEOME" ]]; then
  echo "ERROR: proteome not found: $PROTEOME" >&2
  exit 65
fi
if [[ ! -f "$QUERY_FASTA" ]]; then
  echo "ERROR: query FASTA not found: $QUERY_FASTA" >&2
  exit 65
fi

mkdir -p "$OUTPUT_DIR" "${OUTPUT_DIR}/clusters"

# --- 1. DIAMOND DB build (idempotent) ----------------------------------------
DB_PATH="${OUTPUT_DIR}/${SPECIES}.dmnd"
if [[ ! -f "$DB_PATH" ]]; then
  echo "[1/4] Building DIAMOND DB for ${SPECIES}..."
  cblaster makedb "$PROTEOME" "${OUTPUT_DIR}/${SPECIES}"
else
  echo "[1/4] DIAMOND DB present: $DB_PATH"
fi

# --- 2. cblaster search ------------------------------------------------------
echo "[2/4] cblaster search (query=$QUERY_FASTA)..."
cblaster search \
  --query_file "$QUERY_FASTA" \
  --mode local \
  --database "$DB_PATH" \
  --max_distance 50000 \
  --min_hits 3 \
  --output "${OUTPUT_DIR}/bia-clusters.csv" \
  --plot "${OUTPUT_DIR}/bia-clusters.html"

# --- 3. cblaster extract -----------------------------------------------------
echo "[3/4] cblaster extract, per-cluster GenBank slices..."
cblaster extract \
  --query "${OUTPUT_DIR}/bia-clusters.csv" \
  --output "${OUTPUT_DIR}/clusters" \
  --format genbank

# --- 4. clinker SVG + HTML ---------------------------------------------------
echo "[4/4] clinker, synteny SVG + interactive HTML..."
shopt -s nullglob
gbks=( "${OUTPUT_DIR}/clusters"/*.gbk )
if (( ${#gbks[@]} == 0 )); then
  echo "WARN: no GenBank slices produced; clinker step skipped." >&2
else
  clinker "${gbks[@]}" \
    --output_html "${OUTPUT_DIR}/clinker.html" \
    --output_svg "${OUTPUT_DIR}/clinker.svg"
fi

echo
echo "DONE: cblaster + clinker on ${SPECIES}"
echo "  Output: $OUTPUT_DIR"
echo "  Tip: open ${OUTPUT_DIR}/clinker.html"
