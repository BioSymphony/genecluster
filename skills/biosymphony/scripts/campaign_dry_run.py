#!/usr/bin/env python3
"""Generate per-wave Linear issue bodies for the Mechanistic Variant Atlas.

This is the dry-run generator. It reads variants.yaml + claims.yaml and
emits a directory of Linear-ready issue bodies, one per issue, plus a
DAG file describing blocker relationships.

Every emitted body conforms to references/contract-template.md and is
validated by preflight_check.py before the script exits successfully.

Usage:
    python3 campaign_dry_run.py \\
        --variants  examples/egfr-resistance-v1/variants.yaml \\
        --claims    examples/egfr-resistance-v1/claims.yaml \\
        --out       dry-run/ \\
        --label-prefix MVA-EGFR

Exit codes:
    0 success, every body passed preflight
    1 usage / file error
    2 missing dependency
    5 preflight failure on at least one emitted body
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lib.load_yaml import load_yaml  # noqa: E402

PREFLIGHT = SCRIPT_DIR / "preflight_check.py"

WAVE4_METRICS = [
    ("contact_diff", "contact_diff.py"),
    ("gatekeeper_distance", "gatekeeper_distance.py"),
    ("hbond_diff", "hbond_diff.py"),
    ("pocket_geometry", "pocket_geometry.py"),
]

WAVE6_FAMILIES = [
    ("active_site", "active-site disruption", "close-up + interaction diff"),
    ("allosteric", "allosteric", "pocket shape + αC-helix orientation"),
    ("stability", "stability", "local backbone + hbond network"),
    ("compensatory", "compensatory", "pathway / network analysis"),
    ("ambiguous", "ambiguous", "evidence pack with deferred classification"),
]

SCHEMA_BLOCK = """\
<!-- symphony:schema
schema_version: 1
touched_areas:
{touched_areas_yaml}
complexity: {complexity}
-->"""

RISK_BOILERPLATE = """\
- Do not store private patient identifiers, unpublished sequences, or secret literature in this artifact.
- Record caveats for predicted structures, mutagenized fallbacks, and rendering assumptions in the issue's outcome comment."""


def issue_id(label_prefix: str, wave: int, slug: str) -> str:
    return f"{label_prefix}-W{wave:02d}-{slug}"


def render_schema_block(touched_areas: list[str], complexity: str) -> str:
    yaml_lines = "\n".join(f"  - {p}" for p in touched_areas)
    return SCHEMA_BLOCK.format(touched_areas_yaml=yaml_lines, complexity=complexity)


def make_issue_body(
    *,
    summary: str,
    inputs: list[tuple[str, str]],
    acceptance: list[str],
    validation_commands: str,
    touched_areas: list[tuple[str, str]],
    blocked_by: list[str] | None,
    complexity: str,
    risk_notes: str = RISK_BOILERPLATE,
) -> str:
    """Assemble a contract-conformant issue body."""
    inputs_lines = "\n".join(f"- `{i}` - {desc}" for i, desc in inputs)
    accept_lines = "\n".join(f"- [ ] {item}" for item in acceptance)
    touched_lines = "\n".join(f"- `{p}` - {why}" for p, why in touched_areas)
    deps = (
        "\n".join(f"Blocked by: {b}" for b in blocked_by)
        if blocked_by
        else "Blocked by: none"
    )
    schema = render_schema_block([p for p, _ in touched_areas], complexity)

    body = f"""## Summary

{summary}

## Inputs

{inputs_lines}

## Acceptance Criteria

{accept_lines}

## Validation Commands

```bash
{validation_commands.strip()}
```

## Touched Areas

{touched_lines}

## Dependencies

{deps}

## Risk Notes

{risk_notes}

## Orchestration Guardrails

- Prompt render preflight must prove this issue body is non-empty and contains no unresolved template tags.
- Provider payload preflight is required before any cloud or remote API call; record payload byte size in the worker closeout.
- Snapshot preflight must prove required scripts and inputs exist in the Git ref or workspace the worker actually uses.
- Silent fallback to a different worker, team, provider, or execution mode is a hard stop.

## Resume / Recovery Contract

- Checkpoint: write the last confirmed artifact path and validation command in the Linear closeout comment.
- Resume command: rerun the validation commands above from the repo root after checking the checkpoint artifacts.
- Degraded recovery: if the worker recovers missing prompt, issue, provider, or snapshot state, mark the issue degraded and explain the recovered source.
- Wakeups must rerun prompt, payload, and snapshot diagnostics before retrying a failed action.

## Complexity

tier: {complexity}

{schema}
"""
    return body


