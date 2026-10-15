# HearthMap M1C.2 - Flood record reconciliation (GISTDA 2005-2016 vs 2011-2023)

> Committed copy of `outputs/m1c2-review/README.md`; images and tables live in the untracked review folder.

Descriptive reconciliation of two GISTDA observed-flood products. Roles: 2011-2023 = `PRIMARY_CURRENT_PRODUCT`, 2005-2016 = `LEGACY_COMPARISON_PRODUCT`; neither is ground truth. No hazard-policy profile is selected and no policy change is implemented.

Native yearly fields: legacy - year2005..year2016 int32 {0,1}; flood_freq = sum (verified 214,350/214,350); current - y2011..y2023 from detail[].freq int {0,1}; total = sum (verified). Polygons in the AOI: legacy 214,233, current 163,162. Cell-year presence = flooded share >= 1% of the cell (sensitivity below). Province rows use majority-province cell attribution.

## Findings (evidence-supported only)

**Common period 2011–2016.** In 2011, 2012 and 2013 the two products are
geometrically identical within the AOI (intersection/union 1.000 each year;
1,853.6 / 8.7 / 203.3 km2; legacy-only and current-only area < 0.03 km2 per
year). 2015 has no flooding in the AOI in either product. All disagreement
sits in two years:

* **2014** — legacy 236.9 km2, current 38.2 km2; intersection/union 0.16. The
  current 2014 polygons lie inside legacy 2014 polygons (99.97% of current area
  overlapped), but 198.7 km2 of legacy 2014 polygons have no current
  counterpart. Legacy 2014 polygons with zero overlap total 198.6 km2,
  so nearly all of it consists of whole missing features (including all 15
  legacy polygons ≥ 1 km2), not trimmed edges.
* **2016** — legacy 156.3 km2 (Phayao 127.4, Chiang Rai 28.9), current 0 km2
  anywhere in the AOI: the current product has no 2016 flooding in the three
  provinces.

Pooled over the six years: legacy 2,458.8 km2-years, current 2,104.4,
intersection 2,103.7 (IoU 0.855). The current product captures 85.6% of the
legacy area; the legacy product captures 99.97% of the current area. The
legacy product is **not** larger in every year: it is equal in 2011–2013 and
2015, and larger in 2014 and 2016 only.

**Temporal vs product difference.** Of the 6,387 cells flagged in M1C.1 as
"flooded only in the legacy record", **6,281 (98.3%, 1,565 km2)** were flooded
in the legacy product only during 2005–2010 (5,491 of them in 2005), i.e.
outside the current record. Only 106 cells (26.5 km2) have legacy-only
evidence inside 2011–2016 (71 only in 2011–2016, 35 in both periods). The
M1C.1 reduction in observed flooding is therefore mostly **TEMPORAL** (years
2005–2010 are not in the current record), plus a **product difference**
confined to 2014 and 2016.

**Resolution.** Disagreement is not concentrated in edge bands. Among
area-uniform sample points in legacy-only area, 0.1% lie ≤ 20 m and 0.4% lie
≤ 50 m from a same-year current polygon. Another 54% are in a year with no
current polygon at all (2016), and 25% lie > 500 m away. Where both products
report a year they share their geometry exactly, despite the stated 1:50k vs
20 m difference. **Resolution/generalisation cannot plausibly explain the
disagreement.** Whole features and a whole year are absent from the current
product. Why is not documented (see `flood-product-documentation.md`), so the
cause stays **UNEXPLAINED** at the product level.

**Spatial structure.** Common-period disagreement is clustered in the Chiang
Rai / Phayao lowlands. The largest mixed-disagreement area (185 km2) is in
Phayao near 100.03 E, 19.35 N (DSM median elevation 380 m, slope p90 1.4°,
168 m from a major waterway). There, both products agree in 2011–2013 and the
legacy product adds 2014/2016 flooding. The largest legacy-only common-period
cluster is 7 km2 (Chiang Rai, 99.95 E, 19.62 N). Current-only area is
negligible (0.76 km2, 9 cells, Chiang Mai). Lowland/basin context is
descriptive (DSM elevation and slope, waterway distance), not a cause.

**Recurrence.** Using the same six years for both products, area flooded in ≥
2 of 6 years is 292 km2 (legacy) vs 113 km2 (current), and ≥ 3 of 6 is 63 vs
5 km2. The current record's recurrence counts are lowered by the missing 2014
and 2016 features, so recurrence thresholds on the current product alone
measure that product's year coverage as much as flooding.

