# Cloud dispatch templates

These scripts are reference adapters for bounded public or approved workloads. They are not live pricing guidance, provider recommendations, or unattended production launchers.

## Shared contract

Each dispatcher accepts a tool name, an immutable image or verified machine image, a boot script, and a work directory. Before use:

- review the selected provider's current documentation and terms;
- pin images by digest and verify machine images;
- verify the boot script and every downloaded artifact;
- use a dedicated least-privilege identity;
- restrict storage access to exact input and output prefixes;
- set a budget and timeout;
- define operator-side monitoring and cleanup;
- keep provider payloads in ignored runtime storage.

See [the dispatch contract](../CONTRACT.md).

## Adapters

| Script | Execution surface |
|---|---|
| `runpod-dispatch.sh` | RunPod pod and network volume |
| `aws-dispatch.sh` | EC2 and S3 |
| `gcp-dispatch.sh` | Compute Engine and Cloud Storage |
| `vastai-dispatch.sh` | GPU marketplace instance and private S3 staging |
| `lambda-dispatch.sh` | Lambda instance, SSH, and private S3 staging |

## Credential boundary

Load credentials from an approved operator-side secret store. Do not put credentials in command examples, environment files committed to the repository, launch manifests, worker environments, or boot scripts.

Use attached workload identities where available. A worker should be able to read only its input prefix and write only its output prefix. It should not have project-wide instance administration or access to sibling campaigns.

## Staging

Use private object storage, workload identity, presigned URLs with short expiry, or an approved SSH copy. Do not use anonymous file hosts. Store expected SHA-256 values in the launch contract and fail closed on mismatch.

## Images

Pass immutable image digests, for example:

```text
<REGISTRY>/<IMAGE>@sha256:<DIGEST>
```

Do not rely on `latest`, a mutable tag, or an unverified bootstrap installer.

## Outputs

Dispatch state belongs under ignored `.runtime/provider-dispatch/` directories. Pull only allowlisted summaries, manifests, logs, versions, and hashes. Raw data, databases, model caches, and provider responses remain outside the public repository.

## Cleanup

Cleanup is operator-side. Verify outputs first, then destroy the resource and remove temporary staging objects or access URLs. Never send a long-lived provider API key into a worker for self-termination.

## Validation

Review shell syntax and the generated launch manifest without launching a resource. A live launch requires separate authorization, current provider checks, and a campaign-specific data-handling decision.
