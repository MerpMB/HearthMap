# HearthMap M1B — Hazard evidence report

> Committed copy of `outputs/m1b-review/README.md`; images live in the untracked review folder.

**Status:** PROVISIONAL hazard *evidence* — not a decision. No exclusions, scores or rankings. `M1A1_HUMAN_VISUAL_SIGNOFF = PENDING` (only the builder has looked at the M1A.1 maps), so no rule here may be promoted to a DECISION_RULE. `NO_HIGH_SCREENING_CONCERN_DETECTED` never means safe.

Model and field semantics: `docs/product/hazard-evidence-model.md`; terrain method: `docs/architecture/terrain-methods.md`; thresholds: `config/hazard.yaml`.

## Evidence coverage and provisional states (majority-province attribution)

| scope | cells | complete flood evidence | complete landslide evidence | adequate terrain support (>=10 px) | incomplete evidence | HIGH flood evidence (area) | HIGH landslide evidence (area) | strong terrain concern (area) |
|---|---|---|---|---|---|---|---|---|
| AOI | 162,073 | 100.0% | 86.0% | 99.7% | 14.1% | 3.7% | 25.2% | 6.9% |
| Chiang Mai | 90,101 | 100.0% | 93.1% | 99.7% | 7.0% | 1.0% | 31.7% | 8.6% |
| Phayao | 25,188 | 100.0% | 76.5% | 99.7% | 23.5% | 7.8% | 11.1% | 4.1% |
| Chiang Rai | 46,784 | 100.0% | 77.5% | 99.8% | 22.5% | 6.6% | 20.5% | 5.1% |

Province rows use each cell's majority province; 1,442 cells carry the M1A.1 boundary-attribution caution (context only; hazard values are unaffected).

Overall categorical state (worst hazard wins, never averaged):

| scope | HIGH_SCREENING_CONCERN | SCREENING_CAUTION | UNRESOLVED | NO_HIGH_SCREENING_CONCERN_DETECTED |
|---|---|---|---|---|
| AOI | 52,269 | 79,836 | 17,415 | 12,553 |
| Chiang Mai | 33,101 | 43,622 | 5,403 | 7,975 |
| Phayao | 5,415 | 12,759 | 4,132 | 2,882 |
| Chiang Rai | 13,753 | 23,455 | 7,880 | 1,696 |

Cells by which hazards have HIGH evidence (AOI):

| HIGH evidence combination | cells |
|---|---|
| landslide | 35,160 |
| landslide\|terrain | 6,272 |
| flood | 5,855 |
| terrain | 4,972 |
| flood\|landslide | 10 |

![multi-hazard-evidence.png](../../outputs/m1b-review/multi-hazard-evidence.png)

## Flood (historical observed, TEMPORARY evidence)

GISTDA repeated flooding 2005-2016 (satellite-observed). HIGH = at least 10% of the cell observed flooded in at least 3 of 12 years; CAUTION = any observed flooding on at least 1% of the cell or within 250 m. The 2011-2023 recurrence API stays `BLOCKED_CREDENTIAL_REQUIRED` (no project key in the environment; catalogue keys not used). Observed flooding is concentrated in Chiang Rai and Phayao valley floors. The record ends in 2016 and misses flash floods and cloud-covered events.

![flood-evidence.png](../../outputs/m1b-review/flood-evidence.png)

## Landslide (DMR susceptibility and inventory, kept separate)

DMR susceptibility (gridcode 1-5 = Very Low ... Very High per the data dictionary); ~1 km lattice offset from the HearthMap grid; methodology not published. Repairs in the AOI: 199 ring self-intersections, max area change 2.9e-06 m2. Inventory: 6,082 scar points in the AOI, no event years in the data, very uneven by province.

| DMR class | area km2 (AOI) |
|---|---|
| 1 Very Low | 169.0 |
| 2 Low | 9196.4 |
| 3 Medium | 15111.2 |
| 4 High | 7654.3 |
| 5 Very High | 2209.2 |
| not assessed | 5590.2 |

Unassessed landslide cells: 22,652; 96.8% of them have DSM slope p90 below 10 deg (median 2.5 deg) - mostly lowlands outside the DMR product. Reported only; they stay UNRESOLVED.

![landslide-evidence.png](../../outputs/m1b-review/landslide-evidence.png)

## Terrain (DSM slope, support-aware)

Horn 3x3 slope in degrees on the native 1-arc-second grid with geodesic per-row spacing, halo reads across tile seams, NaN on nodata/edges, no smoothing; weighted per-cell statistics with support (ADR-0009). Interpretation uses slope p90 (robust); raw max is reported but not used. The steepest cells cluster around 98.9E 19.4N with DSM maxima near 2,176 m - consistent with the Doi Chiang Dao limestone massif (not field-confirmed). Support: 136 cells below 1 pixel (UNRESOLVED) and 370 cells with 1-10 pixels (LOW_SUPPORT), all thin edge slivers.

