# Google Cloud execution pattern

Use this pattern for public or synthetic BioSymphony workloads that fit Compute Engine, Batch, or an institutional Google Cloud environment.

## Reference design

1. Put inputs and outputs in separate, access-controlled object prefixes.
2. assign a dedicated service account with only the required object and compute actions.
3. Launch a digest-pinned image or verified machine image.
4. Pass a small launch contract with public object references, hashes, resource limits, and output paths.
5. Write raw results to external storage.
6. Return compact summaries, manifests, logs, versions, and hashes.
7. Delete resources from the operator side after outputs are verified.

## Identity and storage

Prefer attached service accounts and workload identity over service-account keys. Use custom roles or an isolated project when predefined project-wide roles are broader than the workload requires. Limit object permissions to the required bucket prefixes.

Do not include credentials, private project identifiers, raw provider responses, or unpublished data in this repository.

## Reproducibility

Record the image digest, machine type, region, tool and database versions, command, input hashes, output hashes, timeout, and exit state. Keep provider-specific state in ignored runtime storage.

## Before launch

Confirm quotas, accelerator availability, pricing, egress, identity permissions, and cleanup behavior in the official [Google Cloud Batch](https://cloud.google.com/batch/docs) and [service account](https://cloud.google.com/iam/docs/service-account-overview) documentation.