## Decision gate

1. **Do the products materially disagree for the same years?** Yes for 2014
   (IoU 0.16) and 2016 (current has nothing). No for 2011–2013 (identical).
   Pooled 2011–2016: 355 km2-years legacy-only vs 0.7 km2-years current-only.
2. **Can resolution/generalisation explain most of it?** No. The products
   share geometry where both report, and the disagreement consists of whole
   polygons and a whole year that are missing, mostly far from any
   counterpart.
3. **Is the newer record understood well enough to drive regional policy
   alone?** No. It omits AOI flooding that GISTDA's own legacy product records
   for 2014 and 2016, without documentation. Its 2017–2023 completeness can't
   be checked against another product.
4. **Should legacy-only flooding create a verification flag?** Yes, as
   positive evidence that can only raise concern to verification. This covers
   common-period legacy-only evidence (product disagreement, 106 cells) and
   pre-2011 legacy evidence (temporal, 6,281 cells). The two are kept as
   distinct reasons.
5. **Is a recurrence policy ready to be selected?** No. The record a
   recurrence is counted on must first be defined: the current product alone
   undercounts 2014/2016 relative to the legacy product.

## Recommended evidence policy (not implemented)

**D — annual-union record with per-year provenance, plus legacy verification
reasons.** It is a variant of C that the reconciliation supports:

* For 2011–2013 the products are identical, so a per-year union adds nothing
  and double-counts nothing. For 2014 and 2016 the union keeps the legacy
  features the current product lacks. A 2005–2023 annual record (19 years) is
  formed from legacy 2005–2010, union 2011–2016 and current 2017–2023. Every
  year keeps its source label.
* Recurrence would then be "≥ k of 19 years", re-evaluated with recurrence
  years and cell fraction as separate dimensions (`outputs/m1c2/recurrence-
  sensitivity-current.csv` gives the current-only baseline).
* Separate reason codes: `LEGACY_ONLY_COMMON_PERIOD_FLOOD` (product
  disagreement) and `LEGACY_PRE_2011_FLOOD` (temporal). Both are positive
  evidence only; legacy absence never lowers concern.

Trade-offs:

| Option | For | Against |
|---|---|---|
| A. current only, legacy informational | single documented-access product; simple | discards 2014/2016 features GISTDA itself mapped and all 2005–2010 evidence; undercounts recurrence |
| B. current primary + legacy verification flag | keeps current semantics; legacy can only raise to verification | recurrence still counted on an incomplete record; flags only, no strength |
| C. dual-source union (all years) | maximal recall | the record length and definition become implicit unless per-year provenance is kept |
| **D. per-year union with provenance (recommended)** | uses identical geometry where available, fills the 2014/2016 gaps, a 19-year explicit record, legacy reasons kept distinct | longer record changes threshold meaning again (must be re-reviewed); mixes two undocumented products |


## Annual comparison (same year in both products)

