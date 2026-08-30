# Architecture

BioSymphony GeneCluster is an artifact-first control plane for comparative-genomics campaigns. It separates campaign reasoning from heavy execution while preserving a traceable path from each conclusion to its source.

## Core components

### Campaign packet

The packet defines the biological question, scope, controls, route, evidence ledgers, acceptance checks, and review limits. It is the durable contract for both solo and multi-worker campaigns.

### Evidence ledger

Ledgers are the scientific record. They retain stable identifiers, source versions, queries, parameters, hashes, and output locations. A tracker may coordinate tasks and dependencies, but it does not replace the evidence ledger.

### Execution lanes

Local lanes handle planning, normalization, checks, and compact review outputs. External lanes handle large searches, model inference, and other compute-heavy steps. Raw data, credentials, provider responses, and private state stay outside the repository.

### Review packet

The review packet contains compact tables, figures, provenance, unresolved conflicts, and route-specific claim limits. It should be understandable without access to private infrastructure.

## Campaign flow

1. Define the biological question and review decision.
2. Scout sources, queries, controls, and data readiness.
3. Select a route and record its claim ceiling.
4. Execute bounded searches or analyses.
5. Normalize results into versioned, traceable artifacts.
6. Compare evidence channels and surface disagreements.
7. Publish a compact review packet and next-wave contract.

## Bounded work units

Each unit of work should declare inputs, expected outputs, acceptance checks, dependencies, failure behavior, and data-handling limits. This keeps local runs, external workers, and tracker issues interchangeable at the contract level.

## Trust boundary

Only public documentation, synthetic fixtures, compact public summaries, and reusable contracts belong in this repository. Credentials, raw or heavy data, unpublished sequences, provider payloads, and private tracker content do not.
