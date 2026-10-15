"""Load and validate YAML configuration files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from hearthmap.config.models import RegionsConfig, ScoringConfig, SpatialConfig

REGIONS_FILE = "regions.yaml"
SPATIAL_FILE = "spatial.yaml"
SCORING_FILE = "scoring.yaml"


class ConfigError(Exception):
    """A configuration file is missing, unreadable or invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a YAML mapping at top level")
    return data


def _load[M: BaseModel](path: Path, model: type[M]) -> M:
    try:
        return model.model_validate(load_yaml(path))
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration in {path}:\n{exc}") from exc


def load_regions(path: Path) -> RegionsConfig:
    return _load(path, RegionsConfig)


def load_spatial(path: Path) -> SpatialConfig:
    return _load(path, SpatialConfig)


def load_scoring(path: Path) -> ScoringConfig:
    return _load(path, ScoringConfig)


@dataclass(frozen=True)
class ProjectConfig:
    regions: RegionsConfig
    spatial: SpatialConfig
    scoring: ScoringConfig
    config_dir: Path


def load_project_config(config_dir: Path | str = "config") -> ProjectConfig:
    """Load all configuration files from ``config_dir``."""
    config_dir = Path(config_dir)
    return ProjectConfig(
        regions=load_regions(config_dir / REGIONS_FILE),
        spatial=load_spatial(config_dir / SPATIAL_FILE),
        scoring=load_scoring(config_dir / SCORING_FILE),
        config_dir=config_dir,
    )
