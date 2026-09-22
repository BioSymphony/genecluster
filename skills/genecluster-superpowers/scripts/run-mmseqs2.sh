#!/usr/bin/env bash
# run-mmseqs2.sh: run an MMseqs2 iterative-profile search against one proteome.
#
# MMseqs2 is an optional dependency. This wrapper only prepares sequence
# databases, runs the search, and writes a documented tabular result; it does
# not make an orthology call or compare the result with another search engine.

set -euo pipefail

SCRIPT_NAME="${0##*/}"
FORMAT_OUTPUT="query,target,evalue,bits,qaln,taln"

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} [options] <species-slug> [query.faa]
  ${SCRIPT_NAME} --species <species-slug> [options]

Run an MMseqs2 iterative-profile protein search against one target proteome.

Options:
  --species SLUG       Species or dataset slug. Letters, numbers, '.', '_' and
                       '-' are allowed; the first character must be alphanumeric.
  --query FASTA        Query protein FASTA (legacy positional query is supported).
  --target FASTA       Target protein FASTA (aliases: --proteome, --target-fasta).
  --out-dir DIR        Directory for databases, temporary files, and output
                       (alias: --output-dir).
  --threads N          Number of MMseqs2 CPU threads (default: 8).
  -s, --sensitivity X  MMseqs2 search sensitivity (default: 7.5).
  -h, --help           Show this help and exit without checking for MMseqs2.

Defaults relative to this repository:
  query     .runtime/<species-slug>-launch/queries-with-controls.faa
  proteome  .runtime/campaign-<species-slug>-summary/proteome.faa
  output    .runtime/campaign-<species-slug>-summary/superpowers/mmseqs2/

Environment overrides (flags take precedence):
  MMSEQS_QUERY_FASTA, MMSEQS_PROTEOME (or MMSEQS_TARGET_FASTA),
  MMSEQS_OUTPUT_DIR, MMSEQS_THREADS, MMSEQS_SENSITIVITY.
  THREADS and SENSITIVITY remain accepted for compatibility.

Outputs:
  queries-vs-target.outfmt6       tab-separated columns:
                                  ${FORMAT_OUTPUT}
  queries-vs-target.schema.txt    the same comma-separated column list.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 64
}

# Parse options before checking command availability so --help is always useful
# on a machine that does not have the optional MMseqs2 dependency installed.
SPECIES=""
QUERY_FASTA_ARG=""
PROTEOME_ARG=""
OUTPUT_DIR_ARG=""
THREADS="${MMSEQS_THREADS:-${THREADS:-8}}"
SENSITIVITY="${MMSEQS_SENSITIVITY:-${SENSITIVITY:-7.5}}"
POSITIONAL=()

