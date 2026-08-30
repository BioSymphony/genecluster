# Tool evaluation plan

Use this plan to evaluate candidate tools with public or synthetic summary data. Keep credentials, provider identifiers, local paths, raw biological data, and private records outside the repository.

The current tool states are in [Tooling status and version watch](biosymphony-tooling-status.md).

## Scope

Candidate tool groups include:

- cblaster and clinker for cluster homology
- JCVI MCScan for synteny
- MMseqs2 for iterative homolog search
- plantiSMASH and antiSMASH for BGC calls
- Foldseek and ProstT5 for structure-sensitive search
- CLEAN, HIT-EC, DeepEC, and ECPred for function annotation
- P450Rdb and related databases for enzyme-family context
- Quarto and Cytoscape.js for review surfaces

## Execution boundary

- Use the repository as the control plane.
- Run heavy tools in external compute or local scratch storage outside Git.
- Return only derived summaries, figures, version records, hashes, and caveat notes.
- Keep raw reads, full genomes, indexes, model weights, and provider responses outside the repository.

## Evaluate a tool

For each tool:

1. Define the inputs, expected outputs, checks, accepted file types, and limits.
2. Confirm that the command is available.
3. Run a small public or synthetic fixture.
4. Check every output type and size before copying it into the repository.
5. Record the version, license, command, resource class, and failure mode.
6. Promote the tool only when its output is interpretable and reproducible.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| Adopted | A repository contract or wrapper consumes a checked output shape. |
| Validated | The tool produced useful output but is not in the default path. |
| Parked | A known blocker prevents reliable use. |
| Gated | A license, account, data-use, or resource constraint prevents public reuse. |
| Shelved | The tool is redundant or outside the current roadmap. |

## Stop conditions

Stop the evaluation if a process would write any of these items into the repository:

- credentials or signed URLs
- provider or account identifiers
- raw or heavy biological files
- unbounded logs or provider responses
- private tracker records
