# ADR-0004 — GeoPackage files as M0/M1 storage

Status: Accepted (provisional — revisit at M2)

## Context

Options: GeoPackage files, DuckDB + Spatial extension, GeoParquet, PostGIS.

## Decision

Use **GeoPackage** for processed vector layers and outputs in M0/M1.

- Single-file, OGC standard, opens directly in QGIS (primary validation tool).
- Read/write via pyogrio with no extra service.
- Supports multiple layers and attribute indexes; adequate for ~10⁵–10⁶ cells.

DuckDB Spatial is not adopted yet: its strengths (fast SQL over large tables,
Parquet) are not needed until many layers are joined per cell. It can be added
without changing the provenance or scoring contracts. PostGIS waits for M7.

## Consequences

- Each artifact gets a sidecar `<file>.provenance.json` (GeoPackage metadata
  tables were considered, but sidecars are format-agnostic and diffable).
- If per-cell multi-layer joins become slow, add DuckDB or GeoParquet for
  intermediate tables.
