# M2D Wave 1 - regional context evidence (findings)

> **Figures superseded by M2D.1c** ([m2d1c-edge-cell-aoi-accounting.md](m2d1c-edge-cell-aoi-accounting.md)): WorldPop and GHSL are now clipped to the AOI. AOI modelled population is 3,341,405 (was 3,356,000 as a sum of full grid cells) and built-up 330.4 km2 (was 333.3 km2); unresolved shares are 1.61% of modelled population and 0.57% of built-up (were 1.63% and 0.59%). Cell and area shares are unchanged.

Date: 2026-10-16. Branch: `claude/m2d-wave1-regional-context`. **Evidence only: no family score, no ranking, no exclusion, no buffer.**
`FAMILY_SCORING_ALLOWED` stays `false`. No user requirement and no M1E hazard action changed. Hazard outputs keep their own M1E scope statement.

> **Corrected in M2D.1** - see [m2d1-semantics-review.md](m2d1-semantics-review.md). Where this page disagrees (WorldPop/GHSL independence, the DPIM stone-crushing source, DIW status wording, tambon column names, statistic denominators), M2D.1 governs.

Artifact: `outputs/m2d/regional-context-evidence.parquet` (162,073 cells x 117 columns, 500 m grid, EPSG:32647), with
`regional-context-evidence.columns.json` (per-column lineage) and `.provenance.json`. Supporting tables are in `outputs/m2d/tables/`,
review maps in `outputs/m2d-review/`. Human visual sign-off `M2D_HUMAN_VISUAL_SIGNOFF` is **PENDING** (not reviewed, not inferred).

## 1. Sources and decisions

| Family | Source | Decision | What it can say | What it cannot say |
|---|---|---|---|---|
| Population intensity | WorldPop R2025A v1 2025 (constrained, 100 m, CC BY 4.0, alpha release) - MODELLED_POPULATION_ESTIMATE | ACQUIRED, VERIFIED | modelled people per cell | peacefulness, quiet, livability; it is a modelled allocation, partly correlated with built form because built settlement is a covariate |
| Built-form intensity | GHS-BUILT-S R2023A, epoch 2020, 3 arc-second (JRC) | ACQUIRED, VERIFIED | built-up surface (m2) per cell | building count, population; the 2020 epoch is interpolated from the 2018 observation |
| Building footprints | GISTDA thailand-buildings-footprint (API key) | **DEFERRED** (not rejected) | - | no licence/bulk terms, 45.4M national polygons, the AOI count request times out (HTTP 504), merged sources are not uniformly complete |
| Town services | OSM POIs, eight separate components | ACQUIRED, VERIFIED | component presence and baseline drive time | absence of a POI is not absence of a service; no opening status |
| Nightlife | OSM bar/pub/nightclub/stripclub/karaoke_box tags | ACQUIRED as a separate candidate layer | candidate venue tags | a validated cluster, nuisance, quietness |
| Industry (located) | OSM landuse=industrial, man_made=works, industrial=* | ACQUIRED, VERIFIED | mapped industrial land use | operating status, type of harm |
| Industry (register) | DIW factype2, factype3, factype101-105-106 (CSV, 2026-10-01) | ACQUIRED, VERIFIED | tambon-level counts by type code and licence year | **no coordinates and no operating status exist in the register** |
| Mining (current) | DPIM public open API (879 records nationally, 18 in the AOI) | ACQUIRED, VERIFIED | province-level concession records with dates and flags | any location finer than province; pits, quarries or crushing plants |
| Mining (legacy) | DPIM 2016-06-21 snapshot via data.go.th (79 AOI records) | ACQUIRED as LEGACY_CONTEXT | tambon-level 2016 concessions | current truth; an expired concession is not an active mine |
| Stone crushing / concession licences | DPIM official public exports (found in M2D.1) | ACQUIRED, VERIFIED | tambon-level licence register records with status and dates | coordinates, address, current operating status |
| Land price | Treasury D-Value | **not acquired** (acquisition deferred only) | - | recorded as OFFICIAL_APPRAISAL_CONTEXT; the P0 land-price gap is not downgraded |

DPIM holder names, tax ids and customer ids are personal data that area-level context does not need; they are removed before the raw file is written
(documented in the manifest). DIW and DPIM were read from structured downloads or a public API, never by scraping result pages.

## 2. Findings per question

