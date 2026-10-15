# M2A routing engine decision

Status: **decided for M2A (prototype-grade, reproducible)**; revisit before any parcel-level work.

## Requirement

Road travel time, not straight-line distance, is the decision basis for accessibility. It must be
reproducible, run offline over a 39,930 km² area of interest, honour one-way restrictions and road
classes, state its speed assumptions, and leave unreachable cells *unresolved*.

## Options considered

| Option | Reproducible | Turn restrictions | Classes / speeds | Offline | AOI size | Licence | Verdict |
|---|---|---|---|---|---|---|---|
| OSRM | yes | yes (profile) | yes (Lua profile) | yes | fine | BSD-2 | needs a native build / Docker and a PBF; the national Geofabrik PBF (693 MB) exceeds the 250 MB acquisition guard and the AOI subset is an Overpass JSON, not a PBF |
| Valhalla | yes | yes | yes | yes | fine | MIT | same packaging barrier; heavier tile build |
| GraphHopper | yes | yes | yes | yes | fine | Apache-2 | needs a JVM and a PBF |
| pandana | yes | no | edge weights | yes | fine | BSD | not installed; one-way support limited |
| **Own directed-graph prototype (NumPy CSR + heap Dijkstra)** | **yes (pure Python, deterministic tie-break)** | **no turn restrictions** | **per-class speed table in `config/family-infrastructure.yaml`** | **yes** | **1.10 M nodes, 2.23 M directed edges, 12 s to build** | project code | **chosen for M2A** |

## Why the prototype

* The only road source on disk is the OSM Overpass JSON (way geometry, tags) — no PBF. Building an
  OSRM/Valhalla/GraphHopper graph would first require converting that JSON, which adds a second
  unverified step. A small, tested graph builder is simpler to audit.
* Shared vertices are matched by exact lon/lat (1e-7°). Ways that are in the extract twice (province
  borders) are dropped by OSM id. `access=no|private` and `motor_vehicle=no|private` ways are excluded;
  `oneway=yes|-1` and roundabouts are directional.
* Multi-source Dijkstra over the *reversed* graph gives, for every node, the time/distance to its nearest
  facility, so a travel-to-facility metric respects one-ways. Ties break on the smaller facility index.
* Counts within time bands use one bounded search per facility.

## Known limitations (carried into every output)

* **No turn restrictions, no signals, no junction delay, no traffic, weather, rainy-season or surface
  effects.** Times are `BASELINE_DRIVE_TIME`, free-flow class speeds — *not* actual commute time.
* The extract holds `trunk`…`residential` highways (no `track`/`service`). Areas reached only by
  tracks will appear unreachable although they may be passable.
* OSM completeness varies by province (see `docs/research/data-source-registry.yaml`).
* Cell centres and facilities are snapped to the nearest node of the routable network; farther than
  1 km ⇒ no route (`NO_ROAD_WITHIN_SNAP_DISTANCE`). The off-network leg is excluded from the time.
* The Euclidean distance column is `*_diagnostic` only and never substitutes for a failed route.

## Official road data (kept separate)

The DRR rural-highway service (390 links in the AOI) is a link inventory, not a connected network, and
is **not** merged into the OSM graph. It is used as independent context
(`drr_rural_highway_within_1km`) and to check OSM presence. DOH national highways were not found as a
machine-readable service. Provenance of each network stays separate.

## Speed sensitivity

`SLOW ×0.75`, `BASE ×1.0`, `FAST ×1.25` multiply every class speed. Cell-level SLOW/FAST times are stored
for primary schools, secondary schools and hospitals; the review statistics show how medians move.
