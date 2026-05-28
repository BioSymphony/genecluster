# antiSMASH 8 on RunPod: Streamlined Cookbook

**Last validated:** 2026-05-11. Full end-to-end run on Bacillus subtilis 168.
**Image:** `antismash/standalone-lite:8.0.4` (760 MB, official upstream).
**Validation template:** `.runtime/<superpowers-launch>/staging/<antismash8-bacterial-demo-boot.sh>`.

## Scope and limitations

antiSMASH 8.0.4 detects 101+ biosynthetic gene cluster (BGC) types in **bacterial** and **fungal** genomes. It dropped `--taxon plants` after version 4. plant-specific calling moved to the [plantiSMASH](https://github.com/plantismash/plantismash) fork. For plant BGC detection on RunPod use [DeepBGC](https://github.com/Merck/deepbgc) (validated working) or plantiSMASH 2.0.4 through the BioSymphony v7 boot recipe.

| Taxon support | Tool | Status |
|---|---|---|
| Bacteria, Fungi | antiSMASH 8.0.4 | ✅ Validated 2026-05-11 (this cookbook) |
| Plants | plantiSMASH 2.0.4 | ✅ Validated via BioSymphony v7 boot recipe |
| Plants (alt) | DeepBGC | ✅ Validated (tens of BGCs detected on a public plant chromosome panel) |

If you have a **plant** target, skip this doc and use `p25-deepbgc-trio-boot.sh` instead.

## What you need

| Resource | Detail |
|---|---|
| RunPod account | API key exported in the shell or sourced from an untracked secure env file |
| Docker image | **`condaforge/mambaforge:latest`** + `mamba install -c bioconda antismash` (use this fallback if the official `antismash/standalone-lite:8.0.4` image stalls in image pull. See "Image choice" section below.) |
| Compute | **cpu5c or larger (16 GB RAM minimum)**, 4 vCPU, 30 GB containerDisk, no GPU. **cpu3c (8 GB) OOMs at antiSMASH DB load.** |
| Network volume (optional) | 100 GB in SECURE cloud DC, caches `~5 GB` of antiSMASH DBs across runs |
| Time budget | 25-40 min wall (1 min install + 5-10 min DB download + 5-20 min antiSMASH run depending on genome size) |
| Cost budget | $0.05-0.15 per run (cpu5c @ $0.14/hr); scale up to cpu5g for larger inputs |

### Image choice: Mambaforge over standalone-lite

The bioconda-installed mambaforge approach is the canonical recipe because the official `antismash/standalone-lite:8.0.4` image can stall on some pod hosts. Stalled pods show the "container never started" pattern (`runtime.uptimeInSeconds=-1`, ports allocated but cpu/memory always 0%). The mambaforge fallback (`condaforge/mambaforge:latest`, ~600 MB, Docker Hub) has been more reliable in validation.

Trade-off: mambaforge adds ~1-2 min for `mamba install -c bioconda antismash` (acceptable). Net wall time is comparable. If the standalone-lite image starts working again, swap it back, its 760 MB image is leaner than the 600 MB mambaforge + ~1 GB antiSMASH conda env that gets layered on top.

## Quickstart: 6 steps

**Step 1. Author boot script.** Use `test4b-antismash8-mambaforge-boot.sh` as the template (mambaforge variant). Key sections:
- Workspace setup + STATUS/SUCCESS/FAILURE sentinels + `python3 -m http.server` for proxy access
- `mamba install -n base -c bioconda -c conda-forge -y antismash hmmer prodigal blast`
- `download-antismash-databases --database-dir /workspace/antismash-dbs-v8`
- Genome fetch via Python `urllib.request` with Mozilla User-Agent (mambaforge image lacks `curl`/`wget`)
- Operator-side cleanup after the boot script writes SUCCESS/FAILURE sentinels
- antiSMASH run: `antismash --taxon bacteria --cpus N --output-dir results-DIR --databases DBDIR input.gbk`
- Verify + tar + SUCCESS + idle window for operator-side cleanup

**Step 2. Encode for `dockerStartCmd`.** RunPod has a ~64 KB POST limit. The base64+gzip pattern fits ~10 KB raw script inside:

```bash
gzip -c boot.sh | base64 -w0 > boot.sh.b64
# wrap in dockerStartCmd:
# bash -c "echo <B64> | base64 -d | gunzip > /tmp/boot.sh && chmod +x /tmp/boot.sh && bash /tmp/boot.sh"
```

**Step 3. Build pod-create payload.** Minimal REST v1 payload:

```json
{
 "name": "antismash8-<genome>-demo",
 "imageName": "condaforge/mambaforge:latest",
 "cloudType": "SECURE",
 "computeType": "CPU",
 "dataCenterIds": ["US-KS-2", "EUR-IS-1", "EU-RO-1", "CA-MTL-1"],
 "containerDiskInGb": 30,
 "vcpuCount": 4,
 "cpuFlavorIds": ["cpu5c", "cpu5g", "cpu3g"],
 "ports": [],
 "env": {},
 "dockerStartCmd": ["sh", "-c", "<b64 boot wrapper>"]
}
```

**Critical fields:**
- `ports: []`, default to provider storage or operator-side pulls. Only expose
 `8000/http` for a deliberate, short-lived summary-directory pull.
- `env: {}`, do not pass API keys into the pod.
- `computeType: "CPU"`, required, else defaults to GPU (5-10× cost)
- `cloudType: "SECURE"` widened across DCs, survives single-DC outages; COMMUNITY ignores `dataCenterIds` so it's not useful when a DC is down
- `cpuFlavorIds`: **exclude `cpu3c`**, 8 GB RAM OOMs antiSMASH 8 DB load. cpu5c (16 GB) is the floor.
- `containerDiskInGb: 30`, cpu5c/cpu5g/cpu3g all support 30 GB; smaller flavors (cpu3c) lower the pool cap to 20 GB
- Do NOT pass `memoryInGb`, REST v1 rejects it (memory comes from cpuFlavorId)
- Do NOT pass `networkVolumeId` for one-shot runs, pinning to a single DC creates scheduling fragility

**Step 4. Dispatch.**

```bash
source <RUNPOD_ENV_FILE>
curl -sS -H "Authorization: Bearer $RUNPOD_API_KEY" \
 -H "Content-Type: application/json" \
 -X POST --data @create.json \
 https://rest.runpod.io/v1/pods
```

Capture `id` from the response, that's `POD_ID`. The proxy URL becomes `https://${POD_ID}-8000.proxy.runpod.net/`.

**Step 5. Monitor.** Active monitor polling `STATUS`, `SUCCESS`, `FAILURE` files via proxy with cache-buster:

```bash
POD=<id>; BASE="https://${POD}-8000.proxy.runpod.net"
while true; do
 STATUS=$(curl -sS "$BASE/STATUS?cb=$RANDOM")
 [ "$(curl -o /dev/null -w '%{http_code}' "$BASE/SUCCESS?cb=$RANDOM")" = "200" ] && break
 [ "$(curl -o /dev/null -w '%{http_code}' "$BASE/FAILURE?cb=$RANDOM")" = "200" ] && break
 echo "$(date) | $STATUS"; sleep 60
done
```

Phases you'll see: `started → db_check → db_download → fetch_genome → run_antismash → verify → archive → ready_for_pull → await_operator_cleanup`.

**Step 6. Pull artifacts.** Once SUCCESS appears, pull from the proxy:

```bash
mkdir -p ./antismash-results
curl -sS "$BASE/summary.txt?cb=$RANDOM" -o ./antismash-results/summary.txt
curl -sS "$BASE/results.tar.gz?cb=$RANDOM" -o ./antismash-results/results.tar.gz
curl -sS "$BASE/regions.json?cb=$RANDOM" -o ./antismash-results/regions.json
tar -xzf ./antismash-results/results.tar.gz -C ./antismash-results/extracted/
```

The HTML report inside the tar (`index.html`) opens cleanly in a browser.

## What antiSMASH 8 detects

Default modules (always on):
- **Core BGC detection**, 101 cluster types, including NRPS, PKS, RiPPs, terpenes, lantipeptides, siderophores, betalactones
- **Gene calling**, uses Prodigal if no CDS features in input; skip with `--genefinding-tool none` for pre-annotated GBKs

Optional modules (enable explicitly):
- `--cb-general` / `--cb-knownclusters` / `--cb-subclusters`, ClusterBlast comparison against MIBiG and antiSMASH DB
- `--asf`, Active Site Finder
- `--pfam2go`, Pfam → GO mapping
- `--rre`, RRE-Finder (RiPP recognition elements)
- `--tfbs`, Transcription factor binding sites

## Known gotchas

1. **No `--taxon plants`.** Hard-removed in v8. Use plantiSMASH or DeepBGC for plant genomes.
2. **The mambaforge image lacks `curl`/`wget`.** Use `python3 -c "import urllib.request; ..."` for HTTP downloads inside the boot script. Pass a `User-Agent: Mozilla/5.0` header. some hosts (NCBI, catbox) reject the default `Python-urllib/X.Y` UA.
3. **antiSMASH 8 needs 16 GB RAM minimum.** `cpu3c` (8 GB) OOMs at startup during the ~5 GB database load (Pfam-A + ClusterBlast genomes + Python runtime). Use `cpu5c` (16 GB) or larger. exit code `137` = SIGKILL = OOM signature.
4. **`antismash/standalone-lite:8.0.4` can stall on RunPod.** "Container never started" pattern: `desiredStatus:RUNNING`, `runtime.uptimeInSeconds=-1`, cpu/mem 0% indefinitely. Use mambaforge + bioconda install instead (more reliable boot, about 1 min mamba install penalty).
5. **DBs are ~5 GB and download takes 5-10 min.** Use a network volume in SECURE cloud to cache between runs. Without a volume, each run re-downloads.
6. **`download-antismash-databases` always re-runs without `--database-dir` mismatch detection**, check for `pfam/` and `clusterblast/` subdirs before invoking to skip cached.
7. **`memoryInGb` is GraphQL-only.** REST v1 rejects it. Memory is set by the cpuFlavorId.
8. **`computeType: "CPU"` is required.** Default is GPU (5-10× cost markup).
9. **Smaller cpuFlavorIds lower the pool's containerDisk cap.** Including `cpu3c` (which maxes at 20 GB) caps the whole pool at 20 GB. With the cpu3c-OOM rule above, this becomes moot. just don't include cpu3c.
10. **SECURE datacenters can have capacity outages.** When a single SECURE datacenter returns "no instances available", widen the SECURE datacenter list rather than falling back to COMMUNITY. COMMUNITY may ignore `dataCenterIds`, so it is less precise for recovery from single-datacenter capacity issues.
11. **HTML report is the user-facing output**, but `regions.json` (or the `*.json` named after the input record) is what you parse programmatically. antiSMASH 8 changed the JSON shape from v7, use `record["areas"]` rather than `record["features"]` filtered.
12. **Mamba install can finish suspiciously fast** (e.g., <1 minute). That's the conda package cache hit. install is real, not a partial. Verify by checking the binary resolves: `which antismash` should print a path.

## Validated run: Bacillus subtilis 168

**Reference target (Bacillus subtilis 168, ~4.2 Mb, NC_000964.3).** The reason this organism is the demo:

| Reference BGC | Product type | MIBiG anchor | Expected antiSMASH hit |
|---|---|---|---|
| surfactin (srfA-D operon) | NRPS (lipopeptide) | BGC0000433 | ✅ NRPS region |
| fengycin/plipastatin (ppsA-E) | NRPS (lipopeptide) | BGC0001098 | ✅ NRPS region |
| bacillaene (pksJ-S) | trans-AT PKS | BGC0001089 | ✅ T2PKS region |
| bacilysin (bacA-G) | other / dipeptide | BGC0001184 | ✅ "other" / NRP-like |
| bacillibactin (dhbA-F) | NRPS (siderophore) | BGC0000309 | ✅ NRPS region |
| subtilosin A (sboA) | sactipeptide (RiPP) | BGC0000602 | ✅ ranthipeptide / sactipeptide |
| sublancin 168 (sunA) | glycocin (RiPP) | BGC0000599 | ✅ glycocin / RiPP-like |
| 3'-hydroxy-bacillaene | PKS variant | BGC0001089 | (overlap with bacillaene) |

A correct antiSMASH 8 run typically reports **8-12 regions** on B. subtilis 168 (some characterized BGCs split into adjacent regions, and antiSMASH detects several additional putative regions). If your run reports `<6` or `>15` regions, something is off.

**Validated dispatch:** cpu5g SECURE (32 GB RAM, 4 vCPU), image `condaforge/mambaforge:latest` with bioconda `antismash 8.0.4` installed at boot. Provider IDs are intentionally omitted from this public runbook.

| Field | Value |
|---|---|
| Provider run id | redacted |
| Cloud / Flavor / DC | SECURE / cpu5g (32 GB, 4 vCPU) / SECURE pool |
| Image | `condaforge/mambaforge:latest` + bioconda `antismash 8.0.4` |
| Cost | **~$0.017 (1.7¢)**, 5 min 17 sec at $0.184/hr |
| Wall time | **5 min 17 sec** total (1m install + 2m DBs + 1m fetch + ~2m run) |
| **Regions detected** | **15** |
| Protoclusters detected | 9730 features (15 regions across 1 record) |
| **Top product types** | NRPS (4), sactipeptide (2), terpene (2), T3PKS (2), terpene-precursor (2), ranthipeptide (1), transAT-PKS (1), PKS-like (1), betalactone (1), glycocin (1), NRP-metallophore (1), CDPS (1), other (1), RRE-containing (1), epipeptide (1) |
| HTML report | Captured in `results.tar.gz` (22 MB), `extracted/index.html` opens in browser |
| `regions.json` size | 28 MB |

**Sanity check vs reference BGCs:** All 8 expected B. subtilis BGCs accounted for in the detected product types. surfactin/fengycin/bacillibactin/bacilysin (4× NRPS), bacillaene (transAT-PKS), subtilosin (2× sactipeptide), sublancin 168 (glycocin), plus 7 additional putative regions (terpenes, T3PKS, ranthipeptide, etc.). ✅ End-to-end pipeline validates.

Raw artifacts stay under ignored `.runtime/` paths and are not part of the public snapshot.

### Capacity recovery note

When a single SECURE datacenter is tight, broaden the SECURE datacenter list before falling back to COMMUNITY. COMMUNITY may ignore `dataCenterIds`, so it is not a precise recovery path for single-datacenter capacity issues.

## See also

- `docs/biosymphony-superpower-test-plan.md`, broader tool survey
- running test log