| year | province | legacy_km2 | current_km2 | intersection_km2 | legacy_only_km2 | current_only_km2 | union_km2 | intersection_over_union | legacy_captured_by_current | current_captured_by_legacy |
|---|---|---|---|---|---|---|---|---|---|---|
| 2011 | AOI | 1853.611 | 1854.223 | 1853.587 | 0.024 | 0.636 | 1854.246 | 1.0 | 1.0 | 1.0 |
| 2011 | Chiang Mai | 333.564 | 333.925 | 333.557 | 0.007 | 0.368 | 333.932 | 0.999 | 1.0 | 0.999 |
| 2011 | Phayao | 542.897 | 542.98 | 542.893 | 0.004 | 0.087 | 542.984 | 1.0 | 1.0 | 1.0 |
| 2011 | Chiang Rai | 977.15 | 977.317 | 977.137 | 0.013 | 0.18 | 977.33 | 1.0 | 1.0 | 1.0 |
| 2012 | AOI | 8.653 | 8.655 | 8.652 | 0.001 | 0.003 | 8.656 | 1.0 | 1.0 | 1.0 |
| 2012 | Chiang Mai | 0.11 | 0.11 | 0.11 | 0.0 | 0.0 | 0.11 | 1.0 | 1.0 | 1.0 |
| 2012 | Phayao | 1.203 | 1.203 | 1.203 | 0.0 | 0.0 | 1.203 | 1.0 | 1.0 | 1.0 |
| 2012 | Chiang Rai | 7.339 | 7.342 | 7.339 | 0.001 | 0.003 | 7.342 | 1.0 | 1.0 | 1.0 |
| 2013 | AOI | 203.335 | 203.337 | 203.317 | 0.018 | 0.02 | 203.354 | 1.0 | 1.0 | 1.0 |
| 2013 | Chiang Mai | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2013 | Phayao | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2013 | Chiang Rai | 203.335 | 203.337 | 203.317 | 0.018 | 0.02 | 203.354 | 1.0 | 1.0 | 1.0 |
| 2014 | AOI | 236.855 | 38.203 | 38.186 | 198.669 | 0.017 | 236.872 | 0.161 | 0.161 | 1.0 |
| 2014 | Chiang Mai | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2014 | Phayao | 70.18 | 4.442 | 4.439 | 65.74 | 0.003 | 70.182 | 0.063 | 0.063 | 0.999 |
| 2014 | Chiang Rai | 166.675 | 33.761 | 33.747 | 132.929 | 0.015 | 166.69 | 0.202 | 0.202 | 1.0 |
| 2015 | AOI | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2015 | Chiang Mai | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2015 | Phayao | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2015 | Chiang Rai | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2016 | AOI | 156.337 | 0.0 | 0.0 | 156.337 | 0.0 | 156.337 | 0.0 | 0.0 | nan |
| 2016 | Chiang Mai | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | nan | nan | nan |
| 2016 | Phayao | 127.426 | 0.0 | 0.0 | 127.426 | 0.0 | 127.426 | 0.0 | 0.0 | nan |
| 2016 | Chiang Rai | 28.911 | 0.0 | 0.0 | 28.911 | 0.0 | 28.911 | 0.0 | 0.0 | nan |
| 2011-2016 (area-years) | AOI | 2458.79 | 2104.417 | 2103.742 | 355.048 | 0.675 | 2459.466 | 0.855 | 0.856 | 1.0 |
| 2011-2016 (area-years) | Chiang Mai | 333.674 | 334.035 | 333.667 | 0.007 | 0.368 | 334.042 | 0.999 | 1.0 | 0.999 |
| 2011-2016 (area-years) | Phayao | 741.706 | 548.625 | 548.536 | 193.17 | 0.089 | 741.795 | 0.74 | 0.74 | 1.0 |
| 2011-2016 (area-years) | Chiang Rai | 1383.411 | 1221.757 | 1221.54 | 161.871 | 0.218 | 1383.628 | 0.883 | 0.883 | 1.0 |

![year-by-year-agreement.png](../../outputs/m1c2-review/year-by-year-agreement.png)

Each product on its own years (km2, AOI):

| year | legacy_km2_by_year | current_km2_by_year |
|---|---|---|
| 2005 | 1423.53 |  |
| 2006 | 375.08 |  |
| 2007 | 173.7 |  |
| 2008 | 13.66 |  |
| 2009 | 733.52 |  |
| 2010 | 832.25 |  |
| 2011 | 1853.61 | 1854.22 |
| 2012 | 8.65 | 8.65 |
| 2013 | 203.33 | 203.34 |
| 2014 | 236.85 | 38.2 |
| 2015 | 0.0 | 0.0 |
| 2016 | 156.34 | 0.0 |
| 2017 |  | 1096.26 |
| 2018 |  | 34.59 |
| 2019 |  | 162.63 |
| 2020 |  | 0.0 |
| 2021 |  | 36.07 |
| 2022 |  | 487.0 |
| 2023 |  | 0.0 |

## Per-cell common-period classes (AOI)

| common_period_class | cells | area_km2 |
|---|---|---|
| AGREEMENT_NO_FLOOD | 137408 | 33782.11 |
| AGREEMENT_FLOOD | 22133 | 5517.66 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 294 | 73.5 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 9 | 0.76 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 2229 | 556.31 |

Presence-threshold sensitivity (cells):

| class \ presence threshold | 1e-09 | 0.01 | 0.05 | 0.1 |
|---|---|---|---|---|
| AGREEMENT_NO_FLOOD | 135880 | 137408 | 140901 | 144068 |
| AGREEMENT_FLOOD | 23560 | 22133 | 18754 | 15738 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 2356 | 2229 | 2044 | 1850 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 268 | 294 | 363 | 409 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 9 | 9 | 11 | 8 |

