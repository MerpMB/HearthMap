"""Shared vocabularies used across config, provenance and scoring."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum


class Confidence(StrEnum):
    """Ordinal confidence in a source, derived layer or score.

    ``UNKNOWN`` means "not assessed / no evidence" and ranks *below* ``LOW`` for
    aggregation: missing knowledge must never look better than weak knowledge.
    """

    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    @property
    def rank(self) -> int:
        return _CONFIDENCE_RANK[self]

    @classmethod
    def weakest(cls, values: Iterable[Confidence]) -> Confidence:
        """Weakest-link aggregation (ADR-0005). Empty input yields ``UNKNOWN``."""
        values = list(values)
        if not values:
            return cls.UNKNOWN
        return min(values, key=lambda c: c.rank)


_CONFIDENCE_RANK = {
    Confidence.UNKNOWN: 0,
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
}


class VerificationStatus(StrEnum):
    """How far a fact (dataset, code, URL) has been checked by a human."""

    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"
    NEEDS_RESEARCH = "NEEDS_RESEARCH"
