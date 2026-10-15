# Terrain methods (M1B)

Implements ADR-0009. Code: `hearthmap.terrain.slope`, `hearthmap.terrain.zonal`,
`scripts/m1b/terrain_cells.py`.

## Input

Copernicus DEM GLO-30 (DSM; EPSG:4326 horizontal, EGM2008 heights, 1 arc-second).
The DSM includes tree canopy and buildings: **slope from it is not ground
slope**. Every terrain interpretation states this and carries LOW confidence.

## Slope

| Aspect | Choice |
|---|---|
| Algorithm | Horn (1981) 3×3 finite differences |
| Units | degrees (heights and spacing in metres) |
| Pixel spacing | geodesic ground distances (WGS84 ellipsoid, `pyproj.Geod`): east-west spacing per row (shrinks with latitude), north-south spacing per block (mean) |
| CRS | computed on the native geographic grid with ground spacing — never in degree units, no resampling |
| Nodata | any NaN in the 3×3 window → NaN (no infill); the AOI has no nodata pixels |
| Edges | outermost row/column of an array → NaN; blocks are read with a halo so seams between 1°×1° tiles use true neighbours (fixes the one-sided seam differences of the M1A preview) |
| Smoothing | none |

Verified with synthetic surfaces: flat plane (0°), constant inclines east and
north-east (exact `atan` values), row-varying spacing, nodata neighbourhood.

## Support-aware zonal statistics

* Each pixel is an axis-aligned rectangle in EPSG:32647 (centre transformed
  exactly; half-extents = half the geodesic pixel spacing). The small rotation
  of geographic pixels relative to UTM (meridian convergence < 1° over the AOI)
  is ignored.
* A pixel contributes to every cell it overlaps with weight = overlap share.
* Partial edge cells: weights are clipped exactly (shapely) to the cell's in-AOI
  piece.
* `terrain_support_px` = sum of weights (pixel-equivalents);
  `terrain_support_area_fraction` = weighted pixel area / in-AOI cell area. It
  can exceed 1 by ≈0.1–0.5% because pixel extents are ground metres placed in
  UTM grid metres (scale factor ≈0.9996–1.0002) — documented, not corrected.
* Statistics are weighted (min, max, median, p90, p98, threshold shares).
  Support < 1 pixel → all statistics UNKNOWN (NaN). Support < 10 pixels →
  `terrain_low_support`, confidence capped at LOW.
* `slope_max_raw_deg` is reported but interpretations use `slope_p90_deg`
  (robust against single-pixel canopy/building spikes).
