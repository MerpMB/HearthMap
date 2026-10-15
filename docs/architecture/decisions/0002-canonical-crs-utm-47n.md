# ADR-0002 — Canonical CRS: WGS 84 / UTM zone 47N (EPSG:32647)

Status: Accepted (M0)

## Context

Distances, areas, buffers, slopes and grid cells must be measured in metres.
The study area (Chiang Mai, Chiang Rai, Phayao; ≈97.3–100.9°E, ≈17–20.5°N)
lies inside UTM zone 47N (96–102°E). Thai sources mix WGS 84, Indian 1975 and
Web Mercator.

## Decision

- Canonical storage and analysis CRS: **EPSG:32647**.
- Interchange: EPSG:4326. Web display: EPSG:3857 (never for measurement).
- Source CRS must be explicit; layers without CRS metadata are rejected.
- Config validation rejects a geographic or Web-Mercator canonical CRS.

## Consequences

- Distance error < 0.05% across the study area; negligible versus data error.
- Extending to provinces east of 102°E (none planned) would leave the zone;
  revisit then.
- Indian 1975 sources (EPSG:24047/4240) need an explicit, recorded datum
  transformation; this is the main CRS risk. See
  [spatial-model.md §3](../spatial-model.md).
