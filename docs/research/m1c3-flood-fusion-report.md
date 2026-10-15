# HearthMap M1C.3 - Flood evidence fusion policy

> Committed copy of `outputs/m1c3-review/README.md`; images and tables live in the untracked review folder.

**Flood fusion 0.1.0 - status PROVISIONAL; no flood candidate and no hydrogeomorphic profile is selected.** Hydrogeomorphic screening only; observed flooding only - the absence of a polygon in either product is never evidence of no flood risk, and outcomes never mean safe, buildable or rejected. Semantics: `docs/product/flood-fusion-policy.md`.

`observed_year_count_total`: number of calendar years in which at least one available GISTDA product mapped observed flooding (>= presence_min_fraction of the cell); a raw observational count, NOT a probability, return period or homogeneous recurrence series.

## Findings

**Ledger.** 32,621 of 162,073 cells (20.1%) have flooding mapped by at least one
GISTDA product in at least one year 2005–2023; 129,452 have none. The raw count
of mapped years per cell (`observed_year_count_total`) is 1 for 9,076 cells, 2
for 5,624, 3 for 4,782, 4 for 4,478, 5 for 4,049 and 6+ for 4,612. It is a count
of mapped years, not a probability. The mapped area is dominated by a few
regional flood years (mapped area in the AOI: 2011 1,854 km2; 2005 1,424;
2017 1,096; 2010 832; 2009 734; 2022 487). 3,057 cells carry a 2011–2016 product disagreement (2014 and 2016) that
stays visible after fusion.

**The three candidates are not equally different.** `FLOOD_CURRENT_PRIMARY` and
`FLOOD_ANY_SOURCE` differ on only 1,262 cells (315 km2, 0.8% of the AOI; 304 km2
of that is verification → strong). `FLOOD_UNION_CONSERVATIVE` is the outlier: it
adds strong concern for 18,070 cells (4,508 km2) versus 4,337 (1,079 km2) and
5,556 (1,383 km2). Its extra strong cells come from two rules: ≥ 50% of a cell
flooded in any single year (11,238 cells; the triggering years are 2011 for
5,535 cells, 2005 for 4,312, 2017 for 3,458, 2010 for 2,254, 2009 for 2,050) and ≥ 2 years of ≥ 10% anywhere in the 2005–2023 ledger
(17,207 cells, 14,192 of which include 2011: two of the big regional flood
years, not necessarily recurrence at a place).

**Flood-source choice vs hydrogeomorphic-profile choice.**

| | flood-source choice (3 candidates, profile fixed) | profile choice (3 profiles, flood policy fixed) |
|---|---|---|
| mean pairwise changed area | 2,476 km2 (6.2% of AOI) | 6,707 km2 (16.8%) |
| maximum pairwise changed area | 3,733 km2 | 9,125 km2 |
| area that is not identical across all 9 combinations | 32% of the AOI (shared) | |

Over the whole AOI the profile choice moves roughly 2.7 times more area than the
flood-source choice. But the two choices act on different land:

* On **low-slope land** (DSM slope p90 ≤ 5°, 6,026 km2, 15% of the AOI), the
  flood-source choice changes the overall outcome of 47.7% of the area, while the
  profile choice changes only 0.9% (57 km2).
* On **steep land** (> 15°, 28,146 km2, 70% of the AOI), the profile choice
  changes 30%, the flood-source choice 0.6%.
* 77% of all flood-source-sensitive area is on low-slope land (5.1× its share of
  the AOI), and 96% is ≤ 15°.

The two decisions are therefore nearly independent: profiles differ about steep
land (landslide and terrain thresholds), flood policies differ about lowlands.
The slope strata are descriptive only; nothing here says low-slope land is
suitable.

**Sensitive regions.** 3,733 km2 (14,957 cells) change outcome with the
flood-source choice under at least one profile, in 1,489 connected components;
the ten largest hold 53%. All of the leading regions show the same pattern
(REQUIRES_VERIFICATION under both current-primary and any-source, STRONG
CONCERN under the union candidate): Chiang Rai basin (507 km2, 99.77 E, 19.55 N,
82% low slope), Phayao lowland (321 km2), Chiang Mai (259 km2, 99.10 E, 18.81 N),
Chiang Rai east (186 km2) and others. Product disagreement and older-only
evidence are minor contributors there (at most 17% and 30% of the cells in each leading region); recent
2017–2023 evidence dominates.

**Behaviour checks.**

* Positive-only, nesting (current-primary ≤ any-source ≤ union) and the wording
  rules hold for all candidates (tested). No state or code claims safety.
* `FLOOD_UNION_CONSERVATIVE` puts 62% of low-slope land into strong concern, in
  effect removing the lowland search space on the strength of a few regional
  flood years. This is not an error in the rule as written, but it is the
  behaviour most in need of a value judgement and I do not recommend it as
  written.
* All fused candidates drop the previous policy's "within 250 m of observed
  flooding" verification rule (the ledger is area-based). Under BALANCED the
  UNRESOLVED area roughly doubles (468 → 988–990 km2; 848 km2 under the union
  candidate) because cells beside mapped
  flooding and outside DMR landslide coverage no longer carry a verification
  flag. This is a measurable side effect to review, not hidden.
* A flood candidate alone never reaches `REGIONAL_DEPRIORITIZE` (flood caps at
  STRONG); deprioritization comes from landslide/terrain or the multi-hazard
  escalation, so deprioritized area is nearly the same under all three
  candidates (8,181–8,186 km2 under BALANCED).

