# MMseqs2 quickstart

**Status:** checked baseline 18-8cc5c.

```bash
mmseqs createdb <QUERY_FASTA> <QUERY_DB>
mmseqs createdb <TARGET_FASTA> <TARGET_DB>
mmseqs search <QUERY_DB> <TARGET_DB> <RESULT_DB> <TMP_DIR>
mmseqs convertalis <QUERY_DB> <TARGET_DB> <RESULT_DB> <OUTPUT_TSV>
```

Set sensitivity, coverage, identity, and target limits explicitly. Record input accessions and hashes, MMseqs2 version, database commands, search parameters, output schema, results, and hashes.

Keep large indexes outside the repository. A sequence hit supports homology, not a specific enzyme function or physical cluster without independent evidence.
