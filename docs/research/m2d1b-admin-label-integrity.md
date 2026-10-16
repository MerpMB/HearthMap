# M2D.1b - administrative label integrity

Date: 2026-10-16. Branch: `claude/m2d1b-admin-label-integrity`. No routing policy or evidence semantics changed (routing fingerprint `5c35e98882c3ac62`, 1 km snap, population, built-up and
every travel time are byte-identical); no scoring; Wave 2 not started; `M2D_HUMAN_VISUAL_SIGNOFF` stays PENDING.

## The anomaly

The M2D.1a report called the highest-impact unresolved cell "Tha Wang Pha, Phayao". Tha Wang Pha is a district of **Nan**, outside the AOI. The label was wrong.

## Why it was produced

| Item | Value |
|---|---|
| grid_id | `G500-E001332-N004224` |
| centroid | EPSG:32647 (666250, 2112250) = lon 100.58033, lat 19.09645 |
| AOI province (grid `majority_pcode`) | TH56 Phayao (`n_provinces` 1) |
| AOI coverage of the cell | 18.3% (`coverage_fraction`) |
| Where the cell lies (COD boundaries) | 18.3% in Phayao / Pong (TH5606, subdistrict Pha Chang Noi TH560605); 81.7% in Nan / Tha Wang Pha (TH5506, Pa Kha TH550602) |
| Polygon containing the centroid | Nan / Tha Wang Pha (the centroid is outside the AOI) |

**Mechanism: an administrative spatial join, in the reporting script only.** In `routing_coverage_qa.py` the province came from the grid attribute `majority_pcode` (the in-AOI province),
while the district came from a centroid spatial join against the ADM2 layer for **all of Thailand**. The grid deliberately keeps edge cells that only partly cover the AOI, so for such a cell
the centroid can sit in a neighbouring province: the two labels came from different mechanisms and could disagree. It was not a nearest-place lookup, not a source attribute and not formatting.

## Scope

- The same centroid-join pattern was used for the **tambon context** in `build_context.py`. 2,382 of 162,073 cells (1.5%; edge cells with centroid outside their province) were affected:
  2,356 got a blank tambon and therefore a count of 0 (which reads as "no factories" when it was "unmapped"), and 26 inherited a tambon of another AOI province.
- QA review table: 8 of 229 rows had a district from outside their province (Tha Wang Pha/Nan, Li/Lamphun, Sam Ngao/Tak, and blanks for cells whose centroid is in Myanmar or Laos).
- Analytical values were **not** affected: population, built-up, routing, snap distances, travel times and every non-tambon column are identical (tested).

## Corrections

- `assign_max_overlap` (`hearthmap.context.settlement`): a cell takes the unit of **its own province** that contains its centroid; only cells whose centroid is not in an own-province unit fall back to the own-province unit that overlaps the cell most;
  with no overlap the label is blank (unknown), never a neighbour's. `diw_tambon_assignment_method` (ordinary cells 159,691; fallback 2,382), `diw_tambon_overlap_share_of_cell` and the tambon-context counts were regenerated: 1,005 cells changed their DIW count (986 from 0 to more than 0), 97 their DPIM stone-crushing count; all others are unchanged.
- Review table: `district`, `district_th` and the new `district_pcode` now come from the authoritative COD hierarchy of the reported province. The cell is Phayao / Pong (TH5606). New explicit fields carry the context that used to leak into the label:
  `province_pcode`, `district_assignment_method`, `district_overlap_share_of_cell`, `aoi_coverage_fraction_of_cell`, `cell_centroid_lon/lat`, `centroid_in_reported_province`, and `centroid_nationwide_adm1_context` / `centroid_nationwide_adm2_context`.
  A nearest or nationwide place is never put in a district field.
- Invariant tests (`tests/test_m2d1b.py`): every reported district/province pair is a valid COD pair; every district pcode starts with the province pcode; the context fields are separate and explicitly named; tambon context is always a tambon of the cell's own province.

## Side finding to keep in mind for review

Population and built-up are summed over the **whole** 500 m cell, including any part outside the AOI. The 4,636 edge cells hold about 39,900 modelled people, of which at most about 16,000 (0.48% of the AOI total, an upper bound from `1 - coverage_fraction`) lie outside the AOI.
This is a property of the grid design (coverage is recorded in `coverage_fraction`) and was not changed. For the cell above, 82% of its area is in Nan, so its 295 modelled people and 29,205 m2 built-up are mostly outside the AOI and its status as the "highest-impact" unresolved cell is overstated; it is the largest *listed* cell, not evidence of a Phayao routing gap.
The review table now carries `aoi_coverage_fraction_of_cell` so each row can be read with that in mind. The M2D.1a headline shares (1.63% population, 0.59% built-up unresolved) are unaffected to within this bound.
