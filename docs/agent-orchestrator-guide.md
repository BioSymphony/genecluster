# Agent Tool-Use Guide

Use the [tool knowledge base](tooling/README.md) to choose commands and connect analyses for the user’s question.

## Select, Call, and Connect

1. Identify the question, organisms, available inputs, and desired output.
2. Read the relevant tool guide and check local availability and versions.
3. Prepare the required files, identifiers, database, and runtime.
4. Run the command and inspect its exit status and output files.
5. Check output columns, row counts, identifiers, and missing results.
6. Convert or extract the input needed by the next tool.
7. Return the combined findings, sources, and unresolved questions.

See [calling and chaining](tooling/tool-chaining.md) for runnable entry points and format handoffs. Keep tool outputs distinguishable so a report can show conflicting predictions.

## Choose Execution Resources

Run locally when the tool and dataset fit. For external work, prepare the inputs, resource limits, output selection, and cleanup plan before obtaining the user’s approval.

Independent tool calls can run in parallel after their shared inputs are ready. Dependent calls wait for checked outputs. A tracker or OpenAI Symphony can coordinate longer runs; neither is required to use the tool knowledge base or call tools.

## Retain Useful Results

Keep candidate tables, plots, source identifiers, tool and database versions, and the settings needed to interpret the result. Use the [campaign helpers](https://github.com/BioSymphony/genecluster/blob/main/skills/biosymphony/SKILL.md) when the analysis needs more input tracking or restart support.

Keep credentials, private tracker text, raw private data, provider responses, and unpublished sequences outside public artifacts.
