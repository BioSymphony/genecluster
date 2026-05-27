# Coptis chinensis BIA public v0

A worked GeneCluster campaign that targets benzylisoquinoline alkaloid (BIA) gene cluster discovery in *Coptis chinensis* using only public reference data. The campaign exists for the local demo harness, contract validation, and as a starting template for real bioprospecting and pathway-assembly work. All fixtures are tiny synthetic stand-ins; the demo harness validates the contract flow without launching any compute or downloading any data.

## What This Example Demonstrates

- A full GeneCluster campaign packet: manifest, project goals, pathway steps, four ledgers (data, query, resource, database, cache), and fixtures.
- The annotation-direct route landing at claim ceiling `L3_annotation_neighborhood_ready` from a tiny synthetic fixture proteome plus required positive and negative controls.
- A public BIA bioprospecting target (Coptis chinensis as the canonical BIA reference, with Berberis vulgaris and Eschscholzia californica as the typical sister-species comparators) using public NCBI accessions.
- The candidate-search issue dry run that the local demo harness exercises (`make demo-campaign-dry-run`).

## Target Context

- **Organism.** *Coptis chinensis* (Chinese goldthread), chromosome-scale public assembly `GCA_015680905.1` (9 chromosomes, 40,011 annotated proteins).
- **Outgroups / comparators.** *Berberis vulgaris*, *Eschscholzia californica*, *Argemone mexicana*.
- **Target pathway.** Benzylisoquinoline alkaloid (BIA) biosynthesis: tyrosine to dopamine to (S)-norcoclaurine, with downstream methylation, hydroxylation, and the FAD-dependent berberine-bridge step toward protoberberines.
- **Reference enzymes** (used as anchor queries in `query-ledger.tsv`). Canonical Coptis japonica BIA proteins: CjNCS (norcoclaurine synthase), Cj6OMT, CjCNMT, Cj4'OMT, CjCYP80B2, CjBBE (berberine bridge enzyme), CjCYP719A1, CjSTOX. Plus generic transporter context (MATE_BIA_CONTEXT).
- **Caveats.** This is a public-safe example. Cluster claims still require genome coordinates and neighborhood evidence; product claims still require functional or LC-MS/MS validation. The fixtures are synthetic and produce candidate-only ranks, not real biological discoveries.

## Files

| File | Purpose |
| --- | --- |
| `campaign-manifest.json` | Top-level campaign contract: organism, target pathway, accessions, query set, run scopes, claim policy. |
| `project-goals.yaml` | Scientific goal, priorities, allowed and forbidden compute lanes, stop conditions, claim boundaries. |
| `pathway-steps.tsv` | 10 BIA biochemical steps from tyrosine to protoberberines, with EC numbers and known catalyzing families. |
| `data-ledger.tsv` | Public Coptis transcriptome and genome accessions (PRJNA662860, PRJNA649082, assembly GCA_015680905.1). |
| `query-ledger.tsv` | 10 seed protein anchors plus positive and negative controls (ACT2, GAPDH, random shuffle). |
| `resource-ledger.tsv` | Tools and databases the campaign expects (BLAST, DIAMOND, MMseqs2, HMMER, InterProScan, plantiSMASH, antiSMASH, Foldseek, JCVI-MCScan, Quarto, plus Pfam, SwissProt, KEGG, MIBiG, P450Rdb). |
| `database-ledger.tsv` | Reference databases with version pins, run-scope gates, and bootstrap strategies. |
| `cache-ledger.tsv` | Eight required cache roles (network volume, db cache, search result cache, run root, nextflow cache, sra cache, fast scratch, summary export). |
| `fixtures/` | Tiny synthetic fixtures for the local dry run plus a candidate hits TSV for dossier rendering. See [fixtures/README.md](fixtures/README.md). |

## Controls

The query set includes positive controls (ACT2, GAPDH housekeeping proteins) and a negative control (random shuffle). The route scout verifies all three are present before recording any route. Missing controls block the route card.

## What A Successful Dry Run Looks Like

After `make demo-campaign-dry-run`, the generated route decision should report:

- `selected_route: annotation_direct`
- `claim_ceiling: L3_annotation_neighborhood_ready`
- `controls.ok: true` with `present_controls: ["ACT2", "GAPDH", "random_shuffle"]`
- `rejected_routes` listing why transcript-first, transcriptome-only, and tblastn-rescue were not chosen (no transcriptome source available in the fixture)

The demo harness then emits candidate-search issue drafts, builds a summary-only dossier with claim ledger and candidate hits, and renders a static review surface.

## What This Example Does Not Do

The bundled fixtures are too small to support any biological claim. Treat the candidate-hits table as illustration of dossier rendering, not as validated discoveries. The demo harness does not download data, contact NCBI, or launch any provider compute. Real campaigns materialize their own data through the provider data-materialization lane and accept candidate hits only after evidence scoring and claim audit have run.

## Tier And Scope

This example runs on the local-only Tier A control plane. The default run scope for live execution would be `full_campaign_24h` (one-day complete campaign profile), but the demo harness exercises `candidate_search` only.

## See Also

- `skills/biosymphony/SKILL.md` for the full campaign-orchestration skill, including Stage 0 preflight, route scouting, and the maturity ladder.
- `skills/biosymphony/references/campaigns/genecluster-public-mining.md` for the public-mining campaign reference this campaign follows.
- `skills/biosymphony/references/genecluster-cross-species-discovery.md` for the cross-species discovery pattern.
- `docs/glossary.md` for the terms-of-art used across the skill.
- `docs/demo-campaign-dry-run.md` for how the local demo harness exercises this example.
