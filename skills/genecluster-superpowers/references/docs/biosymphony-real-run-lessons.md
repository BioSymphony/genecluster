# BioSymphony Real-Run Lessons For Skill Authors

Status: generalized lessons from early provider-backed runs
Last reviewed: 2026-04-30

This note is for authors building related BioSymphony skills. It generalizes
lessons from real remote campaigns where the primary science lane produced
useful results, but a later context lane exceeded the runtime budget.

## 1. Separate Primary Evidence From Context Lanes

Do not package every desirable downstream analysis as one definition of
success. Define a minimum scientific deliverable and then list optional context
lanes separately.

Good milestone split:

- `primary_evidence`: target data materialized, primary search/model/inference
  completed, normalized output table exists.
- `context_evidence`: neighborhoods, coexpression, maps, local refinements,
  sensitivity analyses, or other enrichments.
- `dossier`: synthesis, claim audit, provenance, caveats, and next steps.

This prevents a late expensive stage from making a real primary result look
like total failure.

## 2. Add A Cardinality Gate Before Expensive Fanout

Every skill should estimate fanout before launching context lanes. The estimator
does not need to be perfect; it needs to catch obvious multiplication errors.

Examples:

- GeneCluster: `queries x candidate_hits x windows x domain_profiles`
- Cryo-EM: `movies x particles x classes x refinement branches`
- DOE: `factors x levels x replicates x response models`
- BioProspector: `organisms x datasets x query families x reference DBs`

If the estimated work exceeds the budget, the worker should switch to a bounded
plan: top-N candidates, deduplicated anchors, smaller reference set, stratified
sample, or a declared `deferred_by_budget` row. It should not silently launch
an exhaustive lane and hope.

## 3. Annotate Once, Join Many

Avoid repeated all-vs-all annotation inside loops. Build reusable ledgers once,
then join them into windows, candidates, maps, or dossiers.

Bad pattern:

- For every candidate window, scan every protein against the full domain DB.

Better pattern:

- Scan the target proteome once against the domain DB.
- Create `protein_id -> domain_calls` and `protein_id -> coordinates` ledgers.
- For each window, join coordinates to precomputed domain calls.

Equivalent patterns apply outside GeneCluster: compute per-particle, per-model,
per-sample, or per-factor annotations once, then reuse them in downstream
views.

## 4. Raw Tool Output Is Not A Deliverable

Raw BLAST, HMMER, RELION, AlphaFold, docking, or optimization output can be a
source artifact, but downstream workers need normalized ledgers with headers,
stable IDs, provenance, and review fields.

Every primary output table should have:

- explicit column names
- input/source IDs that join back to the campaign ledgers
- tool/version/provenance
- confidence or review status
- a distinction between controls, known positives, broad-family hits, and new
  candidate evidence

## 5. Controls Are Not Discoveries

Positive controls passing is important, but it should be reported as control
evidence, not mixed with novel discoveries. Separate:

- known/native positive controls
- cross-species homologs
- broad-family/domain-only hits
- negative controls or decoys
- new candidate hypotheses

This prevents a top-hit table from looking stronger than it is.

## 6. Partial Success Needs A First-Class Summary

Every long run should write a summary even if a late stage fails. The summary
should be produced by an exit trap, watcher, or closeout helper and include:

- stages completed
- stages incomplete
- reason for incompletion
- validated artifacts produced
- artifacts missing
- resume command or next bounded lane
- claim downgrades

Do not rely on a final `summary` stage that runs only after all earlier stages
succeed.

## 7. Cost Models Must Include Agent Tokens

For remote scientific campaigns, cloud compute may be cheaper than agent time.
Polling, diagnosing, waiting, and rereading context with large models can
dominate the actual provider bill.

Skill authors should:

- use deterministic watchers for polling
- reserve high-reasoning agents for design, interpretation, and review
- enforce max-turn or max-cost limits on workers doing operational monitoring
- record provider cost and model-token cost separately

## 8. Volume Persistence Is A Feature And A Risk

Persistent provider volumes make resumed runs cheap and save partial results.
They also create false-complete risk when stale markers survive across retries.

Each provider-backed skill should maintain:

- a volume/run manifest
- stage done markers written only after output validation
- input hashes for resume decisions
- cleanup and backup policy
- stale-output detection when code or inputs changed

## 9. Use Small Real Tests, Not Only Mocks

Mocks validate contracts. They do not validate SRA layout, image pull, tool
paths, file naming, provider volume behavior, or real output sizes. Before a
full run, execute a small real route through the same provider, same image,
same storage, same summary retrieval, and same closeout path.

## 10. Make Claim Levels Explicit

Every skill should define claim levels and force the final report to stay within
them. Suggested generic levels:

- `planned`: lane exists but did not run
- `observed`: artifact exists and validates
- `candidate`: evidence supports a hypothesis
- `context_supported`: independent context supports the hypothesis
- `review_required`: ambiguity or broad-family risk remains
- `validated`: external or stronger validation supports the claim
- `unsupported`: requested claim exceeds evidence

The output should say which level was reached, not just pass/fail.

## Translation To Related Skills

For Cryo-EM:

- Separate import/motion/CTF, particle stack, 2D/3D classification, refinement,
  validation, and figure/dossier lanes.
- Estimate particle/class/refinement fanout before launching exhaustive
  branches.
- Treat a map/model output as primary evidence; local resolution, model quality,
  ligand density, and figure panels are context/review lanes.

For BioProspector:

- Separate literature/reference evidence from target-organism evidence.
- Do not let reference DB hits stand in for target dataset hits.
- Normalize hit ledgers before synthesis; split known positives from new
  hypotheses.

For DOE:

- Estimate design size before generating exhaustive designs.
- Separate feasible design generation, simulation/measurement ingestion,
  model fitting, optimization, and recommendation claims.
- Record deferred factor/level combinations explicitly when budget limits the
  design.

For any provider-backed skill:

- Prove actual container/workload activity, not provider intent.
- Prove exact executables, not package names.
- Write partial summaries on failure.
- Treat open action items as follow-up work items, not as passive notes.
