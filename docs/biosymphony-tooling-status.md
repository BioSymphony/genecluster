# Tooling Status

Upstream releases checked on 2026-11-13. Use the recorded baseline to reproduce
an earlier analysis. The [calling guide](tooling/tool-chaining.md) records
wrapper readiness and the [tooling radar](biosymphony-next-tooling-radar.md)
lists candidates for evaluation.

| Tool | Upstream release | GeneCluster baseline or next check |
|---|---|---|
| MMseqs2 | [18-8cc5c](https://github.com/soedinglab/MMseqs2/releases/tag/18-8cc5c) | 18. Rechecked the six-column export with the native binary. |
| DIAMOND | [2.2.8](https://github.com/bbuchfink/diamond/releases/tag/v2.2.8) | 2.2.5 in the cblaster smoke test. |
| Foldseek | [10-941cd33](https://github.com/steineggerlab/foldseek/releases/tag/10-941cd33) | 10. Record the ProstT5 revision separately. |
| HMMER | [3.4](https://hmmer.org/) | Record the Pfam release with each HMM search. |
| Pfam | [39.0](https://ftp.ebi.ac.uk/pub/databases/Pfam/releases/Pfam39.0/) | Record the Pfam archive version with each search. Compare signature calls before upgrading. |
| InterProScan 5 | [5.78-109.0](https://interproscan-docs.readthedocs.io/en/v5/ReleaseNotes.html) | Final v5 release. Use the recorded v5 bundle for replay. |
| InterProScan 6 | [6.0.3.0](https://github.com/ebi-pf-team/interproscan6/releases/tag/6.0.3.0) | Evaluate the Nextflow runtime, parser, and separately pinned [InterPro data](https://www.ebi.ac.uk/interpro/api/entry/pfam/). |
| antiSMASH | [8.0.4](https://github.com/antismash/antismash/releases/tag/8-0-4) | 8.0.4 cookbook. |
| plantiSMASH | [2.0.4](https://github.com/plantismash/plantismash/releases/tag/plantismash-2.0.4) | 2.0.4 with a non-editable source install. |
| DeepBGC | [0.1.31 on PyPI](https://pypi.org/project/deepbgc/0.1.31/) | 0.1.31. |
| cblaster | [1.4.2](https://github.com/gamcil/cblaster/releases/tag/v1.4.2), also on [PyPI](https://pypi.org/project/cblaster/1.4.2/) and [Bioconda](https://anaconda.org/bioconda/cblaster) | Use 1.4.0. On the two-cluster fixture, 1.4.2 writes search results and fails while serializing its heatmap. |
| clinker | [0.0.32](https://pypi.org/project/clinker/0.0.32/) | 0.0.32 in the cblaster smoke test. |
| JCVI | [1.6.9](https://pypi.org/project/jcvi/1.6.9/) | 1.6.5. Compare anchors before updating the baseline. |
| IQ-TREE | [3.1.4](https://github.com/iqtree/iqtree3/releases/tag/v3.1.4) | Use the recorded 2.x version to reproduce an earlier 2.x tree. |
| MIBiG | [4.0](https://mibig.secondarymetabolites.org/download) | Record the release with cluster matches. |
| igv-reports | [1.17.0](https://github.com/igvteam/igv-reports/releases/tag/v1.17.0) | 1.16.2. Recheck the generated HTML before upgrading. |
| Cytoscape.js | [3.35.0](https://github.com/cytoscape/cytoscape.js/releases/tag/v3.35.0) | 3.33.3. Check interactions and export before upgrading. |
| Quarto | [1.11.9](https://github.com/quarto-dev/quarto-cli/releases/tag/v1.11.9) | 1.9.37 for replay. 1.11.9 rendered a synthetic HTML book and manuscript. Prefer 1.11 for new installs. |
| Plant Metabolic Network | [17](https://plantcyc.org/pmn-17-released/) | Public lookup. Complete database downloads follow [provider terms](https://plantcyc.org/downloads/). |
| P450Rdb | [2.0](https://www.cellknowledge.com.cn/p450rdb_v2/index.html) | Keep experimentally curated entries and model predictions distinct. |

Before changing a baseline, run a public or synthetic fixture and check the
[output contract](tooling/tool-evaluation.md). Record tool, model, and database
versions separately.
