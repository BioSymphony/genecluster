# Atlas writing and review

A GeneCluster atlas must show the evidence behind each conclusion. Keep tool outputs separate until the review step.

## Required layers

Include:

- the campaign question and scope;
- source, query, control, database, and cache ledgers;
- the route card and claim limit;
- candidate and cluster tables;
- evidence by method;
- conflicts and missing evidence;
- figures with source and version details;
- the final claim ledger;
- next actions.

## Write claims from evidence

Use stable identifiers. Cite the source for each biological fact. Link each campaign conclusion to a ledger row or versioned artifact.

Do not convert a tool label directly into a biological conclusion. State what the tool observed, then state the interpretation and its limit.

Keep negative results and tool disagreements. They help a reviewer distinguish weak evidence from missing data.

## Build tables for review

Use one stable row identifier across tables. Define every score and status. Keep units in column names or metadata. Do not mix absent data with negative evidence.

A comparison table should let a reviewer answer:

- Which input produced this row?
- Which tool and version produced the score?
- Which threshold applied?
- Which independent evidence agrees?
- What prevents a stronger claim?

## Build figures for review

Give each figure a descriptive title, readable labels, units, a legend, and source information. Provide alt text. Include a static fallback for interactive figures.

Do not use color as the only status signal. Keep the same colors and symbols across figures.

## Completion criteria

An atlas is ready for review when:

- all required ledgers validate;
- every retained claim has a source;
- the route limit is visible;
- tool conflicts remain visible;
- figures trace back to data;
- versions and hashes are recorded;
- raw and heavy data remain outside the repository.
