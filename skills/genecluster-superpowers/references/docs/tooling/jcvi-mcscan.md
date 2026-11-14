# JCVI MCScan

The repository minimum is JCVI 1.6.5. Upstream 1.6.9 was released on 2026-11-02 and still needs a fixture run before promotion. [JCVI 1.6.9](https://pypi.org/project/jcvi/1.6.9/)

JCVI provides Python MCScan workflows for pairwise and multi-species synteny. It can connect cluster-level findings to chromosome-scale conservation when suitable assemblies and annotations are available.

## Install

```bash
python3 -m pip install "jcvi>=1.6.5"
python3 -m jcvi.compara.catalog --help
```

For the pairwise MCScan workflow, prepare BED files and matching CDS FASTA files. Verify that each BED feature ID matches its FASTA ID after normalization. The upstream pairwise example uses LAST. [MCScan guide](https://github.com/tanghaibao/jcvi/wiki/MCscan-(Python-version))

## Output contract

Record source GFF and sequence identifiers, conversion commands, JCVI and backend versions, parameters, anchor files, plots, and hashes. Synteny claims should state assembly quality, annotation source, and any name normalization applied.