Temporal flags are separate from the common-period class (cells):

| common-period class \ temporal flags | (none) | CURRENT_POST_2016_ONLY | LEGACY_PRE_2011_ONLY | LEGACY_PRE_2011_ONLY|CURRENT_POST_2016_ONLY |
|---|---|---|---|---|
| AGREEMENT_FLOOD | 22133 | 0 | 0 | 0 |
| AGREEMENT_NO_FLOOD | 129452 | 875 | 5628 | 1453 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 7 | 0 | 2 | 0 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 111 | 183 | 0 | 0 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 2229 | 0 | 0 | 0 |

![common-period-agreement.png](../../outputs/m1c2-review/common-period-agreement.png)

![legacy-only-common-period.png](../../outputs/m1c2-review/legacy-only-common-period.png)

![current-only-common-period.png](../../outputs/m1c2-review/current-only-common-period.png)

## The 6,387 legacy-only cells (M1C.1 definition)

| scope | province | breakdown | cells | area_km2 | median_legacy_max_fraction |
|---|---|---|---|---|---|
| AOI | AOI | ONLY_2005_2010 | 6281 | 1565.45 | 0.0443 |
| AOI | AOI | ONLY_2011_2016 | 71 | 17.75 | 0.0574 |
| AOI | AOI | BOTH_2005_2010_AND_2011_2016 | 35 | 8.75 | 0.0995 |
| TH50 | Chiang Mai | ONLY_2005_2010 | 2023 | 501.6 | 0.0362 |
| TH50 | Chiang Mai | ONLY_2011_2016 | 0 | 0.0 | nan |
| TH50 | Chiang Mai | BOTH_2005_2010_AND_2011_2016 | 0 | 0.0 | nan |
| TH56 | Phayao | ONLY_2005_2010 | 1425 | 356.25 | 0.0409 |
| TH56 | Phayao | ONLY_2011_2016 | 54 | 13.5 | 0.0592 |
| TH56 | Phayao | BOTH_2005_2010_AND_2011_2016 | 12 | 3.0 | 0.0774 |
| TH57 | Chiang Rai | ONLY_2005_2010 | 2833 | 707.6 | 0.0528 |
| TH57 | Chiang Rai | ONLY_2011_2016 | 17 | 4.25 | 0.0361 |
| TH57 | Chiang Rai | BOTH_2005_2010_AND_2011_2016 | 23 | 5.75 | 0.1719 |

Legacy-only cells flagged per legacy year: 2005: 5,491, 2006: 143, 2007: 59, 2008: 15, 2009: 716, 2010: 995, 2011: 0, 2012: 0, 2013: 0, 2014: 72, 2015: 0, 2016: 38.

## Spatial disagreement

| class | cells | area_km2 | components | isolated_single_cells | components_lt_1km2 | largest_component_km2 | share_area_in_largest_10 |
|---|---|---|---|---|---|---|---|
| AGREEMENT_FLOOD | 22133 | 5517.66 | 532 | 232 | 371 | 1787.5 | 0.8061 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 294 | 73.5 | 114 | 72 | 98 | 7.0 | 0.4694 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 9 | 0.76 | 6 | 5 | 6 | 0.54 | 1.0 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 2229 | 556.31 | 192 | 74 | 131 | 185.0 | 0.7051 |

