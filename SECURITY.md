# Security

Do not report secrets by opening a public issue.

This repo must not contain API keys, tokens, registry credentials, signed URLs, private provider IDs, unpublished biological sequences, private structures, raw reads, or controlled datasets.

Use [GitHub private vulnerability reporting](https://github.com/BioSymphony/genecluster/security/advisories/new). If that form is unavailable, contact the maintainer through a private channel instead of posting details publicly.

When reporting, do not paste secret values. Describe the file path, commit or snapshot, and class of issue so maintainers can rotate, revoke, and clean up safely.

If you find sensitive material in a local checkout:

1. Stop publication and distribution.
2. Revoke or rotate affected credentials through their provider.
3. Remove the material from the working tree and generated artifacts.
4. Review history, caches, release archives, and mirrors.
5. Publish only after the private report is resolved.
