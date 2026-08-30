# GPU marketplace execution pattern

GPU marketplaces can suit short, public, accelerator-heavy workloads when the campaign can tolerate variable host availability. Provider terms, hardware quality, networking, storage, and security controls vary, so verify them for each launch.

## Portable contract

A marketplace job should need only:

- a digest-pinned image;
- a small public or synthetic input bundle;
- expected input hashes;
- a bounded command and timeout;
- an external output destination;
- an operator-side monitor and cleanup command.

Keep credentials out of the worker whenever possible. Never pass a long-lived marketplace API key into a third-party container for self-termination. Prefer operator-side cleanup or a provider-issued, narrowly scoped, short-lived runtime identity.

## Data boundary

Use marketplace workers only for data the provider is authorized to process. Keep private or unpublished biological data on approved infrastructure. Do not use anonymous file hosts for launch scripts, inputs, status artifacts, or results.

## Supply chain

Pin container images by digest. Verify every downloaded script, archive, database, and binary against a published hash or signature. Avoid `curl | sh`, mutable Git branches, and unverified binary archives.

## Reproducibility

Return a compact manifest containing the provider category, hardware class, image digest, tool and database versions, command, public input identifiers, hashes, timeout, exit state, and cleanup state. Omit credentials, account identifiers, host details, and raw provider responses.

## Before launch

Check the selected provider's current documentation for identity, regional processing, pricing, host verification, data retention, and deletion semantics. The operator remains responsible for monitoring and cleanup.
