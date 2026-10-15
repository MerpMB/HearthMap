# Spatial model and CRS strategy

Status: **Decided for M0/M1** ([ADR-0002](decisions/0002-canonical-crs-utm-47n.md)),
with verification items flagged below. Config: [`config/spatial.yaml`](../../config/spatial.yaml).

## 1. Three CRS roles

| Role | CRS | Used for |
|---|---|---|
| **Source CRS** | Whatever the dataset actually uses — recorded, never assumed | Reading raw data; recorded in provenance as `original_crs` |
| **Canonical analysis/storage CRS** | **EPSG:32647 — WGS 84 / UTM zone 47N** (metres) | All processed layers, every distance, area, buffer, slope and grid calculation |
| **Interchange CRS** | EPSG:4326 — WGS 84 geographic | GeoJSON exchange (RFC 7946 requires WGS 84), sanity envelopes, human-readable coordinates |
| **Web display CRS** | EPSG:3857 — Web Mercator | Basemaps / future web map only. **Never** for measurement (area distortion ≈ 1/cos²φ, ~13% at 19.5°N) |

## 2. Why UTM 47N

- UTM zone 47N spans **96°E–102°E** with central meridian **99°E**. Chiang
  Mai, Chiang Rai and Phayao lie roughly between 97.3°E and 100.9°E — entirely
  inside one zone, so no zone-boundary splitting.
- Maximum offset from the central meridian is ≈2°. At ~18–20°N the UTM point
  scale factor ranges ≈0.9996 (at 99°E) to ≈1.0002 (at the study-area edges):
  distance error well under 0.05%, i.e. < 0.5 m per km. Far below the
  uncertainty of any input dataset we expect.
- It is a standard, widely supported CRS in GDAL/PROJ/QGIS and is commonly
  used by Thai and international datasets for this area.
- It uses the WGS 84 datum, which is what GNSS, OSM and global datasets
  (Copernicus DEM, satellite flood products) use.

Alternatives considered: a custom Lambert/Albers equal-area projection (better
area fidelity, but non-standard and with negligible benefit over this extent);
EPSG:4326 (degrees — wrong units for distance/area); EPSG:3857 (heavy scale
distortion).

## 3. Thai datum hazard: Indian 1975

Many Thai government datasets — especially older ones — are published in the
**Indian 1975** datum (geographic EPSG:4240, UTM 47N **EPSG:24047**). Coordinates
look almost identical to WGS 84 / UTM 47N numbers but are offset by a datum
shift on the order of **hundreds of metres**. Mislabelling one as the other
silently misplaces every feature by more than one grid cell.

Rules:

1. **Never assume a source CRS.** `spatial.yaml: require_explicit_source_crs:
   true`; ingestion refuses layers without CRS metadata.
2. When a source's `.prj`/metadata says UTM 47N, confirm the **datum**
   (WGS 84 vs. Indian 1975) from the publisher's documentation and record it
   in the registry.
3. Indian 1975 → WGS 84 transformations exist in several variants with
   different accuracies. Record which PROJ pipeline was used in the provenance
   step `parameters` (verification item: identify the most appropriate
   transformation for Northern Thailand before M1 ingestion).
4. Validate every ingested layer against a known reference (e.g. overlay on
   OSM roads or imagery in QGIS) before use.

## 4. Analysis grid

- Default cell size **500 m** (`spatial.yaml: grid.cell_size_m`), configurable.
- Cells are squares in EPSG:32647, **snapped to multiples of the cell size**
  from the CRS origin. Cell ids encode the absolute column/row
  (`G500-E000958-N004102` = easting index 958, northing index 4102), so ids are
  stable across runs and across region subsets for the same CRS + size.
- Cell selection: `intersects` (default, keeps edge cells) or
  `centroid_within`; edge cells carry `coverage_fraction`.
- Grid resolution must not exceed the resolution of the evidence: a 500 m cell
  coloured by district-level data is still district-level data — confidence and
  `spatial_resolution` in provenance must say so.
- Rough size: the three provinces cover on the order of 40,000 km² → on the order
  of 150,000–170,000 cells at 500 m (to be measured once real boundaries are
  acquired).

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

- DEMs (e.g. Copernicus GLO-30) are typically distributed in EPSG:4326.
  Reproject once to EPSG:32647 at a resolution close to native (~30 m), with
  bilinear resampling for continuous values, before deriving slope.
- **Slope must be computed on a projected DEM** (or with proper geodesic cell
  sizes); computing slope directly on a degree-grid DEM is a classic error.
- Rasterio is an optional dependency (`pip install -e ".[raster]"`), added when
  the first raster is ingested.

## 7. Sanity envelope

`config/regions.yaml` contains a deliberately generous lon/lat envelope around
Northern Thailand. It is **not** a boundary; it only catches gross CRS errors
(swapped lat/lon, wrong datum by thousands of km, wrong zone).
