# MMseqs2

The local wrapper passed a synthetic protein-search fixture with release 18-8cc5c. It returned the three expected exact matches and excluded the unrelated control. [MMseqs2 18-8cc5c](https://github.com/soedinglab/MMseqs2/releases/tag/18-8cc5c)

MMseqs2 provides fast sequence and profile search for large public protein sets. It can extend candidate discovery beyond a single BLAST pass while retaining tabular evidence for review.

## Calling Wrapper

The wrapper accepts explicit query, target, and output paths. It exports `query,target,evalue,bits,qaln,taln` as tab-separated columns with a schema sidecar. [Calling guide](tool-chaining.md#search-proteins)

## Native CLI Pattern

```bash
mmseqs createdb <QUERY_FASTA> <QUERY_DB>
mmseqs createdb <TARGET_FASTA> <TARGET_DB>
mmseqs search <QUERY_DB> <TARGET_DB> <RESULT_DB> <TMP_DIR> --num-iterations 3 -a
mmseqs convertalis <QUERY_DB> <TARGET_DB> <RESULT_DB> <OUTPUT_TSV> \
  --format-output query,target,evalue,bits,qaln,taln
```

Use `-a` to retain the alignment backtraces required by `qaln` and `taln`. Set sensitivity, coverage, identity, and target limits explicitly for the campaign. [MMseqs2 user guide](https://github.com/soedinglab/MMseqs2/wiki)

## Output contract

Record input accessions and hashes, MMseqs2 version, database build commands, search parameters, output schema, tabular results, and hashes. Keep large indexes in ignored runtime or external storage.

Treat sequence hits as homology evidence. Check function and cluster placement separately.
