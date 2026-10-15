# ADR-0005 — Provenance sidecars and weakest-link confidence

Status: Accepted (provisional)

## Context

We must be able to answer "why does this location have this score?" and must
not present poor-resolution evidence as equally trustworthy as precise data.

## Decision

- Every processed artifact has a JSON sidecar validated by
  `hearthmap.provenance.ProvenanceRecord` (sources by registry id, CRS,
  ordered processing steps, method, resolution, code version, confidence,
  limitations, synthetic flag).
- Confidence is a four-level ordinal: `HIGH > MEDIUM > LOW > UNKNOWN`.
- Aggregation is **weakest link**: an assessment's confidence is the minimum of
  the evidence it relies on. `UNKNOWN` ranks lowest.

## Consequences

- Conservative: one weak input caps the whole result. That is intended while
  data is sparse; it may hide that most evidence is strong. A weighted scheme
  (e.g. weight-share of low-confidence evidence) may be adopted later.
- Confidence assignment for sources is a human judgement guided by
  [data-quality-framework.md](../../research/data-quality-framework.md), not
  computed automatically.
