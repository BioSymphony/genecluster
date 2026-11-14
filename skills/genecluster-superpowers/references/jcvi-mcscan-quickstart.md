# JCVI MCScan quickstart

The repository minimum is JCVI 1.6.5. See the [JCVI MCScan guide](docs/tooling/jcvi-mcscan.md) for the upstream release and fixture status.

```bash
python3 -m pip install "jcvi>=1.6.5"
python3 -m jcvi.compara.catalog --help
```

A minimal synteny workflow prepares normalized BED and sequence inputs, runs the selected alignment backend, creates anchors, and renders a plot. Follow the current [MCScan guide](https://github.com/tanghaibao/jcvi/wiki/MCscan-(Python-version)) for file naming and layout.

Record assemblies, annotations, identifier normalization, JCVI and backend versions, commands, anchor files, plot outputs, and hashes. State assembly quality and do not infer conserved function from synteny alone.
