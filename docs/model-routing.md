# Model And Tool Routing

## Routing Table

| User intent | Preferred lane | Notes |
| --- | --- | --- |
| Inspect or render known structure | PyMOL + ChimeraX | PyMOL for headless rendering, ChimeraX for maps/interfaces/live demos |
| Paper-grade structural figure | PyMOL + ChimeraX + QA | Use named views, saved sessions, high-res exports, manifest |
| AlphaFold confidence or PAE review | AlphaFold DB | pLDDT/PAE guides uncertainty and close-up regions |
| Prediction vs experiment | AlphaFold/Boltz + alignment + PyMOL/ChimeraX | RMSD and discrepancy panels are mandatory |
| Protein/RNA/DNA/ligand complex prediction | AlphaFold 3, Boltz, OpenFold-style tools | Keep license and confidence caveats explicit |
| Binding affinity ranking | Boltz-2 | Use as prioritization signal, not experimental truth |
| Binder generation | BoltzGen, ProteinMPNN, RFdiffusion-style tools | Needs downstream validation and ranking wave |
| Sequence or variant hypothesis | Evo 2 | Upstream DNA/genome lane, feeds structure/design lanes |
| Physics/design/refinement | Rosetta/PyRosetta | Scoring, relax, ddG, interface design, scorefile analysis |
| Cryo-EM map handoff | ChimeraX | Map zoning, contours, orthoplanes, session export |

## Evo 2

Use Evo 2 for sequence and genome-scale hypotheses:

- variant effect triage
- coding sequence edits
- promoter/regulatory element design
- long-context genomic reasoning
- candidate sequences to send downstream into structure/design workflows

Do not treat Evo 2 as a direct 3D structure or figure tool. It is the upstream sequence intelligence layer.

## Boltz And Boltz-2

Use Boltz for biomolecular interaction prediction and Boltz-2 when affinity or hit ranking is central.

Good Symphony split:

1. Build Boltz input YAML.
2. Run batch prediction.
3. Parse structures and affinity fields.
4. Cluster/rank candidates.
5. Create PyMOL/ChimeraX panels for top candidates.
6. QA and caption with caveats.

## BoltzGen

Use BoltzGen for generative binder design. It can produce many candidates, so Symphony is valuable for candidate management:

- generation worker
- validation worker
- ranking worker
- diversity/clustering worker
- visual review worker
- caption/provenance worker

## AlphaFold

Use AlphaFold DB for quick single-chain predictions and AlphaFold 3 where complex biomolecular predictions are needed and licensing permits.

Always preserve:

- source and version
- confidence metrics
- known limitations
- whether model weights/server terms allow the intended use

## Rosetta/PyRosetta

Use Rosetta for physics-aware review and design:

- FastRelax
- interface scoring
- point mutation ddG
- ligand/interface redesign
- scorefile parsing
- top-N design comparison

Rosetta outputs should feed directly into PyMOL/ChimeraX figure lanes.

