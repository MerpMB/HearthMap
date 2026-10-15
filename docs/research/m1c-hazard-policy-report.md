# HearthMap M1C — Hydrogeomorphic Hazard Screening policy report

> Committed copy of `outputs/m1c-review/README.md`; images live in the untracked review folder.

**Policy 0.1.0 — status PROVISIONAL; no default profile.** Human visual sign-off: M1A.1 PENDING, M1B PENDING. Scope: **hydrogeomorphic only** (observed flood 2005-2016, DMR landslide susceptibility, DSM terrain) - not a complete natural-hazard assessment; seismic/active-fault, earthquake, wildfire and other hazards are not covered (`docs/product/natural-hazard-scope.md`). Outcomes are regional screening only: never safe, buildable, rejected or legally excluded; `eligible` is untouched.

Policy semantics: `docs/product/hazard-screening-policy.md`; config: `config/hazard-policy.yaml`.

## Profiles (for sensitivity analysis - none is selected)

| profile | flood strong / deprioritize (>=3 yrs fraction) | Very High strong / deprioritize | High+VH strong / deprioritize | terrain VERIFY / corroborate (DSM p90 deg) | terrain escalates landslide | scar within m / escalates | flood+landslide escalation |
|---|---|---|---|---|---|---|---|
| CONSERVATIVE | 0.05 / 0.25 | 0.1 / 0.25 | 0.25 / 0.5 | 25 / 30 | True | 500 / True | True |
| BALANCED | 0.1 / 0.5 | 0.25 / 0.5 | 0.5 / 0.75 | 30 / 35 | False | 0 / False | True |
| PERMISSIVE | 0.25 / 0.75 | 0.5 / 0.75 | 0.75 / 0.95 | 35 / 40 | False | 0 / False | False |

![policy-profiles-comparison.png](../../outputs/m1c-review/policy-profiles-comparison.png)

## Outcomes by profile and province

Province rows use majority-province attribution; 1,442 cells carry the M1A.1 boundary-attribution caution (outcomes are unaffected).

**AOI** (cells / area / share of area)

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 12,589 / 3,117 km2 (7.8%) | 92,063 / 22,789 km2 (57.1%) | 7,815 / 1,941 km2 (4.9%) | 48,982 / 11,952 km2 (29.9%) | 624 / 132 km2 (0.3%) |
| BALANCED | 20,064 / 4,974 km2 (12.5%) | 93,753 / 23,209 km2 (58.1%) | 11,969 / 2,970 km2 (7.4%) | 35,328 / 8,568 km2 (21.5%) | 959 / 209 km2 (0.5%) |
| PERMISSIVE | 28,492 / 7,067 km2 (17.7%) | 94,532 / 23,411 km2 (58.6%) | 11,140 / 2,764 km2 (6.9%) | 26,022 / 6,262 km2 (15.7%) | 1,887 / 426 km2 (1.1%) |

**Chiang Mai** (cells / area / share of area)

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 8,034 / 1,995 km2 (9.0%) | 46,647 / 11,534 km2 (52.0%) | 3,086 / 763 km2 (3.4%) | 32,047 / 7,803 km2 (35.2%) | 287 / 65 km2 (0.3%) |
| BALANCED | 12,262 / 3,047 km2 (13.8%) | 47,580 / 11,761 km2 (53.1%) | 5,553 / 1,376 km2 (6.2%) | 24,244 / 5,869 km2 (26.5%) | 462 / 107 km2 (0.5%) |
| PERMISSIVE | 16,538 / 4,110 km2 (18.6%) | 48,100 / 11,896 km2 (53.7%) | 6,080 / 1,505 km2 (6.8%) | 18,435 / 4,431 km2 (20.0%) | 948 / 218 km2 (1.0%) |

