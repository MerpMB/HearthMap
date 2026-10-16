# M2D.1d - edge-cell analysis origin and local-vs-external context semantics

Date: 2026-10-16. Branch: `claude/m2d1d-edge-origin-context-semantics`. No routing policy changed (1 km snap, speeds, one-way handling, graph, bands and fingerprint `5c35e98882c3ac62` are frozen and tested),
no user requirement or M1E hazard action changed, no scoring, Wave 2 not started, `M2D_HUMAN_VISUAL_SIGNOFF` stays PENDING. Concepts are defined in [grid-footprint-semantics.md](../architecture/grid-footprint-semantics.md).

## 1. Point semantics

`GRID_CENTROID` is the nominal centre of the 500 m square (kept as `grid_centroid_lon/lat`). `AOI_ANALYSIS_POINT` is the routing and distance origin (`analysis_point_lon/lat`, `analysis_point_method`):

- fully interior cells and edge cells whose centroid lies inside `GRID_FOOTPRINT intersect AOI` keep the centroid (`GRID_CENTROID`);
- other edge cells get the point-on-surface of the clipped footprint (`AOI_REPRESENTATIVE_POINT`): deterministic, inside the footprint, never moved toward roads, services or administrative centres.

**Scope, measured directly** (not assumed equal to the 2,382 administrative fallback cells):

| | Cells |
|---|---|
| Cells | 162,073 (157,344 interior) |
| Partial (edge) cells | 4,729 |
| Partial cells whose centroid is inside the AOI footprint | 2,373 |
| Partial cells whose centroid is outside it | **2,356** |
| Cells whose routing origin changes | **2,356** (interior cells: 0) |
| Cells whose Euclidean-distance origin changes | 2,356 |
| (M2D.1b administrative fallback cells, for comparison) | 2,382 |

The changed-origin cells hold only about 3,966 modelled people (AOI-clipped) and 0.47 km2 of built-up surface.

## 2. Accessibility impact (same frozen routing, nominal centroid vs analysis point; affected cells only)

Route-origin resolution among the 2,356 affected cells: unchanged resolved 782, unchanged unresolved 1,504, **became unresolved 13**, **became resolved 57**. Among cells resolved from both origins the snap distance changes by a median of -131 m.
Service-time impact (`edge-origin-accessibility-impact.csv`; statistics over affected cells only, not whole-AOI medians). For the CORE cluster: 1,822 unchanged, 473 changed but still resolved, 11 became unresolved, 50 became resolved; the median change among changed cells is -0.05 min (10th to 90th percentile -0.45 to +0.20 min).
BROADER and the eight components behave the same (about 1,800-1,840 unchanged, 450-490 changed, 11-12 became unresolved, 50-57 became resolved). Interior cells: every service time and snap distance is identical (0 changed; tested).
Education and healthcare drive times were **not** recomputed: they are produced by the frozen M2A.2 script, which does not reuse this origin helper, so the same 2,356 cells carry nominal-centroid origins there (reported for a separate decision, see section 7).

## 3. Routing QA headline (corrected AOI-clipped evidence and corrected origins)

| | Unresolved cells | Unresolved area | Unresolved modelled population | Unresolved built-up |
|---|---|---|---|---|
| AOI | **42.96%** (was 42.99%) | 42.65% (unchanged) | 1.61% (53,760) | 0.57% |

The change is negligible: 44 more cells are routable, with no change in the area, population or built-up shares at the reported precision. Per province: Chiang Mai 46.3% / 46.0% / 1.52% / 0.61%, Chiang Rai 34.1% / 34.0% / 1.82% / 0.58%, Phayao 47.4% / 46.7% / 1.38% / 0.37% (cells / area / population / built-up).
The CORE and BROADER medians are unchanged (20.52 and 13.43 min among cells routable for both).

## 4. The previously identified cell `G500-E001332-N004224`

| | Old (nominal) | New |
|---|---|---|
| Origin | centroid lon 100.58033, lat 19.09645 (Nan / Tha Wang Pha) | AOI representative point lon 100.58136, lat 19.09771 (Phayao / Pong) |
| Road snap | 10,422 m: unresolved | 10,583 m: unresolved |
| CORE / BROADER / component times | none (unresolved) | none (unresolved) |

The cell stays unresolved (it is 10 km from the routable network from either origin), but the origin is now inside the Phayao part: Nan-origin accessibility no longer stands in for the AOI sliver.
Map: `edge-cell-analysis-origin.png` (overview of interior, valid-edge and replaced origins, plus a zoom on this cell); table: `edge-cell-analysis-origin.csv`.

## 5. Intensity and mass semantics (renames)

