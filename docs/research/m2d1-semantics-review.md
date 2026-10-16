# M2D.1 - evidence semantics and review corrections

Date: 2026-10-16. Branch: `claude/m2d1-evidence-semantics-review`. Corrects [M2D Wave 1](m2d-wave1-findings.md).
Still evidence only: no scoring (`FAMILY_SCORING_ALLOWED` false), no user requirement changed, no M1E hazard action changed (the hazard and requirement
configs are hash-pinned in `tests/test_m2d1.py`), Wave 2 not started. `M2D_HUMAN_VISUAL_SIGNOFF` stays **PENDING**; only the project user can pass it.

## 1. GISTDA credential

The earlier exposure was reported; the project user rotates the key externally. M2D.1 does not read, print, store or use any credential and makes no GISTDA
request (a test fails if any M2D script other than the counts-only assessment references the GISTDA API). GISTDA building footprints stay **DEFERRED, not rejected**
(unclear bulk terms, GHSL is adequate built-form context for the regional stage, credential handling resets after rotation).

## 2. WorldPop is a modelled estimate, and it depends partly on GHSL

Recorded as `MODELLED_POPULATION_ESTIMATE` (estimate year 2025, release R2025A, v1, about 100 m, people per pixel, EPSG:4326, status ALPHA, DOI 10.5258/SOTON/WP00839),
never census-observed population. The R2025A method uses GHSL built-settlement layers and building footprints as covariates, so WorldPop and GHS-BUILT-S are
**not independent**. The 0.87 rank correlation is reported only as a descriptive relationship (`descriptive_rank_correlation_..._PARTLY_DEPENDENT_..._not_validation`
in `build-summary.json`). The artifact carries `population_product_class`, `population_worldpop_depends_partly_on_ghsl = true`, an
`evidence_settlement_state` that says PARTLY_DEPENDENT, per-column lineage notes, a `regional-context-evidence.sources.json` semantics file and a dependency
note on the review map. Population intensity and built-form intensity remain different variables.

## 3. DIW: inclusion semantics are not row status

The acquired DIW resources (class 2, class 3, waste types 101/105/106) have **no row-level status field and no coordinates**. Their catalogue `data_source` is the
factory database *outside industrial estates* (industrial-estate factories are not in these resources, so under-coverage there is expected). Nothing documents whether
closed or cancelled factories are excluded, so every row is `record_status = UNKNOWN` (`row_level_status_field = ABSENT`, `source_context = OUTSIDE_INDUSTRIAL_ESTATES_CLOSURE_EXCLUSION_NOT_DOCUMENTED`);
no row is ever ACTIVE. DIW enters the grid only as tambon context: columns are named `diw_*_count_tambon_context`, lineage says `spatial_resolution = TAMBON_ADMINISTRATIVE`, and a cell merely
inherits its tambon value. No DIW distance, buffer or local-presence column exists (tested). The review map draws DIW at tambon geometry, not as a 500 m surface.

## 4. OSM industrial geometry

The M2D extract held bounding boxes only, so M2D.1 re-acquired the same features with real geometry (`osm-industry-geom-aoi`; 298 of 301 became geometries). Points and polygons are
never summed: `osm_industrial_landuse_polygon_area_fraction_500m`, `osm_works_point_count_*` and `osm_works_polygon_count_*` (separate), `osm_quarry_polygon_area_fraction_500m`,
`osm_quarry_geometry_presence_*` and Euclidean nearest-geometry diagnostics. OSM remains validation/context evidence, not operating status.

## 5. DPIM: the official stone-crushing export exists - what it holds

Found through the DPIM data-centre pages, whose own Export-to-XML button issues a plain public GET to `dses.dpim.go.th/xmlreportservices/generate.do` (six requests, no authentication, no
bypass; the 403 quarry query page was not used). Both exports (stone crushing/grinding licences; mining concessions) carry: licence number, province/district/tambon codes and names,
effective and expiry dates (Buddhist era), register status (stone: opened 22, deregistered 16, halted 3, awaiting notice 1, missing 4; concession: expired 62, unexpired 17, renewed 7, missing 2),
mineral or product and capacity text, and an operator name (removed before storage as personal data). They carry **no coordinates and no street address**.

| Question | Answer |
|---|---|
| Records | AOI: 46 stone-crushing licence records (22 Chiang Mai, 15 Chiang Rai, 9 Phayao); 88 concession records incl. expired (43, 22, 23) |
| Admin resolution | Tambon, matched to the boundary set at 100% (stone) and 98.9% (concessions); AOI tambons average about 100 km2 (median 60 km2) |
| Coordinates | None |
| Status vocabulary | `เปิดการ` opened, `หยุดการ` halted, `ต่ออายุ` renewed, `สิ้นอายุ` expired, `จำหน่ายทะเบียน` deregistered, `รอแจ้งประกอบกิจการ` awaiting operation notice (mapped to `*_REGISTER_STATUS`) |
| Date semantics | Buddhist-era dd/mm/yyyy; status and expiry date can disagree (3 'opened' records have expiry dates already past, the oldest in 2013) and are kept as separate fields |
| Licence/terms | None stated on the export pages; treated as public-information use for non-commercial local research, re-check before redistribution |

