#!/usr/bin/env bash
# Install missing tools for local use. See docs/biosymphony-tooling-status.md
# for upstream releases and replay baselines. For Quarto, set QUARTO_SHA256
# to the published hash for the package you install.

set -euxo pipefail

OS="$(uname -s)"

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
 python3 -m pip install "cblaster==1.4.0"
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
# 5. Quarto CLI
############################################################
if ! command -v quarto >/dev/null 2>&1; then
 QUARTO_VER="${QUARTO_VER:-1.11.9}"
 QUARTO_SHA256="${QUARTO_SHA256:?Set QUARTO_SHA256 to the published package SHA-256}"
 if [[ "$OS" == "Darwin" ]]; then
 PKG_URL="https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VER}/quarto-${QUARTO_VER}-macos.pkg"
 TMP_PKG="$(mktemp -t quarto.XXXXXX.pkg)"
 curl -fsSL -o "$TMP_PKG" "$PKG_URL"
 verify_sha256 "$QUARTO_SHA256" "$TMP_PKG"
 sudo installer -pkg "$TMP_PKG" -target /
 rm -f "$TMP_PKG"
 else
 # Linux x86-64 package.
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
