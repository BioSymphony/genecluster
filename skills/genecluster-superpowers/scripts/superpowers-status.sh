#!/usr/bin/env bash
# superpowers-status.sh: entry point for "what tools do I have available?"
#
# STATUS: mirrors the canonical tool inventory
# Required tools: none (this is the audit)
#
# Prints a table of recommended-tool install status and version. No args.
# Reflects the canonical inventory; tools that print their own
# version do, tools that don't are checked by command/env presence.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# Helper: print one row. $1=tool name, $2=version (or ", "), $3=status, $4=install hint
row() {
 printf " %-18s %-20s %-12s %s\n" "$1" "$2" "$3" "$4"
}

# Helper: run a version probe; echo trimmed first line or ", "
ver() {
 local cmd="$1"; shift
 if ! command -v "$cmd" >/dev/null 2>&1; then echo ", "; return; fi
 # Run the version probe; tolerate non-zero exit (some tools print to stderr)
 "$@" 2>&1 | head -n1 | tr -d '\r' || echo "?"
}

echo
echo "BioSymphony GeneCluster, recommended tool status"
echo " (per docs/biosymphony-tooling-status.md)"
echo " repo: $REPO_ROOT"
echo
printf " %-18s %-20s %-12s %s\n" "Tool" "Version" "Status" "Install hint (if missing)"
echo " -----------------------------------------------------------------------------------------"

# Quarto: ADOPTED
if command -v quarto >/dev/null 2>&1; then
 row "quarto" "$(quarto --version 2>/dev/null || echo '?')" "ADOPTED" "✓"
else
 row "quarto" ", " "MISSING" "brew install quarto (or install-cheap.sh)"
fi

# cblaster
if command -v cblaster >/dev/null 2>&1; then
 row "cblaster" "$(cblaster --version 2>&1 | head -n1)" "available" "✓"
else
 row "cblaster" ", " "MISSING" "pip install cblaster (or install-cheap.sh)"
fi

# clinker
if command -v clinker >/dev/null 2>&1; then
 row "clinker" "$(clinker --version 2>&1 | head -n1)" "available" "✓"
else
 row "clinker" ", " "MISSING" "pip install clinker (or install-cheap.sh)"
fi

# JCVI (Python module)
if python3 -c "import jcvi" >/dev/null 2>&1; then
 jcvi_ver="$(python3 -c 'import jcvi; print(getattr(jcvi, "__version__", "?"))' 2>/dev/null || echo '?')"
 row "jcvi (mcscan)" "$jcvi_ver" "available" "✓"
else
 row "jcvi (mcscan)" ", " "MISSING" "pip install jcvi (or install-cheap.sh)"
fi

# LAST (jcvi alignment backend)
if command -v lastdb >/dev/null 2>&1; then
 row "last/lastdb" "$(lastdb --version 2>&1 | head -n1)" "available" "✓"
else
 row "last/lastdb" ", " "MISSING" "conda install -c bioconda last"
fi

# MMseqs2
if command -v mmseqs >/dev/null 2>&1; then
 row "mmseqs2" "$(mmseqs version 2>&1 | head -n1)" "available" "✓"
else
 row "mmseqs2" ", " "MISSING" "brew install mmseqs2 (or install-cheap.sh)"
fi

# Foldseek
if command -v foldseek >/dev/null 2>&1; then
 row "foldseek" "$(foldseek version 2>&1 | head -n1)" "available" "✓"
else
 row "foldseek" ", " "MISSING" "bash tools/recommended/install-heavy.sh"
fi

# ProstT5 (HF model cached)
if python3 -c "import torch, transformers" >/dev/null 2>&1; then
 trans_ver="$(python3 -c 'import transformers; print(transformers.__version__)' 2>/dev/null || echo '?')"
 row "prostt5 (deps)" "transformers $trans_ver" "available" "✓"
else
 row "prostt5 (deps)" ", " "MISSING" "bash tools/recommended/install-heavy.sh"
fi

# Docker (still useful for ad hoc containers)
if command -v docker >/dev/null 2>&1; then
 row "docker" "$(docker --version 2>&1 | head -n1)" "available" "✓"
else
 row "docker" ", " "MISSING" "Docker Desktop / docker.io"
fi

# plantiSMASH 2.0.4
if command -v plantismash >/dev/null 2>&1; then
 row "plantismash" "$(plantismash --help 2>&1 | head -n1)" "available" "✓"
elif command -v conda >/dev/null 2>&1 && conda env list | awk '{print $1}' | grep -qx plantismash; then
 row "plantismash" "conda env" "available" "✓"
elif command -v mamba >/dev/null 2>&1 && mamba env list | awk '{print $1}' | grep -qx plantismash; then
 row "plantismash" "mamba env" "available" "✓"
else
 row "plantismash" ", " "MISSING" "bash tools/recommended/install-medium.sh"
fi

# CLEAN clone
CLEAN_DIR="${REPO_ROOT}/tools/recommended/clean-hit-ec/src/CLEAN"
if [[ -d "$CLEAN_DIR" ]]; then
 row "clean (EC)" "clone present" "available" "✓"
else
 row "clean (EC)" ", " "MISSING" "bash tools/recommended/install-heavy.sh"
fi

# DIAMOND (used by cblaster + PMN-pathway scripts)
if command -v diamond >/dev/null 2>&1; then
 row "diamond" "$(diamond version 2>&1 | head -n1)" "available" "✓"
else
 row "diamond" ", " "MISSING" "conda install -c bioconda 'diamond>=2.1'"
fi

echo
echo " See: docs/biosymphony-tooling-status.md"
echo " skills/genecluster-superpowers/references/"
echo
