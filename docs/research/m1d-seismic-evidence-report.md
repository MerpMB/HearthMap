# HearthMap M1D - Seismic and active-fault evidence (regional screening)

> Committed copy of `outputs/m1d-review/README.md`; images and tables live in the untracked review folder.

**Seismic evidence 0.2.0 - PROVISIONAL, experimental; regional screening only.** Not a seismic hazard model, not a score, not a ranking, not a site assessment. Ground response is NOT assessed; absence of nearby faults or events is never evidence of low hazard. Semantics: `docs/product/seismic-evidence-model.md`; sources: `docs/research/seismic-source-findings.md`.

## Selected provisional defaults (recorded)

`hydrogeomorphic_profile = BALANCED`, `flood_fusion_policy = FLOOD_ANY_SOURCE`, `selected_for_provisional_screening = true`, `production_truth = false`; thresholds unchanged (fingerprint-checked). See `docs/product/policy-selection.md`.

## Findings (M1D v0.2.0, regional screening; PROVISIONAL and experimental)

**Corrections made in this pass.**

1. *EQ_ZONE semantics.* The official DMR catalogue (data.dmr.go.th, record `eq_zone`)
   states that the layer comes from a **probabilistic analysis of peak ground
   acceleration with a 10% probability of exceedance in 50 years, per Sadigh et al.
   (1997), in the earthquake-hazard assessment project**. The earlier description ("a model
   program with no scenario or return period") was wrong and is withdrawn. The published
   GIS layer expresses the result as **Modified Mercalli intensity zones** (I–III, IV, V,
   VI, VII). The PGA-to-MMI transformation, class boundaries, source model, site/Vs30
   assumptions, map scale and data year are **not documented** and are not inferred.
2. *Licence.* The restrictive wording (no commercial use, not a legal reference, DMR not
   liable) came from the **older national-portal record data.go.th/dataset/eqzone**
   (created 2020-07-18, modified 2021-10-31, mirrored by OD Mekong) and the older
   `activefault` record (2020/2023). The current official DMR catalogue (record modified
   2026-08-13) and the newer data.go.th records state **Creative Commons Attributions**
   with accessible condition "none"; the ArcGIS service states no terms. The registry now
   keeps `dataset_licence`, `service_terms`, `legal_use_disclaimer` and the recorded
   `licence_discrepancy` apart; no non-commercial restriction is recorded as authoritative.
3. *Strong-concern logic.* v0.1 required fault ≤ 5 km **and** zone VII ≥ 50% **and** a
   recorded M ≥ 5 event ≤ 25 km. Because a catalogue gap then prevented escalation, absence
   of an event acted as negative evidence. v0.2.0 removes that: historical events only
   corroborate. Fault proximity (alone ≤ verification) and the hazard zones are not
   independent observations; agreement is "corroborating evidence", never multiplied.

**Before/after (AOI, km²).** The v0.1 replay reproduces the earlier numbers exactly.

| State | v0.1 (3-way AND, superseded) | v0.2.0 (corrected) |
|---|---:|---:|
| No major seismic concern detected | 12,313 (30.8%) | 12,300 (30.8%) |
| Requires seismic verification | 24,362 (61.0%) | 6,194 (15.5%) |
| Strong seismic screening concern | 3,255 (8.2%) | 21,436 (53.7%) |

18,195 km² changes state, almost all verification → strong (18,182 km²), because the
dominant top class no longer needs a fault and an event to coincide; 14,648 strong cells
have no recorded M ≥ 5 event within 50 km. **Neither distribution is product truth.**

**What the strong state is.** Class VII is the highest class in the DMR layer. It covers
21,430 km² (53.7%) of the AOI, and strong concern follows that footprint almost exactly: the
share of the AOI that is STRONG moves only between 53.5% and 54.0% when the VII-coverage
threshold is varied over 10%, 25%, 50% and 75% (zone polygons are broad, so cells are
mostly wholly inside or outside), and borderline escalation changes at most 0.2% of the
AOI. The result is therefore a robust reading of the DMR zone map, **not** an independent
seismic finding. Fault proximity, events and the verification state add context only
(verification 15.5%, mostly cells outside VII within 10 km of a trace or 50 km of an M ≥ 5
event).

**Provinces (share of province area, v0.2.0).** Chiang Rai 75.2% strong (VII covers 75.2%),
Chiang Mai 50.7%, Phayao 24.0%; no major seismic concern detected 0.2% / 37.3% / 64.8%.
Fault context (descriptive): 37.5% of Chiang Rai lies within 5 km of a mapped trace, 28.4% of
Chiang Mai, 10.0% of Phayao; 59.5% of Phayao is 20–50 km from any trace. The three
provinces differ clearly on the evidence in hand, so regional comparison is meaningful.
Fault groups intersecting: Chiang Mai (Mae Tha, Wiang Haeng, Mae Chan, Moei), Chiang Rai
(Mae Ing, Mae Chan, Mae Lao, Phayao, Mae Tha), Phayao (Phayao group).

**Residential lowlands (reporting strata only).** On low-slope land (DSM p90 ≤ 5°) 63.2% is
strong, 19.1% verification, 17.7% none detected, against 51.7% / 15.1% / 33.2% on steep
land: the flat valley floors sit disproportionately inside the top zone and near traces.
Flat terrain is never treated as seismic evidence in either direction.

**Hydrogeomorphic × seismic (selected provisional defaults BALANCED + FLOOD_ANY_SOURCE,
`production_truth` false).** Hydrogeomorphic "no major concern" with seismic verify or strong:
4,053 km² (10.2%), of which strong 3,349 km² (8.4%); hydrogeomorphic strong/deprioritize with
no major seismic concern detected: 3,256 km² (8.2%); both none detected: 2,394 km² (6.0%).
No combined score is produced.

**Historical seismicity.** DMR inventory (118 earthquake records, 1994–2025, M ≥ 3), TMD
felt-event list (477 events with coordinates, 1930–2026) and USGS ComCat (384 events, M ≥ 3,
1912–2026) stay separate; USGS is an international composite catalogue, not the Thai
national record. Within 100 km of the AOI: DMR 84 (3 ≥ M5), TMD 285 (39 ≥ M5), USGS 159
(30 ≥ M5). Completeness is low and uneven (a 2025 burst of 37 DMR records), so absence of
events is never evidence of low hazard.

## Evidence sufficiency gate

* **A. Regional screening — sufficient for conservative provisional comparison.** All three
  provinces are covered (zones 99.97% of the AOI; fault traces and three catalogues
  nationwide), the publisher states the hazard basis, the sensitivity analysis shows the
  strong state is stable against the threshold choices, and the provinces differ
  materially. Remaining regional limits: the PGA-to-MMI mapping, source model and map scale
  are undocumented; the strong class equals the DMR zone VII footprint; fault and history
  context are descriptive.
* **B. Parcel/site assessment — not sufficient.** Ground response is not assessed (local
  geology, sediment/basin effects, site amplification and Vs30, liquefaction, parcel-level
  geotechnical conditions, building design). Nothing here supports a parcel-level seismic
  decision; any shortlisted site needs a site-specific seismic and geotechnical
  investigation.


## Seismic screening distribution (cells / area / share of province area)

| state | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| NO_MAJOR_SEISMIC_CONCERN_DETECTED | 49,939 / 12,300 km2 (30.8%) | 33,601 / 8,259 km2 (37.3%) | 16,239 / 4,016 km2 (64.8%) | 99 / 25 km2 (0.2%) |
| REQUIRES_SEISMIC_VERIFICATION | 25,260 / 6,194 km2 (15.5%) | 10,884 / 2,662 km2 (12.0%) | 2,817 / 691 km2 (11.2%) | 11,559 / 2,841 km2 (24.5%) |
| STRONG_SEISMIC_SCREENING_CONCERN | 86,870 / 21,436 km2 (53.7%) | 45,612 / 11,238 km2 (50.7%) | 6,132 / 1,487 km2 (24.0%) | 35,126 / 8,711 km2 (75.2%) |
| UNRESOLVED | 4 / 0 km2 (0.0%) | 4 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) | 0 / 0 km2 (0.0%) |

