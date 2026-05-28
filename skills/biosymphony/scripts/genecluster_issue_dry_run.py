#!/usr/bin/env python3
"""Generate Linear-ready dry-run issues for GeneCluster campaigns."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from genecluster_preflight import normalize_provider  # noqa: E402
from preflight_check import validate as validate_issue  # noqa: E402


SCHEMA_BLOCK = """\
<!-- symphony:schema
schema_version: 1
touched_areas:
{touched_areas_yaml}
complexity: {complexity}
-->"""


RISK_NOTES = """\
- Do not store private sequences, unpublished structures, API keys, provider credentials, or raw sequence data in Linear.
- No raw FASTQ/SRA/BAM/assembly files may be downloaded into the repo.
- Physical gene-cluster claims require genome coordinates; transcriptome-only evidence may only nominate candidate genes.
- Product-level chemistry, pathway completion, and enzyme function require external biochemical or metabolomics validation."""


RUN_SCOPES = (
    "smoke",
    "candidate_search",
    "genome_context",
    "coexpression",
    "synteny",
    "full_public_mining",
    "next_experiment_design",
    "full_campaign",
    "full_campaign_24h",
)


@dataclass(frozen=True)
class IssueSpec:
    key: str
    wave: int
    slug: str
    summary: str
    agent_role: str
    inputs: list[tuple[str, str]]
    acceptance: list[str]
    validation: str
    touched_areas: list[tuple[str, str]]
    blocked_by: list[str]
    evidence_classes: list[str]
    expected_outputs: list[str]
    artifact_contract: list[str]
    review_gate: list[str]
    handoff_notes: list[str]
    allowed_claim: str
    forbidden_claim: str
    complexity: str


def issue_id(prefix: str, wave: int, slug: str) -> str:
    return f"{prefix}-W{wave:02d}-{slug}"


def schema_block(touched_areas: list[str], complexity: str) -> str:
    return SCHEMA_BLOCK.format(
        touched_areas_yaml="\n".join(f"  - {area}" for area in touched_areas),
        complexity=complexity,
    )


def bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def checklist(items: list[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items)


def make_issue(spec: IssueSpec, issue_ids_by_key: dict[str, str]) -> str:
    inputs_text = "\n".join(f"- `{name}` - {description}" for name, description in spec.inputs)
    touched_text = "\n".join(f"- `{path}` - {description}" for path, description in spec.touched_areas)
    deps = [issue_ids_by_key[key] for key in spec.blocked_by]
    deps_text = "\n".join(f"Blocked by: {dep}" for dep in deps) if deps else "Blocked by: none"
    outputs_text = "\n".join(f"- `{item}`" for item in spec.expected_outputs)
    schema = schema_block([path for path, _ in spec.touched_areas], spec.complexity)
    return f"""## Summary

{spec.summary}

## Agent Role

{spec.agent_role}

## Inputs

{inputs_text}

## Acceptance Criteria

{checklist(spec.acceptance)}

## Validation Commands

```bash
{spec.validation.strip()}
```

## Touched Areas

{touched_text}

## Dependencies

{deps_text}

## Evidence Class

{bullet(spec.evidence_classes)}

## Artifact Contract

Expected outputs:

{outputs_text}

Contract details:

{bullet(spec.artifact_contract)}

## Review Gate

{bullet(spec.review_gate)}

## Handoff Notes

{bullet(spec.handoff_notes)}

## Claim Boundary

This issue may claim:
- {spec.allowed_claim}

This issue must not claim:
- {spec.forbidden_claim}

## Risk Notes

{RISK_NOTES}

## Orchestration Guardrails

- Prompt render preflight must prove this issue body is non-empty and contains no unresolved template tags.
- Provider payload preflight must check byte size before RunPod, SSH, cloud, or managed-workflow submission.
- Snapshot or branch preflight must prove the launch bundle, scripts, and expected small inputs exist in the Git ref/worktree the worker will use.
- Silent fallback to a different worker, team, provider, target dataset, or biological route is a hard stop.

## Resume / Recovery Contract

- Checkpoint: record the last confirmed validation command, artifact path, and remote/provider state in the Linear closeout comment.
- Resume command: rerun the validation command above, then continue from the last confirmed artifact rather than repeating stale failed assumptions.
- Degraded recovery: if the worker recovers missing issue body, bundle, target data, provider state, or prompt context, mark the issue degraded and name the recovered source.
- Wakeups must rerun input, route, prompt, payload, and snapshot diagnostics before retrying any failed launch/search action.

## Complexity

tier: {spec.complexity}

{schema}
"""


def rel(path: Path) -> str:
    return path.as_posix()


def campaign_context(campaign_path: Path) -> dict[str, Any]:
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    example_dir = campaign_path.parent
    provider = normalize_provider(str(campaign.get("execution", {}).get("provider_class", "runpod_pod")))
    return {
        "campaign": campaign,
        "campaign_id": campaign["campaign_id"],
        "campaign_path": rel(campaign_path),
        "example_dir": rel(example_dir),
        "data_ledger": rel(example_dir / "data-ledger.tsv"),
        "query_ledger": rel(example_dir / "query-ledger.tsv"),
        "resource_ledger": rel(example_dir / "resource-ledger.tsv"),
        "provider_class": provider,
    }


def preflight_all(ctx: dict[str, Any]) -> str:
    return f"""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --campaign {ctx['campaign_path']} \\
  --data-ledger {ctx['data_ledger']} \\
  --query-ledger {ctx['query_ledger']} \\
  --resource-ledger {ctx['resource_ledger']}"""


def launch_validation(ctx: dict[str, Any], *, run_scope: str, run_id: str, out: str) -> str:
    return f"""{preflight_all(ctx)}
python3 skills/biosymphony/scripts/genecluster_launch_bundle.py \\
  --campaign {ctx['campaign_path']} \\
  --provider-class {ctx['provider_class']} \\
  --run-scope {run_scope} \\
  --run-id {run_id} \\
  --out {out}
