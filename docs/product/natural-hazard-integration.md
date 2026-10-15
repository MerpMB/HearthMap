# Natural Hazard integration v0.1 (M1E)

Status: **PROVISIONAL**, regional screening only. Config:
[`config/hazard-integration.yaml`](../../config/hazard-integration.yaml); code:
`hearthmap.hazard.integration`. Inputs are the selected provisional defaults
(hydrogeomorphic `BALANCED`, flood policy `FLOOD_ANY_SOURCE`; `production_truth: false`) and
the experimental seismic evidence. Nothing is modified in those; there is **no scalar hazard
score**, no suitability, and parcel/site hazard assessment is **not complete**.

## Philosophy: severity is not one scale

Hazards differ in the decision they imply. A recurrently flooded area may justify
**avoiding** it; severe landslide susceptibility may justify regional **deprioritization**;
regional earthquake shaking usually calls for structural/site **engineering mitigation**
rather than abandoning a province; missing site-response data calls for **investigation**,
never reassurance. "Higher hazard" therefore does not mean "worse land" on one axis, so the
integration keeps four separate decision axes and never averages families.

## Action model (per hazard family)

Each family independently yields `severity`, `confidence`, `recommended_action`,
`response_class` and `reason_codes` (columns `<family>_*`); the integration layer adds axes on
top and never erases them.

| Action | Meaning |
|---|---|
| `NO_MAJOR_ACTION_TRIGGERED` | no action triggered by the implemented evidence (never "safe") |
| `VERIFY_SITE` | site information must be verified |
| `ENGINEERING_MITIGATION_REQUIRED` | design/engineering mitigation matters (seismic) |
| `STRONG_AVOIDANCE_SIGNAL` | geographic avoidance is meaningful (flood, landslide only) |
| `CONTEXT_ONLY` | corroborating context (historical seismicity) |
| `UNRESOLVED` | evidence missing (e.g. landslide outside DMR coverage) |

| Family | Roles | Config guard |
|---|---|---|
| flood | `VERIFY_SITE`, `STRONG_AVOIDANCE_SIGNAL` (source-aware positive evidence; no polygon ≠ flood-safe) | — |
| landslide susceptibility | `VERIFY_SITE`, `STRONG_AVOIDANCE_SIGNAL`; missing DMR coverage explicit | — |
| terrain proxy (DSM) | `VERIFY_SITE`, corroborates landslide | never avoidance |
| seismic shaking (DMR PGA zones shown as MMI) | `ENGINEERING_MITIGATION_REQUIRED`, `VERIFY_SITE` | never avoidance |
| active-fault proximity | `VERIFY_SITE` | never more than verification |
| historical seismicity | corroborating positive evidence, `CONTEXT_ONLY` | never lowers anything |

### Avoid / verify / mitigate / context taxonomy (`rule_responses`, configurable)

strong recurrent flood → AVOID (+VERIFY); strong landslide susceptibility → AVOID (+VERIFY);
steep DSM terrain → VERIFY; regional MMI VII shaking → MITIGATE (+VERIFY); near an active
fault → VERIFY; historical earthquake → CONTEXT (+VERIFY).

## Decision axes per cell

* `regional_search_action` — `CONTINUE_SEARCH`, `CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION`,
  `DEPRIORITIZE_REGION`, `UNRESOLVED`; derived from **hydrogeomorphic outcomes only**.
* `site_verification_action` — `VERIFY_SITE_REQUIRED` / `NONE_TRIGGERED`, with the families
  concerned and a burden count.
* `engineering_mitigation_action` — `SEISMIC_DESIGN_REQUIRED` / `NONE_TRIGGERED`.
* `data_completeness` — `REGIONAL_COMPLETE_SITE_RESPONSE_MISSING`, `PARTIAL_REGIONAL_EVIDENCE`,
  `CRITICAL_REGIONAL_GAP`; with `ground_response_status = NOT_ASSESSED` and
  `site_response_investigation = REQUIRED_FOR_ANY_PARCEL` in every cell.

`natural_hazard_integrated_state` is a dimension-preserving summary, not a score:
`MULTIPLE_ACTIONS` (avoidance signal and mitigation), `STRONG_AVOIDANCE_SIGNAL`,
`ENGINEERING_MITIGATION_REQUIRED`, `UNRESOLVED` (hydrogeomorphic evidence missing),
`VERIFY_SITE`, `NO_MAJOR_ACTION_TRIGGERED`, in that precedence. The full action set is kept
in `hazard_action_set`.

## Regional deprioritization policy

Deprioritization comes only from hazards where geographic avoidance is meaningful: substantial
recurrent flood, strong landslide susceptibility and multiple severe hydrogeomorphic signals
(already encoded in the selected `BALANCED` policy). **Regional seismic shaking alone and
active-fault proximity alone do not deprioritize in v0.1.** `STRONG_SEISMIC_SCREENING_CONCERN`
maps to `ENGINEERING_MITIGATION_REQUIRED`, a **seismic engineering concern**: earthquake-
resistant design and later site-response investigation matter materially; it does not mean
the land is removed from the search. Seismic mildness never cancels flood or landslide
evidence, and mitigation never changes search eligibility (both tested).

## Integration policies (translation only; none selected)

`BALANCED_ACTION` (reference mapping: deprioritize where the selected hydrogeomorphic policy
does), `AVOIDANCE_FIRST` (any flood or landslide avoidance signal deprioritizes),
`VERIFICATION_FIRST` (avoidance signals become verification burden; deprioritize only where
flood and landslide both signal). They govern only how hydrogeomorphic outcomes translate to
search actions; they do not replace the hydrogeomorphic profile.

## Future suitability contract (designed, NOT activated)

Natural Hazard Resilience must later enter land suitability as separate dimensions that keep
their action semantics, never as `hazard_score 0–100`:

| Dimension | Values | Source |
|---|---|---|
| `hazard_search_eligibility` | `SEARCHABLE`, `SEARCHABLE_WITH_CAUTION`, `DEPRIORITIZED`, `UNRESOLVED` | `regional_search_action` |
| `hazard_verification_burden` | `NONE`, `LOW`, `MODERATE`, `HIGH` | families requiring site verification |
| `hazard_engineering_burden` | `NONE`, `SEISMIC_DESIGN_REQUIRED` | `engineering_mitigation_action` |
| `hazard_uncertainty` | `REGIONAL_COMPLETE_SITE_RESPONSE_MISSING`, `PARTIAL_REGIONAL_EVIDENCE`, `CRITICAL_REGIONAL_GAP` | `data_completeness` |

Forbidden: a scalar hazard score, weighted averages of families, collapsing actions to one
number. `HazardDimensions` cannot be converted to a number and `scalar_hazard_score` raises;
the scoring engine does not consume this layer (tested). A later milestone decides how
eligibility gates, how verification and engineering burden are weighed against cost, and how
uncertainty is carried.

## Parcel-level handoff (contract; nothing is checked in M1E)

A shortlisted parcel inherits a checklist from its cell's actions (`parcel_handoff_checklist`,
`parcel_checklist()`): verify historical local flooding; obtain local flood history; check road
and drainage elevation; inspect slope and retaining conditions; review local landslide
susceptibility and scars; verify fault and site geology; assess soil and geotechnical
conditions; evaluate seismic structural requirements; assess liquefaction and site
amplification where relevant; and always a parcel-specific site-response investigation.