# ---------------------------------------------------------------------------
# Wave generators
# ---------------------------------------------------------------------------


def wave1_intake(label: str, variants_path: str, claims_path: str) -> tuple[str, str]:
    iid = issue_id(label, 1, "INTAKE")
    body = make_issue_body(
        summary=(
            "Parse the curated variant list and literature-claim file into a "
            "normalized variant table for the Mechanistic Variant Atlas."
        ),
        inputs=[
            (variants_path, "curated variants with HGVS, COSMIC, drug context, phenotype"),
            (claims_path, "literature claims for the wave-10 auditor"),
        ],
        acceptance=[
            "intake/variant_table.json exists and validates the campaign's intake schema",
            "every variant in the input has a row with HGVS, drug context, phenotype, and claim references",
            "intake/intake_report.md lists per-variant counts, missing fields, and skipped entries with reasons",
        ],
        validation_commands=f"""\
python3 skills/biosymphony/scripts/campaign_intake.py \\
  --variants {variants_path} \\
  --claims {claims_path} \\
  --out intake/
python3 -c "import json; d=json.load(open('intake/variant_table.json')); assert len(d['variants'])>=8, 'too few variants'"\
""",
        touched_areas=[
            ("intake/variant_table.json", "normalized intake output"),
            ("intake/intake_report.md", "intake summary"),
        ],
        blocked_by=None,
        complexity="small",
    )
    return iid, body


def wave2_structure_mapping(
    label: str,
    variant: dict,
    intake_issue: str,
) -> tuple[str, str]:
    vid = variant["id"]
    iid = issue_id(label, 2, f"MAP-{vid}")
    body = make_issue_body(
        summary=(
            f"Query RCSB PDB and AlphaFold DB for structures relevant to variant {vid}. "
            "Build a candidate structure list with apo, holo, and TKI-bound complexes "
            "where deposited."
        ),
        inputs=[
            ("intake/variant_table.json", "normalized variant table from Wave 1"),
            (vid, "target variant identifier in the table"),
        ],
        acceptance=[
            f"mapping/{vid}/candidate_structures.json exists with at least one experimental candidate or an explicit fallback note",
            "every PDB row records resolution, ligand IDs, deposition date when available",
            f"mapping/{vid}/mapping_report.md lists what was found and what was skipped with reason",
        ],
        validation_commands=f"""\
python3 skills/biosymphony/scripts/structure_query.py \\
  --variant {vid} \\
  --table intake/variant_table.json \\
  --out mapping/{vid}/
test -f mapping/{vid}/candidate_structures.json
test -f mapping/{vid}/mapping_report.md\
""",
        touched_areas=[(f"mapping/{vid}/", "per-variant structure candidate listing")],
        blocked_by=[intake_issue],
        complexity="small",
    )
    return iid, body


def wave3_structure_ingest(
    label: str,
    variant: dict,
    mapping_issue: str,
) -> tuple[str, str]:
    vid = variant["id"]
    iid = issue_id(label, 3, f"INGEST-{vid}")
    body = make_issue_body(
        summary=(
            f"Fetch every candidate structure for variant {vid}, validate file integrity, "
            "and produce ingest-clean PDB files. Where no deposited mutant exists, run "
            "PyMOL mutate against the closest WT holo as a flagged fallback."
        ),
        inputs=[
            (f"mapping/{vid}/candidate_structures.json", "candidate structures from Wave 2"),
        ],
        acceptance=[
            f"structures/{vid}/ contains a cleaned PDB file for each accepted candidate",
            "each structure has a sidecar JSON with source, resolution, hash, and predicted vs experimental flag",
            f"structures/{vid}/ingest_report.md records any failed or skipped fetches",
        ],
        validation_commands=f"""\
test -d structures/{vid}
ls structures/{vid}/*.pdb >/dev/null 2>&1 || echo "no PDB files; check ingest_report.md"
test -f structures/{vid}/ingest_report.md\
""",
        touched_areas=[(f"structures/{vid}/", "per-variant cleaned structure files")],
        blocked_by=[mapping_issue],
        complexity="medium",
    )
    return iid, body


