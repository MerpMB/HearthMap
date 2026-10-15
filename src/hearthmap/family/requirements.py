# ruff: noqa: E501, N815, N818
"""M2B.0 family REQUIREMENTS: declarative user preferences, validation and the evidence-sufficiency matrix.

Three concepts are kept apart on purpose:
  USER_REQUIREMENT   what the family wants (config/family-requirements.yaml); unknown values stay ``UNSET``
  DATA_CAPABILITY    whether current M2A evidence could evaluate it (config/family-evidence-capability.yaml)
  EVALUATION_RULE    how it would be scored: NOT ACTIVE here. Nothing in this module reads a grid cell, scores a place,
                     ranks a province or recommends anything. Missing data never rewrites a user's preference.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

REQUIREMENTS_PATH = Path("config/family-requirements.yaml")
CAPABILITY_PATH = Path("config/family-evidence-capability.yaml")
UNSET = "UNSET"
Unset = Literal["UNSET"]
Num = Unset | float
Flag = Unset | bool
EVALUATION_RULE = "NOT_ACTIVE_UNTIL_SCORING_MILESTONE"


class Importance(StrEnum):
    MUST = "MUST"
    STRONG_PREFERENCE = "STRONG_PREFERENCE"
    PREFERENCE = "PREFERENCE"
    NICE_TO_HAVE = "NICE_TO_HAVE"
    IRRELEVANT = "IRRELEVANT"


Imp = Unset | Importance
Tolerance = Unset | Literal["NONE", "LOW", "MODERATE", "HIGH"]


class _M(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )  # a misspelt requirement key is an error, not a silent default


class Stage(_M):
    importance: Imp = UNSET
    preferred_max_drive_minutes: Num = UNSET
    absolute_max_drive_minutes: Num = UNSET
    minimum_choices_within_preferred_time: Num = UNSET


class Vocational(_M):
    importance: Imp = UNSET


class University(_M):
    importance: Imp = UNSET
    preferred_max_drive_minutes: Num = UNSET


class Education(_M):
    kindergarten: Stage = Stage()
    primary: Stage = Stage()
    lower_secondary: Stage = Stage()
    upper_secondary: Stage = Stage()
    vocational: Vocational = Vocational()
    university: University = University()


class PrimaryHealthcare(_M):
    importance: Imp = UNSET
    preferred_max_drive_minutes: Num = UNSET


class HospitalReq(_M):
    importance: Imp = UNSET
    preferred_max_drive_minutes: Num = UNSET
    absolute_max_drive_minutes: Num = UNSET


class Healthcare(_M):
    primary_healthcare: PrimaryHealthcare = PrimaryHealthcare()
    hospital: HospitalReq = HospitalReq()
    regional_or_referral_hospital: HospitalReq = HospitalReq()


class Redundancy1(_M):
    importance: Imp = UNSET
    minimum_count: Num = UNSET
    within_minutes: Num = UNSET


class Redundancy(_M):
    number_of_primary_schools_within_time: Redundancy1 = Redundancy1()
    number_of_secondary_schools_within_time: Redundancy1 = Redundancy1()
    number_of_hospitals_within_time: Redundancy1 = Redundancy1()


class MajorRoad(_M):
    importance: Imp = UNSET
    maximum_baseline_drive_time_to_major_road: Num = UNSET


class RoadAccess(_M):
    major_road: MajorRoad = MajorRoad()
    tolerate_unpaved_local_access: Flag = UNSET
    minimum_all_weather_access_expectation: (
        Unset | Literal["NOT_REQUIRED", "DRY_SEASON_ONLY", "ALL_WEATHER_REQUIRED"]
    ) = UNSET
    route_redundancy_importance: Imp = UNSET


class Electricity(_M):
    must_be_verified_before_purchase: Flag = UNSET
    tolerate_regional_uncertainty_during_screening: Flag = UNSET


class Water(_M):
    accept_non_PWA_system_if_field_verified: Flag = UNSET
    require_municipal_or_PWA_service: Flag = UNSET
    well_water_acceptable: Flag = UNSET


class Telecom(_M):
    minimum_requirement: (
        Unset | Literal["NONE", "MOBILE_VOICE", "MOBILE_DATA", "FIXED_BROADBAND"]
    ) = UNSET
    verification_stage: Unset | Literal["SCREENING", "SHORTLIST", "PARCEL_PURCHASE"] = UNSET


class Utilities(_M):
    electricity: Electricity = Electricity()
    water: Water = Water()
    telecom: Telecom = Telecom()


class UrbanAccess(_M):
    preferred_drive_time_to_town_services: Num = UNSET
    absolute_max_drive_time_to_major_city_services: Num = UNSET
    airport_importance: Imp = UNSET
    shopping_daily_services_importance: Imp = UNSET


class Livability(_M):
    preferred_population_density: (
        Unset | Literal["REMOTE", "RURAL", "PERI_URBAN", "SUBURBAN", "URBAN"]
    ) = UNSET
    avoid_dense_urban_core: Flag = UNSET
    tolerate_tourism_activity: Tolerance = UNSET
    tolerate_nightlife: Tolerance = UNSET
    industrial_nuisance_tolerance: Tolerance = UNSET
    agricultural_surroundings_preference: Imp = UNSET


class Land(_M):
    budget_thb: Num = UNSET
    preferred_area_rai: Num = UNSET
    minimum_area_rai: Num = UNSET
    maximum_area_rai: Num = UNSET
    terrain_tolerance: Unset | Literal["FLAT_ONLY", "GENTLE", "MODERATE", "STEEP_ACCEPTABLE"] = (
        UNSET
    )
    willingness_to_improve_drainage: Flag = UNSET
    willingness_to_build_retaining_structures: Flag = UNSET


class ProjectState(_M):
    family_infrastructure_evidence: dict[str, str]
    requirement_calibration: dict[str, bool]
    family_suitability_scoring: dict[str, bool]
    reason: str


class Requirements(_M):
    schema_version: Literal[1]
    version: str
    status: str
    project_state: ProjectState
    education: Education = Education()
    healthcare: Healthcare = Healthcare()
    redundancy: Redundancy = Redundancy()
    road_access: RoadAccess = RoadAccess()
    utilities: Utilities = Utilities()
    urban_access: UrbanAccess = UrbanAccess()
    livability: Livability = Livability()
    land: Land = Land()


class RequirementConflict(ValueError):
    """The requirements contradict each other. Nothing is normalised or repaired silently."""


def load_requirements(path: Path = REQUIREMENTS_PATH) -> Requirements:
    return Requirements(**yaml.safe_load(Path(path).read_text("utf-8")))


# -- leaves --------------------------------------------------------------------------------------------
def leaves(model: BaseModel, prefix: str = "") -> list[tuple[str, Any]]:
    """(dotted path, value) for every requirement leaf."""
    out: list[tuple[str, Any]] = []
    for name in type(model).model_fields:
        v = getattr(model, name)
        p = f"{prefix}{name}"
        if isinstance(v, BaseModel):
            out += leaves(v, p + ".")
        elif p.startswith(("project_state", "schema_version", "version", "status")):
            continue
        else:
            out.append((p, v))
    return out


def _set(v: Any) -> bool:
    return v != UNSET


# -- validation ----------------------------------------------------------------------------------------
class Issue(BaseModel):
    severity: Literal["ERROR", "WARNING"]
    path: str
    message: str


def validate_requirements(req: Requirements) -> list[Issue]:
    """Contradictions are ERRORs (never repaired); incomplete-but-consistent requirements are WARNINGs."""
    issues: list[Issue] = []

    def err(path: str, msg: str) -> None:
        issues.append(Issue(severity="ERROR", path=path, message=msg))

    def warn(path: str, msg: str) -> None:
        issues.append(Issue(severity="WARNING", path=path, message=msg))

    ps = req.project_state
    if ps.family_suitability_scoring.get("allowed") is not False:
        err(
            "project_state.family_suitability_scoring.allowed",
            "scoring must stay disabled in M2B.0",
        )
    if ps.requirement_calibration.get("allowed") is not True:
        err(
            "project_state.requirement_calibration.allowed",
            "requirement calibration is the purpose of M2B.0",
        )

    # every number must be non-negative; minutes must be positive
    for path, v in leaves(req):
        if isinstance(v, int | float) and not isinstance(v, bool):
            if v < 0:
                err(path, f"negative value {v}")
            if (
                path.endswith(
                    (
                        "minutes",
                        "_minutes",
                        "drive_time_to_major_road",
                        "town_services",
                        "city_services",
                    )
                )
                and v == 0
            ):
                err(path, "a zero-minute threshold is not a usable requirement")

    def thresholds_of(node: BaseModel) -> list[str]:
        return [n for n in type(node).model_fields if n != "importance" and _set(getattr(node, n))]

    def check_obj(path: str, node: BaseModel) -> None:
        imp = getattr(node, "importance", UNSET)
        th = thresholds_of(node)
        if imp is Importance.IRRELEVANT and th:
            err(path, f"importance IRRELEVANT but thresholds are set: {th}")
        if (
            imp in (Importance.MUST, Importance.STRONG_PREFERENCE)
            and not th
            and "importance" in type(node).model_fields
            and len(type(node).model_fields) > 1
        ):
            warn(path, f"importance {imp.value} but no threshold is set yet")
        if _set(imp) is False and th:
            warn(path, "thresholds set without an importance")

    ed = req.education
    for name in ("kindergarten", "primary", "lower_secondary", "upper_secondary"):
        s: Stage = getattr(ed, name)
        p = f"education.{name}"
        check_obj(p, s)
        if (
            _set(s.preferred_max_drive_minutes)
            and _set(s.absolute_max_drive_minutes)
            and s.preferred_max_drive_minutes > s.absolute_max_drive_minutes
        ):
            err(
                p,
                f"preferred time {s.preferred_max_drive_minutes} > absolute maximum {s.absolute_max_drive_minutes}",
            )
        if _set(s.minimum_choices_within_preferred_time):
            if s.minimum_choices_within_preferred_time < 1:
                err(
                    f"{p}.minimum_choices_within_preferred_time",
                    "minimum choices must be at least 1",
                )
            if not _set(s.preferred_max_drive_minutes):
                err(
                    f"{p}.minimum_choices_within_preferred_time",
                    "choices are counted within the preferred time, which is UNSET",
                )
    check_obj("education.vocational", ed.vocational)
    check_obj("education.university", ed.university)

    hc = req.healthcare
    check_obj("healthcare.primary_healthcare", hc.primary_healthcare)
    for name in ("hospital", "regional_or_referral_hospital"):
        h: HospitalReq = getattr(hc, name)
        p = f"healthcare.{name}"
        check_obj(p, h)
        if (
            _set(h.preferred_max_drive_minutes)
            and _set(h.absolute_max_drive_minutes)
            and h.preferred_max_drive_minutes > h.absolute_max_drive_minutes
        ):
            err(
                p,
                f"preferred time {h.preferred_max_drive_minutes} > absolute maximum {h.absolute_max_drive_minutes}",
            )

    for name in (
        "number_of_primary_schools_within_time",
        "number_of_secondary_schools_within_time",
        "number_of_hospitals_within_time",
    ):
        r: Redundancy1 = getattr(req.redundancy, name)
        p = f"redundancy.{name}"
        check_obj(p, r)
        if _set(r.minimum_count) and r.minimum_count < 1:
            err(f"{p}.minimum_count", "a redundancy count below 1 is not a redundancy requirement")
        if _set(r.minimum_count) != _set(r.within_minutes):
            err(p, "minimum_count and within_minutes must be set together")

    ra = req.road_access
    check_obj("road_access.major_road", ra.major_road)
    if (
        ra.tolerate_unpaved_local_access is True
        and ra.minimum_all_weather_access_expectation == "ALL_WEATHER_REQUIRED"
    ):
        warn(
            "road_access",
            "tolerating unpaved local access while requiring all-weather access: confirm what is meant",
        )

    w = req.utilities.water
    if (
        w.require_municipal_or_PWA_service is True
        and w.accept_non_PWA_system_if_field_verified is True
    ):
        err("utilities.water", "requires municipal/PWA service but also accepts a non-PWA system")
    if w.require_municipal_or_PWA_service is True and w.well_water_acceptable is True:
        err("utilities.water", "requires municipal/PWA service but also accepts well water")

    ua = req.urban_access
    check_obj("urban_access", ua)

    lv = req.livability
    if lv.avoid_dense_urban_core is True and lv.preferred_population_density == "URBAN":
        err("livability", "avoids the dense urban core but prefers URBAN density")

    ld = req.land
    if (
        _set(ld.minimum_area_rai)
        and _set(ld.maximum_area_rai)
        and ld.minimum_area_rai > ld.maximum_area_rai
    ):
        err("land", f"minimum area {ld.minimum_area_rai} > maximum area {ld.maximum_area_rai}")
    if _set(ld.preferred_area_rai):
        if _set(ld.minimum_area_rai) and ld.preferred_area_rai < ld.minimum_area_rai:
            err("land.preferred_area_rai", "preferred area is below the minimum")
        if _set(ld.maximum_area_rai) and ld.preferred_area_rai > ld.maximum_area_rai:
            err("land.preferred_area_rai", "preferred area is above the maximum")
    if _set(ld.budget_thb) and ld.budget_thb <= 0:
        err("land.budget_thb", "budget must be positive")
    return issues


def check_requirements(req: Requirements) -> list[Issue]:
    """Raise on any contradiction; return the warnings otherwise."""
    issues = validate_requirements(req)
    errors = [i for i in issues if i.severity == "ERROR"]
    if errors:
        raise RequirementConflict("; ".join(f"{i.path}: {i.message}" for i in errors))
    return issues


# -- capability and the evidence matrix -----------------------------------------------------------------
CAPABILITY_STATUSES = (
    "SUPPORTED",
    "SUPPORTED_WITH_LIMITATIONS",
    "PARTIALLY_SUPPORTED",
    "NOT_SUPPORTED",
)


def load_capability(path: Path = CAPABILITY_PATH) -> dict[str, Any]:
    cap = yaml.safe_load(Path(path).read_text("utf-8"))
    for k, v in cap["capabilities"].items():
        if v["status"] not in CAPABILITY_STATUSES:
            raise ValueError(f"{k}: unknown capability status {v['status']}")
        if not v.get("reason"):
            raise ValueError(f"{k}: a capability needs a reason")
    return cap


def _capability_key(path: str) -> str:
    """Requirement leaf path -> capability key (leaves of one block share a capability)."""
    parts = path.split(".")
    if parts[0] == "education":
        return ".".join(parts[:2])
    if parts[0] == "healthcare":
        return ".".join(parts[:2])
    if parts[0] == "redundancy":
        return ".".join(parts[:2])
    if parts[0] == "road_access":
        return ".".join(parts[:2]) if parts[1] == "major_road" else path
    if parts[0] == "utilities":
        return ".".join(parts[:2])
    if parts[0] == "urban_access":
        return path
    return path


def evidence_matrix(req: Requirements, cap: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per requirement leaf (plus capability-only questions). USER_REQUIREMENT, DATA_CAPABILITY, EVALUATION_RULE stay separate columns."""
    rows: list[dict[str, Any]] = []
    caps = cap["capabilities"]
    for path, value in leaves(req):
        key = _capability_key(path)
        c = caps.get(key) or caps.get(path)
        if c is None:
            raise KeyError(f"no data-capability entry for requirement {path} (expected {key})")
        rows.append({
            "requirement_path": path, "kind": "USER_REQUIREMENT", "user_requirement_value": value if not hasattr(value, "value") else value.value,
            "data_capability": c["status"], "capability_reason": c["reason"], "evidence_columns": "|".join(c.get("evidence_columns", [])),
            "limitations": " ".join(c.get("limitations", [])), "evaluation_rule": EVALUATION_RULE, "needs_user_input": value == UNSET,
        })  # fmt: skip
    for key, c in cap.get("capability_only", {}).items():
        rows.append({
            "requirement_path": key, "kind": "CAPABILITY_ONLY_FUTURE_VERIFICATION", "user_requirement_value": "n/a",
            "data_capability": c["status"], "capability_reason": c["reason"], "evidence_columns": "|".join(c.get("evidence_columns", [])),
            "limitations": " ".join(c.get("limitations", [])), "evaluation_rule": EVALUATION_RULE, "needs_user_input": False,
        })  # fmt: skip
    return rows