![seismic-screening.png](../../outputs/m1d-review/seismic-screening.png)

Evidence-family tiers (AOI):

| family | tier | cells | area_km2 |
|---|---|---|---|
| fault_tier | NONE | 88871 | 21877.4 |
| fault_tier | NOTABLE | 27681 | 6793.8 |
| fault_tier | STRONG_TIER | 45521 | 11259.2 |
| modelled_hazard_tier | NONE | 74676 | 18363.1 |
| modelled_hazard_tier | NOTABLE | 527 | 130.8 |
| modelled_hazard_tier | STRONG_TIER | 86870 | 21436.4 |
| history_tier | NONE | 65055 | 15981.6 |
| history_tier | NOTABLE | 68384 | 16849.3 |
| history_tier | STRONG_TIER | 28634 | 7099.4 |

## Before / after the corrected strong-concern logic

| v0_1_three_way_rule | v0_2_corrected | cells | area_km2 |
|---|---|---|---|
| NO_MAJOR_SEISMIC_CONCERN_DETECTED | NO_MAJOR_SEISMIC_CONCERN_DETECTED | 49939 | 12299.9 |
| NO_MAJOR_SEISMIC_CONCERN_DETECTED | REQUIRES_SEISMIC_VERIFICATION | 54 | 13.3 |
| REQUIRES_SEISMIC_VERIFICATION | REQUIRES_SEISMIC_VERIFICATION | 25206 | 6180.6 |
| REQUIRES_SEISMIC_VERIFICATION | STRONG_SEISMIC_SCREENING_CONCERN | 73759 | 18181.6 |
| STRONG_SEISMIC_SCREENING_CONCERN | STRONG_SEISMIC_SCREENING_CONCERN | 13111 | 3254.8 |
| UNRESOLVED | UNRESOLVED | 4 | 0.1 |

