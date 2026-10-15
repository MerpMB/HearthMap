# ADR-0003 — Hard exclusion is separate from suitability scoring

Status: Accepted (M0)

## Context

A weighted sum lets strengths compensate for weaknesses. For some conditions
(floodway, severe landslide susceptibility, protected land, no legal access)
compensation is unacceptable: a good school does not make a floodway habitable.
Data gaps are common, and a gap must not read as "safe".

## Decision

- Stage A evaluates each enabled hard constraint to `PASS`, `FAIL` or `UNKNOWN`.
  Constraints with no supplied evaluation are `UNKNOWN`.
- Any `FAIL` → `EXCLUDED`, `suitability_score = null`, failing results kept as
  `exclusion_reasons`. Never negative points.
- No `FAIL` but some `UNKNOWN` → `UNRESOLVED` (score computed, flagged), or
  `EXCLUDED` under the strict policy `unknown_hard_constraint: exclude`.
- Stage B (weighted suitability) only produces a total for non-excluded units.
- Missing components default to a null total (`missing_component: null_total`).

## Consequences

- Outputs have three statuses; maps must render `UNRESOLVED` distinctly, not
  as eligible.
- Hard-constraint thresholds are a product decision recorded in config, not
  embedded in code.
- Tests assert that an excluded unit never receives a score, even when every
  component is perfect.
