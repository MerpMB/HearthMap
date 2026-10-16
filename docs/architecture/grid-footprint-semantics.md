# Grid footprint semantics

HearthMap keeps two footprints for every 500 m grid cell. They are different concepts and must not be mixed.

| Concept | Definition | Used for |
|---|---|---|
| `GRID_FOOTPRINT` | The 500 m square, EPSG:32647 (storage and index unit) | cell ids, indexing, routing at the cell centre, full-cell context sums |
| `AOI_ANALYTICAL_FOOTPRINT` | `GRID_FOOTPRINT` intersect the AOI (union of the Chiang Mai, Chiang Rai and Phayao boundaries) | analytical evidence that describes the AOI |

For an edge cell the grid footprint can extend outside the AOI (the grid keeps any cell that overlaps the AOI). `coverage_fraction` is the area share of the grid footprint inside the AOI; fully interior cells have 1.0.

Rules:

1. **Evidence** that describes the AOI must come from the analytical footprint. Evidence located outside the AOI (Nan, Lamphun, Tak, Myanmar, Laos) must not enter an AOI analytical value or an AOI total. A cell being the storage unit does not authorise it.
   Full-cell sums may be kept only in columns named `*_full_cell_context` and labelled `CONTEXT_ONLY`; nothing derived may use them.
2. **Raster evidence** is clipped with the actual AOI geometry (pixel footprint share inside the AOI), not by multiplying a full-cell value by `coverage_fraction`. Cells fully inside the AOI keep their value unchanged.
3. **Administrative labels** (province, district, tambon) come from the cell's own province hierarchy: the unit containing the centroid when it is in an own-province unit, otherwise the own-province unit overlapping the cell most. A centroid join against a neighbouring province or against all of Thailand is never a label.
4. **AOI totals** are sums of analytical-footprint values (or direct pixel-weighted raster totals), never sums of full grid cells.
5. **Point-based fields** (routing and distances evaluated at the cell centroid) are not footprint aggregations, but note that an edge cell's centroid can lie outside the AOI.

Status of existing evidence: see `docs/research/m2d1c-aoi-evidence-audit.csv` (AOI_CLIPPED_ALREADY, FULL_CELL_CONTEXT_ONLY, POTENTIALLY_AFFECTED, NOT_APPLICABLE).

## Point semantics (M2D.1d)

| Concept | Definition |
|---|---|
| `GRID_CENTROID` | the nominal centre of the 500 m square; stored for context (`grid_centroid_lon/lat`) |
| `AOI_ANALYSIS_POINT` | the routing and distance origin: the centroid when it lies inside `GRID_FOOTPRINT intersect AOI`, otherwise the deterministic point-on-surface of that footprint (`analysis_point_lon/lat`, `analysis_point_method`) |

A route origin outside the AOI must not represent the AOI sliver. The analysis point is geographically neutral: never moved toward roads, services or administrative centres.

## Local evidence vs external context (M2D.1d)

Evidence is classified as `LOCAL_AOI_EVIDENCE` (describes the AOI footprint: clipped), `EXTERNAL_ACCESS_CONTEXT` (real-world reach that may cross the AOI boundary: routes and destinations),
`EXTERNAL_INFLUENCE_CONTEXT` (things just outside the AOI that may matter: nearby factories or quarries; no buffer or distance rule is activated) or `MIXED_REQUIRES_SEPARATION` (must be split before use). Local presence is not accessible destination, and local road context is not routing network extent.
Nominal-grid intensity (mass divided by the nominal 0.25 km2 cell) is never described as density within the AOI footprint.
