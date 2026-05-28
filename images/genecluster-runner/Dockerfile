# syntax=docker/dockerfile:1
FROM condaforge/mambaforge:24.9.2-0

ARG DEBIAN_FRONTEND=noninteractive

RUN mamba install -y -n base \
      -c bioconda -c conda-forge \
      'blast>=2.15' \
      'diamond>=2.1' \
      'mmseqs2>=15' \
      'hmmer>=3.4' \
      'miniprot>=0.12' \
      'sra-tools>=3.0' \
      'ncbi-datasets-cli>=16' \
      'minimap2>=2.28' \
      'openjdk>=17' \
      'python>=3.11,<3.13' \
      'sqlite>=3.45' \
      pip \
      curl wget jq rsync ca-certificates \
    && mamba clean -afy \
    && rm -rf /opt/conda/pkgs/*

RUN curl -s https://get.nextflow.io | bash \
    && mv nextflow /usr/local/bin/nextflow \
    && chmod +x /usr/local/bin/nextflow

RUN blastp -version \
 && tblastn -version \
 && blastdbcmd -version \
 && command -v update_blastdb.pl \
 && diamond version \
 && mmseqs version \
 && hmmsearch -h | head -3 \
 && miniprot --version \
 && minimap2 --version \
 && fasterq-dump --version \
 && datasets version \
 && nextflow -v \
 && python3 --version \
 && sqlite3 --version \
 && curl --version

WORKDIR /workspace
CMD ["/bin/bash", "-l"]
