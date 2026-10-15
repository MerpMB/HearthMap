"""Machine-readable data-source registry (docs/research/data-source-registry.md)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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


class SourceRole(StrEnum):
    """Role of a source among alternatives for the same theme."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    VALIDATION_ONLY = "VALIDATION_ONLY"


class AcquisitionStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    ACQUIRED = "ACQUIRED"
    DEFERRED = "DEFERRED"
    BLOCKED_CREDENTIAL_REQUIRED = "BLOCKED_CREDENTIAL_REQUIRED"
    BLOCKED_SIZE_GUARD = "BLOCKED_SIZE_GUARD"


class SourceState(StrEnum):
    """Whether a source exists and whether the AGENT environment can reach it (M2A.2).

    A source an agent cannot reach is not an unavailable source: do not conflate them.
    """

    SOURCE_EXISTS_AGENT_ACCESSIBLE = "SOURCE_EXISTS_AGENT_ACCESSIBLE"
    SOURCE_EXISTS_AGENT_BLOCKED = "SOURCE_EXISTS_AGENT_BLOCKED"
    SOURCE_MANUALLY_ACQUIRED = "SOURCE_MANUALLY_ACQUIRED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class PermittedUse(StrEnum):
    """What a source may be used for (docs/product/legal-vs-screening.md)."""

    REGIONAL_SCREENING = "REGIONAL_SCREENING"
    POTENTIAL_HARD_EXCLUSION = "POTENTIAL_HARD_EXCLUSION"
    LEGAL_WARNING_ONLY = "LEGAL_WARNING_ONLY"
    PARCEL_LEGAL_VERIFICATION = "PARCEL_LEGAL_VERIFICATION"
    VALIDATION_REFERENCE = "VALIDATION_REFERENCE"


_VERIFIED_REQUIRED = (
    "last_verified",
    "publisher",
    "dataset_title",
    "landing_page",
    "data_endpoint",
    "format",
    "source_crs",
    "license_or_usage_notes",
    "verification_evidence",
)


class DataSourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    category: SourceCategory
    priority: Literal["must_have", "useful", "later"]
    verification_status: VerificationStatus
    role: SourceRole | None = None
    # Evidence role within a theme, e.g. TEMPORARY_HISTORICAL_EVIDENCE (current
    # use) vs PRIMARY_HISTORICAL_FLOOD_EVIDENCE (intended once acquirable).
    evidence_role: str | None = None
    intended_role: str | None = None
    metadata_verified: bool = False
    data_verified: bool = False
    acquisition_status: AcquisitionStatus | None = None
    # M2A.2: existence vs agent reachability, and the lawful way to obtain a blocked source.
    source_state: SourceState | None = None
    acquisition_path: str | None = None
    permitted_uses: list[PermittedUse] = Field(default_factory=list)
    publisher: str | None = None
    dataset_title: str | None = None
    landing_page: str | None = None
    data_endpoint: str | None = None
    access_method: str | None = None
    access_restrictions: str | None = None
    source_crs: str | None = None
    format: str | None = None
    coverage: str | None = None
    spatial_resolution: str | None = None
    temporal_coverage: str | None = None
    last_update: str | None = None
    last_verified: dt.date | None = None
    # What was actually inspected to verify (a working URL alone is not verification).
    verification_evidence: str | None = None
    redirects_or_changes: str | None = None
    analytical_suitability: str | None = None
    license_or_usage_notes: str | None = None
    # Where terms differ, keep them apart (M1D): dataset licence, service terms, legal-use
    # disclaimer, and the recorded discrepancy between catalogues.
    dataset_licence: str | None = None
    service_terms: str | None = None
    legal_use_disclaimer: str | None = None
    licence_discrepancy: str | None = None
    methodology: str | None = None
    expected_update_frequency: str | None = None
    confidence: Confidence = Confidence.UNKNOWN
    known_limitations: list[str] = Field(default_factory=list)
    local_raw_path: str | None = None
    processing_status: ProcessingStatus = ProcessingStatus.NOT_ACQUIRED
    notes: str | None = None

    @model_validator(mode="after")
    def _state_rules(self) -> DataSourceEntry:
        if self.verification_status is VerificationStatus.VERIFIED:
            missing = [f for f in _VERIFIED_REQUIRED if not getattr(self, f)]
            if not self.permitted_uses:
                missing.append("permitted_uses")
            if missing:
                raise ValueError(f"{self.id}: VERIFIED entries require {missing}")
        if self.verification_status is VerificationStatus.VERIFIED and not (
            self.metadata_verified and self.data_verified
        ):
            raise ValueError(f"{self.id}: VERIFIED requires metadata_verified and data_verified")
        if self.data_verified and not self.metadata_verified:
            raise ValueError(f"{self.id}: data_verified requires metadata_verified")
        if self.data_verified and self.acquisition_status not in (None, AcquisitionStatus.ACQUIRED):
            raise ValueError(f"{self.id}: data_verified requires the data to be acquired")
        if self.source_state is SourceState.SOURCE_MANUALLY_ACQUIRED and not (
            self.local_raw_path and self.acquisition_status is AcquisitionStatus.ACQUIRED
        ):
            raise ValueError(
                f"{self.id}: SOURCE_MANUALLY_ACQUIRED requires acquired data and local_raw_path"
            )
        if self.source_state is SourceState.SOURCE_EXISTS_AGENT_BLOCKED and self.data_verified:
            raise ValueError(
                f"{self.id}: a source the agent could not reach cannot be data_verified"
            )
        if self.source_state is SourceState.SOURCE_UNAVAILABLE and not self.verification_evidence:
            raise ValueError(
                f"{self.id}: SOURCE_UNAVAILABLE must cite the evidence that it does not exist"
            )
        if PermittedUse.PARCEL_LEGAL_VERIFICATION in self.permitted_uses and (
            PermittedUse.LEGAL_WARNING_ONLY in self.permitted_uses
        ):
            raise ValueError(f"{self.id}: a LEGAL_WARNING_ONLY source cannot verify parcels")
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

    def permits(self, source_id: str, use: PermittedUse) -> bool:
        entry = self.get(source_id)
        return (
            entry.verification_status is VerificationStatus.VERIFIED and use in entry.permitted_uses
        )

    def by_status(self, status: VerificationStatus) -> list[DataSourceEntry]:
        return [s for s in self.sources if s.verification_status is status]


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> DataSourceRegistry:
    # Imported lazily: config depends on spatial, which depends on provenance.
    from hearthmap.config.loader import ConfigError, load_yaml

    try:
        return DataSourceRegistry.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid data-source registry {path}:\n{exc}") from exc
