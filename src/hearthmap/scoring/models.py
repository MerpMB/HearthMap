"""Data contracts for hard constraints, component scores and assessments.

These are plain per-unit records (no GeoPandas) so the same engine can score
grid cells, zones or - later - parcels.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from hearthmap.enums import Confidence


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConstraintOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    # Not evaluated, or evidence insufficient. Never treated as PASS.
    UNKNOWN = "UNKNOWN"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    UNRESOLVED = "UNRESOLVED"


class HardConstraintResult(_Model):
    constraint_id: str
    outcome: ConstraintOutcome
    reason: str
    confidence: Confidence = Confidence.UNKNOWN
    source_ids: list[str] = Field(default_factory=list)


class ComponentScore(_Model):
    """A normalised 0-100 score for one dimension (100 = most suitable).

    ``value=None`` means the component could not be computed; it is handled by
    the ``missing_component`` policy, never silently treated as 0 or 100.
    """

    dimension_id: str
    value: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    confidence: Confidence = Confidence.UNKNOWN
    reasons: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class Assessment(_Model):
    """Full, explainable result for one spatial unit."""

    unit_id: str
    model_id: str
    model_version: str
    status: EligibilityStatus
    # None when EXCLUDED, or when components are missing under the active policy.
    suitability_score: float | None
    components: dict[str, ComponentScore]
    weights: dict[str, float]
    # Share of total (normalised) weight backed by an available component, 0..1.
    coverage: float
    exclusion_reasons: list[HardConstraintResult] = Field(default_factory=list)
    unresolved_constraints: list[HardConstraintResult] = Field(default_factory=list)
    missing_components: list[str] = Field(default_factory=list)
    confidence: Confidence
    notes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE
