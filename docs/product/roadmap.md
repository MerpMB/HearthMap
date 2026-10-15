# Roadmap

Milestones after M0 are **documented, not implemented**. Each milestone must end
with outputs a human has inspected in QGIS and with every layer registered and
provenance-tracked.

## M0 — Foundation (this milestone)

Repository, documentation, configuration, data-source registry, provenance and
confidence model, CRS strategy, grid generator, scoring skeleton, tests.
**Scaffolding only** — no real data, no real scores.

## M1 — Regional hazard + infrastructure scan

- Acquire and register: admin boundaries, DEM, flood history/hazard, landslide
  susceptibility, rivers, protected/forest land, main road network.
- Generate the real 500 m grid for the three provinces.
- First real hard constraints (flood, landslide, slope, protected land) with
  explicit thresholds agreed with the family.
- Coarse `hazard_resilience` and road-access components.
- Validate visually in QGIS against known places.

## M2 — Family suitability

Schools (by level), hospitals/emergency care, travel-time accessibility,
livability layers (density, nuisance sources, air-quality context).

## M3 — Growth / value model

Assessed land values, infrastructure catalysts (rail, road upgrades),
urban-expansion indicators. Output is a probabilistic, explained signal.

## M4 — Candidate-zone shortlist

Aggregate eligible, well-scored cells into coherent zones; target ~10–20
serious candidate zones with written rationales and known gaps.

## M5 — Parcel intelligence

Evaluate real parcels/listings inside shortlisted zones only; title type,
access, slope, drainage, utilities at parcel scale.

## M6 — Field verification

Structured on-site inspection checklists (flood marks, neighbours' accounts,
road condition in rainy season, water pressure, noise, smoke/haze season).

## M7 — Interactive HearthMap

Only after analytical usefulness is demonstrated. Likely PostGIS + a web map.
