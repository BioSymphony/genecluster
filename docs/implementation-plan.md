# Implementation Plan

This public implementation plan describes the reusable GeneCluster control plane. It avoids private operator paths, private tracker IDs, and provider-specific runtime state.

## Phase 0: Public Repo Foundation

Status: present in this snapshot.

Deliverables:

- public README and release boundary
- public-safe AGENTS guidance
- `skills/biosymphony/` validators, references, and examples
- `skills/genecluster-superpowers/` public tool guidance
- `templates/linear-issue.md` tracker-neutral scientific contract shape
- `make public-release-check`

Exit criteria:

- public release check passes
- no raw/heavy biological files or provider artifacts are present
- docs explain what is current guidance versus historical notes

## Phase 1: Campaign Contracts

Goal: make every GeneCluster campaign start from source/query ledgers and a route card.

Deliverables:

- source scout
- query resolution ledger
- campaign preflight
- route scout
- public example manifest
- issue contract validation

Exit criteria:

- public example preflight passes without paid provider access
- unresolved queries produce claim ceilings rather than fake certainty

## Phase 2: Atlas Evidence

Goal: normalize search, annotation, synteny, function, and BGC caller outputs into claim-auditable ledgers.

Deliverables:

- cluster calls
- BGC consensus
- protein-function votes
- protein-function jury
- comparative atlas tables
- review surface manifest

Exit criteria:

- validators reject raw-heavy artifacts and collapsed disagreement
- at least one public or operator-supplied fixture produces a reviewable summary bundle

## Phase 3: Provider Handoff

Goal: keep paid compute powerful but outside public source control.

Deliverables:

- provider handoff manifests
- dispatch templates with ignored runtime output
- summary-only artifact pull rules
- cleanup and hash verification checklist

Exit criteria:

- dispatch templates do not write secrets into payloads or manifests
- provider IDs and response JSON stay under ignored runtime paths
- review surfaces contain summaries, caveats, hashes, and versions only

## Phase 4: Public Polish

Goal: keep the public repo useful on its own.

Deliverables:

- documentation index
- release safety doc
- current tool inventory
- historical notes with provider/private context redacted
- tests and audits run by one command

Exit criteria:

- `make public-release-check` is the obvious public validation command
- first public commit uses fresh history after the scrub passes
