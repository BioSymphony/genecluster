# BioSymphony GeneCluster Atlas Best Practices

Use this guide when turning GeneCluster campaign outputs into a comparative
atlas that other scientists, reviewers, or future agents can inspect.

## Atlas Layers

Keep each atlas separated into four layers:

| Layer | Typical format | Source of truth |
|---|---|---|
| Pipeline outputs | TSV, JSON, compact FASTA snippets, workbooks | The checked run summary |
| Per-species narrative | Markdown or `.qmd` pages | The reviewed species page |
| Cross-species narrative | Markdown or `.qmd` comparison pages | The reviewed comparison page |
| Published atlas | HTML, PDF, static figures, summary workbooks | Rendered from source docs |

The source narrative should live in durable Markdown or Quarto source. Rendered
HTML, PDF, and browser bundles are build artifacts unless they are explicitly
published as examples. Raw reads, full genomes, indexes, databases,
and provider work directories stay outside the repo.

## Naming

Use stable names that carry the biological scope, not temporary run labels.

Per-species workbook:

```text
<species-slug>-<pathway-slug>-pathway-<YYYY-MM-DD>.xlsx
```

Per-species top-hit FASTA bundle:

```text
data/<species-slug>-top-hits.faa
```

Quarto or Markdown pages:

```text
species/<species-slug>.qmd
cross-species/<topic>.qmd
methods/<aspect>.qmd
```

Avoid names such as `results.xlsx`, `final.xlsx`, `new-output.tsv`, or
campaign-specific shorthand that cannot stand alone in a published atlas.

## Required Content

Every species page should include:

- Data state: genome, transcriptome, proteome, annotation, and source versions.
- Query set: canonical pathway proteins plus positive and negative controls.
- Controls: ACT2, GAPDH, and random-shuffle or equivalent negative control
  status.
- Pipeline metrics: proteome size, annotation count, candidate count, anchored
  hits, neighborhoods, runtime, tool versions, and major limits.
- Top hits: one row per query with accession, score, identity, coverage,
  reciprocal or orthology status, and coordinate confidence where available.
- Claim ceiling: what the route can support and what it cannot support.
- Links to compact artifacts: workbooks, ledgers, summary FASTA snippets,
  review HTML, hashes, and manifests.

Every cross-species page should include:

- A pathway-step matrix with one row per enzyme or pathway step.
- A species-by-step support view with evidence classes, not just present/absent
  calls.
- A short explanation of paralog, homeolog, splice, or annotation ambiguity.
- Synteny or neighborhood support only when genome coordinates are valid.
- A limits section for data gaps and route constraints.

## Authoring Rules

- Keep narrative in Markdown or `.qmd`. Do not hand-author final HTML as the
  canonical source.
- Cite primary literature for pathway, enzyme-function, novelty, and taxonomic
  claims.
- Show controls before showing headline hits.
- Keep tables rectangular and machine-readable where possible. If a figure uses
  summarized data, keep the source table beside it.
- Use one visual signal per figure whenever possible: identity, confidence,
  evidence class, or pathway step. Put extra detail in tooltips, side tables, or
  appendices.
- Record tool versions and database versions in ledgers, not only prose.
- Prefer compact derived artifacts in the repo. Raw or heavy artifacts belong in
  provider storage or ignored local runtime directories.

## Claim Review

Run an explicit claim review before publishing any strong novelty, first,
absence, convergence, or cluster-boundary claim.

Use at least three independent review passes:

| Review pass | Question | Output |
|---|---|---|
| Literature check | Does primary literature support each part of the claim? | Supported, partial, contradicted, or unclear |
| Prior-art check | Has this result appeared in another species, pathway, order, or method? | Novel, confirmation, re-derivation, or not novel |
| Alternative explanations | What data gaps, thresholds, or controls could weaken the claim? | Limitations, threshold issues, missing controls |

If the review weakens the claim, revise the headline and keep the support note
visible. A qualified claim with clear limits is stronger than an overstated one
buried behind a polished figure.

## Interactive Viewers

Interactive graph and genome viewers should be usable without trapping the
reader's viewport.

For Cytoscape.js, JBrowse, igv-reports, clinker, or similar embedded viewers:

- Provide visible controls for fit, reset, zoom in, zoom out, and center.
- Bind keyboard shortcuts for common actions.
- Disable wheel zoom unless a modifier key is held.
- Record the initial fit state and make reset restore it.
- Provide a static table or image fallback for PDF and no-JavaScript readers.

Do not use an interactive figure as the only copy of the data. The source table
and figure-generation manifest should remain inspectable.

## Figure Conventions

High-value atlas figures include:

- A pathway diagram colored by evidence class or mean conservation.
- A species-by-step support matrix.
- A candidate-gene neighborhood or synteny block when coordinates support it.
- A phylogeny or species relationship view when making cross-species claims.
- A standardized pipeline metrics table across all species.

Do not make physical cluster claims from transcript-only data. Do not make
convergence claims without explicit prior-art, phylogenetic, or ancestral-state
support. Do not treat a negative search as absence unless the route and controls
support that claim.

## Report Stack

The public repo supports multiple presentation routes. Recommended defaults:

- Markdown for durable source narrative.
- Quarto for HTML/PDF atlas rendering.
- Cytoscape.js for pathway graphs and compact interactive networks.
- igv-reports or JBrowse for summary genome browser views.
- clinker or JCVI MCScan for conserved-neighborhood and synteny views when
  coordinate inputs are valid.

Rendered reports can be hosted as static files. Public examples should include
only summary artifacts, compact source tables, hashes, manifests, limits, and
provenance.

## Definition Of Done

An atlas update is ready to ship when:

- Stage 0 preflight and route selection are recorded.
- Query and control ledgers are complete.
- Controls pass, or failures are explicitly shown and limit the claim.
- Candidate hits are tied to source versions, accessions, scores, and evidence
  classes.
- Comparative pages are updated from the same source tables as the figures.
- Strong claims have passed claim review and been reframed where needed.
- Generated figures have source tables or manifests.
- Public release checks pass.

## Related Docs

- [genecluster-atlas-superpower-runbook.md](genecluster-atlas-superpower-runbook.md)
- [biosymphony-atlas-obsidian-walkthrough.md](biosymphony-atlas-obsidian-walkthrough.md)
- [tooling/quarto.md](tooling/quarto.md)
- [tooling/cytoscape-js.md](tooling/cytoscape-js.md)
- [public-release-safety.md](public-release-safety.md)
