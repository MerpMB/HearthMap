# M2D.1e - accessibility contract unification

Date: 2026-10-16. Branch: `claude/m2d1e-accessibility-contract-unification`. No routing policy changed (graph, speeds, one-way handling, 1 km snap, 120-minute search, bands and fingerprint `5c35e98882c3ac62`),
no school or MoPH source, taxonomy or capability semantics changed, no dataset acquired, no user requirement or M1E hazard action changed, no scoring, Wave 2 not started, `M2D_HUMAN_VISUAL_SIGNOFF` stays PENDING.
Concepts: [grid-footprint-semantics.md](../architecture/grid-footprint-semantics.md).

## 1. One canonical origin contract

`hearthmap.context.origin.canonical_origins` / `load_canonical_origins` is now the only place a cell origin is chosen. It emits `grid_centroid_lon/lat`, `analysis_point_lon/lat`, `analysis_point_method`
(`GRID_CENTROID` for interior cells and for partial cells whose centroid is inside `GRID_FOOTPRINT intersect AOI`; `AOI_REPRESENTATIVE_POINT` otherwise), `aoi_coverage_fraction_of_cell` and `origin_semantics = CANONICAL_AOI_ANALYSIS_POINT`.
M2D (`build_context.py`), M2A (`build_accessibility.py`) and the M2A.1 sensitivity script all call it; the corrected M2A and M2D artifacts carry byte-identical origin columns (tested). A regression test scans every M2/M3/M4 script that routes or snaps and fails if it does not use the contract
or derives an origin from a raw centroid; the nominal centroid survives only as an explicit comparison (`grid_cen_comparison_xy`) or the explicit historical mode.

## 2. M2A education and healthcare re-run (versioned, not rewritten)

`scripts/m2a/build_accessibility.py --m2a2 --origin-corrected` writes a NEW artifact, `outputs/m2a2-origin/family-infrastructure-evidence.parquet` (artifact id `m2a2-origin-corrected-family-infrastructure-evidence`), with provenance to the original M2A.2 facility sources and routing contract.
The frozen `outputs/m2a2/` output is untouched and remains `HISTORICAL_NOMINAL_CENTROID`. Interior cells are numerically identical in every shared column (157,345 cells, 0 differences). The only values that differ are those of the 2,356 changed-origin edge cells.
The M2D artifact does not contain education or healthcare columns; it documents and tests this corrected artifact instead of consuming it.

**Impact** (affected = the 2,356 cells whose origin changed; `m2a-origin-correction-impact.csv`):

| Category | Unchanged resolved | Unchanged unresolved | Changed, still resolved | Became unresolved | Became resolved | Delta median / p10 / p90 / max abs (min) |
|---|---|---|---|---|---|---|
| early childhood | 270 | 1,521 | 497 | 12 | 56 | -0.05 / -0.48 / +0.21 / 8.18 |
| kindergarten | 270 | 1,521 | 497 | 12 | 56 | -0.05 / -0.45 / +0.21 / 4.82 |
| primary school | 269 | 1,521 | 498 | 12 | 56 | -0.05 / -0.46 / +0.21 / 7.33 |
| secondary school | 268 | 1,521 | 499 | 12 | 56 | -0.06 / -0.45 / +0.22 / 5.37 |
| vocational | 210 | 1,766 | 335 | 7 | 38 | -0.05 / -0.43 / +0.18 / 5.38 |
| university | 170 | 1,858 | 292 | 5 | 31 | -0.04 / -0.42 / +0.21 / 3.53 |
| primary health unit | 264 | 1,540 | 483 | 13 | 56 | -0.06 / -0.45 / +0.21 / 8.69 |
| hospital | 267 | 1,534 | 487 | 12 | 56 | -0.05 / -0.45 / +0.23 / 5.38 |
| regional/referral hospital | 165 | 1,880 | 280 | 2 | 29 | -0.04 / -0.41 / +0.21 / 3.52 |

The changed-origin cells hold only 3,966 modelled people (0.12% of the AOI; WorldPop MODELLED_POPULATION_ESTIMATE, AOI-clipped), and the cells whose value actually changed hold about 2,500-3,000 (under 0.09% of the AOI population per category): the change sits in tiny edge footprints, not in the AOI as a whole.
Nearest-facility ids changed in at most 7 cells (education) and 3 (healthcare); band counts changed in 0-203 cells. Route origins resolved (1 km snap): 795 old, 839 new; snap distance median change -131 m among cells resolved from both.

## 3. Destination catalogue extents (measured; `evidence-extent-audit.csv/json`)

| Evidence | ORIGIN | NETWORK | DESTINATION_CATALOG / FEATURE_CONTEXT extent | Measured |
|---|---|---|---|---|
| all | AOI analysis points | - | - | - |
| routing graph | - | the AOI plus a thin margin | - | 1,095,465 nodes: 10,642 outside the AOI (9,739 elsewhere in Thailand, 903 outside Thailand) |
| education | - | - | three-province DOPA registers + OBEC classes | 4,413 routed schools, all inside the AOI; none in any other province; none international |
| healthcare | - | - | three-province MoPH point layers (changwat filter at acquisition) | 644 facilities, all inside the AOI |
| town services | - | - | three-province OSM extract | 5,019 POIs: 5,018 inside the AOI, 1 in Lamphun |
| industrial / quarry / nightlife | - | - | three-province OSM extract | 212 industrial landuse, 46 works, 37 quarry features and 594 nightlife tags, all inside the AOI |
| DIW / DPIM | - | - | tambon registers of the three provinces | tambon level |