**Phayao** (cells / area / share of area)

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 2,929 / 726 km2 (11.7%) | 16,264 / 4,021 km2 (64.9%) | 1,490 / 370 km2 (6.0%) | 4,448 / 1,064 km2 (17.2%) | 57 / 14 km2 (0.2%) |
| BALANCED | 4,473 / 1,109 km2 (17.9%) | 15,769 / 3,895 km2 (62.9%) | 2,025 / 501 km2 (8.1%) | 2,823 / 665 km2 (10.7%) | 98 / 24 km2 (0.4%) |
| PERMISSIVE | 6,315 / 1,566 km2 (25.3%) | 15,181 / 3,747 km2 (60.5%) | 1,511 / 375 km2 (6.1%) | 1,916 / 441 km2 (7.1%) | 265 / 65 km2 (1.1%) |

**Chiang Rai** (cells / area / share of area)

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 1,626 / 396 km2 (3.4%) | 29,152 / 7,234 km2 (62.5%) | 3,239 / 808 km2 (7.0%) | 12,487 / 3,085 km2 (26.7%) | 280 / 53 km2 (0.5%) |
| BALANCED | 3,329 / 818 km2 (7.1%) | 30,404 / 7,553 km2 (65.2%) | 4,391 / 1,093 km2 (9.4%) | 8,261 / 2,035 km2 (17.6%) | 399 / 78 km2 (0.7%) |
| PERMISSIVE | 5,639 / 1,391 km2 (12.0%) | 31,251 / 7,768 km2 (67.1%) | 3,549 / 883 km2 (7.6%) | 5,671 / 1,390 km2 (12.0%) | 674 / 143 km2 (1.2%) |

## Profile transitions (largest changes vs BALANCED)

Area changing outcome vs BALANCED: CONSERVATIVE 6,643 km2, PERMISSIVE 7,129 km2 (AOI 39,930 km2).

| to_profile | from_status | to_status | cells | area_km2 |
|---|---|---|---|---|
| PERMISSIVE | STRONG_REGIONAL_CONCERN | REQUIRES_VERIFICATION | 10132 | 2512.05 |
| CONSERVATIVE | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | 9501 | 2354.08 |
| PERMISSIVE | REGIONAL_DEPRIORITIZE | STRONG_REGIONAL_CONCERN | 9303 | 2305.41 |
| PERMISSIVE | REQUIRES_VERIFICATION | NO_MAJOR_CONCERN_DETECTED | 8428 | 2093.22 |
| CONSERVATIVE | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | 7475 | 1857.66 |
| CONSERVATIVE | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | 5347 | 1324.4 |
| CONSERVATIVE | REQUIRES_VERIFICATION | REGIONAL_DEPRIORITIZE | 4153 | 1030.0 |
| PERMISSIVE | REQUIRES_VERIFICATION | UNRESOLVED | 928 | 217.56 |
| CONSERVATIVE | UNRESOLVED | REQUIRES_VERIFICATION | 335 | 77.2 |
| PERMISSIVE | REGIONAL_DEPRIORITIZE | REQUIRES_VERIFICATION | 3 | 0.75 |

![profile-differences.png](../../outputs/m1c-review/profile-differences.png)

## Candidate thresholds (each rule evaluated alone)

| candidate | threshold | AOI % | Chiang Mai % | Phayao % | Chiang Rai % | AOI km2 |
|---|---|---|---|---|---|---|
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.05 | 4.7 | 1.3 | 9.6 | 8.7 | 1887.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.1 | 3.7 | 1.0 | 7.8 | 6.6 | 1463.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.25 | 2.1 | 0.5 | 5.0 | 3.6 | 846.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.5 | 1.0 | 0.2 | 2.5 | 1.6 | 387.0 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.1 | 9.6 | 12.6 | 3.9 | 7.1 | 3848.0 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.25 | 6.9 | 9.1 | 2.8 | 5.0 | 2768.0 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.5 | 5.5 | 7.3 | 2.2 | 3.9 | 2200.0 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.75 | 3.5 | 4.6 | 1.3 | 2.4 | 1381.0 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.25 | 29.2 | 36.3 | 13.1 | 24.2 | 11656.0 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.5 | 24.7 | 31.0 | 10.8 | 19.9 | 9847.0 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.75 | 19.7 | 25.3 | 7.7 | 15.3 | 7854.0 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.95 | 14.6 | 19.2 | 5.4 | 10.9 | 5839.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 25.0 | 48.9 | 56.0 | 32.7 | 44.2 | 19541.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 30.0 | 25.6 | 30.2 | 15.4 | 22.4 | 10240.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 35.0 | 6.9 | 8.6 | 4.1 | 5.1 | 2754.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 40.0 | 1.4 | 2.0 | 0.8 | 0.8 | 570.0 |

