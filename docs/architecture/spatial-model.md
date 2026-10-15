# Spatial model and CRS strategy

Status: **Provisional for M1** ([ADR-0002](decisions/0002-canonical-crs-utm-47n.md);
datum contract [ADR-0006](decisions/0006-recorded-datum-transformations.md)). Revised in M0.1. Config: [`config/spatial.yaml`](../../config/spatial.yaml).

## 1. Three CRS roles

| Role | CRS | Used for |
|---|---|---|
| **Source CRS** | Whatever the dataset actually uses — recorded, never assumed | Reading raw data; recorded in provenance as `original_crs` |
| **Canonical analysis/storage CRS** | **EPSG:32647 — WGS 84 / UTM zone 47N** (metres) | All processed layers, every distance, area, buffer, slope and grid calculation |
| **Interchange CRS** | EPSG:4326 — WGS 84 geographic | GeoJSON exchange (RFC 7946 requires WGS 84), sanity envelopes, human-readable coordinates |
| **Web display CRS** | EPSG:3857 — Web Mercator | Basemaps / future web map only. **Never** for measurement (area distortion ≈ 1/cos²φ, ~13% at 19.5°N) |

## 2. Why UTM 47N

- UTM zone 47N spans **96°E–102°E**. The validated M1A AOI (COD-AB
  boundaries of Chiang Mai, Chiang Rai and Phayao) spans **98.008°E–100.629°E,
  17.242°N–20.465°N**, entirely inside the zone, so there is no zone-boundary
  splitting.
- EPSG:32647 is therefore an appropriate conformal metric CRS for *regional*
  analysis of this AOI. We deliberately make **no numerical distortion claim**
  (an earlier draft did; it was removed in M0.1 because it had not been
  demonstrated over the AOI). If a calculation ever needs a distortion bound,
  compute it over the AOI (e.g. `pyproj.Proj.get_factors`) and record it.
- It is a standard, widely supported CRS in GDAL/PROJ/QGIS and is commonly
  used by Thai and international datasets for this area.
- It uses the WGS 84 datum, which is what GNSS, OSM and global datasets
  (Copernicus DEM, satellite flood products) use.

Alternatives considered: a custom Lambert/Albers equal-area projection (better
area fidelity, but non-standard and with negligible benefit over this extent);
EPSG:4326 (degrees — wrong units for distance/area); EPSG:3857 (heavy scale
distortion).

## 3. Thai datum hazard: Indian 1975

Thai datasets may use the **Indian 1975** datum (geographic EPSG:4240, UTM 47N
**EPSG:24047**). Its coordinates look like WGS 84 / UTM 47N numbers, so a
mislabelled CRS is not visually obvious. The core issue is not one "offset
size": **a datum change involves choosing a coordinate operation**, and that
choice must never be silent.

### Datum-transformation contract (implemented in `hearthmap.spatial.transform`)

Every normalisation stores a `TransformationRecord` in provenance:

| Field | Meaning |
|---|---|
| `source_crs`, `source_datum` | e.g. `EPSG:24047`, `Indian 1975` |
| `target_crs`, `target_datum` | e.g. `EPSG:32647`, `World Geodetic System 1984 ensemble` |
| `datum_change` | whether a datum transformation (not only a conversion) occurred |
| `operation`, `steps[]` | PROJ operation and each step (`Conversion` / `Transformation`) with authority code |
| `transformation_codes` | e.g. `["EPSG:1812"]` (Indian 1975 to WGS 84 (4)) |
| `accuracy_m` | stated accuracy from the EPSG registry; `None` if unpublished, `0` for pure conversions |
| `candidates`, `selection` | every operation PROJ offered, and whether ours was `only_candidate`, `best_ranked` or `pinned` |
| `proj_pipeline`, `pyproj_version`, `proj_version` | reproducibility |

Rules:

1. **Never assume a source CRS** (`require_explicit_source_crs: true`).
2. Confirm the **datum** from publisher documentation, not only from `.prj`.
3. `hearthmap.spatial.reproject()` refuses any datum change
   (`DatumChangeError`); datum changes must use `reproject_recorded()`.
4. PROJ ranks candidates for the AOI (`area_of_interest`). **Ballpark**
   operations (which skip the datum shift) are refused unless explicitly allowed.
5. An operation can be pinned by authority code (e.g. `pinned="EPSG:1304"`).
6. Observed with pyproj 3.8 / PROJ 9.8 for EPSG:24047 → EPSG:32647 over the AOI:
   EPSG:1812 (stated accuracy 3 m, area "Thailand - onshore"), EPSG:1304 (5 m,
   onshore plus Gulf of Thailand) and a world ballpark offset. Default choice is
   the best-ranked EPSG:1812; a dataset's own documentation should override this
   when it names the transformation used to produce it.
