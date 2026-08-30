# Agent orchestrator guide

Use this guide to run a GeneCluster campaign with a solo agent, a tracker, or a custom orchestrator.

## Divide responsibilities

The repository supplies contracts, ledgers, checks, examples, and output schemas.

The agent must:

- understand the biological question;
- select the evidence route;
- choose bounded work units;
- keep claims within the route limit;
- verify artifacts;
- explain conflicts and uncertainty.

A tracker can store work units and dependencies. It is not the scientific record. The campaign artifacts are the scientific record.

## Start a campaign

1. Record the target pathway, species, comparison, and review decision.
2. Run the Stage 0 source and readiness check.
3. Create the source, query, control, database, and cache ledgers.
4. Select a route and record its claim limit.
5. Define the first bounded work unit.
6. Check its inputs, outputs, dependencies, and validation commands.
7. Run the work locally or prepare an approved external launch.
8. Normalize the output and update the evidence ledger.
9. Review the result before you start the next unit.

## Choose the scale

Use one agent when the next steps share context or must run in sequence.

Use multiple workers when the work units are independent and have clear artifact contracts. Examples include source scouting, candidate search, synteny, and figure preparation.

Use external compute only when local planning has resolved the route, inputs, storage, permissions, budget, timeout, and cleanup path.

## Close a work unit

Record:

- the outcome;
- the checks that ran;
- artifact paths and hashes;
- versions and parameters;
- unresolved conflicts;
- the current claim limit;
- the next bounded action.

Do not include credentials, raw private data, provider responses, or private tracker text in public artifacts.