Interactions (AOI, % of the flagged cells): unresolved for other hazards, and also flagged by other candidate rules:

| candidate | threshold | cells | share_with_landslide_unresolved | share_with_terrain_unresolved | also_flood_recurrent_ge0.10 | also_landslide_very_high_ge0.25 | also_landslide_high_plus_ge0.50 | also_terrain_p90_ge30 |
|---|---|---|---|---|---|---|---|---|
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.05 | 7561 | 89.6 | 0.0 | 77.6 | 0.0 | 0.1 | 0.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.1 | 5865 | 90.1 | 0.0 | 100.0 | 0.0 | 0.2 | 0.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.25 | 3392 | 91.3 | 0.0 | 100.0 | 0.0 | 0.2 | 0.0 |
| FLOOD_RECURRENT_FRACTION (>=3 of 12 yrs) | 0.5 | 1553 | 92.1 | 0.0 | 100.0 | 0.0 | 0.2 | 0.1 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.1 | 15864 | 0.0 | 0.1 | 0.0 | 72.5 | 81.4 | 61.1 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.25 | 11498 | 0.0 | 0.2 | 0.0 | 100.0 | 91.8 | 62.9 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.5 | 9168 | 0.0 | 0.2 | 0.0 | 100.0 | 100.0 | 62.2 |
| LANDSLIDE_VERY_HIGH_FRACTION | 0.75 | 5842 | 0.0 | 0.4 | 0.0 | 100.0 | 100.0 | 65.9 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.25 | 47822 | 0.1 | 0.1 | 0.0 | 24.0 | 84.7 | 49.1 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.5 | 40503 | 0.0 | 0.2 | 0.0 | 26.1 | 100.0 | 49.2 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.75 | 32446 | 0.0 | 0.2 | 0.0 | 28.4 | 100.0 | 51.6 |
| LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION | 0.95 | 24316 | 0.0 | 0.3 | 0.0 | 31.0 | 100.0 | 52.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 25.0 | 79311 | 0.1 | 0.0 | 0.0 | 13.0 | 42.5 | 52.4 |
| TERRAIN_DSM_SLOPE_P90_DEG | 30.0 | 41572 | 0.0 | 0.0 | 0.0 | 17.4 | 48.0 | 100.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 35.0 | 11244 | 0.1 | 0.0 | 0.0 | 24.6 | 53.6 | 100.0 |
| TERRAIN_DSM_SLOPE_P90_DEG | 40.0 | 2357 | 0.1 | 0.0 | 0.0 | 32.2 | 58.5 | 100.0 |

Terrain values derive from the Copernicus GLO-30 **DSM**, not a bare-earth model; terrain can only produce REQUIRES_VERIFICATION or corroborate landslide concern.

## Spatial structure (diagnostic; nothing smoothed or removed)

| profile | set | cells | area_km2 | components | isolated_single_cells | components_lt_1km2 | median_component_km2 | largest_component_km2 | share_area_in_largest_10 |
|---|---|---|---|---|---|---|---|---|---|
| CONSERVATIVE | DEPRIORITIZE | 48982 | 11952.45 | 1807 | 250 | 409 | 1.0 | 1177.39 | 0.5474 |
| CONSERVATIVE | CONCERN_OR_DEPRIORITIZE | 56797 | 13893.14 | 1513 | 279 | 434 | 1.25 | 3405.98 | 0.6014 |
| CONSERVATIVE | UNRESOLVED | 624 | 131.54 | 86 | 41 | 62 | 0.25 | 25.25 | 0.7072 |
| BALANCED | DEPRIORITIZE | 35328 | 8568.37 | 2249 | 216 | 1316 | 0.5 | 707.25 | 0.4314 |
| BALANCED | CONCERN_OR_DEPRIORITIZE | 47297 | 11538.73 | 2338 | 289 | 448 | 1.0 | 897.96 | 0.3881 |
| BALANCED | UNRESOLVED | 959 | 208.75 | 160 | 71 | 120 | 0.322 | 28.75 | 0.5686 |
| PERMISSIVE | DEPRIORITIZE | 26022 | 6262.2 | 2074 | 1110 | 1598 | 0.25 | 575.0 | 0.4813 |
| PERMISSIVE | CONCERN_OR_DEPRIORITIZE | 37162 | 9025.93 | 2404 | 270 | 1404 | 0.5 | 707.25 | 0.4125 |
| PERMISSIVE | UNRESOLVED | 1887 | 426.31 | 389 | 207 | 304 | 0.25 | 34.5 | 0.377 |

