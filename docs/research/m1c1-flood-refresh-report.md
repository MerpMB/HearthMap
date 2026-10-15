# HearthMap M1C.1 — Flood truth refresh (GISTDA 2011-2023)

> Committed copy of `outputs/m1c1-review/README.md`; images live in the untracked review folder.

**Policy 0.2.0 — status PROVISIONAL; no default profile is selected.** Hydrogeomorphic screening only (observed flooding 2011-2023, DMR landslide susceptibility, DSM terrain); not a complete natural-hazard assessment. Outcomes are regional screening only — never safe, buildable, rejected or legally excluded.

## Human visual QA

| gate | status | review_date | reviewer_role | result |
|---|---|---|---|---|
| M1A1_HUMAN_VISUAL_SIGNOFF | PASSED | 2026-10-15 | project user | no blocking visual anomalies observed |
| M1B_HUMAN_VISUAL_SIGNOFF | PASSED | 2026-10-15 | project user | no blocking visual anomalies observed |
| M1C_HUMAN_VISUAL_SIGNOFF | PENDING |  |  |  |

Recorded in `config/human-qa.yaml` exactly as reported; no further observations are implied. The M1C policy review pack was not clearly part of the reviewed material and stays PENDING.

## GISTDA 2011-2023 (verified)

* 167,804 polygons in 124 AOI tiles (83 with features); 163,162 intersect the AOI.
* Each feature has exactly 13 yearly values 2011-2023; yearly `freq` ∈ {0, 1}; `total` = Σ yearly freq for 167,804 of 167,804 features → `total` = years observed flooded. Distribution of `total`: 1: 89,346, 2: 54,289, 3: 19,095, 4: 4,312, 5: 675, 6: 81, 7: 6.
* Geometry: 167804 geometries: 0 null, 0 empty, 0 invalid; repairs 0; exact duplicates 0; pairwise overlap 1.1e-06 m2 (areas additive); reprojected lon/lat → EPSG:32647 (UTM zone 47N (with axis order normalized for visualization), datum change: False).
* Feature-cap check: the two densest tiles re-requested as quadrants returned area ratio 1.000; area ratio 1.000.
* Licence: Open Data Common. Resolution 20 m (publisher). Ends 2023. Detailed methodology unpublished; the publisher's '10-year period' wording does not match the 13 yearly values.

Full semantic comparison: `docs/research/flood-record-comparison.md`.

![new-flood-evidence.png](../../outputs/m1c1-review/new-flood-evidence.png)

## Old vs new flood evidence

Observed flooded area in the AOI (km2, cell-clipped):

| measure | km2 |
|---|---|
| legacy_2005_2016_any | 3569.6 |
| legacy_2005_2016_ge3_of_12_years | 605.2 |
| refreshed_2011_2023_any | 2628.5 |
| refreshed_2011_2023_ge2_of_13_years | 932.9 |
| refreshed_2011_2023_ge3_of_13_years | 285.7 |
| refreshed_2011_2023_ge4_of_13_years | 66.9 |
| refreshed_2011_2023_ge5_of_13_years | 6.1 |
| legacy_recomputed_in_refresh_any | 3569.6 |

Cells with any observed flooding: legacy only 6,387, refreshed only 852, both 27,595, neither 127,239.

