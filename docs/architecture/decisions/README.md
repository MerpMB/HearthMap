# Architecture decision records

Lightweight ADRs. One file per decision: context, decision, consequences,
status. Superseded decisions are kept and marked, not deleted.

| ADR | Title | Status |
|---|---|---|
| [0001](0001-local-first-python-stack.md) | Local-first Python GIS stack, no frontend or server in M0 | Accepted |
| [0002](0002-canonical-crs-utm-47n.md) | Canonical CRS: WGS 84 / UTM zone 47N (EPSG:32647) | Accepted |
| [0003](0003-hard-exclusion-separate-from-scoring.md) | Hard exclusion is separate from suitability scoring | Accepted |
| [0004](0004-geopackage-storage-for-m0.md) | GeoPackage files as M0/M1 storage | Accepted (provisional) |
| [0005](0005-provenance-sidecars-and-weakest-link-confidence.md) | Provenance sidecars and weakest-link confidence | Accepted (provisional) |
| [0006](0006-recorded-datum-transformations.md) | Recorded datum transformations | Accepted (M0.1) |
| [0007](0007-legal-vs-screening-evidence.md) | Legal truth separate from screening geometry | Accepted (M0.1) |
| [0008](0008-dem-choice-m1.md) | DEM choice for M1 regional terrain screening | Accepted (provisional) |
| [0009](0009-zonal-statistics-for-sparse-edge-cells.md) | Zonal statistics for sparse edge cells | Accepted, implemented for terrain (M1B) |
