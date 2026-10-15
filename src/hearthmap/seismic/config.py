"""Validated seismic evidence configuration (config/seismic-evidence.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml

FORBIDDEN_SEISMIC_WORDS = ("EARTHQUAKE_SAFE", "NO_EARTHQUAKE_RISK", "FAULT_SAFE", "SAFE")
INTERPRETATION_STATES = (
    "NO_MAJOR_SEISMIC_CONCERN_DETECTED",
    "REQUIRES_SEISMIC_VERIFICATION",
    "STRONG_SEISMIC_SCREENING_CONCERN",
    "UNRESOLVED",
)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FaultRule(_M):
    verify_within_km: float = Field(gt=0)
    strong_tier_within_km: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> FaultRule:
        if self.strong_tier_within_km > self.verify_within_km:
            raise ValueError("fault strong-tier distance must not exceed the verify distance")
        return self


class ShakingRule(_M):
    class_tier1: str
    class_tier2: str
    tier1_min_fraction: float = Field(gt=0, le=1)
    tier2_min_fraction: float = Field(gt=0, le=1)
    min_assessed_fraction: float = Field(gt=0, le=1)


class HistoryRule(_M):
    magnitude: float = Field(gt=0)
    tier1_within_km: float = Field(gt=0)
    tier2_within_km: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> HistoryRule:
        if self.tier2_within_km > self.tier1_within_km:
            raise ValueError("history tier-2 distance must not exceed the tier-1 distance")
        return self


class Interpretation(_M):
    strong_requires_families: int = Field(ge=2, le=3)
    single_family_max_level: Literal["VERIFY"]
    fault: FaultRule
    shaking: ShakingRule
    history: HistoryRule


class GroundResponse(_M):
    status: Literal["NOT_ASSESSED"]
    available_evidence: list[str]
    missing_evidence: list[str] = Field(min_length=1)


class SeismicConfig(_M):
    schema_version: Literal[1]
    seismic_id: str
    seismic_version: str
    status: Literal["PROVISIONAL"]
    experimental: Literal[True]
    default_policy: None
    reporting_radii_km: list[float]
    history_magnitude_thresholds: list[float]
    sources: dict
    interpretation: Interpretation
    confidence: dict[str, dict[str, str]]
    decision_confidence: Literal["LOW"]
    ground_response: GroundResponse
    prohibited_evidence_columns: list[str]
    reason_codes: dict[str, str]

    @model_validator(mode="after")
    def _guards(self) -> SeismicConfig:
        if self.interpretation.history.magnitude not in self.history_magnitude_thresholds:
            raise ValueError("history.magnitude must be one of history_magnitude_thresholds")
        classes = self.sources["intensity_zones"]["classes"]
        for c in (self.interpretation.shaking.class_tier1, self.interpretation.shaking.class_tier2):
            if c not in classes:
                raise ValueError(f"shaking class {c} is not a publisher MMI class")
        if self.ground_response.available_evidence:
            raise ValueError("ground-response evidence cannot be claimed in v0.1")
        for state in INTERPRETATION_STATES:
            for w in FORBIDDEN_SEISMIC_WORDS:
                if w in state.split("_") and w != "SAFE":
                    raise ValueError(f"state {state} uses forbidden wording")
        for code in self.reason_codes:
            for w in FORBIDDEN_SEISMIC_WORDS:
                if w in code or w in code.split("_"):
                    raise ValueError(f"reason code {code} uses forbidden wording {w}")
        if "fault_distance_score" in str(self.model_dump()).lower():
            raise ValueError("a fault distance score is not allowed in M1D")
        needed = {
            "fault_context",
            "earthquake_hazard_zones",
            "historical_seismicity",
            "ground_response",
        }
        if set(self.confidence) != needed:
            raise ValueError("confidence must keep one entry per evidence family")
        for fam, dims in self.confidence.items():
            if set(dims) != {
                "source",
                "methodology",
                "spatial_completeness",
                "temporal_completeness",
            }:
                raise ValueError(f"{fam}: confidence dimensions must stay separate")
        return self


def load_seismic_config(path: Path | str = "config/seismic-evidence.yaml") -> SeismicConfig:
    try:
        return SeismicConfig.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid seismic config {path}:\n{exc}") from exc
