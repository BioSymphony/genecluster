# Campaign workflow

GeneCluster campaigns move from a biological question to a compact, reviewable evidence packet. The artifacts are the scientific record. A tracker can coordinate work, but it is optional.

## 1. Define the question

Record the target pathway, organism scope, expected comparison, and decision the campaign should support. State exclusions and review limits before searching.

## 2. Build the ledgers

Create source, query, control, database, and cache ledgers. Each entry should carry a stable identifier, version or access date, retrieval route, and intended use. Public examples use public or synthetic inputs only.

## 3. Select a route

Classify the available genome and transcriptome evidence. Choose the route that fits those inputs and record its claim ceiling. For example, transcript-first evidence can nominate candidates but cannot establish physical cluster boundaries.

## 4. Search and normalize

Run bounded candidate searches, retain stable identifiers, and convert outputs into compact tables. Keep raw and heavy artifacts outside the repository. Record tool versions, parameters, hashes, and failure states in the run manifest.

## 5. Compare and score

Combine homology, domain, structure, expression, synteny, and neighborhood evidence only when those sources are available. Keep each evidence channel visible so a reviewer can distinguish agreement from missing data.

## 6. Assemble the review packet

Produce ranked candidates, pathway and cluster views, source citations, unresolved conflicts, and the route-specific claim limit. Every conclusion should trace back to a ledger row or versioned run artifact.

## 7. Close the wave

Mark completed checks, record remaining uncertainty, and define the next bounded action. A solo agent can carry the same packet through the full workflow; a tracker can distribute individual stages without changing the artifact contract.

## Minimum handoff

A useful handoff includes:

- the biological question and scope;
- current ledgers and route card;
- commands or launch contract for reproducibility;
- compact outputs with versions and hashes;
- conclusions tied to evidence;
- explicit limitations and next actions.
