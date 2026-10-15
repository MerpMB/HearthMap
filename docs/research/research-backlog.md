# Research backlog — datasets to locate

Status: updated after M1A (2026-10-15). Registry ids refer to
[data-source-registry.yaml](data-source-registry.yaml).

## M1A outcome

| Theme | Result |
|---|---|
| Boundaries | VERIFIED + acquired: COD-AB (PRIMARY), GISTDA 1:50k (SECONDARY), geoBoundaries ADM1 (VALIDATION_ONLY). Official DOPA dataset still not found. |
| Elevation | VERIFIED + acquired: Copernicus GLO-30 (DSM). FABDEM evaluated, deferred (CC BY-NC-SA). |
| Flood | VERIFIED + acquired: GISTDA repeated flooding 2005–2016 (observed history). 2011–2023 recurrence and event layers need a GISTDA API key (blocked). Modelled hazard not researched yet. |
| Forest / protected | VERIFIED + acquired: RFD reserve forest (legal warning only), GISTDA-served MNRE parks 2014 + sanctuaries. Current DNP boundaries, ALRO and watershed classes still missing. |
| Roads / waterways | VERIFIED + acquired: OSM Overpass AOI subset. National Geofabrik extract rejected (size guard). |
| Landslide | Not started in M1A (still highest-uncertainty must-have). |

Legend: **Must-have** = blocks a hard constraint or core dimension.
**Useful** = materially improves a score. **Later** = enrichment.

## Priority order for M1

| # | Category | Must-have | Useful | Later enrichment | Registry ids |
|---|---|---|---|---|---|
| 1 | Provincial/admin boundaries | Province + district polygons (lineage + datum known) | Sub-district polygons; official set for cross-check | Village points | `boundaries-ocha-cod-ab`, `boundaries-geoboundaries`, `boundaries-thai-official` |
| 2 | DEM / elevation | 30 m DEM for slope + relative elevation | Bare-earth DEM (FABDEM) | Higher-res local DEMs/LiDAR if any | `dem-copernicus-glo30`, `dem-fabdem` |
| 3 | Flood hazard/history | Observed historical flood extents (multi-year) | Modelled flood hazard; surface-water recurrence | Local flood-mark/community records (M6) | `flood-gistda-history`, `flood-jrc-global-surface-water`, `flood-modelled-hazard` |
| 4 | Landslide | Mapped susceptibility polygons | Event inventory | Rainfall-threshold studies | `landslide-dmr-susceptibility`, `landslide-event-inventory` |
| 5 | Rivers/waterways | Main river network | Consistent stream order (HydroRIVERS) | Drainage channels / irrigation canals | `rivers-osm`, `rivers-hydrosheds` |
| 6 | Protected/restricted land | National parks, wildlife sanctuaries, forest reserves, ALRO land | Watershed classes; WDPA as cross-check | Community forests | `protected-dnp-boundaries`, `forest-reserve-rfd`, `land-reform-alro`, `watershed-classification`, `protected-wdpa` |
| 7 | Land-use planning | Comprehensive plan zoning where it exists (and explicit "no plan" extent) | Land-use/land-cover maps | Plan revision pipeline | `planning-comprehensive-plans`, `landuse-ldd` |
| 8 | Road networks | Road network with class (OSM) | Official road class/ownership | Surface/condition, rainy-season passability (field) | `roads-osm`, `roads-official-doh-drr` |
| 9 | Education | Schools with level + coordinates | Universities/vocational | Quality indicators, international/bilingual schools | `schools-official`, `universities` |
| 10 | Hospitals | Hospitals with emergency capability + coordinates | Health centres | Specialist services | `health-facilities-moph` |
| 11 | Electricity | — (grid is widespread; treat as field check) | Grid proximity / coverage | Outage statistics | `electricity-pea` |
| 12 | Water service | Piped water service areas | Village water systems | Groundwater quality/depth | `water-pwa-service` |
| 13 | Assessed land values | Official appraisal values (for M3) | Observed market prices (M5) | Time series | `land-value-treasury-appraisal` |
| 14 | Crime/safety | — | Official statistics at native resolution | — | `crime-police-statistics` |
| 15 | Major infrastructure projects | — | Rail alignment + stations; major road projects | Airport/logistics plans | `infra-rail-north`, `infra-road-projects` |
| 16 | Environmental nuisance | Quarries/mines/landfills/heavy industry (for `severe_nuisance`) | Burning hotspots; PM2.5 context; population density | Noise sources (airports, highways) | `nuisance-sources`, `fire-hotspots-firms`, `air-quality-pcd`, `population-grids` |

Also: `seismic-active-faults` (later; context signal), `telecom-ookla-open-data` (useful).

## Top 5 to acquire first

1. **Admin boundaries** — unblocks the real grid and every regional summary.
2. **DEM (Copernicus GLO-30)** — slope exclusion + relative elevation for flood context.
3. **Protected / forest-reserve / ALRO land** — likely removes the largest area; legally decisive.
4. **Historical flood extents** — core hazard exclusion.
5. **OSM extract (roads + waterways)** — one download, two must-have layers.

Landslide susceptibility is equally important but has the most uncertain
availability; research it in parallel.
