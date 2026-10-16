# ruff: noqa: E501
"""Vocabulary guards for the M2D regional-context artifact: what the evidence may and may not be called."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Any column whose name matches is a scoring/ranking/verdict column and is refused.
_FORBIDDEN = re.compile(
    r"(^|_)(score|rank|ranking|penalty|pass_fail|verdict|suitability|livability|peacefulness)(_|$)"
)

SCOPE_STATEMENTS = {
    "population": "Population intensity is a modelled count of people (WorldPop constrained, top-down, aligned to UN totals). It is not peacefulness, quiet, safety or livability.",
    "built_form": "Built-up surface is satellite-derived (GHS-BUILT-S, epoch 2020 interpolated from 2018 observations). It is not a building count and not population.",
    "services": "Service POIs are OpenStreetMap evidence. Absence of a POI is not absence of a service; no weighted service score exists and the 35-minute preference is not activated.",
    "industry": "A register entry (DIW) or an OSM industrial feature says a factory/land use is recorded. FACTORY_PRESENT is not NUISANCE_CONFIRMED; no exclusion buffer is authorised.",
    "mining": "DPIM concession records and OSM quarry polygons are context. An expired concession is not an active mine; no source here locates a stone-crushing plant to a point.",
    "nightlife": "Nightlife candidates are OSM bar/pub/nightclub/stripclub/karaoke_box tags only; restaurants are not nightlife and nuisance is not confirmed.",
    "hazard": "Natural Hazard scope: M1E hazard outputs are unchanged by M2D and carry their own scope statement (screening, not a parcel hazard determination).",
}


def forbidden_columns(columns: Iterable[str]) -> list[str]:
    """Columns that look like a score, rank, penalty or pass/fail verdict."""
    return [c for c in columns if _FORBIDDEN.search(c.lower())]


SOURCE_SEMANTICS = {
    "population": {
        "product_class": "MODELLED_POPULATION_ESTIMATE",
        "is_not": "census-observed population",
        "estimate_year": 2025,
        "release": "R2025A",
        "version": "v1",
        "resolution_approx_m": 100,
        "units": "people per pixel",
        "crs": "EPSG:4326",
        "product_status": "ALPHA",
        "doi": "10.5258/SOTON/WP00839",
        "worldpop_depends_partly_on_ghsl": True,
        "dependency_note": "WorldPop R2025A uses GHSL built-settlement layers, building footprints and other covariates in its built-settlement growth model, so WorldPop and GHS-BUILT-S are NOT fully independent sources. Their rank correlation is descriptive and is not cross-source corroboration or validation.",
    },
    "diw": {
        "row_level_status_field": False,
        "row_level_coordinates": False,
        "record_status": "UNKNOWN",
        "source_inclusion_semantics": "Catalogue data_source: factory database OUTSIDE industrial estates (class 2 and class 3; waste types 101/105/106 in a separate resource). Whether closed or cancelled factories are excluded is NOT documented for the acquired resources, so no record is ACTIVE.",
        "spatial_resolution": "TAMBON_ADMINISTRATIVE",
    },
    "dpim_licences": {
        "row_level_coordinates": False,
        "spatial_resolution": "TAMBON_ADMINISTRATIVE",
        "licence_status_is_current_operating_status": False,
        "stone_crushing_status_vocabulary_th": {
            "03": "เปิดการ",
            "02": "หยุดการ",
            "04": "ต่ออายุ",
            "06": "สิ้นอายุ",
            "01": "จำหน่ายทะเบียน",
            "08": "รอแจ้งประกอบกิจการ",
        },
        "date_semantics": "Buddhist-era dd/mm/yyyy (effective, expiry); an expiry date and the register status can disagree and are kept as separate fields.",
    },
    "dpim_open_api": {
        "spatial_resolution": "PROVINCE_ADMIN_CONTEXT",
        "may_be_mapped_to_cells": False,
    },
}

CANDIDATE_DEFINITION = "CANDIDATE_DEFINITION"

# Semantic classes of a field. A field says what it is: LOCAL evidence about the AOI, EXTERNAL access or influence context, or a mix that must be separated.
LOCAL_AOI_EVIDENCE = "LOCAL_AOI_EVIDENCE"
EXTERNAL_ACCESS_CONTEXT = "EXTERNAL_ACCESS_CONTEXT"
EXTERNAL_INFLUENCE_CONTEXT = "EXTERNAL_INFLUENCE_CONTEXT"
MIXED_REQUIRES_SEPARATION = "MIXED_REQUIRES_SEPARATION"
SEMANTIC_CLASSES = (
    LOCAL_AOI_EVIDENCE,
    EXTERNAL_ACCESS_CONTEXT,
    EXTERNAL_INFLUENCE_CONTEXT,
    MIXED_REQUIRES_SEPARATION,
)

_RES = {
    "cell": "CELL_500M",
    "tambon": "TAMBON_ADMINISTRATIVE",
    "none": "NOT_SPATIAL",
    "geom": "OSM_GEOMETRY",
}
_WP, _GH = "population-worldpop-r2025a", "builtup-ghsl-r2023a"


def _r(
    pattern: str, family: str, sources: str, etype: str, res: str, **extra: str
) -> tuple[str, dict[str, str]]:
    return pattern, {
        "family": family,
        "sources": sources,
        "evidence_type": etype,
        "spatial_resolution": res,
        **extra,
    }


# (column-name regex, lineage). Every artifact column must match one rule; the first match wins.
COLUMN_LINEAGE_RULES: list[tuple[str, dict[str, str]]] = [
    _r(
        r"^(cell_id|majority_pcode|coverage_fraction)$",
        "GRID",
        "analysis_grid_500m (M1A)",
        "GRID_KEY",
        _RES["cell"],
    ),
    _r(
        r"^(grid_centroid|analysis_point)_(lon|lat|method)$",
        "GRID",
        "analysis_grid_500m (M1A); AOI polygon (M1A boundaries)",
        "POINT_SEMANTICS",
        _RES["cell"],
        note="GRID_CENTROID is the nominal context point; AOI_ANALYSIS_POINT is the routing/distance origin (the centroid when it lies inside GRID_FOOTPRINT intersect AOI, otherwise a point-on-surface of that footprint)",
    ),
    _r(
        r"^(population|built)_.*_full_cell_context$",
        "SETTLEMENT",
        f"{_WP}; {_GH}",
        "FULL_CELL_CONTEXT_ONLY",
        _RES["cell"],
        evidence_footprint="GRID_FOOTPRINT",
        note="summed over the whole 500 m cell including any part outside the AOI; never an AOI analytical value",
    ),
    _r(
        r"^(population_worldpop2025_mass_aoi_clipped|built_ghsl2020_m2_aoi_clipped)$",
        "SETTLEMENT",
        f"{_WP}; {_GH}",
        "AOI_CLIPPED_MASS",
        _RES["cell"],
        semantic_class=LOCAL_AOI_EVIDENCE,
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        mass_class="POPULATION_MASS_AOI_CLIPPED (MODELLED_POPULATION_ESTIMATE) or BUILT_UP_M2_AOI_CLIPPED",
        worldpop_depends_partly_on_ghsl="true",
    ),
    _r(
        r"^(population|built)_.*intensity_",
        "SETTLEMENT",
        f"{_WP}; {_GH}",
        "INTENSITY_PER_NOMINAL_GRID_CELL",
        _RES["cell"],
        semantic_class=LOCAL_AOI_EVIDENCE,
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        denominator="nominal 0.25 km2 grid cell, NOT the AOI footprint",
        note="AOI-clipped numerator over the nominal cell area; an edge cell therefore reads lower than the local density of its AOI part, and this is not a density within the AOI footprint",
    ),
    _r(
        r"^population_",
        "SETTLEMENT",
        _WP,
        "POPULATION_INTENSITY_EVIDENCE",
        _RES["cell"],
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        product_class="MODELLED_POPULATION_ESTIMATE",
        worldpop_depends_partly_on_ghsl="true",
    ),
    _r(
        r"^built_",
        "SETTLEMENT",
        _GH,
        "BUILT_FORM_INTENSITY_EVIDENCE",
        _RES["cell"],
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        note="GHSL is a covariate of the WorldPop model: not independent of population",
    ),
    _r(
        r"^road_(length|intensity)_.*full_cell_context$",
        "SETTLEMENT",
        "osm network (M2A cache)",
        "FULL_CELL_CONTEXT_ONLY",
        _RES["cell"],
        evidence_footprint="GRID_FOOTPRINT",
        note="whole-cell road length including outside the AOI; context only",
    ),
    _r(
        r"^road_(length|intensity)_",
        "SETTLEMENT",
        "osm network (M2A cache)",
        "LOCAL_ROAD_CONTEXT",
        _RES["cell"],
        semantic_class=LOCAL_AOI_EVIDENCE,
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        note="drivable-road length inside the AOI (edge midpoint rule); the routing network itself extends beyond the AOI (ROUTING_NETWORK_EXTENT)",
    ),
    _r(
        r"^settlement_",
        "SETTLEMENT",
        f"{_WP}; {_GH}",
        "SIGNAL_COMPARISON_DESCRIPTIVE",
        _RES["cell"],
        note="partly dependent sources; descriptive agreement only",
    ),
    _r(
        r"^osm_service_poi_",
        "POI_INTENSITY",
        "osm-service-pois-aoi",
        "LOCAL_SERVICE_PRESENCE",
        _RES["cell"],
        semantic_class=LOCAL_AOI_EVIDENCE,
        note="only POIs inside the AOI count; OSM completeness is spatially uneven; not peacefulness and not urban-core truth",
    ),
    _r(
        r"^(service_|drive_time_to_nearest_service_|network_distance_to_nearest_service_|nearest_service_|route_available_service_)",
        "TOWN_SERVICES",
        "osm-service-pois-aoi; osm network (M2A cache)",
        "ACCESSIBLE_SERVICE_DESTINATION_BASELINE_DRIVE_TIME",
        _RES["cell"],
        semantic_class=EXTERNAL_ACCESS_CONTEXT,
        origin="AOI_ANALYSIS_POINT",
        note="destinations are all OSM POIs of the three provinces (including any outside the AOI polygon); destinations across the outer provincial borders are absent from the extract",
    ),
    _r(
        r"^nightlife_",
        "NIGHTLIFE_CANDIDATES",
        "osm-service-pois-aoi",
        "OSM_TAG_CANDIDATE_CONTEXT",
        _RES["cell"],
        semantic_class=EXTERNAL_INFLUENCE_CONTEXT,
        origin="AOI_ANALYSIS_POINT",
    ),
    _r(
        r"^diw_",
        "INDUSTRY",
        "industry-diw-factories; boundaries-ocha-cod-ab",
        "REGISTER_TAMBON_ADMIN_CONTEXT",
        _RES["tambon"],
        note="a cell inherits its tambon value; it does not mean a factory is near the cell",
    ),
    _r(
        r"^osm_(industrial|quarry)_.*polygon_fraction_of_nominal_grid_cell_aoi_clipped$",
        "INDUSTRY",
        "osm-industry-geom-aoi",
        "LOCAL_POLYGON_OCCUPANCY_AOI_CLIPPED",
        _RES["geom"],
        semantic_class=LOCAL_AOI_EVIDENCE,
        evidence_footprint="AOI_ANALYTICAL_FOOTPRINT",
        denominator="nominal 0.25 km2 grid cell",
        note="polygon intersect AOI intersect cell; a polygon wholly outside the AOI contributes nothing",
    ),
    _r(
        r"^osm_(industrial|works)_",
        "INDUSTRY",
        "osm-industry-geom-aoi",
        "EXTERNAL_INFLUENCE_CONTEXT",
        _RES["geom"],
        semantic_class=EXTERNAL_INFLUENCE_CONTEXT,
        origin="AOI_ANALYSIS_POINT",
        note="euclidean context from the AOI analysis point; features just outside the AOI may count; no nuisance distance or buffer is activated",
    ),
    _r(
        r"^osm_quarry_",
        "MINING_QUARRY",
        "osm-industry-geom-aoi",
        "EXTERNAL_INFLUENCE_CONTEXT",
        _RES["geom"],
        semantic_class=EXTERNAL_INFLUENCE_CONTEXT,
        origin="AOI_ANALYSIS_POINT",
        note="euclidean context from the AOI analysis point; features just outside the AOI may count; no nuisance distance or buffer is activated",
    ),
    _r(
        r"^dpim_",
        "MINING_QUARRY",
        "mining-dpim-licence-exports; boundaries-ocha-cod-ab",
        "LICENCE_REGISTER_TAMBON_ADMIN_CONTEXT",
        _RES["tambon"],
        note="licence status is not current operating status; a cell inherits its tambon value",
    ),
    _r(
        r"^legacy_dpim_",
        "MINING_QUARRY",
        "mining-dpim-concessions (2016 snapshot)",
        "LEGACY_CONTEXT",
        _RES["tambon"],
    ),
    _r(
        r"^(road_snap_distance_m|road_access_context|road_any_network_fragment_distance_m|routing_basis|routing_config_fingerprint)$",
        "ROUTING",
        "osm network (M2A cache); config/family-infrastructure.yaml",
        "ROUTING_BASIS",
        _RES["cell"],
        origin="AOI_ANALYSIS_POINT",
    ),
    _r(
        r"^(evidence_|scope_)",
        "COMPLETENESS",
        "derived from the columns of this artifact",
        "EVIDENCE_COMPLETENESS_STATE",
        _RES["none"],
    ),
]