## Decision gate

1. **Is flood-policy uncertainty small enough to choose an overall hazard
   profile?** Yes for the profile decision itself, because the flood choice and
   the profile choice act on different land and are almost independent (0.9% of
   low-slope area depends on the profile; 0.6% of steep area depends on the
   flood source). The flood policy is not settled in lowlands, but that decision
   does not change which profile to prefer.
2. **Which cells remain sensitive to flood-source treatment?** 3,733 km2,
   concentrated in the Chiang Rai and Phayao basins and the Chiang Mai valley
   (see `policy-sensitive-regions.csv`), almost all of it the gap between the
   union candidate and the other two.
3. **Disproportionately inside residential lowlands?** Yes: 77% of the sensitive
   area is on ≤ 5° land, which is 15% of the AOI (ratio 5.1). Whether any of it
   is residential or suitable is not assessed.
4. **Obviously unreasonable behaviour?** None against the stated principles. Two
   behaviours need review: single-year dominance in the union candidate and the
   dropped proximity rule.
5. **Can one flood-fusion policy be recommended for regional screening?**
   `FLOOD_ANY_SOURCE` (provisionally, not selected): any well-supported
   observation raises concern, legacy evidence stays positive-only, recent and
   consensus recurrence escalate, overlap disagreement triggers verification,
   and no single regional flood year dominates. It differs from the current-
   primary candidate on only 0.8% of the AOI, so the real choice is between the
   recurrence-based pair and the union candidate.


## Annual source-aware ledger

Cells by number of years with observed flooding (raw observational count):

| observed years | cells |
|---|---|
| 0 | 129452 |
| 1 | 9076 |
| 2 | 5624 |
| 3 | 4782 |
| 4 | 4478 |
| 5 | 4049 |
| 6 | 2280 |
| 7 | 1192 |
| 8 | 645 |
| 9 | 349 |
| 10 | 106 |
| 11 | 24 |
| 12 | 16 |

![annual-source-ledger-summary.png](../../outputs/m1c3-review/annual-source-ledger-summary.png)

![recent-vs-historical-flood.png](../../outputs/m1c3-review/recent-vs-historical-flood.png)

![product-disagreement.png](../../outputs/m1c3-review/product-disagreement.png)

## Flood policy candidates (exact rules)

Each candidate also inherits every rule of the candidate it extends. A rule fires when the metric is >= `min_cell_fraction` in >= `min_years` years of the window; unavailable years never count.

| candidate | level | rule | metric | years | min_years | min_cell_fraction |
|---|---|---|---|---|---|---|
| FLOOD_CURRENT_PRIMARY | STRONG | FLOOD_CURRENT_PRODUCT_RECURRENT_SUBSTANTIAL | current_fraction | 2011-2023 | 3 | 0.1 |
| FLOOD_CURRENT_PRIMARY | VERIFY | FLOOD_CURRENT_PRODUCT_OBSERVED | current_fraction | 2011-2023 | 1 | 0.05 |
| FLOOD_CURRENT_PRIMARY | VERIFY | FLOOD_LEGACY_ONLY_OBSERVATION | legacy_exclusive_fraction | 2005-2016 | 1 | 0.1 |
| FLOOD_CURRENT_PRIMARY | VERIFY | FLOOD_PRODUCT_DISAGREEMENT_2011_2016 | mismatch_fraction | 2011-2016 | 1 | 0.1 |
| FLOOD_CURRENT_PRIMARY | HISTORICAL | FLOOD_HISTORICAL_OBSERVATION | observed_fraction | 2005-2023 | 1 | 0.01 |
| FLOOD_ANY_SOURCE | STRONG | FLOOD_RECENT_RECURRENCE_2017_2023 | observed_fraction | 2017-2023 | 2 | 0.1 |
| FLOOD_ANY_SOURCE | STRONG | FLOOD_CONSENSUS_RECURRENCE_2011_2016 | intersection_fraction | 2011-2016 | 2 | 0.1 |
| FLOOD_ANY_SOURCE | VERIFY | FLOOD_OBSERVED_2011_2023 | observed_fraction | 2011-2023 | 1 | 0.05 |
| FLOOD_ANY_SOURCE | VERIFY | FLOOD_OLDER_SUBSTANTIAL_2005_2010 | observed_fraction | 2005-2010 | 1 | 0.1 |
| FLOOD_ANY_SOURCE | VERIFY | FLOOD_PRODUCT_DISAGREEMENT_2011_2016 | mismatch_fraction | 2011-2016 | 1 | 0.05 |
| FLOOD_UNION_CONSERVATIVE | STRONG | FLOOD_UNION_REPEAT_OBSERVATIONS | observed_fraction | 2005-2023 | 2 | 0.1 |
| FLOOD_UNION_CONSERVATIVE | STRONG | FLOOD_UNION_SUBSTANTIAL_SINGLE_YEAR | observed_fraction | 2005-2023 | 1 | 0.5 |
| FLOOD_UNION_CONSERVATIVE | VERIFY | FLOOD_UNION_OBSERVED | observed_fraction | 2005-2023 | 1 | 0.05 |
| FLOOD_UNION_CONSERVATIVE | VERIFY | FLOOD_PRODUCT_DISAGREEMENT_2011_2016 | mismatch_fraction | 2011-2016 | 1 | 0.01 |

Reason-code frequency (cells):

