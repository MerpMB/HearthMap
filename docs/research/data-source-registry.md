# Data-source registry

The registry is a **first-class artifact**. The machine-readable source of truth
is [`data-source-registry.yaml`](data-source-registry.yaml), validated by:

```bash
hearthmap check-registry
```

> **M0 state:** no source is `VERIFIED`. Entries are leads drawn from background
> knowledge, recorded so research can be tracked. URLs (where present) were not
> visited during M0. Do not cite any registry fact as established until the
> entry is `VERIFIED`.

## Fields

| Field | Meaning |
|---|---|
| `id` | Stable kebab-case id; referenced from provenance records and scores |
| `name`, `category`, `publisher` | What it is and who publishes it |
| `priority` | `must_have` / `useful` / `later` (see [research-backlog.md](research-backlog.md)) |
| `verification_status` | `VERIFIED` / `CANDIDATE` / `NEEDS_RESEARCH` |
| `source_url`, `access_method`, `format` | How to get it |
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

- `VERIFIED` requires `last_verified` and `source_url`.
- Any `processing_status` other than `NOT_ACQUIRED`/`REJECTED` requires
  `local_raw_path`.
- `confidence` other than `UNKNOWN` requires the entry to be at least
  `CANDIDATE` with `last_verified` set (someone actually looked at it).
- Ids are unique.

## Promoting an entry to VERIFIED — checklist

1. Visit the source; record exact URL and access method.
2. Read the licence; record redistribution and attribution terms.
3. Download a sample; open in QGIS; record **CRS and datum** (Indian 1975?).
4. Record coverage, resolution, vintage/date, update frequency.
5. Write `known_limitations` from what you actually saw.
6. Assign `confidence` per [data-quality-framework.md](data-quality-framework.md).
7. Set `last_verified` to today.
