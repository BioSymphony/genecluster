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

PLANTISMASH_REF="${PLANTISMASH_REF:?Set PLANTISMASH_REF to the reviewed plantiSMASH commit SHA}"
PLANTISMASH_SRC="${DB_DIR}/plantismash-src/${PLANTISMASH_REF}"
if [[ ! -d "${PLANTISMASH_SRC}/.git" ]]; then
 mkdir -p "$(dirname "$PLANTISMASH_SRC")"
 git clone --filter=blob:none https://github.com/plantismash/plantismash.git "$PLANTISMASH_SRC"
fi
git -C "$PLANTISMASH_SRC" fetch --depth 1 origin "$PLANTISMASH_REF"
git -C "$PLANTISMASH_SRC" checkout --detach FETCH_HEAD

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
 MIBIG_SHA256="${MIBIG_SHA256:?Set MIBIG_SHA256 to the published archive SHA-256}"
 TMP_TAR="$(mktemp -t mibig.XXXXXX.tar.gz)"
 curl -fsSL -o "$TMP_TAR" "$MIBIG_URL"
 verify_sha256 "$MIBIG_SHA256" "$TMP_TAR"
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
