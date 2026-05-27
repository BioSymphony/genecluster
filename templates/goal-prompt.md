# BioSymphony GeneCluster Goal Prompt

Use this when giving a capable local agent a `/goal` style task. Replace bracketed
fields, then paste the prompt into Codex, Claude Code, Symphony, or another
orchestrator.

```text
Goal: turn [pathway / mechanism / species question] into a BioSymphony
GeneCluster campaign plan and first executable wave.

Context:
- Target pathway or chemistry: [e.g. MIA, BIA, terpene, custom]
- Target species: [scientific name]
- Comparator species, if known: [list or "agent should propose"]
- Inputs already available: [local paths, accessions, papers, workbooks, or none]
- Desired output: [route card, issue graph, candidate search, atlas dossier, review surface]
- Execution preference: [local only / Symphony + Linear / RunPod / SSH-HPC / cloud VM / decide]
- Budget or time boundary: [none / rough limit]

Use the repo as the campaign control plane:
1. Read README.md, AGENTS.md, docs/agent-orchestrator-guide.md, and the relevant
   BioSymphony skill references.
2. Run the demo harness or local checks if the environment has not been proven.
3. Create or adapt the campaign packet and ledgers needed for this goal.
4. Run preflight, source scouting, route scouting, and the relevant validators.
5. Decide whether the next step is a solo-agent task, a Symphony/Linear issue
   wave, a provider launch bundle, or next-experiment design.
6. Do not wait for every ordinary implementation detail to be specified; make
   conservative choices that match the repo patterns.
7. Keep raw/heavy data and credentials outside the repo. Pull back compact
   summaries, ledgers, reports, versions, hashes, and review surfaces.

Close out with:
- selected route and claim ceiling
- artifacts produced
- validation commands run
- next bounded worker or issue wave
- uncertainties that need user/scientific judgment
```

