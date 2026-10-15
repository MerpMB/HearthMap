# M2B family requirement calibration sheet (UNFILLED)

Status: **blank on purpose.** M2A supplies evidence (what can be reached, what is known). Whether it
is *enough* for the family is a preference that only the owner can state. Nothing below has been
filled in, defaulted or guessed. Every answer is "UNANSWERED" until the owner decides.

How to use: answer each question, then M2B turns the answers into explicit, versioned thresholds
and a scoring design. M2A evidence columns that each answer would be applied to are listed so
nothing is applied implicitly.

## A. Education

| # | Question | Evidence it would use | Answer |
|---|---|---|---|
| A1 | Maximum BASELINE_DRIVE_TIME to an early-childhood centre (min)? Is none acceptable? | `drive_time_to_nearest_early_childhood_centre_min` | UNANSWERED |
| A2 | Maximum drive time to a kindergarten (min)? | `drive_time_to_nearest_kindergarten_min` | UNANSWERED |
| A3 | Maximum drive time to a primary school (min)? Accept a school that is only *derived* as primary? | `drive_time_to_nearest_primary_school_min`, `level_confidence` | UNANSWERED |
| A4 | Maximum drive time to a secondary school (min)? Is boarding/transport an acceptable substitute? | `drive_time_to_nearest_secondary_school_min` | UNANSWERED |
| A5 | Is university or vocational proximity needed, and within how many minutes? | `..._university_min`, `..._vocational_institution_min` | UNANSWERED |
| A6 | Must several pathways be reachable (how many, within which band)? | `education_pathways_within_{15,30,60}min` | UNANSWERED |
| A7 | May school-quality, language or curriculum preferences be added later? If so, what source would you trust? | not available in M2A | UNANSWERED |

## B. Healthcare

| # | Question | Evidence it would use | Answer |
|---|---|---|---|
| B1 | Maximum drive time to a primary health unit (min)? | `drive_time_to_nearest_primary_health_unit_min` | UNANSWERED |
| B2 | Maximum drive time to a hospital (min)? Are private hospitals required (not in M2A data)? | `drive_time_to_nearest_hospital_min` | UNANSWERED |
| B3 | Maximum drive time to a higher-level (regional/tertiary) hospital (min)? Can you supply an authoritative list so this can be computed? | `higher_level_hospital_*` (deferred) and `config/healthcare-reference-levels.yaml` | UNANSWERED |
| B4 | Is emergency/trauma capability required? Which source would you accept as proof? | not available in M2A | UNANSWERED |

## C. Roads and access

| # | Question | Evidence it would use | Answer |
|---|---|---|---|
| C1 | Minimum acceptable road access (connected road within 500 m / 1 km)? | `road_access_context`, `road_snap_distance_m` | UNANSWERED |
| C2 | Is access to a primary/trunk/secondary road required within some distance? | `nearest_major_road_distance_m` | UNANSWERED |
| C3 | How much redundancy matters (two independent routes, flood-free route)? | not computed in M2A | UNANSWERED |
| C4 | Is a rainy-season or unpaved-road penalty acceptable to model? | not available (BASELINE_DRIVE_TIME is free-flow) | UNANSWERED |
| C5 | Which speed sensitivity should be treated as the planning case (SLOW / BASE / FAST)? | `..._slow_min`, `..._fast_min` | UNANSWERED |

## D. Utilities

| # | Question | Evidence it would use | Answer |
|---|---|---|---|
| D1 | How much electricity-service uncertainty is tolerable before a parcel is considered? | `electricity_service_potential` (NOT_ASSESSED everywhere) | UNANSWERED |
| D2 | Is non-PWA water acceptable *if field-verified* (well, village or municipal system)? Which options? | `water_service_context`, `water_service_verification_required` | UNANSWERED |
| D3 | Is reliable mobile/broadband coverage required, and at what level? | telecom DEFERRED | UNANSWERED |

## E. Data and process

| # | Question | Answer |
|---|---|---|
| E1 | May M2B proceed with 2020–2021 facility data, or should the MOE register / newer DOPA data be obtained first? | UNANSWERED |
| E2 | How should stale evidence be treated (warn only, widen thresholds, or block)? | UNANSWERED |
| E3 | Should healthcare/education access ever offset a hazard action? **M2A assumes NO**: a hazard avoidance or mitigation signal is never compensated by family access. | UNANSWERED (default fixed: no compensation) |
| E4 | Does the owner want the M2A review maps checked first (human QA gate `m2a_human_visual_signoff`, currently PENDING)? | UNANSWERED |

Principle carried into M2B: accessibility is not desirability, and no family or infrastructure
score exists until these answers do.
