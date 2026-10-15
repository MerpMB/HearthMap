# Data-source registry

The registry is a **first-class artifact**. The machine-readable source of truth
is [`data-source-registry.yaml`](data-source-registry.yaml), validated by:

```bash
hearthmap check-registry
```

> **M1A state (2026-10-15):** 8 sources are `VERIFIED` (inspected at the
> source and the data opened). All others remain leads; do not cite them as
> established fact. No source is yet permitted for `POTENTIAL_HARD_EXCLUSION`
> or `PARCEL_LEGAL_VERIFICATION`.

## Fields

| Field | Meaning |
|---|---|
| `id` | Stable kebab-case id; referenced from provenance records and scores |
| `name`, `category`, `publisher` | What it is and who publishes it |
| `priority` | `must_have` / `useful` / `later` (see [research-backlog.md](research-backlog.md)) |
| `verification_status` | `VERIFIED` / `CANDIDATE` / `NEEDS_RESEARCH` |
| `role` | `PRIMARY` / `SECONDARY` / `VALIDATION_ONLY` among sources for the same theme |
| `permitted_uses` | `REGIONAL_SCREENING`, `POTENTIAL_HARD_EXCLUSION`, `LEGAL_WARNING_ONLY`, `PARCEL_LEGAL_VERIFICATION`, `VALIDATION_REFERENCE` ([legal-vs-screening.md](../product/legal-vs-screening.md)) |
| `dataset_title`, `landing_page`, `data_endpoint` | Exact title, official landing page, actual endpoint used |
| `access_method`, `access_restrictions`, `format`, `source_crs` | How to get it and what it is |
| `last_update` | Publisher's last update, as stated |
| `verification_evidence` | What was actually inspected (a working URL is not verification) |
| `redirects_or_changes` | Redirects, renamed files, changed services |
| `analytical_suitability` | What the data may and may not support |
| `coverage`, `spatial_resolution`, `temporal_coverage` | Where, how fine, when |
| `last_verified` | Date someone actually checked the entry (required for `VERIFIED`) |
| `license_or_usage_notes` | Licence, attribution, redistribution limits |
| `expected_update_frequency` | How often it changes |
| `confidence` | Quality of the dataset itself (`HIGH`…`UNKNOWN`); `UNKNOWN` until inspected |
| `known_limitations` | List; required reading before using the data |
| `local_raw_path` | Where the acquired copy lives under `data/raw/` (required once acquired) |
| `processing_status` | `NOT_ACQUIRED` / `ACQUIRED` / `PROCESSING` / `PROCESSED` / `REJECTED` |
| `notes` | Free text |

## State model

```text
NEEDS_RESEARCH ──(dataset identified)──► CANDIDATE ──(checked: url, licence,
                                                       coverage, date, sample opened)──► VERIFIED
```

Rules enforced by validation:

- `VERIFIED` requires `last_verified`, `publisher`, `dataset_title`,
  `landing_page`, `data_endpoint`, `format`, `source_crs`,
  `license_or_usage_notes`, `verification_evidence` and non-empty
  `permitted_uses`.
- A `LEGAL_WARNING_ONLY` source cannot also claim `PARCEL_LEGAL_VERIFICATION`.
- A `FAIL` (definitive exclusion) may only cite sources that are `VERIFIED`
  with `POTENTIAL_HARD_EXCLUSION` (`hearthmap.scoring.evidence`).
- Any `processing_status` other than `NOT_ACQUIRED`/`REJECTED` requires
  `local_raw_path`.
- `confidence` other than `UNKNOWN` requires the entry to be at least
  `CANDIDATE` with `last_verified` set (someone actually looked at it).
- Ids are unique.

## Promoting an entry to VERIFIED — checklist

1. Visit the source; record landing page, exact data endpoint, access method
   and any redirects or changed services.
2. Read the licence; record redistribution and attribution terms.
3. Download a sample; open in QGIS; record **CRS and datum** (Indian 1975?).
4. Record coverage, resolution, vintage/date, update frequency.
5. Write `known_limitations` from what you actually saw.
6. Assign `confidence` per [data-quality-framework.md](data-quality-framework.md).
7. Set `last_verified` to today.