| reason_code | FLOOD_ANY_SOURCE | FLOOD_CURRENT_PRIMARY | FLOOD_UNION_CONSERVATIVE |
|---|---|---|---|
| FLOOD_CONSENSUS_RECURRENCE_2011_2016 | 1756 | 0 | 1756 |
| FLOOD_CURRENT_PRODUCT_OBSERVED | 23406 | 23406 | 23406 |
| FLOOD_CURRENT_PRODUCT_RECURRENT_SUBSTANTIAL | 4337 | 4337 | 4337 |
| FLOOD_HISTORICAL_OBSERVATION | 32621 | 32621 | 32621 |
| FLOOD_LEGACY_ONLY_OBSERVATION | 19951 | 19951 | 19951 |
| FLOOD_OBSERVED_2011_2023 | 23545 | 0 | 23545 |
| FLOOD_OLDER_SUBSTANTIAL_2005_2010 | 19458 | 0 | 19458 |
| FLOOD_PRODUCT_DISAGREEMENT_2011_2016 | 2653 | 2312 | 3057 |
| FLOOD_RECENT_RECURRENCE_2017_2023 | 4365 | 0 | 4365 |
| FLOOD_UNION_OBSERVED | 0 | 0 | 28492 |
| FLOOD_UNION_REPEAT_OBSERVATIONS | 0 | 0 | 17207 |
| FLOOD_UNION_SUBSTANTIAL_SINGLE_YEAR | 0 | 0 | 11238 |

## Candidate comparison

**AOI** (cells / area / share)

| flood ladder state | FLOOD_CURRENT_PRIMARY | FLOOD_ANY_SOURCE | FLOOD_UNION_CONSERVATIVE |
|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 129,452 / 31,799 km2 (79.6%) | 129,452 / 31,799 km2 (79.6%) | 129,452 / 31,799 km2 (79.6%) |
| HISTORICAL_SIGNAL | 5,575 / 1,388 km2 (3.5%) | 5,532 / 1,378 km2 (3.5%) | 4,094 / 1,019 km2 (2.5%) |
| REQUIRES_FLOOD_VERIFICATION | 22,709 / 5,663 km2 (14.2%) | 21,533 / 5,370 km2 (13.5%) | 10,457 / 2,604 km2 (6.5%) |
| STRONG_FLOOD_SCREENING_CONCERN | 4,337 / 1,079 km2 (2.7%) | 5,556 / 1,383 km2 (3.5%) | 18,070 / 4,508 km2 (11.3%) |
| UNRESOLVED | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) |

**Chiang Mai** (cells / area / share)

| flood ladder state | FLOOD_CURRENT_PRIMARY | FLOOD_ANY_SOURCE | FLOOD_UNION_CONSERVATIVE |
|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 82,315 / 20,229 km2 (91.3%) | 82,315 / 20,229 km2 (91.3%) | 82,315 / 20,229 km2 (91.3%) |
| HISTORICAL_SIGNAL | 1,869 / 463 km2 (2.1%) | 1,869 / 463 km2 (2.1%) | 1,352 / 334 km2 (1.5%) |
| REQUIRES_FLOOD_VERIFICATION | 5,614 / 1,393 km2 (6.3%) | 5,558 / 1,379 km2 (6.2%) | 3,217 / 796 km2 (3.6%) |
| STRONG_FLOOD_SCREENING_CONCERN | 303 / 76 km2 (0.3%) | 359 / 90 km2 (0.4%) | 3,217 / 801 km2 (3.6%) |
| UNRESOLVED | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) |

**Phayao** (cells / area / share)

| flood ladder state | FLOOD_CURRENT_PRIMARY | FLOOD_ANY_SOURCE | FLOOD_UNION_CONSERVATIVE |
|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 16,876 / 4,116 km2 (66.5%) | 16,876 / 4,116 km2 (66.5%) | 16,876 / 4,116 km2 (66.5%) |
| HISTORICAL_SIGNAL | 1,265 / 316 km2 (5.1%) | 1,242 / 310 km2 (5.0%) | 940 / 235 km2 (3.8%) |
| REQUIRES_FLOOD_VERIFICATION | 5,905 / 1,476 km2 (23.8%) | 5,833 / 1,458 km2 (23.5%) | 2,443 / 611 km2 (9.9%) |
| STRONG_FLOOD_SCREENING_CONCERN | 1,142 / 286 km2 (4.6%) | 1,237 / 309 km2 (5.0%) | 4,929 / 1,232 km2 (19.9%) |
| UNRESOLVED | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) |

**Chiang Rai** (cells / area / share)

| flood ladder state | FLOOD_CURRENT_PRIMARY | FLOOD_ANY_SOURCE | FLOOD_UNION_CONSERVATIVE |
|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 30,261 / 7,454 km2 (64.4%) | 30,261 / 7,454 km2 (64.4%) | 30,261 / 7,454 km2 (64.4%) |
| HISTORICAL_SIGNAL | 2,441 / 610 km2 (5.3%) | 2,421 / 605 km2 (5.2%) | 1,802 / 450 km2 (3.9%) |
| REQUIRES_FLOOD_VERIFICATION | 11,190 / 2,794 km2 (24.1%) | 10,142 / 2,533 km2 (21.9%) | 4,797 / 1,197 km2 (10.3%) |
| STRONG_FLOOD_SCREENING_CONCERN | 2,892 / 718 km2 (6.2%) | 3,960 / 984 km2 (8.5%) | 9,924 / 2,475 km2 (21.4%) |
| UNRESOLVED | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) |