7. Validate every ingested layer against an independent reference before use.

No M1A source required a datum change: all are WGS 84 based (EPSG:4326,
EPSG:3857 or EPSG:32647), so every M1A record has `datum_change: false`.

## 4. Analysis grid

- Default cell size **500 m** (`spatial.yaml: grid.cell_size_m`), configurable.
- Cells are squares in EPSG:32647, **snapped to multiples of the cell size**
  from the CRS origin. Cell ids encode the absolute column/row
  (`G500-E000958-N004102` = easting index 958, northing index 4102), so ids are
  stable across runs and across region subsets for the same CRS + size.
- Cell selection: `intersects` (default; interiors must overlap, edge-touching
  cells excluded) or `centroid_within`; every cell carries `coverage_fraction`.
- Grid resolution must not exceed the resolution of the evidence: a 500 m cell
  coloured by district-level data is still district-level data — confidence and
  `spatial_resolution` in provenance must say so.
- Measured in M1A: **162,073 cells** (157,344 full, 4,729 partial) over the
  39,930.34 km² COD-AB AOI ([m1a-validation-report.md](../research/m1a-validation-report.md)).

### 4.1 Grid / sampling contract

The 500 m grid is a **regional analysis surface**, not the fundamental
resolution of any dataset. Overlays retain metrics such as:

| Metric | Meaning |
|---|---|
| `coverage_fraction` | share of the cell inside the AOI |
| `<layer>_affected_area_fraction` | share of the cell covered by the union of intersecting features |
| `<layer>_max_<value>` | worst (max) attribute among intersecting features, e.g. max flood recurrence |
| mean / percentile / threshold-share | e.g. `elev_mean_m`, `slope_gt15_fraction` from native pixels |
| `dist_<feature>_m` | straight-line distance to the nearest feature |

**Hazard overlays are never designed around centroid sampling alone.** A narrow
but severe hazard (a 10 m channel along a cell edge) appears as
`affected_area_fraction > 0` and in `max_*` even though the centroid misses it
(`hearthmap.spatial.overlay.polygon_cell_metrics`, tested). A fraction of 0
means "no mapped feature", never "no hazard".

### 4.2 Area terminology and invariant (M1A.1)

Never call `cell_count × cell_area` "grid area" when edge cells exist:

| Term | Definition |
|---|---|
| `raw_cell_footprint_area` | n_cells × cell area (includes overhang outside the boundary) |
| `clipped_coverage_area` | Σ cell area × coverage_fraction |
| `boundary_area` | area of the boundary polygon(s) |
| `edge_overhang_area` | raw_cell_footprint_area − clipped_coverage_area |
| `coverage_difference` | clipped_coverage_area − boundary_area |

Invariant: `|coverage_difference| ≤ 1 m² + 1e-9 × boundary_area`
(`hearthmap.qa.coverage_accounting`; the M1A build fails if it is violated).

### 4.3 Boundary uncertainty (M1A.1)

`boundary_uncertainty_review` marks cells intersecting zones where an
independent reference departs from COD-AB by ≥ 250 m (half a cell). It is a
**review layer** (`review_only`, `decision_use = NONE`): overlays refuse it and
scores cannot cite it. It signals caution about a cell's administrative
attribution, never a hazard or restriction. COD-AB remains unchanged.

## 5. Analysis units other than the grid

| Operation | Natural unit |
|---|---|
| Flood/landslide/protected-area overlay | Polygon ∩ cell (area fraction) |
| Distance to river / school / hospital | Point/line features; computed in metres |
| Travel time | Road network (graph), later rasterised to cells |
| Crime/safety, some census data | Administrative area (district/sub-district) — never down-scaled as if precise |
| Slope/elevation | Raster in canonical CRS, summarised per cell (mean/max/percentile) |
| Title, access, buildability | Parcel (M5) |

## 6. Rasters

- Copernicus GLO-30 is distributed in EPSG:4326 with EGM2008 heights (EPSG:3855).
- The M1A terrain preview avoids resampling: slope is computed on the native
  grid with **geodesic pixel spacing** per row, and native pixel centres are
  binned into 500 m cells. Any future raster product in EPSG:32647 must record
  its resampling method in provenance.
- **Slope is never computed in degree units.**
- Rasterio is an optional dependency (`pip install -e ".[raster]"`), added when
  the first raster is ingested.

## 7. Sanity envelope

`config/regions.yaml` contains a deliberately generous lon/lat envelope around
Northern Thailand. It is **not** a boundary; it only catches gross CRS errors
(swapped lat/lon, wrong datum by thousands of km, wrong zone).
