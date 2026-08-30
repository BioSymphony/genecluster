# Tooling radar

Last reviewed: 2026-08-30

This radar tracks promising public tools and data sources that are not yet adopted by GeneCluster. A listing is not an endorsement or integration claim.

## Admission criteria

A candidate should have:

- a public source and clear license or access terms;
- a versioned installation or service interface;
- a plausible GeneCluster input and output contract;
- a public or synthetic fixture;
- manageable compute, storage, and redistribution requirements;
- a clear claim boundary.

## Near-term candidates

| Candidate | Current public state | Potential use | Integration requirement |
|---|---|---|---|
| Ensembl Plants | release 63 | plant assemblies, annotations, orthology | Normalize stable accessions and checksums into source ledgers |
| ATTED-II | v13 | plant coexpression support | Keep correlation evidence separate from physical clustering |
| Rhea | release 141 | curated biochemical reactions | Map reaction identifiers without inferring gene function from reaction membership alone |
| RetroRules | 3.0.0 | reaction-rule expansion | Record rule diameter, release, and uncertainty |
| HIT-EC | public source repository | EC prediction with abstention | Add immutable code/model versions and a public protein fixture |
| Proto | public Git repository | sequence-design experimentation | Keep planned until a public toy fixture and stable install contract exist |

Sources: [Ensembl Plants data](https://plants.ensembl.org/info/data/ftp/index.html), [ATTED-II](https://atted.jp/), [Rhea](https://www.rhea-db.org/), [RetroRules](https://retrorules.org/download), [HIT-EC](https://github.com/datax-lab/HIT-EC), and [Proto](https://github.com/evo-design/proto-language).

## Later candidates

- workflow portability through Nextflow, Snakemake, or another reproducible engine;
- provenance packaging with RO-Crate profiles;
- additional public synteny and coexpression sources;
- static review surfaces for large cluster comparisons;
- provider-neutral artifact transfer with explicit allowlists and hashes.

These remain planned until a concrete public fixture and maintainer need justify the extra dependency surface.

## Promotion path

1. select one public or synthetic fixture;
2. record the official source, version, license, and access date;
3. define exact inputs, outputs, failure states, and resource limits;
4. run the fixture outside the public source tree when it creates heavy data;
5. retain compact outputs, versions, commands, and hashes;
6. add a quickstart or wrapper;
7. update the canonical tooling status.

Do not record private tracker IDs, credentials, local paths, provider payloads, raw data, unpublished sequences, or private output locations.