## Sensitivity (experimental; no thresholds selected)

AOI area (km2) by state:

| variant | NO_MAJOR_SEISMIC_CONCERN_DETECTED | REQUIRES_SEISMIC_VERIFICATION | STRONG_SEISMIC_SCREENING_CONCERN | UNRESOLVED | CHANGED_VS_BASE |
|---|---|---|---|---|---|
| BASE (VII strong >= 0.50, escalation 2 signals) | 12300.0 | 6194.0 | 21436.0 | 0.0 | 0.0 |
| VII_strong_ge_0.10 | 12300.0 | 6063.0 | 21567.0 | 0.0 | 131.0 |
| VII_strong_ge_0.25 | 12300.0 | 6119.0 | 21511.0 | 0.0 | 75.0 |
| VII_strong_ge_0.50_no_escalation | 12300.0 | 6194.0 | 21436.0 | 0.0 | 0.0 |
| VII_strong_ge_0.50_escalation_1_signal | 12300.0 | 6171.0 | 21460.0 | 0.0 | 23.0 |
| VII_strong_ge_0.75 | 12300.0 | 6275.0 | 21355.0 | 0.0 | 81.0 |
| VII_strong_ge_0.75_escalation_1_signal | 12300.0 | 6233.0 | 21397.0 | 0.0 | 86.0 |
| fault_verify_5km | 12375.0 | 6118.0 | 21436.0 | 1.0 | 75.0 |
| fault_verify_20km | 10558.0 | 7936.0 | 21436.0 | 0.0 | 1742.0 |
| history_M4_verify_50km | 3222.0 | 15272.0 | 21436.0 | 0.0 | 9078.0 |
| history_M6_verify_50km | 14653.0 | 3840.0 | 21436.0 | 1.0 | 2354.0 |
| history_verify_100km | 164.0 | 18330.0 | 21436.0 | 0.0 | 12137.0 |

Strong-concern share of each province (%):

