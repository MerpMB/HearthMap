# Seismic evidence model v0.2 (M1D)

Status: **PROVISIONAL and experimental**, regional screening only. Config:
[`config/seismic-evidence.yaml`](../../config/seismic-evidence.yaml); code:
`hearthmap.seismic`. No final seismic policy is selected, there is no scalar Natural
Hazard score, and nothing is ranked.

## Four concepts, never collapsed

| Concept | Source | What it is | What it is not |
|---|---|---|---|
| `FAULT_CONTEXT` | DMR active-fault traces (640 polylines, 17 groups) | distance, nearest group, trace counts within 5/10/20/50 km | shaking or risk; there is **no `fault_distance_score`** |
| `EARTHQUAKE_HAZARD` | DMR `EQ_ZONE`: probabilistic PGA hazard (10% probability of exceedance in 50 years, Sadigh et al. 1997) **displayed as MMI zones** I–III … VII | area share of each class per cell | measured intensity; the PGA→MMI mapping is undocumented |
| `HISTORICAL_SEISMICITY` | DMR inventory, TMD felt events, USGS ComCat (kept separate, not deduplicated) | per-source counts and maxima within radii; nearest event ≥ M4/5/6 | a future probability; absence of events is not low hazard |
| `GROUND_RESPONSE` | none | status `NOT_ASSESSED` plus the explicit list of missing evidence | inferable from slope or flatness |

Fault traces, hazard zones and catalogues are **not statistically independent** (the DMR
hazard analysis may itself use fault/seismicity information). Agreement between them is
reported as *corroborating evidence*; nothing is multiplied.

## Interpretation (experimental thresholds in config)

`NO_MAJOR_SEISMIC_CONCERN_DETECTED` < `REQUIRES_SEISMIC_VERIFICATION` <
`STRONG_SEISMIC_SCREENING_CONCERN`, plus `UNRESOLVED`. Never "earthquake safe",
"no earthquake risk" or "fault safe".

* **Modelled hazard (EQ_ZONE).** Top class VII covering ≥ 50% of the cell (a majority /
  "dominant" rule) may on its own give STRONG; ≥ 10% gives verification. A borderline share
  (10–50%) is escalated to STRONG only if **two positive corroborating signals** are present
  (fault ≤ 5 km and a recorded M ≥ 5 event ≤ 25 km).
* **Fault proximity.** ≤ 10 km gives at most `REQUIRES_SEISMIC_VERIFICATION`; it cannot
  create strong concern alone (no documented methodology links trace distance to shaking).
  ≤ 5 km is a corroborating signal.
* **Historical events.** A recorded M ≥ 5 event ≤ 50 km may raise verification and adds
  reason codes; ≤ 25 km corroborates. History is **never required** for a modelled-hazard
  result and its absence never lowers anything (v0.1 violated this and was corrected).
* **UNRESOLVED.** Zone coverage < 50% of the cell and no other signal.

Per cell the outputs keep the context metrics, the tier of each family, the number of
corroborating signals, `seismic_reason_codes`, informational and unresolved codes,
`seismic_evidence_completeness` (never complete: ground response is missing),
`seismic_decision_confidence` (LOW) and `seismic_scope =
REGIONAL_SCREENING_NOT_SITE_ASSESSMENT`. Source, methodology, spatial and temporal
confidence stay separate per family (`outputs/m1d-review/source-confidence.csv`). Any cell's
state can be explained deterministically from its reason codes.

## Independence guarantees (tested)

The interpretation reads only its named input columns: slope/lowland strata and the
hydrogeomorphic results are never inputs and cannot lower or raise a state; the
hydrogeomorphic policy cannot alter seismic evidence and seismic evidence cannot mutate the
hydrogeomorphic policy. Hydrogeomorphic × seismic appears only as a diagnostic cross-tab.

## Regional screening vs site assessment

Missing ground-response modelling does **not** make regional screening unusable; it
**prevents any claim of parcel- or site-level seismic safety.** See
[ground-response limitations](#ground-response-limitations).

## Ground-response limitations

Not assessed (missing evidence recorded per cell): local geology and ground material,
sediment thickness and basin effects (relevant to the Chiang Rai, Phayao and Chiang Mai
basins), site amplification and Vs30, liquefaction susceptibility, parcel-level geotechnical
conditions, building design and code zone. Flat land can have low landslide concern and
still amplify shaking; flat terrain is never positive or negative seismic evidence.