| class | rank | area_km2 | cells | lon | lat | majority_province | legacy_flooded_km2_2011_2016_sum | current_flooded_km2_2011_2016_sum | median_elevation_m_dsm | median_slope_p90_deg_dsm | median_dist_major_waterway_m | share_landslide_not_assessed | cell_ids_first_last |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AGREEMENT_FLOOD | 1 | 1787.5 | 7150 | 99.877 | 19.602 | Chiang Rai | 726.36 | 720.07 | 404.0 | 2.9 | 1318.0 | 0.751 | G500-E001220-N004200..G500-E001200-N004445 |
| AGREEMENT_FLOOD | 2 | 880.5 | 3522 | 100.191 | 19.719 | Chiang Rai | 309.77 | 299.0 | 369.4 | 2.2 | 1476.0 | 0.737 | G500-E001250-N004258..G500-E001296-N004460 |
| AGREEMENT_FLOOD | 3 | 447.03 | 1798 | 99.063 | 18.853 | Chiang Mai | 117.64 | 117.79 | 316.9 | 2.7 | 235.0 | 0.883 | G500-E001013-N004127..G500-E000984-N004235 |
| AGREEMENT_FLOOD | 4 | 350.67 | 1427 | 99.972 | 20.319 | Chiang Rai | 144.38 | 141.11 | 376.3 | 1.8 | 696.0 | 0.821 | G500-E001201-N004456..G500-E001200-N004526 |
| AGREEMENT_FLOOD | 5 | 298.25 | 1193 | 100.309 | 19.576 | Phayao | 90.4 | 90.41 | 402.4 | 5.6 | 1448.0 | 0.58 | G500-E001273-N004300..G500-E001278-N004374 |
| AGREEMENT_FLOOD | 6 | 204.18 | 824 | 98.888 | 18.61 | Chiang Mai | 38.83 | 38.85 | 298.7 | 2.4 | 279.0 | 0.908 | G500-E000957-N004080..G500-E000993-N004142 |
| AGREEMENT_FLOOD | 7 | 189.5 | 758 | 99.251 | 19.938 | Chiang Mai | 64.73 | 64.73 | 466.2 | 2.5 | 747.0 | 0.752 | G500-E001026-N004370..G500-E001076-N004434 |
| AGREEMENT_FLOOD | 8 | 124.36 | 498 | 99.512 | 19.282 | Chiang Rai | 46.63 | 46.64 | 563.6 | 3.3 | 465.0 | 0.361 | G500-E001105-N004237..G500-E001106-N004291 |
| AGREEMENT_FLOOD | 9 | 92.5 | 370 | 99.19 | 19.376 | Chiang Mai | 41.11 | 41.12 | 443.3 | 2.9 | 2558.0 | 0.573 | G500-E001038-N004264..G500-E001035-N004300 |
| AGREEMENT_FLOOD | 10 | 73.25 | 293 | 99.991 | 19.496 | Chiang Rai | 13.07 | 12.37 | 382.2 | 1.5 | 892.0 | 0.788 | G500-E001211-N004300..G500-E001205-N004326 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 1 | 7.0 | 28 | 99.947 | 19.62 | Chiang Rai | 3.16 | 0.01 | 390.9 | 2.8 | 21.0 | 0.179 | G500-E001194-N004336..G500-E001200-N004343 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 2 | 6.75 | 27 | 99.921 | 19.652 | Chiang Rai | 4.29 | 0.0 | 392.9 | 7.1 | 2785.0 | 0.259 | G500-E001193-N004342..G500-E001193-N004349 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 3 | 5.25 | 21 | 99.889 | 19.348 | Phayao | 1.9 | 0.0 | 430.7 | 9.2 | 6121.0 | 0.0 | G500-E001185-N004275..G500-E001186-N004282 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 4 | 5.0 | 20 | 100.262 | 19.076 | Phayao | 1.22 | 0.0 | 288.9 | 5.7 | 0.0 | 0.0 | G500-E001262-N004214..G500-E001266-N004223 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 5 | 2.75 | 11 | 100.017 | 19.454 | Chiang Rai | 0.4 | 0.0 | 379.5 | 3.7 | 0.0 | 0.545 | G500-E001212-N004300..G500-E001213-N004306 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 6 | 1.75 | 7 | 100.06 | 19.42 | Phayao | 0.11 | 0.0 | 442.6 | 24.6 | 979.0 | 0.0 | G500-E001221-N004294..G500-E001223-N004296 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 7 | 1.5 | 6 | 99.894 | 19.624 | Chiang Rai | 0.3 | 0.0 | 395.4 | 4.8 | 0.0 | 0.667 | G500-E001186-N004339..G500-E001188-N004341 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 8 | 1.5 | 6 | 100.072 | 19.443 | Phayao | 0.36 | 0.0 | 420.5 | 28.3 | 254.0 | 0.0 | G500-E001223-N004299..G500-E001225-N004302 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 9 | 1.5 | 6 | 100.402 | 19.14 | Phayao | 0.14 | 0.0 | 329.5 | 16.6 | 0.0 | 0.0 | G500-E001293-N004233..G500-E001296-N004234 |
| LEGACY_ONLY_IN_COMMON_PERIOD | 10 | 1.5 | 6 | 99.863 | 19.207 | Phayao | 0.75 | 0.0 | 392.8 | 1.5 | 0.0 | 1.0 | G500-E001181-N004246..G500-E001181-N004249 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 1 | 0.54 | 4 | 99.053 | 18.666 | Chiang Mai | 0.0 | 0.07 | 295.8 | 2.8 | 959.0 | 1.0 | G500-E001010-N004127..G500-E001010-N004128 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 2 | 0.12 | 1 | 98.699 | 18.344 | Chiang Mai | 0.0 | 0.0 | 273.2 | 9.9 | 0.0 | 1.0 | G500-E000936-N004056..G500-E000936-N004056 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 3 | 0.08 | 1 | 99.064 | 18.66 | Chiang Mai | 0.0 | 0.01 | 295.0 | 3.4 | 0.0 | 1.0 | G500-E001013-N004126..G500-E001013-N004126 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 4 | 0.01 | 1 | 98.922 | 18.534 | Chiang Mai | 0.0 | 0.0 | 285.0 | 1.4 | 0.0 | 1.0 | G500-E000983-N004098..G500-E000983-N004098 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 5 | 0.01 | 1 | 98.699 | 18.421 | Chiang Mai | 0.0 | 0.0 | 269.5 | 4.1 | 0.0 | 1.0 | G500-E000936-N004073..G500-E000936-N004073 |
| CURRENT_ONLY_IN_COMMON_PERIOD | 6 | 0.0 | 1 | 99.116 | 18.678 | Chiang Mai | 0.0 | 0.0 | 301.4 | 0.3 | 0.0 | 1.0 | G500-E001024-N004130..G500-E001024-N004130 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 1 | 185.0 | 740 | 100.03 | 19.349 | Phayao | 265.13 | 110.65 | 380.2 | 1.4 | 168.0 | 0.903 | G500-E001199-N004239..G500-E001242-N004323 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 2 | 46.0 | 184 | 99.827 | 19.531 | Chiang Rai | 41.82 | 24.29 | 399.8 | 2.3 | 295.0 | 0.908 | G500-E001164-N004304..G500-E001184-N004342 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 3 | 37.0 | 148 | 100.164 | 19.633 | Chiang Rai | 56.24 | 33.04 | 365.8 | 1.1 | 474.0 | 0.784 | G500-E001242-N004329..G500-E001247-N004352 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 4 | 35.75 | 143 | 99.842 | 19.258 | Phayao | 30.82 | 15.11 | 394.7 | 1.4 | 65.0 | 1.0 | G500-E001179-N004237..G500-E001173-N004277 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 5 | 28.0 | 112 | 100.038 | 20.12 | Chiang Rai | 28.57 | 11.83 | 374.4 | 4.8 | 164.0 | 0.312 | G500-E001208-N004438..G500-E001228-N004460 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 6 | 17.75 | 71 | 99.943 | 19.819 | Chiang Rai | 20.33 | 11.26 | 389.7 | 3.4 | 2067.0 | 0.887 | G500-E001196-N004376..G500-E001198-N004391 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 7 | 17.25 | 69 | 100.181 | 19.576 | Phayao | 18.59 | 10.56 | 367.9 | 0.9 | 175.0 | 0.942 | G500-E001244-N004322..G500-E001247-N004338 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 8 | 10.5 | 42 | 100.279 | 19.138 | Phayao | 6.82 | 3.06 | 295.1 | 4.1 | 0.0 | 0.81 | G500-E001266-N004224..G500-E001270-N004239 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 9 | 7.75 | 31 | 100.273 | 18.98 | Phayao | 3.62 | 1.24 | 269.1 | 4.0 | 0.0 | 0.742 | G500-E001264-N004192..G500-E001270-N004203 |
| MIXED_COMMON_PERIOD_DISAGREEMENT | 10 | 7.25 | 29 | 99.99 | 20.345 | Chiang Rai | 10.57 | 6.58 | 372.4 | 0.9 | 0.0 | 0.69 | G500-E001207-N004496..G500-E001206-N004503 |

