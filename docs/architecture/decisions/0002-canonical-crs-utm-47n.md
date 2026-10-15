# ADR-0002 — Canonical CRS: WGS 84 / UTM zone 47N (EPSG:32647)

Status: Accepted (M0); revised in M0.1 — provisional analysis CRS

## Context

Distances, areas, buffers, slopes and grid cells must be measured in metres.
The validated AOI (COD-AB: 98.008–100.629°E, 17.242–20.465°N) lies inside
UTM zone 47N (96–102°E). Thai sources mix WGS 84, Indian 1975 and
Web Mercator.

## Decision

- Canonical storage and analysis CRS: **EPSG:32647**.
- Interchange: EPSG:4326. Web display: EPSG:3857 (never for measurement).
- Source CRS must be explicit; layers without CRS metadata are rejected.
- Config validation rejects a geographic or Web-Mercator canonical CRS.

## Consequences

- Appropriate for regional metric analysis because the AOI lies inside UTM
  zone 47N. No numerical distortion bound is claimed (an unverified figure was
  removed in M0.1).
- Extending to provinces east of 102°E (none planned) would leave the zone;
  revisit then.
- Indian 1975 sources (EPSG:24047/4240) need an explicit, recorded datum
  transformation ([ADR-0006](0006-recorded-datum-transformations.md)).
