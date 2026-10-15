# ADR-0006 — Recorded datum transformations

Status: Accepted (M0.1)

## Context

Thai sources mix WGS 84 and legacy Indian 1975 (EPSG:4240 / EPSG:24047). PROJ
offers several Indian 1975 → WGS 84 operations with different stated accuracies
and areas of use, plus a "ballpark" fallback that performs no datum shift.
`GeoDataFrame.to_crs()` picks one silently.

## Decision

- Datum shifts are performed only by PROJ (via pyproj), never hand-coded.
- `hearthmap.spatial.transform.plan_transformation()` lists PROJ's candidates
  for the AOI, refuses ballpark operations by default, honours a pinned
  authority code, and returns a `TransformationRecord` (source/target CRS and
  datum, operation, step authority codes, stated accuracy, candidates,
  selection mode, PROJ pipeline and versions).
- `reproject_recorded()` applies exactly the chosen operation and returns the
  record, which is stored in `ProvenanceRecord.crs_transformations`.
- Plain `reproject()` raises `DatumChangeError` on any datum change.

## Consequences

- Every M1A normalisation carries a transformation record (all were pure
  conversions within WGS 84; `datum_change: false`).
- When a dataset's documentation names the operation used to create it, pin
  that operation instead of accepting PROJ's ranking.
- Grid-based operations (e.g. NTv2) would appear as `unavailable_operations`
  when grids are missing; the planner reports them rather than degrading
  silently.
