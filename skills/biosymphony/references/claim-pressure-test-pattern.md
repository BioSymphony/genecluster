# Claim pressure-test pattern

Every "novel," "first," or "outstanding mystery" claim in a campaign dossier goes through a three-agent pressure test before it lands in a deliverable. The pattern catches over-claiming early, when the cost of reframing is low.

## When to run it

Run it before:

- a campaign closeout writes a headline claim that uses words like "novel," "first," "convergent," "unprecedented," "outstanding mystery," or "absent"
- any review surface or HTML report makes a comparative claim across species
- any external-facing summary (manuscript draft, slide deck, press text) is generated from campaign artifacts

Skip it for:

- routine candidate-hit tables
- ledger validation
- internal artifact checks that do not produce headline language

## The three agents

```
Agent 1 — Literature audit
  Verify each component of the claim against primary literature.
  Verdicts: VERIFIED / PARTIALLY SUPPORTED / CONTRADICTED / UNCLEAR.
  Demand DOIs or PMIDs for each verdict.

Agent 2 — Prior-art / convergence check
  Has this been shown before? In other species? Other orders? Other clades?
  Distinguish: novel discovery / independent confirmation / re-derivation /
  not novel.

Agent 3 — Steel-man / counter-evidence
  Adversarial framing: "I am a hostile reviewer. Find every weakness."
  Attack vectors: methodology, threshold abuse, taxonomic confusion,
  prior art ignored, "outstanding mystery" overstatement, missing controls.
  Verdicts: STRONG / MODERATE / WEAK / NULL.
```

Run the three in parallel. Each writes a short verdict file the orchestrator reads back into the claim audit.

## What the pattern catches

In practice the pass typically returns several specific overstatements per headline claim. Common patterns:

- "absent from X" claims that turn out to be "alternate enzyme present"
- "convergence" claims that depend on an ancestral-state reconstruction the campaign did not actually run
- "outstanding mystery" framing that ignores prior work in a sister taxon
- thresholds chosen after the fact rather than pre-registered
- mixing positive controls with novel discoveries in the same top-hit table

## What to do with the verdicts

The honest reframing is the deliverable. Land the fact-check verdicts as an addendum linked from the headline, not buried. The user-facing message is "we know the original framing was overstated, here is the corrected version." That is stronger science than pretending the first draft was right.

If the steel-man returns STRONG counter-evidence, the claim drops to the next claim ceiling down (for example, from `validated` to `context_supported`, or from `candidate` to `review_required`). The route card and the claim audit must reflect the downgrade.

## Cost framing

The pattern is intentionally a small fraction of campaign budget. On most provider-backed campaigns it adds well under an hour of wall time and a small fraction of the compute bill. The cost of skipping it shows up later as an embarrassing public claim, a manuscript revision cycle, or a follow-up campaign correcting the original framing.

## Related patterns

- **Multi-agent discovery dispatch.** A larger fan-out pattern (more agents, longer per-agent context) used during hypothesis generation, before evidence is in hand. The pressure test described here is its review-side counterpart.
- **Claim audit.** Run by `genecluster_claim_audit.py`. The pressure test feeds the claim audit by surfacing language the audit then enforces against the route card's claim ceiling.
- **Route card.** Records the claim ceiling the campaign is allowed to reach. Pressure-test verdicts can force the route card to a lower ceiling.

## See also

- `skills/biosymphony/SKILL.md` — overall campaign orchestration and claim audit
- `docs/glossary.md` — claim ceiling, route card, claim audit definitions
- `docs/biosymphony-real-run-lessons.md` — separating primary evidence from context, and explicit claim levels
