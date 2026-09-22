# Annotation-Direct Entry Point

`run.py` delegates to `pipeline/demo3/run.py`. That engine is absent from this package, so this entry point cannot run an analysis by itself.

Use the [tool-calling guide](../../docs/tooling/tool-chaining.md) for commands and wrappers included in the public package. Use the [fixture demo](../../docs/demo-campaign-dry-run.md) to inspect example outputs without external tools.

`python3 pipeline/genecluster_annotation_direct/run.py --help` reports the missing dependency. An analysis invocation exits with status 2 until the engine is supplied.
