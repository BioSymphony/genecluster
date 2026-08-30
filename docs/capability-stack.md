# Capability stack

BioSymphony GeneCluster provides campaign contracts, evidence ledgers, tool adapters, execution handoffs, and review outputs for comparative genome mining.

## Campaign control

- define targets, comparators, controls, exclusions, and review decisions;
- scout public data and record stable identifiers;
- choose a route based on genome and transcriptome readiness;
- set a claim ceiling before analysis;
- divide work into bounded, checkable units;
- retain versions, parameters, hashes, and failure states.

## Analysis capabilities

- sequence and profile search;
- domain and function annotation;
- BGC calling and cluster comparison;
- structure search and representation;
- synteny, neighborhood, and expression support;
- multi-species comparison;
- evidence normalization and claim checks.

A capability is useful only when its inputs are available and its output fits the selected route. Missing genome coordinates, for example, prevent physical cluster-boundary claims.

## Review outputs

- ranked candidate tables;
- route cards and evidence ledgers;
- cluster and pathway views;
- source and version provenance;
- unresolved conflicts;
- review limits and next actions.

## Execution lanes

Local execution covers planning, small transformations, checks, and compact reports. External workers may handle large databases, searches, models, or assemblies. Provider templates are examples, not proof that a provider is configured or suitable for a specific workload.

## Tool inventory

The [tooling status](biosymphony-tooling-status.md) separates current upstream releases from repository baselines and distinguishes available, checked, adopted, planned, and gated integrations.

Use the [recommended-tool skill](https://github.com/BioSymphony/genecluster/blob/main/skills/genecluster-superpowers/SKILL.md) when adding a tool covered by the packaged subset.

## Public boundary

Public and synthetic fixtures, reusable contracts, and compact public summaries belong in the repository. Raw or heavy data, credentials, private paths, provider payloads, unpublished sequences, and private tracker content do not.