Transitions between candidates (flood ladder):

| FLOOD_CURRENT_PRIMARY \ FLOOD_ANY_SOURCE (cells) | NO_MAJOR_OBSERVED_SIGNAL | HISTORICAL_SIGNAL | REQUIRES_FLOOD_VERIFICATION | STRONG_FLOOD_SCREENING_CONCERN |
|---|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 129452 | 0 | 0 | 0 |
| HISTORICAL_SIGNAL | 0 | 5532 | 43 | 0 |
| REQUIRES_FLOOD_VERIFICATION | 0 | 0 | 21490 | 1219 |
| STRONG_FLOOD_SCREENING_CONCERN | 0 | 0 | 0 | 4337 |

| FLOOD_ANY_SOURCE \ FLOOD_UNION_CONSERVATIVE (cells) | NO_MAJOR_OBSERVED_SIGNAL | HISTORICAL_SIGNAL | REQUIRES_FLOOD_VERIFICATION | STRONG_FLOOD_SCREENING_CONCERN |
|---|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 129452 | 0 | 0 | 0 |
| HISTORICAL_SIGNAL | 0 | 4094 | 1438 | 0 |
| REQUIRES_FLOOD_VERIFICATION | 0 | 0 | 9019 | 12514 |
| STRONG_FLOOD_SCREENING_CONCERN | 0 | 0 | 0 | 5556 |

| FLOOD_CURRENT_PRIMARY \ FLOOD_UNION_CONSERVATIVE (cells) | NO_MAJOR_OBSERVED_SIGNAL | HISTORICAL_SIGNAL | REQUIRES_FLOOD_VERIFICATION | STRONG_FLOOD_SCREENING_CONCERN |
|---|---|---|---|---|
| NO_MAJOR_OBSERVED_SIGNAL | 129452 | 0 | 0 | 0 |
| HISTORICAL_SIGNAL | 0 | 4094 | 1481 | 0 |
| REQUIRES_FLOOD_VERIFICATION | 0 | 0 | 8976 | 13733 |
| STRONG_FLOOD_SCREENING_CONCERN | 0 | 0 | 0 | 4337 |

![flood-policy-candidates.png](../../outputs/m1c3-review/flood-policy-candidates.png)

## Rule-family sensitivity (AOI, each rule on its own)

| family | rule | years | cells | area_km2 | share_of_area |
|---|---|---|---|---|---|
| A_RECENT_RECURRENCE | >= 1 yrs @ 0.05 | 2017-2023 | 13712 | 3418.53 | 8.56 |
| B_COMMON_PERIOD_CONSENSUS | >= 1 yrs @ 0.05 | 2011-2016 | 20798 | 5185.36 | 12.99 |
| A_RECENT_RECURRENCE | >= 1 yrs @ 0.1 | 2017-2023 | 11513 | 2869.29 | 7.19 |
| B_COMMON_PERIOD_CONSENSUS | >= 1 yrs @ 0.1 | 2011-2016 | 17588 | 4386.64 | 10.99 |
| A_RECENT_RECURRENCE | >= 1 yrs @ 0.25 | 2017-2023 | 7736 | 1927.91 | 4.83 |
| B_COMMON_PERIOD_CONSENSUS | >= 1 yrs @ 0.25 | 2011-2016 | 11634 | 2902.74 | 7.27 |
| A_RECENT_RECURRENCE | >= 1 yrs @ 0.5 | 2017-2023 | 4130 | 1029.49 | 2.58 |
| B_COMMON_PERIOD_CONSENSUS | >= 1 yrs @ 0.5 | 2011-2016 | 5890 | 1470.51 | 3.68 |
| A_RECENT_RECURRENCE | >= 2 yrs @ 0.05 | 2017-2023 | 5496 | 1368.47 | 3.43 |
| B_COMMON_PERIOD_CONSENSUS | >= 2 yrs @ 0.05 | 2011-2016 | 2293 | 570.05 | 1.43 |
| A_RECENT_RECURRENCE | >= 2 yrs @ 0.1 | 2017-2023 | 4365 | 1086.2 | 2.72 |
| B_COMMON_PERIOD_CONSENSUS | >= 2 yrs @ 0.1 | 2011-2016 | 1756 | 436.65 | 1.09 |
| A_RECENT_RECURRENCE | >= 2 yrs @ 0.25 | 2017-2023 | 2537 | 630.78 | 1.58 |
| B_COMMON_PERIOD_CONSENSUS | >= 2 yrs @ 0.25 | 2011-2016 | 918 | 227.87 | 0.57 |
| A_RECENT_RECURRENCE | >= 2 yrs @ 0.5 | 2017-2023 | 1041 | 259.02 | 0.65 |
| B_COMMON_PERIOD_CONSENSUS | >= 2 yrs @ 0.5 | 2011-2016 | 293 | 72.99 | 0.18 |
| A_RECENT_RECURRENCE | >= 3 yrs @ 0.05 | 2017-2023 | 1317 | 328.47 | 0.82 |
| B_COMMON_PERIOD_CONSENSUS | >= 3 yrs @ 0.05 | 2011-2016 | 260 | 64.1 | 0.16 |
| A_RECENT_RECURRENCE | >= 3 yrs @ 0.1 | 2017-2023 | 1011 | 252.01 | 0.63 |
| B_COMMON_PERIOD_CONSENSUS | >= 3 yrs @ 0.1 | 2011-2016 | 159 | 38.97 | 0.1 |
| A_RECENT_RECURRENCE | >= 3 yrs @ 0.25 | 2017-2023 | 521 | 129.64 | 0.32 |
| B_COMMON_PERIOD_CONSENSUS | >= 3 yrs @ 0.25 | 2011-2016 | 48 | 11.55 | 0.03 |
| A_RECENT_RECURRENCE | >= 3 yrs @ 0.5 | 2017-2023 | 187 | 46.17 | 0.12 |
| B_COMMON_PERIOD_CONSENSUS | >= 3 yrs @ 0.5 | 2011-2016 | 3 | 0.75 | 0.0 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 1 yrs @ 0.01 | 2005-2010 | 26723 | 6668.83 | 16.7 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 1 yrs @ 0.05 | 2005-2010 | 22419 | 5596.41 | 14.02 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 1 yrs @ 0.1 | 2005-2010 | 19458 | 4857.22 | 12.16 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 1 yrs @ 0.25 | 2005-2010 | 13623 | 3400.67 | 8.52 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 1 yrs @ 0.5 | 2005-2010 | 7711 | 1924.71 | 4.82 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 2 yrs @ 0.01 | 2005-2010 | 14583 | 3641.79 | 9.12 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 2 yrs @ 0.05 | 2005-2010 | 11604 | 2897.76 | 7.26 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 2 yrs @ 0.1 | 2005-2010 | 9387 | 2344.21 | 5.87 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 2 yrs @ 0.25 | 2005-2010 | 5386 | 1345.03 | 3.37 |
| C_LEGACY_HISTORICAL_SIGNAL | >= 2 yrs @ 0.5 | 2005-2010 | 2182 | 544.4 | 1.36 |
| D_PRODUCT_DISAGREEMENT | mismatch >= 0.01 in any year | 2011-2016 | 3057 | 759.31 | 1.9 |
| D_PRODUCT_DISAGREEMENT | mismatch >= 0.05 in any year | 2011-2016 | 2653 | 660.17 | 1.65 |
| D_PRODUCT_DISAGREEMENT | mismatch >= 0.1 in any year | 2011-2016 | 2312 | 575.4 | 1.44 |
| D_PRODUCT_DISAGREEMENT | mismatch >= 0.25 in any year | 2011-2016 | 1714 | 426.69 | 1.07 |
| D_PRODUCT_DISAGREEMENT | mismatch >= 0.5 in any year | 2011-2016 | 1054 | 262.59 | 0.66 |

