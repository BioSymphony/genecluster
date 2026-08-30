# JCVI MCScan

**Status:** available; repository minimum 1.6.5; current upstream 1.6.6 as of 2026-08-30.

JCVI provides Python MCScan workflows for pairwise and multi-species synteny. It can connect cluster-level findings to chromosome-scale conservation when suitable assemblies and annotations are available.

## Install

```bash
python3 -m pip install "jcvi>=1.6.5"
python3 -m jcvi.compara.catalog --help
```

LAST or another documented alignment backend may also be required.

## Output contract

Record source GFF and sequence identifiers, conversion commands, JCVI and backend versions, parameters, anchor files, plots, and hashes. Synteny claims should state assembly quality, annotation source, and any name normalization applied.

Sources: [JCVI on PyPI](https://pypi.org/project/jcvi/) and the [MCScan guide](https://github.com/tanghaibao/jcvi/wiki/MCscan-(Python-version)).
