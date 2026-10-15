# Provisional policy selection (recorded in M1D, 2026-10-15)

The project owner selected, for **regional screening only**:

```
hydrogeomorphic_profile: BALANCED
flood_fusion_policy: FLOOD_ANY_SOURCE
selected_for_provisional_screening: true
production_truth: false
```

Machine-readable record: [`config/regional-screening-defaults.yaml`](../../config/regional-screening-defaults.yaml)
(with a fingerprint of the selected thresholds; tests fail if they change). The selections
stay provisional until the M1C, M1C.1, M1C.2 and M1C.3 visual QA gates are PASSED
(`config/human-qa.yaml`: M1A.1 and M1B PASSED; the others PENDING). Thresholds were not
modified in M1D.

## Rationale

**BALANCED** — CONSERVATIVE would be too aggressive given the coarse landslide susceptibility
and DSM-derived terrain proxies; PERMISSIVE is less appropriate for long-term family-home
screening where false-negative hazard decisions are costly; BALANCED gives a reasonable
regional search filter while retaining verification states. It is a **project risk-tolerance
decision, not a scientific optimum.**

**FLOOD_ANY_SOURCE** — positive evidence from either verified GISTDA product matters; legacy
evidence can raise concern but never lower it; source disagreements stay explicit; it avoids
the excessive lowland sensitivity of FLOOD_UNION_CONSERVATIVE; it does not discard valid
historical observations because a newer product omitted them.

CONSERVATIVE, PERMISSIVE, FLOOD_CURRENT_PRIMARY, FLOOD_UNION_CONSERVATIVE and the v0.2.1
current-only flood rule remain as sensitivity references. The selection is not parcel-level
truth.
