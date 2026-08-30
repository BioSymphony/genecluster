# JCVI MCScan quickstart

**Status:** available; repository minimum 1.6.5; upstream 1.6.6 as of 2026-08-30.

```bash
python3 -m pip install "jcvi>=1.6.5"
python3 -m jcvi.compara.catalog --help
```

A minimal synteny workflow prepares normalized BED and sequence inputs, runs the selected alignment backend, creates anchors, and renders a plot. Follow the current [MCScan guide](https://github.com/tanghaibao/jcvi/wiki/MCscan-(Python-version)) for file naming and layout.

Record assemblies, annotations, identifier normalization, JCVI and backend versions, commands, anchor files, plot outputs, and hashes. State assembly quality and do not infer conserved function from synteny alone.