def wave4_metric(
    label: str,
    variant: dict,
    metric_key: str,
    ingest_issue: str,
) -> tuple[str, str]:
    vid = variant["id"]
    iid = issue_id(label, 4, f"METRIC-{vid}-{metric_key.upper()}")
    metric_specific = {
        "contact_diff": (
            "Compute residue-residue contact diff between WT and variant structures "
            "for the kinase-domain holo complexes.",
            f"""\
python3 skills/biosymphony/scripts/metrics/contact_diff.py \\
  --wt structures/{vid}/wt_holo.pdb \\
  --variant structures/{vid}/variant_holo.pdb \\
  --focus-residue A:{variant.get('residue', 0) or 0} \\
  --cutoff 5.0 \\
  --out metrics/{vid}/contact_diff.json\
""",
        ),
        "gatekeeper_distance": (
            "Compute distance and VDW overlap between the gatekeeper residue (T790 in EGFR) "
            "and bound TKI atoms.",
            f"""\
python3 skills/biosymphony/scripts/metrics/gatekeeper_distance.py \\
  --structure structures/{vid}/variant_holo.pdb \\
  --gatekeeper A:790 \\
  --ligand-resname IRE \\
  --out metrics/{vid}/gatekeeper_distance.json\
""",
        ),
        "hbond_diff": (
            "Compute heavy-atom h-bond diff between WT and variant in the binding site and "
            "kinase hinge region.",
            f"""\
python3 skills/biosymphony/scripts/metrics/hbond_diff.py \\
  --wt structures/{vid}/wt_holo.pdb \\
  --variant structures/{vid}/variant_holo.pdb \\
  --focus-residues A:790,A:858,A:792,A:797 \\
  --out metrics/{vid}/hbond_diff.json\
""",
        ),
        "pocket_geometry": (
            "Compute pocket geometry descriptors for the ATP/TKI binding cleft in WT and variant.",
            f"""\
python3 skills/biosymphony/scripts/metrics/pocket_geometry.py \\
  --wt structures/{vid}/wt_holo.pdb \\
  --variant structures/{vid}/variant_holo.pdb \\
  --pocket-residues A:719,A:721,A:722,A:743,A:745,A:790,A:854,A:855,A:856 \\
  --out metrics/{vid}/pocket_geometry.json\
""",
        ),
    }
    summary, validation = metric_specific[metric_key]
    body = make_issue_body(
        summary=f"Variant {vid}: {summary}",
        inputs=[
            (f"structures/{vid}/wt_holo.pdb", "cleaned WT holo structure from Wave 3"),
            (f"structures/{vid}/variant_holo.pdb", "cleaned variant holo structure from Wave 3"),
        ],
        acceptance=[
            f"metrics/{vid}/{metric_key}.json exists and validates against the metric schema",
            "the JSON includes a diagnostics block with method notes and any caveats",
            "any missing residue or ligand is reported as a warning, not silently dropped",
        ],
        validation_commands=validation,
        touched_areas=[(f"metrics/{vid}/{metric_key}.json", f"{metric_key} metric output")],
        blocked_by=[ingest_issue],
        complexity="small",
    )
    return iid, body


def wave5_classify(
    label: str,
    variant: dict,
    metric_issues: list[str],
) -> tuple[str, str]:
    vid = variant["id"]
    iid = issue_id(label, 5, f"CLASSIFY-{vid}")
    body = make_issue_body(
        summary=(
            f"Run the rule-based mechanism classifier on variant {vid} using its Wave 4 metrics. "
            "Output a per-drug-context classification with confidence."
        ),
        inputs=[
            (f"metrics/{vid}/contact_diff.json", "Wave 4 contact diff"),
            (f"metrics/{vid}/gatekeeper_distance.json", "Wave 4 gatekeeper metric"),
            (f"metrics/{vid}/hbond_diff.json", "Wave 4 h-bond diff"),
            (f"metrics/{vid}/pocket_geometry.json", "Wave 4 pocket geometry"),
        ],
        acceptance=[
            f"classification/{vid}/classification.json exists with a per-drug-context mechanism call",
            "confidence is in [0.0, 1.0]",
            "if the top-2 confidence margin is under 0.1, the classification is ambiguous",
            f"classification/{vid}/rationale.md explains which metric drove the call",
        ],
        validation_commands=f"""\
python3 skills/biosymphony/scripts/classify_mechanism.py \\
  --variant {vid} \\
  --metrics-dir metrics/{vid}/ \\
  --out classification/{vid}/
test -f classification/{vid}/classification.json
python3 -c "import json; d=json.load(open('classification/{vid}/classification.json')); assert 'mechanism' in d, 'missing mechanism call'"\
""",
        touched_areas=[(f"classification/{vid}/", "per-variant mechanism classification")],
        blocked_by=metric_issues,
        complexity="medium",
    )
    return iid, body


