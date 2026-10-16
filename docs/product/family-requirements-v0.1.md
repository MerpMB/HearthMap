# Family requirements v0.1 (M2B.0)

Status: **calibration contract only.** Config: [`config/family-requirements.yaml`](../../config/family-requirements.yaml) (what the family wants),
[`config/family-evidence-capability.yaml`](../../config/family-evidence-capability.yaml) (what current evidence can evaluate); code:
`hearthmap.family.requirements`; matrix: `outputs/m2b0/requirement-evidence-matrix.csv` (`python scripts/m2b0/build_matrix.py`).
**No cell is scored, no province is ranked, no recommendation exists.** Input passes 1 and 2 (below) have populated the explicit decisions so far; M2B.0 ends `READY_FOR_NEXT_USER_REQUIREMENT_INPUT`.

## Project state

```yaml
family_infrastructure_evidence:
  healthcare: adequate_for_calibration
  education: partial_and_stale
  routing: adequate_for_calibration
requirement_calibration: {allowed: true}
family_suitability_scoring: {allowed: false}
reason: current education register remains incomplete
```

Calibration is allowed because requirements are **user preferences, not derived geographic facts**: a stale school register does not change
what the family wants. Scoring stays off until the education register is current enough and the owner has answered the requirement
questions (validation raises an error if scoring is enabled here).

## Three concepts that stay separate

| Concept | Where | Example |
|---|---|---|
| `USER_REQUIREMENT` | `family-requirements.yaml` | primary school <= 15 min |
| `DATA_CAPABILITY` | `family-evidence-capability.yaml` | baseline drive time to classified primary schools exists, but facility freshness is partial -> `PARTIALLY_SUPPORTED` |
| `EVALUATION_RULE` | (none) | `NOT_ACTIVE_UNTIL_SCORING_MILESTONE` on every row |

Missing or partial data never redefines a preference (tested): a requirement value is carried into the matrix unchanged whatever its capability.

## Input pass 1 (explicit user decisions only)

| Requirement | Preferred | Absolute | Importance | Current evidence support |
|---|---|---|---|---|
| Kindergarten drive time | 15 min | 25 min | PREFERENCE | PARTIALLY_SUPPORTED (stale register) |
| Primary school | 15 | 25 | MUST | PARTIALLY_SUPPORTED |
| Lower secondary | 20 | 30 | MUST | PARTIALLY_SUPPORTED (pooled with upper secondary) |
| Upper secondary | 25 | 40 | STRONG_PREFERENCE | PARTIALLY_SUPPORTED (pooled) |
| Hospital | 20 | 35 | MUST | SUPPORTED_WITH_LIMITATIONS |
| Regional / referral hospital | 45 | 75 | STRONG_PREFERENCE | SUPPORTED_WITH_LIMITATIONS (source typecode only) |
| Drive time to town services | 35 | UNSET (none given) | STRONG_PREFERENCE | NOT_SUPPORTED (no town-services layer) |
| Avoid the dense urban core | true | - | STRONG_PREFERENCE | NOT_SUPPORTED (no density/urban-core evidence) |

The quieter option is preferred even if normal town access is about 30-35 minutes. **Choice diversity is decision context, not a gate:** no fixed minimum
number of schools was requested, so every `minimum_choices_*` and redundancy count stays `UNSET`; counts and travel times are kept so alternatives can be
compared, and a location with a single institution in the preferred band is not failed or penalised. Everything else (university, vocational, airport,
utilities, road surface, all-weather access, telecom, land, density range, school quality, emergency capability) remains `UNSET`.

## Input pass 2 (explicit user decisions only)

| Requirement | Value | Importance | Evidence support / stage |
|---|---|---|---|
| Land purchase budget (**bare land price only**) | absolute max THB 500,000; preferred UNSET | MUST | NOT_SUPPORTED / evidence missing (no land-price data) |
| House-construction budget | UNSET (separate from the land price; not stated) | - | NOT_SUPPORTED / user requirement only |
| Parcel area (min / preferred / max) | UNSET (usable area to be considered separately from nominal area later) | - | NOT_SUPPORTED / parcel verification |
| Legal vehicle access | required | MUST | NOT_SUPPORTED regionally / parcel verification |
| All-weather vehicle access (year-round, normal vehicle) | required | MUST | NOT_SUPPORTED regionally / parcel verification |
| Unpaved final access | acceptable (if it stays usable in the wet season) | - | NOT_SUPPORTED / field verification |
| Major-road proximity | UNSET (no time or distance given) | - | PARTIALLY_SUPPORTED (distance only) |
| Water | PWA **not** required; a village/municipal/local-government system is acceptable **only if field-verified as reliable** before purchase; well/groundwater UNSET | MUST (verified supply) | NOT_SUPPORTED / field verification (outside PWA is not confirmed water) |
| Telecom | **fixed fiber** (not 4G, 5G, fixed wireless or satellite), verified before purchase | MUST | NOT_SUPPORTED (no spatial fiber layer); the evidence gap never weakens the MUST |
| Electricity | UNSET (nothing confirmed in this pass) | - | NOT_SUPPORTED / parcel verification |
| Town services drive time | preferred 35 min (pass 1); hard maximum policy `CASE_BY_CASE`; `absolute_max_drive_time_to_major_city_services` UNSET | STRONG_PREFERENCE | NOT_SUPPORTED / user requirement only |
| Site improvement (drainage, retaining structures, grading/fill) | willing (true), no project-level limit and no financial allowance stated | - | NOT_SUPPORTED / user requirement only |
| Parcel terrain / slope tolerance | UNSET (not inferred from willingness to improve) | - | PARTIALLY_SUPPORTED |