![terrain-slope-support.png](../../outputs/m1b-review/terrain-slope-support.png)

## Waterway context

OSM distances and in-cell lengths are context only - not flood safety; OSM completeness differs strongly by province.

![waterway-context.png](../../outputs/m1b-review/waterway-context.png)

## Unknown / incomplete evidence

![unknown-incomplete-evidence.png](../../outputs/m1b-review/unknown-incomplete-evidence.png)

## Experimental exclusion-candidate sensitivity (no threshold selected)

| candidate_rule | threshold | AOI % | Chiang Mai % | Phayao % | Chiang Rai % |
|---|---|---|---|---|---|
| SEVERE_LANDSLIDE_EVIDENCE | >= 0.1 | 9.6 | 12.6 | 3.9 | 7.1 |
| SEVERE_LANDSLIDE_EVIDENCE | >= 0.25 | 6.9 | 9.1 | 2.8 | 5.0 |
| SEVERE_LANDSLIDE_EVIDENCE | >= 0.5 | 5.5 | 7.3 | 2.2 | 3.9 |
| SEVERE_LANDSLIDE_EVIDENCE | >= 0.75 | 3.5 | 4.6 | 1.3 | 2.4 |
| STRONG_RECURRENT_FLOOD_EVIDENCE | >= 0.1 | 3.7 | 1.0 | 7.8 | 6.6 |
| STRONG_RECURRENT_FLOOD_EVIDENCE | >= 0.25 | 2.1 | 0.5 | 5.0 | 3.6 |
| STRONG_RECURRENT_FLOOD_EVIDENCE | >= 0.5 | 1.0 | 0.2 | 2.5 | 1.6 |
| STRONG_RECURRENT_FLOOD_EVIDENCE | >= 0.05 | 4.7 | 1.3 | 9.6 | 8.7 |
| EXTREME_TERRAIN_EVIDENCE | >= 25 | 48.9 | 55.9 | 32.7 | 44.2 |
| EXTREME_TERRAIN_EVIDENCE | >= 30 | 25.6 | 30.2 | 15.4 | 22.4 |
| EXTREME_TERRAIN_EVIDENCE | >= 35 | 6.9 | 8.6 | 4.1 | 5.1 |
| EXTREME_TERRAIN_EVIDENCE | >= 40 | 1.4 | 2.0 | 0.8 | 0.7 |
| EXTREME_TERRAIN_EVIDENCE | >= 45 | 0.3 | 0.5 | 0.2 | 0.2 |
| INSUFFICIENT_HAZARD_DATA | < 1 | 14.0 | 6.9 | 23.8 | 22.5 |
| INSUFFICIENT_HAZARD_DATA | < 0.67 | 14.0 | 6.9 | 23.8 | 22.5 |
| INSUFFICIENT_HAZARD_DATA | < 0.34 | 0.0 | 0.0 | 0.0 | 0.0 |

Terrain is the most brittle candidate (25 -> 30 -> 35 deg moves the flagged share from about 49% to 26% to 7% of the AOI, on a DSM); flood and landslide candidates change more gradually; INSUFFICIENT_HAZARD_DATA is a step function because completeness takes only three values.

![experimental-exclusion-sensitivity.png](../../outputs/m1b-review/experimental-exclusion-sensitivity.png)

## Boundary context (Wiang Pa Pao)

Cells in GISTDA zones gistda-50k-0008/0009 keep their physical hazard evidence ({'SCREENING_CAUTION': 28, 'HIGH_SCREENING_CONCERN': 8}); only their province attribution is uncertain.

## Files

| File | Bytes |
|---|---:|
| experimental-exclusion-candidates.parquet | 962,171 |
| hazard-data-dictionary.csv | 11,494 |
| hazard-evidence.parquet | 22,878,814 |
| hazard-statistics.json | 12,806 |
| hearthmap-hazard-evidence.gpkg | 155,471,872 |
| hearthmap-hazard-evidence.gpkg.provenance.json | 4,257 |
| threshold-sensitivity.csv | 9,138 |
| m1b-review/experimental-exclusion-sensitivity.png | 168,178 |
| m1b-review/flood-evidence.png | 184,354 |
| m1b-review/landslide-evidence.png | 232,399 |
| m1b-review/multi-hazard-evidence.png | 235,507 |
| m1b-review/terrain-slope-support.png | 652,633 |
| m1b-review/unknown-incomplete-evidence.png | 138,405 |
| m1b-review/waterway-context.png | 433,601 |
