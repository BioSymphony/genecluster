![BioSymphony GeneCluster banner](docs/diagrams/genecluster-retro-synth-banner.jpg)

# BioSymphony GeneCluster

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Cite](https://img.shields.io/badge/cite-CITATION.cff-blue.svg)](CITATION.cff)

GeneCluster gives your agent tool guides and command wrappers for
comparative genomics and transcriptome analysis. Your agent can plan an
analysis, run the tools, and connect their outputs.

## Start With Your Agent

Share the [GeneCluster repository](https://github.com/BioSymphony/genecluster) with your agent
and ask it to read [GeneCluster Superpowers](skills/genecluster-superpowers/SKILL.md).
Give it your question, organisms, and available data.

> Read GeneCluster Superpowers. Compare candidate genes across [organisms]
> using [my reference proteins, target proteomes, and matching genome
> annotations]. Choose and set up the tools you need, then run the analysis.
> Return a candidate table with source accessions and compare gene order
> where coordinates are available.

<a href="docs/diagrams/genecluster-session-flow.svg">
  <picture>
    <source media="(max-width: 720px)" srcset="docs/diagrams/genecluster-session-flow-mobile.svg">
    <img src="docs/diagrams/genecluster-session-flow.svg" alt="The agent chooses tools, sets them up, runs them, and prepares the next input.">
  </picture>
</a>

## Tools Your Agent Can Use

| Task | Tools | What you get |
|---|---|---|
| Find public inputs | [NCBI Datasets, Ensembl, and nf-core/fetchngs](docs/biosymphony-next-tooling-radar.md#find-public-inputs) | Assembly accessions, annotation releases, and RNA-seq run accessions |
| Search for protein homologs | [MMseqs2](docs/tooling/mmseqs2.md), BLAST, DIAMOND | Protein IDs, alignments, and scores |
| Annotate protein families and domains | [InterProScan and HMMER/Pfam](docs/tooling/interproscan-pfam.md) | Signature IDs and residue ranges |
| Compare protein folds | [Foldseek + ProstT5](docs/tooling/foldseek-prostt5.md) | Matches from structures or sequence-derived representations |
| Look up plant pathways and enzymes | [PlantCyc and P450Rdb](docs/tooling/plantcyc-p450rdb.md), [Rhea](docs/biosymphony-next-tooling-radar.md#find-public-inputs) | Pathway, enzyme, and reaction records |
| Predict candidate gene clusters | [antiSMASH](docs/biosymphony-antismash-cookbook.md) for bacteria and fungi, [plantiSMASH](docs/tooling/plantismash.md) for plants | Annotated genomic regions |
| Compare genomic neighborhoods | [cblaster + clinker](docs/tooling/cblaster-clinker.md) | Conserved neighborhoods and interactive gene maps |
| Compare gene order | [JCVI MCScan](docs/tooling/jcvi-mcscan.md) | Synteny anchors and plots |
| Present results | [Quarto](docs/tooling/quarto.md), [Cytoscape.js](docs/tooling/cytoscape-js.md) | HTML reports and interactive networks |

The [tooling radar](docs/biosymphony-next-tooling-radar.md) covers tools to
evaluate, including OrthoFinder for orthogroups, IsoQuant and SQANTI3 for long-read
transcriptomes, and [CLEAN and HIT-EC](docs/tooling/clean-hit-ec.md) for enzyme
classification.

## Example Requests For Your Agent

- **Plan a comparison.** “Find public genome assemblies and matching annotations
  for these three plant species. Return the assembly accessions and a plan for
  comparing gene order, including required files and compute.”
- **Find and annotate homologs.** “Search these plant proteomes with my reference
  proteins. Annotate the matches and return a table with protein IDs, alignment
  coverage, and domain accessions.”
- **Compare genomic neighborhoods.** “Find regions around these reference genes
  in my annotated genomes. Return a gene map and a table of homologs with their
  assembly accessions and coordinates.”
- **Search transcriptomes.** “Find transcripts related to this reference
  protein in my transcriptome assemblies. Report transcript IDs and domain
  matches for the predicted proteins.”
- **Compare folds.** “Search this reference structure set for matches to my
  candidate proteins. Report the structural scores alongside sequence evidence.”

## Set Up, Run, And Connect Tools

Your agent uses the [tool knowledge base](docs/tooling/README.md) to check file
formats and database requirements. It checks tested versions in the
[version table](docs/biosymphony-tooling-status.md), sets up tools with the
[installers and templates](tools/recommended/README.md), and follows the
[calling guide](docs/tooling/tool-chaining.md) for runnable wrappers and
commands that need adapting.

<a href="docs/diagrams/genecluster-tool-chain.svg">
  <picture>
    <source media="(max-width: 720px)" srcset="docs/diagrams/genecluster-tool-chain-mobile.svg">
    <img src="docs/diagrams/genecluster-tool-chain.svg" alt="MMseqs2 finds protein matches. The agent extracts their sequences, adds domain annotations, and joins the results by protein ID for a Quarto report.">
  </picture>
</a>

To compare neighborhoods, your agent can extract GenBank regions from
cblaster’s search session and display them in clinker.

For longer analyses, your agent can use the
[campaign helpers](skills/biosymphony/SKILL.md) to track inputs and resume stages.
See [Contributing](CONTRIBUTING.md) for maintainer checks.
