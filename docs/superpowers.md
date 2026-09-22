# GeneCluster Superpowers

GeneCluster supplies tool knowledge and calling helpers that an AI agent can use to connect bioinformatics analyses.

| Capability | What the agent does |
|---|---|
| Tool knowledge | Reads inputs, commands, outputs, versions, and limits in the [knowledge base](tooling/README.md) |
| Tool calls | Prepares inputs and invokes a CLI command, Python helper, or configured container |
| Tool chaining | Resolves identifiers, extracts sequences, converts columns, and supplies the next tool’s input |
| Combined results | Joins search, annotation, and genome-context evidence into candidate tables and reports |

For example, an agent can run a protein search, extract matched sequences, add domain annotations, and join the results for a report. A cluster-comparison chain preserves a cblaster search session, extracts annotated regions, and supplies those GenBank records to clinker.

Start with the [tool skill](https://github.com/BioSymphony/genecluster/blob/main/skills/genecluster-superpowers/SKILL.md) and [calling guide](tooling/tool-chaining.md). The [version table](biosymphony-tooling-status.md) records checked tool baselines; the calling guide identifies wrappers that need adaptation.

Campaign tracking and scheduling support longer analyses. They are optional to a single tool call or a short chain.
