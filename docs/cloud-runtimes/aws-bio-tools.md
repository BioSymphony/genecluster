# AWS execution pattern

Use this pattern for public or synthetic BioSymphony workloads that fit EC2, AWS Batch, or an institutional AWS environment.

## Reference design

1. Store inputs and outputs in separate, access-controlled prefixes.
2. Give the worker a dedicated role limited to the required input and output prefixes.
3. Launch a digest-pinned image or a verified machine image.
4. pass a small launch contract containing public object references, expected hashes, limits, and output paths.
5. Write raw results to external storage.
6. return only compact summaries, manifests, logs, versions, and hashes.
7. terminate resources from the operator side after outputs are verified.

## Identity and storage

Prefer instance profiles, task roles, or workload identities over static access keys. Restrict object permissions to the exact bucket prefixes and actions required by the job. Do not grant account-wide read or write access for convenience.

Encrypt private workloads, keep unpublished data out of public buckets, and avoid copying provider payloads into issues or documentation.

## Reproducibility

Record the image digest, instance or batch definition, region, tool and database versions, command, input hashes, output hashes, timeout, and exit state. Do not record credentials, account identifiers, private bucket names, or raw provider responses in this repository.

## Before launch

Confirm current service quotas, regional capacity, pricing, data-egress implications, and cleanup behavior in the official [AWS Batch](https://docs.aws.amazon.com/batch/) and [EC2 security](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security.html) documentation.
