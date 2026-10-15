"""M2A family & infrastructure EVIDENCE (presence, accessibility, context). No scoring."""

from hearthmap.family.config import FamilyConfig, load_config
from hearthmap.family.dedup import deduplicate, normalise_name
from hearthmap.family.qa import coordinate_flags
from hearthmap.family.routing import Network, build_network, multi_source_dijkstra
from hearthmap.family.semantics import (
    FORBIDDEN_FIELDS,
    electricity_context,
    freshness,
    telecom_context,
    water_context,
)
from hearthmap.family.taxonomy import classify_education, classify_health

__all__ = [
    "FORBIDDEN_FIELDS",
    "FamilyConfig",
    "Network",
    "build_network",
    "classify_education",
    "classify_health",
    "coordinate_flags",
    "deduplicate",
    "electricity_context",
    "freshness",
    "load_config",
    "multi_source_dijkstra",
    "normalise_name",
    "telecom_context",
    "water_context",
]
