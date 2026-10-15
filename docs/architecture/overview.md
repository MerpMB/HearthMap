# Architecture overview

Status: M0. Describes what exists now and the intended shape of what comes next.
Decision records live in [decisions/](decisions/).

## 1. Shape of the system

HearthMap is a **local-first analytical pipeline**, not an application server.

```text
 data-source registry (YAML)          config/ (YAML, validated)
            │                                  │
            ▼                                  ▼
 data/raw/<source>/<version>/   ──►  ingestion ──► validation ──► spatial ops
   (untracked, as acquired)          (CRS required,  (CRS, geometry,  (reproject,
                                      checksum,       envelope)        grid, overlay)
                                      SourceReference)                       │
                                                                             ▼
                            data/processed/*.gpkg  + *.provenance.json sidecars
                                                                             │
                                                                             ▼
                      scoring: hard constraints ─► eligibility ─► weighted suitability
                                                                             │
                                                                             ▼
                          outputs/ (GeoPackage for QGIS, text explanations)
```

No frontend, no database server, no cloud. QGIS is the inspection tool.

## 2. Package layout (`src/hearthmap/`)

| Module | Responsibility | M0 state |
|---|---|---|
| `enums.py` | Shared vocabularies: `Confidence`, `VerificationStatus` | Implemented |
| `config/` | Pydantic models + YAML loaders for regions, spatial (CRS/grid), scoring | Implemented |
| `spatial/` | CRS checks/reprojection, geometry validity/repair, bounding boxes, grid generation | Implemented (primitives) |
| `validation/` | Composite layer checks producing a report (CRS, geometry, envelope) | Implemented (minimal) |
| `provenance/` | `ProvenanceRecord`, `SourceReference`, `ProcessingStep`, sidecar I/O, data-source registry model | Implemented |
| `ingestion/` | Read a registered vector source, refuse missing CRS, checksum, emit `SourceReference` | Minimal generic reader only; no source-specific pipelines |
| `scoring/` | Hard-constraint evaluation contract, weighted suitability, explanation rendering | Skeleton: arithmetic + contracts, **no real layer computations** |
| `cli.py` | `hearthmap check-config`, `check-registry`, `make-grid` | Implemented |

Dependencies point one way: `config`, `enums` ← `spatial` ← `validation` /
`ingestion` ← `scoring`/`cli`. `scoring` does not depend on GeoPandas: it
operates on plain per-unit results so it can be fed from grid cells, polygons
or (later) parcels.

## 3. Key contracts

### 3.1 Decision contract

```text
eligible = all enabled hard constraints evaluated and PASS
if any FAIL:          status = EXCLUDED, suitability_score = null, exclusion_reasons = [...]
elif any UNKNOWN:     status = UNRESOLVED (or EXCLUDED under strict policy)
else:                 status = ELIGIBLE, suitability_score = weighted component score
```

Details: [scoring-model-v0.1.md](../product/scoring-model-v0.1.md),
[ADR-0003](decisions/0003-hard-exclusion-separate-from-scoring.md).

### 3.2 Provenance contract

Every processed artifact has a JSON sidecar `<artifact>.provenance.json`
(`hearthmap.provenance.ProvenanceRecord`) recording:

| Field | Meaning |
|---|---|
| `sources[]` | `source_id` (registry id), `source_version`, `source_date`, `acquired_at`, `original_crs`, `local_path`, `checksum_sha256` |
| `normalized_crs` | CRS of the artifact |
| `steps[]` | Ordered transformations: `operation` (reproject, filter, repair, aggregate, calculate, …), description, parameters |
| `method` | Human description of the calculation |
| `spatial_resolution` | Effective resolution (e.g. "500 m grid; inputs at district level") |
| `code_version` | Git commit (suffixed `-dirty` if the working tree had changes) |
| `confidence`, `limitations[]` | Uncertainty carried forward |
| `synthetic` | `true` if any input was synthetic — must never be mistaken for real output |

Sources are referenced by **registry id** so the registry entry (publisher,
licence, date, known limitations) is one lookup away.

### 3.3 Uncertainty contract

Three levels carry a `Confidence` (`HIGH`/`MEDIUM`/`LOW`/`UNKNOWN`):

1. **Source dataset** — registry entry `confidence` (stays `UNKNOWN` until the
   dataset is actually inspected).
2. **Derived layer** — `ProvenanceRecord.confidence`; rule of thumb: no higher
   than the weakest input, downgraded further when the transformation increases
   apparent precision (e.g. district statistic painted onto 500 m cells).
3. **Score** — each `ComponentScore` / `HardConstraintResult` carries confidence;
   an assessment takes the weakest link (ADR-0005).

Guidance for assigning levels: [data-quality-framework.md](../research/data-quality-framework.md).

### 3.4 Explainability

An `Assessment` holds status, total, per-dimension components (value,
confidence, reasons, concerns, source ids), exclusion reasons, unresolved
constraints, coverage and the normalised weights used.
`render_explanation()` turns it into the "CELL / STATUS / TOTAL / WHY /
CONCERNS / SOURCES" text block. Answering *"why does this location have this
score?"* is therefore a lookup, not reverse engineering.

## 4. Storage

M0/M1: **GeoPackage** files under `data/processed/` and `outputs/`
([ADR-0004](decisions/0004-geopackage-storage-for-m0.md)). DuckDB Spatial
may be added for heavy tabular joins; PostGIS when an interactive application
exists (M7).

## 5. What is scaffolding

- `ingestion/` has a generic reader only.
- `scoring/` computes arithmetic over components supplied by the caller; no
  component is computed from real data yet.
- Hard-constraint definitions in config have no thresholds.
- The data-source registry lists candidates; none is verified.
