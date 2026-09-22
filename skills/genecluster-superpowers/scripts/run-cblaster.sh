#!/usr/bin/env bash
# Run a local cblaster search and turn its JSON session into clinker GenBank inputs.
#
# STATUS: foundation; wrapper contract tested with fake CLIs, biology unvalidated.
# Required tools: cblaster, clinker, diamond
# Install: pip install "cblaster>=1.4.0" "clinker>=0.0.32"
#
# Preferred interface:
#   run-cblaster.sh --organism LABEL --query QUERY_FASTA \
#     (--genbank ANNOTATED_GENOME | --database DB_PREFIX_OR_DMND) [options]
#
# Positional shorthand is also accepted as:
#   run-cblaster.sh LABEL QUERY_FASTA ANNOTATED_GENOME
#
# ANNOTATED_GENOME is a GenBank/EMBL file, or a GFF/GTF with a matching FASTA.
# A prepared database must have both DB_PREFIX.dmnd and DB_PREFIX.sqlite3.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  run-cblaster.sh --organism LABEL --query QUERY_FASTA \
    (--genbank ANNOTATED_GENOME | --database DB_PREFIX_OR_DMND) [options]

Options:
  --out-dir DIR          Output directory (default: .runtime/cblaster/LABEL)
  --gap BP               Maximum inter-hit gap (default: 50000)
  --min-hits N           Minimum cluster hits (default: 3)
  -h, --help             Show this help

The local route requires an annotated genome for database construction or a
prepared cblaster database pair (.dmnd plus sibling .sqlite3). A protein-only
FASTA cannot provide the genomic coordinates needed by extract_clusters.
USAGE
}

fail() {
  echo "ERROR: $1" >&2
  exit "${2:-64}"
}

ORGANISM=""
QUERY_FASTA=""
GENOME_FILE=""
DATABASE_INPUT=""
OUTPUT_DIR=""
MAX_GAP=50000
MIN_HITS=3
POSITIONAL=()

