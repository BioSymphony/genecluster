# Campaign preflight

Run Stage 0 before candidate search or paid compute. The preflight checks whether the campaign has enough public evidence to start.

## Questions

Stage 0 answers five questions:

1. Which target data exists?
2. Are the query seeds and controls complete?
3. Does the selected pathway fit the target species?
4. Which comparison species add useful evidence?
5. What claim can the available data support?

## Required inputs

Prepare:

- a campaign manifest;
- project goals;
- pathway steps;
- source and data ledgers;
- query and control ledgers;
- database and cache ledgers.

Use public, synthetic, or placeholder data in this repository.

## Run the check

Inspect the command options:

```bash
python3 skills/biosymphony/scripts/genecluster_campaign_preflight.py --help
```

The check writes `campaign-launch-readiness.json`.

Continue only when the file contains `preflight_status: "ready"`. If the check reports a blocker, fix the ledger or select a route with a lower claim limit.

## Review the result

Confirm:

- stable source identifiers;
- current versions or access dates;
- resolved query sequences;
- positive, negative, and broad-family controls;
- a selected route;
- rejected routes with reasons;
- a clear claim limit;
- no raw or heavy files in the repository.

## Update shared public data

When you update the public species catalog, cite the source for each new claim. Do not add a pathway, cluster, or comparative label without public evidence.
