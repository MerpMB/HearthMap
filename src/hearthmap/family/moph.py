# ruff: noqa: E501
"""MoPH facility classification from SOURCE fields only (type code, level code, ministry, status).

The public MoPH hospital point layers (and an HCODE export, if one is ever supplied) carry an explicit facility
type (``typecode``) and hospital level (``level_``). Those fields, not names, drive the class here. Capabilities
(emergency, trauma, ICU, specialists) are never inferred from a class: ``capabilities_source_supported`` stays empty
unless a source field explicitly states one.
"""

from __future__ import annotations

import re
from typing import Any

# source typecode (as published) -> normalised class
TYPECODE_CLASS = {
    "โรงพยาบาลส่งเสริมสุขภาพตำบล": "PRIMARY_HEALTH_UNIT",
    "ศูนย์บริการสาธารณสุข อปท.": "PRIMARY_HEALTH_UNIT",
    "ศูนย์บริการสาธารณสุข": "PRIMARY_HEALTH_UNIT",
    "โรงพยาบาลชุมชน": "COMMUNITY_HOSPITAL",
    "โรงพยาบาลทั่วไป": "GENERAL_HOSPITAL",
    "โรงพยาบาลศูนย์": "REGIONAL_REFERRAL_HOSPITAL",
    "สำนักงานสาธารณสุขจังหวัด": "OTHER_NON_SERVICE_POINT",
    "สำนักงานสาธารณสุขอำเภอ": "OTHER_NON_SERVICE_POINT",
    "ศูนย์วิชาการ": "OTHER_NON_SERVICE_POINT",
}
# hospital-level code (prefix of ``level_``) -> class, used only when the typecode gives no class
LEVEL_CLASS = {
    "A": "REGIONAL_REFERRAL_HOSPITAL",
    "S": "GENERAL_HOSPITAL",
    "M1": "GENERAL_HOSPITAL",
    "M2": "COMMUNITY_HOSPITAL",
    "F1": "COMMUNITY_HOSPITAL",
    "F2": "COMMUNITY_HOSPITAL",
    "F3": "COMMUNITY_HOSPITAL",
}
HOSPITAL_CLASSES = (
    "COMMUNITY_HOSPITAL",
    "GENERAL_HOSPITAL",
    "REGIONAL_REFERRAL_HOSPITAL",
    "REGIONAL_OR_TERTIARY_HOSPITAL",
    "UNIVERSITY_HOSPITAL",
    "HOSPITAL_UNSPECIFIED_LEVEL",
)
SPECIALISED_NAME_KEYWORDS = (
    "ประสาท",
    "สวนปรุง",
    "จิตเวช",
    "ธัญญารักษ์",
    "มะเร็ง",
    "ทันตกรรม",
    "โรคผิวหนัง",
    "โรคทรวงอก",
    "ราชประชาสมาสัย",
    "โรคติดต่อ",
)


def level_code(level_text: Any) -> str | None:
    """'F2 - โรงพยาบาลชุมชนขนาดกลาง' -> 'F2'; 'A' -> 'A'; empty -> None."""
    if level_text is None or (isinstance(level_text, float) and level_text != level_text):
        return None
    m = re.match(r"^\s*([A-Za-z]+\d?)\b", str(level_text))
    return m.group(1).upper() if m else None


def classify_health_moph(
    typecode: Any,
    level_text: Any,
    minname: Any,
    name: Any,
    status: Any,
    higher_level_classes: tuple[str, ...] = ("REGIONAL_REFERRAL_HOSPITAL",),
) -> dict[str, Any]:
    """Class from the source type code (preferred) or level code; method and confidence are recorded."""
    tc = None if typecode is None or str(typecode) in ("", "nan", "None") else str(typecode).strip()
    lc = level_code(level_text)
    out: dict[str, Any] = {
        "source_native_type": tc,
        "source_native_level": None
        if level_text is None or str(level_text) in ("", "nan", "None")
        else str(level_text),
        "facility_class": "UNKNOWN",
        "class_basis": "NONE",
        "class_confidence": "NONE",
        "capabilities_source_supported": [],  # never inferred
        "is_service_point": True,
        "is_active": str(status).strip() == "กำลังใช้งาน",
    }
    if tc in TYPECODE_CLASS:
        out |= {
            "facility_class": TYPECODE_CLASS[tc],
            "class_basis": "SOURCE_TYPECODE",
            "class_confidence": "HIGH",
        }
    elif (
        tc and "โรงพยาบาล" in tc
    ):  # e.g. 'โรงพยาบาล นอก สธ.' (hospital outside MoPH): type given, level may be
        if lc in LEVEL_CLASS:
            out |= {
                "facility_class": LEVEL_CLASS[lc],
                "class_basis": "SOURCE_LEVEL_CODE",
                "class_confidence": "HIGH",
            }
        elif _has(str(minname), ("อุดมศึกษา",)):
            out |= {
                "facility_class": "UNIVERSITY_HOSPITAL",
                "class_basis": "SOURCE_MINISTRY_FIELD",
                "class_confidence": "HIGH",
            }
        elif _has(str(name), SPECIALISED_NAME_KEYWORDS):
            out |= {
                "facility_class": "SPECIALISED_HOSPITAL",
                "class_basis": "NAME_KEYWORD",
                "class_confidence": "MEDIUM",
            }
        else:
            out |= {
                "facility_class": "HOSPITAL_UNSPECIFIED_LEVEL",
                "class_basis": "SOURCE_TYPECODE_LEVEL_NOT_STATED",
                "class_confidence": "MEDIUM",
            }
    elif lc in LEVEL_CLASS:
        out |= {
            "facility_class": LEVEL_CLASS[lc],
            "class_basis": "SOURCE_LEVEL_CODE",
            "class_confidence": "HIGH",
        }
    out["is_service_point"] = out["facility_class"] != "OTHER_NON_SERVICE_POINT"
    out["higher_level"] = out["facility_class"] in higher_level_classes
    return out


def _has(text: str, kws: tuple[str, ...]) -> bool:
    return any(k in text for k in kws)
