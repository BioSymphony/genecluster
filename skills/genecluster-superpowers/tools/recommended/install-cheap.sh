#!/usr/bin/env bash
# tools/recommended/install-cheap.sh
#
# Idempotent installer for the cheap-tier tools recommended by the
# superpower roadmap:
#
# - cblaster 1.4.0 (cluster homology search) pip
# - clinker 0.0.32 (cluster comparison SVG) pip
# - JCVI 1.6.5 + MCScan (macro-synteny ribbons) pip
# - MMseqs2 18-8cc5c (iterative-profile BLAST replace) bioconda
# - igv-reports 1.16.2 (analyst-friendly track HTML) pip
# - Quarto 1.9.37 (report spine) .pkg / .deb
#
# Re-runnable: each step probes for an existing install before doing work.
# Local exploration only. Canonical bio-tool execution is cloud-first via
# RunPod images and dispatch scripts.

set -euxo pipefail

OS="$(uname -s)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

############################################################
# 1. cblaster + clinker via pip
############################################################
if ! command -v cblaster >/dev/null 2>&1; then
 python3 -m pip install --upgrade "cblaster>=1.4.0"
fi
if ! command -v clinker >/dev/null 2>&1; then
 python3 -m pip install --upgrade "clinker>=0.0.32"
fi

############################################################
# 2. JCVI (MCScan Python) via pip + bioconda for LAST/lastdb
############################################################
if ! python3 -c "import jcvi" >/dev/null 2>&1; then
 python3 -m pip install --upgrade "jcvi>=1.6.5"
fi

# LAST is the alignment backend for MCScan
if ! command -v lastdb >/dev/null 2>&1; then
 if command -v mamba >/dev/null 2>&1; then
 mamba install -y -c bioconda last
 elif command -v conda >/dev/null 2>&1; then
 conda install -y -c bioconda last
 else
 echo "WARNING: no conda/mamba available; install LAST manually for JCVI synteny."
 fi
fi

############################################################
# 3. MMseqs2 via bioconda (or homebrew on macOS)
############################################################
if ! command -v mmseqs >/dev/null 2>&1; then
 if [[ "$OS" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
 brew install mmseqs2
 elif command -v mamba >/dev/null 2>&1; then
 mamba install -y -c conda-forge -c bioconda "mmseqs2>=18"
 elif command -v conda >/dev/null 2>&1; then
 conda install -y -c conda-forge -c bioconda "mmseqs2>=18"
 else
 echo "WARNING: install MMseqs2 manually, no brew/conda/mamba detected."
 fi
fi

############################################################
# 4. igv-reports via pip
############################################################
if ! command -v create_report >/dev/null 2>&1; then
 python3 -m pip install --upgrade "igv-reports>=1.16.2"
fi

############################################################
# 5. Quarto 1.9 (CLI)
############################################################
if ! command -v quarto >/dev/null 2>&1; then
 if [[ "$OS" == "Darwin" ]]; then
 # macOS .pkg installer; pinned 1.9.37 (matches the version actually adopted)
 QUARTO_VER="1.9.37"
 PKG_URL="https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VER}/quarto-${QUARTO_VER}-macos.pkg"
 TMP_PKG="$(mktemp -t quarto.XXXXXX.pkg)"
 curl -fsSL -o "$TMP_PKG" "$PKG_URL"
 sudo installer -pkg "$TMP_PKG" -target /
 rm -f "$TMP_PKG"
 else
 # Linux: .deb (or use the PyPI wrapper as a fallback)
 QUARTO_VER="1.9.37"
 DEB_URL="https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VER}/quarto-${QUARTO_VER}-linux-amd64.deb"
 TMP_DEB="$(mktemp -t quarto.XXXXXX.deb)"
 curl -fsSL -o "$TMP_DEB" "$DEB_URL"
 sudo dpkg -i "$TMP_DEB" || python3 -m pip install --upgrade "quarto-cli==1.9.*"
 rm -f "$TMP_DEB"
 fi
fi

############################################################
# Verification
############################################################
echo "=========================================="
echo "Verifying installed versions"
echo "=========================================="
cblaster --version || true
clinker --version || true
python3 -c "import jcvi; print('jcvi', jcvi.__version__)" || true
mmseqs version || true
create_report --help >/dev/null 2>&1 && echo "igv-reports OK" || echo "igv-reports MISSING"
quarto --version || true
echo "install-cheap.sh: complete."
