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
# Foundation only: running this is safe but the artifacts are not yet wired
# into pipeline/genecluster_annotation_direct/.

set -euxo pipefail

OS="$(uname -s)"
ARCH="$(uname -m)"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS_DIR="${REPO_ROOT}/tools/recommended"
DB_DIR="${REPO_ROOT}/.runtime/databases"
mkdir -p "$DB_DIR" "${TOOLS_DIR}/foldseek/bin"

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
 curl -fsSL -o "$TMP_TAR" "$URL"
 tar xzf "$TMP_TAR" -C "${TOOLS_DIR}/foldseek/" --strip-components=1
 rm -f "$TMP_TAR"
fi
export PATH="${TOOLS_DIR}/foldseek/bin:${PATH}"

############################################################
# 2. ProstT5 dependencies + cache the HF model once
############################################################
python3 -m pip install --upgrade "torch>=2.1" "transformers>=4.40" "sentencepiece"
python3 - <<'PY'
from transformers import T5Tokenizer, T5EncoderModel
T5Tokenizer.from_pretrained("Rostlab/ProstT5")
T5EncoderModel.from_pretrained("Rostlab/ProstT5")
print("ProstT5 cached.")
PY

############################################################
# 3. CLEAN (Yu Science 2023)
############################################################
CLEAN_DIR="${TOOLS_DIR}/clean-hit-ec/src/CLEAN"
if [[ ! -d "$CLEAN_DIR" ]]; then
 mkdir -p "${TOOLS_DIR}/clean-hit-ec/src"
 git clone --depth 1 https://github.com/tttianhao/CLEAN.git "$CLEAN_DIR"
 (
 cd "$CLEAN_DIR"
 if [[ ! -d esm ]]; then
 git clone --depth 1 https://github.com/facebookresearch/esm.git
 fi
 python3 -m pip install --upgrade -r requirements.txt
 (cd esm && python3 -m pip install -e .)
 )
fi

############################################################
# 4. CLEAN-Contact (PNNL-CompBio Comm Biol 2024)
############################################################
CLEAN_CONTACT_DIR="${TOOLS_DIR}/clean-hit-ec/src/CLEAN-Contact"
if [[ ! -d "$CLEAN_CONTACT_DIR" ]]; then
 git clone --depth 1 https://github.com/PNNL-CompBio/CLEAN-Contact.git "$CLEAN_CONTACT_DIR"
fi

############################################################
# 5. Foldseek AFDB-SwissProt small target DB
############################################################
AFDB_DIR="${DB_DIR}/foldseek-afdb-swissprot"
if [[ ! -f "${AFDB_DIR}/.installed" ]]; then
 mkdir -p "$AFDB_DIR"
 pushd "$AFDB_DIR" >/dev/null
 foldseek databases Alphafold/Swiss-Prot afdb-swissprot tmp || true
 popd >/dev/null
 : > "${AFDB_DIR}/.installed"
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
