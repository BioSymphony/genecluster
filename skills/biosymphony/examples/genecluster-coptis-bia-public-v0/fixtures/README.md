# Coptis BIA example fixtures

Tiny synthetic fixtures for the local dry run. None of these files are large enough to support a real biological claim; they exist so the local validators and the demo harness can exercise the contract flow without any provider launch or data download.

## Files

| File | Type | What consumes it |
| --- | --- | --- |
| `query-with-controls.faa` | Synthetic FASTA with one pathway-query sequence plus the three required controls (ACT2, GAPDH, random shuffle). | `genecluster_annotation_scout.py` (route-scout query input). |
| `fixture-proteome.faa` | Synthetic two-sequence proteome (protA, protB). | Route-scout joined-evidence check. |
| `fixture-genomic.gff` | Minimal GFF3 covering the fixture proteome's locus. | Route-scout neighborhood join. |
| `route-source-ledger.tsv` | One-row source ledger pointing at the fixture proteome and GFF, with `source_id=example_fixture`. | Route-scout source input. |
| `candidate_hits.tsv` | Three-row synthetic candidate-hits table representing one BBE-like hit, one 6OMT-like hit, and one CYP719-like domain hit. | `genecluster_dossier_skeleton.py` (dossier rendering). |

## Use Only For

- Local control-plane validation.
- Demo harness output.
- Schema and contract regression.

## Do Not Use For

- Any scientific claim about *Coptis chinensis*, the BIA pathway, or any candidate enzyme.
- Production candidate search. Real campaigns materialize their own data through the provider data-materialization lane.
- Benchmarking. The fixtures are too small to be representative of any real run.
