# GeneCluster Demo Harness

The demo harness exercises the public GeneCluster control plane without launching paid compute or downloading raw biological data. It is meant to answer: can this repo turn a pathway/species example into validated issue contracts, a compact evidence package, and a static review surface?

## Run

```bash
make demo-campaign-dry-run
```

The default writes to a temp directory so public snapshot checks stay clean. Output paths are printed on stdout.

To run the demo with a persistent, browse-friendly output path:

```bash
make demo-explore
```

This writes to `.demo-output/` (gitignored) at the repo root and prints the first set of files to open. `make demo-explore-clean` removes the directory; `make clean-generated` clears it as well.

Useful switches:

```bash
make demo-campaign-smoke
make demo-campaign-public-mining
```

Or set a custom path:

```bash
BIOSYMPHONY_DEMO_OUT=/tmp/biosymphony-genecluster-demo make demo-campaign-dry-run
```

## What It Produces

- `issues/` - campaign-scoped Symphony/Linear issue drafts for the selected run scope.
- `source-scout/` - registry-derived source/query resolution ledgers.
- `route-scout/` - route card and annotation ledger from tiny joined proteome/GFF fixtures.
- `dossier/` - a backward-compatible output directory containing the summary-only candidate evidence package: HTML, TSV, XLSX, Data Package, RO-Crate metadata, claim ledger, and provenance.
- `review/` - a static review surface generated from the claim ledger.
- `README.md` - generated orientation for the output bundle.
- `demo-summary.json` - machine-readable run summary with validation statuses and key artifact paths.
- `*-summary.json` and `*-preflight.txt` - machine-readable summaries and validation logs, including route-ledger validation via `genecluster_preflight.py --route-annotation-ledger`.

## Read The Demo Output

After `make demo-explore` (or `make demo-campaign-dry-run` with the path it prints), open these five artifacts in order:

1. **`README.md`** in the output directory. Auto-generated orientation with the route decision, claim ceiling, validation statuses, and an "Open First" link list.
2. **`review/index.html`**. The static review surface: summary HTML, claim table, evidence, provenance, all hashed and packaged together. The first place a human reviewer would look.
3. **`route-scout/route_decision.json`**. The route card. Shows which evidence route the scout picked (annotation-direct, transcript-first, synteny, rescue), why it rejected the alternatives, and what claim ceiling the chosen route allows. The campaign's claim ceiling is set here, before any candidate search runs.
4. **`dossier/dossier-manifest.json`**. The summary manifest. Every produced artifact is listed with byte sizes and SHA-256 hashes, plus Data Package and RO-Crate metadata sidecars. This is what would be returned from a real provider run, with raw outputs deliberately excluded.
5. **`issues/`** (campaign issue drafts). Read one or two: each issue is a contract for a bounded worker, with summary, agent role, inputs, acceptance criteria, validation commands, touched areas, dependencies, evidence class, artifact contract, and review gate. These are what Symphony, Claude workers, or your preferred agent would fan out across.

## What Makes A Demo Output Good

The `demo-summary.json` reports validation flags. All five should be `true`:

- `example_preflight_ok`: the bundled Coptis BIA campaign passes the contract validator.
- `source_scout_preflight_ok`: the source-scout output validates against the query registry and required-claims policy.
- `route_scout_preflight_ok`: the route card has positive and negative controls, no missing required fields, and no contradictory rejections.
- `dossier_preflight_ok`: the summary manifest matches its declared artifact-pull policy and the candidate-hits table is well-formed.
- `review_surface_contract_ok`: the review surface stays summary-only.

If any flag is `false`, the matching `*-preflight.txt` or `*-summary.json` file in the output directory has the reason.

## What It Proves

- The local validators accept the public Coptis campaign contract and ledgers.
- Source scouting produces deterministic no-network ledgers from the public query registry.
- Route scouting selects an annotation-direct path from the tiny fixture proteome/GFF plus required controls, then validates the route ledger's route name, claim ceiling, control status, and join counts.
- The repo can render bounded worker issues for the candidate-search campaign across waves.
- Fixture candidate hits can become a reviewable evidence package with provenance and claim boundaries.
- Review-surface contracts validate before anything is handed to a provider or a worker lane.
