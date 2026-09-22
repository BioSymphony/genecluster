# Documentation

Start with the [campaign workflow](workflow-campaigns.md) to plan an analysis or the [demo guide](demo-campaign-dry-run.md) to inspect example outputs. Use [tooling status](biosymphony-tooling-status.md) to distinguish checked integrations from proposed tools.

## Core workflow

- [Capability stack](capability-stack.md) — supported campaign capabilities and limits.
- [Glossary](glossary.md) — shared terms for routes, evidence, maturity, and review.
- [Campaign workflow](workflow-campaigns.md) — campaign steps, required files, and review decisions.
- [Architecture](architecture.md) — control plane, execution lanes, and evidence flow.
- [Agent guide](agent-orchestrator-guide.md) — solo-agent, tracker, and custom-orchestrator use.
- [Demo campaign](demo-campaign-dry-run.md) — local example packet and review surface.

## Campaign and review guidance

- [Campaign preflight](biosymphony-campaign-preflight-runbook.md) — source, query, and readiness checks.
- [Atlas runbook](genecluster-atlas-superpower-runbook.md) — steps for assembling a comparative report.
- [Atlas best practices](biosymphony-atlas-best-practices.md) — claims, figures, and report review.
- [Superpowers](superpowers.md) — work units, dependencies, and parallel execution.
- [Model routing](model-routing.md) — choosing bounded worker roles.

## Tools and execution

- [Tooling status](biosymphony-tooling-status.md) — current upstream versions, public baselines, and integration status.
- [Per-tool guides](tooling/README.md) — concise setup and output contracts.
- [Tooling radar](biosymphony-next-tooling-radar.md) — source-backed candidates that are not yet integrated.
- [Tool evaluation contract](tooling/tool-evaluation.md) — versions, controls, outputs, and acceptance criteria for a proposed integration.
- [Cloud runtime guidance](cloud-runtimes/README.md) — portable, public-safe execution patterns.

## Reference and roadmap

- [Capability roadmap](biosymphony-genecluster-superpower-roadmap.md) — planned public additions.
- [Tool-check protocol](biosymphony-superpower-test-plan.md) — repeatable validation method.
- [Implementation plan](implementation-plan.md) — phased public-repo roadmap.
- [Public release safety](public-release-safety.md) — publication boundaries and checks.

## Diagrams

The [diagrams](diagrams/) directory illustrates campaign steps, work-unit contracts, provenance, analysis routes, readiness stages, function evidence, and local/external execution boundaries.

## Bundled examples

- [GeneCluster BIA example](https://github.com/BioSymphony/genecluster/tree/main/skills/biosymphony/examples/genecluster-coptis-bia-public-v0)
- [Variant-effect atlas example](https://github.com/BioSymphony/genecluster/tree/main/skills/biosymphony/examples/egfr-resistance-v1)

Examples use public or synthetic data only.
