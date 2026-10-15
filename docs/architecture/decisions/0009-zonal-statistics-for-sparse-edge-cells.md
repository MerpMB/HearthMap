# ADR-0009 — Zonal statistics for sparse edge cells

Status: Accepted (M1B) - implemented in `hearthmap.terrain.zonal` and used for all
M1B terrain indicators. Not applied to any suitability or constraint.

## Context

The M1A terrain preview bins native DEM pixel *centres* into 500 m cells. 120
of 162,073 cells received no pixel centre. M1A.1 showed they are all partial
edge cells whose in-AOI part is a sliver: coverage fraction ≤ 1.45%
(median 0.11%), clipped area ≤ 3,615 m² (median 282 m²), mean width ≤ 18 m —
narrower than the ~30 m (1 arc-second) pixel spacing. Total area is
0.06 km². Another 88 partial cells have a clipped area below two pixels yet
received at least one pixel centre - their statistics rest on one or two
pixels.

Options considered:

| Option | Assessment |
|---|---|
| Pixel-centre binning (current preview) | Simple, unbiased for full cells; leaves slivers empty; 1–2-pixel cells are statistically fragile |
| Nearest valid pixel | Fills every cell but invents a value from outside the cell; hides the sparsity; unacceptable for hazard/constraint inputs |
| Weighted raster overlap (fraction of each pixel inside the clipped cell) | Uses all evidence touching the cell, exact for partial cells; slightly more compute |
| Retain UNKNOWN | Honest; must be combined with a minimum-support rule |

## Decision (proposed)

1. Future zonal statistics use **weighted raster overlap** (pixel weights =
   area of the pixel inside the cell ∩ AOI).
2. Every zonal metric carries its **support**: effective pixel count
   (sum of weights) and clipped cell area.
3. If support is below **1 pixel** (sum of weights < 1), the metric is
   **UNKNOWN** — never filled from a nearest pixel.
4. Metrics with support below a configurable minimum (proposed 10 pixels)
   are flagged `LOW_SUPPORT` and their confidence is capped at LOW.
5. Nearest-pixel filling is permitted only for visual previews, never for
   constraints or scores.

## Consequences

- No silent filling; sliver cells stay visibly unknown.
- Hazard-relevant extremes (max slope) remain area-weighted at boundaries.
- Requires a weighted zonal routine (e.g. exact-extract style) when terrain
  metrics are first used in M1B or later.