def wave6_template(
    label: str,
    family_key: str,
    family_name: str,
    family_render: str,
) -> tuple[str, str]:
    """Generic template for Wave 6, instantiated per variant after Wave 5 routes."""
    iid = issue_id(label, 6, f"PANEL-{family_key.upper()}-TEMPLATE")
    body = make_issue_body(
        summary=(
            f"Render the {family_name} evidence panel for a variant routed to this family by Wave 5. "
            f"Panel content: {family_render}."
        ),
        inputs=[
            (
                f"classification/<variant_id>/classification.json",
                f"Wave 5 classification with mechanism = {family_key}",
            ),
            ("structures/<variant_id>/", "cleaned structures from Wave 3"),
            ("metrics/<variant_id>/", "Wave 4 metrics that drove the classification"),
        ],
        acceptance=[
            f"figure-dossier/panels/<variant_id>_{family_key}.png exists, 2200x1700 minimum, nonblank",
            f"figure-dossier/panels/<variant_id>_{family_key}.json sidecar lists the exact metrics annotated",
            f"figure-dossier/sessions/<variant_id>_{family_key}.pse or .cxs is saved",
        ],
        validation_commands=f"""\
ls figure-dossier/panels/*_{family_key}.png >/dev/null 2>&1 && echo "{family_key} panels present"
ls figure-dossier/sessions/*_{family_key}.* >/dev/null 2>&1 && echo "{family_key} sessions present"
test -f figure-dossier/figure_manifest.json\
""",
        touched_areas=[
            (f"figure-dossier/panels/", f"{family_name} panels"),
            (f"figure-dossier/sessions/", f"saved {family_name} sessions"),
        ],
        blocked_by=[issue_id(label, 5, "ALL")],  # placeholder; runner expands per-variant
        complexity="medium",
    )
    return iid, body


def wave7_synthesis(label: str, classify_issues: list[str]) -> tuple[str, str]:
    iid = issue_id(label, 7, "SYNTHESIS")
    body = make_issue_body(
        summary=(
            "Hold all per-variant Wave 5/6 outputs together and produce campaign-level "
            "patterns: mechanism distribution, co-occurrence, resistance pathway map."
        ),
        inputs=[
            ("classification/", "all per-variant classifications from Wave 5"),
            ("metrics/", "all per-variant metrics from Wave 4"),
        ],
        acceptance=[
            "synthesis/mechanism_distribution.json exists with counts and percent per mechanism family",
            "synthesis/cooccurrence.json exists describing variant pairs that recur",
            "synthesis/resistance_pathway_map.svg exists",
            "synthesis/synthesis_report.md narrates the campaign-level findings",
        ],
        validation_commands="""\
test -f synthesis/mechanism_distribution.json
test -f synthesis/cooccurrence.json
test -f synthesis/resistance_pathway_map.svg
test -f synthesis/synthesis_report.md\
""",
        touched_areas=[("synthesis/", "campaign-level synthesis artifacts")],
        blocked_by=classify_issues,
        complexity="medium",
    )
    return iid, body


def wave8_therapy(label: str, synthesis_issue: str) -> tuple[str, str]:
    iid = issue_id(label, 8, "THERAPY")
    body = make_issue_body(
        summary=(
            "For the dominant mechanism class(es) identified in Wave 7, draft candidate "
            "counter-strategies. Output is explicitly a computational hypothesis, not a "
            "validated recommendation."
        ),
        inputs=[
            ("synthesis/mechanism_distribution.json", "dominant mechanism counts from Wave 7"),
            ("synthesis/synthesis_report.md", "Wave 7 narrative"),
        ],
        acceptance=[
            "therapy/strategy_brief.md exists, references at least one variant per dominant mechanism",
            "therapy/candidate_chemotypes.yaml lists at least one candidate strategy per dominant mechanism",
            "every recommendation is marked 'computational hypothesis, not validated'",
        ],
        validation_commands="""\
test -f therapy/strategy_brief.md
test -f therapy/candidate_chemotypes.yaml
grep -q 'computational hypothesis' therapy/strategy_brief.md\
""",
        touched_areas=[("therapy/", "therapeutic-implication drafts")],
        blocked_by=[synthesis_issue],
        complexity="medium",
    )
    return iid, body