Answers: facilities outside the three provinces are **absent** (education 0, healthcare 0, town services 1). A Phayao cell **cannot** route to a Nan facility (0 Nan records in any catalogue, although the network reaches into Nan). A Chiang Mai border cell can reach exactly one Lamphun town-service POI and no Lampang or Mae Hong Son destination of any family.
No international destinations are included. The facility catalogues are AOI-province-limited, so edge accessibility is **destination-boundary-limited**. No neighbouring-province register was acquired.

## 4. Destination completeness and semantics

Every service and facility result keeps both the routing result and `*_destination_catalog_completeness`: `COMPLETE_WITHIN_AVAILABLE_CATALOG`, `BOUNDARY_LIMITED` or `SOURCE_COMPLETENESS_UNKNOWN`.
The rule is parameter-free: an outside destination must be reached by first leaving the AOI, so it can only beat the catalogued one when the drive time to a *domestic* exit node (`drive_time_to_aoi_exit_domestic_min`) is shorter than the time to the catalogued nearest destination (or no catalogued destination is reachable);
origins that are not routable are `SOURCE_COMPLETENESS_UNKNOWN`. It is relative to the catalogue, never an absolute OSM or register completeness claim, and a valid route does not prove the true real-world nearest destination.
The international exit time is reported for information only: cross-province movement inside Thailand is ordinary, movement into Myanmar or Laos is not, and no international-access model exists.

Lineage now says (per field): town-service times are `ACCESSIBILITY_CONTEXT_WITH_AOI_LIMITED_DESTINATIONS` (`semantic_role ACCESSIBLE_EXTERNAL_CONTEXT`, `catalog_extent THREE_PROVINCE_OSM_EXTRACT`, `completeness BOUNDARY_LIMITED` where flagged);
industrial, quarry and nightlife Euclidean context are `AOI_FEATURE_PROXIMITY_CONTEXT` / `BOUNDARY_TRUNCATED_INFLUENCE_CONTEXT` (`semantic_role EXTERNAL_INFLUENCE_CONTEXT`, `completeness BOUNDARY_LIMITED`): a factory just outside the extract has not been considered; local POI presence stays `LOCAL_AOI_EVIDENCE`, distinct from accessible destinations.
The local/external architecture is kept and gains a completeness dimension rather than being deleted.

Town-service completeness (cells, of 162,073; `town-service-destination-completeness.csv`): CORE cluster 75,713 complete within the catalogue, 16,725 boundary-limited, 69,635 unknown (no routable origin); BROADER 80,780 / 11,658 / 69,635; pharmacy 67,033 / 25,405 / 69,635.

## 5. Boundary-sensitive QA (`accessibility-boundary-distance-bands.csv`; descriptive, nothing corrected)

By distance from the analysis point to the AOI boundary, CORE cluster, median drive time among cells with a route and the share flagged BOUNDARY_LIMITED:

| Band | Cells | Median min | Boundary-limited share |
|---|---|---|---|
| 0-0.5 km | 6,109 | 33.7 | 59% |
| 0.5-1 km | 3,507 | 35.0 | 55% |
| 1-2 km | 6,616 | 31.9 | 51% |
| 2-5 km | 17,979 | 28.3 | 47% |
| 5-10 km | 26,531 | 22.0 | 35% |
| 10-20 km | 43,261 | 19.9 | 11% |
| >20 km | 58,070 | 18.7 | 0.4% |

Edge cells do show longer service times, and the same gradient exists for hospitals (median 28.8 min in the 0-0.5 km band against 17.0 min beyond 20 km), while primary-school times barely move (5.6 against 4.4 min). Mountainous border terrain also lengthens times, so the gradient is **consistent with** destination truncation but does not prove it.
No statistical correction was applied. Map: `accessibility-boundary-context.png`.

## 6. The previously identified cell `G500-E001332-N004224`

| | Nominal | Corrected (education, healthcare and town services alike) |
|---|---|---|
| Origin | centroid 100.58033, 19.09645 (Nan) | AOI representative point 100.58136, 19.09771 (Phayao / Pong), 46 m from the AOI boundary |
| Road snap | 10,422 m | 10,583 m: unresolved for every family |

Every education, healthcare and town-service result for the cell is unresolved with `SOURCE_COMPLETENESS_UNKNOWN`. Its destination catalogues cannot see any facility outside Phayao (0 Nan records; the network does reach across the border), and no destination was invented.

## 7. Evaluability (no promotions, no cosmetic downgrades)

The `safety_reason` of TOWN-SERVICES, EDU-KG, EDU-PRIMARY, EDU-LOWSEC, EDU-UPSEC, HC-PRIMARY, HC-HOSPITAL and HC-REGIONAL now states the destination-boundary limit (catalogue limited to the three provinces, BOUNDARY_LIMITED, no invented or international destinations).
States are unchanged (nothing is READY; town-services component accessibility stays READY_WITH_LIMITATIONS; education PARTIAL; priorities unchanged); the matrix and plan documents were regenerated.