![largest-disagreement-regions.png](../../outputs/m1c2-review/largest-disagreement-regions.png)

### Edge vs interior (area-uniform sample points; 179,916 points, seed 20261015)

Distance from disagreement area to the other product's same-year polygon:

| product | band | points | share_of_disagreement |
|---|---|---|---|
| current | <= 20 m | 24 | 100.0 |
| legacy | 100-250 m | 2426 | 6.61 |
| legacy | 20-50 m | 120 | 0.33 |
| legacy | 250-500 m | 4657 | 12.69 |
| legacy | 50-100 m | 446 | 1.22 |
| legacy | <= 20 m | 35 | 0.1 |
| legacy | > 500 m | 9048 | 24.66 |
| legacy | no polygon in other product that year | 19958 | 54.4 |

Disagreement by size of the source polygon:

| product | size_bin | points | share |
|---|---|---|---|
| current | 0.01-0.1 km2 | 10 | 41.7 |
| current | 0.1-1 km2 | 5 | 20.8 |
| current | < 0.01 km2 | 7 | 29.2 |
| current | >= 1 km2 | 2 | 8.3 |
| legacy | 0.01-0.1 km2 | 12671 | 34.5 |
| legacy | 0.1-1 km2 | 14539 | 39.6 |
| legacy | < 0.01 km2 | 4301 | 11.7 |
| legacy | >= 1 km2 | 5179 | 14.1 |