def wave9_dossier(label: str, therapy_issue: str) -> list[tuple[str, str]]:
    """Wave 9 fans into assembly, caption, QA, and manifest issues."""
    issues: list[tuple[str, str]] = []

    # 9a: assembly
    iid_assemble = issue_id(label, 9, "ASSEMBLE")
    body_assemble = make_issue_body(
        summary=(
            "Assemble the multi-panel figure dossier from Wave 6 panels and Wave 7 synthesis "
            "artifacts."
        ),
        inputs=[
            ("figure-dossier/panels/", "panels rendered in Wave 6"),
            ("synthesis/", "synthesis outputs from Wave 7"),
            ("therapy/strategy_brief.md", "Wave 8 therapeutic implications"),
        ],
        acceptance=[
            "figure-dossier/figure.png exists, multi-panel, 4400x3400 minimum, nonblank",
            "figure-dossier/storyboard.md describes the panel order and reading flow",
            "all referenced panels exist on disk",
        ],
        validation_commands="""\
test -f figure-dossier/figure.png
test -f figure-dossier/storyboard.md
python3 -c "from pathlib import Path; assert Path('figure-dossier/panels').is_dir()"\
""",
        touched_areas=[
            ("figure-dossier/figure.png", "assembled figure"),
            ("figure-dossier/storyboard.md", "panel reading order"),
        ],
        blocked_by=[therapy_issue],
        complexity="medium",
    )
    issues.append((iid_assemble, body_assemble))

    # 9b: caption + provenance
    iid_caption = issue_id(label, 9, "CAPTION")
    body_caption = make_issue_body(
        summary=(
            "Draft the figure caption and provenance for the assembled dossier. Caption "
            "must reference exact PDB IDs, software versions, and any modeling caveats."
        ),
        inputs=[
            ("figure-dossier/figure.png", "assembled figure"),
            ("figure-dossier/panels/", "panel sidecar JSON files"),
            ("synthesis/synthesis_report.md", "Wave 7 narrative"),
        ],
        acceptance=[
            "figure-dossier/caption_draft.md exists, <= 250 words",
            "every PDB ID and software version cited in the caption appears in the manifest",
            "figure-dossier/provenance.md links every artifact back to its producing issue",
        ],
        validation_commands="""\
test -f figure-dossier/caption_draft.md
test -f figure-dossier/provenance.md
python3 -c "import re,sys; t=open('figure-dossier/caption_draft.md').read(); assert len(re.findall(r'\\\\b\\\\w+\\\\b', t))<=250, 'caption too long'"\
""",
        touched_areas=[
            ("figure-dossier/caption_draft.md", "draft caption"),
            ("figure-dossier/provenance.md", "artifact provenance"),
        ],
        blocked_by=[iid_assemble],
        complexity="small",
    )
    issues.append((iid_caption, body_caption))

    # 9c: QA
    iid_qa = issue_id(label, 9, "QA")
    body_qa = make_issue_body(
        summary=(
            "Run the figure QA worker over the dossier: nonblank panels, palette check, "
            "label legibility check, resolution audit."
        ),
        inputs=[
            ("figure-dossier/figure.png", "assembled figure"),
            ("figure-dossier/panels/", "individual panels"),
        ],
        acceptance=[
            "figure-dossier/qa_report.md lists every panel checked with pass/fail",
            "no panel is blank or below resolution threshold",
            "palette is colorblind-safe (Okabe-Ito or equivalent)",
        ],
        validation_commands="""\
test -f figure-dossier/qa_report.md
grep -q 'PASS' figure-dossier/qa_report.md
! grep -q 'FAIL' figure-dossier/qa_report.md\
""",
        touched_areas=[("figure-dossier/qa_report.md", "QA outcomes")],
        blocked_by=[iid_assemble],
        complexity="small",
    )
    issues.append((iid_qa, body_qa))

    # 9d: manifest
    iid_manifest = issue_id(label, 9, "MANIFEST")
    body_manifest = make_issue_body(
        summary=(
            "Emit figure-dossier/figure_manifest.json that conforms to the BioSymphony "
            "figure manifest schema, listing every input, artifact, software version, "
            "Linear issue, and validation result."
        ),
        inputs=[
            ("figure-dossier/", "assembled dossier contents"),
            ("intake/variant_table.json", "campaign intake table"),
        ],
        acceptance=[
            "figure-dossier/figure_manifest.json validates against figure-manifest.schema.json",
            "every artifact in the manifest has a sha256 hash",
            "every Linear issue ID referenced in the manifest is in the campaign DAG",
        ],
        validation_commands="""\
python3 skills/biosymphony/scripts/figure_manifest_check.py figure-dossier/figure_manifest.json
test -f figure-dossier/figure_manifest.json\
""",
        touched_areas=[("figure-dossier/figure_manifest.json", "validated dossier manifest")],
        blocked_by=[iid_caption, iid_qa],
        complexity="small",
    )
    issues.append((iid_manifest, body_manifest))

    return issues


