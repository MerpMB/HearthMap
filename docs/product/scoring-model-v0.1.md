# Scoring model v0.1 (provisional)

Status: **PROVISIONAL.** The structure (two stages, null for excluded, explicit
unknowns) is intended to be stable. The weights, the list of hard constraints
and every threshold are placeholders to be tuned once family requirements and
real datasets exist. Source of truth: [`config/scoring.yaml`](../../config/scoring.yaml).
Implementation: `src/hearthmap/scoring/`.

## 1. Two-stage decision

```text
Stage A — hard constraints                 Stage B — suitability
---------------------------                ---------------------------------
each → PASS / FAIL / FLAG / UNKNOWN        only for units not excluded
any FAIL (definitive) → EXCLUDED, null     weighted mean of 0–100 components
any UNKNOWN or FLAG   → UNRESOLVED         confidence = weakest link
all PASS              → ELIGIBLE           rankable only if complete + ELIGIBLE
```

### Status semantics

| Status | Meaning | `suitability_score` |
|---|---|---|
| `ELIGIBLE` | Every enabled hard constraint was evaluated and passed | Computed (may still be null if components are missing — see §3) |
| `EXCLUDED` | At least one hard constraint failed | **Always null.** Exclusion reasons listed |
| `UNRESOLVED` | No failures, but at least one constraint is `UNKNOWN` or `FLAG`ged (screening / legal-verification evidence) | Computed but provisional; not rankable; unknowns and flags listed |

Policy `unknown_hard_constraint: exclude` (in config) turns `UNRESOLVED` into
`EXCLUDED` for a strict, conservative run.

Exclusions are **never** converted into negative points or low scores. A
hard-constraint failure is a different kind of fact from a weak score.

A hard constraint that receives **no evaluation at all** is treated as
`UNKNOWN` — the engine never assumes a pass.

**M0.1 refinement — definitive vs screening evidence.** `FAIL` now requires
`evidence_class: DEFINITIVE_EXCLUSION` and a constraint configured with
`definitive_exclusion_allowed: true`. Screening or approximate legal evidence
is reported as `FLAG` (`SCREENING_WARNING` / `REQUIRES_LEGAL_VERIFICATION`)
and can never become an exclusion. Strict-policy exclusions are labelled
`exclusion_basis: conservative_policy`. See
[legal-vs-screening.md](legal-vs-screening.md).

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

### 3.1 Ranking comparability (M0.1)

Every assessment exposes `coverage`, `score_basis` (`complete` /
`renormalized` / `none`) and `rankable`. **A score built from fewer dimensions
must not look equivalent to a complete score.** Normal cross-unit ranking
(`ScoringModel.rank`) includes only units that are `ELIGIBLE` with
`score_basis: complete`. Renormalised, incomplete or `UNRESOLVED` scores take
part only when the explicit experimental policy
`allow_incomplete_ranking: true` is set, and each such assessment carries an
`EXPERIMENTAL` note. The repository config keeps it `false`.

## 4. Confidence

Ordered levels `HIGH > MEDIUM > LOW > UNKNOWN`. Overall confidence of an
assessment is the **weakest** confidence among the evidence it depends on:

- `ELIGIBLE` / `UNRESOLVED`: all hard-constraint results + all contributing
  components (an `UNKNOWN` constraint therefore drives confidence to `UNKNOWN`).
- `EXCLUDED`: the failing constraint results (how sure are we that it is
  excluded?).

Weakest-link is deliberately conservative and simple. A weighted or
probabilistic scheme may replace it later (see open questions).

**Future refinement (documented, not implemented):** uncertainty must not stay
collapsed into one enum. It will be separated into:

| Facet | Where it lives today | Question it answers |
|---|---|---|
| Source confidence | registry `confidence` | How good is the dataset itself? |
| Transformation confidence | `TransformationRecord.accuracy_m`, provenance steps | Did normalisation add positional error? |
| Coverage / completeness | `Assessment.coverage`, `score_basis`, overlay fractions | How much of the decision is backed by evidence at all? |
| Decision confidence | `Assessment.confidence` (weakest link) | How far can this status/score be trusted? |

The facets are already stored separately; only the *aggregate* is still a
single weakest-link enum.

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