Polygon-level overlap with the other product, same year:

| year | product | size_bin | polygons | area_km2 | polygons_with_no_overlap | area_km2_with_no_overlap | area_weighted_overlap_share |
|---|---|---|---|---|---|---|---|
| 2011 | legacy | < 0.01 km2 | 85928 | 203.05 | 59.0 | 0.01 | 0.9999 |
| 2011 | legacy | 0.01-0.1 km2 | 25695 | 722.48 | 0.0 | 0.0 | 1.0 |
| 2011 | legacy | 0.1-1 km2 | 2947 | 699.9 | 0.0 | 0.0 | 1.0 |
| 2011 | legacy | >= 1 km2 | 130 | 228.2 | 0.0 | 0.0 | 1.0 |
| 2011 | current | < 0.01 km2 | 75806 | 154.12 | 45.0 | 0.06 | 0.9994 |
| 2011 | current | 0.01-0.1 km2 | 23834 | 680.25 | 14.0 | 0.57 | 0.999 |
| 2011 | current | 0.1-1 km2 | 2975 | 728.67 | 1.0 | 0.4 | 0.9992 |
| 2011 | current | >= 1 km2 | 160 | 292.0 | 0.0 | 0.0 | 0.9998 |
| 2012 | legacy | < 0.01 km2 | 1256 | 2.22 | 1.0 | 0.0 | 0.9999 |
| 2012 | legacy | 0.01-0.1 km2 | 179 | 4.71 | 0.0 | 0.0 | 0.9999 |
| 2012 | legacy | 0.1-1 km2 | 11 | 1.72 | 0.0 | 0.0 | 1.0 |
| 2012 | legacy | >= 1 km2 | 0 | 0.0 | 0.0 | 0.0 |  |
| 2012 | current | < 0.01 km2 | 1506 | 2.25 | 1.0 | 0.0 | 0.9992 |
| 2012 | current | 0.01-0.1 km2 | 168 | 4.3 | 0.0 | 0.0 | 0.9998 |
| 2012 | current | 0.1-1 km2 | 14 | 2.1 | 0.0 | 0.0 | 0.9998 |
| 2012 | current | >= 1 km2 | 0 | 0.0 | 0.0 | 0.0 |  |
| 2013 | legacy | < 0.01 km2 | 9359 | 21.66 | 11.0 | 0.0 | 0.9998 |
| 2013 | legacy | 0.01-0.1 km2 | 2911 | 85.02 | 0.0 | 0.0 | 0.9998 |
| 2013 | legacy | 0.1-1 km2 | 348 | 81.74 | 0.0 | 0.0 | 1.0 |
| 2013 | legacy | >= 1 km2 | 11 | 14.92 | 0.0 | 0.0 | 1.0 |
| 2013 | current | < 0.01 km2 | 15566 | 29.65 | 7.0 | 0.0 | 0.9997 |
| 2013 | current | 0.01-0.1 km2 | 3462 | 95.48 | 0.0 | 0.0 | 0.9999 |
| 2013 | current | 0.1-1 km2 | 312 | 68.79 | 0.0 | 0.0 | 1.0 |
| 2013 | current | >= 1 km2 | 7 | 9.4 | 0.0 | 0.0 | 1.0 |
| 2014 | legacy | < 0.01 km2 | 16341 | 32.7 | 10638.0 | 21.13 | 0.3519 |
| 2014 | legacy | 0.01-0.1 km2 | 3202 | 88.42 | 2248.0 | 66.15 | 0.2511 |
| 2014 | legacy | 0.1-1 km2 | 357 | 83.71 | 334.0 | 79.23 | 0.0535 |
| 2014 | legacy | >= 1 km2 | 15 | 32.04 | 15.0 | 32.04 | 0.0 |
| 2014 | current | < 0.01 km2 | 7221 | 12.44 | 0.0 | 0.0 | 0.9997 |
| 2014 | current | 0.01-0.1 km2 | 941 | 22.25 | 0.0 | 0.0 | 0.9994 |
| 2014 | current | 0.1-1 km2 | 20 | 3.51 | 0.0 | 0.0 | 0.9997 |
| 2014 | current | >= 1 km2 | 0 | 0.0 | 0.0 | 0.0 |  |
| 2015 | legacy |  | 0 |  |  |  |  |
| 2015 | current |  | 0 |  |  |  |  |
| 2016 | legacy | < 0.01 km2 | 10057 | 19.7 | 10057.0 | 19.7 | 0.0 |
| 2016 | legacy | 0.01-0.1 km2 | 2017 | 56.31 | 2017.0 | 56.31 | 0.0 |
| 2016 | legacy | 0.1-1 km2 | 264 | 60.72 | 264.0 | 60.72 | 0.0 |
| 2016 | legacy | >= 1 km2 | 9 | 19.6 | 9.0 | 19.6 | 0.0 |
| 2016 | current |  | 0 |  |  |  |  |

