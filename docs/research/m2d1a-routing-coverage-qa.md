# M2D.1a - routing coverage QA

Date: 2026-10-16. Branch: `claude/m2d1a-routing-coverage-qa`. A narrow QA pass before human visual signoff.
No evidence semantics changed, no source acquired, no routing recomputed, no routing parameter changed (the 1 km snap radius and the frozen
BASELINE_DRIVE_TIME network and fingerprint `5c35e98882c3ac62` are untouched and tested), no scoring, Wave 2 not started.
`M2D_HUMAN_VISUAL_SIGNOFF` stays PENDING.

**Question.** About 43.0% of cells (42.7% of area) have no connected road within 1 km. Is that mostly unpopulated, unbuilt terrain, or is meaningful settlement being missed?

**Answer.** It is overwhelmingly low-settlement terrain. The cell and area gaps overstate the practical gap in mountainous country by a factor of about 25 to 70.

## Weighted coverage (`outputs/m2d/tables/routing-coverage-weighted.csv`)

Population is the WorldPop R2025A **MODELLED_POPULATION_ESTIMATE** (alpha), not observed population. Built-up is the **sum of GHSL built-up surface in m2** per cell (a mass, not a cell count).

| Scope | Unresolved cells | Unresolved area | Unresolved modelled population | Unresolved built-up m2 |
|---|---|---|---|---|
| Chiang Mai | 46.3% | 46.0% | 1.53% (28,997 of 1.89 M) | 0.61% |
| Chiang Rai | 34.2% | 34.0% | 1.82% (20,693 of 1.13 M) | 0.60% |
| Phayao | 47.4% | 46.7% | 1.53% (5,034 of 0.33 M) | 0.47% |
| **Whole AOI** | **43.0%** | **42.7%** | **1.63% (54,724 of 3,355,999)** | **0.59% (1.97 M of 333.3 M m2)** |

Unresolved cells keep their population and built-up quantity; they are never counted as zero.

## Settlement overlap (`outputs/m2d-review/routing-unresolved-settlement-overlap.csv`, `.png`)

Descriptive distributions are in `routing-unresolved-settlement-distributions.csv`: unresolved cells have a median of 0 modelled people and 0 m2 built-up (23% hold any modelled
population, 5.6% any built-up), against 78% and 52% of routable cells. No policy threshold is invented. For the review map only, a display class marks unresolved cells at or above the median of
routable *non-zero* cells (modelled population 8.3, built-up 1,566 m2); this is a reference for display, not a threshold, and the class is called *settlement-like for review*, not routing failure.

| Display class | Cells |
|---|---|
| Routable settlement | 71,982 |
| Routable, no settlement signal | 20,416 |
| Unresolved, low-settlement terrain | 68,168 |
| Unresolved, settlement-like for review | 1,507 |

The 1,507 review cells hold about 22,500 modelled people (0.67% of the AOI) and 1.48 M m2 built-up (0.44%). The review table lists the 228 cells that are in the top 150 by modelled
population or the top 150 by built-up m2 among unresolved cells (grid id, province, district, modelled population, built-up m2 and fraction, distance to the routable network, distance to any road
fragment, road-access context, unresolved reason); it has no suitability, ranking or score field. Most listed cells are in Mae Fa Luang, Omkoi, Doi Tao, Mae Chaem, Chom Thong and Mae Suai.

## Cause inspection (`routing-unresolved-cause-summary.csv`; descriptive, no policy change)

Among the 1,507 settlement-like unresolved cells:
- **1,152 (77%) lie 1-2 km from the routable network** - just beyond the snap radius (about 16,400 of the 22,500 modelled people). A snap-radius sensitivity study would recover most of them, but that is a routing-policy change and needs a separate review; the snap distance was not changed.
- **225** lie 2-5 km and 12 lie farther: settlement reached only by minor roads or tracks that the primary-to-unclassified OSM graph does not hold (missing minor roads), or modelled people in places with no mapped road at all.
- **118 sit within 1 km of an isolated OSM road fragment** that is not connected to the main network (disconnected segments or topology gaps). The single highest cell (G500-E001332-N004224, Phayao / Pong; 295 modelled people, 29,205 m2 built-up) is 58 m from such a fragment and 10.4 km from the routable graph. **Correction (M2D.1b):** this report first labelled it "Tha Wang Pha, Phayao"; Tha Wang Pha is in Nan. The cell is only 18% inside the AOI (Phayao / Pong), so most of its modelled population lies outside the AOI. See [m2d1b-admin-label-integrity.md](m2d1b-admin-label-integrity.md).
- A WorldPop or GHSL model artefact cannot be excluded for isolated high cells; both products are modelled and partly dependent.

## Town-service statistics

Every travel-time summary in `descriptive-statistics.csv` still exposes routable cell count (`cells_resolved`), resolved area share, unresolved cell count and unresolved area share, labelled
`MEDIAN_AMONG_ROUTABLE_CELLS_ONLY`. As QA context only (travel times are not population-weighted), `town-services-population-coverage-context.csv` shows that 57,168 modelled people (1.70%) live in cells
with no route to a CORE or BROADER cluster, and gives the same figure per component.

## Conclusion

The unresolved share is not material for population or built-up mass (1.6% and 0.6%), so the routing graph is not systematically missing meaningful settlement. The few settlement-like gaps are concentrated just
outside the snap radius or beside disconnected fragments. No routing change is proposed here; if the owner wants those 1,507 cells reached, the 1-2 km band and the isolated fragments are the places to look in a separate, reviewed routing change.
