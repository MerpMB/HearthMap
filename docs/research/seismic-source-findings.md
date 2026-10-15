# Seismic sources — verification and licence findings (M1D, 2026-10-16)

All records below were read directly (CKAN `package_search`/`package_show` APIs, ArcGIS
REST metadata, the data files themselves). Registry entries:
`docs/research/data-source-registry.yaml`.

## DMR EQ_ZONE (`seismic-intensity-zones-dmr`) — corrected semantics

Official DMR catalogue (`data.dmr.go.th`, record `eq_zone`, created 2023-06-19, modified
2026-08-13), `data_source`, verbatim:

> การวิเคราะห์ความน่าจะเป็นของค่าความเร่งพื้นดินสูงสุดของแผ่นดินไหวที่มีโอกาสเพียง 10% ที่มีค่าสูงกว่าค่าที่วิเคราะห์ได้ในคาบเวลา 50 ปี ตามสมการของ Sadigh and others (1997) ในโครงการการประเมินภัยพิบัติแผ่นดินไหว

i.e. a probabilistic analysis of peak ground acceleration with a 10% probability of
exceedance in 50 years, using the Sadigh et al. (1997) relation, in the earthquake-hazard
assessment project. Notes: boundaries of areas that may be affected by earthquakes in
Thailand "using a model program and probabilistic analysis". The data dictionary (05030103)
describes `INTENSITY` as the Modified Mercalli intensity zone code; the ArcGIS layer exposes
classes I–III, IV, V, VI, VII.

| Item | Finding |
|---|---|
| Probabilistic basis | yes: PGA hazard |
| Probability / period | 10% in 50 years |
| Ground-motion relation | Sadigh and others (1997) |
| Displayed as | MMI zones; **PGA→MMI transformation and class boundaries not documented** |
| Map scale | not stated (catalogue, data dictionary, service) |
| Vintage | catalogue record 2023-06-19 / 2026-08-13; earlier data.go.th record 2020-07-18 (shapefile `eq_zone_20200718`); data year not stated |
| Remaining unknowns | source model (faults/seismicity used), site/Vs30 assumptions, scale, data year, validity locally |

Data: 427 polygons, EPSG:32647, 1 self-intersecting ring repaired, no overlaps, covers 99.97%
of the AOI; AOI class areas IV 39, V 8,729, VI 9,721, VII 21,430 km².

## DMR active-fault dataset (`seismic-active-faults-dmr`)

Official record `zone-acttivefault` ("กลุ่มรอยเลื่อนมีพลัง"): compiled from satellite-image
interpretation, geology, geomorphology, earthquake events and other sources, with field
checking, fault dating and corrections. 640 traces, valid, attribute length = geometry
length, three republished service aliases are identical. Attributes are sparse (DIP "0" for
593; trench, date, reference fields empty) so only geometry, group and type are used as
context. The `t-activefault` listing (1,329 points) is consistent with the traces (all within
19.95 km) and is used for validation only. The field data dictionary for the fault dataset
could not be downloaded (HTTP 502).

## Licence investigation

| Record | Licence | Access condition |
|---|---|---|
| data.dmr.go.th `eq_zone`, `zone-acttivefault`, `t-activefault` (2023 → 2026-08-13) | Creative Commons Attributions | none |
| data.go.th `gdpublish-zone-acttivefault`, `gdpublish-t-activefault` (2023 → 2026-09-25) | Creative Commons Attributions | none |
| data.go.th `eqzone` (2020-07-18 → 2021-10-31) and OD Mekong mirror | Creative Commons Attributions | not a legal reference; no commercial use; DMR not liable |
| data.go.th `activefault` (2020-07-14 → 2023-04-19) | Creative Commons Attributions | same restrictive text |
| ArcGIS services (EQ_ZONE, fault layers) | — | no `copyrightText`, no description |

The earlier "forbids commercial use and legal reference" finding came from the **older
national-portal records** (and the OD Mekong mirror of `eqzone`), not from the DMR
catalogue or the service. The registry keeps `dataset_licence`, `service_terms`,
`legal_use_disclaimer` and `licence_discrepancy` separate and does not adopt a
non-commercial restriction as authoritative; project use (non-commercial regional screening
with attribution, no legal-reference use) satisfies both readings. DMR confirmation of which
record governs is an open question.

## Historical seismicity

* **DMR geohazard events** (`geohazard-events-dmr`): 118 earthquake records 1994–2025,
  M 3.0–6.3, curated inventory with undocumented selection.
* **TMD felt events** (`seismic-felt-events-tmd`): 552 records from 624 BC chronicles to
  2026, 477 with coordinates (1930–2026); mixed magnitude/MM text, Thai Buddhist-era dates.
  TMD publishes no bulk instrumental catalogue or API (recent-event RSS only). Preferred
  Thai context where usable.
* **USGS ComCat** (`seismicity-usgs-comcat`): 384 events M ≥ 3, 1912–2026; an international
  composite catalogue of contributed network solutions, **not the Thai national record**;
  corroborating only.

The three sources are not merged or deduplicated; the evidence uses per-source counts and
only the existence of an event across sources.