python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --launch-manifest {out}/launch-manifest.json"""


def issue_catalog(ctx: dict[str, Any]) -> dict[str, IssueSpec]:
    campaign_id = ctx["campaign_id"]
    campaign_path = ctx["campaign_path"]
    data_ledger = ctx["data_ledger"]
    query_ledger = ctx["query_ledger"]
    resource_ledger = ctx["resource_ledger"]
    provider_class = ctx["provider_class"]

    return {
        "contract_gate": IssueSpec(
            key="contract_gate",
            wave=0,
            slug="CONTRACT-GATE",
            summary=f"Freeze the provider-neutral GeneCluster contract for {campaign_id} before any discovery work starts.",
            agent_role="Contract steward. Verify scope, provider class, artifact policy, and claim boundaries without downloading sequence data.",
            inputs=[(campaign_path, "campaign manifest")],
            acceptance=[
                "campaign-manifest.json passes GeneCluster preflight",
                "execution.large_local_downloads is false",
                "execution.artifact_policy is summaries_only",
                "execution.web_tool_policy is container-only",
                "all declared run scopes are treated as planning scopes until an artifact contract exists",
            ],
            validation=f"python3 skills/biosymphony/scripts/genecluster_preflight.py --campaign {campaign_path}",
            touched_areas=[(campaign_path, "campaign contract")],
            blocked_by=[],
            evidence_classes=["review_required"],
            expected_outputs=["campaign-manifest.json"],
            artifact_contract=[
                "No biological discovery outputs are produced by this gate.",
                "Record provider-neutral assumptions and any provider-specific gaps in the Linear comment.",
            ],
            review_gate=[
                "Human reviewer confirms no private data, tokens, or raw sequence paths are embedded.",
                "Reviewer confirms the run scope matches the intended discovery milestone.",
            ],
            handoff_notes=[
                "Downstream agents may use the manifest as the source of truth for provider class and artifact policy.",
                "If provider credentials are missing, report variable names only, never values.",
            ],
            allowed_claim="The campaign contract is ready for GeneCluster planning and remote or configured-workdir preparation.",
            forbidden_claim="Any sequence data has been downloaded, analyzed, or used to discover candidate genes.",
            complexity="small",
        ),
        "data_gate": IssueSpec(
            key="data_gate",
            wave=1,
            slug="DATA-GATE",
            summary="Validate public accession metadata, license posture, and remote-only storage paths for GeneCluster discovery.",
            agent_role="Data provenance agent. Check accession metadata and storage policy while keeping raw sequence files out of the repo.",
            inputs=[(data_ledger, "public accession metadata ledger")],
            acceptance=[
                "data-ledger.tsv passes GeneCluster preflight",
                "all large input paths point to remote or provider-managed storage",
                "no local_path is present for raw sequence data",
                "data sensitivity, upload allowance, retention, and redistribution fields are populated",
            ],
            validation=f"python3 skills/biosymphony/scripts/genecluster_preflight.py --data-ledger {data_ledger}",
            touched_areas=[(data_ledger, "data metadata ledger")],
            blocked_by=["contract_gate"],
            evidence_classes=["review_required"],
            expected_outputs=["data-ledger.tsv"],
            artifact_contract=[
                "Ledger rows must preserve accession, source URL, expected size, checksum status, data sensitivity, and allowed compute location.",
                "Large artifacts remain remote-only and are referenced by pointer, not copied into Linear.",
            ],
            review_gate=[
                "Reviewer verifies public/open terms or explicit approval before any provider upload.",
                "Reviewer rejects rows with local raw sequence or repo-contained heavy workdir paths.",
            ],
            handoff_notes=[
                "Candidate-search agents should treat this ledger as the only approved input inventory.",
                "New accessions require a fresh data-gate pass before dispatch.",
            ],
            allowed_claim="The accession metadata and remote storage plan are ready for the requested GeneCluster scope.",
            forbidden_claim="The raw accessions have been fetched, converted, assembled, or locally inspected.",
            complexity="small",
        ),
        "query_gate": IssueSpec(
            key="query_gate",
            wave=2,
            slug="QUERY-GATE",
            summary="Validate query seed classes, negative controls, and literature caveats for provider-neutral gene discovery.",
            agent_role="Query curation agent. Separate high-confidence seed enzymes from broad-family probes and unresolved pathway steps.",
            inputs=[(query_ledger, "query seed ledger")],
            acceptance=[
                "query-ledger.tsv passes GeneCluster preflight",
                "query seeds include core strictosidine, DCS, and C17 OMT classes when applicable",
                "broad CYP/OMT/reductase probes carry false-positive risk notes",
                "native target-species tailoring caveats are preserved",
            ],
            validation=f"python3 skills/biosymphony/scripts/genecluster_preflight.py --query-ledger {query_ledger}",
            touched_areas=[(query_ledger, "query seed ledger")],
            blocked_by=["contract_gate"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "review_required"],
            expected_outputs=["query-ledger.tsv"],
            artifact_contract=[
                "Each seed records accession resolution status, family scope, motif requirements, decoys or negative controls, and curation status.",
                "Unresolved sequence accessions must be resolved in the provider workdir, not by adding FASTA files to the repo.",
            ],
            review_gate=[
                "Reviewer confirms query seeds are specific enough for the planned claim level.",
                "Reviewer flags broad-family hits that cannot support product chemistry without additional evidence.",
            ],
            handoff_notes=[
                "Search agents should emit hit evidence against query_id values from this ledger.",
                "Ranking agents should downweight family_seed or context_only rows unless corroborated.",
            ],
            allowed_claim="The query set is ready for the requested GeneCluster discovery scope.",
            forbidden_claim="Any query seed has been experimentally validated by this issue.",
            complexity="small",
        ),
        "resource_gate": IssueSpec(
            key="resource_gate",
            wave=2,
            slug="RESOURCE-GATE",
            summary="Validate tool, database, citation, and license resources before provider dispatch.",
            agent_role="Resource and license agent. Confirm that every external dependency is usable under the campaign's container-only policy.",
            inputs=[(resource_ledger, "resource/license ledger")],
            acceptance=[
                "resource-ledger.tsv passes GeneCluster preflight",
                "restricted-or-review resources are either approved or explicitly deferred",
                "container-only use mode is preserved for public web tools",
                "versions and citations are sufficient for provenance records",
            ],
            validation=f"python3 skills/biosymphony/scripts/genecluster_preflight.py --resource-ledger {resource_ledger}",
            touched_areas=[(resource_ledger, "resource and license ledger")],
            blocked_by=["contract_gate"],
            evidence_classes=["review_required"],
            expected_outputs=["resource-ledger.tsv"],
            artifact_contract=[
                "Ledger rows must include resource type, version, license class, use mode, and citation.",
                "No API keys, account tokens, or provider credentials are recorded in this artifact.",
            ],
            review_gate=[
                "Reviewer confirms public webserver use is not required for the planned run.",
                "Reviewer accepts or rejects restricted resources before launch-ready status.",
            ],
            handoff_notes=[
                "Remote execution agents must copy resource versions into versions.json and citations into citations.bib when available.",
                "If a resource is deferred, downstream claims must note the missing evidence lane.",
            ],
            allowed_claim="The resource plan is reviewable for provider-neutral GeneCluster execution.",
            forbidden_claim="All resources are installed, licensed for every provider, or ready for launch credentials.",
            complexity="small",
        ),
        "smoke_bundle": IssueSpec(
            key="smoke_bundle",
            wave=3,
            slug="SMOKE-BUNDLE",
            summary="Generate a smoke-scope launch bundle that validates metadata and dossier skeleton wiring only.",
            agent_role="Smoke-run coordinator. Build a small control-plane bundle and prove the campaign can be staged without heavy compute.",
            inputs=[
                (campaign_path, "campaign contract"),
                (data_ledger, "data metadata ledger"),
                (query_ledger, "query seed ledger"),
                (resource_ledger, "resource/license ledger"),
            ],
            acceptance=[
                "smoke launch-manifest.json passes GeneCluster preflight",
                "provider notes list missing credentials by environment variable name only",
                "expected artifacts are small summaries, ledgers, provenance, versions, and licenses",
                "no heavy local workdir is introduced under the repo",
            ],
            validation=launch_validation(
                ctx,
                run_scope="smoke",
                run_id="genecluster-smoke-dry-run",
                out=".runtime/genecluster-launch-smoke",
            ),
            touched_areas=[(".runtime/genecluster-launch-smoke/", "local ignored launch-prep bundle")],
            blocked_by=["data_gate", "query_gate", "resource_gate"],
            evidence_classes=["review_required"],
            expected_outputs=["launch-manifest.json", "run-later.sh", "README.md"],
            artifact_contract=[
                "Bundle must be sufficient to rehearse metadata/query/resource validation.",
                "Expected artifacts must not include raw sequence files, assemblies, databases, or workflow workdirs.",
            ],
            review_gate=[
                "Reviewer confirms the smoke bundle is not launch-ready heavy compute.",
                "Reviewer confirms the selected provider class can represent smoke scope or records a provider substitution.",
            ],
            handoff_notes=[
                "Use smoke output to prove Linear-to-Symphony handoff before activating candidate search.",
                "Provider-specific launch remediation belongs in follow-up notes, not in secrets-bearing issue text.",
            ],
            allowed_claim="The smoke-scope control plane is internally valid and ready for operator review.",
            forbidden_claim="Candidate search, genome context, coexpression, or synteny analysis has run.",
            complexity="small",
        ),
        "smoke_review": IssueSpec(
            key="smoke_review",
            wave=3,
            slug="SMOKE-REVIEW",
            summary="Review smoke-scope outputs for provenance completeness and dispatch readiness.",
            agent_role="Review gate agent. Confirm that the smoke run or rehearsal produced only small, auditable control-plane artifacts.",
            inputs=[("genecluster-dossier-smoke/dossier-manifest.json", "smoke dossier manifest or rehearsal manifest")],
            acceptance=[
                "smoke manifest records campaign id, provider class, run scope, validation commands, and artifact policy",
                "versions.json and licenses.tsv are present when a smoke run executed",
                "provenance.jsonl includes at least campaign and ledger validation records",
                "claim-ledger.md contains no biological discovery claims",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --provenance-jsonl genecluster-dossier-smoke/data/provenance.jsonl \\
  --claim-ledger genecluster-dossier-smoke/claim-ledger.md""",
            touched_areas=[("genecluster-dossier-smoke/", "small smoke-run returned artifacts")],
            blocked_by=["smoke_bundle"],
            evidence_classes=["review_required"],
            expected_outputs=["data/provenance.jsonl", "data/versions.json", "data/licenses.tsv", "claim-ledger.md"],
            artifact_contract=[
                "All returned files must be small summaries or ledgers.",
                "The claim ledger must explicitly say smoke evidence is not candidate discovery.",
            ],
            review_gate=[
                "Reviewer confirms smoke artifacts are sufficient to activate the first discovery wave.",
                "Reviewer opens new issues for missing provenance fields instead of relaxing claim boundaries.",
            ],
            handoff_notes=[
                "Candidate-search agents may proceed only after smoke review accepts provider and provenance wiring.",
                "If no smoke run executed, attach the launch-manifest review result instead.",
            ],
            allowed_claim="Smoke-scope provenance and control-plane wiring are ready for candidate-search dispatch.",
            forbidden_claim="Any gene, locus, cluster, expression module, or synteny relationship has been discovered.",
            complexity="small",
        ),
        "candidate_launch": IssueSpec(
            key="candidate_launch",
            wave=4,
            slug="CANDIDATE-SEARCH",
            summary=f"Prepare the provider-neutral candidate-search milestone using provider class {provider_class} and return only small summaries.",
            agent_role="Candidate discovery agent. Run or stage homology/domain search in the configured provider workdir and emit reviewable summaries.",
            inputs=[
                (campaign_path, "campaign contract"),
                (data_ledger, "remote data ledger"),
                (query_ledger, "query seed ledger"),
                (resource_ledger, "resource/license ledger"),
            ],
            acceptance=[
                "candidate_search launch-manifest.json passes GeneCluster preflight",
                "remote or configured-workdir run writes candidate_hits.tsv, candidate-ranking.tsv, evidence.jsonl, provenance.jsonl, versions.json, and licenses.tsv",
                "large_artifacts_remote_only lists raw inputs, databases, and workflow workdirs outside the repo",
                "local return contains only summaries, manifests, compact reports, and spreadsheets",
            ],
            validation=launch_validation(
                ctx,
                run_scope="candidate_search",
                run_id="genecluster-candidate-search-dry-run",
                out=".runtime/genecluster-launch-candidate-search",
            ),
            touched_areas=[("remote:/workspace/genecluster/runs/genecluster-candidate-search-dry-run/", "remote or provider-managed candidate-search workdir")],
            blocked_by=["smoke_review"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "genome_localized", "review_required"],
            expected_outputs=[
                "data/candidate_hits.tsv",
                "data/candidate-ranking.tsv",
                "data/evidence.jsonl",
                "data/provenance.jsonl",
                "data/versions.json",
                "data/licenses.tsv",
                "dossier-manifest.json",
            ],
            artifact_contract=[
                "candidate_hits.tsv must use GeneCluster candidate-hit columns and review statuses.",
                "evidence.jsonl must link every candidate claim to source artifacts and confidence.",
                "provenance.jsonl must record command, database, version, provider class, and remote workdir pointer.",
            ],
            review_gate=[
                "Reviewer confirms broad-family hits are marked needs-human-review unless corroborated.",
                "Reviewer rejects product-level claims that lack metabolomics or functional assay evidence.",
            ],
            handoff_notes=[
                "Genome-context, coexpression, and synteny agents consume candidate_id, query_id, dataset_id, and evidence ids from this output.",
                "Do not hand off raw FASTA, BLAST databases, or assemblies through Linear.",
            ],
            allowed_claim="Remote or configured-workdir candidate-search summaries exist and are ready for dossier review.",
            forbidden_claim="Candidate hits are accepted biological conclusions or experimentally validated pathway genes.",
            complexity="medium",
        ),
        "candidate_dossier_review": IssueSpec(
            key="candidate_dossier_review",
            wave=5,
            slug="CANDIDATE-DOSSIER-REVIEW",
            summary="Validate the candidate-search dossier and claim boundaries after candidate-search output is available.",
            agent_role="Candidate dossier reviewer. Check artifact integrity, traceability, and claim separation before any context-specific lane proceeds.",
            inputs=[("genecluster-dossier/dossier-manifest.json", "candidate-search dossier manifest")],
            acceptance=[
                "dossier-manifest.json passes GeneCluster preflight",
                "candidate_hits.tsv and candidate-ranking.tsv rows trace to evidence.jsonl and provenance.jsonl",
                "claim-ledger.md separates candidate genes from physical cluster claims",
                "review statuses are assigned for broad-family, incomplete, paralog, homeolog, and transcript-only risks",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --dossier-manifest genecluster-dossier/dossier-manifest.json \\
  --candidate-hits genecluster-dossier/data/candidate_hits.tsv \\
  --candidate-ranking genecluster-dossier/data/candidate-ranking.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --provenance-jsonl genecluster-dossier/data/provenance.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/", "small returned candidate-search dossier artifacts")],
            blocked_by=["candidate_launch"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "genome_localized", "review_required"],
            expected_outputs=[
                "dossier-manifest.json",
                "claim-ledger.md",
                "data/candidate_hits.tsv",
                "data/candidate-ranking.tsv",
                "data/export.xlsx",
            ],
            artifact_contract=[
                "Dossier manifest must list all small artifacts and remote-only large artifact pointers.",
                "Claim ledger must contain Allowed claims, Forbidden overclaims, and Validation caveats sections.",
            ],
            review_gate=[
                "Reviewer decides whether candidate evidence is strong enough to activate genome-context, coexpression, or synteny lanes.",
                "Reviewer captures rejected and needs-rerun candidates instead of silently dropping them.",
            ],
            handoff_notes=[
                "Downstream context lanes should consume the reviewed dossier, not the provider workdir directly.",
                "Accepted and rejected candidate ids remain part of the scientific ledger.",
            ],
            allowed_claim="The candidate-search dossier is internally consistent and ready for human scientific review.",
            forbidden_claim="The pathway has been completed, product chemistry has been proven, or candidates are experimentally validated.",
            complexity="medium",
        ),
        "workflow_class_readiness": IssueSpec(
            key="workflow_class_readiness",
            wave=5,
            slug="WORKFLOW-CLASS-READINESS",
            summary="Validate the broad workflow-class contract so harder GeneCluster requests route through explicit activation and claim gates.",
            agent_role="Workflow-class planner. Inspect workflow-class-plan, lane activation, evidence escalation, claim levels, and deferred-lane ledgers before downstream workers fan out.",
            inputs=[
                ("genecluster-launch/workflow-class-plan.json", "workflow class activation contract"),
                ("genecluster-launch/lane-activation-plan.json", "activated/deferred/blocked lane matrix"),
                ("genecluster-launch/evidence-escalation-plan.json", "claim-safe evidence escalation rules"),
            ],
            acceptance=[
                "workflow-class-plan.json includes all supported GeneCluster workflow classes",
                "lane-activation-plan.json has explicit activated, blocked, and deferred lanes with reasons",
                "claim-levels.tsv separates candidate, genome-localized, neighborhood, pathway, and validated-elsewhere claims",
                "workflow-deferred-lanes.tsv records budget/data deferrals instead of silently dropping lanes",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --workflow-class-plan genecluster-launch/workflow-class-plan.json \\
  --lane-activation-plan genecluster-launch/lane-activation-plan.json \\
  --evidence-escalation-plan genecluster-launch/evidence-escalation-plan.json \\
  --claim-levels genecluster-launch/claim-levels.tsv \\
  --workflow-deferred-lanes genecluster-launch/workflow-deferred-lanes.tsv""",
            touched_areas=[
                ("genecluster-launch/workflow-class-plan.json", "workflow class plan"),
                ("genecluster-launch/lane-activation-plan.json", "lane activation plan"),
                ("genecluster-launch/evidence-escalation-plan.json", "evidence escalation plan"),
                ("genecluster-launch/claim-levels.tsv", "claim-level contract"),
                ("genecluster-launch/workflow-deferred-lanes.tsv", "deferred workflow lane ledger"),
            ],
            blocked_by=["candidate_dossier_review"],
            evidence_classes=["review_required"],
            expected_outputs=[
                "workflow-class-plan.json",
                "lane-activation-plan.json",
                "evidence-escalation-plan.json",
                "claim-levels.tsv",
                "workflow-deferred-lanes.tsv",
            ],
            artifact_contract=[
                "Workflow class artifacts are planning summaries only; no raw sequence or database files are included.",
                "Deferred lanes remain visible to downstream agents as caveats and possible rerun branches.",
            ],
            review_gate=[
                "Reviewer confirms low-ROI lanes are opt-in or deferred by budget.",
                "Reviewer blocks any issue that upgrades evidence without satisfying the escalation plan.",
            ],
            handoff_notes=[
                "Use this issue as the routing table for long-read isoform, transcriptome-only, copy, expression, synteny, PAV/SV, graph, and single-cell/spatial subworkers.",
                "The activated lane list guides worker dispatch; blocked/deferred lanes guide caveats and next-run planning.",
            ],
            allowed_claim="The campaign has a validated workflow-class routing contract.",
            forbidden_claim="All workflow classes have been executed or produced biological evidence.",
            complexity="medium",
        ),
        "genome_context": IssueSpec(
            key="genome_context",
            wave=6,
            slug="GENOME-CONTEXT",
            summary="Review genome/GFF resources and candidate coordinates before any physical neighborhood claim is made.",
            agent_role="Genome-context agent. Anchor candidates to genome coordinates, extract local neighborhoods, and classify coordinate support.",
            inputs=[
                ("genecluster-dossier/data/candidate_hits.tsv", "reviewed candidate table"),
                (data_ledger, "approved data and reference ledger"),
            ],
            acceptance=[
                "cluster_neighborhoods.tsv passes GeneCluster preflight",
                "every neighborhood-supported row has candidate_id, anchor_gene_id, coordinate_status, evidence_ids, and review_status",
                "transcript-only candidates remain transcript_only or unknown, not genome_localized",
                "claim-ledger.md preserves physical-cluster caveats and boundary evidence requirements",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --cluster-neighborhoods genecluster-dossier/data/cluster_neighborhoods.tsv \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/data/cluster_neighborhoods.tsv", "reviewed genome neighborhood summary")],
            blocked_by=["candidate_dossier_review"],
            evidence_classes=["genome_localized", "neighborhood_supported", "review_required"],
            expected_outputs=["data/cluster_neighborhoods.tsv", "claim-ledger.md"],
            artifact_contract=[
                "Neighborhood rows must cite coordinate status and evidence ids rather than raw genome files.",
                "Genome assemblies, GFFs, and indexes remain provider-managed or remote-only.",
            ],
            review_gate=[
                "Reviewer confirms a physical-cluster claim cites genome coordinates and boundary logic.",
                "Reviewer rejects transcriptome-only rows that imply physical clustering.",
            ],
            handoff_notes=[
                "Synteny agents may use only genome_localized candidates with reviewed coordinate evidence.",
                "Coexpression agents may include transcript-only candidates but must not infer physical neighborhoods from expression.",
            ],
            allowed_claim="Genome-localized candidates and reviewed local-neighborhood hypotheses are available for downstream evidence integration.",
            forbidden_claim="Transcript hits alone define a physical gene cluster or cluster boundary.",
            complexity="medium",
        ),
        "coexpression": IssueSpec(
            key="coexpression",
            wave=7,
            slug="COEXPRESSION",
            summary="Add expression and coexpression evidence without converting expression support into cluster proof.",
            agent_role="Coexpression agent. Normalize expression summaries, compute or import module support, and connect expression edges to candidate ids.",
            inputs=[
                ("genecluster-dossier/data/candidate_hits.tsv", "reviewed candidate table"),
                (data_ledger, "approved transcriptome/sample ledger"),
            ],
            acceptance=[
                "coexpression_edges.tsv is present as a small summary artifact",
                "candidate-ranking.tsv records expression or module support without overwriting homology/domain evidence",
                "evidence.jsonl includes coexpression_supported records with confidence and review_status",
                "claim-ledger.md states that coexpression does not prove physical clustering or product chemistry",
            ],
            validation="""test -f genecluster-dossier/data/coexpression_edges.tsv
python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --candidate-ranking genecluster-dossier/data/candidate-ranking.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/data/coexpression_edges.tsv", "small coexpression evidence summary")],
            blocked_by=["candidate_dossier_review"],
            evidence_classes=["coexpression_supported", "transcript_hit", "review_required"],
            expected_outputs=["data/coexpression_edges.tsv", "data/candidate-ranking.tsv", "data/evidence.jsonl", "claim-ledger.md"],
            artifact_contract=[
                "coexpression_edges.tsv must include candidate ids, sample or module ids, edge weight, method, and provenance ids.",
                "Expression matrices, alignments, and count workdirs remain remote-only unless explicitly approved outside the repo.",
            ],
            review_gate=[
                "Reviewer checks that tissue/sample metadata supports the biological comparison being claimed.",
                "Reviewer downgrades coexpression-only claims when sample count, tissue coverage, or normalization is weak.",
            ],
            handoff_notes=[
                "Ranking agents may use coexpression as support, not as standalone pathway validation.",
                "Next-experiment agents should turn weak expression support into sample-design recommendations.",
            ],
            allowed_claim="Expression or coexpression support is available for candidate prioritization.",
            forbidden_claim="Coexpression proves enzyme function, product chemistry, or physical gene clustering.",
            complexity="medium",
        ),
        "synteny": IssueSpec(
            key="synteny",
            wave=8,
            slug="SYNTENY",
            summary="Add orthology and synteny support for reviewed genome-localized candidates.",
            agent_role="Synteny agent. Compare reviewed loci across references or relatives and summarize conserved neighborhoods.",
            inputs=[
                ("genecluster-dossier/data/cluster_neighborhoods.tsv", "reviewed genome-neighborhood table"),
                ("genecluster-dossier/data/candidate_hits.tsv", "reviewed candidate table"),
            ],
            acceptance=[
                "synteny_blocks.tsv is present as a small summary artifact",
                "orthogroups.tsv is present when orthology inference was used",
                "evidence.jsonl links synteny evidence to candidate_id and neighborhood_cluster_id",
                "claim-ledger.md separates synteny support from experimental validation",
            ],
            validation="""test -f genecluster-dossier/data/synteny_blocks.tsv
test -f genecluster-dossier/data/orthogroups.tsv
python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/data/synteny_blocks.tsv", "small synteny evidence summary")],
            blocked_by=["genome_context"],
            evidence_classes=["genome_localized", "neighborhood_supported", "review_required"],
            expected_outputs=["data/synteny_blocks.tsv", "data/orthogroups.tsv", "data/evidence.jsonl", "claim-ledger.md"],
            artifact_contract=[
                "Synteny rows must reference reviewed genome coordinates and remote-only source artifacts.",
                "Orthology and synteny commands, database versions, and species/reference IDs must be recorded in provenance.",
            ],
            review_gate=[
                "Reviewer confirms synteny support is not inferred for unlocalized transcript-only candidates.",
                "Reviewer flags lineage expansion, assembly fragmentation, or paralogy as caveats.",
            ],
            handoff_notes=[
                "Full public-mining audit should integrate synteny as context evidence, not final pathway proof.",
                "Next-experiment design should use synteny gaps to prioritize DNA-seq or reference improvement only when justified.",
            ],
            allowed_claim="Synteny or conserved-neighborhood support exists for reviewed genome-localized candidates.",
            forbidden_claim="Synteny alone proves pathway membership, metabolite product, or enzyme function.",
            complexity="medium",
        ),
        "public_mining_audit": IssueSpec(
            key="public_mining_audit",
            wave=9,
            slug="PUBLIC-MINING-AUDIT",
            summary="Audit the complete public-mining dossier across candidate search, genome context, coexpression, and synteny lanes.",
            agent_role="Scientific claim auditor. Integrate all public evidence lanes and enforce claim-level boundaries before handoff.",
            inputs=[("genecluster-dossier/dossier-manifest.json", "public-mining dossier manifest")],
            acceptance=[
                "dossier-manifest.json passes GeneCluster preflight",
                "candidate-ranking.tsv rows trace to evidence.jsonl and provenance.jsonl",
                "claim-ledger.md lists allowed claims, forbidden overclaims, validation caveats, and rejected claims",
                "dossier separates transcript candidates, genome-localized candidates, neighborhood-supported candidates, and review-required candidates",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --dossier-manifest genecluster-dossier/dossier-manifest.json \\
  --candidate-hits genecluster-dossier/data/candidate_hits.tsv \\
  --candidate-ranking genecluster-dossier/data/candidate-ranking.tsv \\
  --cluster-neighborhoods genecluster-dossier/data/cluster_neighborhoods.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --provenance-jsonl genecluster-dossier/data/provenance.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/", "small returned public-mining dossier artifacts")],
            blocked_by=["coexpression", "synteny"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "genome_localized", "neighborhood_supported", "coexpression_supported", "review_required"],
            expected_outputs=["dossier-manifest.json", "data/candidate-ranking.tsv", "data/evidence.jsonl", "data/provenance.jsonl", "claim-ledger.md"],
            artifact_contract=[
                "Every claim in claim-ledger.md must link to evidence ids and source artifacts.",
                "Dossier manifest must include only small local summaries and remote pointers for large artifacts.",
            ],
            review_gate=[
                "Reviewer decides which candidates are accepted, rejected, needs-rerun, or next-experiment candidates.",
                "Reviewer blocks publication-candidate status until evidence and license caveats are resolved.",
            ],
            handoff_notes=[
                "Next-experiment design consumes accepted, rejected, and unresolved claim lists from this audit.",
                "Provider reruns should be opened as separate bounded issues with exact artifact deltas.",
            ],
            allowed_claim="The public-mining dossier is internally reviewable and ready for human scientific decisions.",
            forbidden_claim="The pathway has been experimentally validated or product-level chemistry has been proven.",
            complexity="medium",
        ),
        "next_experiment_design": IssueSpec(
            key="next_experiment_design",
            wave=10,
            slug="NEXT-EXPERIMENT-DESIGN",
            summary="Convert public-mining evidence gaps into sequencing, metabolomics, and enzyme-validation experiment options.",
            agent_role="Next-experiment designer. Produce a vendor/lab-ready plan that is explicitly derived from dossier gaps and claim limits.",
            inputs=[
                ("genecluster-dossier/claim-ledger.md", "accepted, rejected, and unresolved claim ledger"),
                ("genecluster-dossier/data/candidate-ranking.tsv", "reviewed candidate ranking"),
                ("genecluster-dossier/data/evidence.jsonl", "evidence ledger"),
            ],
            acceptance=[
                "next-experiment-brief.md separates RNA-seq, DNA-seq/reference, metabolomics, and enzyme-validation recommendations",
                "each proposed experiment maps to an unresolved claim or evidence gap",
                "controlled/private sequence or material handling requirements are flagged before vendor-facing output",
                "candidate-discovery experiments are separated from biochemical validation experiments",
            ],
            validation="""test -f genecluster-dossier/next-experiment-brief.md
python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --candidate-ranking genecluster-dossier/data/candidate-ranking.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/next-experiment-brief.md", "next-experiment planning brief")],
            blocked_by=["public_mining_audit"],
            evidence_classes=["review_required"],
            expected_outputs=["next-experiment-brief.md"],
            artifact_contract=[
                "Brief must include experiment objective, input material, assay or sequencing scope, acceptance criteria, and claim unlocked.",
                "No private sequences, sample identifiers, or vendor credentials are embedded in Linear.",
            ],
            review_gate=[
                "Reviewer confirms public data gaps justify new data generation.",
                "Reviewer confirms validation experiments are not presented as already performed.",
            ],
            handoff_notes=[
                "Use this issue as the handoff to wet-lab, sequencing, vendor, or grant-planning workflows.",
                "Open separate execution issues for any experiment that requires private material or spend approval.",
            ],
            allowed_claim="A next-experiment plan has been derived from reviewed public-data evidence gaps.",
            forbidden_claim="Any proposed experiment has been run, funded, approved, or validated.",
            complexity="medium",
        ),
        "full_launch_bundle": IssueSpec(
            key="full_launch_bundle",
            wave=5,
            slug="FULL-CAMPAIGN-BUNDLE",
            summary=f"Generate and validate the full Coptis launch-ready bundle for provider class {provider_class} without launching compute.",
            agent_role="Full-campaign coordinator. Stage all remote lanes for Coptis public mining while keeping execution and credentials under operator control.",
            inputs=[
                (campaign_path, "campaign contract"),
                (data_ledger, "remote data ledger"),
                (query_ledger, "query seed ledger"),
                (resource_ledger, "resource/license ledger"),
            ],
            acceptance=[
                "full_campaign launch-manifest.json passes GeneCluster preflight",
                "launch manifest lists all full-run lanes and expected small artifacts",
                "provider notes report missing credentials without exposing secret values",
                "large local downloads remain disabled and raw artifacts remain outside the repo",
            ],
            validation=launch_validation(
                ctx,
                run_scope="full_campaign",
                run_id="genecluster-Coptis-full-dry-run",
                out=".runtime/genecluster-launch-full-campaign",
            ),
            touched_areas=[(".runtime/genecluster-launch-full-campaign/", "local ignored full-run launch-prep bundle")],
            blocked_by=["candidate_dossier_review"],
            evidence_classes=["review_required"],
            expected_outputs=["launch-manifest.json", "run-later.sh", "README.md"],
            artifact_contract=[
                "Launch manifest must enumerate full-run lanes, expected small artifacts, and remote-only large artifact policy.",
                "The bundle is a control-plane artifact and must not imply compute has run.",
            ],
            review_gate=[
                "Reviewer confirms provider credentials, budget, storage, and artifact sync policy before launch-ready status.",
                "Reviewer confirms optional lanes can be skipped only with claim caveats preserved.",
            ],
            handoff_notes=[
                "After execution, downstream review lanes consume the returned dossier artifacts.",
                "If the provider class changes, regenerate this bundle instead of editing launch-manifest.json manually.",
            ],
            allowed_claim="The full Coptis run is launch-prepared and ready for operator credential/provider review.",
            forbidden_claim="The full run has executed or produced biological candidate conclusions.",
            complexity="medium",
        ),
        "full_campaign_audit": IssueSpec(
            key="full_campaign_audit",
            wave=11,
            slug="FULL-CAMPAIGN-AUDIT",
            summary="Audit the full Coptis dossier for evidence ranking, overclaims, and next-experiment readiness.",
            agent_role="Full-campaign claim auditor. Review all returned Coptis public-mining artifacts against the campaign caveats.",
            inputs=[("genecluster-dossier/dossier-manifest.json", "full-run dossier manifest")],
            acceptance=[
                "dossier-manifest.json passes GeneCluster preflight",
                "candidate-ranking.tsv rows trace to evidence.jsonl and provenance.jsonl",
                "next-experiment-brief.md separates sequencing, metabolomics, and biochemical validation gaps",
                "claim-ledger.md preserves unresolved native 9-hydroxylase and 9-OMT caveats",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --dossier-manifest genecluster-dossier/dossier-manifest.json \\
  --candidate-hits genecluster-dossier/data/candidate_hits.tsv \\
  --candidate-ranking genecluster-dossier/data/candidate-ranking.tsv \\
  --cluster-neighborhoods genecluster-dossier/data/cluster_neighborhoods.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --provenance-jsonl genecluster-dossier/data/provenance.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/", "small returned full Coptis dossier artifacts")],
            blocked_by=["full_launch_bundle", "genome_context", "coexpression", "synteny"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "genome_localized", "neighborhood_supported", "coexpression_supported", "review_required"],
            expected_outputs=["dossier-manifest.json", "data/candidate-ranking.tsv", "claim-ledger.md", "next-experiment-brief.md"],
            artifact_contract=[
                "Full dossier must include candidate, genome-context, synteny, coexpression, provenance, license, citation, and claim artifacts.",
                "Every high-level claim must cite evidence ids and state whether it is candidate, pathway_hypothesis, cluster_hypothesis, or validated_elsewhere.",
            ],
            review_gate=[
                "Reviewer blocks final acceptance when product claims exceed public evidence.",
                "Reviewer records which evidence gaps should become next-experiment issues.",
            ],
            handoff_notes=[
                "Use this audit as the final public-data handoff for Coptis v0.",
                "Publication-facing or wet-lab claims require separate human approval and supporting experiments.",
            ],
            allowed_claim="The full Coptis dossier is internally reviewable and ready for human scientific decisions.",
            forbidden_claim="the target pathway has been proven in planta by this workflow.",
            complexity="medium",
        ),
        "full_24h_launch_bundle": IssueSpec(
            key="full_24h_launch_bundle",
            wave=5,
            slug="FULL-CAMPAIGN-24H-BUNDLE",
            summary=f"Generate and validate the one-day complete campaign launch-ready bundle for provider class {provider_class} without launching compute.",
            agent_role="One-day full-campaign coordinator. Stage a reference-first, cache-first Coptis run that must complete a summary dossier inside the 24-hour runtime budget.",
            inputs=[
                (campaign_path, "campaign contract"),
                (data_ledger, "remote data ledger"),
                (query_ledger, "query seed ledger"),
                (resource_ledger, "resource/license ledger"),
            ],
            acceptance=[
                "full_campaign_24h launch-manifest.json passes GeneCluster preflight",
                "runner command includes --max-runtime-hours 24",
                "launch manifest contains runtime_policy and deferred-lanes.json in expected artifacts",
                "large local downloads remain disabled and raw artifacts remain outside the repo",
            ],
            validation=launch_validation(
                ctx,
                run_scope="full_campaign_24h",
                run_id="genecluster-Coptis-full-24h-dry-run",
                out=".runtime/genecluster-launch-full-campaign-24h",
            ),
            touched_areas=[(".runtime/genecluster-launch-full-campaign-24h/", "local ignored one-day full-run launch-prep bundle")],
            blocked_by=["candidate_dossier_review"],
            evidence_classes=["review_required"],
            expected_outputs=["launch-manifest.json", "run-later.sh", "README.md"],
            artifact_contract=[
                "Launch manifest must encode the 24-hour runtime budget, lane degradation order, expected small artifacts, and remote-only large artifact policy.",
                "The bundle is a control-plane artifact and must not imply compute has run.",
            ],
            review_gate=[
                "Reviewer confirms the 24-hour profile defers optional max databases and de novo assembly unless explicitly overridden.",
                "Reviewer confirms the run can finish with caveats rather than extending runtime.",
            ],
            handoff_notes=[
                "After execution, downstream review consumes the returned complete dossier and deferred-lane manifest.",
                "Escalate to open-ended full_campaign only after this dossier shows a specific evidence gap worth a multi-day run.",
            ],
            allowed_claim="The one-day Coptis full run is launch-prepared and ready for operator credential/provider review.",
            forbidden_claim="The one-day full run has executed or produced biological candidate conclusions.",
            complexity="medium",
        ),
        "full_24h_audit": IssueSpec(
            key="full_24h_audit",
            wave=11,
            slug="FULL-CAMPAIGN-24H-AUDIT",
            summary="Audit the one-day Coptis dossier, including deferred lanes, overclaims, and next-run escalation criteria.",
            agent_role="One-day full-campaign claim auditor. Review returned artifacts against the runtime budget and campaign caveats.",
            inputs=[("genecluster-dossier/dossier-manifest.json", "one-day full-run dossier manifest")],
            acceptance=[
                "dossier-manifest.json passes GeneCluster preflight",
                "deferred-lanes.json explains every lane not used as evidence",
                "claim-ledger.md preserves unresolved native 9-hydroxylase and 9-OMT caveats",
                "next-experiment-brief.md separates evidence gaps from validated claims",
            ],
            validation="""python3 skills/biosymphony/scripts/genecluster_preflight.py \\
  --dossier-manifest genecluster-dossier/dossier-manifest.json \\
  --candidate-hits genecluster-dossier/data/candidate_hits.tsv \\
  --cluster-neighborhoods genecluster-dossier/data/cluster_neighborhoods.tsv \\
  --evidence-jsonl genecluster-dossier/data/evidence.jsonl \\
  --provenance-jsonl genecluster-dossier/data/provenance.jsonl \\
  --claim-ledger genecluster-dossier/claim-ledger.md""",
            touched_areas=[("genecluster-dossier/", "small returned one-day full Coptis dossier artifacts")],
            blocked_by=["full_24h_launch_bundle", "genome_context"],
            evidence_classes=["transcript_hit", "protein_hit", "domain_hit", "genome_localized", "neighborhood_supported", "review_required"],
            expected_outputs=["dossier-manifest.json", "deferred-lanes.json", "claim-ledger.md", "next-experiment-brief.md"],
            artifact_contract=[
                "One-day dossier must be complete even when optional lanes are deferred by budget.",
                "Deferred lanes must be represented as caveats, not silently omitted evidence.",
            ],
            review_gate=[
                "Reviewer blocks final acceptance when product claims exceed the one-day evidence.",
                "Reviewer records exactly which deferred lane, if any, justifies a later multi-day run.",
            ],
            handoff_notes=[
                "Use this audit as the default final handoff for the first Coptis v0 full run.",
                "Open-ended full_campaign is an escalation path, not the default first full run.",
            ],
            allowed_claim="The one-day Coptis dossier is internally reviewable and ready for human scientific decisions.",
            forbidden_claim="the target pathway has been proven in planta by this workflow.",
            complexity="medium",
        ),
    }


SCOPE_PLANS: dict[str, list[str]] = {
    "smoke": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
    ],
    "candidate_search": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
    ],
    "genome_context": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "genome_context",
    ],
    "coexpression": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "coexpression",
    ],
    "synteny": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "genome_context",
        "synteny",
    ],
    "full_public_mining": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "genome_context",
        "coexpression",
        "synteny",
        "public_mining_audit",
    ],
    "next_experiment_design": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "genome_context",
        "coexpression",
        "synteny",
        "public_mining_audit",
        "next_experiment_design",
    ],
    "full_campaign": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "full_launch_bundle",
        "genome_context",
        "coexpression",
        "synteny",
        "public_mining_audit",
        "full_campaign_audit",
        "next_experiment_design",
    ],
    "full_campaign_24h": [
        "contract_gate",
        "data_gate",
        "query_gate",
        "resource_gate",
        "smoke_bundle",
        "smoke_review",
        "candidate_launch",
        "candidate_dossier_review",
        "workflow_class_readiness",
        "full_24h_launch_bundle",
        "genome_context",
        "coexpression",
        "synteny",
        "public_mining_audit",
        "full_24h_audit",
        "next_experiment_design",
    ],
}


