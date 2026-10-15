# Requirements v0.1 (provisional)

Status: **PROVISIONAL.** These are the initial requirements as stated at M0.
Precise family requirements (thresholds, distances, priorities) are still to be
defined; see [open-questions.md](../research/open-questions.md).

## R1 — Geographic scope

- R1.1 Initial scope: Chiang Rai, Chiang Mai and Phayao provinces.
- R1.2 Regions are configuration (`config/regions.yaml`) and can be enabled,
  disabled or extended without code changes.
- R1.3 Province geometry must come from an acquired, registered boundary
  dataset. No hand-drawn or fabricated boundaries.

## R2 — Decision outcomes the system must support

| ID | Requirement | Stage |
|---|---|---|
| R2.1 | Low natural-hazard exposure (flood, landslide, slope; seismic context where meaningful) | Exclusion + scoring |
| R2.2 | Good basic utilities (electricity, water, telecom) | Scoring (exclusion only where evidence is reliable) |
| R2.3 | Practical, legally sound road access | Exclusion (no/dubious access) + scoring (quality/travel time) |
| R2.4 | Access to schools and future education options (kindergarten → university/vocational) | Scoring |
| R2.5 | Access to healthcare, incl. emergency care | Scoring |
| R2.6 | Peaceful residential environment (density, nuisance, noise, air quality) | Exclusion (severe nuisance) + scoring |
| R2.7 | Low local safety concerns **only where evidence supports it** | Scoring at evidence resolution only |
| R2.8 | Suitable land-use / planning context | Exclusion (incompatible/protected) + scoring |
| R2.9 | Reasonable access to urban services without living in dense cores | Scoring |
| R2.10 | Long-term value potential, framed probabilistically | Scoring |
| R2.11 | Suitability for raising a family over 20–30 years | Emergent from the above |

## R3 — Decision model

- R3.1 Two stages: hard constraints (exclusion) then weighted suitability.
- R3.2 Excluded units have **no** suitability score (null), plus reasons.
- R3.3 Units with unevaluated hard constraints are `UNRESOLVED`, never silently
  eligible.
- R3.4 Dimension weights are configurable and validated.
- R3.5 Every score carries a confidence level and a list of sources.

## R4 — Explainability and provenance

- R4.1 For any unit, the system can produce status, total, components,
  confidence, positive reasons, concerns and sources.
- R4.2 Every processed artifact is traceable to source dataset/version,
  acquisition time, CRS changes, transformations, method, and code version.

## R5 — Spatial analysis

- R5.1 Regional screening on a configurable grid (default 500 m).
- R5.2 Point, polygon, network, administrative and (later) parcel-level
  operations are supported where they are the right unit; the grid is a
  decision surface, not the only analysis unit.
- R5.3 Distance and area calculations happen in a projected metric CRS.

## R6 — Non-functional

- R6.1 Local-first: runs on a single workstation; no cloud services in M0–M4.
- R6.2 Outputs inspectable in QGIS.
- R6.3 Large/raw data never enters Git.
- R6.4 Tested (pytest) and linted (Ruff).

## R7 — Ethics

- R7.1 No village- or household-level safety inference from coarse statistics.
- R7.2 Land value appreciation never described as certain.
- R7.3 Dataset age and completeness recorded and surfaced.
