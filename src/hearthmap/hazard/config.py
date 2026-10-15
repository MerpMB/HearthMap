"""Validated hazard-evidence configuration (config/hazard.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TerrainInterp(_M):
    high_slope_p90_deg: float = Field(gt=0, lt=90)
    caution_slope_p90_deg: float = Field(gt=0, lt=90)


class TerrainCfg(_M):
    min_support_px: float = Field(gt=0)
    low_support_px: float = Field(gt=0)
    slope_thresholds_deg: list[float]
    interpretation: TerrainInterp


class FloodInterp(_M):
    high_recurrence_years: int = Field(ge=1)
    high_min_area_fraction: float = Field(gt=0, le=1)
    caution_min_area_fraction: float = Field(gt=0, le=1)
    caution_distance_m: float = Field(ge=0)


class FloodSource(_M):
    """What a flood indicator means: source, period and source-native metric."""

    source_id: str
    role: Literal["PRIMARY_HISTORICAL_FLOOD_EVIDENCE", "HISTORICAL_CORROBORATION"]
    evidence_period: str
    record_years: int = Field(ge=1)
    source_native_metric: str
    source_native_semantics: str
    used_for_interpretation: bool


class FloodCfg(_M):
    primary_source: FloodSource
    legacy_source: FloodSource
    interpretation: FloodInterp

    @model_validator(mode="after")
    def _semantics(self) -> FloodCfg:
        if not self.primary_source.used_for_interpretation:
            raise ValueError("the primary flood source must be the one interpreted")
        if self.legacy_source.used_for_interpretation:
            raise ValueError("the legacy flood source is corroboration/context only")
        if self.interpretation.high_recurrence_years > self.primary_source.record_years:
            raise ValueError("high_recurrence_years exceeds the primary record length")
        return self


class LandslideInterp(_M):
    high_very_high_min_fraction: float = Field(gt=0, le=1)
    high_high_or_above_min_fraction: float = Field(gt=0, le=1)
    caution_high_or_above_min_fraction: float = Field(gt=0, le=1)
    caution_medium_or_above_min_fraction: float = Field(gt=0, le=1)
    caution_inventory_points: int = Field(ge=1)


class LandslideCfg(_M):
    min_assessed_fraction: float = Field(gt=0, le=1)
    interpretation: LandslideInterp


class ExperimentalRule(_M):
    field: str
    thresholds: list[float] | None = None
    thresholds_below: list[float] | None = None


class Gates(_M):
    m1a1_human_visual_signoff: Literal["PENDING", "PASSED"]
    m1b_human_visual_signoff: Literal["PENDING", "PASSED"] = "PENDING"


class HazardConfig(_M):
    schema_version: Literal[1]
    status: Literal["PROVISIONAL", "ACCEPTED"]
    gates: Gates
    terrain: TerrainCfg
    flood: FloodCfg
    landslide: LandslideCfg
    experimental_exclusion_candidates: dict[str, ExperimentalRule]


def load_hazard_config(path: Path | str = "config/hazard.yaml") -> HazardConfig:
    try:
        return HazardConfig.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid hazard configuration {path}:\n{exc}") from exc