| variant | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| BASE (VII strong >= 0.50, escalation 2 signals) | 53.7 | 50.7 | 24.0 | 75.2 |
| VII_strong_ge_0.10 | 54.0 | 51.0 | 24.4 | 75.6 |
| VII_strong_ge_0.25 | 53.9 | 50.9 | 24.2 | 75.5 |
| VII_strong_ge_0.50_no_escalation | 53.7 | 50.7 | 24.0 | 75.2 |
| VII_strong_ge_0.50_escalation_1_signal | 53.7 | 50.7 | 24.0 | 75.4 |
| VII_strong_ge_0.75 | 53.5 | 50.5 | 23.8 | 75.0 |
| VII_strong_ge_0.75_escalation_1_signal | 53.6 | 50.6 | 23.8 | 75.3 |
| fault_verify_5km | 53.7 | 50.7 | 24.0 | 75.2 |
| fault_verify_20km | 53.7 | 50.7 | 24.0 | 75.2 |
| history_M4_verify_50km | 53.7 | 50.7 | 24.0 | 75.2 |
| history_M6_verify_50km | 53.7 | 50.7 | 24.0 | 75.2 |
| history_verify_100km | 53.7 | 50.7 | 24.0 | 75.2 |

Strong-concern share of each reporting stratum (%):

| variant | LOW_SLOPE_LE_5 | GENTLE_5_15 | LOW_OR_GENTLE_LE_15 | STEEP_GT_15 |
|---|---|---|---|---|
| BASE (VII strong >= 0.50, escalation 2 signals) | 63.2 | 53.2 | 58.3 | 51.7 |
| VII_strong_ge_0.10 | 63.5 | 53.6 | 58.7 | 52.0 |
| VII_strong_ge_0.25 | 63.4 | 53.4 | 58.5 | 51.9 |
| VII_strong_ge_0.50_no_escalation | 63.2 | 53.2 | 58.3 | 51.7 |
| VII_strong_ge_0.50_escalation_1_signal | 63.3 | 53.2 | 58.4 | 51.8 |
| VII_strong_ge_0.75 | 63.0 | 53.0 | 58.1 | 51.6 |
| VII_strong_ge_0.75_escalation_1_signal | 63.1 | 53.0 | 58.2 | 51.7 |
| fault_verify_5km | 63.2 | 53.2 | 58.3 | 51.7 |
| fault_verify_20km | 63.2 | 53.2 | 58.3 | 51.7 |
| history_M4_verify_50km | 63.2 | 53.2 | 58.3 | 51.7 |
| history_M6_verify_50km | 63.2 | 53.2 | 58.3 | 51.7 |
| history_verify_100km | 63.2 | 53.2 | 58.3 | 51.7 |

Strong-concern area by hydrogeomorphic status (km2):

| hydro_status | BASE (VII strong >= 0.50, escalation 2 signals) | VII_strong_ge_0.10 | VII_strong_ge_0.75 | VII_strong_ge_0.75_escalation_1_signal |
|---|---|---|---|---|
| NO_MAJOR_CONCERN_DETECTED | 3348.0 | 3370.0 | 3334.0 | 3338.0 |
| REQUIRES_VERIFICATION | 11421.0 | 11491.0 | 11386.0 | 11407.0 |
| STRONG_REGIONAL_CONCERN | 1702.0 | 1714.0 | 1694.0 | 1702.0 |
| REGIONAL_DEPRIORITIZE | 4222.0 | 4248.0 | 4201.0 | 4208.0 |
| UNRESOLVED | 744.0 | 745.0 | 740.0 | 741.0 |

## Active-fault context (descriptive)

| province | fault_zone | traces_intersecting_province | trace_length_inside_km | trace_length_within_20km_buffer_km | max_MCE_source_native |
|---|---|---|---|---|---|
| Chiang Mai | MAE THA | 37 | 525.5 | 691.9 | 6.9000001 |
| Chiang Mai | WIANG HAENG | 25 | 147.5 | 163.5 | 6.69999981 |
| Chiang Mai | MAE CHAN | 5 | 64.6 | 101.5 | 6.80000019 |
| Chiang Mai | MOEI | 1 | 11.2 | 238.3 | 7.0999999 |
| Chiang Mai | MAE HONG SON | 0 | 0.0 | 130.3 | 7.0999999 |
| Chiang Mai | MAE LAO | 0 | 0.0 | 8.2 | 6.80000019 |
| Chiang Mai | PHA YAO | 0 | 0.0 | 201.5 | 7.0 |
| Chiang Rai | MAE ING | 12 | 153.1 | 202.6 | 6.9000001 |
| Chiang Rai | MAE CHAN | 15 | 136.5 | 188.3 | 6.80000019 |
| Chiang Rai | MAE LAO | 6 | 87.8 | 87.8 | 6.80000019 |
| Chiang Rai | PHA YAO | 7 | 81.3 | 238.6 | 7.0 |
| Chiang Rai | MAE THA | 2 | 12.9 | 164.8 | 6.9000001 |
| Phayao | PHA YAO | 5 | 81.1 | 266.0 | 7.0 |
| Phayao | MAE ING | 0 | 0.0 | 47.3 | 6.9000001 |
| Phayao | PUA | 0 | 0.0 | 4.6 | 6.5999999 |
| Phayao | THOEN | 0 | 0.0 | 60.6 | 7.0 |

