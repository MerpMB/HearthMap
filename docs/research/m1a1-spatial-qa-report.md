# HearthMap M1A.1 — Human spatial QA report

> Committed copy of `outputs/m1a-review/README.md` (images live in the untracked review folder; regenerate with `python scripts/m1a1/build_review.py && python scripts/m1a1/write_readme.py`).

Code version `b8ab73a9a32e6276cf70169918099f8fabee4cea`. **Descriptive QA only** — no boundary was modified, nothing is scored, ranked or excluded. Every review layer carries `review_only = true`, `decision_use = NONE`; overlays refuse such layers and scores cannot cite `review:` sources.

Figures are PNG excerpts readable without QGIS; the optional `hearthmap-m1a-review.gpkg` holds review-only subsets for anyone who wants to pan around.

![overview.png](../../outputs/m1a-review/overview.png)

## 1. Boundary disagreements

Zones = polygon parts of the symmetric difference between COD-AB (PRIMARY, unchanged) and each reference, per province. `max_offset_m` = largest distance from the zone outline to the COD-AB boundary (50 m sampling). A zone is **material** when that offset is ≥ 250 m (half a grid cell: enough to change an edge cell's majority province). `corroboration_fraction` = share of the zone's alternative edge (the reference's own line) lying within 250 m of the *other* reference's line - i.e. whether both references follow the same alternative boundary. Classes are provisional, rule-labelled descriptions, not causes.

- GISTDA 1:50k: **76 material zones, 216.3 km²**; 31 of them (48.9 km²) are corroborated ≥ 50% by geoBoundaries — i.e. both independent references place the line elsewhere than COD-AB.
- geoBoundaries (OSM 2017): **172 material zones, 3490.7 km²**; only 86 zones (83.9 km²) are corroborated by GISTDA. Most of its divergence is unique to geoBoundaries.

GISTDA material-zone area by what lies on the other side of the edge (km²):

| other_side | km2 |
|---|---|
| Mae Hong Son | 85.3 |
| Myanmar/Laos (international) | 66.3 |
| Tak | 31.2 |
| Chiang Rai | 11.6 |
| Chiang Mai | 11.5 |
| Lamphun | 5.5 |
| Lampang | 3.4 |
| Nan | 0.7 |
| Phrae | 0.6 |
| Phayao | 0.1 |

Largest GISTDA zones (full table: `boundary-disagreements.csv`):

| zone_id | province | nearest_district | other_side | border_type | max_offset_m | median_offset_m | symmetric_difference_area_km2 | affected_grid_cells | corroboration_fraction | provisional_class |
|---|---|---|---|---|---|---|---|---|---|---|
| gistda-50k-0001 | TH50 | Mae Ai | Myanmar/Laos (international) | international | 4368 | 2393 | 34.94 | 182 | 0.08 | LIKELY_BORDER_INTERPRETATION |
| gistda-50k-0002 | TH50 | Omkoi | Mae Hong Son | neighbour_province | 3346 | 1827 | 27.49 | 146 | 0.0 | POTENTIALLY_MATERIAL |
| gistda-50k-0003 | TH50 | Omkoi | Tak | neighbour_province | 3773 | 1798 | 26.28 | 138 | 0.0 | POTENTIALLY_MATERIAL |
| gistda-50k-0004 | TH50 | Omkoi | Mae Hong Son | neighbour_province | 2505 | 1852 | 24.77 | 40 | 0.0 | POTENTIALLY_MATERIAL |
| gistda-50k-0005 | TH50 | Chiang Dao | Myanmar/Laos (international) | international | 4724 | 2118 | 17.37 | 98 | 0.64 | LIKELY_BORDER_INTERPRETATION |
| gistda-50k-0006 | TH50 | Hot | Mae Hong Son | neighbour_province | 2029 | 1453 | 10.32 | 64 | 0.0 | POTENTIALLY_MATERIAL |
| gistda-50k-0007 | TH50 | Wiang Haeng | Mae Hong Son | neighbour_province | 1435 | 905 | 7.95 | 58 | 0.12 | POTENTIALLY_MATERIAL |
| gistda-50k-0008 | TH57 | Wiang Pa Pao | Chiang Mai | aoi_internal | 1876 | 1112 | 5.0 | 36 | 0.91 | POTENTIALLY_MATERIAL |
| gistda-50k-0009 | TH50 | Wiang Pa Pao | Chiang Rai | aoi_internal | 1873 | 1115 | 5.0 | 36 | 0.91 | POTENTIALLY_MATERIAL |
| gistda-50k-0010 | TH50 | Wiang Haeng | Mae Hong Son | neighbour_province | 1341 | 369 | 3.9 | 35 | 0.18 | POTENTIALLY_MATERIAL |
| gistda-50k-0011 | TH50 | Wiang Haeng | Mae Hong Son | neighbour_province | 1234 | 462 | 3.74 | 31 | 0.17 | POTENTIALLY_MATERIAL |
| gistda-50k-0012 | TH50 | Omkoi | Tak | neighbour_province | 1467 | 727 | 3.49 | 26 | 0.0 | POTENTIALLY_MATERIAL |

### Chiang Mai

![chiang-mai-boundary-disagreement.png](../../outputs/m1a-review/chiang-mai-boundary-disagreement.png)

The Chiang Mai statistics (p95 offset 1.1 km, max 4.9 km vs GISTDA) come from a small number of **edge blocks**, not from a systematic shift: the median offset stays ~37 m. GISTDA material zones in Chiang Mai, grouped by edge (corroboration = share of the GISTDA line within 250 m of the geoBoundaries line):

| edge | zones | area_km2 | max_offset_km | corroborated (>=50%) | not corroborated |
|---|---|---|---|---|---|
| Border with Mae Hong Son | 16 | 85.3 | 3.3 |  | 0002, 0004, 0006, 0007, 0010, 0011 ... |
| International border (Myanmar) | 9 | 63.8 | 4.7 | 0005, 0013, 0016, 0035, 0040, 0043 ... | 0001, 0014 |
| Border with Tak | 4 | 31.2 | 3.8 |  | 0003, 0012, 0027, 0130 |
| Border with Chiang Rai | 11 | 11.5 | 1.9 | 0009, 0026, 0028, 0039, 0048, 0059 ... | 0032, 0044, 0063, 0075 |
| Border with Lamphun | 8 | 5.5 | 1.1 |  | 0015, 0034, 0037, 0067, 0068, 0098 ... |
| Border with Lampang | 1 | 0.7 | 0.4 | 0036 |  |

The largest disagreement that changes *which AOI province* an area belongs to is on the Chiang Mai / Chiang Rai edge near Wiang Pa Pao (`gistda-50k-0009`, 5.0 km², primary only for Chiang Mai, max offset 1.9 km, corroboration 91%).

No evidence was found to test a *vintage* explanation (no dated boundary editions are available), so no zone is classed LIKELY_SOURCE_VINTAGE_DIFFERENCE.

### Chiang Rai and Phayao

![chiang-rai-boundary-review.png](../../outputs/m1a-review/chiang-rai-boundary-review.png)

![phayao-boundary-review.png](../../outputs/m1a-review/phayao-boundary-review.png)

### Boundary uncertainty mask (`boundary_uncertainty_review`)

| Reference | Cells | Share of AOI cells | Clipped area of affected cells km² | Share of AOI area | Cells by majority province |
|---|---:|---:|---:|---:|---|
| gistda_50k | 1,442 | 0.89% | 277.4 | 0.69% | {'TH50': 1208, 'TH57': 176, 'TH56': 58} |
| geoboundaries | 10,147 | 6.26% | 2151.0 | 5.39% | {'TH50': 6652, 'TH57': 1852, 'TH56': 1643} |
| any_reference | 10,649 | 6.57% | 2265.2 | 5.67% | {'TH50': 7078, 'TH57': 1905, 'TH56': 1666} |

What kind of land the uncertainty cells are (context only, `boundary-uncertainty-context.csv`):

| group | cells | median_elev_mean_m | median_slope_gt15_fraction | share_reserve_ge_0_9 | share_park_gt_0 | median_dist_major_road_m | share_observed_flood_gt_0 |
|---|---|---|---|---|---|---|---|
| AOI (all cells) | 162073 | 650 | 59.2% | 72.3% | 22.3% | 3656 | 21.0% |
| uncertainty cells: geoboundaries | 10147 | 989 | 77.3% | 83.8% | 16.0% | 10122 | 7.3% |
| uncertainty cells: gistda_50k | 1442 | 953 | 70.1% | 84.3% | 23.1% | 3028 | 2.6% |

**Materiality for HearthMap.** The GISTDA-flagged cells (0.9% of the AOI) are mostly steep, high, reserve-covered border terrain that later hazard/legal screening will treat cautiously anyway. They matter where province attribution matters - planning regulation and administrative statistics - e.g. on internal edges such as Wiang Pa Pao (Chiang Mai/Chiang Rai) or Saraphi (Chiang Mai/Lamphun). The mask therefore remains a *caution flag on administrative attribution*, never a hazard input. geoBoundaries is too divergent (and only 2017 OSM) to drive any caution by itself.

## 2. Reserve-forest coverage (actual area, not touched cells)

![forest-coverage-overview.png](../../outputs/m1a-review/forest-coverage-overview.png)

`reserve_area_fraction` = area(RFD reserve ∩ cell ∩ AOI) / area(cell ∩ AOI). RFD reserve polygons cover **30,235 km² = 75.7% of the AOI area**. The distribution is strongly bimodal: most cells are either (almost) fully inside a reserve or not at all; 9.8% of touched cells have a fraction between 0 and 0.9.

| reserve_area_fraction | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| > 0 | 80.2% | 86.9% | 74.4% | 70.4% |
| >= 0.01 | 79.8% | 86.6% | 73.9% | 69.9% |
| >= 0.1 | 78.8% | 85.8% | 72.5% | 68.7% |
| >= 0.25 | 77.7% | 84.9% | 71.0% | 67.5% |
| >= 0.5 | 76.0% | 83.5% | 68.8% | 65.7% |
| >= 0.75 | 74.0% | 81.6% | 66.4% | 63.8% |
| >= 0.9 | 72.3% | 79.8% | 64.8% | 62.2% |

![forest-overlap-examples.png](../../outputs/m1a-review/forest-overlap-examples.png)

### Overlapping legal-screening categories (exact combinations, no double counting)

| combination | area_km2 | share_of_scope |
|---|---|---|
| reserve+park+sanctuary | 0.0 | 0.0% |
| reserve+park | 7254.9 | 18.2% |
| reserve+sanctuary | 2148.0 | 5.4% |
| park+sanctuary | 0.0 | 0.0% |
| reserve | 20832.3 | 52.2% |
| park | 688.8 | 1.7% |
| sanctuary | 63.5 | 0.2% |

Cells (category present with fraction > 0):

| combination | cells | share_of_cells |
|---|---|---|
| reserve | 86,518 | 53.4% |
| reserve+park | 33,305 | 20.5% |
| none | 29,510 | 18.2% |
| reserve+sanctuary | 9,761 | 6.0% |
| park | 2,490 | 1.5% |
| reserve+park+sanctuary | 334 | 0.2% |
| sanctuary | 155 | 0.1% |

Reserve and national-park polygons overlap on 18.2% of the AOI. This is consistent with parks having been declared over reserve land while the RFD 2019 layer still draws both - not verified here. These are descriptive combinations; they must not be summed into a severity score. Rule unchanged: RFD/park/sanctuary geometry is SCREENING / REQUIRES_LEGAL_VERIFICATION and cannot create a definitive exclusion.

## 3. Flood geometry repair audit

![flood-overview.png](../../outputs/m1a-review/flood-overview.png)

- Repaired: **308 of 214,350 features (0.144%)**; reason: {'Ring Self-intersection': 308}.
- Geometry types: {'MultiPolygon -> MultiPolygon': 239, 'Polygon -> Polygon': 69} (no type changes); component count changed for 0; empty after repair: 0.
- |area delta|: median 1.8e-11 m², p95 1.9e-09 m², max 3.7e-08 m² (max 3.7e-13 %). Total 1.6e-13 km².
- Replay vs M1A layer: max area difference 8.2e-08 m².
- Interpretation: every invalidity is a ring touching itself at a single vertex (zero-area self-intersection). `make_valid` only re-expressed topology; **shapes did not materially change**. 'Before' areas are diagnostic (shoelace on invalid rings).

![flood-repair-examples.png](../../outputs/m1a-review/flood-repair-examples.png)

Flood source roles: `flood-gistda-repeated-2005-2016` = TEMPORARY_HISTORICAL_EVIDENCE; `flood-gistda-history` (2011–2023) = metadata_verified, data NOT verified, BLOCKED_CREDENTIAL_REQUIRED, intended PRIMARY_HISTORICAL_FLOOD_EVIDENCE. Catalogue example API keys were not used.

## 4. Grid area accounting

Invariant: Σ(cell area × coverage_fraction) = boundary area within 1 m² + 1e-9 × boundary area.

| scope | n_cells | raw_cell_footprint_area_km2 | clipped_coverage_area_km2 | boundary_area_km2 | edge_overhang_area_km2 | coverage_difference_m2 | tolerance_m2 | invariant_ok |
|---|---|---|---|---|---|---|---|---|
| TH50 | 90332 | 22583.0 | 22159.519971 | 22159.519971 | 423.480029 | -0.0 | 23.0 | True |
| TH56 | 25345 | 6336.25 | 6193.138319 | 6193.138319 | 143.111681 | 0.0 | 7.0 | True |
| TH57 | 47198 | 11799.5 | 11577.678233 | 11577.678233 | 221.821767 | 0.0 | 13.0 | True |
| AOI | 162073 | 40518.25 | 39930.336523 | 39930.336523 | 587.913477 | -0.0 | 41.0 | True |

## 5. Terrain preview QA and the 120 DEM edge cells

![terrain-review.png](../../outputs/m1a-review/terrain-review.png)

Rivers and major roads (OSM, independent) run along DSM valleys in all four windows; no raster offset, striping or tile-seam artifacts are visible at 500 m.

- 120 cells have no DEM pixel centre; all are partial edge cells: coverage ≤ 1.45% (median 0.11%), clipped area ≤ 3,615 m² (median 282 m²), mean width ≤ 18 m; total 0.060 km².
- Cause: pixel centres lie on a ~29 × 31 m lattice; a sliver narrower than that lattice can fall between centres. They were not filled.
- 202 partial cells are smaller than two pixels; 114 of them have none.
- Recommended policy (ADR-0009, proposed): weighted raster overlap with recorded support; UNKNOWN when support < 1 pixel; LOW_SUPPORT flag below ~10 pixels; never nearest-pixel filling for constraints or scores.

## 6. Files

| File | Bytes |
|---|---:|
| boundary-disagreements.csv | 672,892 |
| boundary-uncertainty-context.csv | 379 |
| chiang-mai-boundary-disagreement.png | 250,823 |
| chiang-rai-boundary-review.png | 174,361 |
| dem-edge-cells.csv | 6,200 |
| flood-overview.png | 229,252 |
| flood-repair-audit.csv | 67,094 |
| flood-repair-examples.png | 294,716 |
| forest-category-overlaps.csv | 3,624 |
| forest-coverage-overview.png | 294,321 |
| forest-coverage-summary.csv | 2,612 |
| forest-fraction-histogram.csv | 366 |
| forest-overlap-examples.png | 70,219 |
| hearthmap-m1a-review.gpkg | 65,282,048 |
| overview.png | 245,932 |
| phayao-boundary-review.png | 154,934 |
| qa-summary.json | 25,267 |
| terrain-review.png | 391,905 |

Review GeoPackage layers: province_boundaries, reference_boundaries, boundary_disagreement_zones, boundary_uncertainty_review, forest_review, flood_repair_review, selected_grid_cells (all except province_boundaries are review_only).

