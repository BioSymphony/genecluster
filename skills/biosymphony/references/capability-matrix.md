# Capability Matrix

Use this reference before claiming a campaign can run locally.

## Tier A: Local Now

Verified baseline is operator-specific. Confirm with
`skills/biosymphony/scripts/capability_probe.py --json` before claiming a
local path, binary, or companion repo is available.

Typical Tier A components:

- Symphony + Linear operator stack configured outside this repo
- PyMOL app or CLI
- ChimeraX app or CLI/REST path
- optional companion structural-biology helper skills
- optional live-demo or voice-demo repos
- Hugging Face CLI when model downloads are needed
- conda/mamba or another reproducible package manager

Good Tier A campaigns:

- static and scripted molecular figure dossiers
- ChimeraX map/session storytelling through GUI + REST
- deterministic recipe rehearsal
- provenance traceback
- caption and QA workflows

## Tier B: Installable Experimental

Do not claim these as installed unless `capability_probe.py` confirms them:

- ColabFold local
- ESMFold or ESM-style local prediction
- ProteinMPNN or LigandMPNN
- MLX-based local model helpers
- OpenMM
- MDAnalysis or MDTraj
- Boltz-1 local lanes

## Tier C: Manual Or Licensed

Requires manual setup, license, or careful local policy:

- PyRosetta
- Phenix
- Coot
- ISOLDE
- advanced cryo-EM refinement beyond ChimeraX visualization

## Tier D: Cloud Or Remote

Treat as future remote lanes:

- AlphaFold 3 at scale
- BoltzGen candidate generation at scale
- Evo 2 large-model runs
- RFdiffusion at scale
- broad GPU design/prediction batches

## Rule

The capability probe wins over prose. If this file and the live probe disagree, report the live probe and update this file only after confirming the change.
