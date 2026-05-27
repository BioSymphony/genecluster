---
name: Bug report
about: A validator failed, an artifact came out wrong, or the agent got stuck
labels: bug
---

## Mission

Which campaign or mission were you running? (Plain-language description is fine.)

## Route

Which route did the agent pick? (annotation-direct, transcript-first, genome-context, synteny, transcriptome-only, rescue, next-experiment-design)

## Claim ceiling

What claim ceiling did the route card record?

## What you expected

What did you expect to see?

## What you got

What did you see instead? Include validator output and the exact command (or agent action) that produced it. Redact any secrets, pod IDs, or local paths before pasting.

## Environment

- OS:
- Python version:
- Agent (Claude Code, Codex, Symphony, other):
- Provider lane (local, RunPod, AWS, GCP, Vast.ai, Lambda Labs, SSH/HPC):

## Validators that ran

Paste output from `make public-release-check` or the failing preflight, if relevant.
