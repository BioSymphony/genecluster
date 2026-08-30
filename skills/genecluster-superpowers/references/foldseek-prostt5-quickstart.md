# Foldseek and ProstT5 quickstart

**Status:** checked Foldseek baseline 10-941cd33. Pin ProstT5 to an immutable model revision.

```bash
foldseek easy-search <QUERY> <TARGET_DB> <OUTPUT_TSV> <TMP_DIR> \
  --format-output query,target,evalue,bits,alntmscore
```

Verify the Foldseek archive or image, model revision, and target database manifest before use. Record query and target identifiers, structure or model provenance, exact versions, command, thresholds, outputs, and hashes.

Keep structures, model caches, and databases outside the repository. Structural similarity supports a shared fold or possible mechanistic relationship; it does not prove substrate specificity or pathway membership.
