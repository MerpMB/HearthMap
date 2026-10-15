"""Data contracts for hard constraints, component scores and assessments.

These are plain per-unit records (no GeoPandas) so the same engine can score
grid cells, zones or - later - parcels.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hearthmap.enums import Confidence


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConstraintOutcome(StrEnum):
    PASS = "PASS"
    # Definitive: evidence is authoritative enough to exclude. Always -> EXCLUDED.
    FAIL = "FAIL"
    # Evidence indicates the condition, but the evidence cannot certify it
    # (screening geometry, approximate legal boundary). Never -> EXCLUDED.
    FLAG = "FLAG"
    # Not evaluated, or evidence insufficient. Never treated as PASS.
    UNKNOWN = "UNKNOWN"


class EvidenceClass(StrEnum):
    """What a hard-constraint result is allowed to mean (docs/product/legal-vs-screening.md)."""

    # Authoritative evidence, for a constraint configured to permit exclusion.
    DEFINITIVE_EXCLUSION = "DEFINITIVE_EXCLUSION"
    # Approximate/indicative evidence (e.g. coarse hazard mapping): investigate.
    SCREENING_WARNING = "SCREENING_WARNING"
    # Apparent legal restriction from GIS that must be confirmed against
    # authoritative land documents / officials before any conclusion.
    REQUIRES_LEGAL_VERIFICATION = "REQUIRES_LEGAL_VERIFICATION"


_FLAG_CLASSES = {EvidenceClass.SCREENING_WARNING, EvidenceClass.REQUIRES_LEGAL_VERIFICATION}


class EligibilityStatus(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    UNRESOLVED = "UNRESOLVED"


class HardConstraintResult(_Model):
    constraint_id: str
    outcome: ConstraintOutcome
    reason: str
    evidence_class: EvidenceClass | None = None
    confidence: Confidence = Confidence.UNKNOWN
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _outcome_matches_evidence(self) -> HardConstraintResult:
        ec = self.evidence_class
        if self.outcome is ConstraintOutcome.FAIL and ec is not EvidenceClass.DEFINITIVE_EXCLUSION:
            raise ValueError(
                f"{self.constraint_id}: FAIL requires evidence_class DEFINITIVE_EXCLUSION; "
                "use FLAG for screening or legal-verification evidence"
            )
        if self.outcome is ConstraintOutcome.FLAG and ec not in _FLAG_CLASSES:
            raise ValueError(
                f"{self.constraint_id}: FLAG requires evidence_class SCREENING_WARNING or "
                "REQUIRES_LEGAL_VERIFICATION"
            )
        if (
            self.outcome in (ConstraintOutcome.PASS, ConstraintOutcome.UNKNOWN)
            and ec is EvidenceClass.DEFINITIVE_EXCLUSION
        ):
            raise ValueError(f"{self.constraint_id}: DEFINITIVE_EXCLUSION only accompanies FAIL")
        return self


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
    # "definitive" = a FAIL; "conservative_policy" = UNKNOWNs excluded by strict policy.
    exclusion_basis: Literal["definitive", "conservative_policy"] | None = None
    unresolved_constraints: list[HardConstraintResult] = Field(default_factory=list)
    # Screening / legal-verification hits: investigate, never auto-excluded.
    flags: list[HardConstraintResult] = Field(default_factory=list)
    # How the total was formed: all weighted dimensions present, renormalised, or none.
    score_basis: Literal["complete", "renormalized", "none"] = "none"
    # Whether this unit may take part in normal cross-unit ranking.
    rankable: bool = False
    missing_components: list[str] = Field(default_factory=list)
    confidence: Confidence
    notes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return self.status is EligibilityStatus.ELIGIBLE
