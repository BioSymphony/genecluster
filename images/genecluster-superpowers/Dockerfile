# syntax=docker/dockerfile:1
#
# BioSymphony GeneCluster Superpowers image
# Extends the base genecluster-runner with the 8 free/open foundation tools
# from the superpower-discovery roadmap. See:
# docs/biosymphony-superpower-test-plan.md (Phase 0 image build spec)
# docs/biosymphony-genecluster-superpower-roadmap.md (verdict matrices)
#
# Architecture (heavy weights stay on volume, source bakes in):
#
# In image (~5-6 GB):
# - bioconda: foldseek, last/lastz (cheap layer)
# - pip in base env: cblaster, clinker, JCVI MCScan, igv-reports, transformers, torch
# - HIT-EC v2.0.0 source + model.ckpt (small)
# - CLEAN source in dedicated /opt/conda/envs/clean env (PyTorch 1.11 pinned)
# - plantiSMASH 2.0 source in dedicated /opt/conda/envs/plantismash env (HMMER+BLAST+...)
# - P450Rdb 4-file dataset (CSVs + FASTA, ~90 MB)
#
# On volume (pre-staged via separate dispatches before each test):
# - ProstT5 model (~3 GB) → <volume>/db-cache/prostt5/
# - CLEAN ESM-1b weights (~7 GB) → <volume>/db-cache/clean/esm1b/
# - CLEAN pretrained checkpoints → <volume>/db-cache/clean/pretrained/
# - AFDB-SwissProt foldseek DB (~50 GB) → <volume>/db-cache/foldseek/afdb-swissprot/
# - plantiSMASH 2.0 databases → <volume>/db-cache/plantismash/
#
# Verified upstream URLs:
# plantiSMASH 2.0.4: github.com/plantismash/plantismash (release plantismash-2.0.4)
# CLEAN: github.com/tttianhao/CLEAN (tag v1.0.1, MIT)
# HIT-EC: github.com/datax-lab/HIT-EC (tag v2.0.0, MIT)
# P450Rdb v2.0: cellknowledge.com.cn/p450rdb_v2 (4 files, CN-hosted)
# ProstT5: huggingface.co/Rostlab/ProstT5

ARG BASE_IMAGE=ghcr.io/biosymphony/genecluster-runner:v0.1
FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive

# Build args, override at build time if upstream changes.
ARG CLEAN_REPO_URL=https://github.com/tttianhao/CLEAN.git
ARG CLEAN_REPO_REF=v1.0.1
ARG PLANTISMASH_REPO_URL=https://github.com/plantismash/plantismash.git
ARG PLANTISMASH_REPO_REF=plantismash-2.0.4
ARG HIT_EC_REPO_URL=https://github.com/datax-lab/HIT-EC.git
ARG HIT_EC_REPO_REF=v2.0.0
ARG P450RDB_BASE_URL=https://www.cellknowledge.com.cn/p450rdb_v2/download