while (($# > 0)); do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --species)
      (($# >= 2)) || die "--species requires a value"
      SPECIES="$2"
      shift 2
      ;;
    --query|--query-fasta)
      (($# >= 2)) || die "$1 requires a FASTA path"
      QUERY_FASTA_ARG="$2"
      shift 2
      ;;
    --target|--proteome|--target-fasta)
      (($# >= 2)) || die "$1 requires a FASTA path"
      PROTEOME_ARG="$2"
      shift 2
      ;;
    --out-dir|--output-dir)
      (($# >= 2)) || die "$1 requires a directory path"
      OUTPUT_DIR_ARG="$2"
      shift 2
      ;;
    --threads)
      (($# >= 2)) || die "--threads requires a positive integer"
      THREADS="$2"
      shift 2
      ;;
    -s|--sensitivity)
      (($# >= 2)) || die "$1 requires a numeric value"
      SENSITIVITY="$2"
      shift 2
      ;;
    --)
      shift
      POSITIONAL+=("$@")
      break
      ;;
    -*)
      die "unknown option: $1 (use --help)"
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

if ((${#POSITIONAL[@]} > 0)); then
  [[ -z "$SPECIES" ]] || die "species was supplied both positionally and with --species"
  SPECIES="${POSITIONAL[0]}"
fi
if ((${#POSITIONAL[@]} > 1)); then
  [[ -z "$QUERY_FASTA_ARG" ]] || die "query FASTA was supplied both positionally and with --query"
  QUERY_FASTA_ARG="${POSITIONAL[1]}"
fi
((${#POSITIONAL[@]} <= 2)) || die "too many positional arguments (use --help)"
[[ -n "$SPECIES" ]] || die "a species or dataset slug is required (use --help)"

# Keep the slug a path component. This accepts arbitrary public species or
# dataset names while rejecting absolute paths, traversal, and shell syntax.
if [[ ! "$SPECIES" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  die "unsafe species slug '$SPECIES'; use letters, numbers, '.', '_' or '-'"
fi
[[ "$THREADS" =~ ^[1-9][0-9]*$ ]] || die "threads must be a positive integer: '$THREADS'"
[[ "$SENSITIVITY" =~ ^[0-9]+([.][0-9]+)?$ ]] || die "sensitivity must be numeric: '$SENSITIVITY'"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SUMMARY_DIR="${REPO_ROOT}/.runtime/campaign-${SPECIES}-summary"

if [[ -n "$QUERY_FASTA_ARG" ]]; then
  QUERY_FASTA="$QUERY_FASTA_ARG"
elif [[ -n "${MMSEQS_QUERY_FASTA:-}" ]]; then
  QUERY_FASTA="$MMSEQS_QUERY_FASTA"
else
  QUERY_FASTA="${REPO_ROOT}/.runtime/${SPECIES}-launch/queries-with-controls.faa"
fi

if [[ -n "$PROTEOME_ARG" ]]; then
  PROTEOME="$PROTEOME_ARG"
elif [[ -n "${MMSEQS_PROTEOME:-}" ]]; then
  PROTEOME="$MMSEQS_PROTEOME"
elif [[ -n "${MMSEQS_TARGET_FASTA:-}" ]]; then
  PROTEOME="$MMSEQS_TARGET_FASTA"
else
  PROTEOME="${SUMMARY_DIR}/proteome.faa"
fi

if [[ -n "$OUTPUT_DIR_ARG" ]]; then
  OUTPUT_DIR="$OUTPUT_DIR_ARG"
elif [[ -n "${MMSEQS_OUTPUT_DIR:-}" ]]; then
  OUTPUT_DIR="$MMSEQS_OUTPUT_DIR"
else
  OUTPUT_DIR="${SUMMARY_DIR}/superpowers/mmseqs2"
fi

ensure_output_dir_ready() {
  if [[ -e "$OUTPUT_DIR" && ! -d "$OUTPUT_DIR" ]]; then
    die "output path exists and is not a directory: $OUTPUT_DIR"
  fi
  if [[ -d "$OUTPUT_DIR" ]]; then
    local -a output_entries
    shopt -s nullglob dotglob
    output_entries=("$OUTPUT_DIR"/*)
    shopt -u nullglob dotglob
    ((${#output_entries[@]} == 0)) || die "output directory must be new or empty; refusing to reuse: $OUTPUT_DIR"
  fi
}

ensure_output_dir_ready

if ! command -v mmseqs >/dev/null 2>&1; then
  echo "ERROR: 'mmseqs' is not installed or not on PATH." >&2
  echo "       Install it separately, then rerun this wrapper." >&2
  exit 127
fi

[[ -f "$PROTEOME" ]] || die "target proteome FASTA not found: $PROTEOME"
[[ -f "$QUERY_FASTA" ]] || die "query FASTA not found: $QUERY_FASTA"

TMP_DIR="${OUTPUT_DIR}/tmp"
QUERY_DB="${OUTPUT_DIR}/queries.db"
TARGET_DB="${OUTPUT_DIR}/target.db"
RESULT_DB="${OUTPUT_DIR}/queries-vs-target.result"
OUTPUT_TSV="${OUTPUT_DIR}/queries-vs-target.outfmt6"
SCHEMA_FILE="${OUTPUT_DIR}/queries-vs-target.schema.txt"
mkdir -p "$TMP_DIR"

echo "[1/3] mmseqs createdb (queries + ${SPECIES} proteome)..."
mmseqs createdb "$QUERY_FASTA" "$QUERY_DB"
mmseqs createdb "$PROTEOME" "$TARGET_DB"

echo "[2/3] mmseqs search --num-iterations 3 -s ${SENSITIVITY} --threads ${THREADS}..."
mmseqs search \
  "$QUERY_DB" \
  "$TARGET_DB" \
  "$RESULT_DB" \
  "$TMP_DIR" \
  --num-iterations 3 \
  -a \
  -s "$SENSITIVITY" \
  --threads "$THREADS"

echo "[3/3] mmseqs convertalis (documented tabular output)..."
mmseqs convertalis \
  "$QUERY_DB" \
  "$TARGET_DB" \
  "$RESULT_DB" \
  "$OUTPUT_TSV" \
  --format-mode 0 \
  --format-output "$FORMAT_OUTPUT"

[[ -f "$OUTPUT_TSV" ]] || die "MMseqs2 did not create the expected output: $OUTPUT_TSV"
printf '%s\n' "$FORMAT_OUTPUT" > "$SCHEMA_FILE"

echo
echo "DONE: MMseqs2 iterative-profile search on ${SPECIES}"
echo "  Output: $OUTPUT_TSV"
echo "  Schema: $SCHEMA_FILE"
