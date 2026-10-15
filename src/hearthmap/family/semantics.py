# ruff: noqa: E501
"""Evidence-state vocabularies for infrastructure context and data freshness.

These encode what a source can and cannot say. Nothing here scores anything, and absence of
evidence is never converted into 'no service'.
"""

from __future__ import annotations

from datetime import date
from typing import Any

FORBIDDEN_FIELDS = (
    "school_quality_score", "best_school", "good_school", "family_score",
    "infrastructure_score", "total_family_score",
)  # fmt: skip

ELECTRICITY_STATES = ("REGIONAL_SERVICE_POTENTIAL", "NOT_ASSESSED")
WATER_STATES = ("PWA_SERVICE_AREA", "NON_PWA_OR_UNKNOWN_SERVICE")


def electricity_context(pea_machine_readable_evidence: bool = False) -> dict[str, Any]:
    """PEA Power Map is planning information with no obligation: never 'parcel electricity available'."""
    if pea_machine_readable_evidence:
        state, conf = "REGIONAL_SERVICE_POTENTIAL", "LOW"
    else:
        state, conf = "NOT_ASSESSED", "NONE"
    return {
        "electricity_evidence_type": "REVIEW_CONTEXT_ONLY_NO_MACHINE_READABLE_SOURCE"
        if state == "NOT_ASSESSED"
        else "PEA_POWER_MAP_PLANNING_INFORMATION",
        "electricity_service_potential": state,
        "electricity_confidence": conf,
        "electricity_parcel_verification_required": True,
    }


def water_context(in_pwa_area: bool | None) -> dict[str, Any]:
    """Outside (or unknown vs) a PWA area is NEVER 'no water'. ``None`` = no polygon evidence at all."""
    state = "PWA_SERVICE_AREA" if in_pwa_area else "NON_PWA_OR_UNKNOWN_SERVICE"
    return {
        "water_service_context": state,
        "water_service_verification_required": True,  # a parcel connection always needs verification, inside a PWA area or not
        "water_note": "service-area evidence only; outside PWA is not 'no water' (wells, municipal, village systems exist)",
    }


def telecom_context(spatial_evidence: bool = False) -> dict[str, Any]:
    """Province-level shares are not grid coverage, so telecom is DEFERRED unless real spatial data exists."""
    return {
        "telecom_evidence": "DEFERRED_NO_SPATIAL_COVERAGE_DATA"
        if not spatial_evidence
        else "SPATIAL_COVERAGE",
        "telecom_resolution": "NONE" if not spatial_evidence else "SPATIAL",
        "telecom_confidence": "NONE" if not spatial_evidence else "LOW",
    }


def freshness(
    source_date: str,
    verification_date: str,
    expected_update_frequency: str,
    stale_after_years: float,
) -> dict[str, Any]:
    """Record source/verification dates and flag a dataset as STALE when older than the threshold."""
    sd = date.fromisoformat(source_date)
    vd = date.fromisoformat(verification_date)
    age_years = (vd - sd).days / 365.25
    return {
        "source_date": source_date,
        "verification_date": verification_date,
        "expected_update_frequency": expected_update_frequency,
        "age_years": round(age_years, 2),
        "freshness_status": "STALE" if age_years > stale_after_years else "CURRENT",
    }