## Residential-lowland sensitivity (slope strata for reporting only)

| stratum | measure | stratum_area_km2 | stratum_share_of_aoi | changed_area_km2 | share_of_stratum_changed | share_of_all_changed_in_stratum | disproportion_ratio |
|---|---|---|---|---|---|---|---|
| ALL | flood_ladder_differs_across_candidates | 39930.3 | 1.0 | 3797.5 | 0.0951 | 1.0 | 1.0 |
| ALL | overall_status_differs_across_flood_candidates:any_profile | 39930.3 | 1.0 | 3733.3 | 0.0935 | 1.0 | 1.0 |
| ALL | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 39930.3 | 1.0 | 9124.0 | 0.2285 | 1.0 | 1.0 |
| LOW_SLOPE_LE_5 | flood_ladder_differs_across_candidates | 6026.2 | 0.1509 | 2877.8 | 0.4776 | 0.7578 | 5.021 |
| LOW_SLOPE_LE_5 | overall_status_differs_across_flood_candidates:any_profile | 6026.2 | 0.1509 | 2875.8 | 0.4772 | 0.7703 | 5.104 |
| LOW_SLOPE_LE_5 | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 6026.2 | 0.1509 | 56.6 | 0.0094 | 0.0062 | 0.041 |
| GENTLE_5_15 | flood_ladder_differs_across_candidates | 5758.2 | 0.1442 | 721.7 | 0.1253 | 0.19 | 1.318 |
| GENTLE_5_15 | overall_status_differs_across_flood_candidates:any_profile | 5758.2 | 0.1442 | 701.2 | 0.1218 | 0.1878 | 1.302 |
| GENTLE_5_15 | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 5758.2 | 0.1442 | 551.3 | 0.0957 | 0.0604 | 0.419 |
| LOW_OR_GENTLE_LE_15 | flood_ladder_differs_across_candidates | 11784.4 | 0.2951 | 3599.5 | 0.3054 | 0.9479 | 3.212 |
| LOW_OR_GENTLE_LE_15 | overall_status_differs_across_flood_candidates:any_profile | 11784.4 | 0.2951 | 3577.0 | 0.3035 | 0.9581 | 3.247 |
| LOW_OR_GENTLE_LE_15 | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 11784.4 | 0.2951 | 607.9 | 0.0516 | 0.0666 | 0.226 |
| STEEP_GT_15 | flood_ladder_differs_across_candidates | 28145.9 | 0.7049 | 198.0 | 0.007 | 0.0521 | 0.074 |
| STEEP_GT_15 | overall_status_differs_across_flood_candidates:any_profile | 28145.9 | 0.7049 | 156.2 | 0.0056 | 0.0419 | 0.059 |
| STEEP_GT_15 | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 28145.9 | 0.7049 | 8516.1 | 0.3026 | 0.9334 | 1.324 |
| UNKNOWN | flood_ladder_differs_across_candidates | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| UNKNOWN | overall_status_differs_across_flood_candidates:any_profile | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| UNKNOWN | overall_status_differs_across_profiles:FLOOD_ANY_SOURCE | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

