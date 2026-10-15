# M2A.2 findings: manual-assisted facility refresh

Status: **healthcare refreshed from a current public MoPH source; education still waiting for a manually supplied MOE
register.** Numbers are in `outputs/m2a2-review/` (untracked) and the generated `m2a2-report.md`.

## Source-state semantics (registry `source_state`)

| State | Meaning | Examples |
|---|---|---|
| `SOURCE_EXISTS_AGENT_ACCESSIBLE` | exists and the agent fetched it | MoPH public hospital point layers (update68, update69) |
| `SOURCE_EXISTS_AGENT_BLOCKED` | exists, the agent environment cannot reach it; `acquisition_path` says how the project user can supply it | MOE current school register; MoPH HCODE |
| `SOURCE_MANUALLY_ACQUIRED` | supplied by the project user and validated (requires acquired data and a raw path) | (none yet) |
| `SOURCE_UNAVAILABLE` | does not exist (requires cited evidence) | (none) |

The MOE register is **not** classified unavailable. A blocked source cannot be `data_verified`.

## Manual-import contract (`data/manual/`, `config/manual-imports.yaml`)

* Put the untouched original plus a filled `MANIFEST.template.yaml` (publisher, dataset title, original URL, download date, file name,
  SHA-256, licence, acquired-by, notes) in `data/manual/<source_id>/`. Contents are git-ignored; only the README and template are tracked.
* `python scripts/m2a2/import_manual.py <source_id>` recomputes the checksum, reads `.xlsx`/`.csv` (no new dependency), maps columns by
  exact alias (an unexpected schema is refused and the columns are printed), then checks: duplicate official ids, missing and invalid
  coordinates, province mismatch (coordinates vs stated province), stale internal dates (Buddhist-era academic years handled) and
  unexpected AOI/national coverage. A file that fails a blocking check is refused; a verified file is copied unchanged to
  `data/raw/<source_id>/manual-<date>/` with a manifest. HCODE is never fetched automatically and its bot challenge is never bypassed.

## What the public MoPH layer gave (automated)

* `pherportal.moph.go.th/arcgis/rest/services/MOPH_DATA/Hospital_update68` (layer last edited 2026-09-09; HCODE keys `maincode`/`oldcode`,
  `typecode`, `level_`, status, bed, ministry, coordinates). 644 records in the three provinces; classes come from the source type/level
  fields: 574 primary units, 43 community, 7 general, 2 regional (Nakornping, Chiang Rai Prachanukroh), 4 university, 7 hospitals outside
  MoPH with no level stated, 3 specialised (name rule), 4 administrative offices (not service points).
* Cross-checks: update69 (638 shared ids, 0 class changes), CITIZENinfo 2020 (80% match by name and location), OSM (current-only objects kept as evidence).
* **Quality flags:** the layer's point geometry and its lat/lon attributes disagree by more than 100 m for 129 records. The geometry agrees
  better with the independent 2020 file (median 36 m vs 363 m among the conflicting records), so it is used; both coordinates are stored.
  Most records carry 2023 record dates although the service was edited in 2026.
* I could not confirm that this layer is the "Hospital Coordinates Service" named on MoPH Open Data; it is recorded as what it is.

## Limits that remain

* No capability (emergency, trauma, ICU, specialist) exists in any accessible source; classes are not capability.
* Higher-level hospital = source type "regional" only; large general hospitals are not promoted (configurable).
* Education remains DOPA 2021 + OBEC 2020 classes until the MOE register is imported. Then the roles become
  MOE PRIMARY, DOPA HISTORICAL/FALLBACK, OBEC CLASSIFICATION/VALIDATION, OSM CROSS-CHECK.