def build_issues(campaign_path: Path, label_prefix: str, run_scope: str = "candidate_search") -> dict[str, str]:
    if run_scope not in SCOPE_PLANS:
        raise ValueError(f"unknown run_scope: {run_scope}")

    ctx = campaign_context(campaign_path)
    catalog = issue_catalog(ctx)
    selected_keys = SCOPE_PLANS[run_scope]
    issue_ids_by_key = {
        key: issue_id(label_prefix, catalog[key].wave, catalog[key].slug)
        for key in selected_keys
    }
    missing_deps = sorted(
        {dep for key in selected_keys for dep in catalog[key].blocked_by if dep not in issue_ids_by_key}
    )
    if missing_deps:
        raise ValueError(f"run_scope {run_scope} has missing dependencies: {', '.join(missing_deps)}")

    return {
        issue_ids_by_key[key]: make_issue(catalog[key], issue_ids_by_key)
        for key in selected_keys
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate GeneCluster dry-run Linear issue bodies.")
    parser.add_argument("--campaign", type=Path, required=True, help="Campaign manifest JSON.")
    parser.add_argument("--out", type=Path, required=True, help="Output issue directory.")
    parser.add_argument("--label-prefix", default="GENECLUSTER-MIT", help="Issue id prefix.")
    parser.add_argument("--run-scope", choices=RUN_SCOPES, default="candidate_search")
    args = parser.parse_args()

    issues = build_issues(args.campaign, args.label_prefix, args.run_scope)
    args.out.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for iid, body in issues.items():
        result = validate_issue(body)
        if not result["ok"]:
            failures.append(f"{iid}: {result['errors']}")
        (args.out / f"{iid}.md").write_text(body, encoding="utf-8")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 5
    print(json.dumps({"ok": True, "run_scope": args.run_scope, "issues": sorted(issues)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