![policy-sensitive-lowlands.png](../../outputs/m1c3-review/policy-sensitive-lowlands.png)

## Hydrogeomorphic policy matrix (flood policy x profile)

`V021_CURRENT_ONLY_REFERENCE` is the earlier policy 0.2.1 flood rule (current product only, profile-specific thresholds), kept as a reference.

**AOI** (cells / km2)

| flood policy | profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|---|
| V021_CURRENT_ONLY_REFERENCE | CONSERVATIVE | 14,095 / 3,493 | 93,624 / 23,186 | 5,874 / 1,455 | 47,196 / 11,505 | 1,284 / 291 |
| V021_CURRENT_ONLY_REFERENCE | BALANCED | 22,135 / 5,492 | 93,583 / 23,171 | 9,842 / 2,437 | 34,501 / 8,361 | 2,012 / 468 |
| V021_CURRENT_ONLY_REFERENCE | PERMISSIVE | 31,204 / 7,745 | 91,635 / 22,689 | 9,804 / 2,429 | 25,572 / 6,150 | 3,858 / 918 |
| FLOOD_CURRENT_PRIMARY | CONSERVATIVE | 19,371 / 4,810 | 85,073 / 21,067 | 7,983 / 1,979 | 45,595 / 11,108 | 4,051 / 966 |
| FLOOD_CURRENT_PRIMARY | BALANCED | 25,984 / 6,453 | 86,161 / 21,331 | 11,998 / 2,975 | 33,774 / 8,181 | 4,156 / 990 |
| FLOOD_CURRENT_PRIMARY | PERMISSIVE | 32,155 / 7,983 | 87,648 / 21,697 | 12,802 / 3,177 | 25,302 / 6,082 | 4,166 / 991 |
| FLOOD_ANY_SOURCE | CONSERVATIVE | 19,349 / 4,805 | 83,895 / 20,773 | 9,192 / 2,281 | 45,596 / 11,108 | 4,041 / 964 |
| FLOOD_ANY_SOURCE | BALANCED | 25,959 / 6,447 | 84,985 / 21,038 | 13,204 / 3,275 | 33,779 / 8,182 | 4,146 / 988 |
| FLOOD_ANY_SOURCE | PERMISSIVE | 32,128 / 7,976 | 86,469 / 21,403 | 14,018 / 3,480 | 25,302 / 6,082 | 4,156 / 989 |
| FLOOD_UNION_CONSERVATIVE | CONSERVATIVE | 18,828 / 4,675 | 72,506 / 17,929 | 21,648 / 5,390 | 45,606 / 11,110 | 3,485 / 826 |
| FLOOD_UNION_CONSERVATIVE | BALANCED | 25,375 / 6,301 | 73,653 / 18,208 | 25,669 / 6,387 | 33,793 / 8,186 | 3,583 / 848 |
| FLOOD_UNION_CONSERVATIVE | PERMISSIVE | 31,480 / 7,814 | 75,187 / 18,586 | 26,511 / 6,599 | 25,302 / 6,082 | 3,593 / 849 |

**Chiang Mai** (cells / km2)

| flood policy | profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|---|
| V021_CURRENT_ONLY_REFERENCE | CONSERVATIVE | 8,587 / 2,133 | 46,592 / 11,524 | 2,523 / 622 | 31,736 / 7,726 | 663 / 154 |
| V021_CURRENT_ONLY_REFERENCE | BALANCED | 12,924 / 3,213 | 46,968 / 11,611 | 5,033 / 1,247 | 24,114 / 5,836 | 1,062 / 252 |
| V021_CURRENT_ONLY_REFERENCE | PERMISSIVE | 17,269 / 4,293 | 46,708 / 11,549 | 5,814 / 1,439 | 18,390 / 4,420 | 1,920 / 459 |
| FLOOD_CURRENT_PRIMARY | CONSERVATIVE | 10,705 / 2,661 | 43,023 / 10,645 | 2,676 / 661 | 31,585 / 7,688 | 2,112 / 505 |
| FLOOD_CURRENT_PRIMARY | BALANCED | 14,347 / 3,568 | 44,389 / 10,977 | 5,159 / 1,278 | 24,053 / 5,821 | 2,153 / 515 |
| FLOOD_CURRENT_PRIMARY | PERMISSIVE | 17,666 / 4,392 | 45,924 / 11,355 | 5,979 / 1,480 | 18,377 / 4,416 | 2,155 / 516 |
| FLOOD_ANY_SOURCE | CONSERVATIVE | 10,705 / 2,661 | 42,967 / 10,631 | 2,732 / 675 | 31,585 / 7,688 | 2,112 / 505 |
| FLOOD_ANY_SOURCE | BALANCED | 14,347 / 3,568 | 44,333 / 10,963 | 5,215 / 1,292 | 24,053 / 5,821 | 2,153 / 515 |
| FLOOD_ANY_SOURCE | PERMISSIVE | 17,666 / 4,392 | 45,868 / 11,341 | 6,035 / 1,494 | 18,377 / 4,416 | 2,155 / 516 |
| FLOOD_UNION_CONSERVATIVE | CONSERVATIVE | 10,540 / 2,620 | 40,570 / 10,034 | 5,590 / 1,386 | 31,585 / 7,688 | 1,816 / 432 |
| FLOOD_UNION_CONSERVATIVE | BALANCED | 14,174 / 3,525 | 41,947 / 10,369 | 8,073 / 2,003 | 24,053 / 5,821 | 1,854 / 441 |
| FLOOD_UNION_CONSERVATIVE | PERMISSIVE | 17,480 / 4,345 | 43,495 / 10,751 | 8,893 / 2,205 | 18,377 / 4,416 | 1,856 / 442 |

