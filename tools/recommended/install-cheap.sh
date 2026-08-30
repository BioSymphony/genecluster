#!/usr/bin/env bash
# tools/recommended/install-cheap.sh
#
# Idempotent installer for the cheap-tier tools recommended by the
# superpower roadmap:
#
# - cblaster >=1.4.0 (cluster homology search) pip; upstream 1.4.2 reviewed
# - clinker 0.0.32 (cluster comparison SVG) pip
# - JCVI >=1.6.5 + MCScan (macro-synteny ribbons) pip; upstream 1.6.6 reviewed
# - MMseqs2 18-8cc5c (iterative-profile BLAST replace) bioconda
# - igv-reports >=1.16.2 (analyst-friendly track HTML) pip; upstream 1.16.3 reviewed
# - Quarto 1.9.37 (report spine) .pkg / .deb
#
# Re-runnable: each step probes for an existing install before doing work.
# Local exploration only. Canonical bio-tool execution is cloud-first via
# RunPod images and dispatch scripts.

set -euxo pipefail

OS="$(uname -s)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

verify_sha256() {
 local expected="$1" file="$2" actual
 if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$file" | awk '{print $1}')"
 else
  actual="$(shasum -a 256 "$file" | awk '{print $1}')"
 fi
 [[ "$actual" == "$expected" ]] || { echo "ERROR: SHA-256 mismatch for $file" >&2; exit 1; }
}

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
 # Checked baseline. Confirm the published checksum before installation.
 QUARTO_VER="1.9.37"
 QUARTO_SHA256="${QUARTO_SHA256:?Set QUARTO_SHA256 to the published package SHA-256}"
 PKG_URL="https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VER}/quarto-${QUARTO_VER}-macos.pkg"
 TMP_PKG="$(mktemp -t quarto.XXXXXX.pkg)"
 curl -fsSL -o "$TMP_PKG" "$PKG_URL"
 verify_sha256 "$QUARTO_SHA256" "$TMP_PKG"
 sudo installer -pkg "$TMP_PKG" -target /
 rm -f "$TMP_PKG"
 else
 # Linux: .deb (or use the PyPI wrapper as a fallback)
 QUARTO_VER="1.9.37"
 QUARTO_SHA256="${QUARTO_SHA256:?Set QUARTO_SHA256 to the published package SHA-256}"
 DEB_URL="https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VER}/quarto-${QUARTO_VER}-linux-amd64.deb"
 TMP_DEB="$(mktemp -t quarto.XXXXXX.deb)"
 curl -fsSL -o "$TMP_DEB" "$DEB_URL"
 verify_sha256 "$QUARTO_SHA256" "$TMP_DEB"
 sudo dpkg -i "$TMP_DEB"
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
