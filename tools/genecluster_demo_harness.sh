#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Run the local BioSymphony GeneCluster demonstration harness.

Usage:
  tools/genecluster_demo_harness.sh [output-dir]

Environment:
  BIOSYMPHONY_DEMO_OUT      Output directory. Defaults to a temp directory.
  BIOSYMPHONY_DEMO_SCOPE    Issue dry-run scope. Defaults to candidate_search.
  BIOSYMPHONY_DEMO_PREFIX   Candidate issue prefix. Defaults to GCDEMO.
EOF
  exit 0
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(CDPATH= cd -- "${script_dir}/.." && pwd)"
cd "${repo_root}"

example_dir="skills/biosymphony/examples/genecluster-coptis-bia-public-v0"
campaign="${example_dir}/campaign-manifest.json"
candidate_hits="${example_dir}/fixtures/candidate_hits.tsv"
query_registry="skills/biosymphony/references/genecluster-query-registry.tsv"
required_claims="skills/biosymphony/references/required-claims.tsv"
route_query_fasta="${example_dir}/fixtures/query-with-controls.faa"
route_source_ledger="${example_dir}/fixtures/route-source-ledger.tsv"
scope="${BIOSYMPHONY_DEMO_SCOPE:-candidate_search}"
prefix="${BIOSYMPHONY_DEMO_PREFIX:-GCDEMO}"