Per-cell flood screening tier (each record with its own definition: HIGH = ≥ 10% of the cell flooded in ≥ 3 of the record's years; CAUTION = any observed flooding ≥ 1% or within 250 m):

| flood_change_class | AOI cells | AOI km2 | Chiang Mai km2 | Phayao km2 | Chiang Rai km2 |
|---|---|---|---|---|---|
| CONSISTENT_NO_MAJOR_SIGNAL | 122038 | 29964.7 | 19581.0 | 3676.6 | 6707.1 |
| CONSISTENT_CONCERN | 29028 | 7227.7 | 1833.8 | 1813.8 | 3580.1 |
| NEWER_DATA_INCREASES_CONCERN | 1905 | 470.6 | 121.4 | 89.0 | 260.2 |
| NEWER_DATA_DECREASES_CONCERN | 9102 | 2267.4 | 623.4 | 615.0 | 1028.9 |
| NOT_DIRECTLY_COMPARABLE | 0 | 0.0 | 0.0 | 0.0 | 0.0 |

| 2005-2016 tier \ 2011-2023 tier | CAUTION | HIGH | NONE_DETECTED |
|---|---|---|---|
| CAUTION | 26992 | 869 | 5273 |
| HIGH | 3826 | 2036 | 3 |
| NONE_DETECTED | 1036 | 0 | 122038 |

Largest contiguous changes:

| set | rank | area_km2 | cells | lon | lat | majority_province |
|---|---|---|---|---|---|---|
| NEWER_DATA_INCREASES_CONCERN | 1 | 22.75 | 91 | 99.41 | 20.052 | Chiang Mai |
| NEWER_DATA_INCREASES_CONCERN | 2 | 15.75 | 63 | 99.283 | 19.996 | Chiang Mai |
| NEWER_DATA_INCREASES_CONCERN | 3 | 12.5 | 50 | 99.955 | 19.95 | Chiang Rai |
| NEWER_DATA_INCREASES_CONCERN | 4 | 11.5 | 46 | 100.059 | 20.346 | Chiang Rai |
| NEWER_DATA_INCREASES_CONCERN | 5 | 10.25 | 41 | 99.842 | 20.344 | Chiang Rai |
| NEWER_DATA_INCREASES_CONCERN | 6 | 9.75 | 39 | 100.387 | 19.111 | Phayao |
| NEWER_DATA_INCREASES_CONCERN | 7 | 8.25 | 33 | 100.42 | 19.164 | Phayao |
| NEWER_DATA_INCREASES_CONCERN | 8 | 7.0 | 28 | 99.913 | 20.262 | Chiang Rai |
| NEWER_DATA_INCREASES_CONCERN | 9 | 7.0 | 28 | 99.52 | 19.692 | Chiang Rai |
| NEWER_DATA_INCREASES_CONCERN | 10 | 6.0 | 24 | 99.675 | 19.416 | Chiang Rai |
| NEWER_DATA_DECREASES_CONCERN | 1 | 87.25 | 349 | 100.08 | 19.798 | Chiang Rai |
| NEWER_DATA_DECREASES_CONCERN | 2 | 68.0 | 272 | 100.347 | 20.143 | Chiang Rai |
| NEWER_DATA_DECREASES_CONCERN | 3 | 49.0 | 196 | 100.026 | 19.085 | Phayao |
| NEWER_DATA_DECREASES_CONCERN | 4 | 46.0 | 184 | 99.872 | 19.452 | Phayao |
| NEWER_DATA_DECREASES_CONCERN | 5 | 43.5 | 174 | 99.158 | 19.87 | Chiang Mai |
| NEWER_DATA_DECREASES_CONCERN | 6 | 43.0 | 172 | 100.032 | 19.193 | Phayao |
| NEWER_DATA_DECREASES_CONCERN | 7 | 42.5 | 170 | 98.997 | 18.768 | Chiang Mai |
| NEWER_DATA_DECREASES_CONCERN | 8 | 42.25 | 169 | 99.198 | 19.386 | Chiang Mai |
| NEWER_DATA_DECREASES_CONCERN | 9 | 39.25 | 157 | 99.913 | 19.115 | Phayao |
| NEWER_DATA_DECREASES_CONCERN | 10 | 36.25 | 145 | 98.752 | 18.491 | Chiang Mai |

![old-vs-new-flood.png](../../outputs/m1c1-review/old-vs-new-flood.png)

## M1B evidence refresh

Landslide tiers unchanged: True; terrain tiers unchanged: True. Overall screening state changed in 6,898 cells (1,721 km2). Mean evidence completeness 0.9531 → 0.9531.

| before | after | cells | area_km2 |
|---|---|---|---|
| HIGH_SCREENING_CONCERN | UNRESOLVED | 3433 | 857.53 |
| SCREENING_CAUTION | NO_HIGH_SCREENING_CONCERN_DETECTED | 1906 | 476.27 |
| UNRESOLVED | HIGH_SCREENING_CONCERN | 770 | 190.44 |
| HIGH_SCREENING_CONCERN | SCREENING_CAUTION | 389 | 97.24 |
| NO_HIGH_SCREENING_CONCERN_DETECTED | SCREENING_CAUTION | 302 | 74.81 |
| SCREENING_CAUTION | HIGH_SCREENING_CONCERN | 98 | 24.5 |

## M1C profile refresh (policy 0.1.0 on 2005-2016 → 0.2.0 on 2011-2023)

Only the flood record (and the explicit flood threshold semantics) changed; every landslide/terrain/multi-hazard threshold is identical. Province rows use majority-province attribution.

**AOI** (cells before → after / km2 before → after (Δ km2))

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 12,589 → 14,095 / 3,117 → 3,493 km2 (+377) | 92,063 → 93,624 / 22,789 → 23,186 km2 (+397) | 7,815 → 5,874 / 1,941 → 1,455 km2 (-486) | 48,982 → 47,196 / 11,952 → 11,505 km2 (-447) | 624 → 1,284 / 132 → 291 km2 (+160) |
| BALANCED | 20,064 → 22,135 / 4,974 → 5,492 km2 (+518) | 93,753 → 93,583 / 23,209 → 23,171 km2 (-38) | 11,969 → 9,842 / 2,970 → 2,437 km2 (-533) | 35,328 → 34,501 / 8,568 → 8,361 km2 (-207) | 959 → 2,012 / 209 → 468 km2 (+259) |
| PERMISSIVE | 28,492 → 31,204 / 7,067 → 7,745 km2 (+678) | 94,532 → 91,635 / 23,411 → 22,689 km2 (-722) | 11,140 → 9,804 / 2,764 → 2,429 km2 (-335) | 26,022 → 25,572 / 6,262 → 6,150 km2 (-113) | 1,887 → 3,858 / 426 → 918 km2 (+491) |

**Chiang Mai** (cells before → after / km2 before → after (Δ km2))

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 8,034 → 8,587 / 1,995 → 2,133 km2 (+138) | 46,647 → 46,592 / 11,534 → 11,524 km2 (-10) | 3,086 → 2,523 / 763 → 622 km2 (-140) | 32,047 → 31,736 / 7,803 → 7,726 km2 (-77) | 287 → 663 / 65 → 154 km2 (+89) |
| BALANCED | 12,262 → 12,924 / 3,047 → 3,213 km2 (+166) | 47,580 → 46,968 / 11,761 → 11,611 km2 (-149) | 5,553 → 5,033 / 1,376 → 1,247 km2 (-130) | 24,244 → 24,114 / 5,869 → 5,836 km2 (-32) | 462 → 1,062 / 107 → 252 km2 (+145) |
| PERMISSIVE | 16,538 → 17,269 / 4,110 → 4,293 km2 (+183) | 48,100 → 46,708 / 11,896 → 11,549 km2 (-347) | 6,080 → 5,814 / 1,505 → 1,439 km2 (-66) | 18,435 → 18,390 / 4,431 → 4,420 km2 (-11) | 948 → 1,920 / 218 → 459 km2 (+242) |

**Phayao** (cells before → after / km2 before → after (Δ km2))

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 2,929 → 3,356 / 726 → 832 km2 (+107) | 16,264 → 17,071 / 4,021 → 4,222 km2 (+202) | 1,490 → 929 / 370 → 230 km2 (-140) | 4,448 → 3,713 / 1,064 → 880 km2 (-184) | 57 → 119 / 14 → 29 km2 (+16) |
| BALANCED | 4,473 → 5,064 / 1,109 → 1,257 km2 (+148) | 15,769 → 16,123 / 3,895 → 3,983 km2 (+88) | 2,025 → 1,285 / 501 → 316 km2 (-185) | 2,823 → 2,476 / 665 → 579 km2 (-87) | 98 → 240 / 24 → 59 km2 (+36) |
| PERMISSIVE | 6,315 → 7,090 / 1,566 → 1,760 km2 (+194) | 15,181 → 14,730 / 3,747 → 3,634 km2 (-113) | 1,511 → 1,031 / 375 → 255 km2 (-120) | 1,916 → 1,661 / 441 → 377 km2 (-64) | 265 → 676 / 65 → 168 km2 (+103) |

**Chiang Rai** (cells before → after / km2 before → after (Δ km2))

| profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|
| CONSERVATIVE | 1,626 → 2,152 / 396 → 528 km2 (+132) | 29,152 → 29,961 / 7,234 → 7,440 km2 (+205) | 3,239 → 2,422 / 808 → 602 km2 (-205) | 12,487 → 11,747 / 3,085 → 2,899 km2 (-186) | 280 → 502 / 53 → 108 km2 (+55) |
| BALANCED | 3,329 → 4,147 / 818 → 1,022 km2 (+204) | 30,404 → 30,492 / 7,553 → 7,576 km2 (+23) | 4,391 → 3,524 / 1,093 → 874 km2 (-218) | 8,261 → 7,911 / 2,035 → 1,946 km2 (-88) | 399 → 710 / 78 → 157 km2 (+79) |
| PERMISSIVE | 5,639 → 6,845 / 1,391 → 1,693 km2 (+302) | 31,251 → 30,197 / 7,768 → 7,506 km2 (-262) | 3,549 → 2,959 / 883 → 735 km2 (-149) | 5,671 → 5,521 / 1,390 → 1,352 km2 (-38) | 674 → 1,262 / 143 → 290 km2 (+147) |

![balanced-policy-refreshed.png](../../outputs/m1c1-review/balanced-policy-refreshed.png)

![profile-change-summary.png](../../outputs/m1c1-review/profile-change-summary.png)

## Policy stability

| profile | cells changed | area changed km2 | share of AOI | more concern (cells / km2) | less concern (cells / km2) | to/from UNRESOLVED | Chiang Mai / Phayao / Chiang Rai km2 |
|---|---|---|---|---|---|---|---|
| CONSERVATIVE | 9,665 | 2,404 | 6.02% | 1,655 / 411 | 7,170 / 1,792 | 840 | 640 / 680 / 1,084 |
| BALANCED | 9,328 | 2,319 | 5.81% | 1,386 / 343 | 6,655 / 1,663 | 1287 | 659 / 660 / 1,000 |
| PERMISSIVE | 9,048 | 2,252 | 5.64% | 957 / 238 | 5,682 / 1,420 | 2409 | 678 / 631 / 943 |

Named transitions (cells / km2, before → after):

| transition | direction | CONSERVATIVE | BALANCED | PERMISSIVE |
|---|---|---|---|---|
| NO_MAJOR_CONCERN_DETECTED → REQUIRES_VERIFICATION | forward | 278 / 69.4 km2 | 367 / 91.1 km2 | 348 / 87.0 km2 |
| REQUIRES_VERIFICATION → NO_MAJOR_CONCERN_DETECTED | reverse | 1,784 / 446.0 km2 | 2,438 / 609.3 km2 | 3,060 / 765.0 km2 |
| REQUIRES_VERIFICATION → STRONG_REGIONAL_CONCERN | forward | 820 / 203.2 km2 | 803 / 198.7 km2 | 533 / 132.1 km2 |
| STRONG_REGIONAL_CONCERN → REQUIRES_VERIFICATION | reverse | 3,043 / 760.4 km2 | 3,174 / 793.2 km2 | 2,096 / 523.5 km2 |
| STRONG_REGIONAL_CONCERN → REGIONAL_DEPRIORITIZE | forward | 329 / 81.7 km2 | 151 / 37.2 km2 | 52 / 13.0 km2 |
| REGIONAL_DEPRIORITIZE → STRONG_REGIONAL_CONCERN | reverse | 618 / 154.5 km2 | 398 / 99.5 km2 | 283 / 70.8 km2 |
| REQUIRES_VERIFICATION → REGIONAL_DEPRIORITIZE | forward | 228 / 56.2 km2 | 65 / 16.2 km2 | 24 / 5.8 km2 |
| REGIONAL_DEPRIORITIZE → REQUIRES_VERIFICATION | reverse | 1,725 / 430.7 km2 | 645 / 160.8 km2 | 243 / 60.8 km2 |

All BALANCED transitions:

| before | after | cells | area_km2 |
|---|---|---|---|
| STRONG_REGIONAL_CONCERN | REQUIRES_VERIFICATION | 3174 | 793.17 |
| REQUIRES_VERIFICATION | NO_MAJOR_CONCERN_DETECTED | 2438 | 609.27 |
| REQUIRES_VERIFICATION | UNRESOLVED | 1167 | 285.45 |
| REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | 803 | 198.69 |
| REGIONAL_DEPRIORITIZE | REQUIRES_VERIFICATION | 645 | 160.85 |
| REGIONAL_DEPRIORITIZE | STRONG_REGIONAL_CONCERN | 398 | 99.5 |
| NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | 367 | 91.06 |
| STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | 151 | 37.2 |
| UNRESOLVED | REQUIRES_VERIFICATION | 117 | 27.0 |
| REQUIRES_VERIFICATION | REGIONAL_DEPRIORITIZE | 65 | 16.25 |
| STRONG_REGIONAL_CONCERN | UNRESOLVED | 3 | 0.75 |

Largest contiguous changed regions:

| set | rank | area_km2 | cells | lon | lat | majority_province |
|---|---|---|---|---|---|---|
| CONSERVATIVE:MORE_CONCERN | 1 | 29.0 | 116 | 99.294 | 19.998 | Chiang Mai |
| CONSERVATIVE:MORE_CONCERN | 2 | 14.25 | 57 | 99.954 | 19.949 | Chiang Rai |
| CONSERVATIVE:MORE_CONCERN | 3 | 14.25 | 57 | 99.9 | 20.327 | Chiang Rai |
| CONSERVATIVE:MORE_CONCERN | 4 | 8.0 | 32 | 100.389 | 19.115 | Phayao |
| CONSERVATIVE:MORE_CONCERN | 5 | 7.75 | 31 | 99.24 | 19.936 | Chiang Mai |
| CONSERVATIVE:LESS_CONCERN | 1 | 206.0 | 824 | 99.986 | 19.135 | Phayao |
| CONSERVATIVE:LESS_CONCERN | 2 | 112.75 | 451 | 99.737 | 19.583 | Chiang Rai |
| CONSERVATIVE:LESS_CONCERN | 3 | 47.75 | 191 | 99.198 | 19.386 | Chiang Mai |
| CONSERVATIVE:LESS_CONCERN | 4 | 44.25 | 177 | 99.814 | 19.278 | Phayao |
| CONSERVATIVE:LESS_CONCERN | 5 | 39.5 | 158 | 98.756 | 18.499 | Chiang Mai |
| BALANCED:MORE_CONCERN | 1 | 18.75 | 75 | 99.283 | 19.993 | Chiang Mai |
| BALANCED:MORE_CONCERN | 2 | 13.5 | 54 | 99.954 | 19.949 | Chiang Rai |
| BALANCED:MORE_CONCERN | 3 | 9.75 | 39 | 99.906 | 20.323 | Chiang Rai |
| BALANCED:MORE_CONCERN | 4 | 7.5 | 30 | 100.388 | 19.114 | Phayao |
| BALANCED:MORE_CONCERN | 5 | 7.0 | 28 | 99.913 | 20.262 | Chiang Rai |
| BALANCED:LESS_CONCERN | 1 | 161.75 | 647 | 99.995 | 19.134 | Phayao |
| BALANCED:LESS_CONCERN | 2 | 42.25 | 169 | 99.198 | 19.386 | Chiang Mai |
| BALANCED:LESS_CONCERN | 3 | 36.0 | 144 | 99.724 | 19.538 | Chiang Rai |
| BALANCED:LESS_CONCERN | 4 | 35.5 | 142 | 98.753 | 18.491 | Chiang Mai |
| BALANCED:LESS_CONCERN | 5 | 28.5 | 114 | 99.71 | 19.666 | Chiang Rai |
| PERMISSIVE:MORE_CONCERN | 1 | 14.75 | 59 | 99.292 | 20.0 | Chiang Mai |
| PERMISSIVE:MORE_CONCERN | 2 | 6.25 | 25 | 99.788 | 19.488 | Chiang Rai |
| PERMISSIVE:MORE_CONCERN | 3 | 4.5 | 18 | 100.387 | 19.114 | Phayao |
| PERMISSIVE:MORE_CONCERN | 4 | 4.5 | 18 | 99.905 | 20.133 | Chiang Rai |
| PERMISSIVE:MORE_CONCERN | 5 | 4.0 | 16 | 99.24 | 19.933 | Chiang Mai |
| PERMISSIVE:LESS_CONCERN | 1 | 63.0 | 252 | 100.013 | 19.313 | Phayao |
| PERMISSIVE:LESS_CONCERN | 2 | 41.75 | 167 | 100.024 | 19.184 | Phayao |
| PERMISSIVE:LESS_CONCERN | 3 | 35.25 | 141 | 99.213 | 19.398 | Chiang Mai |
| PERMISSIVE:LESS_CONCERN | 4 | 31.75 | 127 | 98.757 | 18.482 | Chiang Mai |
| PERMISSIVE:LESS_CONCERN | 5 | 19.75 | 79 | 99.705 | 19.679 | Chiang Rai |

![flood-policy-change.png](../../outputs/m1c1-review/flood-policy-change.png)

## Flood threshold review (2011-2023 semantics)

Configured: source `flood-gistda-history`, period 2011-2023, 13 years; source-native metric: total = number of years 2011-2023 observed flooded (sum of yearly detail.freq, each 0/1). Derived: flood_years_ge{min_years_flooded}_area_fraction = share of the cell observed flooded in >= min_years_flooded of the 13 years; *_min_fraction thresholds apply to that share.

| candidate | threshold | cells | area_km2 | share_of_area | share_with_landslide_unresolved | also_landslide_high_plus_ge0.50 |
|---|---|---|---|---|---|---|
| FLOOD_YEARS_GE2_OF_13 (2011-2023) FRACTION | 0.05 | 10588 | 2640.02 | 6.61 | 0.8398 | 0.0024 |
| FLOOD_YEARS_GE2_OF_13 (2011-2023) FRACTION | 0.1 | 8712 | 2171.52 | 5.44 | 0.858 | 0.0018 |
| FLOOD_YEARS_GE2_OF_13 (2011-2023) FRACTION | 0.25 | 5477 | 1364.19 | 3.42 | 0.8808 | 0.0009 |
| FLOOD_YEARS_GE2_OF_13 (2011-2023) FRACTION | 0.5 | 2700 | 672.76 | 1.68 | 0.9074 | 0.0004 |
| FLOOD_YEARS_GE3_OF_13 (2011-2023) FRACTION | 0.05 | 3828 | 952.3 | 2.38 | 0.889 | 0.0018 |
| FLOOD_YEARS_GE3_OF_13 (2011-2023) FRACTION | 0.1 | 2905 | 722.08 | 1.81 | 0.9029 | 0.0014 |
| FLOOD_YEARS_GE3_OF_13 (2011-2023) FRACTION | 0.25 | 1605 | 398.38 | 1.0 | 0.9178 | 0.0006 |
| FLOOD_YEARS_GE3_OF_13 (2011-2023) FRACTION | 0.5 | 728 | 180.73 | 0.45 | 0.9272 | 0.0 |
| FLOOD_YEARS_GE4_OF_13 (2011-2023) FRACTION | 0.05 | 1030 | 255.01 | 0.64 | 0.8864 | 0.0029 |
| FLOOD_YEARS_GE4_OF_13 (2011-2023) FRACTION | 0.1 | 740 | 183.42 | 0.46 | 0.8946 | 0.0041 |
| FLOOD_YEARS_GE4_OF_13 (2011-2023) FRACTION | 0.25 | 382 | 94.58 | 0.24 | 0.9136 | 0.0026 |
| FLOOD_YEARS_GE4_OF_13 (2011-2023) FRACTION | 0.5 | 122 | 30.1 | 0.08 | 0.918 | 0.0 |
| FLOOD_YEARS_GE5_OF_13 (2011-2023) FRACTION | 0.05 | 121 | 29.41 | 0.07 | 0.8264 | 0.0083 |
| FLOOD_YEARS_GE5_OF_13 (2011-2023) FRACTION | 0.1 | 72 | 17.36 | 0.04 | 0.8472 | 0.0 |
| FLOOD_YEARS_GE5_OF_13 (2011-2023) FRACTION | 0.25 | 29 | 6.99 | 0.02 | 0.8276 | 0.0 |
| FLOOD_YEARS_GE5_OF_13 (2011-2023) FRACTION | 0.5 | 11 | 2.63 | 0.01 | 0.9091 | 0.0 |

## Files

| File | Bytes |
|---|---:|
| m1c1/evidence-refresh-transitions.csv | 1,431 |
| m1c1/flood-2011-2023-api-completeness.json | 586 |
| m1c1/flood-2011-2023-qa.json | 2,266 |
| m1c1/flood-2011-2023-repair-audit.csv | 255 |
| m1c1/flood-change-cells.parquet | 1,119,422 |
| m1c1/flood-change-largest-regions.csv | 1,344 |
| m1c1/flood-change-summary.csv | 1,212 |
| m1c1/policy-refresh-distribution.csv | 5,117 |
| m1c1/policy-refresh-largest-changes.csv | 1,842 |
| m1c1/policy-refresh-transitions.csv | 3,181 |
| m1c1/refresh-statistics.json | 4,722 |
| m1c1-review/balanced-policy-refreshed.png | 138,595 |
| m1c1-review/flood-policy-change.png | 215,796 |
| m1c1-review/new-flood-evidence.png | 205,717 |
| m1c1-review/old-vs-new-flood.png | 193,526 |
| m1c1-review/profile-change-summary.png | 46,808 |
