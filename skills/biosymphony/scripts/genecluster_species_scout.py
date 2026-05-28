#!/usr/bin/env python3
"""genecluster_species_scout, early-data-research fan-out scout.

Given a target species + pathway, auto-discover related species with potentially
overlapping pathway data and tabulate their data state. Designed to run BEFORE
any campaign launch, when the operator has NOT supplied a comparative species
list. Produces a structured 5-section report on:

  - Data (assembly state, RNA-Seq breadth, annotation status)
  - Inputs (seed protein query set, if pathway resolves to KEGG)
  - Relevance (pathway overlap; sister vs convergent producers)
  - Novelty (existing publications mapping pathway-to-species)
  - Importance (composite comparative value ranking)

The scout is network-light (stdlib only, urllib + json + csv). It hits:

  - NCBI E-utilities (taxonomy walks, SRA esearch)
  - NCBI Datasets v2 REST (assembly summaries)
  - NGDC GWH plants index (fallback when NCBI empty)
  - KEGG REST (pathway → enzyme list)

It reads ``data/pathway-species-catalog.tsv`` (repo-local) for known producers,
then fans out via tax-walk to find additional candidates. Novelty + Importance
are pre-populated from catalog rows when present; for unknown pathways the
scout prints a TODO placeholder that ``genecluster_campaign_preflight`` fills
in via a literature-audit agent dispatch.

CLI

  ./genecluster_species_scout.py \\
      --target "Coptis chinensis" \\
      --pathway BIA \\
      --out-dir .runtime/<campaign-id>-preflight \\
      [--max-candidates 12] \\
      [--related-species "Berberis vulgaris,Coptis teeta,Eschscholzia californica"] \\
      [--catalog data/pathway-species-catalog.tsv] \\
      [--ncbi-api-key $NCBI_API_KEY] \\
      [--dry-run]

Outputs

  <out-dir>/species_scout.tsv              , one row per candidate
  <out-dir>/species_scout.json             , full structured findings
  <out-dir>/relevance-novelty-summary.md   , 5-section human report
  <out-dir>/seed-query-candidates.tsv      , KEGG-derived enzyme list (if pathway resolved)

Exit codes

  0  Success; report written
  1  Argument error
  2  Network error after retries
  3  No candidates found (target unknown AND tax-walk empty)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DATASETS_BASE = "https://api.ncbi.nlm.nih.gov/datasets/v2"
NGDC_BASE = "https://ngdc.cncb.ac.cn/gwh"
KEGG_BASE = "https://rest.kegg.jp"
USER_AGENT = os.environ.get(
    "BIOSYMPHONY_USER_AGENT",
    "BioSymphony-GeneCluster-SpeciesScout/0.1 (contact: project-maintainer)",
)
DEFAULT_TIMEOUT = 30
RETRIES = 3
RETRY_BACKOFF = 1.5

PATHWAY_KEGG_HINTS = {
    "BIA": "map00950",
    "Benzylisoquinoline alkaloid biosynthesis": "map00950",
    "MIA": "map00901",
    "Monoterpene indole alkaloid biosynthesis": "map00901",
    "Indole alkaloid biosynthesis": "map00901",
    "Tropane alkaloid biosynthesis": "map00960",
    "Tropane piperidine pyridine alkaloid biosynthesis": "map00960",
    "Isoquinoline alkaloid biosynthesis": "map00950",
}

TISSUE_TOKENS = (
    "root", "leaf", "leaves", "stem", "flower", "fruit", "rhizome",
    "seed", "latex", "capsule", "shoot", "callus", "cell_culture",
    "whole_plant", "whole plant", "bark",
)

CONTROL_QUERIES = (
    {
        "query_id": "POSCTRL_ACTIN",
        "enzyme_name": "Actin (ACT2)",
        "ec": ", ",
        "uniprot": "P0CJ47",
        "ref_species": "Arabidopsis thaliana",
        "role": "positive control",
        "notes": "Universal housekeeping protein; must hit >90% identity in target proteome",
    },
    {
        "query_id": "POSCTRL_GAPDH",
        "enzyme_name": "Glyceraldehyde-3-phosphate dehydrogenase",
        "ec": "1.2.1.12",
        "uniprot": "P25856",
        "ref_species": "Arabidopsis thaliana",
        "role": "positive control",
        "notes": "Backup housekeeping; >85% identity expected",
    },
    {
        "query_id": "NEGCTRL_RANDOM",
        "enzyme_name": "Shuffled control",
        "ec": ", ",
        "uniprot": ", ",
        "ref_species": ", ",
        "role": "negative control",
        "notes": "150 aa Fisher-Yates shuffle of POSCTRL_ACTIN; should return 0 hits",
    },
)


def log(msg: str, *, level: str = "INFO") -> None:
    sys.stderr.write(f"[species-scout {level}] {msg}\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _http_get(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """GET with explicit User-Agent + retries. Returns raw body bytes."""
    last_exc: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout) as exc:
            last_exc = exc
            if attempt < RETRIES:
                wait = RETRY_BACKOFF ** attempt
                log(f"GET {url[:80]} failed ({exc}); retry {attempt}/{RETRIES} after {wait:.1f}s", level="WARN")
                time.sleep(wait)
    raise RuntimeError(f"HTTP GET failed after {RETRIES} retries: {url} ({last_exc})")


def http_json(url: str) -> Any:
    return json.loads(_http_get(url).decode("utf-8", errors="replace"))


def http_text(url: str) -> str:
    return _http_get(url).decode("utf-8", errors="replace")


def http_xml(url: str) -> ET.Element:
    return ET.fromstring(_http_get(url))


def with_api_key(url: str, api_key: str | None) -> str:
    if not api_key:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}api_key={urllib.parse.quote(api_key)}"


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@dataclass
class CatalogRow:
    pathway_id: str
    pathway_name: str
    species: str
    common_name: str = ""
    genus: str = ""
    family: str = ""
    plant_order: str = ""
    best_genome_accession: str = ""
    genome_source: str = ""
    genome_level: str = ""
    annotation_present: str = ""
    rna_seq_bioprojects: str = ""
    tissues_covered: str = ""
    year_latest: str = ""
    key_publication_pmid: str = ""
    key_publication_doi: str = ""
    comparative_value: str = ""
    novelty_window: str = ""
    campaign_used_in: str = ""
    last_audit_date: str = ""
    notes: str = ""


def read_catalog(path: Path) -> list[CatalogRow]:
    if not path.exists():
        return []
    rows: list[CatalogRow] = []
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for raw in reader:
            cleaned = {k: (raw.get(k, "") or "").strip() for k in raw}
            rows.append(
                CatalogRow(
                    pathway_id=cleaned.get("pathway_id", ""),
                    pathway_name=cleaned.get("pathway_name", ""),
                    species=cleaned.get("species", ""),
                    common_name=cleaned.get("common_name", ""),
                    genus=cleaned.get("genus", ""),
                    family=cleaned.get("family", ""),
                    plant_order=cleaned.get("plant_order", ""),
                    best_genome_accession=cleaned.get("best_genome_accession", ""),
                    genome_source=cleaned.get("genome_source", ""),
                    genome_level=cleaned.get("genome_level", ""),
                    annotation_present=cleaned.get("annotation_present", ""),
                    rna_seq_bioprojects=cleaned.get("rna_seq_bioprojects", ""),
                    tissues_covered=cleaned.get("tissues_covered", ""),
                    year_latest=cleaned.get("year_latest", ""),
                    key_publication_pmid=cleaned.get("key_publication_pmid", ""),
                    key_publication_doi=cleaned.get("key_publication_doi", ""),
                    comparative_value=cleaned.get("comparative_value", ""),
                    novelty_window=cleaned.get("novelty_window", ""),
                    campaign_used_in=cleaned.get("campaign_used_in", ""),
                    last_audit_date=cleaned.get("last_audit_date", ""),
                    notes=cleaned.get("notes", ""),
                )
            )
    return rows


def catalog_match_pathway(rows: list[CatalogRow], pathway: str) -> list[CatalogRow]:
    pathway_norm = pathway.strip().lower()
    matches: list[CatalogRow] = []
    for row in rows:
        if row.pathway_id.lower() == pathway_norm or pathway_norm in row.pathway_name.lower():
            matches.append(row)
    return matches


# ---------------------------------------------------------------------------
# NCBI taxonomy + datasets
# ---------------------------------------------------------------------------


@dataclass
class TaxonomyRecord:
    species: str
    taxid: str = ""
    genus: str = ""
    family: str = ""
    plant_order: str = ""
    lineage: list[str] = field(default_factory=list)
    error: str = ""


def fetch_taxonomy(species: str, api_key: str | None) -> TaxonomyRecord:
    """Resolve a binomial → taxid + lineage via E-utilities."""
    record = TaxonomyRecord(species=species)
    term = urllib.parse.quote(f"{species}[Scientific Name]")
    esearch_url = with_api_key(
        f"{NCBI_BASE}/esearch.fcgi?db=taxonomy&term={term}&retmode=json",
        api_key,
    )
    try:
        data = http_json(esearch_url)
        ids = (data.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            record.error = "taxid_not_found"
            return record
        record.taxid = ids[0]
    except Exception as exc:  # noqa: BLE001 - REST traversal
        record.error = f"esearch_failed:{exc}"
        return record

    efetch_url = with_api_key(
        f"{NCBI_BASE}/efetch.fcgi?db=taxonomy&id={record.taxid}&retmode=xml",
        api_key,
    )
    try:
        root = http_xml(efetch_url)
    except Exception as exc:  # noqa: BLE001
        record.error = f"efetch_failed:{exc}"
        return record

    for lineage_node in root.findall(".//Taxon/LineageEx/Taxon"):
        rank = (lineage_node.findtext("Rank") or "").strip()
        name = (lineage_node.findtext("ScientificName") or "").strip()
        if not name:
            continue
        record.lineage.append(f"{rank}:{name}" if rank else name)
        if rank == "genus":
            record.genus = name
        elif rank == "family":
            record.family = name
        elif rank == "order":
            record.plant_order = name
    if not record.genus and species:
        record.genus = species.split()[0]
    return record


def fetch_genus_siblings(genus: str, api_key: str | None, *, max_results: int = 50) -> list[str]:
    """Return all binomials in a genus that have any NCBI taxonomy entry at species rank."""
    if not genus:
        return []
    term = urllib.parse.quote(f"{genus}[Subtree] AND species[Rank]")
    url = with_api_key(
        f"{NCBI_BASE}/esearch.fcgi?db=taxonomy&term={term}&retmode=json&retmax={max_results}",
        api_key,
    )
    try:
        data = http_json(url)
        ids = (data.get("esearchresult") or {}).get("idlist") or []
    except Exception as exc:  # noqa: BLE001
        log(f"genus sibling search for {genus} failed: {exc}", level="WARN")
        return []
    if not ids:
        return []

    fetch_url = with_api_key(
        f"{NCBI_BASE}/efetch.fcgi?db=taxonomy&id={','.join(ids)}&retmode=xml",
        api_key,
    )
    try:
        root = http_xml(fetch_url)
    except Exception as exc:  # noqa: BLE001
        log(f"genus sibling efetch for {genus} failed: {exc}", level="WARN")
        return []
    species: list[str] = []
    for node in root.findall(".//Taxon"):
        rank = (node.findtext("Rank") or "").strip()
        if rank != "species":
            continue
        name = (node.findtext("ScientificName") or "").strip()
        if name and name not in species:
            species.append(name)
    return species


@dataclass
class AssemblyRecord:
    species: str
    accession: str = ""
    assembly_level: str = ""
    submitter: str = ""
    submission_year: str = ""
    chromosome_count: str = ""
    annotation_present: str = "unknown"
    source: str = ""
    error: str = ""


def fetch_ncbi_assembly(species: str) -> AssemblyRecord:
    """Use Datasets v2 to pull the best public assembly for a species."""
    record = AssemblyRecord(species=species)
    encoded = urllib.parse.quote(species)
    # NB: the filters.assembly_source query param was silently producing
    # 0-report responses; rely on Datasets default + downstream level sort.
    url = f"{DATASETS_BASE}/genome/taxon/{encoded}/dataset_report?page_size=10"
    try:
        data = http_json(url)
    except Exception as exc:  # noqa: BLE001
        record.error = f"datasets_failed:{exc}"
        return record
    reports = data.get("reports") or []
    if not reports:
        return record

    def rank(level: str) -> int:
        order = {"complete": 4, "chromosome": 3, "scaffold": 2, "contig": 1}
        return order.get(level.lower(), 0)

    reports.sort(
        key=lambda r: (
            rank(((r.get("assembly_info") or {}).get("assembly_level") or "")),
            (r.get("assembly_info") or {}).get("submission_date") or "",
        ),
        reverse=True,
    )
    best = reports[0]
    info = best.get("assembly_info") or {}
    record.accession = best.get("accession") or ""
    record.assembly_level = (info.get("assembly_level") or "").lower()
    record.submitter = info.get("submitter") or ""
    record.submission_year = ((info.get("submission_date") or "")[:4]) or ""
    record.source = "NCBI"
    stats = best.get("assembly_stats") or {}
    chrom = stats.get("number_of_organelles") or stats.get("number_of_contigs")
    if isinstance(chrom, int):
        record.chromosome_count = str(chrom)
    annotation_info = best.get("annotation_info") or {}
    if annotation_info.get("name"):
        record.annotation_present = "yes"
    else:
        # NCBI annotation_info can be unreliable. Probe later by URL.
        record.annotation_present = "unknown"
    return record


@dataclass
class SraBreadth:
    species: str
    run_count: int = 0
    tissue_counts: dict[str, int] = field(default_factory=dict)
    top_bioprojects: list[str] = field(default_factory=list)
    latest_year: str = ""
    error: str = ""


def fetch_sra_breadth(species: str, api_key: str | None, *, max_runs: int = 200) -> SraBreadth:
    record = SraBreadth(species=species)
    term = urllib.parse.quote(
        f'"{species}"[Organism] AND (transcriptome[Strategy] OR rna-seq[Strategy] OR rnaseq[All Fields])'
    )
    url = with_api_key(
        f"{NCBI_BASE}/esearch.fcgi?db=sra&term={term}&retmode=json&retmax={max_runs}",
        api_key,
    )
    try:
        data = http_json(url)
    except Exception as exc:  # noqa: BLE001
        record.error = f"esearch_failed:{exc}"
        return record
    ids = (data.get("esearchresult") or {}).get("idlist") or []
    record.run_count = int((data.get("esearchresult") or {}).get("count") or 0)
    if not ids:
        return record
    # Pull summary docs for tissue/title parsing
    sum_url = with_api_key(
        f"{NCBI_BASE}/esummary.fcgi?db=sra&id={','.join(ids[:50])}&retmode=json",
        api_key,
    )
    try:
        summary = http_json(sum_url)
    except Exception as exc:  # noqa: BLE001
        record.error = f"esummary_failed:{exc}"
        return record

    tissue_counts: dict[str, int] = {}
    bioprojects: dict[str, int] = {}
    years: list[str] = []
    docs = (summary.get("result") or {})
    for sid in ids[:50]:
        doc = docs.get(sid) or {}
        if not isinstance(doc, dict):
            continue
        haystack = " ".join([
            str(doc.get("expxml", "")),
            str(doc.get("runs", "")),
            str(doc.get("study", "")),
            str(doc.get("library_name", "")),
        ]).lower()
        for tissue in TISSUE_TOKENS:
            if tissue in haystack:
                key = tissue.replace(" ", "_")
                tissue_counts[key] = tissue_counts.get(key, 0) + 1
        for match in re.finditer(r"PRJ[A-Z]{1,3}\d{4,}", haystack.upper()):
            bp = match.group(0)
            bioprojects[bp] = bioprojects.get(bp, 0) + 1
        # Only accept plausible years preceded by a non-digit (avoid matching
        # accession numbers like SRR2075XXX). Window: 2000-2030.
        for match in re.finditer(r"(?:^|[^0-9])(20[0-3]\d)(?:[^0-9]|$)", haystack):
            yr = match.group(1)
            if 2000 <= int(yr) <= 2030:
                years.append(yr)

    record.tissue_counts = dict(sorted(tissue_counts.items(), key=lambda kv: -kv[1]))
    record.top_bioprojects = [bp for bp, _ in sorted(bioprojects.items(), key=lambda kv: -kv[1])[:3]]
    record.latest_year = max(years) if years else ""
    return record


# ---------------------------------------------------------------------------
# NGDC GWH fallback (probe-only)
# ---------------------------------------------------------------------------


@dataclass
class NgdcRecord:
    species: str
    accession: str = ""
    note: str = ""


def probe_ngdc_for_genus(genus: str) -> dict[str, NgdcRecord]:
    """Walk the NGDC GWH plants HTML index for genus → assembly hits.

    NGDC GWH plants index is reachable from the default remote lane; here we use it
    as a fallback for species with no NCBI assembly. This is a best-effort
    scrape, failures are non-fatal.
    """
    if not genus:
        return {}
    out: dict[str, NgdcRecord] = {}
    encoded = urllib.parse.quote(genus)
    try:
        html = http_text(f"{NGDC_BASE}/Assembly/list?searchInfo={encoded}")
    except Exception as exc:  # noqa: BLE001
        log(f"NGDC GWH probe for {genus} failed: {exc}", level="WARN")
        return out
    # Pull GWH* accessions paired with binomials on the same row
    pattern = re.compile(r"(GWH[A-Z]{2,6}\d{6,}(?:\.\d+)?).{0,400}?<i>([A-Z][a-z]+\s+[a-z]+)</i>", re.DOTALL)
    for match in pattern.finditer(html):
        accession, binomial = match.group(1), match.group(2)
        if binomial not in out:
            out[binomial] = NgdcRecord(species=binomial, accession=accession, note="NGDC GWH plants")
    return out


# ---------------------------------------------------------------------------
# KEGG → enzyme query candidates
# ---------------------------------------------------------------------------


@dataclass
class KeggEnzyme:
    ec: str
    enzyme_name: str = ""
    kegg_id: str = ""


def resolve_kegg_pathway(pathway: str) -> str:
    """Return a KEGG pathway map id (e.g. map00901) or empty string."""
    if not pathway:
        return ""
    direct = pathway.strip()
    if re.fullmatch(r"map\d{5}", direct):
        return direct
    return PATHWAY_KEGG_HINTS.get(direct) or PATHWAY_KEGG_HINTS.get(direct.title(), "")


def fetch_kegg_enzymes(map_id: str) -> list[KeggEnzyme]:
    if not map_id:
        return []
    try:
        body = http_text(f"{KEGG_BASE}/link/enzyme/{map_id}")
    except Exception as exc:  # noqa: BLE001
        log(f"KEGG link failed for {map_id}: {exc}", level="WARN")
        return []
    ecs: list[str] = []
    for line in body.splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[1].startswith("ec:"):
            ec_id = parts[1].split(":", 1)[1]
            if ec_id not in ecs:
                ecs.append(ec_id)
    enzymes: list[KeggEnzyme] = []
    for ec in ecs[:40]:
        try:
            detail = http_text(f"{KEGG_BASE}/get/ec:{ec}")
        except Exception:  # noqa: BLE001
            enzymes.append(KeggEnzyme(ec=ec))
            continue
        name = ""
        for line in detail.splitlines():
            if line.startswith("NAME"):
                name = line[4:].strip().rstrip(";")
                break
        enzymes.append(KeggEnzyme(ec=ec, enzyme_name=name))
    return enzymes


def kegg_to_seed_queries(enzymes: list[KeggEnzyme]) -> list[dict[str, str]]:
    """Translate KEGG enzymes into seed-query placeholder rows.

    These are *placeholders*: the operator (or campaign_preflight via a Codex
    agent) is expected to enrich each row with a canonical UniProt anchor.
    """
    rows: list[dict[str, str]] = []
    for idx, enz in enumerate(enzymes, start=1):
        rows.append(
            {
                "query_id": f"PROPQ{idx:03d}",
                "enzyme_name": enz.enzyme_name or f"EC {enz.ec}",
                "ec": enz.ec,
                "uniprot": "(needs_anchor_resolution)",
                "ref_species": "",
                "role": "candidate",
                "notes": "KEGG-derived placeholder; resolve UniProt anchor before launch",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Composite candidate record
# ---------------------------------------------------------------------------


@dataclass
class CandidateRecord:
    species: str
    role: str  # "target" | "catalog" | "tax-walk"
    catalog_row: dict[str, Any] | None = None
    taxonomy: dict[str, Any] | None = None
    assembly: dict[str, Any] | None = None
    sra: dict[str, Any] | None = None
    ngdc: dict[str, Any] | None = None
    composite_score: float = 0.0
    rank_notes: list[str] = field(default_factory=list)

    def to_tsv_row(self) -> dict[str, str]:
        tx = self.taxonomy or {}
        asm = self.assembly or {}
        sra = self.sra or {}
        ngdc = self.ngdc or {}
        cat = self.catalog_row or {}
        return {
            "species": self.species,
            "role": self.role,
            "genus": tx.get("genus", "") or cat.get("genus", ""),
            "family": tx.get("family", "") or cat.get("family", ""),
            "plant_order": tx.get("plant_order", "") or cat.get("plant_order", ""),
            "ncbi_accession": asm.get("accession", "") or cat.get("best_genome_accession", ""),
            "assembly_level": asm.get("assembly_level", "") or cat.get("genome_level", ""),
            "annotation_present": asm.get("annotation_present", "") or cat.get("annotation_present", ""),
            "ngdc_accession": ngdc.get("accession", ""),
            "rna_seq_run_count": str(sra.get("run_count", "")),
            "rna_seq_tissues": ";".join((sra.get("tissue_counts") or {}).keys()),
            "rna_seq_bioprojects": ";".join(sra.get("top_bioprojects") or []),
            "year_latest": sra.get("latest_year", "") or asm.get("submission_year", "") or cat.get("year_latest", ""),
            "comparative_value": cat.get("comparative_value", ""),
            "novelty_window": cat.get("novelty_window", ""),
            "composite_score": f"{self.composite_score:.2f}",
            "rank_notes": "; ".join(self.rank_notes),
        }


def score_candidate(record: CandidateRecord, *, target_genus: str = "") -> None:
    """Apply a deterministic composite ranking score."""
    score = 0.0
    notes: list[str] = []

    asm = record.assembly or {}
    cat = record.catalog_row or {}
    sra = record.sra or {}
    ngdc = record.ngdc or {}

    level = (asm.get("assembly_level") or cat.get("genome_level") or "").lower()
    if level in {"chromosome", "complete"}:
        score += 30; notes.append("chr-scale assembly")
    elif level == "scaffold":
        score += 15; notes.append("scaffold assembly")
    elif level == "contig":
        score += 5; notes.append("contig only")
    elif ngdc.get("accession"):
        score += 18; notes.append("NGDC-GWH fallback assembly")
    else:
        notes.append("no genome assembly")

    annot = (asm.get("annotation_present") or cat.get("annotation_present") or "").lower()
    if annot == "yes":
        score += 20; notes.append("annotation present")
    elif annot == "partial":
        score += 10; notes.append("partial annotation")

    tissues = sra.get("tissue_counts") or {}
    if len(tissues) >= 3:
        score += 15; notes.append(f"{len(tissues)} tissues in SRA")
    elif tissues:
        score += 7; notes.append(f"{len(tissues)} tissues in SRA")
    elif (cat.get("tissues_covered") or "").strip():
        score += 5; notes.append("tissues recorded in catalog")

    year = sra.get("latest_year") or asm.get("submission_year") or cat.get("year_latest") or ""
    try:
        yr = int(year)
        if yr >= 2024:
            score += 10; notes.append(f"recent ({yr})")
        elif yr >= 2020:
            score += 5; notes.append(f"recent-ish ({yr})")
    except (TypeError, ValueError):
        pass

    cv = (cat.get("comparative_value") or "").upper()
    if cv == "HIGH":
        score += 22; notes.append("catalog HIGH comparative value")
    elif cv in {"MED", "MEDIUM"}:
        score += 7; notes.append("catalog MED comparative value")
    elif cv == "BASELINE":
        score += 12; notes.append("baseline / canonical target")

    if record.role == "target":
        score += 5; notes.append("campaign target")

    # Same-genus-as-target bonus: direct congeners are nearly always the
    # highest-value comparator regardless of other signals.
    if target_genus and record.role != "target":
        candidate_genus = ""
        for source in (record.taxonomy, record.catalog_row):
            if isinstance(source, dict) and source.get("genus"):
                candidate_genus = source["genus"]
                break
        if not candidate_genus and record.species:
            candidate_genus = record.species.split()[0]
        if candidate_genus and candidate_genus.lower() == target_genus.lower():
            score += 12
            notes.append("same genus as target")

    record.composite_score = round(score, 2)
    record.rank_notes = notes


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------


def select_candidates(
    target: str,
    pathway: str,
    catalog_rows: list[CatalogRow],
    related_override: list[str] | None,
    max_candidates: int,
    api_key: str | None,
) -> list[CandidateRecord]:
    """Decide which species to investigate."""
    target_record = CandidateRecord(species=target, role="target")
    for row in catalog_rows:
        if row.species == target:
            target_record.catalog_row = asdict(row)
            break
    selected: list[CandidateRecord] = [target_record]

    if related_override:
        for sp in related_override:
            sp = sp.strip()
            if sp and sp != target and not any(c.species == sp for c in selected):
                selected.append(CandidateRecord(species=sp, role="catalog"))
        return selected[:max_candidates]

    # Bring in catalog rows that match the pathway and aren't the target.
    for row in catalog_match_pathway(catalog_rows, pathway):
        if row.species == target:
            continue
        if any(c.species == row.species for c in selected):
            continue
        rec = CandidateRecord(species=row.species, role="catalog")
        rec.catalog_row = asdict(row)
        selected.append(rec)

    if len(selected) >= max_candidates:
        return selected[:max_candidates]

    # Tax-walk: add genus siblings of the target until we hit the cap.
    target_taxonomy = fetch_taxonomy(target, api_key)
    if target_taxonomy.genus:
        siblings = fetch_genus_siblings(target_taxonomy.genus, api_key, max_results=30)
        for sp in siblings:
            if sp == target:
                continue
            if any(c.species == sp for c in selected):
                continue
            selected.append(CandidateRecord(species=sp, role="tax-walk"))
            if len(selected) >= max_candidates:
                break

    return selected[:max_candidates]


# ---------------------------------------------------------------------------
# Scout driver
# ---------------------------------------------------------------------------


def scout_candidate(
    record: CandidateRecord,
    api_key: str | None,
    *,
    ngdc_cache: dict[str, dict[str, NgdcRecord]],
) -> None:
    """Mutate the candidate in place with fetched data."""
    tax = fetch_taxonomy(record.species, api_key)
    record.taxonomy = asdict(tax)
    assembly = fetch_ncbi_assembly(record.species)
    record.assembly = asdict(assembly)
    sra = fetch_sra_breadth(record.species, api_key)
    record.sra = asdict(sra)
    if not assembly.accession:
        # Probe NGDC GWH only when NCBI is empty (saves bandwidth)
        genus = tax.genus or record.species.split()[0]
        if genus not in ngdc_cache:
            ngdc_cache[genus] = probe_ngdc_for_genus(genus)
        match = ngdc_cache[genus].get(record.species)
        if match:
            record.ngdc = asdict(match)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


SCOUT_COLUMNS = [
    "species", "role", "genus", "family", "plant_order",
    "ncbi_accession", "assembly_level", "annotation_present",
    "ngdc_accession", "rna_seq_run_count", "rna_seq_tissues",
    "rna_seq_bioprojects", "year_latest", "comparative_value",
    "novelty_window", "composite_score", "rank_notes",
]


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SCOUT_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in SCOUT_COLUMNS})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def render_summary(
    target: str,
    pathway: str,
    map_id: str,
    candidates: list[CandidateRecord],
    seed_queries: list[dict[str, str]],
    catalog_match_count: int,
) -> str:
    """Render the 5-section human report."""
    lines: list[str] = []
    lines.append(f"# Campaign preflight, {target} ({pathway})")
    lines.append("")
    lines.append(f"_Generated by `genecluster_species_scout.py` on {time.strftime('%Y-%m-%d %H:%M:%S')}_")
    lines.append("")
    lines.append(f"- **Target species:** {target}")
    lines.append(f"- **Pathway:** {pathway}" + (f" → KEGG `{map_id}`" if map_id else " (no KEGG mapping found)"))
    lines.append(f"- **Candidate species evaluated:** {len(candidates)}")
    lines.append(f"- **Catalog matches:** {catalog_match_count}")
    lines.append("")

    # 1. Data
    lines.append("## 1. Data")
    lines.append("")
    lines.append("| Species | Role | Assembly | Level | Annotation | SRA runs | Tissues | Year | Score |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    sorted_candidates = sorted(candidates, key=lambda c: (-c.composite_score, c.role != "target", c.species))
    for c in sorted_candidates:
        asm = c.assembly or {}
        sra = c.sra or {}
        cat = c.catalog_row or {}
        ngdc = c.ngdc or {}
        accession = asm.get("accession") or ngdc.get("accession") or cat.get("best_genome_accession") or ", "
        level = asm.get("assembly_level") or cat.get("genome_level") or ", "
        annotation = asm.get("annotation_present") or cat.get("annotation_present") or ", "
        runs = sra.get("run_count") or 0
        tissues = ", ".join((sra.get("tissue_counts") or {}).keys()) or cat.get("tissues_covered", ", ")
        year = sra.get("latest_year") or asm.get("submission_year") or cat.get("year_latest") or ", "
        lines.append(
            f"| {c.species} | {c.role} | {accession} | {level} | {annotation} | "
            f"{runs} | {tissues} | {year} | {c.composite_score:.1f} |"
        )
    lines.append("")

    # 2. Inputs
    lines.append("## 2. Inputs (seed protein query set)")
    lines.append("")
    if seed_queries:
        lines.append(f"KEGG pathway `{map_id}` resolved to {len(seed_queries)} candidate enzymes.")
        lines.append("")
        lines.append("| query_id | EC | enzyme | uniprot_anchor | notes |")
        lines.append("|---|---|---|---|---|")
        for q in seed_queries:
            lines.append(
                f"| {q['query_id']} | {q['ec']} | {q['enzyme_name']} | {q['uniprot']} | {q['notes']} |"
            )
        lines.append("")
        lines.append("Plus standard controls:")
        lines.append("")
        lines.append("| query_id | role | uniprot | enzyme |")
        lines.append("|---|---|---|---|")
        for q in CONTROL_QUERIES:
            lines.append(f"| {q['query_id']} | {q['role']} | {q['uniprot']} | {q['enzyme_name']} |")
        lines.append("")
        lines.append("> **Operator action required:** UniProt anchor placeholders (`(needs_anchor_resolution)`)")
        lines.append("> must be resolved to canonical SwissProt accessions before launch.")
        lines.append("> See `genecluster_campaign_preflight.py --resolve-uniprot` (Codex agent fan-out).")
    else:
        lines.append("KEGG mapping not resolved for this pathway. ")
        lines.append("Inputs must be operator-supplied or derived via a literature-audit agent.")
        lines.append("See for the dispatch pattern.")
    lines.append("")

    # 3. Relevance
    lines.append("## 3. Relevance (pathway overlap with target)")
    lines.append("")
    target_record = next((c for c in sorted_candidates if c.role == "target"), None)
    target_family = ""
    target_order = ""
    if target_record and target_record.taxonomy:
        target_family = target_record.taxonomy.get("family", "")
        target_order = target_record.taxonomy.get("plant_order", "")
    lines.append(f"Target placement: family **{target_family or '?'}**, order **{target_order or '?'}**.")
    lines.append("")
    sister_family = [c for c in sorted_candidates if (c.taxonomy or {}).get("family") == target_family and c.role != "target"]
    sister_order = [
        c for c in sorted_candidates
        if (c.taxonomy or {}).get("plant_order") == target_order
        and (c.taxonomy or {}).get("family") != target_family
        and c.role != "target"
    ]
    convergent = [
        c for c in sorted_candidates
        if (c.taxonomy or {}).get("plant_order") and (c.taxonomy or {}).get("plant_order") != target_order
    ]
    lines.append(f"- **Same family ({target_family or '?'}):** {len(sister_family)} candidates "
                 f"({', '.join(c.species for c in sister_family) or ', '})")
    lines.append(f"- **Same order, different family:** {len(sister_order)} candidates "
                 f"({', '.join(c.species for c in sister_order) or ', '})")
    lines.append(f"- **Different order (convergent producers):** {len(convergent)} candidates "
                 f"({', '.join(c.species for c in convergent) or ', '})")
    lines.append("")

    # 4. Novelty
    lines.append("## 4. Novelty (existing publications mapping pathway-to-species)")
    lines.append("")
    with_pub: list[CandidateRecord] = []
    without_pub: list[CandidateRecord] = []
    for c in sorted_candidates:
        cat = c.catalog_row or {}
        if cat.get("key_publication_pmid") or cat.get("key_publication_doi"):
            with_pub.append(c)
        else:
            without_pub.append(c)
    if with_pub:
        lines.append("Catalog-tracked prior publications:")
        for c in with_pub:
            cat = c.catalog_row or {}
            pmid = cat.get("key_publication_pmid") or ", "
            doi = cat.get("key_publication_doi") or ", "
            window = cat.get("novelty_window") or ", "
            lines.append(f"- **{c.species}** . PMID {pmid}, DOI {doi}. Window: {window}")
    if without_pub:
        lines.append("")
        lines.append("Candidates with **no prior publication tracked in catalog** "
                     "(potentially novel; trigger literature-audit agent):")
        for c in without_pub:
            lines.append(f"- {c.species}")
    lines.append("")
    lines.append("> **Operator action required:** confirm novelty via literature audit per ")
    lines.append(">. The audit writes back ")
    lines.append("> into `key_publication_pmid` + `novelty_window` columns of the catalog.")
    lines.append("")

    # 5. Importance
    lines.append("## 5. Importance (composite comparative-value ranking)")
    lines.append("")
    lines.append("Top 3 recommended comparators (by composite score):")
    lines.append("")
    top3 = [c for c in sorted_candidates if c.role != "target"][:3]
    for idx, c in enumerate(top3, start=1):
        lines.append(f"{idx}. **{c.species}** (score {c.composite_score:.1f}) . {'; '.join(c.rank_notes)}")
    lines.append("")
    lines.append("Sequencing priority (lowest infrastructure friction first):")
    for idx, c in enumerate(top3, start=1):
        asm = c.assembly or {}
        ngdc = c.ngdc or {}
        path_hint = "NCBI" if asm.get("accession") else ("NGDC GWH" if ngdc.get("accession") else "RNA-Seq de novo")
        lines.append(f"{idx}. {c.species}, staging via {path_hint}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Next step:** run `genecluster_campaign_preflight.py` to convert this report into a ")
    lines.append("launch-readiness contract that downstream pipeline stages will consume. ")
    lines.append("If novelty/inputs need agent fan-out, the preflight wrapper handles dispatch.")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Early-data-research fan-out scout for BioSymphony campaigns.")
    parser.add_argument("--target", required=True, help="Target species binomial, e.g. 'Coptis chinensis'.")
    parser.add_argument("--pathway", required=True, help="Pathway id (BIA / MIA / KEGG map id / full name).")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory for scout artifacts.")
    parser.add_argument("--catalog", type=Path,
                        default=Path("data/pathway-species-catalog.tsv"),
                        help="Path to the repo-local pathway-species catalog TSV.")
    parser.add_argument("--related-species", default="",
                        help="Comma-separated explicit comparator list; if supplied, skips catalog + tax-walk.")
    parser.add_argument("--max-candidates", type=int, default=12,
                        help="Hard cap on number of candidates evaluated.")
    parser.add_argument("--ncbi-api-key", default=os.environ.get("NCBI_API_KEY", ""),
                        help="Optional NCBI API key (lifts rate limit to 10 req/sec).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve candidates + KEGG only; skip per-candidate NCBI/SRA/NGDC fetches.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    target = args.target.strip()
    pathway = args.pathway.strip()
    if not target or not pathway:
        log("--target and --pathway are required", level="ERROR")
        return 1
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    catalog_rows = read_catalog(args.catalog)
    catalog_pathway_matches = catalog_match_pathway(catalog_rows, pathway)
    related = [s for s in (args.related_species.split(",") if args.related_species else []) if s.strip()]

    log(f"Target: {target} | Pathway: {pathway} | Catalog rows: {len(catalog_rows)} "
        f"(pathway-matched: {len(catalog_pathway_matches)})")

    candidates = select_candidates(
        target,
        pathway,
        catalog_rows,
        related,
        args.max_candidates,
        args.ncbi_api_key or None,
    )
    if not candidates:
        log("no candidates found; aborting", level="ERROR")
        return 3

    log(f"selected {len(candidates)} candidates: {', '.join(c.species for c in candidates)}")

    # Resolve KEGG enzymes (cheap, run regardless of dry-run)
    map_id = resolve_kegg_pathway(pathway)
    seed_queries: list[dict[str, str]] = []
    if map_id:
        enzymes = fetch_kegg_enzymes(map_id)
        seed_queries = kegg_to_seed_queries(enzymes)
        log(f"KEGG {map_id} → {len(seed_queries)} candidate enzymes")

    ngdc_cache: dict[str, dict[str, NgdcRecord]] = {}
    if not args.dry_run:
        for c in candidates:
            log(f"scouting {c.species} ({c.role})")
            try:
                scout_candidate(c, args.ncbi_api_key or None, ngdc_cache=ngdc_cache)
            except Exception as exc:  # noqa: BLE001
                log(f"scout failed for {c.species}: {exc}", level="WARN")
            time.sleep(0.4)  # NCBI etiquette without api key (~3 req/s)
    else:
        log("dry-run: skipping per-candidate fetches")

    target_genus = target.split()[0] if target else ""
    for c in candidates:
        if c.role == "target" and (c.taxonomy or {}).get("genus"):
            target_genus = c.taxonomy["genus"]
            break

    for c in candidates:
        score_candidate(c, target_genus=target_genus)

    tsv_rows = [c.to_tsv_row() for c in candidates]
    write_tsv(out_dir / "species_scout.tsv", tsv_rows)
    write_json(
        out_dir / "species_scout.json",
        {
            "target": target,
            "pathway": pathway,
            "kegg_map_id": map_id,
            "catalog_pathway_matches": len(catalog_pathway_matches),
            "candidates": [asdict(c) for c in candidates],
            "seed_queries": seed_queries,
            "controls": list(CONTROL_QUERIES),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "scout_version": "0.1",
        },
    )
    summary_md = render_summary(target, pathway, map_id, candidates, seed_queries, len(catalog_pathway_matches))
    (out_dir / "relevance-novelty-summary.md").write_text(summary_md, encoding="utf-8")

    if seed_queries:
        seed_path = out_dir / "seed-query-candidates.tsv"
        columns = ["query_id", "enzyme_name", "ec", "uniprot", "ref_species", "role", "notes"]
        with seed_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, delimiter="\t")
            writer.writeheader()
            for q in seed_queries:
                writer.writerow(q)
            for q in CONTROL_QUERIES:
                writer.writerow({k: q.get(k, "") for k in columns})
        log(f"wrote {seed_path}")

    log(f"wrote {out_dir / 'species_scout.tsv'}")
    log(f"wrote {out_dir / 'species_scout.json'}")
    log(f"wrote {out_dir / 'relevance-novelty-summary.md'}")
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
