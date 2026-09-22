# Recommended Tool Helpers

This directory contains opt-in installers and per-tool command templates. Calling wrappers are under `skills/genecluster-superpowers/scripts/`; see the [calling guide](https://github.com/BioSymphony/genecluster/blob/main/docs/tooling/tool-chaining.md) for their readiness and required inputs.

The scripts preserve documented minimums or checked baselines. A minimum such as `>=1.6.5` is not an exact pin. Review upstream changes and verify hashes or signatures before installing downloaded artifacts.

| Helper | Scope |
|---|---|
| `install-cheap.sh` | cblaster, clinker, JCVI, MMseqs2, igv-reports, Quarto |
| `install-medium.sh` | plantiSMASH and MIBiG |
| `install-heavy.sh` | Foldseek, ProstT5, CLEAN, and reference databases |
| Per-tool directories | Command templates and small rendering examples |

See the [tooling status](https://github.com/BioSymphony/genecluster/blob/main/docs/biosymphony-tooling-status.md) before adopting a version. Heavy data and model caches belong under ignored runtime storage or an external work directory, never in the repository.

Installers are convenience references, not unattended production bootstrap scripts. Inspect them, supply immutable sources and published checksums where available, and use least-privilege credentials outside the repository.
