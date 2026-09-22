# Tool Evaluation Contract

Evaluate one missing capability against an existing baseline before adding a dependency. The [tooling radar](../biosymphony-next-tooling-radar.md) identifies candidates; the [status table](../biosymphony-tooling-status.md) records checked integrations.

## Evaluation Record

Keep one compact record with these fields:

| Field | Required evidence |
|---|---|
| Question | The campaign decision that this tool could improve |
| Sources | Official repository, paper, publication or release date, and retrieval date |
| Versions | Immutable code revision, model revision/hash, database release/hash, and environment lock or container digest |
| Terms | Separate code, weights, data, hosted-service, and output-redistribution terms |
| Input | Public accession or synthetic fixture, checksum, organism, coordinate convention, and size |
| Baseline | Existing method, held-out split, controls, and predeclared acceptance thresholds |
| Resources | Maximum runtime, memory, storage, network access, and any approved spending |
| Output | Expected columns/types, identifier mapping, row counts, missing values, and output checksums |
| Result | Measured error, coverage, abstention, runtime, resource use, and differences from the baseline |
| Decision | Adopt, revise, or defer, with the measured reason and remaining limits |

An unrun evaluation records `not_run` for results. A published benchmark score remains an upstream claim until reproduced on the declared fixture.

## Capability Checks

| Capability | Check before promotion |
|---|---|
| Gene calling | Valid GFF/GTF coordinates, strand, phase, IDs, and reference assembly; compare exon and gene recovery on held-out loci |
| Enzyme annotation | Per-class error and coverage on held-out families; preserve partial EC labels, missing predictions, and abstention |
| Learned representations | Exact model/tokenizer revision, windowing, output dimensions, and improvement over a simple baseline on held-out species |
| Neighborhood selection | Stable accession mapping, explicit similarity thresholds, deterministic selection, and preserved coordinates |
| Agent source lookup | Correct accession/version, cited source, retrieval date, bounded output, and explicit service errors |
| Report generation | Reopen output, verify links and identifiers, and compare required tables with their source artifacts |

Measure score calibration before using probability language. Report model scores, residue relevance, similarity, and experimental evidence as separate fields.

## Failure Cases

Test malformed inputs, duplicate identifiers, missing records, empty results, and unavailable services. Add decoy files and conflicting metadata to source-lookup tests. Check artifact contents independently of an agent's narrative or an LLM grader.

Keep raw inputs, model files, intermediate arrays, and full traces in external or ignored runtime storage. Publish only reviewed fixture data, compact summaries, and provenance. Add a wrapper only for the tested contract; link to upstream documentation for the rest of the tool.