`NOT_SUPPORTED` describes the data, never the requirement: it is not a failure, and the matrix has an `evidence_stage` column
(`REGIONAL_EVIDENCE | EVIDENCE_MISSING | PARCEL_VERIFICATION | FIELD_VERIFICATION | USER_REQUIREMENT_ONLY`) saying where verification must happen.

**Hazard contract (unchanged):** `hazard_contract` in the config states that M1E hazard actions are immutable, that willingness to improve a site never
overrides them, and that family access never offsets them (validation fails otherwise). Willingness to build drainage does not cancel recurrent-flood
evidence, retaining walls do not cancel landslide avoidance, and engineering a site does not turn a severe hazard signal into suitability.

Remaining UNSET groups: university / vocational / primary care importance; school and hospital redundancy counts and all minimum-choice numbers;
airport, shopping, absolute major-city limit; major-road and route-redundancy values; electricity; well water; livability beyond the urban-core
preference (density range, tourism, nightlife, industrial nuisance, agricultural surroundings); preferred land budget and all parcel-area values; terrain tolerance.

## How to fill in requirements

Unstated values are `UNSET` ("the owner has not decided"), not a default. Fill values with the owner; invented defaults are not product truth.
Minutes are `BASELINE_DRIVE_TIME` (free-flow), not commute time. Use importance instead of numeric weights:
`MUST | STRONG_PREFERENCE | PREFERENCE | NICE_TO_HAVE | IRRELEVANT` (weights may be derived later).

Sections: **education** (kindergarten, primary, lower/upper secondary: importance, preferred/absolute max minutes, minimum choices within the
preferred time; vocational: importance; university: importance and preferred minutes) - **healthcare** (primary care, hospital, regional/referral
hospital; no trauma/emergency field: that is a future facility-verification question) - **redundancy** (counts of primary schools, secondary
schools, hospitals within a time) - **road access** (max drive time to a major road, unpaved tolerance, all-weather expectation, route
redundancy) - **utilities** (tolerance, not evidence) - **urban access** - **livability** (placeholders) - **land** (budget, area, terrain,
drainage and retaining-structure willingness).

## Conflict detection (errors, never silently repaired)

Preferred time above the absolute maximum; minimum choices below 1 (or set while the preferred time is `UNSET`); an `IRRELEVANT` item that still
carries thresholds; a redundancy count below 1 or count/time set separately; negative or zero-minute values; requiring PWA/municipal water while
accepting non-PWA or well water; minimum area above maximum (or preferred outside the range); avoiding the dense urban core while preferring
`URBAN` density; enabling scoring. Warnings (not errors): `MUST`/`STRONG_PREFERENCE` with no threshold yet; thresholds without an importance;
tolerating unpaved access while requiring all-weather access. A misspelt key is rejected rather than defaulted.

## Evidence sufficiency (79 requirement leaves + 3 capability-only questions)

| Group | Current capability | Why |
|---|---|---|
| Education stages, vocational, university, school redundancy | `PARTIALLY_SUPPORTED` | stale register (DOPA 2021 + OBEC 2020), lower/upper secondary pooled, band counts only (15/30/60) |
| Primary care, hospital, hospital redundancy | `SUPPORTED_WITH_LIMITATIONS` | current MoPH layer; government only; records mostly 2023-dated; type is not capability |
| Regional/referral hospital | `SUPPORTED_WITH_LIMITATIONS` | source typecode "regional" = 2 hospitals; nothing about emergency/ICU |
| Distance/class of nearest major road | `PARTIALLY_SUPPORTED` | distance, not drive time, was computed |
| Unpaved tolerance, all-weather access, route redundancy | `NOT_SUPPORTED` | no surface/season/alternative-route evidence |
| Electricity, water, telecom | `NOT_SUPPORTED` | `NOT_ASSESSED` / `NON_PWA_OR_UNKNOWN_SERVICE` / `DEFERRED`; parcel verification later |
| Urban access, livability, budget, parcel area | `NOT_SUPPORTED` | no town/airport/retail layer, population grid, nuisance or land-price data |
| Terrain tolerance, drainage and retaining willingness | `PARTIALLY_SUPPORTED` | regional slope proxy and M1E hazard actions only; hazard actions are never offset by family access |
| School quality; emergency/trauma/ICU capability | `NOT_SUPPORTED` (capability-only) | presence is not quality; facility type is not capability |

## Education source backlog (open in parallel, NOT combined here)

MOE central CKAN per-school resource (temporarily unreachable, would be PRIMARY) - DOPA 2021 (historical fallback) - OBEC 2020 class ranges
(authoritative classification) - DLA school list 2569, private-school (OPEC) evidence and current vocational data (candidates, not acquired) -
MOE Data Virtualization report (presence evidence, not extractable) - OSM (cross-check). A federated current register is future work, with each
source's role, vintage and conflicts kept explicit.
