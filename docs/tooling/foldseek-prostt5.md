# Foldseek + ProstT5: integration plan for BioSymphony GeneCluster

**Status:** validated; upstream Foldseek release 10-941cd33 confirmed current in the latest audit.
**Priority:** ★4. cross-species evidence layer
**Endorsed by:** sequence/structure tool survey (solo, but high-impact)

## Purpose

Foldseek (Steinegger lab, *Nat Biotech* 2024) does fast structure-based homology search. ProstT5 (Heinzinger 2024 *NAR Genomics*) is a bilingual sequence-and-3Di-token language model that lets Foldseek operate from sequence alone, no AlphaFold step needed. The combination catches convergent enzymes invisible to BLAST: same fold, <15% sequence identity, different family. Convergent-enzyme cases (one enzyme family substituting for another that catalyzes the same reaction) are the regime where Foldseek wins.

## What it adds to a comparative atlas

When a headline question is convergent biosynthesis (different enzyme families catalyzing the same reaction), BLAST and HMMER both fail at <20% identity. Foldseek + ProstT5 is the only tool that can support a "fold-level convergence" claim. Adding it lifts a comparative survey toward a convergence analysis with structural evidence.

## Install

```bash
# Foldseek: prebuilt binaries (fastest path)
# macOS (universal, includes Apple Silicon)
wget https://mmseqs.com/foldseek/foldseek-osx-universal.tar.gz
tar xvzf foldseek-osx-universal.tar.gz
export PATH="$(pwd)/foldseek/bin:$PATH"

# Linux AVX2
# wget https://mmseqs.com/foldseek/foldseek-linux-avx2.tar.gz
# tar xvzf foldseek-linux-avx2.tar.gz

# Or via bioconda
conda install -c bioconda "foldseek>=10"

# ProstT5 model (download once; cached by transformers)
pip install "torch>=2.1" "transformers>=4.40" "sentencepiece"
python -c "from transformers import T5Tokenizer, T5EncoderModel; \
 T5Tokenizer.from_pretrained('Rostlab/ProstT5'); \
 T5EncoderModel.from_pretrained('Rostlab/ProstT5')"

# Verify
foldseek version
```

## Sample CLI: running on our existing data

```bash
# Convert candidates to 3Di via ProstT5 and search against AFDB-Plants subset
mkdir -p .runtime/foldseek-out

# 1. Build a target DB from a reference (start with AFDB-SwissProt; AFDB-Plants ~350 GB later)
foldseek databases Alphafold/Swiss-Prot afdb-swissprot tmp

# 2. Sequence-only search via ProstT5 (Foldseek encodes our queries to 3Di internally)
foldseek easy-search \
 .runtime/<species>-summary/cluster-candidates.faa \
 afdb-swissprot \
 .runtime/foldseek-out/stephania-vs-afdb.m8 \
 tmp \
 --prostt5-model Rostlab/ProstT5 \
 --threads 8 \
 --format-output query,target,evalue,bits,prob,alntmscore
```

## Integration point in our pipeline

- New stage in `pipeline/genecluster_annotation_direct/run.py` (gated on flag `--enable-foldseek`): run Foldseek easy-search on cluster-candidate proteins missed by BLAST/hmmscan.
- New enrichment module: ``pipeline/genecluster_annotation_direct/`` parsing the `.m8` output into per-protein `tm_top_hit`, `tm_score`, `tm_evalue`.
- Postprocess: new sheet `structure-foldseek` in the per-species xlsx; flag rows where Foldseek hit ≠ BLAST hit (the convergence cases).
- Quarto: cross-species page `convergence-evidence.qmd` listing fold-homology-but-no-sequence-homology cases.

## Estimated integration cost

5-7 days focused (this is the heaviest add).
- Day 1: Local Foldseek + ProstT5 install validated on a 10-protein test set.
- Day 2: Pick target DB strategy (AFDB-SwissProt small / AFDB-Plants 350 GB / EBI Foldseek server).
- Day 3-4: Wire `easy-search` into run.py; parse `.m8` into enrichment TSV.
- Day 5: Postprocess xlsx integration; flag the convergence cases.
- Day 6-7: Cross-species convergence page in Quarto + manuscript-figure styling.

## Open questions / decisions to make before integrating

- Local AFDB-Plants (~350 GB) vs EBI Foldseek server (no disk, slower, throttled)?
- Apple Silicon: does ProstT5 run via Metal (`-mps`) acceptably without an NVIDIA GPU?
- Threshold for "convergence call": probability + TM-score combination, or just TM ≥ 0.5?
- Do we deposit AlphaFold structures of our candidates to PDB / Zenodo as a manuscript bonus?

## Citations

- Foldseek *Nat Biotech* 2024: https://www.nature.com/articles/s41587-023-01773-0
- Foldseek GitHub: https://github.com/steineggerlab/foldseek
- ProstT5 *NAR Genomics* 2024: https://academic.oup.com/nargab/article/6/4/lqae150/7901286
- ProstT5 GitHub: https://github.com/mheinzinger/ProstT5
- ProstT5 HF model card: https://huggingface.co/Rostlab/ProstT5
- AFDB plant download: https://alphafold.ebi.ac.uk/download