def wave10_audit(
    label: str,
    claim: dict,
    manifest_issue: str,
) -> tuple[str, str]:
    cid = claim["id"]
    vid = claim["variant_ref"]
    iid = issue_id(label, 10, f"AUDIT-{cid}")
    expected = claim.get("expected_verdict", "unset")
    body = make_issue_body(
        summary=(
            f"Audit literature claim {cid} (variant {vid}) against the campaign's own "
            "evidence and emit a verdict: supported / qualified / not_supported / untestable."
        ),
        inputs=[
            ("examples/egfr-resistance-v1/claims.yaml", "literature claims source"),
            (f"metrics/{vid}/", "Wave 4 metric outputs for the referenced variant"),
            (f"classification/{vid}/", "Wave 5 classification for the referenced variant"),
            ("figure-dossier/figure_manifest.json", "validated dossier manifest"),
        ],
        acceptance=[
            f"audit/{cid}/audit.json exists with verdict in supported|qualified|not_supported|untestable",
            f"audit/{cid}/audit.md narrates the verdict in <= 150 words",
            "the verdict references at least one Wave 4 or Wave 5 artifact by path",
            f"if the testable_predictions are not available in the campaign output, verdict is untestable (expected for this run: {expected})",
        ],
        validation_commands=f"""\
python3 skills/biosymphony/scripts/claim_audit.py \\
  --claim {cid} \\
  --claims examples/egfr-resistance-v1/claims.yaml \\
  --metrics-dir metrics/{vid}/ \\
  --classification-dir classification/{vid}/ \\
  --out audit/{cid}/
test -f audit/{cid}/audit.json
python3 -c "import json; d=json.load(open('audit/{cid}/audit.json')); assert d['verdict'] in {{'supported','qualified','not_supported','untestable'}}"\
""",
        touched_areas=[(f"audit/{cid}/", "claim auditor output")],
        blocked_by=[manifest_issue],
        complexity="small",
    )
    return iid, body


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def write_issue(out_dir: Path, iid: str, body: str) -> Path:
    p = out_dir / "issues" / f"{iid}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def run_preflight(path: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), str(path), "--json"],
        capture_output=True,
        text=True,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, result.stdout + result.stderr
    return bool(data.get("ok")), json.dumps(data, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate per-wave Linear issue bodies for the Mechanistic Variant Atlas."
    )
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label-prefix", default="MVA")
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip preflight validation of emitted bodies (CI/inspection only).",
    )
    args = parser.parse_args()

    if not args.variants.is_file():
        print(f"variants file not found: {args.variants}", file=sys.stderr)
        return 1
    if not args.claims.is_file():
        print(f"claims file not found: {args.claims}", file=sys.stderr)
        return 1

    variants_doc = load_yaml(args.variants)
    claims_doc = load_yaml(args.claims)
    variants = variants_doc.get("variants", [])
    claims = claims_doc.get("claims", [])
    label = args.label_prefix
    relative_variants_path = "skills/biosymphony/examples/egfr-resistance-v1/variants.yaml"
    relative_claims_path = "skills/biosymphony/examples/egfr-resistance-v1/claims.yaml"

    args.out.mkdir(parents=True, exist_ok=True)
    dag: dict = {
        "schema_version": 1,
        "campaign": "mechanistic-variant-atlas",
        "label_prefix": label,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "issues": [],
    }
    written: list[Path] = []

    def add(iid: str, body: str, blocked_by: list[str] | None = None, wave: int | None = None) -> None:
        path = write_issue(args.out, iid, body)
        written.append(path)
        dag["issues"].append(
            {
                "id": iid,
                "path": str(path.relative_to(args.out)),
                "blocked_by": blocked_by or [],
                "wave": wave,
            }
        )

    # Wave 1
    intake_id, intake_body = wave1_intake(label, relative_variants_path, relative_claims_path)
    add(intake_id, intake_body, [], wave=1)

    # Wave 2 (per variant)
    mapping_ids: list[str] = []
    for v in variants:
        iid, body = wave2_structure_mapping(label, v, intake_id)
        add(iid, body, [intake_id], wave=2)
        mapping_ids.append(iid)

    # Wave 3 (per variant)
    ingest_ids_by_variant: dict[str, str] = {}
    for v, mid in zip(variants, mapping_ids):
        iid, body = wave3_structure_ingest(label, v, mid)
        add(iid, body, [mid], wave=3)
        ingest_ids_by_variant[v["id"]] = iid

    # Wave 4 (per variant per metric)
    metric_ids_by_variant: dict[str, list[str]] = {v["id"]: [] for v in variants}
    for v in variants:
        ingest = ingest_ids_by_variant[v["id"]]
        for metric_key, _ in WAVE4_METRICS:
            iid, body = wave4_metric(label, v, metric_key, ingest)
            add(iid, body, [ingest], wave=4)
            metric_ids_by_variant[v["id"]].append(iid)

    # Wave 5 (per variant)
    classify_ids: list[str] = []
    for v in variants:
        iid, body = wave5_classify(label, v, metric_ids_by_variant[v["id"]])
        add(iid, body, metric_ids_by_variant[v["id"]], wave=5)
        classify_ids.append(iid)

    # Wave 6 (templates only: instantiated per variant after Wave 5)
    wave6_template_ids: list[str] = []
    for fkey, fname, frend in WAVE6_FAMILIES:
        iid, body = wave6_template(label, fkey, fname, frend)
        add(iid, body, classify_ids, wave=6)
        wave6_template_ids.append(iid)

    # Wave 7
    synth_id, synth_body = wave7_synthesis(label, classify_ids)
    add(synth_id, synth_body, classify_ids, wave=7)

    # Wave 8
    therapy_id, therapy_body = wave8_therapy(label, synth_id)
    add(therapy_id, therapy_body, [synth_id], wave=8)

    # Wave 9 (4 issues)
    wave9_issues = wave9_dossier(label, therapy_id)
    last_manifest_id = None
    for i, (iid, body) in enumerate(wave9_issues):
        # blocker chain: 9a depends on therapy; 9b/9c depend on 9a; 9d depends on 9b+9c
        if i == 0:
            blocked = [therapy_id]
        elif i in (1, 2):
            blocked = [wave9_issues[0][0]]
        else:
            blocked = [wave9_issues[1][0], wave9_issues[2][0]]
        add(iid, body, blocked, wave=9)
        if "MANIFEST" in iid:
            last_manifest_id = iid

    if last_manifest_id is None:
        print("internal error: did not emit Wave 9 manifest issue", file=sys.stderr)
        return 5

    # Wave 10 (per claim)
    for claim in claims:
        iid, body = wave10_audit(label, claim, last_manifest_id)
        add(iid, body, [last_manifest_id], wave=10)

    # Write DAG
    dag_path = args.out / "dag.json"
    dag_path.write_text(json.dumps(dag, indent=2), encoding="utf-8")

    # Preflight every issue body
    failures: list[tuple[str, str]] = []
    if not args.no_preflight:
        for path in written:
            ok, detail = run_preflight(path)
            if not ok:
                failures.append((str(path), detail))

    print(f"emitted {len(written)} issue bodies under {args.out / 'issues'}")
    print(f"DAG: {dag_path}")
    if args.no_preflight:
        print("preflight skipped (--no-preflight)")
        return 0
    if failures:
        print(f"FAIL: {len(failures)} issue body/ies did not pass preflight", file=sys.stderr)
        for path, detail in failures[:5]:
            print(f"--- {path} ---", file=sys.stderr)
            print(detail, file=sys.stderr)
        return 5
    print(f"preflight: ok on all {len(written)} bodies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
