#!/usr/bin/env bash
# Draft wrapper for plantiSMASH 2.0.4.
# Usage: run-plantismash.sh <species>
# Stage matching genomic.fna and genomic.gff in
# .runtime/campaign-<species>-summary/. Check reference IDs and CDS phase.
# Reports and candidate regions go under superpowers/plantismash/.
# Install: bash tools/recommended/install-medium.sh

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
GENOME_FASTA="${SUMMARY_DIR}/genomic.fna"
GENOME_GFF="${SUMMARY_DIR}/genomic.gff"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/plantismash"

if [[ ! -f "$GENOME_FASTA" || ! -f "$GENOME_GFF" ]]; then
  printf 'ERROR: plantiSMASH needs matching input files: %s and %s\n' "$GENOME_FASTA" "$GENOME_GFF" >&2
  exit 65
fi

mkdir -p "$OUTPUT_DIR"

# --- Run ---------------------------------------------------------------------
echo "[1/1] plantiSMASH 2.0.4 on ${SPECIES}..."
"${PLANTISMASH_CMD[@]}" \
  --taxon plants \
  --genefinding none \
  --gff3 "$GENOME_GFF" \
  --outputfolder "$OUTPUT_DIR" \
  "$GENOME_FASTA"

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
