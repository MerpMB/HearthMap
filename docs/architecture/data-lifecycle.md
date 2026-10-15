# Data lifecycle: RAW → VALIDATED → NORMALIZED → DERIVED

Status: Accepted (M1A).

| Stage | Location | Content | Rules |
|---|---|---|---|
| **RAW** | `data/raw/<source_id>/<version>/` | Files exactly as acquired + `manifest.json` (+ publisher metadata snapshots) | Never modified or overwritten (`download()` refuses). `verify_raw()` re-hashes every artifact before each build. |
| (extracted) | `data/interim/<source_id>/<version>/` | Archive contents (e.g. RAR → shapefile) | Re-creatable from RAW. |
| **VALIDATED** | `data/interim/m1a/validation/*.json` | Statistics, checks, mismatches vs references | Mismatches are recorded, not corrected. A failed gate stops downstream steps. |
| **NORMALIZED** | `data/processed/m1a/*.gpkg` | AOI-filtered layers in EPSG:32647; explicit geometry repair recorded | Each layer has a provenance sidecar in `data/processed/m1a/provenance/` incl. `TransformationRecord`s. |
| **DERIVED** | `data/processed/m1a/grid.gpkg`, `overlays.gpkg`, `dem.gpkg`; `outputs/m1a/` | Grid, overlay metrics, terrain preview, review package | No scores in M1A. |

`manifest.json` (`hearthmap.ingestion.acquire.RawManifest`) records per source:
landing page, licence, publisher metadata captured at acquisition, notes, and
per artifact: original filename, stored path, source URL / endpoint (including
query parameters for API subsets), final URL after redirects, acquisition
timestamp, size, SHA-256, and relevant HTTP headers.

Rebuild order (M1A):

```bash
python scripts/m1a/build_boundaries.py   # validation gate + grid
python scripts/m1a/build_dem.py
python scripts/m1a/build_layers.py
python scripts/m1a/package.py            # outputs/m1a/hearthmap-m1a.gpkg
```