Share of province area by distance to the nearest mapped trace (%):

| band | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| <= 5 km | 28.2 | 28.4 | 10.0 | 37.5 |
| 5-10 km | 17.0 | 16.2 | 8.8 | 22.9 |
| 10-20 km | 21.6 | 17.9 | 21.8 | 28.4 |
| 20-50 km | 32.8 | 36.6 | 59.5 | 11.2 |
| > 50 km | 0.5 | 0.8 | 0.0 | 0.0 |

![active-fault-context.png](../../outputs/m1d-review/active-fault-context.png)

## DMR hazard zones (probabilistic PGA 10% in 50 years, shown as MMI)

Share of province area by class (%):

| class | AOI | Chiang Mai | Phayao | Chiang Rai |
|---|---|---|---|---|
| I-III | 0.0 | 0.0 | 0.0 | 0.0 |
| IV | 0.1 | 0.2 | 0.0 | 0.0 |
| V | 21.9 | 26.7 | 44.0 | 0.7 |
| VI | 24.3 | 22.4 | 31.9 | 24.0 |
| VII | 53.7 | 50.7 | 24.0 | 75.2 |

![earthquake-intensity-context.png](../../outputs/m1d-review/earthquake-intensity-context.png)

## Historical seismicity (sources kept separate)

| source | records | with_coordinates | with_magnitude | usable_points | year_min | year_max | within_100km_of_aoi | within_100km_ge_M4 | within_100km_ge_M5 | within_100km_ge_M6 | note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dmr | 118 | 118 | 118 | 118 | 1994 | 2025 | 84 | 14 | 3 | 1 |  |
| tmd | 552 | 477 | 550 | 477 | 1930 | 2026 | 285 | 112 | 39 | 6 | records without coordinates (chronicles, intensity-only, unparsed) are excluded from spatial metrics: 75 |
| usgs | 384 | 384 | 384 | 384 | 1912 | 2026 | 159 | 152 | 30 | 7 |  |

![historical-seismicity.png](../../outputs/m1d-review/historical-seismicity.png)

## Hydrogeomorphic x seismic (diagnostic cross-tab, km2; no combined score)

| hydro_status | NO_MAJOR_SEISMIC_CONCERN_DETECTED | REQUIRES_SEISMIC_VERIFICATION | STRONG_SEISMIC_SCREENING_CONCERN | UNRESOLVED |
|---|---|---|---|---|
| NO_MAJOR_CONCERN_DETECTED | 2394.0 | 705.0 | 3348.0 | 0.0 |
| REQUIRES_VERIFICATION | 6538.0 | 3079.0 | 11421.0 | 0.0 |
| STRONG_REGIONAL_CONCERN | 789.0 | 784.0 | 1702.0 | 0.0 |
| REGIONAL_DEPRIORITIZE | 2467.0 | 1494.0 | 4222.0 | 0.0 |
| UNRESOLVED | 112.0 | 132.0 | 744.0 | 0.0 |