## Recurrence review

Same six years for both products (km2 flooded in >= k of 2011-2016):

| min_years_of_6_common | legacy_km2 | current_km2 |
|---|---|---|
| 1 | 2100.79 | 1986.47 |
| 2 | 291.99 | 112.54 |
| 3 | 62.75 | 5.37 |
| 4 | 3.02 | 0.05 |
| 5 | 0.24 | 0.0 |
| 6 | 0.0 | 0.0 |

Current product, full record - years flooded (of 13) x share of cell, kept as separate dimensions (% of AOI area):

| min years flooded (of 13) | >= 0.05 of cell (% AOI) | >= 0.1 of cell (% AOI) | >= 0.25 of cell (% AOI) | >= 0.5 of cell (% AOI) |
|---|---|---|---|---|
| 1 | 14.72 | 12.86 | 9.43 | 5.79 |
| 2 | 6.61 | 5.44 | 3.42 | 1.68 |
| 3 | 2.38 | 1.81 | 1.0 | 0.45 |
| 4 | 0.64 | 0.46 | 0.24 | 0.08 |
| 5 | 0.07 | 0.04 | 0.02 | 0.01 |

## Lowland unresolved semantics (policy 0.2.1)

Policy outputs now carry `hazard_interpretation` (what the assessed hazards say), `data_completeness` and `landslide_assessment_status` (`ASSESSED` / `PARTIALLY_ASSESSED` / `NOT_ASSESSED`) as separate fields, plus `assessed_hazards`. Outside DMR coverage the landslide level reads `NOT_ASSESSED`, never `NONE` or 'low'; flood/terrain interpretation remains available and explanations say so. The `regional_search_status` rule is unchanged.

## Human QA

| gate | status |
|---|---|
| M1A1_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1B_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1C_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C1_HUMAN_VISUAL_SIGNOFF (outputs/m1c1-review) | NOT RECORDED (no review reported) |
| M1C2_HUMAN_VISUAL_SIGNOFF (outputs/m1c2-review) | NOT RECORDED (no review reported) |

## Files

| File | Bytes |
|---|---:|
| annual-comparison.csv | 2,424 |
| common-period-agreement.png | 163,250 |
| common-period-cell-comparison.parquet | 3,622,259 |
| current-only-common-period.png | 82,857 |
| largest-disagreement-regions.csv | 5,154 |
| largest-disagreement-regions.png | 480,060 |
| legacy-only-breakdown.csv | 651 |
| legacy-only-common-period.png | 95,674 |
| reconciliation-summary.json | 11,737 |
| year-by-year-agreement.png | 113,834 |
| m1c2/common-period-classes.csv | 1,052 |
| m1c2/disagreement-by-source-polygon-size.csv | 372 |
| m1c2/disagreement-distance-bands-by-year.csv | 383 |
| m1c2/disagreement-distance-bands.csv | 389 |
| m1c2/example-components.csv | 166,497 |
| m1c2/polygon-overlap-by-size.csv | 1,928 |
| m1c2/recurrence-common-period.csv | 132 |
| m1c2/recurrence-sensitivity-current.csv | 3,081 |
