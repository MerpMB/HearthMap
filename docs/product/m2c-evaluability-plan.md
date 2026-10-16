# M2C evaluability plan

Plain-language plan, generated from `config/family-evaluability.yaml`. **Planning only: scoring is not authorised (`FAMILY_SCORING_ALLOWED: false`),
no evaluation rule is active, no evidence is acquired here, and M1E hazard actions stay independent.** The row-level detail is in
`outputs/m2c/evaluation-permission-matrix.csv` (requirement x decision stage) and the acquisition plan is `docs/research/m2c-evidence-backlog.md`.

Decision stages: REGIONAL_SCREENING, CANDIDATE_ZONE_COMPARISON, PARCEL_SHORTLIST, PRE_PURCHASE_VERIFICATION. For every requirement the plan keeps
five evidence concepts apart (exists, resolution, freshness, completeness, evaluation safety) and gives a state per stage: a column existing in an artifact never makes a requirement READY.

## 1. What HearthMap can evaluate now (regionally, with stated limitations)

- `HC-PRIMARY` Primary healthcare travel time
- `HC-HOSPITAL` Hospital travel time
- `HC-REGIONAL` Regional / referral hospital travel time

Cells with no road access or beyond the search limit stay unresolved, never passing. Facility type is not capability.

## 2. What it cannot evaluate (regionally)

- `HC-CAPABILITY` Emergency / trauma / ICU capability (future verification path)
- `LAND-PRICE` Bare-land purchase price ceiling (THB 500,000)
- `ELEC-GRID` Grid electricity at the parcel (before purchase)
- `WATER-PWA` Water path - PWA service
- `WATER-LOCAL` Water path - municipal / local-government public water
- `WATER-VILLAGE` Water path - village water system
- `WATER-GROUND` Water path - groundwater / well
- `FIBER` Fixed fiber internet (before purchase)
- `ROAD-B-LEGAL` Road access B - legal vehicle access
- `ROAD-C-ALLWEATHER` Road access C - all-weather vehicle access
- `ROAD-D-SURFACE` Road access D - road surface (unpaved final access acceptable)
- `ROAD-E-NOISE` Road access E - residential exposure to major-road noise
- `NUIS-INDUSTRIAL` Industrial nuisance avoidance
- `NUIS-MINING` Mining / quarry / crushing nuisance avoidance
- `NUIS-NIGHTLIFE` Nightlife concentration avoidance
- `PARCEL-AREA` Parcel size (intentionally unset)

Missing evidence triggers verification or new evidence work, never rejection and never a pass.

## 3. What can be evaluated only approximately

- `EDU-KG` Kindergarten travel time
- `EDU-PRIMARY` Primary school travel time
- `EDU-LOWSEC` Lower secondary travel time
- `EDU-UPSEC` Upper secondary travel time
- `TOWN-SERVICES` Town-services access (preferred 35 min)
- `LAND-PRICE` Bare-land purchase price ceiling (THB 500,000)
- `ELEC-GRID` Grid electricity at the parcel (before purchase)
- `WATER-GROUND` Water path - groundwater / well
- `FIBER` Fixed fiber internet (before purchase)
- `ROAD-A-NETWORK` Road access A - network accessibility (OSM routing)
- `ROAD-C-ALLWEATHER` Road access C - all-weather vehicle access
- `ROAD-E-NOISE` Road access E - residential exposure to major-road noise
- `NUIS-NIGHTLIFE` Nightlife concentration avoidance
- `SETTLE-PEACE` Quiet, lower-density setting (avoid the dense urban core)
- `TERRAIN-PREF` Gentle / rolling terrain preference

Partial evidence (stale or pooled education) and labelled proxies (`PROXY_ONLY`) are never presented as verified.

## 4. What must wait until parcel inspection

- `ELEC-GRID` Grid electricity at the parcel (before purchase)
- `WATER-PWA` Water path - PWA service
- `WATER-LOCAL` Water path - municipal / local-government public water
- `WATER-VILLAGE` Water path - village water system
- `WATER-GROUND` Water path - groundwater / well
- `FIBER` Fixed fiber internet (before purchase)
- `ROAD-B-LEGAL` Road access B - legal vehicle access
- `ROAD-C-ALLWEATHER` Road access C - all-weather vehicle access
- `ROAD-D-SURFACE` Road access D - road surface (unpaved final access acceptable)
- `PARCEL-AREA` Parcel size (intentionally unset)

These are satisfied only by parcel documents, provider/PEA confirmation or field verification, never by regional evidence.

Explicitly irrelevant (excluded from evaluation and prioritisation): `IRR-AIRPORT` Airport proximity (IRRELEVANT), `IRR-UNIVERSITY` University proximity (IRRELEVANT), `IRR-VOCATIONAL` Vocational access (IRRELEVANT).

## 5. What evidence to acquire next (derived priorities)

- IRRELEVANT importance -> NOT_APPLICABLE_IRRELEVANT (never prioritised).
- No evidence gap (or the gap is owner calibration, not data) -> NO_EVIDENCE_GAP.
- Importance UNSET / no requirement stated -> NOT_PRIORITISED_REQUIREMENT_UNSET.
- Otherwise the class follows the EARLIEST decision stage at which the evidence would shape the work: regional screening -> P0, candidate-zone comparison -> P1, parcel shortlist -> P2, pre-purchase verification -> P3.
- P0 additionally requires importance MUST or STRONG_PREFERENCE and that the evidence changes the regional search space; otherwise a regional item is P1 (a preference never blocks regional evaluation).
- Acquisition feasibility, cost of false positives/negatives and source quality are recorded for planning but never change the class: an easy dataset is not prioritised for being easy.

