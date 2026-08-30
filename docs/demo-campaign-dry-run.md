# GeneCluster demo

The demo builds a campaign packet from bundled public or synthetic fixtures. It does not launch external compute or download raw biological data.

## Run the demo

From the repository root, run:

```bash
make demo-campaign-dry-run
```

For a smaller packet, run:

```bash
make demo-campaign-smoke
```

For the full public-mining issue graph, run:

```bash
make demo-campaign-public-mining
```

## Inspect the output

The demo writes generated files to an ignored output directory. Review these items first:

1. `README.md` for packet orientation.
2. `route-scout/route_decision.json` for the selected route and claim limit.
3. `issues/` for bounded work-unit contracts.
4. `dossier/dossier-manifest.json` for artifact hashes and provenance.
5. `review/index.html` for the static review page.

## What the demo checks

The demo checks contract shape, control coverage, route selection, ledger joins, output manifests, hashes, and claim limits.

The demo does not prove that an external provider, large database, or biological tool is ready. Use a separate public fixture before you promote a tool or execution path.
