"""Configuration loading and validation."""

from hearthmap.config.loader import (
    ConfigError,
    ProjectConfig,
    load_project_config,
    load_regions,
    load_scoring,
    load_spatial,
)
from hearthmap.config.models import (
    CRSConfig,
    DimensionConfig,
    GridConfig,
    HardConstraintConfig,
    RegionConfig,
    RegionsConfig,
    ScoringConfig,
    ScoringPolicies,
    SpatialConfig,
)

__all__ = [
    "CRSConfig",
    "ConfigError",
    "DimensionConfig",
    "GridConfig",
    "HardConstraintConfig",
    "ProjectConfig",
    "RegionConfig",
    "RegionsConfig",
    "ScoringConfig",
    "ScoringPolicies",
    "SpatialConfig",
    "load_project_config",
    "load_regions",
    "load_scoring",
    "load_spatial",
]
