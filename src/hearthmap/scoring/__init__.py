"""Hard-constraint exclusion and weighted suitability scoring (skeleton)."""

from hearthmap.scoring.engine import ScoringInputError, ScoringModel
from hearthmap.scoring.explain import render_explanation
from hearthmap.scoring.models import (
    Assessment,
    ComponentScore,
    ConstraintOutcome,
    EligibilityStatus,
    EvidenceClass,
    HardConstraintResult,
)

__all__ = [
    "Assessment",
    "ComponentScore",
    "ConstraintOutcome",
    "EligibilityStatus",
    "EvidenceClass",
    "HardConstraintResult",
    "ScoringInputError",
    "ScoringModel",
    "render_explanation",
]
