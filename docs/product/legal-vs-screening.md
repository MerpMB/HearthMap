# Legal truth vs. screening geometry

Status: **Accepted (M0.1).** Implementation: `hearthmap.scoring.models`
(`ConstraintOutcome`, `EvidenceClass`), `hearthmap.scoring.evidence`,
registry `permitted_uses`. Decision record: [ADR-0007](../architecture/decisions/0007-legal-vs-screening-evidence.md).

## Principle

A coarse or approximate government GIS boundary is **not** parcel-level legal
truth. A national-forest-reserve polygon can flag a location for investigation;
the land's legal status must be confirmed against authoritative documents
(title deed, land office, forest officials).

M1A found this stated by the publisher itself: the Royal Forest Department's
reserve-forest dataset says (translated) *"this data cannot be used to certify
forest boundaries; certification must be performed by forest officials"*, and
labels its WMS/WFS services *"approximate national reserved forest boundaries,
not legally citable"*.

## Model

| Outcome | Evidence class | Effect |
|---|---|---|
| `PASS` | (optional) | Constraint satisfied for screening purposes |
| `FAIL` | **must** be `DEFINITIVE_EXCLUSION` | `EXCLUDED`, score null |
| `FLAG` | `SCREENING_WARNING` or `REQUIRES_LEGAL_VERIFICATION` | `UNRESOLVED`, listed under *requires verification*; **never** excluded, not rankable |
| `UNKNOWN` | — | `UNRESOLVED` (or `EXCLUDED` by *conservative policy*, labelled as such) |

Evidence classes:

- **DEFINITIVE_EXCLUSION** — authoritative evidence, for a constraint whose
  config sets `definitive_exclusion_allowed: true`, resting only on sources whose
  registry entry is `VERIFIED` with `POTENTIAL_HARD_EXCLUSION` permitted
  (`check_evidence_authority`).
- **SCREENING_WARNING** — approximate/indicative evidence (e.g. 1:50k observed
  flood polygons): investigate, maybe deprioritise in views.
- **REQUIRES_LEGAL_VERIFICATION** — apparent legal restriction from GIS
  (forest reserve, national park, sanctuary, land-reform area): must be checked
  with documents/officials before any conclusion.

Guards (all tested):

1. A `FAIL` cannot be built without `DEFINITIVE_EXCLUSION`; a `FLAG` cannot claim it.
2. The engine rejects a `FAIL` for a constraint that does not permit definitive
   exclusion — screening evidence cannot be "upgraded" by accident.
3. A `FAIL` must cite sources the registry permits for hard exclusion.
4. Strict policy (`unknown_hard_constraint: exclude`) affects only `UNKNOWN`,
   and labels the result `exclusion_basis: conservative_policy`.
5. All legal/land-status constraints in `config/scoring.yaml` have
   `definitive_exclusion_allowed: false`.

## Source suitability (M1A)

| Source | Regional screening | Potential hard exclusion | Legal warning only | Parcel legal verification |
|---|---|---|---|---|
| `forest-reserve-rfd` (RFD reserve polygons) | yes | **no** | **yes** | **no** (publisher disclaimer) |
| `protected-gistda-mnre` (parks 2014, sanctuaries) | yes | no | yes | no |
| `flood-gistda-history` (2011–2023, primary since M1C.1) | yes | not yet (observed history only) | — | no |
| `flood-gistda-repeated-2005-2016` (legacy corroboration) | context only | no | — | no |
| `boundaries-ocha-cod-ab` | yes (AOI definition) | n/a | — | no |
| OSM roads/waterways | yes | no | — | no (road ≠ legal access) |

Parcel-level legal verification is out of scope until M5/M6 (title documents,
land office, forest officials, site visits).
