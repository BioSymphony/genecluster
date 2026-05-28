#!/usr/bin/env bash
# tools/recommended/install-medium.sh
#
# Idempotent installer for medium-weight tools recommended by the
# superpower roadmap:
#
# - plantiSMASH 2.0.4 (source + conda env; non-editable install)
# - MIBiG 4.0 BGC bundle (download to .runtime/databases/mibig-4)
#
# Re-runnable. Heavier than install-cheap.sh (a few GB on first run; mostly
# conda env and BGC archive). Local exploration only; canonical execution is
# cloud-first via RunPod images and dispatch scripts.

set -euxo pipefail

OS="$(uname -s)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_DIR="${REPO_ROOT}/.runtime/databases"
mkdir -p "$DB_DIR"

############################################################
# 1. plantiSMASH 2.0.4 via source + conda
############################################################
if command -v conda >/dev/null 2>&1; then
 CONDA_BIN="conda"
elif command -v mamba >/dev/null 2>&1; then
 CONDA_BIN="mamba"
else
 echo "ERROR: conda or mamba is required for plantiSMASH 2.0.4."
 exit 1
fi

PLANTISMASH_REF="${PLANTISMASH_REF:-plantismash-2.0.4}"
PLANTISMASH_SRC="${DB_DIR}/plantismash-src/${PLANTISMASH_REF}"
if [[ ! -d "${PLANTISMASH_SRC}/.git" ]]; then
 mkdir -p "$(dirname "$PLANTISMASH_SRC")"
 git clone --depth 1 --branch "$PLANTISMASH_REF" \
 https://github.com/plantismash/plantismash.git "$PLANTISMASH_SRC"
else
 git -C "$PLANTISMASH_SRC" fetch --tags --force origin "$PLANTISMASH_REF"
 git -C "$PLANTISMASH_SRC" checkout "$PLANTISMASH_REF"
fi

if ! "$CONDA_BIN" env list | awk '{print $1}' | grep -qx plantismash; then
 "$CONDA_BIN" env create -n plantismash -f "${PLANTISMASH_SRC}/environment.yml"
fi

# Use a normal install, not editable mode. straight.plugin performs filesystem
# discovery and can miss plugins under modern editable installs.
"$CONDA_BIN" run -n plantismash python -m pip install --upgrade "$PLANTISMASH_SRC"
"$CONDA_BIN" run -n plantismash python -c "from straight.plugin import load; plugins=list(load('antismash.specific_modules')); assert plugins, 'empty plantiSMASH plugin list'; print('plantiSMASH plugins', len(plugins))"

############################################################
# 2. MIBiG 4.0: curated reference BGCs
############################################################
MIBIG_DIR="${DB_DIR}/mibig-4"
if [[ ! -f "${MIBIG_DIR}/.installed" ]]; then
 mkdir -p "$MIBIG_DIR"
 # MIBiG 4.0 download URL (NAR Dec 2024)
 MIBIG_URL="https://dl.secondarymetabolites.org/mibig/mibig_json_4.0.tar.gz"
 TMP_TAR="$(mktemp -t mibig.XXXXXX.tar.gz)"
 curl -fsSL -o "$TMP_TAR" "$MIBIG_URL"
 tar xzf "$TMP_TAR" -C "$MIBIG_DIR"
 rm -f "$TMP_TAR"
 : > "${MIBIG_DIR}/.installed"
fi

############################################################
# Verification
############################################################
echo "=========================================="
echo "Verifying installed versions"
echo "=========================================="
"$CONDA_BIN" run -n plantismash plantismash --help >/dev/null && echo "plantiSMASH env: OK" || echo "plantiSMASH env: MISSING"
echo "MIBiG dir: $(ls -1 "$MIBIG_DIR" | wc -l) entries"
echo "install-medium.sh: complete."