### P0 - blocks responsible regional evaluation

- `EDU-PRIMARY` Primary school travel time - A MUST whose travel time shapes the search space, resting on a stale register.
- `EDU-LOWSEC` Lower secondary travel time - A MUST on a stage the current artifact cannot separate, on a stale register.
- `EDU-UPSEC` Upper secondary travel time - A strong preference on the same stale, pooled evidence.
- `TOWN-SERVICES` Town-services access (preferred 35 min) - A strong preference with no evidence at all that decides how far from towns the search can go.
- `LAND-PRICE` Bare-land purchase price ceiling (THB 500,000) - A MUST that can remove large parts of the search space and has no evidence yet. M2D deferred acquisition only: the Treasury D-Value appraisal is recorded as OFFICIAL_APPRAISAL_CONTEXT research, not acquired, and the P0 gap is unchanged.
- `SETTLE-PEACE` Quiet, lower-density setting (avoid the dense urban core) - A strong preference that decides which areas are too urban, with no evidence yet.

### P1 - high value for candidate comparison

- `EDU-KG` Kindergarten travel time - Education travel times shape which regions are searched; the register is stale, so the evidence gap matters at the first stage.
- `ROAD-E-NOISE` Road access E - residential exposure to major-road noise - A strong avoidance preference that can only be proxied at the candidate-zone scale.
- `NUIS-INDUSTRIAL` Industrial nuisance avoidance - A strong avoidance preference with no usable evidence; a missed factory is costly.
- `NUIS-MINING` Mining / quarry / crushing nuisance avoidance - A strong avoidance preference with no usable evidence.
- `NUIS-NIGHTLIFE` Nightlife concentration avoidance - A strong avoidance preference that can only be proxied from venue clusters.

### P2 - important for the parcel shortlist

- `ELEC-GRID` Grid electricity at the parcel (before purchase) - A MUST whose truth exists only at the parcel; regional evidence cannot decide it.
- `WATER-PWA` Water path - PWA service - The requirement is verified water at the parcel; PWA is only one possible path.
- `FIBER` Fixed fiber internet (before purchase) - A MUST decided at the address, not at the regional level.
- `ROAD-B-LEGAL` Road access B - legal vehicle access - A MUST that exists only at the parcel.
- `ROAD-C-ALLWEATHER` Road access C - all-weather vehicle access - A MUST verified by inspecting the road in the wet season.
- `ROAD-D-SURFACE` Road access D - road surface (unpaved final access acceptable) - Surface evidence only matters as part of the all-weather check.

### P3 - pre-purchase / field verification

- `WATER-LOCAL` Water path - municipal / local-government public water - Reliability of a local system can only be established in the field.
- `WATER-VILLAGE` Water path - village water system - Only field verification can establish village-system reliability.
- `WATER-GROUND` Water path - groundwater / well - Suitability of a well is parcel truth; regional potential can only add context.

The derived priorities broadly match the expected picture: town services, settlement intensity, current education and land-market evidence
sit at P0/P1; nuisance families and noise at P1; electricity, fiber, legal access, all-weather access and water verification at P2/P3. The derivation is
rule-based and independent of how easy a dataset is to obtain.

## 6. Why scoring is still disabled

`FAMILY_SCORING_ALLOWED` is false. Criteria not yet met:

- P0 evidence for EDU-PRIMARY is PARTIAL at REGIONAL_SCREENING
- P0 evidence for EDU-LOWSEC is PARTIAL at REGIONAL_SCREENING
- P0 evidence for EDU-UPSEC is PARTIAL at REGIONAL_SCREENING
- P0 evidence for TOWN-SERVICES is PARTIAL at REGIONAL_SCREENING
- P0 evidence for LAND-PRICE is BLOCKED_BY_SOURCE_GAP at REGIONAL_SCREENING
- P0 evidence for SETTLE-PEACE is PARTIAL at REGIONAL_SCREENING
- the owner has not reviewed the interpretation of each evaluable requirement or authorised scoring

Criteria already satisfied by the plan:

- every MUST entry has an explicit evaluation or verification stage (13 entries)
- missing evidence is never positive (policy VERIFY_NOT_PASS on every row)
- hazard actions remain independent and immutable

Scoring could become safe only when all of these hold (the owner must then explicitly authorise it):

- Every MUST/STRONG_PREFERENCE requirement is either evaluable at a regional/candidate stage (READY, READY_WITH_LIMITATIONS or explicit PROXY_ONLY) or has been moved to an explicit later-stage verification state.
- Evidence that decides the regional search space (P0 families) is at least READY_WITH_LIMITATIONS, or an explicitly labelled PROXY_ONLY with documented semantics approved by the owner.
- No unsupported MUST requirement is silently ignored: it appears in the permission matrix with a verification stage.
- No unresolved or missing evidence is interpreted as positive evidence.
- Proxy evidence is never presented as verified, and parcel/field requirements are never satisfied by regional evidence.
- User requirements (config/family-requirements.yaml) are unchanged by evidence gaps; IRRELEVANT dimensions stay excluded.
- M1E hazard actions remain independent and immutable; family access, terrain preference and site-improvement willingness never offset them.
- The owner has reviewed the interpretation of each evaluable requirement (including the numeric meaning of any preference) and explicitly authorised scoring.