# ============================================================
# Cheap layer, bioconda installs (foldseek, last, lastz)
# ============================================================
RUN mamba install -y -n base \
 -c bioconda -c conda-forge \
 'foldseek>=10' \
 'last>=1500' \
 'lastz>=1.04' \
 'gcc_linux-64' \
 'gxx_linux-64' \
 && mamba clean -afy \
 && rm -rf /opt/conda/pkgs/*

# gcc_linux-64 installs as `x86_64-conda-linux-gnu-gcc`; symlink to plain gcc
# so pip-built C extensions (jcvi.assembly.chic etc.) find it.
RUN ln -sf /opt/conda/bin/x86_64-conda-linux-gnu-gcc /usr/local/bin/gcc \
 && ln -sf /opt/conda/bin/x86_64-conda-linux-gnu-g++ /usr/local/bin/g++ \
 && gcc --version | head -1

# ============================================================
# Cheap layer, pip installs in base env (modern PyTorch, used by HIT-EC + ProstT5)
# ============================================================
RUN pip install --no-cache-dir \
 'cblaster>=1.4' \
 'clinker>=0.0.32' \
 'jcvi>=1.6.5' \
 'igv-reports>=1.16.2' \
 'transformers>=4.40' \
 'huggingface_hub>=0.20' \
 'torch>=2.0' \
 'tokenizers>=0.15' \
 'sentencepiece>=0.1.99' \
 'gdown>=5.0'

# ============================================================
# HIT-EC v2.0.0 (datax-lab/HIT-EC, MIT)
# Pinned to Python 3.9 + torch 1.13 + pytorch-lightning 1.9, must run in
# isolated conda env, conflicts with base env's torch>=2.0 (used by ProstT5).
# Their requirements.txt has a bogus `python==3.9.16` line which is invalid
# for pip, strip it out before pip install.
# Runner scripts must call: conda run -n hit-ec python /opt/hit-ec/predict.py ...
# ============================================================
RUN mamba create -y -n hit-ec python=3.9.16 \
 && mamba install -y -n hit-ec -c conda-forge -c pytorch \
 'pytorch=1.13' \
 'numpy=1.23.5' \
 'scikit-learn=1.2.2' \
 'tqdm=4.65' \
 && mamba clean -afy \
 && git clone --depth 1 --branch ${HIT_EC_REPO_REF} ${HIT_EC_REPO_URL} /opt/hit-ec \
 && cd /opt/hit-ec \
 && grep -v '^python' requirements.txt > /tmp/hit-ec-reqs.txt \
 && /opt/conda/envs/hit-ec/bin/pip install --no-cache-dir -r /tmp/hit-ec-reqs.txt \
 && curl -fsSL -o /opt/hit-ec/model.ckpt \
 "https://github.com/datax-lab/HIT-EC/releases/download/${HIT_EC_REPO_REF}/model.ckpt"

# ============================================================
# CLEAN v1.0.1 (tttianhao/CLEAN)
# License: declared Apache-2.0 in setup.py classifier BUT ships
# "NON-EXCLUSIVE RESEARCH USE LICENSE FOR CLEAN SOFTWARE.pdf", research-use
# is the operative restriction. Atlas + manuscript use is fine; commercial
# embedding would need an upstream license dialogue.
# Pinned to PyTorch 1.x + fair-esm 2.0.0 + matplotlib 3.4.1 + pandas 1.4.2
# (per repo-root requirements.txt), runs in dedicated /opt/conda/envs/clean.
# ESM-1b weights (~7 GB) + pretrained checkpoint (gdown) NOT baked into image;
# pre-stage to volume at Phase 6.0.
# Runner scripts: `conda run -n clean python -m CLEAN.inference ...`
# ============================================================
RUN mamba create -y -n clean python=3.10 \
 && mamba install -y -n clean -c conda-forge -c pytorch \
 'pytorch>=1.11,<1.14' \
 'numpy>=1.22,<2' \
 'pandas>=1.4,<2.2' \
 'scikit-learn>=1.0,<1.4' \
 'scipy>=1.7,<1.12' \
 'matplotlib>=3.4,<3.9' \
 'tqdm>=4.64' \
 && mamba clean -afy \
 && git clone --depth 1 --branch ${CLEAN_REPO_REF} ${CLEAN_REPO_URL} /opt/CLEAN \
 && /opt/conda/envs/clean/bin/pip install --no-cache-dir 'fair-esm>=2.0,<3' \
 && cd /opt/CLEAN \
 && /opt/conda/envs/clean/bin/python build.py install

# ============================================================
# plantiSMASH 2.0.4 (plantismash/plantismash, AGPL-3.0+)
# Has its own conda env (HMMER 3+2, BLAST+, DIAMOND, MUSCLE, FastTree, Prodigal, CD-HIT, pplacer).
# Databases pre-staged to volume; source + env baked in.
# Runner script must `conda run -n plantismash plantismash ...`.
# Note: AGPL is copyleft, atlas hosting must not expose plantiSMASH as a service without source.
# Use non-editable install: straight.plugin does filesystem discovery and can
# miss plugins under modern editable installs.
# ============================================================
RUN git clone --depth 1 --branch ${PLANTISMASH_REPO_REF} ${PLANTISMASH_REPO_URL} /opt/plantismash \
 && mamba env create -f /opt/plantismash/environment.yml -n plantismash \
 && mamba clean -afy \
 && /opt/conda/envs/plantismash/bin/pip install --no-cache-dir /opt/plantismash \
 && /opt/conda/envs/plantismash/bin/python -c "from straight.plugin import load; plugins=list(load('antismash.specific_modules')); assert plugins, 'empty plantiSMASH plugin list'; print('plantismash plugins', len(plugins))"

# ============================================================
# P450Rdb v2.0 (cellknowledge.com.cn, academic-CC-BY-4.0)
# 4 separate downloads with %20 URL-encoded spaces.
# CN host: download speed varies from non-China RunPod regions.
# ============================================================
RUN mkdir -p /opt/p450rdb \
 && cd /opt/p450rdb \
 && curl -fL --retry 3 --connect-timeout 30 -o reactions.csv \
 "${P450RDB_BASE_URL}/1.%20Reactions.CSV" \
 && curl -fL --retry 3 --connect-timeout 30 -o p450s.csv \
 "${P450RDB_BASE_URL}/2.%20P450s.CSV" \
 && curl -fL --retry 3 --connect-timeout 30 -o compounds.csv \
 "${P450RDB_BASE_URL}/3.%20Compounds.CSV" \
 && curl -fL --retry 3 --connect-timeout 30 -o sequences.fasta \
 "${P450RDB_BASE_URL}/Sequence.fasta" \
 && wc -l *.csv && head -1 sequences.fasta

# ============================================================
# Verify, every tool resolves; pre-stage paths exist; image ready for smoke-pod
# ============================================================
RUN command -v cblaster && cblaster --version 2>&1 | head -1 \
 && command -v clinker && clinker --version 2>&1 | head -1 \
 && command -v foldseek && foldseek version 2>&1 | head -1 \
 && command -v lastz \
 && command -v last-train \
 && python -c "import jcvi; print('jcvi OK')" \
 && python -c "import torch; print(f'torch {torch.__version__}')" \
 && python -c "import transformers; print(f'transformers {transformers.__version__}')" \
 && python -c "from huggingface_hub import snapshot_download; print('huggingface_hub OK')" \
 && test -f /opt/hit-ec/model.ckpt || (echo "FAIL: HIT-EC weights missing" && exit 1) \
 && /opt/conda/envs/hit-ec/bin/python -c "import torch; assert torch.__version__.startswith('1.13'), f'HIT-EC env torch={torch.__version__} not 1.13'" \
 && test -d /opt/CLEAN || (echo "FAIL: CLEAN missing" && exit 1) \
 && /opt/conda/envs/clean/bin/python -c "import torch; assert torch.__version__.startswith('1.'), f'CLEAN env torch={torch.__version__} not 1.x'" \
 && /opt/conda/envs/clean/bin/python -c "import CLEAN; print('CLEAN module import OK')" \
 && test -d /opt/plantismash || (echo "FAIL: plantiSMASH missing" && exit 1) \
 && /opt/conda/envs/plantismash/bin/python -c "import sys; print(f'plantismash env python={sys.version}')" \
 && test -f /opt/p450rdb/reactions.csv || (echo "FAIL: P450Rdb missing" && exit 1) \
 && test -f /opt/p450rdb/sequences.fasta || (echo "FAIL: P450Rdb sequences missing" && exit 1)

WORKDIR /workspace
CMD ["/bin/bash", "-l"]
