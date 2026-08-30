# Per-tool dispatch contract

This contract applies to every boot script and dispatcher under `images/genecluster-superpowers/`. It defines portable artifacts and public-safety requirements; it does not authorize a cloud launch.

## Inputs

Each launch declares:

- tool and run identifiers;
- a digest-pinned image or verified machine image;
- public or approved input references with SHA-256 values;
- a bounded command, resource limit, and timeout;
- an external output location;
- an operator-side monitor and cleanup command.

## Credentials

Credentials stay in the operator's approved secret store. Do not write them to source files, payloads, manifests, logs, status files, or container environments. Prefer short-lived workload identities and bucket-prefix permissions.

Workers must not receive provider API keys for self-termination. Cleanup is operator-side unless the provider supplies a narrowly scoped, short-lived runtime identity.

## Sentinels

Each tool writes these files under its run work directory:

| File | Requirement |
|---|---|
| `STATUS` | Atomically rewritten, single-line phase and timestamp |
| `SUCCESS` | Created only after exit code and expected outputs are verified |
| `FAILURE` | Compact error summary with no secrets or raw private data |
| `<tool>-summary.tsv` | Compact output that follows the tool's documented schema |
| `tools.txt` | Exact binary and version inventory |
| `manifest.json` | Inputs, versions, parameters, hashes, exit state, and limits |

Clear stale sentinels at startup. A process exit code alone is not scientific success.

## Staging and supply chain

- Use private, access-controlled object storage or an approved SSH route.
- Use time-limited access URLs when direct workload identity is unavailable.
- Never use anonymous file hosts for scripts, inputs, status, or results.
- Pin container images by digest.
- Fetch immutable releases or commits.
- Verify every script, archive, binary, model, and database against a published hash or signature.
- Avoid `curl | sh`, mutable branches, and unverified installers.

## Output schema

A tool summary should include stable query and target identifiers, evidence kind, primary score, version, and compact tool-specific metadata. Document extra columns in the per-tool guide.

## Egress

Return compact summaries, manifests, logs, versions, and hashes. Keep raw and heavy artifacts in approved external storage. If an HTTP review endpoint is explicitly enabled, serve only a sanitized summary directory for a short period.

## Monitoring and cleanup

Monitors should check state, progress, output growth, and timeout. Stop after repeated no-progress signals or contract failures. After completion:

1. verify expected outputs and hashes;
2. pull only allowlisted summaries;
3. record cleanup state;
4. destroy the resource from the operator side;
5. remove temporary access URLs and staging objects.

Provider identifiers and raw API responses remain in ignored runtime state.
