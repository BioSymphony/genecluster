# GeneCluster Annotation-Direct Engine

Stable entrypoint for annotation-direct GeneCluster campaigns.

```bash
python3 pipeline/genecluster_annotation_direct/run.py \
  --species coptis_chinensis \
  --proteome /opt/inputs/proteome.faa \
  --gff /opt/inputs/genomic.gff \
  --queries /opt/inputs/queries.faa \
  --pfam-hmm /opt/dbs/Pfam-A.hmm \
  --swissprot-dmnd /opt/dbs/swissprot.dmnd \
  --workdir /workspace/genecluster \
  --window-kb 50 \
  --threads 8
```

The implementation currently delegates to the delivered campaign engine so the
Coptis regression stays bit-for-bit close to the shipped workflow while Atlas
campaigns can depend on a non-demo path.
