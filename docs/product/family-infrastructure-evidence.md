# Family & infrastructure evidence v0.1 (M2A)

Status: **PROVISIONAL, evidence only.** Config: [`config/family-infrastructure.yaml`](../../config/family-infrastructure.yaml);
code: `hearthmap.family`; artifact: `outputs/m2a/family-infrastructure-evidence.parquet` (one row per 500 m cell).
There is **no family score, no infrastructure score, no school-quality field and no ranking** of any
province or location. M2A answers *what a location can reach and what evidence exists*, not whether
that is enough for the family (that is M2B, after the owner fills `m2b-requirements-sheet.md`).

## Five concepts that are never converted into each other

| Concept | In M2A |
|---|---|
| PRESENCE | a facility exists in a (stale) government register |
| ACCESSIBILITY | `BASELINE_DRIVE_TIME` over the OSM road network to the nearest facility of a category |
| CAPACITY / SERVICE LEVEL | **not available** (no beds, classrooms, enrolment, or verified hospital level) |
| QUALITY | **not available** and forbidden fields (`school_quality_score`, `best_school`, `good_school`) are tested absent |
| RELIABILITY | **not available** (no outage, closure or rainy-season data) |

## What each column family means

* `drive_time_to_nearest_<cat>_min`, `network_distance_to_nearest_<cat>_km`, `nearest_<cat>_id`,
  `route_available_<cat>`, `<cat>_unresolved_reason` for early-childhood centres, kindergartens, primary
  schools, secondary schools, vocational institutions, universities, primary health units, hospitals and
  higher-level hospitals. A cell that cannot be routed stays **NaN with a reason**
  (`NO_ROAD_WITHIN_SNAP_DISTANCE`, `UNREACHABLE_WITHIN_SEARCH_LIMIT_OR_NETWORK`, `NO_FACILITIES_IN_CATEGORY`,
  `CATEGORY_DEFERRED_NO_VERIFIED_CLASSIFICATION`). Straight-line distance exists only as
  `euclidean_distance_to_nearest_<cat>_km_diagnostic` and never fills a failed route.
* `<cat>_count_within_{15,30,60}min`: facilities reachable within the band (−1 = unresolved).
  `education_pathways_within_*min`: how many of the six education pathways are reachable.
* `*_slow_min` / `*_fast_min`: speed sensitivity (×0.75 / ×1.25) for primary school, secondary school and hospital.
* `road_access_context`, `road_snap_distance_m`, `nearest_major_road_*`, `drr_rural_highway_within_1km`.
* Electricity: `electricity_service_potential` is `NOT_ASSESSED` everywhere (PEA Power Map has no verified
  machine-readable public endpoint; when it does, the best state is `REGIONAL_SERVICE_POTENTIAL`, never
  parcel availability). `electricity_parcel_verification_required` is always true.
* Water: `water_service_context` is `NON_PWA_OR_UNKNOWN_SERVICE` everywhere (no PWA polygons are
  published). This is **not** "no water". `water_service_verification_required` is always true.
* Telecom: `telecom_evidence = DEFERRED_NO_SPATIAL_COVERAGE_DATA` (NBTC publishes aggregate shares only).

## Taxonomy and its honesty

Education levels are **derived** from institution names and DOPA sub-codes with a stated basis and
confidence (`level_basis`, `level_confidence`); the authoritative MOE register was unreachable. A school
with an unstated level defaults to PRIMARY at LOW confidence. Source-native sub-codes are always kept.
Health facility classes use ministry/name only: PRIMARY_HEALTH_UNIT, HOSPITAL_UNSPECIFIED_LEVEL,
SPECIALISED_HOSPITAL, UNIVERSITY_HOSPITAL. **No capability (emergency, trauma, ICU) is ever assigned**, and
"higher-level hospital" is empty until an authoritative list is supplied in
`config/healthcare-reference-levels.yaml`.

## Data freshness

Education: DOPA gis-02, budget year 2564 (≈2021) — **STALE**. Health: CITIZENinfo file dated 2020-03-14 —
**STALE**. OSM: 2026-10-15 — current. Every facility row carries `source_date`, `verification_date`,
`expected_update_frequency`, `freshness_status` (stale after 3 years, configurable).

## Handoff to hazards

M2A never edits an M1E action. Hazard avoidance, verification and mitigation actions stay visible and
independent; excellent school or hospital access never compensates for a hazard signal (tested).