while (($# > 0)); do
  case "$1" in
    --organism)
      (($# >= 2)) || fail "--organism requires a value"
      ORGANISM="$2"
      shift 2
      ;;
    --query-file|--query)
      (($# >= 2)) || fail "$1 requires a value"
      QUERY_FASTA="$2"
      shift 2
      ;;
    --genbank|--genome|--annotated-genome)
      (($# >= 2)) || fail "$1 requires a value"
      GENOME_FILE="$2"
      shift 2
      ;;
    --database|--db)
      (($# >= 2)) || fail "$1 requires a value"
      DATABASE_INPUT="$2"
      shift 2
      ;;
    --out-dir|--output-dir)
      (($# >= 2)) || fail "$1 requires a value"
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --gap|--max-distance)
      (($# >= 2)) || fail "$1 requires a value"
      MAX_GAP="$2"
      shift 2
      ;;
    --min-hits)
      (($# >= 2)) || fail "--min-hits requires a value"
      MIN_HITS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while (($# > 0)); do
        POSITIONAL+=("$1")
        shift
      done
      ;;
    -*)
      fail "unknown option: $1"
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if ((${#POSITIONAL[@]} > 0)); then
  if ((${#POSITIONAL[@]} != 3)) || [[ -n "$ORGANISM$QUERY_FASTA$GENOME_FILE$DATABASE_INPUT" ]]; then
    fail "positional form requires LABEL QUERY_FASTA ANNOTATED_GENOME; use flags for a prepared database"
  fi
  ORGANISM="${POSITIONAL[0]}"
  QUERY_FASTA="${POSITIONAL[1]}"
  GENOME_FILE="${POSITIONAL[2]}"
fi

[[ -n "$ORGANISM" ]] || fail "missing --organism"
[[ "$ORGANISM" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || fail "organism label must be 1-64 safe letters, digits, dot, underscore, or hyphen"
[[ -n "$QUERY_FASTA" ]] || fail "missing --query"
[[ -f "$QUERY_FASTA" ]] || fail "query FASTA not found: $QUERY_FASTA" 65
[[ "$MAX_GAP" =~ ^[0-9]+$ ]] || fail "--gap must be a non-negative integer"
[[ "$MIN_HITS" =~ ^[1-9][0-9]*$ ]] || fail "--min-hits must be a positive integer"
if [[ -n "$GENOME_FILE" && -n "$DATABASE_INPUT" ]]; then
  fail "choose exactly one of --genbank or --database"
fi
if [[ -z "$GENOME_FILE" && -z "$DATABASE_INPUT" ]]; then
  fail "provide --genbank ANNOTATED_GENOME or --database DB_PREFIX_OR_DMND"
fi

if [[ -n "$GENOME_FILE" ]]; then
  [[ -f "$GENOME_FILE" ]] || fail "annotated genome not found: $GENOME_FILE" 65
  case "$GENOME_FILE" in
    *.gff|*.gff3|*.gtf|*.gff.gz|*.gff3.gz|*.gtf.gz)
      GFF_BASE="${GENOME_FILE%.gz}"
      GFF_BASE="${GFF_BASE%.*}"
      GFF_FASTA_FOUND=""
      for suffix in .fa .fsa .fna .fasta; do
        if [[ -f "${GFF_BASE}${suffix}" ]]; then
          GFF_FASTA_FOUND="${GFF_BASE}${suffix}"
          break
        fi
      done
      [[ -n "$GFF_FASTA_FOUND" ]] || fail "GFF/GTF input needs a matching FASTA beside: $GENOME_FILE" 65
      ;;
  esac
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="${REPO_ROOT}/.runtime/cblaster/${ORGANISM}"
fi
if [[ -e "$OUTPUT_DIR" ]]; then
  [[ -d "$OUTPUT_DIR" ]] || fail "output path is not a directory: $OUTPUT_DIR" 65
  if [[ -n "$(find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    fail "output directory is not empty; use a fresh --out-dir for each run: $OUTPUT_DIR" 65
  fi
fi
mkdir -p "$OUTPUT_DIR"

for tool in cblaster clinker diamond; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: '$tool' not installed; install cblaster, clinker, and DIAMOND before running." >&2
    exit 127
  fi
done

DB_PREFIX=""
DB_DMND=""
DB_SQLITE=""
if [[ -n "$GENOME_FILE" ]]; then
  DB_PREFIX="${OUTPUT_DIR}/${ORGANISM}"
  DB_DMND="${DB_PREFIX}.dmnd"
  DB_SQLITE="${DB_PREFIX}.sqlite3"
  if [[ ! -f "$DB_DMND" || ! -f "$DB_SQLITE" ]]; then
    echo "[1/4] Building cblaster database from annotated genome..."
    if [[ -e "$DB_DMND" || -e "$DB_SQLITE" ]]; then
      cblaster makedb "$GENOME_FILE" --name "$DB_PREFIX" --force
    else
      cblaster makedb "$GENOME_FILE" --name "$DB_PREFIX"
    fi
  else
    echo "[1/4] cblaster database present: $DB_PREFIX"
  fi
else
  case "$DATABASE_INPUT" in
    *.dmnd)
      DB_DMND="$DATABASE_INPUT"
      DB_PREFIX="${DATABASE_INPUT%.dmnd}"
      ;;
    *.sqlite3)
      DB_SQLITE="$DATABASE_INPUT"
      DB_PREFIX="${DATABASE_INPUT%.sqlite3}"
      DB_DMND="${DB_PREFIX}.dmnd"
      ;;
    *)
      DB_PREFIX="$DATABASE_INPUT"
      DB_DMND="${DB_PREFIX}.dmnd"
      DB_SQLITE="${DB_PREFIX}.sqlite3"
      ;;
  esac
  DB_SQLITE="${DB_PREFIX}.sqlite3"
fi
[[ -f "$DB_DMND" && -f "$DB_SQLITE" ]] || fail "cblaster database requires both $DB_DMND and $DB_SQLITE" 66

SESSION_JSON="${OUTPUT_DIR}/search-session.json"
SUMMARY_TSV="${OUTPUT_DIR}/clusters.tsv"
CBLASTER_HTML="${OUTPUT_DIR}/cblaster.html"
CLUSTERS_DIR="${OUTPUT_DIR}/clusters"
CLINKER_HTML="${OUTPUT_DIR}/clinker.html"
mkdir -p "$CLUSTERS_DIR"

echo "[2/4] cblaster search (organism=$ORGANISM query=$QUERY_FASTA)..."
cblaster search \
  --query_file "$QUERY_FASTA" \
  --mode local \
  --database "$DB_DMND" \
  --gap "$MAX_GAP" \
  --min_hits "$MIN_HITS" \
  --session_file "$SESSION_JSON" \
  --output "$SUMMARY_TSV" \
  --output_delimiter $'\t' \
  --plot "$CBLASTER_HTML"
[[ -f "$SESSION_JSON" ]] || fail "cblaster search did not write session JSON: $SESSION_JSON" 66

echo "[3/4] cblaster extract_clusters (session=$SESSION_JSON)..."
cblaster extract_clusters "$SESSION_JSON" \
  --output "$CLUSTERS_DIR" \
  --format genbank

echo "[4/4] clinker interactive HTML..."
shopt -s nullglob
gbks=("${CLUSTERS_DIR}"/*.gbk "${CLUSTERS_DIR}"/*.gb "${CLUSTERS_DIR}"/*.genbank)
if ((${#gbks[@]} == 0)); then
  echo "WARN: extract_clusters produced no GenBank files; clinker step skipped." >&2
else
  clinker "${gbks[@]}" --plot "$CLINKER_HTML"
fi

echo
echo "DONE: cblaster + clinker for ${ORGANISM}"
echo "  Output: $OUTPUT_DIR"
