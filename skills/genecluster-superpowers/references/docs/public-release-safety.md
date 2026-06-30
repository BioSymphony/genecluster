# Public Release Safety

BioSymphony GeneCluster is designed to publish the reusable control plane without publishing non-public run state or internal source material. A public snapshot should contain contracts, check scripts, examples, templates, and summary runbooks. It should exclude operational secrets, provider state, raw biological data, and private tracker context.

## Must Stay Out

- API keys, tokens, registry credentials, signed URLs, cookie dumps, and `.env` files.
- Provider response JSON, pod or instance IDs, network volume IDs, account numbers, monitor URLs, and stop commands containing credentials.
- Raw reads, private sequences, unpublished structures, controlled datasets, full genome mirrors, BLAST/DIAMOND/HMMER indexes, and model weights.
- `.runtime/`, `logs/`, `artifacts/`, provider dispatch directories, bytecode caches, local app state, and private automation stack paths.
- Private tracker text, private issue IDs, worker lane names, and local operator usernames or email addresses.

## Allowed Public Material

- Public-safe ledgers, schemas, templates, and check scripts.
- Public examples with synthetic, placeholder, or already-public accession data.
- Summary-only notes with provider identifiers omitted.
- Cloud dispatch templates that require credentials from environment variables or untracked secure stores.
- Review-surface examples that contain summaries, hashes, caveats, and provenance, not raw/heavy source data.

## Required Check

Run this before any public commit or archive:

```bash
make public-release-check
```

The check fails on local runtime folders, bytecode caches, provider artifacts, heavy biological extensions, local absolute paths, private registry owners, personal emails, and known non-public provider IDs.

## Provider Dispatch Rules

- Default dispatch output must live under `.runtime/provider-dispatch/` or another ignored path.
- Do not write API keys into payload files, launch manifests, or container environment.
- Prefer provider storage, S3/GCS, SSH, or operator-side tools for artifact pull.
- If HTTP proxy pull is unavoidable, serve only a summary directory, keep the TTL short, and expose no raw data or credentials.
- A public launch manifest may contain placeholders and operator-side command shapes, but not real keys, account IDs, volume IDs, pod IDs, or local private-key paths.

## First Public Commit

Use a fresh public history after the checks pass. Do not copy private git history into the public repository.
