# Model and tool routing

Choose the smallest method that can answer the campaign question.

## Routing rules

| Need | Preferred method | Review limit |
|---|---|---|
| Exact or close sequence match | BLAST, DIAMOND, or MMseqs2 | Supports homology, not exact function |
| Domain or family evidence | HMMER or InterProScan | Supports family membership |
| Structure similarity | Foldseek or a reviewed structure model | Supports fold-level similarity |
| Genome neighborhood | Coordinates, GFF, and neighborhood capture | Requires a suitable genome |
| Conserved order | Synteny or cluster comparison | Requires normalized identifiers and comparable assemblies |
| Enzyme label | Multiple function-evidence methods | Keep confidence and abstention |
| Physical validation | Experiment design | Computational evidence cannot replace the experiment |

## Choose an execution lane

Run small searches and transformations locally.

Use an external worker when the method needs large databases, accelerators, or substantial storage. Define the input, output, resource limit, timeout, and cleanup path before launch.

## Record the route

Record the selected method, rejected methods, versions, parameters, evidence type, and claim limit. Do not replace a requested provider or method without reporting the change.
