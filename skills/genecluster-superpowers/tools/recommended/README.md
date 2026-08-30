# Recommended tool helpers

This directory contains opt-in installers, templates, and wrappers for a subset of the public tool inventory.

The scripts preserve documented minimums or checked baselines. A minimum such as `>=1.6.5` is not an exact pin. Review upstream changes and verify hashes or signatures before installing downloaded artifacts.

| Helper | Scope |
|---|---|
| `install-cheap.sh` | cblaster, clinker, JCVI, MMseqs2, igv-reports, Quarto |
| `install-medium.sh` | plantiSMASH and MIBiG |
| `install-heavy.sh` | Foldseek, ProstT5, CLEAN, and reference databases |
| `templates/` | public input and issue-contract templates |
| `wrappers/` | compact output adapters |

See the [tooling status](https://github.com/BioSymphony/genecluster/blob/main/docs/biosymphony-tooling-status.md) before adopting a version. Heavy data and model caches belong under ignored runtime storage or an external work directory, never in the repository.

Installers are convenience references, not unattended production bootstrap scripts. Inspect them, supply immutable sources and published checksums where available, and use least-privilege credentials outside the repository.
