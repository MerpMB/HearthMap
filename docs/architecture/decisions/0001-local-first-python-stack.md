# ADR-0001 — Local-first Python GIS stack, no frontend or server in M0

Status: Accepted (M0)

## Context

The first milestones are analytical: acquire datasets, check them, overlay
them, and judge whether outputs make sense. The audience is one family plus a
builder. Interactive UX is not the bottleneck; data quality and reasoning are.

## Decision

- Python ≥ 3.12, GeoPandas / Shapely 2 / PyProj / pyogrio for vector work.
- Pydantic v2 for configuration and provenance models (validation + JSON
  round-tripping for free).
- Rasterio as an *optional* extra, added when a raster is first ingested.
- pytest + Ruff for quality.
- QGIS as the inspection and human-validation tool.
- **No** web frontend, PostGIS, cloud, auth or deployment in M0.

## Consequences

- Everything runs on one workstation and is reproducible from files.
- An interactive app (M7) will need a storage migration (likely PostGIS) and an
  API; the provenance and scoring models are plain data and should port cleanly.
- Windows is the current development platform; GDAL comes via pyogrio/pyproj
  wheels, avoiding a system GDAL install.