if [[ $# -gt 0 ]]; then
  out_dir="$1"
elif [[ -n "${BIOSYMPHONY_DEMO_OUT:-}" ]]; then
  out_dir="${BIOSYMPHONY_DEMO_OUT}"
else
  out_dir="$(mktemp -d "${TMPDIR:-/tmp}/biosymphony-genecluster-demo.XXXXXX")"
fi
mkdir -p "${out_dir}"
out_dir="$(CDPATH= cd -- "${out_dir}" && pwd)"

on_error() {
  status=$?
  printf 'BioSymphony GeneCluster demo harness failed with status %s\n' "${status}" >&2
  printf 'output_dir=%s\n' "${out_dir}" >&2
  exit "${status}"
}
trap on_error ERR

export PYTHONDONTWRITEBYTECODE=1

python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
  --campaign "${campaign}" \
  --project-goals "${example_dir}/project-goals.yaml" \
  --pathway-steps "${example_dir}/pathway-steps.tsv" \
  --data-ledger "${example_dir}/data-ledger.tsv" \
  --query-ledger "${example_dir}/query-ledger.tsv" \
  --resource-ledger "${example_dir}/resource-ledger.tsv" \
  --database-ledger "${example_dir}/database-ledger.tsv" \
  --cache-ledger "${example_dir}/cache-ledger.tsv" \
  > "${out_dir}/example-preflight.txt"

python3 -B skills/biosymphony/scripts/genecluster_source_scout.py \
  --campaign "${campaign}" \
  --query-registry "${query_registry}" \
  --out-dir "${out_dir}/source-scout" \
  --json \
  > "${out_dir}/source-scout-summary.json"

python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
  --query-registry "${query_registry}" \
  --required-claims "${required_claims}" \
  --source-ledger "${out_dir}/source-scout/source-ledger.tsv" \
  > "${out_dir}/source-scout-preflight.txt"

python3 -B skills/biosymphony/scripts/genecluster_annotation_scout.py \
  --campaign "${campaign}" \
  --query-fasta "${route_query_fasta}" \
  --source-ledger "${route_source_ledger}" \
  --out-dir "${out_dir}/route-scout" \
  --json \
  > "${out_dir}/route-scout-summary.json"

python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
  --route-annotation-ledger "${out_dir}/route-scout/annotation-ledger.tsv" \
  > "${out_dir}/route-scout-preflight.txt"

python3 -B skills/biosymphony/scripts/genecluster_issue_dry_run.py \
  --campaign "${campaign}" \
  --out "${out_dir}/issues" \
  --label-prefix "${prefix}" \
  --run-scope "${scope}" \
  > "${out_dir}/issue-dry-run-summary.json"

python3 -B skills/biosymphony/scripts/genecluster_dossier_skeleton.py \
  --campaign "${campaign}" \
  --candidate-hits "${candidate_hits}" \
  --out "${out_dir}/dossier" \
  > "${out_dir}/dossier-manifest.path"

python3 -B skills/biosymphony/scripts/genecluster_preflight.py \
  --dossier-manifest "${out_dir}/dossier/dossier-manifest.json" \
  --candidate-hits "${out_dir}/dossier/data/candidate_hits.tsv" \
  --candidate-ranking "${out_dir}/dossier/data/candidate-ranking.tsv" \
  --evidence-jsonl "${out_dir}/dossier/data/evidence.jsonl" \
  --provenance-jsonl "${out_dir}/dossier/data/provenance.jsonl" \
  --claim-ledger "${out_dir}/dossier/claim-ledger.md" \
  > "${out_dir}/dossier-preflight.txt"

python3 -B skills/biosymphony/scripts/genecluster_review_surface.py \
  --claim-ledger "${out_dir}/dossier/claim-ledger.tsv" \
  --out-dir "${out_dir}/review" \
  --review-id genecluster-demo-review \
  --json \
  > "${out_dir}/review-surface-summary.json"

python3 -B skills/biosymphony/scripts/genecluster_atlas_contracts.py \
  --review-surface-manifest "${out_dir}/review/review_surface_manifest.json" \
  --json \
  > "${out_dir}/review-surface-contract-check.json"

issue_count="$(find "${out_dir}/issues" -type f -name '*.md' | wc -l | tr -d ' ')"

python3 -B - "${out_dir}" "${scope}" "${campaign}" "${issue_count}" <<'PY'
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

out = Path(sys.argv[1])
scope = sys.argv[2]
campaign = sys.argv[3]
issue_count = int(sys.argv[4])


def load_json(rel: str) -> dict:
    path = out / rel
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def text_ok(rel: str) -> bool:
    try:
        return "BioSymphony GeneCluster preflight: ok" in (out / rel).read_text(encoding="utf-8")
    except OSError:
        return False


review_contract = load_json("review-surface-contract-check.json")
route_scout = load_json("route-scout-summary.json")
summary = {
    "schema_version": "biosymphony_genecluster_demo.v1",
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "campaign": campaign,
    "run_scope": scope,
    "counts": {
        "campaign_issue_drafts": issue_count,
    },
    "validation": {
        "example_preflight_ok": text_ok("example-preflight.txt"),
        "source_scout_preflight_ok": text_ok("source-scout-preflight.txt"),
        "route_scout_preflight_ok": text_ok("route-scout-preflight.txt"),
        "dossier_preflight_ok": text_ok("dossier-preflight.txt"),
        "review_surface_contract_ok": bool(review_contract.get("ok")),
    },
    "route": {
        "selected_route": route_scout.get("decision", {}).get("selected_route", ""),
        "claim_ceiling": route_scout.get("decision", {}).get("claim_ceiling", ""),
        "selected_source_id": route_scout.get("decision", {}).get("selected_source_id", ""),
    },
    "artifacts": {
        "source_scout_report": "source-scout/source-scout-report.json",
        "source_ledger": "source-scout/source-ledger.tsv",
        "query_resolution_ledger": "source-scout/query-resolution-ledger.tsv",
        "route_decision": "route-scout/route_decision.json",
        "annotation_ledger": "route-scout/annotation-ledger.tsv",
        "campaign_issues": "issues/",
        "dossier_manifest": "dossier/dossier-manifest.json",
        "dossier_claim_ledger": "dossier/claim-ledger.tsv",
        "review_surface": "review/index.html",
        "review_manifest": "review/review_surface_manifest.json",
    },
    "checks": {
        "source_scout": "source-scout-summary.json",
        "source_scout_preflight": "source-scout-preflight.txt",
        "route_scout": "route-scout-summary.json",
        "route_scout_preflight": "route-scout-preflight.txt",
        "issue_dry_run": "issue-dry-run-summary.json",
        "dossier_preflight": "dossier-preflight.txt",
        "review_contract": "review-surface-contract-check.json",
    },
}
(out / "demo-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

validation_lines = "\n".join(
    f"- {name}: {'ok' if ok else 'failed'}"
    for name, ok in summary["validation"].items()
)
readme = f"""# BioSymphony GeneCluster Demo Output

Generated: {summary['generated_at']}

Run scope: `{scope}`
Campaign: `{campaign}`

## Open First

- [Review surface](review/index.html)
- [Demo summary](demo-summary.json)
- [Route decision](route-scout/route_decision.json)
- [Source scout report](source-scout/source-scout-report.json)
- [Dossier manifest](dossier/dossier-manifest.json)

## Counts

- Campaign issue drafts: {issue_count}
- Selected route: `{summary['route']['selected_route']}`
- Claim ceiling: `{summary['route']['claim_ceiling']}`

## Validation

{validation_lines}

## Useful Folders

- `issues/` - campaign-scoped issue contracts.
- `source-scout/` - registry-derived source/query resolution ledgers.
- `route-scout/` - selected route card and annotation ledger.
- `dossier/` - compact candidate dossier.
- `review/` - static claim review surface.

This directory is generated output. It should stay outside source control unless an operator intentionally copies a selected summary artifact.
"""
(out / "README.md").write_text(readme, encoding="utf-8")
PY

printf 'BioSymphony GeneCluster demo harness complete\n'
printf 'output_dir=%s\n' "${out_dir}"
printf 'campaign_issue_drafts=%s (%s)\n' "${issue_count}" "${scope}"
printf 'route_decision=%s\n' "${out_dir}/route-scout/route_decision.json"
printf 'demo_summary=%s\n' "${out_dir}/demo-summary.json"
printf 'demo_readme=%s\n' "${out_dir}/README.md"
printf 'dossier_manifest=%s\n' "${out_dir}/dossier/dossier-manifest.json"
printf 'review_surface=%s\n' "${out_dir}/review/index.html"