| pattern | stratum | cells | area_km2 | share_of_scope_area |
|---|---|---|---|---|
| hydro_favourable_seismic_meaningful | ALL | 16328 | 4053.3 | 0.1015 |
| hydro_favourable_seismic_meaningful | LOW_SLOPE_LE_5 | 1356 | 331.8 | 0.0551 |
| hydro_favourable_seismic_strong | ALL | 13499 | 3348.5 | 0.0839 |
| hydro_favourable_seismic_strong | LOW_SLOPE_LE_5 | 1147 | 280.1 | 0.0465 |
| hydro_concern_seismic_none_detected | ALL | 13361 | 3256.2 | 0.0815 |
| hydro_concern_seismic_none_detected | LOW_SLOPE_LE_5 | 705 | 176.2 | 0.0292 |
| hydro_favourable_and_seismic_none_detected | ALL | 9631 | 2393.9 | 0.06 |
| hydro_favourable_and_seismic_none_detected | LOW_SLOPE_LE_5 | 958 | 237.1 | 0.0394 |

![hydrogeomorphic-vs-seismic.png](../../outputs/m1d-review/hydrogeomorphic-vs-seismic.png)

## Residential-lowland context (slope strata for reporting only, %)

| state | ALL | LOW_SLOPE_LE_5 | GENTLE_5_15 | LOW_OR_GENTLE_LE_15 | STEEP_GT_15 |
|---|---|---|---|---|---|
| NO_MAJOR_SEISMIC_CONCERN_DETECTED | 30.8 | 17.7 | 32.9 | 25.1 | 33.2 |
| REQUIRES_SEISMIC_VERIFICATION | 15.5 | 19.1 | 13.9 | 16.6 | 15.1 |
| STRONG_SEISMIC_SCREENING_CONCERN | 53.7 | 63.2 | 53.2 | 58.3 | 51.7 |
| UNRESOLVED | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

![seismic-lowland-context.png](../../outputs/m1d-review/seismic-lowland-context.png)

## Confidence dimensions (kept separate)

| family | source | methodology | spatial_completeness | temporal_completeness |
|---|---|---|---|---|
| fault_context | MEDIUM | LOW | MEDIUM | NOT_APPLICABLE |
| earthquake_hazard_zones | MEDIUM | MEDIUM | HIGH | MEDIUM |
| historical_seismicity | MEDIUM | LOW | LOW | LOW |
| ground_response | NOT_ASSESSED | NOT_ASSESSED | NOT_ASSESSED | NOT_APPLICABLE |
| decision (per cell) | - | - | - | LOW |

## Human QA

| gate | status |
|---|---|
| M1A1_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1B_HUMAN_VISUAL_SIGNOFF | PASSED |
| M1C_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C1_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C2_HUMAN_VISUAL_SIGNOFF | PENDING |
| M1C3_HUMAN_VISUAL_SIGNOFF | PENDING |

No review of the M1C, M1C.1, M1C.2, M1C.3 or M1D map packs has been reported; none is inferred.

## Files

| File | Bytes |
|---|---:|
| active-fault-context.png | 242,994 |
| before-after-strong-logic.csv | 468 |
| earthquake-intensity-context.png | 225,662 |
| example-explanations.md | 7,881 |
| fault-distance-bands.csv | 1,972 |
| fault-regional-context.csv | 780 |
| historical-seismicity-summary.csv | 401 |
| historical-seismicity.png | 116,665 |
| hydro-seismic-disagreement.csv | 2,286 |
| hydro-vs-seismic-crosstab.csv | 11,600 |
| hydrogeomorphic-vs-seismic.png | 170,749 |
| intensity-class-area.csv | 1,704 |
| seismic-family-tiers.csv | 367 |
| seismic-interpretation-distribution.csv | 994 |
| seismic-lowland-context.csv | 1,216 |
| seismic-lowland-context.png | 125,848 |
| seismic-screening.png | 153,424 |
| seismic-sensitivity-hydro-crosstab.csv | 20,699 |
| seismic-sensitivity.csv | 35,678 |
| seismic-statistics.json | 11,087 |
| source-confidence.csv | 313 |
| strong-seismic-regions.csv | 287 |
| m1d/hydro-seismic-diagnostic-cells.parquet | 958,465 |
| m1d/intensity-zones-repair-audit.csv | 433 |
| m1d/seismic-evidence.gpkg | 74,416,128 |
| m1d/seismic-evidence.gpkg.provenance.json | 7,496 |
| m1d/seismic-evidence.parquet | 4,337,022 |
