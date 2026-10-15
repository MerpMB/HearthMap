# M2A.1 findings: education & healthcare source refresh

Status: **facility refresh incomplete — the current MOE and MoPH registers were not acquirable lawfully from this
environment.** Everything below is reproducible from `scripts/m2a1/`; numbers are in `outputs/m2a1-review/`
(untracked) and summarised in `m2a1-report.md` generated there.

## What was tried (all recorded in `source-access-log.json`)

| Source | Result |
|---|---|
| MOE catalogue (`catalog.moe.go.th`, https) | connection refused (Python, curl, fetch tool, in-app browser) |
| MOE catalogue over plain http | answers, but is an **empty** CKAN instance (0 datasets, `package_show` empty) — not the live catalogue |
| `data.moe.go.th`, MOE file server `203.159.172.49` | unresolved / timed out |
| MoPH HCODE (`hcode.moph.go.th`) | HTTP 403; with a browser User-Agent a Cloudflare bot challenge — **not bypassed** |
| MoPH Open Data (`opendata.moph.go.th`) | HDC statistical-report service; not a facility register |
| "GIS HEALTH" 2026 coordinate dataset (data.go.th `dataset_12_020`) | Amnat Charoen provincial publication; outside the AOI; rejected as national truth |
| OBEC open API `OBEC_SCHOOL_007` | reachable, public, authoritative — but academic year **2563 (2020)** |
| OpenStreetMap facilities | reachable, current (2026-10-16), crowd-sourced |

## Roles actually applied

* Education: DOPA 2021 = FALLBACK primary layer (stale); OBEC 2020 = AUTHORITATIVE_CLASSIFICATION; OSM 2026 = CURRENT_VALIDATION.
* Health: CITIZENinfo 2020 = FALLBACK primary (stale); OSM 2026 = CURRENT_VALIDATION; hospital level PARTIALLY_ASSESSED.
* `compose_primary` refuses to mix: validation rows are never appended to a primary layer and two primary-type sources are rejected.

## Findings

* Authoritative class ranges now classify about half the schools (the rest are private, local-authority or
  unmatched); the M2A baseline derived every school level from names.
* Authoritative ranges show many OBEC schools serve kindergarten and lower-secondary grades. Kindergarten and
  secondary-school accessibility therefore improved a lot in M2A terms (median secondary-school drive time roughly halved), while
  primary-school and healthcare accessibility barely moved. This is a correction of M2A's derived-level pessimism, not
  evidence about school quality.
* Reconciliation shows how stale both registers are against current OSM objects, but "current-only" is not proof of a
  new facility and "stale-only" is not proof of closure.
* Routing (network, speeds, snap rules) is frozen; the config fingerprint is asserted by a test.

## What unblocks M2B

1. The current MOE institution register (official id, affiliation, level fields, status, coordinates, update date) —
   request it from the MOE Education Data Center or fetch from a network that can reach `catalog.moe.go.th`.
2. A MoPH HCODE export (facility, organisation type, service level, hospital level, coordinates, active status).
3. Then add loaders for them as PRIMARY (source roles, `compose_primary` and `reconcile` are already in place) and demote DOPA / CITIZENinfo to HISTORICAL_VALIDATION.
