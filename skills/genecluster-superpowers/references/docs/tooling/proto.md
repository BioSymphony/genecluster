# Proto

**Status:** candidate design layer; reviewed from public sources.

Proto is Evo Design's framework for writing biological design programs. In BioSymphony, it fits after GeneCluster has a reviewed candidate map, when the next step is ranked sequence, construct, promoter, or protein-variant design.

## What It Adds

- `proto-language`: typed sequences, regions, constructs, generators, constraints, optimizers, and programs.
- `proto-tools`: shared Input / Config / Output wrappers for search, alignment, annotation, PLMs, structure prediction, scoring, and retrieval tools.
- Hosted MCP: agent access for tool discovery, schema inspection, runs, asset fetches, program validation, and metrics.

## Good Uses

- Turn open pathway questions into ranked design candidates.
- Standardize multi-tool design runs behind one export shape.
- Compare wrappers for BLAST, MMseqs2, MAFFT, Foldseek, TM-align, InterProScan, NCBI retrieval, Evo2, ESM-family models, Chai-1, Boltz-2, and interface scorers.
- Reuse the program vocabulary even when execution stays local or on a provider.

## BioSymphony Output Shape

```text
proto-design/
  proto-program.py
  proto-program-export/
  proto-design-candidates.tsv
  proto-constraint-scores.tsv
  proto-run-metadata.json
  validation-report.json
```

Record:

- package or API version
- local or hosted execution
- tools and models used
- input provenance
- candidate IDs, scores, thresholds, and ranks
- exported artifact hashes

## First Smoke

1. Use public toy inputs.
2. Run locally with runtime and cache paths outside git, or under ignored `.runtime/`.
3. Export results.
4. Convert the export into `proto-design-candidates.tsv`, `proto-constraint-scores.tsv`, and `proto-run-metadata.json`.
5. Check that credentials, model weights, raw inputs, and bulky outputs stayed out of the repo.

## Sources

- [Proto about](https://proto.evodesign.org/about)
- [Proto MCP introduction](https://proto.evodesign.org/docs/mcp/introduction)
- [Proto MCP setup](https://proto.evodesign.org/docs/mcp/setup)
- [`evo-design/proto-language`](https://github.com/evo-design/proto-language)
- [`evo-design/proto-tools`](https://github.com/evo-design/proto-tools)
- [`evo-design/proto-client`](https://github.com/evo-design/proto-client)
