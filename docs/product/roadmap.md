# Roadmap

Milestones after M0 are **documented, not implemented**. Each milestone must end
with outputs a human has inspected in QGIS and with every layer registered and
provenance-tracked.

## M0 — Foundation (this milestone)

Repository, documentation, configuration, data-source registry, provenance and
confidence model, CRS strategy, grid generator, scoring skeleton, tests.
**Scaffolding only** — no real data, no real scores.

## M0.1 + M1A — Verification gate and geography truth (done)

Foundation corrections (datum contract, legal vs screening evidence, ranking
comparability, area-based overlays) and the first verified/acquired sources
with a validated 500 m grid. No scoring. See
[m1a-validation-report.md](../research/m1a-validation-report.md).

## M1B — Hazard evidence engine v0.1 (done, provisional)

Per-cell hazard evidence (flood observed 2005-2016, DMR landslide susceptibility
and inventory, support-aware DSM terrain, OSM waterway context) with
provisional categorical interpretation, experimental exclusion candidates and
threshold sensitivity. Next: hazard policy review (thresholds, which evidence
may ever become definitive) - blocked on M1A.1 human visual sign-off.

## M1C — Hydrogeomorphic hazard screening policy v0.1 (done, provisional)

Corrected terminology (hazard-specific labels, `HIGH_SCREENING_CONCERN`,
dataset-evaluated vs positive evidence), a regional screening ladder
(`NO_MAJOR_CONCERN_DETECTED` … `REGIONAL_DEPRIORITIZE`, `UNRESOLVED`) with
reason codes and explanations, three sensitivity profiles, fragmentation
diagnostics and the Natural Hazard Resilience scope statement (hydrogeomorphic
only; seismic required before scoring). No profile is selected. Next: human
policy selection, after M1A.1 and M1B visual sign-off. See
[m1c-hazard-policy-report.md](../research/m1c-hazard-policy-report.md).

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
