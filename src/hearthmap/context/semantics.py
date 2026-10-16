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


# (column-name regex, lineage). Every artifact column must match one rule; the first match wins.
COLUMN_LINEAGE_RULES: list[tuple[str, dict[str, str]]] = [
    (
        r"^(cell_id|majority_pcode|coverage_fraction)$",
        {"family": "GRID", "sources": "analysis_grid_500m (M1A)", "evidence_type": "GRID_KEY"},
    ),
    (
        r"^population_",
        {
            "family": "SETTLEMENT",
            "sources": "population-worldpop-r2025a",
            "evidence_type": "POPULATION_INTENSITY_EVIDENCE",
        },
    ),
    (
        r"^built_",
        {
            "family": "SETTLEMENT",
            "sources": "builtup-ghsl-r2023a",
            "evidence_type": "BUILT_FORM_INTENSITY_EVIDENCE",
        },
    ),
    (
        r"^road_density_",
        {
            "family": "SETTLEMENT",
            "sources": "osm network (M2A cache)",
            "evidence_type": "ROAD_NETWORK_DENSITY_CONTEXT",
        },
    ),
    (
        r"^settlement_",
        {
            "family": "SETTLEMENT",
            "sources": "population-worldpop-r2025a; builtup-ghsl-r2023a",
            "evidence_type": "SIGNAL_COMPARISON_DESCRIPTIVE",
        },
    ),
    (
        r"^(service_|drive_time_to_nearest_service_|network_distance_to_nearest_service_|nearest_service_|route_available_service_)",
        {
            "family": "TOWN_SERVICES",
            "sources": "osm-service-pois-aoi; osm network (M2A cache)",
            "evidence_type": "SERVICE_COMPONENT_ACCESS_BASELINE_DRIVE_TIME",
        },
    ),
    (
        r"^nightlife_",
        {
            "family": "NIGHTLIFE_CANDIDATES",
            "sources": "osm-service-pois-aoi",
            "evidence_type": "OSM_TAG_CANDIDATE_CONTEXT",
        },
    ),
    (
        r"^diw_",
        {
            "family": "INDUSTRY",
            "sources": "industry-diw-factories; boundaries-ocha-cod-ab",
            "evidence_type": "REGISTER_TAMBON_LEVEL_CONTEXT",
        },
    ),
    (
        r"^osm_(industrial|works)_",
        {
            "family": "INDUSTRY",
            "sources": "osm-industry-aoi",
            "evidence_type": "OSM_LANDUSE_CONTEXT",
        },
    ),
    (
        r"^osm_quarry_",
        {
            "family": "MINING_QUARRY",
            "sources": "osm-industry-aoi",
            "evidence_type": "OSM_LANDUSE_CONTEXT",
        },
    ),
    (
        r"^legacy_dpim_",
        {
            "family": "MINING_QUARRY",
            "sources": "mining-dpim-concessions (2016 snapshot)",
            "evidence_type": "LEGACY_CONTEXT",
        },
    ),
    (
        r"^(road_snap_distance_m|routing_basis|routing_config_fingerprint)$",
        {
            "family": "ROUTING",
            "sources": "osm network (M2A cache); config/family-infrastructure.yaml",
            "evidence_type": "ROUTING_BASIS",
        },
    ),
    (
        r"^(evidence_|scope_)",
        {
            "family": "COMPLETENESS",
            "sources": "derived from the columns of this artifact",
            "evidence_type": "EVIDENCE_COMPLETENESS_STATE",
        },
    ),
]
