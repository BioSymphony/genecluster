#!/usr/bin/env bash
# run-jcvi-mcscan.sh: pairwise macro-synteny ribbons between two atlas species
#
# STATUS: adaptation required; wrapper not tested. A JCVI tool baseline does
#         not certify this wrapper.
# ADAPTATION REQUIRED:
#   Replace the placeholder sequence paths with matching CDS FASTA files and
#   verify GFF identifiers, the BED conversion options, and the LAST/MCScan
#   commands against the pinned JCVI release before use. This script has no
#   public fixture or successful runtime contract.
# Required tools: python3 with jcvi installed; lastdb
# Install: pip install "jcvi>=1.6.5"
#          conda install -c bioconda last
#       (or run tools/recommended/install-cheap.sh)
#
# Usage:
#   run-jcvi-mcscan.sh <species_a> <species_b>
#
# Each argument is a species slug used by the campaign directory layout.
#
# What it does:
#   1. Reads each species' GFF and sequence inputs from its campaign directory.
#   2. Converts each GFF to JCVI BED and stages the sequence files.
#   3. python -m jcvi.compara.catalog ortholog (LAST + MCScan)
#   4. python -m jcvi.graphics.synteny: ribbon PDF
#
# Output: .runtime/jcvi-synteny/<species_a>-vs-<species_b>/

set -euo pipefail

# --- Tool availability -------------------------------------------------------
if ! python3 -c "import jcvi" >/dev/null 2>&1; then
  echo "ERROR: jcvi not installed." >&2
  echo "       Run: bash tools/recommended/install-cheap.sh" >&2
  echo "       Or:  pip install \"jcvi>=1.6.5\"" >&2
  exit 127
fi
if ! command -v lastdb >/dev/null 2>&1; then
  echo "ERROR: 'lastdb' not installed (LAST is jcvi's alignment backend)." >&2
  echo "       Run: conda install -c bioconda last" >&2
  exit 127
fi

# --- Args --------------------------------------------------------------------
SPECIES_A="${1:-}"
SPECIES_B="${2:-}"
if [[ -z "$SPECIES_A" || -z "$SPECIES_B" ]]; then
  echo "Usage: run-jcvi-mcscan.sh <species_a> <species_b>" >&2
  echo "  Each argument must name a species campaign directory" >&2
  exit 64
fi
if [[ "$SPECIES_A" == "$SPECIES_B" ]]; then
  echo "ERROR: species_a and species_b must differ." >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUM_A="${REPO_ROOT}/.runtime/campaign-${SPECIES_A}-summary"
SUM_B="${REPO_ROOT}/.runtime/campaign-${SPECIES_B}-summary"
GFF_A="${SUM_A}/genomic.gff"
GFF_B="${SUM_B}/genomic.gff"
CDS_A="${SUM_A}/proteome.faa"     # placeholder; replace with matching CDS FASTA
CDS_B="${SUM_B}/proteome.faa"     # placeholder; replace with matching CDS FASTA

for f in "$GFF_A" "$GFF_B" "$CDS_A" "$CDS_B"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: required input not found: $f" >&2
    exit 65
  fi
done

OUTPUT_DIR="${REPO_ROOT}/.runtime/jcvi-synteny/${SPECIES_A}-vs-${SPECIES_B}"
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# --- 1. GFF → BED ------------------------------------------------------------
echo "[1/3] GFF → JCVI BED for ${SPECIES_A}, ${SPECIES_B}..."
python3 -m jcvi.formats.gff bed --type=mRNA --key=ID \
  "$GFF_A" -o "${SPECIES_A}.bed"
python3 -m jcvi.formats.gff bed --type=mRNA --key=ID \
  "$GFF_B" -o "${SPECIES_B}.bed"

# --- 2. Stage CDS via symlink ------------------------------------------------
ln -sf "$CDS_A" "${SPECIES_A}.cds"
ln -sf "$CDS_B" "${SPECIES_B}.cds"

# --- 3. JCVI ortholog catalog (LAST + MCScan) --------------------------------
echo "[2/3] jcvi.compara.catalog ortholog ${SPECIES_A} ${SPECIES_B}..."
python3 -m jcvi.compara.catalog ortholog \
  "${SPECIES_A}" "${SPECIES_B}" \
  --no_strip_names

# --- 4. Synteny ribbon plot --------------------------------------------------
# seqids.txt + layout.txt are project-level; one-time hand edit per atlas.
# If absent, write minimal stubs and warn.
if [[ ! -f seqids.txt ]]; then
  echo "WARN: seqids.txt not found; writing all-chromosomes default. Edit before publishing." >&2
  awk '{print $1}' "${SPECIES_A}.bed" | sort -u | head -n 20 | paste -sd, - > seqids.txt
  awk '{print $1}' "${SPECIES_B}.bed" | sort -u | head -n 20 | paste -sd, - >> seqids.txt
fi
if [[ ! -f layout.txt ]]; then
  echo "WARN: layout.txt not found; writing minimal default. Edit before publishing." >&2
  cat > layout.txt <<EOF
# y, xstart, xend, rotation, color, label, va, bed
.6, .1, .9, 0, , ${SPECIES_A}, top, ${SPECIES_A}.bed
.4, .1, .9, 0, , ${SPECIES_B}, bottom, ${SPECIES_B}.bed
# edges
e, 0, 1, ${SPECIES_A}.${SPECIES_B}.lifted.anchors
EOF
fi

echo "[3/3] Render synteny ribbon PDF..."
python3 -m jcvi.graphics.synteny seqids.txt layout.txt \
  --outfile "${SPECIES_A}-vs-${SPECIES_B}-synteny.pdf"

echo
echo "ADAPTATION REQUIRED: inspect JCVI outputs before downstream use."
echo "  Output: $OUTPUT_DIR"
echo "  Edit seqids.txt / layout.txt to refine the figure."
