#!/usr/bin/env bash
# run-plantismash.sh: plantiSMASH 2.0.4 against one atlas species
#
# STATUS: validated on RunPod through the BioSymphony v7 boot recipe
# Required tools: plantiSMASH 2.0.4 command or conda env named plantismash
# Install: bash tools/recommended/install-medium.sh
#
# Usage:
#   run-plantismash.sh <species>
#
# <species> = coptis | houttuynia | stephania | phellodendron
#
# What it does:
#   Runs plantiSMASH 2.0.4 against the species genomic.gff (motif-driven BGC
#   detection: 12 BGC types incl. BIA / terpene / saccharide). Produces
#   GenBank region records and an interactive HTML report. Compare against our
#   anchor-windowed cluster_neighborhoods.tsv to find motif-driven clusters
#   our anchor pipeline missed.
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
  echo "  species: coptis | houttuynia | stephania | phellodendron" >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/-summary"
GENOME_GFF="${SUMMARY_DIR}/genomic.gff"
OUTPUT_DIR="${SUMMARY_DIR}/superpowers/plantismash"

if [[ ! -f "$GENOME_GFF" ]]; then
  echo "ERROR: genomic.gff not found: $GENOME_GFF" >&2
  exit 65
fi

mkdir -p "$OUTPUT_DIR"

# --- Run ---------------------------------------------------------------------
echo "[1/1] plantiSMASH 2.0.4 on ${SPECIES}..."
"${PLANTISMASH_CMD[@]}" \
  --taxon plants \
  --genefinding-tool none \
  --outputfolder "$OUTPUT_DIR" \
  "$GENOME_GFF"

echo
if compgen -G "${OUTPUT_DIR}/*.gbk" >/dev/null; then
  echo "plantiSMASH GenBank output: present"
else
  echo "WARN: no GenBank output found in ${OUTPUT_DIR}." >&2
fi

echo
echo "DONE: plantiSMASH 2.0.4 on ${SPECIES}"
echo "  Output: ${OUTPUT_DIR}/"
echo "  Tip: open ${OUTPUT_DIR}/index.html"
echo "  Coordinate-overlap-join output regions with cluster_neighborhoods.tsv"
echo "  to find motif-driven clusters anchor-windowing missed."
