# ruff: noqa: E501
"""Education and healthcare taxonomies.

Rules, in order, never use institution quality. The source-native type is always preserved;
levels derived from names/sub-codes are marked ``DERIVED`` with a confidence (the MOE register that
would carry authoritative levels was unreachable, so this is the best available evidence).
"""

from __future__ import annotations

import unicodedata
from typing import Any

EDU_LEVELS = (
    "EARLY_CHILDHOOD", "KINDERGARTEN", "PRIMARY", "LOWER_SECONDARY", "UPPER_SECONDARY",
    "VOCATIONAL", "UNIVERSITY_TERTIARY", "OTHER", "UNKNOWN",
)  # fmt: skip


def _clean(name: str) -> str:
    n = unicodedata.normalize("NFC", str(name or ""))
    return "".join(ch for ch in n if ch not in "​‌‍﻿").strip()


def _has(name: str, kws: list[str]) -> bool:
    return any(k in name for k in kws)


def classify_education(name: str, subcode: str | None, cfg: dict[str, Any]) -> dict[str, Any]:
    """Return levels (list), kind, basis, confidence; ``native_type`` is the untouched source sub-code."""
    e = cfg["education"]
    n = _clean(name)
    sc = str(subcode) if subcode is not None else ""
    base = {
        "native_type": sc or None,
        "levels": ["UNKNOWN"],
        "kind": "UNKNOWN",
        "level_basis": "NONE",
        "level_confidence": "NONE",
        "derived": True,
    }

    if sc in e["source_subcodes_non_institutional"] or _has(n, e["non_schooling_keywords"]):
        return {
            **base,
            "levels": ["OTHER"],
            "kind": "NON_SCHOOLING_LEARNING_RESOURCE",
            "level_basis": "NAME_KEYWORD_OR_SOURCE_SUBCODE",
            "level_confidence": "MEDIUM",
        }
    if _has(n, e["early_childhood_keywords"]) or sc in e["early_childhood_subcodes"]:
        conf = "HIGH" if _has(n, e["early_childhood_keywords"]) else "MEDIUM"
        return {
            **base,
            "levels": ["EARLY_CHILDHOOD"],
            "kind": "EARLY_CHILDHOOD_CENTRE",
            "level_basis": "NAME_KEYWORD" if conf == "HIGH" else "SOURCE_SUBCODE",
            "level_confidence": conf,
        }
    if _has(
        n, e["university_keywords"]
    ):  # before vocational: "มหาวิทยาลัยเทคโนโลยี..." is a university
        return {
            **base,
            "levels": ["UNIVERSITY_TERTIARY"],
            "kind": "UNIVERSITY_OR_COLLEGE",
            "level_basis": "NAME_KEYWORD",
            "level_confidence": "MEDIUM",
        }
    if _has(n, e["vocational_keywords"]) or sc in e["vocational_subcodes"]:
        return {
            **base,
            "levels": ["VOCATIONAL"],
            "kind": "VOCATIONAL_COLLEGE",
            "level_basis": "NAME_KEYWORD"
            if _has(n, e["vocational_keywords"])
            else "SOURCE_SUBCODE",
            "level_confidence": "MEDIUM",
        }
    if sc in e["university_subcodes"]:
        return {
            **base,
            "levels": ["UNIVERSITY_TERTIARY"],
            "kind": "UNIVERSITY_OR_COLLEGE",
            "level_basis": "SOURCE_SUBCODE",
            "level_confidence": "LOW",
        }
    is_school = "โรงเรียน" in n or sc in e["school_subcodes"]
    if not is_school:
        return base
    levels: list[str] = []
    basis, conf = "NAME_KEYWORD", "LOW"
    if _has(n, e["kindergarten_keywords"]):
        levels.append("KINDERGARTEN")
        conf = "MEDIUM"
    if _has(n, ["วิทยาคม", "มัธยม"]) or sc in e["secondary_subcodes"]:
        levels += ["LOWER_SECONDARY", "UPPER_SECONDARY"]
        conf = "MEDIUM"
        basis = "NAME_KEYWORD" if _has(n, ["วิทยาคม", "มัธยม"]) else "SOURCE_SUBCODE"
    if not levels:  # unstated basic school: treated as primary-providing, LOW confidence
        levels, basis = ["PRIMARY"], "DEFAULT_BASIC_SCHOOL_LEVEL_NOT_STATED"
    return {
        **base,
        "levels": levels,
        "kind": "SCHOOL",
        "level_basis": basis,
        "level_confidence": conf,
    }


HEALTH_HOSPITAL_CLASSES = (
    "COMMUNITY_HOSPITAL", "GENERAL_HOSPITAL", "REGIONAL_OR_TERTIARY_HOSPITAL",
    "UNIVERSITY_HOSPITAL", "HOSPITAL_UNSPECIFIED_LEVEL",
)  # fmt: skip


def classify_health(
    name: str, official_id: str | None, ministry: str | None, dept: str | None, cfg: dict[str, Any],
    reference: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:  # fmt: skip
    """Facility class from source-supported fields only. ``capabilities`` is never inferred."""
    h = cfg["healthcare"]
    n = _clean(name)
    ref = (reference or {}).get(str(official_id or ""))
    out = {
        "facility_class": "UNKNOWN",
        "class_basis": "NONE",
        "class_confidence": "NONE",
        "capabilities_source_supported": [],
        "derived": True,
    }
    if ref:
        return {
            **out,
            "facility_class": ref["level"],
            "class_basis": "AUTHORITATIVE_REFERENCE_LIST",
            "class_confidence": "HIGH",
            "derived": False,
        }
    if _has(n, h["primary_unit_keywords"]):
        return {
            **out,
            "facility_class": "PRIMARY_HEALTH_UNIT",
            "class_basis": "NAME_KEYWORD",
            "class_confidence": "HIGH",
        }
    if h["hospital_name_keyword"] in n:
        if _has(str(ministry or ""), h["university_ministry_keywords"]):
            return {
                **out,
                "facility_class": "UNIVERSITY_HOSPITAL",
                "class_basis": "MINISTRY_FIELD",
                "class_confidence": "HIGH",
            }
        if _has(n, h["specialised_keywords"]):
            return {
                **out,
                "facility_class": "SPECIALISED_HOSPITAL",
                "class_basis": "NAME_KEYWORD",
                "class_confidence": "MEDIUM",
            }
        return {
            **out,
            "facility_class": "HOSPITAL_UNSPECIFIED_LEVEL",
            "class_basis": "NAME_KEYWORD_HOSPITAL_LEVEL_NOT_STATED",
            "class_confidence": "MEDIUM",
        }
    return {
        **out,
        "facility_class": "OTHER",
        "class_basis": "NO_RULE_MATCHED",
        "class_confidence": "LOW",
    }
