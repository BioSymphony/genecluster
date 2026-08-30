# Cloud runtime guidance

Last reviewed: 2026-08-30

These pages describe portable execution patterns for public or synthetic workloads. They are not a live price comparison, provider endorsement, or substitute for current provider documentation.

## Choose by workload

- Use CPU instances for indexing, annotation, and moderate sequence search.
- Use GPU instances for structure models and other accelerator-bound work.
- Use batch or HPC schedulers when queues, shared data, and institutional controls already exist.
- Keep the campaign control plane and review packet portable across providers.

## Public-safety invariants

- Never place credentials in the repository, container image, user-data script, launch manifest, or worker environment unless the provider explicitly requires a narrowly scoped runtime identity.
- Use short-lived identities, least-privilege roles, and bucket-prefix restrictions.
- Pin images by digest and verify downloaded artifacts with published hashes or signatures.
- Keep raw, heavy, private, and unpublished data outside this repository.
- Return compact summaries, manifests, versions, and hashes.
- Set a budget, timeout, and operator-side cleanup path before launch.
- Verify current pricing, availability, regional rules, licenses, and provider terms at launch time.

## Provider references

- [AWS pattern](aws-bio-tools.md)
- [Google Cloud pattern](gcp-bio-tools.md)
- [GPU marketplace pattern](neocloud-bio-tools.md)

The dispatch templates under `images/genecluster-superpowers/dispatch/` are reference implementations. Review permissions, identities, checksums, image digests, and cleanup behavior before adapting them.
