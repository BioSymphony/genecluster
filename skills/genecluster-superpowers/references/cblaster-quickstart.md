# cblaster and clinker quickstart

**Status:** available upstream; public end-to-end wrapper fixture planned.

Reviewed versions: cblaster 1.4.2 and clinker 0.0.32.

```bash
python3 -m pip install "cblaster>=1.4.0" "clinker>=0.0.32"

cblaster search \
  --query_file <QUERY_FASTA> \
  --mode remote \
  --output .runtime/cblaster-out/clusters.csv \
  --plot .runtime/cblaster-out/clusters.html

cblaster extract \
  --query .runtime/cblaster-out/clusters.csv \
  --output .runtime/cblaster-out/clusters \
  --format genbank

clinker .runtime/cblaster-out/clusters/*.gbk \
  --plot .runtime/cblaster-out/clinker.html
```

The clinker CLI does not document `--output_html` or `--output_svg`. Use a separately documented browser/rendering step for a static export.

The local route requires prepared GenBank or compatible genome inputs. Record query identifiers, database and access date, versions, parameters, outputs, and hashes.
