# Scoring model v0.1 (provisional)

Status: **PROVISIONAL.** The structure (two stages, null for excluded, explicit
unknowns) is intended to be stable. The weights, the list of hard constraints
and every threshold are placeholders to be tuned once family requirements and
real datasets exist. Source of truth: [`config/scoring.yaml`](../../config/scoring.yaml).
Implementation: `src/hearthmap/scoring/`.

## 1. Two-stage decision

```text
Stage A — hard constraints            Stage B — suitability
---------------------------           ---------------------------------
each constraint → PASS/FAIL/UNKNOWN   only for units not excluded
any FAIL      → EXCLUDED (score=null) weighted mean of 0–100 components
any UNKNOWN   → UNRESOLVED            confidence = weakest link
all PASS      → ELIGIBLE
```

### Status semantics

| Status | Meaning | `suitability_score` |
|---|---|---|
| `ELIGIBLE` | Every enabled hard constraint was evaluated and passed | Computed (may still be null if components are missing — see §3) |
| `EXCLUDED` | At least one hard constraint failed | **Always null.** Exclusion reasons listed |
| `UNRESOLVED` | No failures, but at least one constraint could not be evaluated | Computed but provisional; the unknown constraints are listed as concerns |

Policy `unknown_hard_constraint: exclude` (in config) turns `UNRESOLVED` into
`EXCLUDED` for a strict, conservative run.

Exclusions are **never** converted into negative points or low scores. A
hard-constraint failure is a different kind of fact from a weak score.

A hard constraint that receives **no evaluation at all** is treated as
`UNKNOWN` — the engine never assumes a pass.

## 2. Dimensions and provisional weights

| Dimension id | Label | Weight |
|---|---|---:|
| `hazard_resilience` | Natural hazard resilience | 25 |
| `family_services` | Family / education / healthcare | 20 |
| `infrastructure` | Infrastructure & utilities | 15 |
| `livability` | Livability / peaceful environment | 15 |
| `value_potential` | Long-term value potential | 15 |
| `accessibility` | Accessibility | 10 |

- Weights must be ≥ 0, at least one > 0, ids unique; if `weights_total` is set
  in config the weights must sum to it (catches typos). The engine always
  works with normalised weights (sum = 1).
- Each component score is on 0–100 where 100 = most suitable. How each
  dimension is computed from layers is **not yet defined** (M1–M3).

Note the overlap between *hazard resilience* (scoring) and hazard *exclusions*:
exclusions remove intolerable exposure; the score differentiates among the
tolerable remainder (e.g. distance above flood extents, gentle vs. moderate
slope).

## 3. Missing components

Config `missing_component`:

- `null_total` (default, strict): if any positively-weighted component is
  missing the total is null, with a note naming the missing dimensions.
- `renormalize`: the total is the weighted mean over available components; the
  result reports `coverage` (fraction of total weight available) and is null if
  coverage < `min_component_coverage`. Renormalising implicitly assumes the
  missing dimension is "average of the others" — use it only for exploratory
  runs and always display coverage.

## 4. Confidence

Ordered levels `HIGH > MEDIUM > LOW > UNKNOWN`. Overall confidence of an
assessment is the **weakest** confidence among the evidence it depends on:

- `ELIGIBLE` / `UNRESOLVED`: all hard-constraint results + all contributing
  components (an `UNKNOWN` constraint therefore drives confidence to `UNKNOWN`).
- `EXCLUDED`: the failing constraint results (how sure are we that it is
  excluded?).

Weakest-link is deliberately conservative and simple. A weighted or
probabilistic scheme may replace it later (see open questions).

## 5. Provisional hard constraints

Defined in config as *descriptions*. None has a threshold yet (`rule_defined:
false`); thresholds require real datasets and family decisions.

| id | Intent |
|---|---|
| `flood_unacceptable` | Inside floodway / repeated deep-inundation zone |
| `landslide_severe` | High/very-high landslide susceptibility or recorded event footprint |
| `slope_unsuitable` | Slope too steep for safe, affordable residential construction |
| `protected_or_state_land` | National park, wildlife sanctuary, national forest reserve, watershed class 1–2, other state land |
| `restricted_land_rights` | Land categories that cannot carry secure private title (e.g. ALRO Sor Por Kor) |
| `incompatible_planning` | Planning designation that prohibits residential building |
| `no_legal_access` | No public road access, or access legally dubious |
| `severe_nuisance` | Within a buffer of a severe nuisance source (quarry, landfill, heavy industry) |

## 6. Explanation output (target shape)

`hearthmap.scoring.render_explanation()` produces, per unit:

```text
UNIT: G500-E000958-N004102
STATUS      ELIGIBLE
TOTAL       89.7 / 100
COMPONENTS  ... per dimension, with confidence
CONFIDENCE  MEDIUM
WHY         + positive reasons from components
CONCERNS    - concerns, unknown constraints, missing components
SOURCES     registry ids
```

## 7. Explicitly not in v0.1

- No real component computations. No real scores anywhere.
- No distance-decay functions, travel-time models or thresholds.
- No machine learning, no investment forecasts.
