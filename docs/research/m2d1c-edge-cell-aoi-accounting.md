# M2D.1c - edge-cell AOI evidence accounting

> **Updated in M2D.1d** ([m2d1d-edge-origin-context-semantics.md](m2d1d-edge-origin-context-semantics.md)): the AOI-clipped columns are renamed (`*_mass_aoi_clipped`, `*_intensity_per_nominal_grid_cell*`) and routing/distance origins now use AOI analysis points. The unresolved cell share is 42.96%; area, population and built-up shares are unchanged.

Date: 2026-10-16. Branch: `claude/m2d1c-edge-cell-aoi-accounting`. Corrects an accounting issue found by the M2D.1b audit.
No routing policy, user requirement or M1E hazard action changed (tested); routing, travel times and every non-settlement analytical value are byte-identical;
no scoring; Wave 2 not started; `M2D_HUMAN_VISUAL_SIGNOFF` stays PENDING. Grid semantics are defined in [grid-footprint-semantics.md](../architecture/grid-footprint-semantics.md).

## The issue

WorldPop and GHSL values were summed over the **whole** 500 m cell, so an edge cell that only partly covers the AOI also collected population and built-up surface from Nan, Lamphun, Tak, Myanmar and Laos.

## The correction

- **AOI polygon:** the union of the three province boundaries, the same AOI M1A and M1B use; it reproduces the stored `coverage_fraction` exactly (checked on a sample of edge cells, difference 2e-16).
- **Clipping:** a pixel is assigned to the cell holding its centre (unchanged rule); its analytical contribution is its value times the share of the **pixel footprint inside the AOI** (centre-and-corner test, 8 x 8 point lattice for mixed boundary pixels).
  This is not `full-cell value x coverage_fraction`: the dense settlement can sit on either side of the boundary, and the weighting follows the actual pixels. Pixel values are conserved totals, so footprint share is value share under a uniform-within-pixel assumption.
- **Interior cells:** cells fully inside the AOI keep their full-cell value by rule (`coverage_fraction` at least 1 - 1e-9; 157,344 cells, maximum difference 0.0 people and 0.0 m2, tested). The correction touches edge cells only.
- **Columns:** `population_worldpop2025_mass_aoi_clipped` and `built_ghsl2020_m2_aoi_clipped` keep their names with corrected semantics (AOI-clipped; lineage `evidence_footprint = AOI_ANALYTICAL_FOOTPRINT`, `evidence_settlement_footprint` states it).
  The previous sums are kept as `*_full_cell_context` (lineage `FULL_CELL_CONTEXT_ONLY`, `GRID_FOOTPRINT`) and no derived column, map, statistic or QA table uses them except the explicit old-vs-corrected comparisons.
- **Densities and fractions** are still per the nominal 0.25 km2 cell, now with the AOI-clipped numerator, so an edge cell reads lower than the local density of its AOI part. Dividing by the (possibly tiny) footprint area would inflate slivers because pixels are assigned by centre, so I did not.
  Neighbourhood means (1.5 and 2.5 km) of interior cells near the edge shift slightly because their edge neighbours changed.

## AOI totals (`outputs/m2d/tables/aoi-evidence-totals-old-vs-clipped.csv`)

| Quantity | Old: sum of full grid cells (context only) | New: AOI-clipped total | Difference | Difference |
|---|---|---|---|---|
| WorldPop modelled population (MODELLED_POPULATION_ESTIMATE, alpha) | 3,356,000 | **3,341,405** | 14,595 | 0.43% |
| GHSL built-up surface | 333.293 km2 | **330.409 km2** | 2.884 km2 | 0.87% |

A sum of full grid cells is not an AOI total. Closure check: pixel value inside the AOI whose centre lies in no grid cell is 1.4 people and 0 m2.

## Edge cells (`outputs/m2d-review/edge-cell-aoi-accounting.csv`)

4,729 cells have partial AOI coverage; for **1,139** of them the evidence actually changed (the rest hold no populated or built pixels outside the AOI). Together they lost 14,595 modelled people and 2.88 km2 of built-up surface; 679 of them are less than half inside the AOI.
Columns: grid id, AOI coverage fraction, province, district (from the M2D.1b hierarchy), full-cell vs AOI-clipped population and built-up and the amounts removed. No score or rank field.

## The cell that triggered the audit - `G500-E001332-N004224`

| | Full cell (context) | AOI-clipped |
|---|---|---|
| WorldPop modelled population | 294.89 | **27.53** |
| GHSL built-up m2 | 29,205 | **2,704** |
| AOI coverage fraction | | 0.1835 |

About 91% of its modelled population and built-up surface came from the Nan side (81.7% of the cell); only the Phayao / Pong sliver remains. It is no longer the largest unresolved-settlement cell.

## Routing QA recomputed (`routing-coverage-old-vs-aoi-clipped.csv`)

Cell and area shares are unchanged; the corrected population and built-up shares replace the old figures.

| Scope | Unresolved cells | Unresolved area | Unresolved modelled population | Unresolved built-up |
|---|---|---|---|---|
| Chiang Mai | 46.3% | 46.0% | 1.52% (28,597 of 1,879,418) | 0.61% |
| Chiang Rai | 34.2% | 34.0% | 1.82% (20,636 of 1,133,681) | 0.58% |
| Phayao | 47.4% | 46.7% | 1.38% (4,535 of 328,306) | 0.37% |
| **AOI** | **43.0%** | **42.7%** | **1.61% (53,768 of 3,341,405)** | **0.57% (1.89 of 330.4 km2)** |

(The earlier 1.63% and 0.59% were computed on full-cell sums.) Settlement-like unresolved cells: 1,497 (was 1,507), about 22,000 modelled people; 1,222 of them lie 1-2 km from the routable network, 249 lie 2-5 km, 26 lie farther, (111 of the 1,497 sit beside an isolated road fragment).
The conclusion of M2D.1a stands: the gaps are overwhelmingly low-settlement terrain, and no routing change is proposed.

## Other raster and grid evidence audited (`m2d1c-aoi-evidence-audit.csv`; nothing else changed)

| Field | Class |
|---|---|
| WorldPop population (M2D) | AOI_CLIPPED_ALREADY (as of this task; full-cell sum kept as FULL_CELL_CONTEXT_ONLY) |
| GHSL built-up (M2D) | AOI_CLIPPED_ALREADY (as of this task) |
| M1B terrain statistics | AOI_CLIPPED_ALREADY (exact clip of edge cells to their in-AOI part) |
| M1B flood and landslide metrics, M1D seismic metrics | AOI_CLIPPED_ALREADY (clipped to the AOI polygon and `coverage_fraction`; confirmed from code, not re-derived) |
| M1A screening overlays (flood, forest, park area fractions) | POTENTIALLY_AFFECTED: polygon fractions are measured against the full cell, so features outside the AOI in an edge cell count; for separate review |
| M2D OSM road density | POTENTIALLY_AFFECTED: road length of the whole cell over 0.25 km2 |
| M2D OSM service-POI counts and intensity | POTENTIALLY_AFFECTED (low): POIs come from the three provinces, but edge cells count the whole cell |
| M2D OSM industrial and quarry polygon area fractions | POTENTIALLY_AFFECTED: fraction of the nominal cell, no AOI clip |
| M2D Euclidean context counts and nearest distances; M2A routing | NOT_APPLICABLE to aggregation (point-based from the cell centroid, which can lie outside the AOI for edge cells) |
| Tambon context | handled by M2D.1b (administrative label, not evidence aggregation) |

The potentially affected fields are reported for separate review; historical milestone outputs were not changed.
