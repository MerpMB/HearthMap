# Hydrogeomorphic Hazard Screening policy v0.1 (M1C)

Status: **PROVISIONAL** (v0.2.0), no default profile. Gates:
`M1A1_HUMAN_VISUAL_SIGNOFF = PASSED`, `M1B_HUMAN_VISUAL_SIGNOFF = PASSED`
(`config/human-qa.yaml`); the M1C review pack itself is not recorded as
reviewed. Config:
[`config/hazard-policy.yaml`](../../config/hazard-policy.yaml); code:
`hearthmap.hazard.policy`. Scope: hydrogeomorphic only
([natural-hazard-scope.md](natural-hazard-scope.md)).

## Decision ladder (`regional_search_status`)

| Outcome | Meaning | Never means |
|---|---|---|
| `NO_MAJOR_CONCERN_DETECTED` | Within the implemented datasets and thresholds, no major hydrogeomorphic concern was detected | safe, low risk, no flood/landslide risk |
| `REQUIRES_VERIFICATION` | A hazard concern and/or a data-quality issue should be checked (`hazard_verification_required`, `data_verification_required` are separate flags) | unsuitable |
| `STRONG_REGIONAL_CONCERN` | Strong evidence for at least one hazard | rejected |
| `REGIONAL_DEPRIORITIZE` | Spend regional search effort elsewhere unless there is a compelling reason to investigate | unsafe, unbuildable, legally excluded |
| `UNRESOLVED` | Evidence too incomplete for a screening statement | low hazard |

`regional_search_status` is separate from `eligible` in the suitability model
and is never written into it. Policy outcomes cannot be cited as scoring
evidence (`policy:` sources are rejected).

## Exact rule

Per profile, every threshold from config:

1. **Per-hazard concern level** `NONE < VERIFY < STRONG < DEPRIORITIZE`
   * Flood (v0.2.0: GISTDA 2011–2023; recurrent = observed flooded in ≥
     `min_years_flooded` of the **13** years; source, period and record length
     are stated in `source_requirements.flood` and checked against the
     evidence — v0.1.0 used ≥ 3 of 12 years, 2005–2016): DEPRIORITIZE if recurrent
     fraction ≥ `deprioritize_min_fraction`; STRONG if ≥ `strong_min_fraction`;
     VERIFY if any observed flooding ≥ `verify_min_fraction` or within
     `verify_distance_m`. No observed flood is informational only
     (`NO_OBSERVED_FLOOD_IN_RECORD`), never reassurance.
   * Landslide (DMR susceptibility, publisher classes): DEPRIORITIZE if Very
     High ≥ `very_high_deprioritize` or High+Very High ≥ `high_plus_deprioritize`;
     STRONG likewise with `*_strong`; VERIFY if High+ ≥ `verify_high_plus` or
     Medium+ ≥ `verify_medium_plus`. High+Very High is summed so a cell split
     between the two classes is not read as mild.
   * Scars (DMR inventory, corroborating positive evidence only; association =
     scar point inside the cell or within `scar_within_m` of the cell polygon):
     raise NONE → VERIFY; raise STRONG → DEPRIORITIZE only if
     `scar_escalates_strong`. Absence of scars never lowers anything.
   * Terrain (Copernicus GLO-30 **DSM**, slope p90): VERIFY if p90 ≥
     `verify_slope_p90_deg`. Terrain is **capped at VERIFY** — it never produces
     STRONG or DEPRIORITIZE on its own.
2. **Corroboration** (categorical): landslide ≥ STRONG and p90 ≥
   `corroborate_slope_p90_deg` adds `LANDSLIDE_TERRAIN_CORROBORATED`; only if
   `corroboration_escalates_landslide` does it raise STRONG → DEPRIORITIZE.
   Dependency between DMR inputs and terrain is **UNKNOWN** (methodology
   unpublished), so no probabilities are multiplied or combined.
3. **Multi-hazard**: base = maximum level (never an average). If flood and
   landslide are both ≥ STRONG and `escalate_flood_and_landslide_strong`:
   DEPRIORITIZE (`MULTIPLE_STRONG_HAZARD_SIGNALS`). Terrain does not count as a
   separate hazard for escalation.
4. **Incompleteness**: landslide assessed < `landslide_min_assessed_fraction`
   or terrain support < `terrain_min_support_px` → `UNRESOLVED` unless the base
   level is ≥ VERIFY (positive evidence stays visible; unresolved reasons are
   still recorded). `evidence_completeness_class`: `COMPLETE`,
   `UNRESOLVED_PARTIAL`, `UNRESOLVED_CRITICAL` (assessed <
   `landslide_critical_assessed_fraction` or terrain unsupported).
5. **Mapping**: DEPRIORITIZE → `REGIONAL_DEPRIORITIZE`, STRONG →
   `STRONG_REGIONAL_CONCERN`, VERIFY → `REQUIRES_VERIFICATION`, NONE →
   `NO_MAJOR_CONCERN_DETECTED`.

**Inputs** are restricted to `POLICY_INPUTS`. Forest/park/sanctuary, boundary
uncertainty and waterway columns are prohibited (validated in config and
tested): waterways cannot reduce flood concern, boundary disagreement cannot
change an outcome, legal screening is no hazard penalty.

## Outputs per cell

Per profile: `regional_search_status`, per-hazard policy levels,
`hazard_reason_codes`, `data_reason_codes`, `unresolved_reasons`,
`missing_or_incomplete_sources`, `informational_codes`, completeness class —
alongside the unchanged M1B evidence (hazard-specific states, confidences,
dataset-evaluated/positive-evidence flags, waterway context). Explanations are
rendered deterministically from reason-code templates (`reason_codes` in
config) and always include "THIS DOES NOT MEAN".

### Flood fusion (M1C.3)

`apply_policy(..., flood_override=...)` lets a fused flood ladder
(`config/flood-fusion.yaml`, [flood-fusion-policy.md](flood-fusion-policy.md))
replace the profile's own flood rule; nothing else changes. Slope strata are
reporting-only and prohibited as policy inputs.

### Separate completeness semantics (v0.2.1, M1C.2)

`hazard_interpretation` (`NO_MAJOR_CONCERN_IN_ASSESSED_HAZARDS`,
`CONCERN_REQUIRING_VERIFICATION`, `STRONG_CONCERN`,
`DEPRIORITIZATION_LEVEL_CONCERN`) states what the hazards that were actually
assessed indicate; `assessed_hazards` lists them; `data_completeness` is the
completeness class; `landslide_assessment_status` is `ASSESSED`,
`PARTIALLY_ASSESSED` or `NOT_ASSESSED`. Outside DMR coverage the landslide
level is `NOT_ASSESSED` (never `NONE`, never "low susceptibility"), and the
flood/terrain interpretation stays visible. The `regional_search_status` rule
is unchanged.

## Profiles

`CONSERVATIVE`, `BALANCED`, `PERMISSIVE` exist for sensitivity analysis. None
is correct or default. Profiles are monotone (tested): CONSERVATIVE is never
less concerned than BALANCED, which is never less concerned than PERMISSIVE.