**LICENCE_STATUS is not CURRENT_OPERATING_STATUS**: columns are `dpim_*_register_status_*_tambon_context`, `dpim_status_semantics = REGISTER_STATUS_NOT_CURRENT_OPERATING_STATUS`, and `is_current_operating_status` is false in the table.
The DPIM open API (18 AOI concessions, province only) is `PROVINCE_ADMIN_CONTEXT`, appears only in `dpim-province-admin-context.csv`, and is never mapped to cells. The 2016 snapshot stays LEGACY_CONTEXT.

**Formal request decision.** Not recommended now. The exports give identity (licence number), register status, dates and tambon, which is enough for regional screening and
candidate-zone context in an area of about 40,000 km2 and about 400 tambons; only 11 tambons hold an 'opened' stone-crushing licence and 12 hold an unexpired concession. Exact locations would matter
only for tambons that overlap a shortlisted zone, and even then field verification is the final check; a targeted request or site visit at the candidate-zone stage for those few tambons would be
proportionate. It would not materially improve regional-stage decisions.

## 6. Town services

Component-level drive times are the primary evidence. CORE and BROADER clusters are `CANDIDATE_DEFINITION` (column `service_cluster_*_definition_status`); neither is chosen and the 35-minute preference is not activated.
Sensitivity stays visible (`service-cluster-sensitivity.csv`, `town-services-cluster-sensitivity.png`): among the 91,837 cells routable for both, the median is 20.5 min (CORE) vs 13.4 min (BROADER), a 7.1 min
difference of medians; the median of the paired per-cell difference is 1.6 min and its 90th percentile 26.2 min, so the definition matters most where services are sparse.

## 7. Routing denominators

69,675 of 162,073 cells (43.0% of cells, 42.7% of area) have no connected road within 1 km and are unresolved (NaN with a reason, never zero, never a Euclidean fallback). Every service-time statistic
now states its denominator (`statistic_population = MEDIAN_AMONG_ROUTABLE_CELLS_ONLY`, `cells_total`, `cells_resolved`, `cells_unresolved`, resolved and unresolved cell and area shares) in
`descriptive-statistics.csv`; `routing-denominators.csv` gives the cell and area coverage per province (routable area share: Chiang Mai 54.0%, Phayao 53.3%, Chiang Rai 66.0%). A routable-only median is never called AOI-wide.

## 8. Urban-core calibration (no definition chosen)

`urban-core-calibration-distributions.csv` gives quantile distributions (all cells and non-zero cells; AOI and provinces) for population density, built fraction, road density, OSM service-POI intensity and
components reached in 15 min, with a note that no quantile is a policy threshold. `urban-core-calibration-panels.png` shows six reference towns (orientation only) with the four variables as separate panels
and the same colour limit per column. Nothing is combined, no `DENSE_URBAN_CORE` exists, and OSM POI intensity (`DESCRIPTIVE_CONTEXT`, completeness spatially uneven) is not labelled peacefulness or urban-core truth.
No night-time-lights source was acquired.

## 9. M2C evaluability (nothing becomes READY)

| Entry | Before | After | Why |
|---|---|---|---|
| SETTLE-PEACE | PARTIAL | PROXY_ONLY (regional and candidate) | descriptive signals exist, peacefulness is not observed, WorldPop and GHSL are partly dependent |
| TOWN-SERVICES | PARTIAL | READY_WITH_LIMITATIONS for COMPONENT ACCESSIBILITY ONLY | the requirement-level bundle is not yet defined; clusters are candidates |
| NUIS-INDUSTRIAL | PARTIAL (candidate) | PROXY_ONLY (candidate) | tambon register context plus OSM geometry do not prove nuisance |
| NUIS-MINING | PARTIAL (candidate) | PROXY_ONLY (candidate); point resolution stays blocked by location | tambon licence register plus OSM quarry geometry; no coordinates |
| NUIS-NIGHTLIFE | PROXY_ONLY | PROXY_ONLY | OSM tag candidates only |

Priorities are unchanged (land price stays P0); no evaluation rule is active; `FAMILY_SCORING_ALLOWED` is false.

## 10. Review pack (`outputs/m2d-review/`)

population-intensity, built-form-intensity, population-vs-built-form-dependency, town-services-components, town-services-cluster-sensitivity, routing-unresolved-coverage,
diw-tambon-factory-context, osm-industrial-context, stone-crushing-licence-context, dpim-mining-quarry-context, evidence-completeness, urban-core-calibration-panels.