Largest BALANCED components:

| set | rank | component_area_km2 | cells | lon | lat | majority_province | dominant_reason |
|---|---|---|---|---|---|---|---|
| DEPRIORITIZE | 1 | 707.25 | 2829 | 98.504 | 18.617 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 2 | 596.83 | 2469 | 98.717 | 19.284 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 3 | 591.8 | 2436 | 99.342 | 19.068 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 4 | 576.48 | 2374 | 98.212 | 17.743 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 5 | 250.25 | 1001 | 99.284 | 19.547 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 6 | 231.14 | 953 | 98.242 | 18.552 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 7 | 215.0 | 860 | 98.796 | 19.544 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 8 | 199.04 | 838 | 99.156 | 20.067 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 9 | 179.75 | 719 | 99.491 | 19.982 | Chiang Rai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| DEPRIORITIZE | 10 | 148.75 | 595 | 99.577 | 19.858 | Chiang Rai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| CONCERN_OR_DEPRIORITIZE | 1 | 897.96 | 3680 | 98.739 | 19.353 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| CONCERN_OR_DEPRIORITIZE | 2 | 785.0 | 3140 | 98.504 | 18.617 | Chiang Mai | HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT |
| CONCERN_OR_DEPRIORITIZE | 3 | 673.03 | 2761 | 99.34 | 19.07 | Chiang Mai | TERRAIN_STEEPNESS_PROXY_HIGH |
| CONCERN_OR_DEPRIORITIZE | 4 | 669.86 | 2749 | 98.211 | 17.745 | Chiang Mai | TERRAIN_STEEPNESS_PROXY_HIGH |
| CONCERN_OR_DEPRIORITIZE | 5 | 305.25 | 1221 | 99.998 | 19.207 | Phayao | STRONG_RECURRENT_FLOOD_EVIDENCE |

![largest-deprioritized-regions.png](../../outputs/m1c-review/largest-deprioritized-regions.png)

## Unresolved / incomplete evidence (BALANCED)

Cells with incomplete evidence keep any positive evidence visible; only cells with no concern signal become UNRESOLVED (incompleteness overrides reassurance).

| evidence_completeness_class | regional_search_status | cells | area_km2 |
|---|---|---|---|
| UNRESOLVED_CRITICAL | REGIONAL_DEPRIORITIZE | 1412 | 336.1 |
| UNRESOLVED_CRITICAL | REQUIRES_VERIFICATION | 14181 | 3501.6 |
| UNRESOLVED_CRITICAL | STRONG_REGIONAL_CONCERN | 3609 | 901.2 |
| UNRESOLVED_CRITICAL | UNRESOLVED | 692 | 144.6 |
| UNRESOLVED_PARTIAL | REGIONAL_DEPRIORITIZE | 82 | 20.4 |
| UNRESOLVED_PARTIAL | REQUIRES_VERIFICATION | 2282 | 567.2 |
| UNRESOLVED_PARTIAL | STRONG_REGIONAL_CONCERN | 250 | 61.6 |
| UNRESOLVED_PARTIAL | UNRESOLVED | 267 | 64.1 |

![unresolved-evidence.png](../../outputs/m1c-review/unresolved-evidence.png)

## Reason codes (area km2 of cells carrying each code)

