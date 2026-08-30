# BioSymphony GeneCluster

[![Public release check](https://github.com/BioSymphony/genecluster/actions/workflows/public-release-check.yml/badge.svg)](https://github.com/BioSymphony/genecluster/actions/workflows/public-release-check.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-blue.svg)](CITATION.cff)
[![Agents](https://img.shields.io/badge/agents-Claude%20Code%20%7C%20Codex%20%7C%20Symphony-ff69b4.svg)](docs/agent-orchestrator-guide.md)

![BioSymphony GeneCluster banner](docs/diagrams/genecluster-retro-synth-banner.jpg)

BioSymphony GeneCluster is a public skill kit for comparative genome mining. It helps an agent turn a biological question into a traceable campaign.

You provide a pathway, target molecule, or missing biosynthetic step. The kit provides ledgers, route cards, runners, checks, and review templates.

## What the kit does

A GeneCluster campaign can:

- find candidate biosynthetic gene clusters in a new species;
- search for a missing enzyme in a published pathway;
- compare a pathway across related species;
- combine homology, structure, domains, expression, synteny, and genome context;
- record tool versions, source identifiers, parameters, hashes, and limits;
- prepare the next experiment when public evidence cannot resolve a question.

Each route sets a claim limit. For example, transcript evidence can support a candidate-gene claim. It cannot support a physical cluster-boundary claim without genome coordinates.

<p align="center"><img src="docs/diagrams/genecluster-route-claim-ceiling.png" alt="The available data selects a route, and the route sets the claim limit." width="700"></p>

## How a campaign works

Give your agent a clear request. For example:

> Compare the target pathway across four related species. Identify conserved enzymes, species-specific candidates, and possible cluster boundaries. Use public data only.

The agent then:

1. records the question, scope, controls, and review decision;
2. checks the available genome and transcriptome data;
3. builds source, query, database, and cache ledgers;
4. selects a route and records its claim limit;
5. runs bounded searches or prepares an external launch contract;
6. normalizes results into compact evidence tables;
7. returns conclusions, sources, conflicts, limits, and next actions.

The artifacts form the scientific record. You can use a tracker to coordinate work, but the tracker is optional.

<p align="center"><img src="docs/diagrams/genecluster-session-flow.png" alt="You define the campaign and approve external work. The agent prepares and reviews each stage." width="320"></p>

## Execution options

- **Local:** Plan the campaign, validate contracts, transform small files, and build review outputs.
- **External worker:** Run large searches, models, assemblies, or database operations on approved infrastructure.
- **HPC or scheduler:** Use the same launch and artifact contracts with an existing cluster.
- **Solo agent:** Complete the workflow without a tracker.
- **Multiple workers:** Split bounded stages across a tracker or orchestrator.

Keep raw data, heavy files, credentials, provider responses, and unpublished sequences outside this repository.

<p align="center"><img src="docs/diagrams/genecluster-local-cloud-boundary.png" alt="The local control plane sends bounded work to an external worker. Only compact summaries return." width="760"></p>

## Repository layout

- `skills/biosymphony/` contains campaign instructions, ledgers, checks, and runners.
- `skills/genecluster-superpowers/` contains quickstarts and wrappers for selected tools.
- `pipeline/` contains pipeline scaffolds and enrichment helpers.
- `images/` contains container and dispatch reference files.
- `docs/` contains public workflow, tool, architecture, and review guidance.
- `data/` contains public pathway and species examples.
- `templates/` contains tracker-neutral work-unit and solo-agent prompts.
- `tools/` contains optional installers, wrappers, and static checks.

## Start here

- [Campaign workflow](docs/workflow-campaigns.md)
- [Capability stack](docs/capability-stack.md)
- [Glossary](docs/glossary.md)
- [Agent guide](docs/agent-orchestrator-guide.md)
- [Tooling status](docs/biosymphony-tooling-status.md)
- [Atlas runbook](docs/genecluster-atlas-superpower-runbook.md)
- [Documentation index](docs/README.md)

For a solo campaign, start with [the goal prompt](templates/goal-prompt.md).

## Verify the public snapshot

These commands are for maintainers. You do not need them to read or adopt the contracts.

Requirements:

- Python 3
- `make`
- ripgrep (`rg`)

Run the full release check:

```bash
make public-release-check
```

Run only the static public-safety checks:

```bash
make public-audit-strict
```

Run the optional local demo:

```bash
make demo-campaign-dry-run
```

The demo uses bundled public or synthetic fixtures. It does not require paid provider access.

## Contribute

Read [CONTRIBUTING.md](CONTRIBUTING.md) before you open a change. Report security problems through the private process in [SECURITY.md](SECURITY.md).