**Phayao** (cells / km2)

| flood policy | profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|---|
| V021_CURRENT_ONLY_REFERENCE | CONSERVATIVE | 3,356 / 832 | 17,071 / 4,222 | 929 / 230 | 3,713 / 880 | 119 / 29 |
| V021_CURRENT_ONLY_REFERENCE | BALANCED | 5,064 / 1,257 | 16,123 / 3,983 | 1,285 / 316 | 2,476 / 579 | 240 / 59 |
| V021_CURRENT_ONLY_REFERENCE | PERMISSIVE | 7,090 / 1,760 | 14,730 / 3,634 | 1,031 / 255 | 1,661 / 377 | 676 / 168 |
| FLOOD_CURRENT_PRIMARY | CONSERVATIVE | 4,798 / 1,193 | 14,992 / 3,703 | 1,500 / 373 | 3,214 / 756 | 684 / 170 |
| FLOOD_CURRENT_PRIMARY | BALANCED | 6,070 / 1,508 | 14,355 / 3,541 | 1,873 / 463 | 2,193 / 508 | 697 / 173 |
| FLOOD_CURRENT_PRIMARY | PERMISSIVE | 7,314 / 1,816 | 13,839 / 3,412 | 1,790 / 445 | 1,545 / 348 | 700 / 174 |
| FLOOD_ANY_SOURCE | CONSERVATIVE | 4,785 / 1,190 | 14,914 / 3,683 | 1,595 / 397 | 3,214 / 756 | 680 / 169 |
| FLOOD_ANY_SOURCE | BALANCED | 6,055 / 1,505 | 14,279 / 3,522 | 1,968 / 487 | 2,193 / 508 | 693 / 172 |
| FLOOD_ANY_SOURCE | PERMISSIVE | 7,297 / 1,812 | 13,765 / 3,393 | 1,885 / 469 | 1,545 / 348 | 696 / 173 |
| FLOOD_UNION_CONSERVATIVE | CONSERVATIVE | 4,639 / 1,153 | 11,474 / 2,823 | 5,277 / 1,317 | 3,216 / 756 | 582 / 145 |
| FLOOD_UNION_CONSERVATIVE | BALANCED | 5,896 / 1,465 | 10,851 / 2,665 | 5,650 / 1,408 | 2,197 / 509 | 594 / 148 |
| FLOOD_UNION_CONSERVATIVE | PERMISSIVE | 7,123 / 1,768 | 10,348 / 2,539 | 5,575 / 1,391 | 1,545 / 348 | 597 / 148 |

**Chiang Rai** (cells / km2)

| flood policy | profile | NO_MAJOR_CONCERN_DETECTED | REQUIRES_VERIFICATION | STRONG_REGIONAL_CONCERN | REGIONAL_DEPRIORITIZE | UNRESOLVED |
|---|---|---|---|---|---|---|
| V021_CURRENT_ONLY_REFERENCE | CONSERVATIVE | 2,152 / 528 | 29,961 / 7,440 | 2,422 / 602 | 11,747 / 2,899 | 502 / 108 |
| V021_CURRENT_ONLY_REFERENCE | BALANCED | 4,147 / 1,022 | 30,492 / 7,576 | 3,524 / 874 | 7,911 / 1,946 | 710 / 157 |
| V021_CURRENT_ONLY_REFERENCE | PERMISSIVE | 6,845 / 1,693 | 30,197 / 7,506 | 2,959 / 735 | 5,521 / 1,352 | 1,262 / 290 |
| FLOOD_CURRENT_PRIMARY | CONSERVATIVE | 3,868 / 957 | 27,058 / 6,720 | 3,807 / 946 | 10,796 / 2,664 | 1,255 / 290 |
| FLOOD_CURRENT_PRIMARY | BALANCED | 5,567 / 1,377 | 27,417 / 6,813 | 4,966 / 1,233 | 7,528 / 1,852 | 1,306 / 301 |
| FLOOD_CURRENT_PRIMARY | PERMISSIVE | 7,175 / 1,775 | 27,885 / 6,930 | 5,033 / 1,251 | 5,380 / 1,317 | 1,311 / 302 |
| FLOOD_ANY_SOURCE | CONSERVATIVE | 3,859 / 954 | 26,014 / 6,460 | 4,865 / 1,209 | 10,797 / 2,664 | 1,249 / 289 |
| FLOOD_ANY_SOURCE | BALANCED | 5,557 / 1,375 | 26,373 / 6,552 | 6,021 / 1,496 | 7,533 / 1,853 | 1,300 / 300 |
| FLOOD_ANY_SOURCE | PERMISSIVE | 7,165 / 1,773 | 26,836 / 6,669 | 6,098 / 1,517 | 5,380 / 1,317 | 1,305 / 301 |
| FLOOD_UNION_CONSERVATIVE | CONSERVATIVE | 3,649 / 902 | 20,462 / 5,072 | 10,781 / 2,688 | 10,805 / 2,666 | 1,087 / 249 |
| FLOOD_UNION_CONSERVATIVE | BALANCED | 5,305 / 1,312 | 20,855 / 5,173 | 11,946 / 2,977 | 7,543 / 1,856 | 1,135 / 259 |
| FLOOD_UNION_CONSERVATIVE | PERMISSIVE | 6,877 / 1,701 | 21,344 / 5,296 | 12,043 / 3,002 | 5,380 / 1,317 | 1,140 / 259 |

