"""Machine-readable data-source registry (docs/research/data-source-registry.md)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml
from hearthmap.enums import Confidence, VerificationStatus

DEFAULT_REGISTRY_PATH = Path("docs/research/data-source-registry.yaml")


class SourceCategory(StrEnum):
    BOUNDARIES = "boundaries"
    ELEVATION = "elevation"
    FLOOD = "flood"
    LANDSLIDE = "landslide"
    SEISMIC = "seismic"
    HYDROLOGY = "hydrology"
    PROTECTED_LAND = "protected_land"
    LAND_RIGHTS = "land_rights"
    PLANNING = "planning"
    LAND_USE = "land_use"
    ROADS = "roads"
    EDUCATION = "education"
    HEALTH = "health"
    ELECTRICITY = "electricity"
    WATER = "water"
    TELECOM = "telecom"
    LAND_VALUE = "land_value"
    SAFETY = "safety"
    INFRASTRUCTURE_PROJECTS = "infrastructure_projects"
    ENVIRONMENT = "environment"
    POPULATION = "population"


class ProcessingStatus(StrEnum):
    NOT_ACQUIRED = "NOT_ACQUIRED"
    ACQUIRED = "ACQUIRED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REJECTED = "REJECTED"


class DataSourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    category: SourceCategory
    priority: Literal["must_have", "useful", "later"]
    verification_status: VerificationStatus
    publisher: str | None = None
    source_url: str | None = None
    access_method: str | None = None
    format: str | None = None
    coverage: str | None = None
    spatial_resolution: str | None = None
    temporal_coverage: str | None = None
    last_verified: dt.date | None = None
    license_or_usage_notes: str | None = None
    expected_update_frequency: str | None = None
    confidence: Confidence = Confidence.UNKNOWN
    known_limitations: list[str] = Field(default_factory=list)
    local_raw_path: str | None = None
    processing_status: ProcessingStatus = ProcessingStatus.NOT_ACQUIRED
    notes: str | None = None

    @model_validator(mode="after")
    def _state_rules(self) -> DataSourceEntry:
        if self.verification_status is VerificationStatus.VERIFIED:
            missing = [f for f in ("last_verified", "source_url") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"{self.id}: VERIFIED entries require {missing}")
        if self.confidence is not Confidence.UNKNOWN and (
            self.last_verified is None
            or self.verification_status is VerificationStatus.NEEDS_RESEARCH
        ):
            raise ValueError(
                f"{self.id}: confidence {self.confidence} claims the data was assessed; "
                "set last_verified and at least CANDIDATE status, or keep UNKNOWN"
            )
        needs_path = self.processing_status not in (
            ProcessingStatus.NOT_ACQUIRED,
            ProcessingStatus.REJECTED,
        )
        if needs_path and not self.local_raw_path:
            raise ValueError(
                f"{self.id}: processing_status {self.processing_status} requires local_raw_path"
            )
        return self


class DataSourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    sources: list[DataSourceEntry]

    @model_validator(mode="after")
    def _unique_ids(self) -> DataSourceRegistry:
        ids = [s.id for s in self.sources]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate source ids: {dupes}")
        return self

    def get(self, source_id: str) -> DataSourceEntry:
        for entry in self.sources:
            if entry.id == source_id:
                return entry
        raise KeyError(f"unknown data source id: {source_id!r}")

    def __contains__(self, source_id: object) -> bool:
        return any(entry.id == source_id for entry in self.sources)

    def by_status(self, status: VerificationStatus) -> list[DataSourceEntry]:
        return [s for s in self.sources if s.verification_status is status]


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> DataSourceRegistry:
    try:
        return DataSourceRegistry.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid data-source registry {path}:\n{exc}") from exc