**Settlement.** Inside the grid: 3.36 M people (Chiang Mai 1.89 M, Chiang Rai 1.13 M, Phayao 0.33 M) and 333 km2 of built-up surface. Population and built form are
semantically different variables from PARTLY DEPENDENT sources (WorldPop R2025A uses GHSL layers as covariates). Their rank correlation (0.87 across cells with either signal) is descriptive only and is not corroboration or validation. They stay separate columns; neither is peacefulness.

**Town services.** 5,540 OSM service POIs reduce to 5,019 after collapsing same-component duplicates within 40 m. Components stay apart
(convenience 1,645; fuel 813; general retail 679; bank/ATM 626; public administration 425; grocery/supermarket 320; pharmacy 261; market 250).
Baseline drive times (frozen M2A routing, no tuning) exist for the 91,837 cells with a road within 1 km. Median drive time to the nearest
convenience store is 9.5 min, grocery/supermarket 18.3 min, pharmacy 28.2 min.

**Cluster definition sensitivity (no production definition chosen).** CORE (at least 4 distinct components linked within 400 m; 2,216 POIs) gives a median
20.5 min to the nearest cluster; BROADER (at least 3 components within 800 m; 3,385 POIs) gives 13.4 min. The two answers differ by about seven minutes at the
median, so the result is sensitive to the definition and the owner must decide what "town services" means before the 35-minute preference can mean anything.
It is not activated.

**Industry.** The DIW registers hold 2,061 unique AOI factories (Chiang Mai 1,135, Chiang Rai 689, Phayao 237), all matched to a tambon by name, but with no
coordinates. A register entry is not nuisance (`FACTORY_PRESENT != NUISANCE_CONFIRMED`). OSM adds 301 located features (215 industrial land use, 46 works, 37 quarry, 3
other). At tambon level OSM sees industrial land use in 101 of the 324 tambons that have DIW factories, so OSM alone under-maps industry.

**Mining and quarrying.** DIW type codes give 21 stone-crushing/grinding (301), 57 earth/sand/gravel excavation (302), 17 screening (303) and 130 sand dredging (304)
records at tambon level. OSM has 37 quarry polygons. They agree weakly: 7 tambons have both a DIW stone-crushing record and an OSM quarry, 22 have only an OSM quarry,
4 only a DIW record. The DPIM open API lists 18 unexpired AOI concessions at province level only (PROVINCE_ADMIN_CONTEXT, never mapped to cells). M2D.1 added the official DPIM exports at tambon level: 46 stone-crushing licence records and 88 concession records including expired ones (register statuses only). The 2016 snapshot is legacy context. **No source acquired here places a licensed plant to a point or gives a current operating status.**

**Nightlife.** 594 OSM candidate tags. Phayao has very few (median distance to the nearest candidate is 36 km), which more likely reflects OSM completeness than quiet.

## 3. Completeness and limits that matter

- 69,675 of 162,073 cells (43%) have no connected drivable road within 1 km in the M2A network (primary to unclassified roads only), so their service drive times are
  UNRESOLVED (NaN with a reason, never 0 and never a Euclidean fallback). Statistics above are over routed cells.
- OSM completeness varies; DIW has no coordinates; DPIM has no coordinates; the legacy snapshot is nine years old.
- Euclidean "within 1/2/5 km" counts are descriptive context radii. They are not exclusion buffers and no buffer is authorised.
- Population and built-form rasters are modelled; the 500 m cell is a coarse unit for both.

## 4. Open questions for the owner

1. What counts as "town services" (which components, and CORE or BROADER clustering or another definition)? The 35-minute preference stays inactive until this is answered.
2. Whether an official request for exact DPIM licence locations would materially help is assessed in M2D.1 (not recommended at the regional stage).
3. Should GISTDA building footprints be pursued (terms and a feasible extraction route) or is GHS-BUILT-S enough for built form?
4. What does "dense urban core" mean numerically? Population, built form and road density are available as separate signals; no interpretation is authorised.
5. Night-time lights and POI intensity (the remaining peacefulness signals) are not acquired.
6. Land price remains the largest P0 gap; acquisition is deferred, not downgraded.

## 5. Operational note

The GISTDA feature API echoes the caller's `api_key` in the `links` array of every response. An early probe printed a response body, so the project key appeared in the
working transcript (it was not written to any repository file or committed). Rotate the key. Any stored GISTDA response must strip `links` first and document that
transformation; `scripts/m2d/assess_gistda_buildings.py` stores counts only and asserts that the key never reaches its output.
