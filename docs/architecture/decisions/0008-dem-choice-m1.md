# ADR-0008 — DEM choice for M1 regional terrain screening

Status: Accepted (provisional, M1A)

## Context

Terrain (elevation, slope) is needed for screening. Candidates were evaluated
on 2026-10-15 from publisher pages and, for Copernicus, the data itself.

| | Copernicus DEM GLO-30 | FABDEM V1-2 |
|---|---|---|
| Surface | **DSM** (includes canopy, buildings) | Bare-earth estimate (ML removal of forest and buildings from Copernicus DEM) |
| Horizontal | 1 arc-second (~30 m), WGS84-G1150 (EPSG:4326) | ~30 m (1 arc-second), derived from Copernicus |
| Vertical datum | EGM2008 (EPSG:3855) | Inherited from Copernicus (not independently verified) |
| Source age | TanDEM-X acquisitions 2011–2015; AWS bucket = 2021 release (objects dated 2022-05-09) | Derived from Copernicus; V1-2 |
| Licence | Copernicus DEM licence, free for the general public; attribution notice | **CC BY-NC-SA 4.0** (non-commercial, share-alike); commercial use via Fathom |
| Access | **Anonymous HTTPS** from AWS Open Data (verified: tile HEAD/GET without credentials). Copernicus Data Space requires registration | data.bris download |
| Redistribution | Allowed with attribution notice | Share-alike, non-commercial only |

Later Copernicus releases (2022_1–2024_1) changed other regions (Norway,
Spanish Pyrenees, Armenia/Azerbaijan/Moldova, Spain) per the Copernicus Data
Space description; no Thai change was listed, so the AWS 2021 release is
adequate for M1.

## Decision

- **Use Copernicus GLO-30 provisionally** for M1 regional terrain screening,
  always labelled as a DSM.
- **Retain FABDEM as a cross-validation candidate only**; it is *not* a project
  dependency because its non-commercial, share-alike licence could constrain
  future use or sharing of derived outputs. Acquire it only for a bounded
  comparison study, with outputs kept separate.
- No slope suitability score in M1A. Per-cell terrain statistics are an
  *analytical preview* for QA.

## Consequences

- Slope in forested terrain is biased by canopy edges; heights include canopy
  (AOI maximum 2,579.7 m vs Doi Inthanon's ~2,565 m summit).
- A bare-earth check (FABDEM sample, or field/LiDAR where available) is needed
  before any slope threshold becomes a hard constraint.
