# Hazard evidence model v0.1 (M1B)

Status: **PROVISIONAL.** Config: [`config/hazard.yaml`](../../config/hazard.yaml).
Code: `hearthmap.hazard`, `hearthmap.terrain`, `scripts/m1b/`.
Gate: `M1A1_HUMAN_VISUAL_SIGNOFF = PENDING` — no hazard rule may become a
decision rule until it is cleared.

M1B converts geography into explainable per-cell **hazard evidence**. It does
not answer "where should we buy?", excludes nothing, and scores nothing.

## 1. Evidence levels

| Level | What it is | M1B |
|---|---|---|
| `RAW_EVIDENCE` | Source features/pixels exactly as acquired (data/raw) | yes |
| `DERIVED_INDICATOR` | Per-cell measurements: area fractions, counts, distances, weighted quantiles | yes |
| `PROVISIONAL_HAZARD_INTERPRETATION` | Rule-labelled per-hazard states with reasons and confidence | yes |
| `DECISION_RULE` | Anything that changes eligibility, exclusion or ranking | **no** |

`outputs/m1b/hazard-data-dictionary.csv` lists every field with its level,
hazard, source and meaning.

## 2. Indicators per cell (DERIVED_INDICATOR)

All area fractions are relative to the cell's **in-AOI area** and come from
intersection areas — never from centroid membership.

**Flood** (`flood-gistda-repeated-2005-2016`, role `TEMPORARY_HISTORICAL_EVIDENCE`,
period 2005–2016): `flood_area_fraction`, `flood_freq_ge{2,3,5}_area_fraction`
(share of the cell observed flooded in ≥ k of 12 years), `flood_max_freq`,
`flood_dominant_freq` (area-weighted), `flood_feature_count`,
`flood_distance_m` (cell polygon to nearest flood polygon; 0 = touching),
`flood_evidence_period`, `flood_source_role`. The 2011–2023 GISTDA recurrence
API remains `BLOCKED_CREDENTIAL_REQUIRED`; no key was present in the
environment and catalogue example keys were not used.

**Landslide susceptibility** (`landslide-susceptibility-dmr`):
`landslide_class{1..5}_fraction` using the **publisher's own `gridcode`**
(1 Very Low, 2 Low, 3 Medium, 4 High, 5 Very High — from the DMR data
dictionary and the per-class descriptions in the data),
`landslide_assessed_fraction` (= `landslide_source_support`; area actually
covered by the DMR product), `landslide_max_class`, `landslide_dominant_class`
(+ labels), `landslide_class_distribution` (`code:fraction` list). Unassessed
area stays unassessed — it is never read as "Very Low".

**Landslide events** (`landslide-inventory-dmr`, a separate concept):
`landslide_inventory_points` (mapped scars inside the cell),
`landslide_inventory_distance_m`. Coverage is uneven (aerial-photo
interpretation); absence of scars is not evidence of stability.

**Terrain** (`dem-copernicus-glo30`, a DSM): `terrain_support_px`,
`terrain_support_area_fraction`, `elev_min_m`, `elev_median_m`, `elev_max_m`,
`slope_median_deg`, `slope_p90_deg`, `slope_p98_deg` (robust high),
`slope_max_raw_deg` (raw — prone to canopy/building artifacts),
`slope_gt{5,15,30}_fraction`. Method: [terrain-methods.md](../architecture/terrain-methods.md).

**Waterways** (`osm-overpass-aoi`): `dist_major_waterway_m` (river/canal),
`dist_any_waterway_m` (incl. stream), `waterway_{river,canal,stream}_length_m`.
Distance from a mapped waterway is **not** flood safety; OSM completeness
varies strongly by province. No ephemeral/permanent classification (tags do not
support it).

**Context (never read by interpretation):** `boundary_attribution_uncertain`,
`boundary_zone_ids` (M1A.1 GISTDA material zones, e.g. Wiang Pa Pao
`gistda-50k-0008/0009`), `reserve_area_fraction`, `park_area_fraction`,
`sanctuary_area_fraction`, `requires_legal_verification`. No penalty, no
exclusion, no weighting.

## 3. Provisional interpretation

States per hazard: `HIGH_HAZARD_EVIDENCE`, `CAUTION`,
`NO_HIGH_HAZARD_EVIDENCE_DETECTED`, `UNRESOLVED`. There is no "SAFE" or
"LOW RISK" state: `NO_HIGH_HAZARD_EVIDENCE_DETECTED` only says the evidence
used found nothing above the rule thresholds.

| Hazard | HIGH | CAUTION | UNRESOLVED |
|---|---|---|---|
| Flood | ≥ 10% of cell observed flooded in ≥ 3 of 12 years | ≥ 1% observed flooded once, or observed flooding within 250 m | outside source extent (none in AOI) |
| Landslide | ≥ 25% Very High, or ≥ 50% High+Very High | any High/Very High, ≥ 50% Medium+, or ≥ 1 mapped scar | < 50% of cell assessed by DMR (unless HIGH already) |
| Terrain | DSM slope p90 ≥ 35° | DSM slope p90 ≥ 20° | support < 1 pixel (ADR-0009) |

Confidence: flood MEDIUM when evidence is present, LOW for "nothing observed";
landslide MEDIUM when ≥ 90% assessed else LOW; terrain always LOW (DSM).

**Multi-hazard view (no averaging):** `overall_state` is categorical:
HIGH if any hazard is HIGH → else UNRESOLVED if any is unresolved → else
CAUTION if any is CAUTION → else NO_HIGH_HAZARD_EVIDENCE_DETECTED.
`high_hazards`, `caution_hazards`, `unresolved_hazards` list which hazards
drove the state, so a very-high landslide cell with no observed flooding stays
HIGH (landslide). `evidence_completeness` = share of the three hazards
resolved; `interpretation_confidence` = weakest per-hazard confidence.

## 4. Experimental exclusion candidates

`outputs/m1b/experimental-exclusion-candidates.parquet` holds boolean flags for
every configured threshold of `SEVERE_LANDSLIDE_EVIDENCE`,
`STRONG_RECURRENT_FLOOD_EVIDENCE`, `EXTREME_TERRAIN_EVIDENCE` and
`INSUFFICIENT_HAZARD_DATA`. Each row carries `experimental = true`,
`affects_eligibility = false`, `feeds_scoring = false`. Source ids prefixed
`experimental:` are rejected by scoring models. These flags show what a future
rule *would* do; they are not excluded land. No threshold is selected.

`threshold-sensitivity.csv` reports, for every candidate threshold, cells,
share of cells, area and share of area per province and AOI, plus unknown
cells (never silently counted as affected).
