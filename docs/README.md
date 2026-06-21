# Documentation Map

This directory is the operating manual for the public GeneCluster control plane.

## Start Here

- [capability-stack.md](capability-stack.md) - what the repo can do: campaign brain, tool lanes, execution lanes, and atlas outputs.
- [glossary.md](glossary.md) - terms-of-art used across the skill, including route cards, evidence normalizers, maturity ladders, and review limits.
- [agent-orchestrator-guide.md](agent-orchestrator-guide.md) - how capable agents should use the repo with local resources, tracker issue graphs, `/goal`, or cloud lanes.
- [superpowers.md](superpowers.md) - how the skill helps agents handle graph-shaped scientific work.
- [demo-campaign-dry-run.md](demo-campaign-dry-run.md) - one-command local harness for issue contracts, review packets, and review surfaces.
- [architecture.md](architecture.md) - the public GeneCluster control-plane model.
- [workflow-campaigns.md](workflow-campaigns.md) - campaign and issue-contract flow.
- [model-routing.md](model-routing.md) - model/worker routing notes.
- [diagrams/genecluster-issue-contract.png](diagrams/genecluster-issue-contract.png) - visual issue-contract lifecycle.
- [diagrams/genecluster-provenance-traceback.png](diagrams/genecluster-provenance-traceback.png) - visual claim-to-source traceback.
- [diagrams/genecluster-stage0-preflight.png](diagrams/genecluster-stage0-preflight.png) - mandatory Stage 0 five-pillar readiness gate.
- [diagrams/genecluster-route-claim-ceiling.png](diagrams/genecluster-route-claim-ceiling.png) - route decision tree and review limits.
- [diagrams/genecluster-maturity-ladder.png](diagrams/genecluster-maturity-ladder.png) - L0 to L5 maturity ladder with check gates.
- [diagrams/genecluster-function-jury.png](diagrams/genecluster-function-jury.png) - multi-tool function scoring and consensus view.
- [diagrams/genecluster-local-cloud-boundary.png](diagrams/genecluster-local-cloud-boundary.png) - local control plane vs cloud execution boundary.
- [diagrams/genecluster-session-flow.png](diagrams/genecluster-session-flow.png) - human-in-the-loop session flow with approval gate.

## Checks And Runbooks

- [biosymphony-campaign-preflight-runbook.md](biosymphony-campaign-preflight-runbook.md) - Stage 0 source, query, and readiness preflight.
- [genecluster-atlas-superpower-runbook.md](genecluster-atlas-superpower-runbook.md) - atlas campaign operating runbook.
- [biosymphony-atlas-obsidian-walkthrough.md](biosymphony-atlas-obsidian-walkthrough.md) - optional Obsidian editing view.
- [biosymphony-antismash-cookbook.md](biosymphony-antismash-cookbook.md) - antiSMASH public example pattern.

## Tool Status

- [biosymphony-tooling-status.md](biosymphony-tooling-status.md) - canonical public inventory of checked, parked, gated, and shelved tools.
- [biosymphony-genecluster-superpower-roadmap.md](biosymphony-genecluster-superpower-roadmap.md) - recommended-tool roadmap.
- [biosymphony-superpower-test-plan.md](biosymphony-superpower-test-plan.md) - historical tool-check protocol.
- [tooling/README.md](tooling/README.md) - per-tool integration docs.
- [cloud-runtimes/README.md](cloud-runtimes/README.md) - AWS, GCP, neocloud, and provider-portability notes.

## Forward Research

- [biosymphony-next-tooling-radar.md](biosymphony-next-tooling-radar.md) - candidate future tools.

## Release Ops

- [public-release-safety.md](public-release-safety.md) - release hygiene rules for public snapshots.
- [implementation-plan.md](implementation-plan.md) - phased public-repo roadmap (foundation, contracts, atlas outputs, and onward).

## Bundled Example

- [Coptis chinensis BIA example](../skills/biosymphony/examples/genecluster-coptis-bia-public-v0/README.md) - worked GeneCluster campaign packet used by the demo harness.
- [egfr-resistance-v1 example](../skills/biosymphony/examples/egfr-resistance-v1/README.md) - sibling-pattern variant-effect atlas example (same contract loop on a different campaign topology).
