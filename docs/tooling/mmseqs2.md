# MMseqs2

**Status:** checked baseline 18-8cc5c.

MMseqs2 provides fast sequence and profile search for large public protein sets. It can extend candidate discovery beyond a single BLAST pass while retaining tabular evidence for review.

## Calling Wrapper

The wrapper accepts explicit query, target, and output paths. See the [calling guide](tool-chaining.md#search-proteins) for a complete example and readiness. It exports `query,target,evalue,bits,qaln,taln` as tab-separated columns, with a schema sidecar. Its fake-CLI tests check command construction and error handling.

## Native CLI Pattern

```bash
mmseqs createdb <QUERY_FASTA> <QUERY_DB>
mmseqs createdb <TARGET_FASTA> <TARGET_DB>
mmseqs search <QUERY_DB> <TARGET_DB> <RESULT_DB> <TMP_DIR>
mmseqs convertalis <QUERY_DB> <TARGET_DB> <RESULT_DB> <OUTPUT_TSV>
```

Set sensitivity, coverage, identity, and target limits explicitly for the campaign.

## Output contract

Record input accessions and hashes, MMseqs2 version, database build commands, search parameters, output schema, tabular results, and hashes. Keep large indexes in ignored runtime or external storage.

A sequence hit supports homology, not a specific enzyme function or physical cluster, without independent evidence.

Source: [MMseqs2 releases](https://github.com/soedinglab/MMseqs2/releases).
