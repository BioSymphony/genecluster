# Proto

**Status:** Planned. No public integration claim is made.

Proto is Evo Design's framework for biological design programs. It may fit after a GeneCluster campaign produces a reviewed candidate map. A later design stage could then rank sequences, constructs, promoters, or protein variants.

## Relevant components

- `proto-language` defines typed sequences, regions, constructs, generators, constraints, optimizers, and programs.
- `proto-tools` provides common input, configuration, and output wrappers for biological tools.
- The hosted MCP service provides tool discovery, schema inspection, runs, asset retrieval, program validation, and metrics.

## Possible uses

- Turn evidence gaps into ranked design candidates.
- Give multiple design tools a consistent output contract.
- Compare wrappers for search, alignment, annotation, protein-language models, structure prediction, scoring, and retrieval.
- Reuse the program vocabulary when execution remains local or runs on external compute.

## Proposed output contract

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
- candidate identifiers, scores, thresholds, and ranks
- artifact hashes

## Evaluation procedure

1. Use public or synthetic inputs.
2. Keep runtime files and caches outside Git or under ignored `.runtime/` storage.
3. Export the result.
4. Normalize the export to the proposed output contract.
5. Confirm that credentials, model weights, raw inputs, and heavy outputs remain outside the repository.

## Public sources

- [Proto overview](https://proto.evodesign.org/about)
- [Proto MCP introduction](https://proto.evodesign.org/docs/mcp/introduction)
- [Proto MCP setup](https://proto.evodesign.org/docs/mcp/setup)
- [`evo-design/proto-language`](https://github.com/evo-design/proto-language)
- [`evo-design/proto-tools`](https://github.com/evo-design/proto-tools)
- [`evo-design/proto-client`](https://github.com/evo-design/proto-client)
