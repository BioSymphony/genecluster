# Call and Chain Tools

Use the wrappers to run a tool. Check its output before joining results or preparing the next input.

## Choose a Tool

Read the [knowledge base](README.md) for inputs and commands, then check the [version table](../biosymphony-tooling-status.md). A checked tool baseline describes earlier output checks; wrapper readiness is separate.

| Entry point | What it does | Readiness |
|---|---|---|
| `run-mmseqs2.sh` | Build protein databases, run an iterative search, and export six named columns | Synthetic run passed with MMseqs2 18-8cc5c |
| `run-cblaster.sh` | Search an annotated genome or prepared database, extract GenBank regions, and call clinker | Two-cluster synthetic run passed with cblaster 1.4.0 |
| `run-foldseek-prostt5.sh` | Outline sequence-derived structure search | Adapt model, database, flags, and output fields |
| `run-jcvi-mcscan.sh` | Outline pairwise synteny analysis | Supply matching coordinate and CDS inputs; adapt the template |
| `run-plantismash.sh` | Outline plant cluster prediction | Draft expects matching genomic.fna and genomic.gff |
| `run-clean-hit-ec.sh` | Outline enzyme-function prediction | Adapt model setup, input splitting, and output parsing |

Find wrappers under `skills/genecluster-superpowers/scripts/` and installers under `tools/recommended/`.

## Search Proteins

With MMseqs2 installed, run from the repository root and substitute your input and output paths:

```bash
bash skills/genecluster-superpowers/scripts/run-mmseqs2.sh \
  --query queries.faa --target proteins.faa \
  --out-dir /path/to/work/mmseqs-search dataset
```

The wrapper writes six tab-separated columns (`query,target,evalue,bits,qaln,taln`) to `queries-vs-target.outfmt6` and saves a schema sidecar. Use a fresh output directory for each input set.

To add domain evidence, extract hit sequences from the target FASTA and annotate them with [HMMER or InterProScan](interproscan-pfam.md). Join annotations to the search table by protein ID.

## Compare Gene Clusters

Install cblaster 1.4.0, DIAMOND, and clinker. Set the contact email as shown in the [cblaster guide](cblaster-clinker.md), then run:

```bash
bash skills/genecluster-superpowers/scripts/run-cblaster.sh \
  --organism dataset --query queries.faa \
  --genbank annotated-genome.gbk --out-dir /path/to/work/cluster-search
```

Use a new or empty output directory. To reuse a prepared cblaster database, replace `--genbank` with `--database /path/to/database/prefix`. The database needs both `.dmnd` and `.sqlite3` files.

The wrapper preserves `search-session.json`, exports annotated GenBank regions, and passes those files to clinker. The summary TSV describes hits; cluster extraction reads the session JSON. See the [cblaster guide](cblaster-clinker.md) for GFF inputs and output details.

## Prepare Each Handoff

| Next analysis | Check before calling it |
|---|---|
| Protein annotation | Extract sequences for the selected hit IDs; retain source identifiers |
| Structure search | Prepare structures or compatible ProstT5-derived inputs and target databases |
| Gene-order comparison | Match sequence IDs to genomic coordinates and use the expected CDS format |
| Cluster comparison | Retain genome coordinates and annotated regions |
| Combined table or report | Match column names, identifiers, units, and coordinate conventions |

The campaign's Python table helpers consume compact tables in documented schemas. Convert native tool output before passing it to these helpers. The [fixture demo](../demo-campaign-dry-run.md) exercises table processing and report checks without running the external tools.

Keep the commands, versions, input references, and output locations needed to reproduce a result. For longer work, [campaign helpers](https://github.com/BioSymphony/genecluster/blob/main/skills/biosymphony/SKILL.md) add resumable stages and input tracking. A tracker is optional.
