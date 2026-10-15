"""Hazard evidence engine (M1B): indicators, provisional interpretation, experimental rules."""

from hearthmap.hazard.config import HazardConfig, load_hazard_config
from hearthmap.hazard.evidence import (
    CONTEXT_COLUMNS,
    DEPRECATED_TERMS,
    EXPERIMENTAL_SOURCE_PREFIX,
    HAZARD_LABELS,
    INTERPRETATION_INPUTS,
    OVERALL_LABELS,
    EvidenceLevel,
    EvidenceTier,
    experimental_candidates,
    interpret,
    threshold_sensitivity,
)

__all__ = [
    "CONTEXT_COLUMNS",
    "DEPRECATED_TERMS",
    "EXPERIMENTAL_SOURCE_PREFIX",
    "HAZARD_LABELS",
    "INTERPRETATION_INPUTS",
    "OVERALL_LABELS",
    "EvidenceLevel",
    "EvidenceTier",
    "HazardConfig",
    "experimental_candidates",
    "interpret",
    "load_hazard_config",
    "threshold_sensitivity",
]
