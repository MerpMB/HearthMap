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

# (column-name regex, lineage). Every artifact column must match one rule; the first match wins.
_RES = {"cell": "CELL_500M", "tambon": "TAMBON_ADMINISTRATIVE", "none": "NOT_SPATIAL"}
COLUMN_LINEAGE_RULES: list[tuple[str, dict[str, str]]] = [
    (
        r"^(cell_id|majority_pcode|coverage_fraction)$",
        {
            "family": "GRID",
            "sources": "analysis_grid_500m (M1A)",
            "evidence_type": "GRID_KEY",
            "spatial_resolution": _RES["cell"],
        },
    ),
    (
        r"^(population|built)_.*_full_cell_context$",
        {
            "family": "SETTLEMENT",
            "sources": "population-worldpop-r2025a; builtup-ghsl-r2023a",
            "evidence_type": "FULL_CELL_CONTEXT_ONLY",
            "evidence_footprint": "GRID_FOOTPRINT",
            "spatial_resolution": _RES["cell"],
            "note": "summed over the whole 500 m cell including any part outside the AOI; never an AOI analytical value",
        },
    ),
    (
        r"^population_",
        {
            "family": "SETTLEMENT",
            "sources": "population-worldpop-r2025a",
            "evidence_type": "POPULATION_INTENSITY_EVIDENCE",
            "evidence_footprint": "AOI_ANALYTICAL_FOOTPRINT",
            "spatial_resolution": _RES["cell"],
            "product_class": "MODELLED_POPULATION_ESTIMATE",
            "worldpop_depends_partly_on_ghsl": "true",
        },
    ),
    (
        r"^built_",
        {
            "family": "SETTLEMENT",
            "sources": "builtup-ghsl-r2023a",
            "evidence_type": "BUILT_FORM_INTENSITY_EVIDENCE",
            "evidence_footprint": "AOI_ANALYTICAL_FOOTPRINT",
            "spatial_resolution": _RES["cell"],
            "note": "GHSL is a covariate of the WorldPop model: not independent of population",
        },
    ),
    (
        r"^road_density_",
        {
            "family": "SETTLEMENT",
            "sources": "osm network (M2A cache)",
            "evidence_type": "ROAD_NETWORK_DENSITY_CONTEXT",
            "spatial_resolution": _RES["cell"],
        },
    ),
    (
        r"^settlement_",
        {
            "family": "SETTLEMENT",
            "sources": "population-worldpop-r2025a; builtup-ghsl-r2023a",
            "evidence_type": "SIGNAL_COMPARISON_DESCRIPTIVE",
            "spatial_resolution": _RES["cell"],
            "note": "partly dependent sources; descriptive agreement only",
        },
    ),
    (
        r"^osm_service_poi_",
        {
            "family": "POI_INTENSITY",
            "sources": "osm-service-pois-aoi",
            "evidence_type": "DESCRIPTIVE_CONTEXT",
            "spatial_resolution": _RES["cell"],
            "note": "OSM completeness is spatially uneven; not peacefulness and not urban-core truth",
        },
    ),
    (
        r"^(service_|drive_time_to_nearest_service_|network_distance_to_nearest_service_|nearest_service_|route_available_service_)",
        {
            "family": "TOWN_SERVICES",
            "sources": "osm-service-pois-aoi; osm network (M2A cache)",
            "evidence_type": "SERVICE_COMPONENT_ACCESS_BASELINE_DRIVE_TIME",
            "spatial_resolution": _RES["cell"],
        },
    ),
    (
        r"^nightlife_",
        {
            "family": "NIGHTLIFE_CANDIDATES",
            "sources": "osm-service-pois-aoi",
            "evidence_type": "OSM_TAG_CANDIDATE_CONTEXT",
            "spatial_resolution": _RES["cell"],
        },
    ),
    (
        r"^diw_",
        {
            "family": "INDUSTRY",
            "sources": "industry-diw-factories; boundaries-ocha-cod-ab",
            "evidence_type": "REGISTER_TAMBON_ADMIN_CONTEXT",
            "spatial_resolution": _RES["tambon"],
            "note": "a cell inherits its tambon value; it does not mean a factory is near the cell",
        },
    ),
    (
        r"^osm_(industrial|works)_",
        {
            "family": "INDUSTRY",
            "sources": "osm-industry-geom-aoi",
            "evidence_type": "OSM_GEOMETRY_CONTEXT",
            "spatial_resolution": "OSM_GEOMETRY",
        },
    ),
    (
        r"^osm_quarry_",
        {
            "family": "MINING_QUARRY",
            "sources": "osm-industry-geom-aoi",
            "evidence_type": "OSM_GEOMETRY_CONTEXT",
            "spatial_resolution": "OSM_GEOMETRY",
        },
    ),
    (
        r"^dpim_",
        {
            "family": "MINING_QUARRY",
            "sources": "mining-dpim-licence-exports; boundaries-ocha-cod-ab",
            "evidence_type": "LICENCE_REGISTER_TAMBON_ADMIN_CONTEXT",
            "spatial_resolution": _RES["tambon"],
            "note": "licence status is not current operating status; a cell inherits its tambon value",
        },
    ),
    (
        r"^legacy_dpim_",
        {
            "family": "MINING_QUARRY",
            "sources": "mining-dpim-concessions (2016 snapshot)",
            "evidence_type": "LEGACY_CONTEXT",
            "spatial_resolution": _RES["tambon"],
        },
    ),
    (
        r"^(road_snap_distance_m|routing_basis|routing_config_fingerprint)$",
        {
            "family": "ROUTING",
            "sources": "osm network (M2A cache); config/family-infrastructure.yaml",
            "evidence_type": "ROUTING_BASIS",
            "spatial_resolution": _RES["cell"],
        },
    ),
    (
        r"^(evidence_|scope_)",
        {
            "family": "COMPLETENESS",
            "sources": "derived from the columns of this artifact",
            "evidence_type": "EVIDENCE_COMPLETENESS_STATE",
            "spatial_resolution": _RES["none"],
        },
    ),
]