| Now | Was | Meaning |
|---|---|---|
| `population_worldpop2025_mass_aoi_clipped` | `..._count_500m` | POPULATION_MASS_AOI_CLIPPED (MODELLED_POPULATION_ESTIMATE) |
| `built_ghsl2020_m2_aoi_clipped` | `..._surface_m2_500m` | BUILT_UP_M2_AOI_CLIPPED |
| `population_worldpop2025_intensity_per_nominal_grid_cell_km2` (+ means) | `..._density_per_km2` | AOI-clipped mass divided by the nominal 0.25 km2 cell |
| `built_ghsl2020_intensity_fraction_of_nominal_grid_cell` (+ means) | `..._fraction_500m` | AOI-clipped m2 over the nominal cell area |
| `*_full_cell_context` | unchanged | CONTEXT_ONLY, whole cell |

Lineage states the denominator ("nominal 0.25 km2 grid cell, NOT the AOI footprint"). No `density within the AOI footprint` field exists, and no `value / tiny sliver area` metric was introduced; if one is ever wanted it must carry support information.

## 6. Disposition of the M2D local and context fields

| Field family | Class | Handling |
|---|---|---|
| Road length and intensity (`road_length_*_aoi_clipped_500m`, `road_intensity_*`) | LOCAL_AOI_EVIDENCE | drivable-road length inside the AOI (edge midpoint rule); `road_length_*_full_cell_context` kept as context. LOCAL_ROAD_CONTEXT is not ROUTING_NETWORK_EXTENT: the routing graph stays unclipped (more than 1,000 nodes lie outside the AOI) so routes can cross borders |
| Service POI counts and intensity (`osm_service_poi_local_*`) | LOCAL_AOI_EVIDENCE (LOCAL_SERVICE_PRESENCE) | only POIs inside the AOI count (one routed POI lies outside the AOI polygon and is excluded from local counts) |
| Service drive times and counts (`drive_time_to_nearest_service_*`, `service_*`) | EXTERNAL_ACCESS_CONTEXT (ACCESSIBLE_SERVICE_DESTINATION) | all OSM POIs of the three provinces are legitimate destinations, including any outside the AOI polygon; destinations across the outer provincial borders (Nan, Lamphun, Tak, Myanmar, Laos) are absent from the extract, so edge-cell times can be overstated |
| Industrial and quarry polygon fractions (`*_polygon_fraction_of_nominal_grid_cell_aoi_clipped`) | LOCAL_AOI_EVIDENCE (LOCAL_POLYGON_OCCUPANCY_AOI_CLIPPED) | polygon intersect AOI; a polygon wholly outside the AOI contributes nothing |
| Industrial/works/quarry euclidean counts, presence and nearest distances; nightlife counts | EXTERNAL_INFLUENCE_CONTEXT | measured from the AOI analysis point; features just outside the AOI may count; no nuisance distance or buffer is activated |
| DIW/DPIM tambon context | administrative context (TAMBON_ADMINISTRATIVE) | unchanged from M2D.1b |
| WorldPop/GHSL mass and intensity | LOCAL_AOI_EVIDENCE | AOI-clipped (M2D.1c) |

No source was blindly clipped to the AOI: external access and influence concepts keep their outside-AOI reach.

## 7. M1A screening-overlay audit (`outputs/m2d/tables/m1a-overlay-edge-audit.csv`; nothing rewritten)

M1A overlay fractions (flood observed, forest reserve, national park, wildlife sanctuary) are measured against the full nominal cell. Among the 4,729 partial cells:

| Layer | Partial cells with the feature in the full cell | Cells affected ONLY by features outside the AOI | Cells whose fraction changes by more than 0.05 on the AOI footprint |
|---|---|---|---|
| flood observed | 241 | 4 | 99 |
| forest reserve | 4,163 | 49 | 1,127 |
| national park | 1,178 | 110 | 589 |
| wildlife sanctuary | 597 | 47 | 158 |

The fields are consumed only by M1A packaging and the M1A.1 spatial-QA statistics and maps; M1B-M1E use their own AOI-clipped metrics and no active decision reads the overlay table (checked by search and tested). Edge-cell dilution can therefore alter M1A.1 QA text for at most a few hundred cells and
no screening state used downstream. **Outcome: DOCUMENTATION_ONLY.** The M1A `dist_major_road_m` and `dist_river_or_canal_m` use the nominal centroid; the same 2,356 cells would have a different origin: also documentation only. M2A education and healthcare drive times carry the same nominal-centroid origin for those cells:
they stay as milestone truth, but a separate M2A re-run on AOI analysis points would be the consistent fix if the owner wants it.