| reason_code | CONSERVATIVE | BALANCED | PERMISSIVE |
|---|---|---|---|
| LANDSLIDE_SUSCEPTIBILITY_BELOW_DEPRIORITIZATION | 14791.0 | 15534.0 | 16187.0 |
| TERRAIN_STEEPNESS_PROXY_HIGH | 19541.0 | 10240.0 | 2754.0 |
| OBSERVED_FLOOD_EVIDENCE | 8613.0 | 8247.0 | 7647.0 |
| HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT | 7310.0 | 5981.0 | 4701.0 |
| LANDSLIDE_NOT_ASSESSED | 5597.0 | 5597.0 | 5597.0 |
| VERY_HIGH_LANDSLIDE_SUSCEPTIBILITY_DOMINANT | 2768.0 | 2200.0 | 1381.0 |
| STRONG_LANDSLIDE_SUSCEPTIBILITY_EVIDENCE | 1932.0 | 1897.0 | 2098.0 |
| LANDSLIDE_TERRAIN_CORROBORATED | 5946.0 | 1530.0 | 306.0 |
| STRONG_RECURRENT_FLOOD_EVIDENCE | 1041.0 | 1076.0 | 666.0 |
| HISTORICAL_LANDSLIDE_SCAR_NEARBY | 4073.0 | 868.0 | 868.0 |
| PARTIAL_LANDSLIDE_COVERAGE | 730.0 | 730.0 | 730.0 |
| SCAR_CORROBORATES_LANDSLIDE_SUSCEPTIBILITY | 2137.0 | 404.0 | 351.0 |
| RECURRENT_FLOOD_SUBSTANTIAL_COVERAGE | 846.0 | 387.0 | 180.0 |
| LOW_TERRAIN_SUPPORT | 2.0 | 2.0 | 2.0 |
| MULTIPLE_STRONG_HAZARD_SIGNALS | 4.0 | 2.0 | 0.0 |
| TERRAIN_SUPPORT_INSUFFICIENT | 0.0 | 0.0 | 0.0 |

![reason-code-distribution.png](../../outputs/m1c-review/reason-code-distribution.png)

## Example explanation (BALANCED, generated from reason codes)

```text
CELL: G500-E001020-N004216
PROFILE: BALANCED (policy 0.1.0, PROVISIONAL)

HYDROGEOMORPHIC SCREENING
NO_MAJOR_CONCERN_DETECTED
evidence completeness: COMPLETE

WHY
- no major hydrogeomorphic concern detected within implemented datasets and thresholds

FLOOD
No strong historical recurrence detected in the 2005-2016 record (not evidence of no flood risk)

UNCERTAINTY
- terrain from Copernicus GLO-30 is a DSM (canopy/buildings), not ground slope
- DMR susceptibility methodology is not published; it is susceptibility, not probability of failure
- flood evidence is satellite-observed 2005-2016 only

THIS DOES NOT MEAN
- the parcel is unsafe or safe
- construction is impossible or approved
- no site survey is required
- natural hazards other than flood/landslide/terrain (e.g. earthquakes, active faults, wildfire) were assessed
```

More examples: `outputs/m1c/example-explanations.md`.

## Files

| File | Bytes |
|---|---:|
| candidate-threshold-sensitivity.csv | 6,983 |
| example-explanations.md | 5,630 |
| fragmentation-summary.csv | 798 |
| hazard-screening-policy.gpkg | 120,987,648 |
| hazard-screening-policy.gpkg.provenance.json | 2,212 |
| largest-components.csv | 9,002 |
| policy-results.parquet | 6,525,501 |
| policy-statistics.json | 15,359 |
| policy-status-by-scope.csv | 4,000 |
| profile-transitions.csv | 3,690 |
| reason-code-distribution.csv | 3,675 |
| m1c-review/largest-deprioritized-regions.png | 112,694 |
| m1c-review/policy-profiles-comparison.png | 334,167 |
| m1c-review/profile-differences.png | 229,406 |
| m1c-review/reason-code-distribution.png | 79,275 |
| m1c-review/unresolved-evidence.png | 165,854 |
