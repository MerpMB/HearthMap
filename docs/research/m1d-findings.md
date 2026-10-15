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
