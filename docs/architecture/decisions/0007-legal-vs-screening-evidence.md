# ADR-0007 — Legal truth is separate from screening geometry

Status: Accepted (M0.1)

## Context

M0's PASS/FAIL/UNKNOWN model risked treating any GIS hit as a definitive
FAIL. Government publishers explicitly state that some layers (e.g. RFD
reserve-forest polygons) cannot certify legal boundaries.

## Decision

Add outcome `FLAG` and an `EvidenceClass` (`DEFINITIVE_EXCLUSION`,
`SCREENING_WARNING`, `REQUIRES_LEGAL_VERIFICATION`). `FAIL` keeps its M0
meaning (→ `EXCLUDED`, null score) but now requires definitive evidence, a
constraint configured to allow it, and registry-permitted sources. Screening
and legal-warning evidence produce `FLAG` → `UNRESOLVED`, never `EXCLUDED`.
Details: [legal-vs-screening.md](../../product/legal-vs-screening.md).

## Consequences

- M0 contracts are preserved (FAIL → EXCLUDED, UNKNOWN ≠ PASS, null score).
- Forest/protected overlaps in M1A are `REQUIRES_LEGAL_VERIFICATION` evidence.
- Shortlisting may later *filter views* on flags, but that is a presentation
  choice, not an exclusion.
