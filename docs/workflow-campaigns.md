# Workflow Campaigns

> **Status:** This file is the original brainstorm catalog from the initial repo scaffold. The flagship campaign family for this public skill is GeneCluster (`skills/biosymphony/references/campaigns/genecluster-*.md`, worked example `skills/biosymphony/examples/genecluster-coptis-bia-public-v0/`). The Mechanistic Variant Atlas pattern (`skills/biosymphony/references/campaigns/mechanistic-variant-atlas.md`, example `skills/biosymphony/examples/egfr-resistance-v1/`) is a documented sibling pattern. The catalog below is preserved as ideation; promote any item to a real campaign by writing a new spec under `skills/biosymphony/references/campaigns/` that conforms to the contract template and passes `preflight_check.py` for every wave.

## 1. Paper Figure Replicator

Goal: recreate or extend a structural figure from published PDB/EMDB inputs.

Issue graph:

1. Resolve PDB/EMDB/UniProt IDs and metadata.
2. Fetch structures/maps and validate file integrity.
3. Create analysis metrics: chains, ligands, contacts, validation, map notes.
4. Build PyMOL overview and local panels.
5. Build ChimeraX map/interface panels.
6. QA all exports and sessions.
7. Draft caption and provenance.

## 2. AlphaFold Reality Check

Goal: compare predicted and experimental structures.

Issue graph:

1. Fetch AFDB or run AlphaFold/Boltz.
2. Fetch experimental structure.
3. Align and compute RMSD/per-residue deviations.
4. Use pLDDT/PAE to identify uncertainty regions.
5. Render global overlay and close-up discrepancy panels.
6. Draft interpretation caveats.

## 3. Cryo-EM Evidence Pack

Goal: produce a map-backed figure panel set.

Issue graph:

1. Fetch model and map.
2. Validate model/map provenance and resolution metadata.
3. Create global model-map overview.
4. Zone density around active site or ligand.
5. Add orthoplane validation beat.
6. Export publication panel and ChimeraX session.

## 4. Binder Design Campaign

Goal: generate, rank, and visualize candidate binders.

Issue graph:

1. Prepare target and binding-site specification.
2. Generate candidates with BoltzGen or other design engine.
3. Predict/rank structures with Boltz-2 or related tools.
4. Run Rosetta relaxation/scoring where available.
5. Cluster and choose top candidates.
6. Render interface panels and contact networks.
7. Produce ranked report and figure dossier.

## 5. Variant-To-Mechanism Pipeline

Goal: connect sequence variants to structural interpretation.

Issue graph:

1. Use Evo 2 or variant data to rank sequence changes.
2. Generate mutant structures or remodel affected regions.
3. Compute contacts, ddG, pocket shifts, or interface changes.
4. Render before/after mechanism panels.
5. Draft interpretation with confidence limits.

## 6. Live Demo Storyboard

Goal: produce a deterministic structural demo with recorded recipes.

Issue graph:

1. Define spoken beats and expected tool calls.
2. Implement deterministic recipe.
3. Run dry-run recipe verification.
4. Run live capture rehearsal.
5. Export final view, session, and transcript.

A deterministic telomerase cycle demo with recorded recipes is the flagship example for this pattern.

