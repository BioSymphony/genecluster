# Foldseek and ProstT5

**Status:** checked baseline Foldseek 10-941cd33; ProstT5 must be pinned to an immutable model revision.

Foldseek compares protein structures and ProstT5 can represent sequences in the 3Di alphabet. Together they can add a structure-oriented evidence channel when sequence similarity is weak.

## Reproducibility contract

Pin the Foldseek binary or image by version and hash. Pin the ProstT5 model to an immutable revision and record the model terms. Verify all downloaded archives and databases.

```bash
foldseek easy-search <QUERY> <TARGET_DB> <OUTPUT_TSV> <TMP_DIR> \
  --format-output query,target,evalue,bits,alntmscore
```

Use the current upstream help to select thresholds appropriate to the query and database.

## Output contract

Retain query and target identifiers, structure or model provenance, exact versions and revisions, command, thresholds, tabular output, database manifest, and hashes. Keep structures, model caches, and databases outside the repository.

Structural similarity supports a shared fold or possible mechanistic relationship; it does not establish substrate specificity or pathway membership by itself.

Sources: [Foldseek releases](https://github.com/steineggerlab/foldseek/releases) and [ProstT5](https://huggingface.co/Rostlab/ProstT5).
