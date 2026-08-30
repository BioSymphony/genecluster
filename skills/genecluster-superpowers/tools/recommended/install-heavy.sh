#!/usr/bin/env bash
# tools/recommended/install-heavy.sh
#
# Idempotent installer for heavy-tier tools recommended by the
# superpower roadmap: Expect tens of GB of disk and an optional
# GPU pass.
#
# - Foldseek 10 (structure-based search) binary
# - ProstT5 (sequence -> 3Di language model) HF cache
# - CLEAN (contrastive EC prediction) git + pip
# - CLEAN-Contact (structural EC variant) git
# - AFDB-SwissProt (Foldseek) (small structure target DB) foldseek databases
#
# AFDB-Plants (~350 GB) is INTENTIONALLY not auto-fetched here: see
# docs/tooling/foldseek-prostt5.md for the manual fetch plan once we commit
# to local plant-fold search.
#
# Review source versions, hashes, licenses, and storage needs before running.

set -euxo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS_DIR="${REPO_ROOT}/tools/recommended"
DB_DIR="${REPO_ROOT}/.runtime/databases"
mkdir -p "$DB_DIR" "${TOOLS_DIR}/foldseek/bin"

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
# 1. Foldseek prebuilt binary
############################################################
if ! command -v foldseek >/dev/null 2>&1 && [[ ! -x "${TOOLS_DIR}/foldseek/bin/foldseek" ]]; then
 if [[ "$OS" == "Darwin" ]]; then
 URL="https://mmseqs.com/foldseek/foldseek-osx-universal.tar.gz"
 elif [[ "$OS" == "Linux" && "$ARCH" == "x86_64" ]]; then
 URL="https://mmseqs.com/foldseek/foldseek-linux-avx2.tar.gz"
 else
 echo "ERROR: unsupported OS/arch ${OS} ${ARCH} for Foldseek prebuilt; build from source manually."
 exit 1
 fi
 TMP_TAR="$(mktemp -t foldseek.XXXXXX.tar.gz)"
 FOLDSEEK_SHA256="${FOLDSEEK_SHA256:?Set FOLDSEEK_SHA256 to the published archive SHA-256}"
 curl -fsSL -o "$TMP_TAR" "$URL"
 verify_sha256 "$FOLDSEEK_SHA256" "$TMP_TAR"
 tar xzf "$TMP_TAR" -C "${TOOLS_DIR}/foldseek/" --strip-components=1
 rm -f "$TMP_TAR"
fi
export PATH="${TOOLS_DIR}/foldseek/bin:${PATH}"

############################################################
# 2. ProstT5 dependencies + cache the HF model once
############################################################
python3 -m pip install --upgrade "torch>=2.1" "transformers>=4.40" "sentencepiece"
PROSTT5_REVISION="${PROSTT5_REVISION:?Set PROSTT5_REVISION to a reviewed immutable model revision}"
export PROSTT5_REVISION
python3 - <<'PY'
import os
from transformers import T5Tokenizer, T5EncoderModel
revision = os.environ["PROSTT5_REVISION"]
T5Tokenizer.from_pretrained("Rostlab/ProstT5", revision=revision)
T5EncoderModel.from_pretrained("Rostlab/ProstT5", revision=revision)
print("ProstT5 cached.")
PY

############################################################
# 3. CLEAN (Yu Science 2023)
############################################################
CLEAN_DIR="${TOOLS_DIR}/clean-hit-ec/src/CLEAN"
CLEAN_REF="${CLEAN_REF:?Set CLEAN_REF to a reviewed immutable commit SHA}"
ESM_REF="${ESM_REF:?Set ESM_REF to a reviewed immutable commit SHA}"
if [[ ! -d "$CLEAN_DIR" ]]; then
 mkdir -p "${TOOLS_DIR}/clean-hit-ec/src"
 git clone https://github.com/tttianhao/CLEAN.git "$CLEAN_DIR"
 (
 cd "$CLEAN_DIR"
 git checkout --detach "$CLEAN_REF"
 if [[ ! -d esm ]]; then
 git clone https://github.com/facebookresearch/esm.git
 git -C esm checkout --detach "$ESM_REF"
 fi
 python3 -m pip install --upgrade -r requirements.txt
 (cd esm && python3 -m pip install -e .)
 )
fi

############################################################
# 4. CLEAN-Contact (PNNL-CompBio Comm Biol 2024)
############################################################
CLEAN_CONTACT_DIR="${TOOLS_DIR}/clean-hit-ec/src/CLEAN-Contact"
CLEAN_CONTACT_REF="${CLEAN_CONTACT_REF:?Set CLEAN_CONTACT_REF to a reviewed immutable commit SHA}"
if [[ ! -d "$CLEAN_CONTACT_DIR" ]]; then
 git clone https://github.com/PNNL-CompBio/CLEAN-Contact.git "$CLEAN_CONTACT_DIR"
 git -C "$CLEAN_CONTACT_DIR" checkout --detach "$CLEAN_CONTACT_REF"
fi

############################################################
# 5. Foldseek AFDB-SwissProt small target DB
############################################################
AFDB_DIR="${DB_DIR}/foldseek-afdb-swissprot"
if [[ ! -f "${AFDB_DIR}/.installed" ]]; then
 echo "AFDB-SwissProt is not auto-fetched. Stage a versioned database, verify its manifest, then create ${AFDB_DIR}/.installed." >&2
fi

############################################################
# Verification
############################################################
echo "=========================================="
echo "Verifying installed versions"
echo "=========================================="
foldseek version || true
python3 -c "import torch, transformers; print('torch', torch.__version__, 'transformers', transformers.__version__)" || true
[[ -d "$CLEAN_DIR" ]] && echo "CLEAN clone: present" || echo "CLEAN clone: MISSING"
[[ -d "$CLEAN_CONTACT_DIR" ]] && echo "CLEAN-Contact clone: present" || echo "CLEAN-Contact clone: MISSING"
echo "AFDB-SwissProt dir: $(ls -1 "$AFDB_DIR" | wc -l) entries"
echo "install-heavy.sh: complete."