Pairwise changed area (km2):

| axis | mean | max |
|---|---|---|
| flood_choice | 2476.2 | 3733.3 |
| profile_choice | 6707.1 | 9125.2 |

![overall-policy-matrix.png](../../outputs/m1c3-review/overall-policy-matrix.png)

## Sensitive regions (flood-source choice changes the outcome under >= 1 profile)

| rank | area_km2 | cells | lon | lat | majority_province | share_low_slope_le_5 | share_low_or_gentle_le_15 | median_elev_m_dsm | share_product_disagreement | share_older_only_evidence | share_recent_evidence | median_observed_years | most_common_ladder_triple_CP_AS_UC | balanced_status_by_candidate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 506.75 | 2027 | 99.77 | 19.549 | Chiang Rai | 0.818 | 0.973 | 410.5 | 0.038 | 0.034 | 0.564 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 2 | 321.25 | 1285 | 99.972 | 19.127 | Phayao | 0.899 | 0.99 | 403.5 | 0.048 | 0.093 | 0.456 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 3 | 258.69 | 1043 | 99.097 | 18.809 | Chiang Mai | 0.968 | 0.999 | 312.9 | 0.004 | 0.032 | 0.844 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 4 | 185.5 | 742 | 100.173 | 19.756 | Chiang Rai | 0.704 | 0.876 | 366.5 | 0.085 | 0.049 | 0.636 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 5 | 162.0 | 648 | 100.321 | 20.072 | Chiang Rai | 0.836 | 0.974 | 357.7 | 0.028 | 0.298 | 0.412 | 3.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 6 | 141.5 | 566 | 100.132 | 19.489 | Phayao | 0.94 | 0.982 | 372.2 | 0.17 | 0.062 | 0.754 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 7 | 137.25 | 549 | 99.924 | 20.246 | Chiang Rai | 0.936 | 0.985 | 387.2 | 0.0 | 0.02 | 0.962 | 5.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 8 | 105.75 | 423 | 100.33 | 19.543 | Phayao | 0.768 | 0.995 | 401.9 | 0.031 | 0.012 | 0.532 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 9 | 91.25 | 365 | 99.512 | 19.288 | Chiang Rai | 0.767 | 0.962 | 557.8 | 0.0 | 0.019 | 0.899 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 10 | 87.0 | 348 | 98.913 | 18.646 | Chiang Mai | 0.98 | 1.0 | 300.2 | 0.0 | 0.083 | 0.011 | 3.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 11 | 72.5 | 290 | 99.196 | 19.374 | Chiang Mai | 0.838 | 0.983 | 440.6 | 0.0 | 0.024 | 0.924 | 5.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 12 | 54.75 | 219 | 99.487 | 19.617 | Chiang Rai | 0.639 | 0.973 | 473.8 | 0.0 | 0.018 | 0.954 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 13 | 53.0 | 212 | 99.952 | 20.401 | Chiang Rai | 1.0 | 1.0 | 378.0 | 0.005 | 0.0 | 0.991 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 14 | 43.25 | 173 | 98.954 | 18.97 | Chiang Mai | 0.78 | 0.988 | 320.1 | 0.0 | 0.092 | 0.532 | 4.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |
| 15 | 33.0 | 132 | 99.995 | 19.47 | Chiang Rai | 0.924 | 0.992 | 379.4 | 0.205 | 0.03 | 0.871 | 5.0 | REQ/REQ/STR | REQUIRES_VERIFICATION / REQUIRES_VERIFICATION / STRONG_REGIONAL_CONCERN |

## Human QA

| gate | status |
|---|---|
| M1A1_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1B_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1C_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C1_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C2_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C3_HUMAN_VISUAL_SIGNOFF | PENDING |

No review of the M1C, M1C.1, M1C.2 or M1C.3 map packs has been reported; none is inferred.

## Files

| File | Bytes |
|---|---:|
| annual-source-ledger-summary.png | 157,210 |
| flood-ledger-summary.parquet | 2,760,827 |
| flood-ledger-summary.parquet.provenance.json | 1,984 |
| flood-policy-candidates.png | 235,845 |
| flood-policy-comparison.csv | 4,610 |
| lowland-policy-sensitivity.csv | 5,493 |
| overall-policy-matrix.png | 788,817 |
| policy-matrix.csv | 21,414 |
| policy-sensitive-lowlands.png | 135,970 |
| policy-sensitive-regions.csv | 4,259 |
| product-disagreement.png | 141,207 |
| recent-vs-historical-flood.png | 282,312 |
| m1c3/flood-ladder-by-stratum.csv | 6,666 |
| m1c3/flood-ledger-long.parquet | 4,907,621 |
| m1c3/flood-policy-transitions.csv | 1,995 |
| m1c3/flood-reason-code-counts.csv | 1,629 |
| m1c3/fusion-statistics.json | 3,213 |
| m1c3/ledger-by-year.csv | 2,037 |
| m1c3/policy-results-long.parquet | 9,723,806 |
| m1c3/policy-transitions.csv | 22,014 |
| m1c3/rule-family-sensitivity.csv | 17,014 |
| m1c3/stability-pairwise-area.csv | 1,296 |
