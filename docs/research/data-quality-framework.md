# Data-quality and interpretation framework

Status: provisional guidance (M0). Applies to sources, derived layers and scores.

## 1. Confidence levels

| Level | Assign to a **source** when… | Assign to a **derived layer/score** when… |
|---|---|---|
| `HIGH` | Authoritative or well-validated; documented method; resolution finer than the analysis unit; recent relative to how fast the phenomenon changes; spot-checks in QGIS matched reality | All inputs `HIGH`; transformation does not add apparent precision |
| `MEDIUM` | Reputable but with known gaps (incomplete coverage, generalised geometry, some age) | Inputs `MEDIUM`+; modest aggregation/down-scaling |
| `LOW` | Coarse, old, partial, crowd-sourced with unknown completeness, or method undocumented | Any input `LOW`, or data painted onto units much finer than its native resolution |
| `UNKNOWN` | Not yet inspected | Inputs missing or unknown — **not** the same as "fine" |

Confidence is a human judgement recorded with a reason (in `known_limitations`
or provenance `limitations`). The code only propagates it (weakest link).

## 2. Quality dimensions to check per source

- **Positional accuracy & datum** — CRS present and correct? Indian 1975 vs WGS 84?
- **Resolution** — native cell size / mapping scale / admin level.
- **Completeness** — does absence of features mean absence in reality?
- **Currency** — data date vs. rate of change (roads change fast, faults don't).
- **Lineage** — who made it, how, from what.
- **Consistency** — classification stable across the three provinces?
- **Legal meaning** — for planning/protected land: is the line legally binding?

## 3. Interpretation rules

### Missing data is not positive data
- "No recorded flood event" ≠ "no flood risk". "No mapped plan" ≠ "residential
  allowed". "No speed tests" ≠ "no internet".
- Missing hard-constraint evaluations produce `UNKNOWN` → `UNRESOLVED`.

### Do not invent precision
- Data keeps its native resolution in reasoning. A province-level statistic
  assigned to 500 m cells is identical for every cell in the province and
  **must not** differentiate between them.
- Record `spatial_resolution` honestly in provenance, e.g. "500 m grid; values
  from district-level statistics".

### Official ≠ accurate or current
- Government datasets get the same scrutiny: record date, completeness, known
  disputes (e.g. contested forest-reserve lines).

### Crime / safety
- Use only at the resolution published (likely province or police-station area).
- Never infer village- or household-level safety; never label communities.
- Recorded crime reflects reporting and policing, not only crime.
- If evidence is too coarse to differentiate candidate areas, leave the
  dimension out of differentiation and say so.

### Land value
- Appreciation is a probabilistic signal with stated assumptions — never a
  forecast, never "will".
- Assessed (official) values and market prices are different quantities.

### Synthetic data
- Synthetic geometry exists only in `tests/`. Anything derived from it is marked
  `synthetic: true` in provenance and must never be shown as real output.

## 4. Minimum acceptance for a processed layer

- [ ] Source registered (id), at least `CANDIDATE`; `VERIFIED` before it drives an exclusion
- [ ] CRS explicit, reprojected to EPSG:32647, datum transformation recorded
- [ ] Geometries valid (or repaired, with a provenance step)
- [ ] Inside the study-area envelope
- [ ] Provenance sidecar written
- [ ] Visually inspected in QGIS against a reference
- [ ] Confidence + limitations recorded
