# EGFR Resistance v1: Variant-Effect Atlas Example

This is a sibling-pattern example for the BioSymphony GeneCluster public skill. It illustrates that the same contract loop (source ledger, query resolution, route card, evidence scoring, claim audit, dossier) also handles variant-effect campaigns, not only gene cluster discovery.

The flagship campaign family for this repo is GeneCluster (find biosynthetic gene clusters, assemble pathway evidence). The Coptis BIA example at `../genecluster-coptis-bia-public-v0/` is the worked example for that family. This example shows the contract loop running against a different campaign topology: 10 EGFR kinase-domain variants × 5 structural metrics, with a literature-claim auditor.

The example is designed for a **dry run first**. It does not seed Linear and does not dispatch Symphony workers until the dry-run validates cleanly.

## What This Example Demonstrates

- The shared contract loop hosting a variant × metric matrix (content-dependent branching, cross-issue meta-reasoning, multi-claim ledger, provenance).
- Tier A only, runs on the verified local stack (PyMOL, ChimeraX, Symphony). No new prediction-model installs are required.
- The Wave 10 claim auditor exercising all four verdict types: `supported`, `qualified`, `not_supported`, `untestable`.
- Real published variants and real published claims so the audit verdicts can be sanity-checked against the literature.

## Files

| File | Purpose |
| --- | --- |
| `variants.yaml` | 10 EGFR variants with HGVS, COSMIC IDs, drug context, expected PDB structures, AFDB availability, classifier hints |
| `claims.yaml` | 14 literature claims spanning all four expected verdict types for the Wave 10 auditor |
| `expected_dossier.md` | What a successful campaign run should produce; used as a manual-review checklist (TBD, added after first dry run) |

## Variants Included

| ID | Type | Drug context |
| --- | --- | --- |
| L858R | Primary activating | TKI-sensitizing |
| del E746-A750 | Primary activating | TKI-sensitizing |
| T790M | Acquired resistance | First-gen TKI resistance, osimertinib retains |
| C797S | Acquired resistance | Osimertinib covalent escape |
| L718Q | Acquired resistance | Osimertinib resistance |
| G724S | Acquired resistance | Osimertinib resistance |
| L792H | Acquired resistance | Osimertinib resistance |
| A763_Y764insFQEA | Primary activating + intrinsic resistance | Exon 20 insertion |
| S768I | Uncommon activating | Variable; stress-test for ambiguous routing |
| G719A | Uncommon activating | Reduced first-gen TKI sensitivity |

## Dry-Run Procedure

The dry-run path is the only path supported in v1. It produces:

- a campaign manifest
- one Linear-issue body per wave (validated by `preflight_check.py`)
- a per-variant DAG (validated by `campaign_check.py` once that script lands)

The intended sequence (campaign-runner script not yet implemented; this section defines the contract for it):

```bash
# 1. Verify the local stack
python3 skills/biosymphony/scripts/capability_probe.py --json

# 2. Validate the example inputs
python3 -c "import yaml; yaml.safe_load(open('skills/biosymphony/examples/egfr-resistance-v1/variants.yaml'))"
python3 -c "import yaml; yaml.safe_load(open('skills/biosymphony/examples/egfr-resistance-v1/claims.yaml'))"

# 3. (Future) generate Linear issue bodies for the dry run
# python3 skills/biosymphony/scripts/campaign_dry_run.py \
#   --campaign skills/biosymphony/references/campaigns/mechanistic-variant-atlas.md \
#   --variants skills/biosymphony/examples/egfr-resistance-v1/variants.yaml \
#   --claims skills/biosymphony/examples/egfr-resistance-v1/claims.yaml \
#   --out dry-run/

# 4. (Future) preflight every generated issue body
# for f in dry-run/issues/*.md; do
#   python3 skills/biosymphony/scripts/preflight_check.py "$f"
# done
```

`campaign_dry_run.py` is a Phase 2 deliverable. Until it lands, the campaign exists as the spec in `references/campaigns/mechanistic-variant-atlas.md` plus the example data here, with hand-authored issue bodies for the first proven wave.

## Capability Tier Boundary

This example runs on Tier A only. The campaign spec marks Tier B/C/D promotion paths but does not require them.

What v1 does locally:

- Fetch existing PDB structures (RCSB API)
- Fetch existing AFDB predictions (AlphaFold DB API)
- PyMOL `mutate` for variants where neither PDB nor AFDB has the mutant
- Compute structural metrics (contacts, hbonds, pocket geometry, gatekeeper distance, drug-pocket interaction)
- Run a rule-based mechanism classifier (no ML)
- Render panels (PyMOL ray, ChimeraX REST)
- Audit literature claims against the campaign's own metrics

What v1 does not do:

- Run BoltzGen, BioEmu, RFdiffusion, or full AlphaFold 3 locally
- Compute quantitative ddG (would need PyRosetta, Tier C)
- Integrate wet-lab assay data
- Sample conformational ensembles for allosteric reasoning (would need BioEmu, Tier D)

These are explicit v2 extensions.

## Expected Wave 10 Verdict Distribution

The 14 claims in `claims.yaml` are designed to exercise all auditor verdict types:

| Expected verdict | Count | Example |
| --- | --- | --- |
| supported | 7 | T790M_gatekeeper_clash, C797S_covalent_loss |
| qualified | 5 | L858R_destabilizes_inactive, del_E746_A750_p_loop_shortening |
| untestable | 2 | T790M_atp_affinity_increase (kinetic), C797S_phenotype_resistance (clinical) |
| not_supported | 0 | none in v1, added in a later iteration |

A successful v1 dry run produces a Wave 10 audit summary that approximately matches this distribution. Significant divergence (for example, the auditor marking everything `supported`) indicates the auditor logic is too lenient and should be tuned.

## Risk Notes

- All variants and claims in this example are public, published data. No private patient identifiers, unpublished sequences, or embargoed structures are included.
- AFDB predictions and PyMOL mutagenesis fallbacks are computational models; their use must be flagged in any artifact and treated as caveat-bearing in dossiers.
- Drug-context-specific conclusions only apply to the listed TKIs and their published binding modes. Do not extrapolate to other inhibitor scaffolds without recomputing.

## Next Steps

After the first dry run passes preflight on every generated issue body:

1. Inspect the dry-run issue bodies manually for science quality.
2. Implement the metric scripts (`scripts/metrics/contact_diff.py`, `pocket_geometry.py`, `gatekeeper_distance.py`, `hbond_diff.py`), they are spec'd in the campaign doc but not yet built.
3. Wire `scripts/campaign_dry_run.py` to read the campaign spec and produce issue bodies with parameters substituted.
4. Run a single-variant live test (T790M alone) through Symphony with `max_concurrent_agents: 1`.
5. Promote to full 10-variant fan-out only after the single-variant live test produces a clean dossier.

This staging is required by Phase 2 of `docs/implementation-plan.md`.
