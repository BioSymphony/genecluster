# Public release safety

The public repository contains reusable contracts, checks, examples, templates, and summary guidance.

## Exclude these items

Do not publish:

- credentials, tokens, signed URLs, cookies, or environment files;
- account, provider, volume, pod, or instance identifiers;
- raw reads, private sequences, controlled data, databases, indexes, or model weights;
- runtime directories, logs, caches, or provider responses;
- private tracker content, local paths, personal email addresses, or unpublished results.

## Allowed content

You can publish:

- public or synthetic examples;
- schemas, templates, validators, and wrappers;
- stable public accessions and citations;
- placeholder paths and credential variable names;
- compact summaries, versions, hashes, and claim limits.

## Run the checks

Before publication, run:

```bash
make public-release-check
```

For an audit without demo execution, run:

```bash
make public-audit-strict
```

The audit removes generated Python caches and `.demo-output` before scanning. The content scan includes SVGs, examples, tests, and embedded binary text. It rejects local paths, common credential formats, restricted folders, and unreviewed artifacts. Findings report file locations and rule names without printing matched values.

The public tree has a 12 MiB total size limit and a 5 MiB per-file limit. Raw-data exceptions name exact small public fixtures. Keep unused media, model files, and downloaded catalogs outside the release tree.

Review the complete diff and visible media before publication. Pattern checks cannot detect every secret, private discussion, or sensitive image. Check the exact commit that will be published; these commands do not inspect older Git history.

## Dispatch rules

Store dispatch output in an ignored runtime directory. Keep credentials in the operator's secret store. Do not send provider API keys to workers.

Use private storage, short-lived access, exact permissions, image digests, and verified downloads. Pull only approved summary files.

## Release history

Publish only reviewed public history. Do not copy non-public repository history into a public release.
