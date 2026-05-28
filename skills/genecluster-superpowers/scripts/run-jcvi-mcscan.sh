#!/usr/bin/env bash
# run-jcvi-mcscan.sh: pairwise macro-synteny ribbons between two atlas species
#
# STATUS: foundation, not yet tested in production
# Required tools: python3 with jcvi installed; lastdb
# Install: pip install "jcvi>=1.6.5"
#          conda install -c bioconda last
#       (or run tools/recommended/install-cheap.sh)
#
# Usage:
#   run-jcvi-mcscan.sh <species_a> <species_b>
#
# Each species ∈ { coptis, houttuynia, stephania, phellodendron }.
#
# What it does:
#   1. GFF → JCVI BED for each species (uses .runtime/campaign-<sp>-summary/genomic.gff)
#   2. Stages CDS via symlink (uses proteome.faa as the operational stand-in;
#      JCVI accepts protein FASTA when CDS is absent, with a warning)
#   3. python -m jcvi.compara.catalog ortholog (LAST + MCScan)
#   4. python -m jcvi.graphics.synteny: ribbon PDF
#
# Output: .runtime/<jcvi-synteny>/<species_a>-vs-<species_b>/

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
  echo "  Each ∈ { coptis, houttuynia, stephania, phellodendron }" >&2
  exit 64
fi
if [[ "$SPECIES_A" == "$SPECIES_B" ]]; then
  echo "ERROR: species_a and species_b must differ." >&2
  exit 64
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUM_A="${REPO_ROOT}/.runtime/-summary"
SUM_B="${REPO_ROOT}/.runtime/-summary"
GFF_A="${SUM_A}/genomic.gff"
GFF_B="${SUM_B}/genomic.gff"
CDS_A="${SUM_A}/proteome.faa"     # stand-in; see header note
CDS_B="${SUM_B}/proteome.faa"

for f in "$GFF_A" "$GFF_B" "$CDS_A" "$CDS_B"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: required input not found: $f" >&2
    exit 65
  fi
done

OUTPUT_DIR="${REPO_ROOT}/.runtime/<jcvi-synteny>/${SPECIES_A}-vs-${SPECIES_B}"
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
echo "DONE: jcvi MCScan ${SPECIES_A} vs ${SPECIES_B}"
echo "  Output: $OUTPUT_DIR"
echo "  Edit seqids.txt / layout.txt to refine the figure."
