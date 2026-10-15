# M2A.3 findings: MOE acquisition pivot (Data Virtualization)

Result: **`MOE_CURRENT_REGISTER_MANUAL_OR_SERVER_RECOVERY_REQUIRED`.** The Data Virtualization reports are a useful presence signal
but not a location register, and no structured/export route exists, so education stays on DOPA 2021 + OBEC 2020 classes.

## MOE CKAN state

`catalog.moe.go.th/th/dataset/dataset_04_25660427` times out for the project user in a normal browser and for independent checks.
Registry: `source_exists` (state `SOURCE_EXISTS_AGENT_BLOCKED`), `availability: TEMPORARILY_UNREACHABLE`, `last_access_attempt: 2026-10-16`.
It is not marked unavailable, and the server was not hammered (no further retries this milestone).

## What the e-INSPECTION / Data Virtualization system is

`https://inp.moe.go.th/inspec2026/?module=basic_info` (MOE Office of the Inspector General) is a PHP page whose three selectable reports are
**Power BI publish-to-web embeds**; the page's own endpoint `_pages/_api/get_powerbi_data.php?id=1..3` returns only a title, a footer
("data from the MOE Data Virtualization service") and the embed link. Findings (`scripts/m2a3/inspect_inp_moe.py`):

* No documented API, no download/export control in the HTML, no CSV/XLSX/JSON endpoint. The data sits behind Power BI's internal query
  service, an undocumented interface that was **not** used; rendered tables were **not** scraped.
* Viewing the report once as a person would shows: academic year 2569 term 1, 11,508,493 students nationally, and a per-school table with
  10-digit MOE code, name, size class, male/female counts, affiliation, with province/district filters. It does **not** show coordinates,
  grades served or school status, and offers no export.
* No terms are stated for the service; none are inferred from the parent site. The embed key is a capability URL and is not stored.

## Role

Verified metadata; role **VALIDATION / CURRENT-PRESENCE EVIDENCE; NOT_SUITABLE_AS_PRIMARY_LOCATION_REGISTER** (registry entry
`moe-data-virtualization-student-report`, `CANDIDATE`, no permitted analytical use yet, nothing acquired). It would be valuable for
telling which register schools still have enrolment in 2026 once a table can be exported (ask the MOE Education Data Center / ICT Center
for the Data Virtualization institution table, or use an export if the report owner enables one).

## Remaining blocker

A current institution-level register with coordinates and levels: the MOE CKAN dataset (when the server recovers) or a manual supply into
`data/manual/moe-register-current/` (contract from M2A.2). Source hierarchy is unchanged: MOE current register would be PRIMARY, DOPA 2021
historical/fallback, OBEC 2020 classification validation, OSM cross-check.
