# BioSymphony GeneCluster Superpower Test Plan

This is the public-safe version of the historical tool validation protocol. Private run logs, provider IDs, issue IDs, local paths, and cost ledger details are intentionally omitted.

## Goal

Exercise candidate open tools against summary atlas data, decide whether each tool is adopted, parked, gated, or shelved, and feed the result into the public tooling inventory.

The current canonical state lives in [biosymphony-tooling-status.md](biosymphony-tooling-status.md).

## Test Scope

Candidate lanes include:

- cblaster and clinker for cluster homology
- JCVI MCScan for synteny
- MMseqs2 for iterative homolog search
- plantiSMASH and antiSMASH for BGC calls
- Foldseek and ProstT5 for structure-sensitive search
- CLEAN, HIT-EC, DeepEC, and ECPred for function annotation
- P450Rdb and related domain databases for enzyme family context
- Quarto and Cytoscape.js for review surfaces

## Public Execution Model

- Keep the laptop/repo as the control plane.
- Run heavy tools in an external provider workspace or a local scratch area outside git.
- Pull back only derived summaries: TSV, JSON, SVG/PNG/PDF figures, short HTML, version files, hashes, and caveat notes.
- Keep raw reads, full genomes, indexes, model weights, and provider responses out of the repo.

## Per-Tool Protocol

For each tool:

1. Create a scientific contract with inputs, expected outputs, validation commands, accepted file types, and caveats.
2. Run a command-presence smoke test.
3. Run a tiny fixture or public summary-data test.
4. Check output sizes and file extensions before copying anything into the repo.
5. Record version, license posture, command, runtime class, and failure mode.
6. Promote the tool only when output is interpretable and reproducible.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| Adopted | Output landed in an atlas or review surface and has a reproducible command shape. |
| Validated | Tool ran cleanly and produced useful output, but is not in the default path. |
| Parked | Install or wrapper works partly, but a known blocker remains. |
| Gated | License, account, data-use, or heavy-model constraint blocks public reuse. |
| Shelved | Tool is lower priority or redundant until a campaign needs it. |

## Safety Gates

Stop and review if a test tries to write credentials, provider IDs, raw/heavy biological files, unbounded logs, or private tracker details into the repo.
