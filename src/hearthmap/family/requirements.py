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
    absolute_max_drive_minutes: Num = UNSET  # not a hard gate: the owner set none


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


class AccessReq(_M):
    required: Flag = UNSET
    importance: Imp = UNSET


class RoadAccess(_M):
    major_road: MajorRoad = MajorRoad()
    legal_vehicle_access: AccessReq = (
        AccessReq()
    )  # parcel-level legal/legitimate access; never provable from regional data
    all_weather_vehicle_access: AccessReq = (
        AccessReq()
    )  # a normal vehicle year-round; concerns usability, not paving
    tolerate_unpaved_local_access: Flag = (
        UNSET  # unpaved/gravel FINAL access acceptable (if it stays usable in the wet season)
    )
    route_redundancy_importance: Imp = UNSET


class Electricity(_M):
    """Actual usable public/grid electricity at the parcel. Capacity, transformer, phase, cost and reliability are NOT requirements here."""

    grid_service_required: Flag = UNSET
    importance: Imp = UNSET
    verification_stage: (
        Unset | Literal["SCREENING", "SHORTLIST", "PARCEL_PURCHASE", "BEFORE_PURCHASE"]
    ) = UNSET
    must_be_verified_before_purchase: Flag = UNSET
    tolerate_regional_uncertainty_during_screening: Flag = UNSET


class Water(_M):
    importance: Imp = UNSET  # importance of a verified, reliable supply (any acceptable system)
    must_be_verified_before_purchase: Flag = UNSET
    accept_non_PWA_system_if_field_verified: Flag = UNSET
    require_municipal_or_PWA_service: Flag = UNSET
    well_water_acceptable: Flag = UNSET


SUBSTITUTES = Literal["MOBILE_4G", "MOBILE_5G", "FIXED_WIRELESS", "SATELLITE"]


class Telecom(_M):
    minimum_requirement: (
        Unset | Literal["NONE", "MOBILE_VOICE", "MOBILE_DATA", "FIXED_BROADBAND", "FIXED_FIBER"]
    ) = UNSET
    importance: Imp = UNSET
    verification_stage: (
        Unset | Literal["SCREENING", "SHORTLIST", "PARCEL_PURCHASE", "BEFORE_PURCHASE"]
    ) = UNSET
    substitutes_not_accepted: Unset | list[SUBSTITUTES] = (
        UNSET  # technologies that do NOT satisfy the requirement
    )


class Utilities(_M):
    electricity: Electricity = Electricity()
    water: Water = Water()
    telecom: Telecom = Telecom()


class UrbanAccess(_M):
    preferred_drive_time_to_town_services: Num = UNSET
    preferred_drive_time_to_town_services_importance: Imp = UNSET
    absolute_max_drive_time_to_major_city_services: Num = UNSET
    hard_limit_policy: Unset | Literal["CASE_BY_CASE", "FIXED"] = UNSET
    airport_importance: Imp = UNSET
    shopping_daily_services_importance: Imp = UNSET


class AvoidPref(_M):
    """A residential-exposure avoidance PREFERENCE (not a hard exclusion). Distances/buffers are UNSET until the owner gives them."""

    value: Flag = UNSET
    importance: Imp = UNSET
    buffer_distance_m: Num = UNSET


class Livability(_M):
    preferred_population_density: (
        Unset | Literal["REMOTE", "RURAL", "PERI_URBAN", "SUBURBAN", "URBAN"]
    ) = UNSET
    avoid_dense_urban_core: Flag = UNSET
    avoid_dense_urban_core_importance: Imp = UNSET
    tolerate_tourism_activity: Tolerance = UNSET
    tolerate_nightlife: Tolerance = UNSET
    industrial_nuisance_tolerance: Tolerance = UNSET
    agricultural_surroundings_preference: Imp = UNSET
    # INPUT PASS 3 avoidance preferences (residential exposure; context-dependent, never a blanket exclusion of mapped features)
    avoid_industrial_nuisance: AvoidPref = AvoidPref()
    avoid_mining_quarry_nuisance: AvoidPref = AvoidPref()
    avoid_major_road_noise: AvoidPref = (
        AvoidPref()
    )  # separate from ACCESS to a major road (road_access.major_road)
    avoid_nightlife_concentration: AvoidPref = (
        AvoidPref()
    )  # residential nuisance, not restaurants or normal town services


class PurchaseBudget(_M):
    """Budget for the LAND PURCHASE PRICE only (bare land); never a house-construction budget."""

    preferred_thb: Num = UNSET
    absolute_max_thb: Num = UNSET
    importance: Imp = UNSET


class Land(_M):
    land_purchase_budget: PurchaseBudget = PurchaseBudget()
    house_construction_budget_thb: Num = (
        UNSET  # deliberately separate from the land price; not stated
    )
    preferred_area_rai: Num = UNSET
    minimum_area_rai: Num = UNSET
    maximum_area_rai: Num = UNSET
    terrain_preference: Unset | Literal["FLAT", "GENTLE_ROLLING", "HILLY"] = (
        UNSET  # what is liked, not what is tolerated
    )
    terrain_preference_importance: Imp = UNSET
    terrain_tolerance: Unset | Literal["FLAT_ONLY", "GENTLE", "MODERATE", "STEEP_ACCEPTABLE"] = (
        UNSET
    )
    willingness_to_improve_drainage: Flag = UNSET
    willingness_to_build_retaining_structures: Flag = UNSET
    willingness_to_grade_or_fill: Flag = UNSET


class ProjectState(_M):
    family_infrastructure_evidence: dict[str, str]
    requirement_calibration: dict[str, bool]
    family_suitability_scoring: dict[str, bool]
    reason: str


class HazardContract(_M):
    """Hazard (M1E) and preference semantics stay separate: a willingness to engineer a site never changes a hazard action."""

    m1e_actions_immutable: bool
    site_improvement_willingness_overrides_hazard_actions: bool
    family_access_offsets_hazard_actions: bool
    terrain_preference_overrides_hazard_actions: bool


class Requirements(_M):
    schema_version: Literal[1]
    version: str
    status: str
    project_state: ProjectState
    hazard_contract: HazardContract
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
        elif p.startswith(
            ("project_state", "hazard_contract", "schema_version", "version", "status")
        ):
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

    def pair(path: str, value: Any, importance: Any, flag: bool = False) -> None:
        """A scalar requirement with its own importance field (value without importance warns; IRRELEVANT with a value fails)."""
        active = value is True if flag else _set(value)
        if importance is Importance.IRRELEVANT and active:
            err(path, "importance IRRELEVANT but a requirement value is set")
        elif active and not _set(importance):
            warn(path, "value set without an importance")
        elif importance in (Importance.MUST, Importance.STRONG_PREFERENCE) and not active:
            warn(path, f"importance {importance.value} but no value is set yet")

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
    pc = hc.primary_healthcare
    if (
        _set(pc.preferred_max_drive_minutes)
        and _set(pc.absolute_max_drive_minutes)
        and pc.preferred_max_drive_minutes > pc.absolute_max_drive_minutes
    ):
        err(
            "healthcare.primary_healthcare",
            f"preferred time {pc.preferred_max_drive_minutes} > absolute maximum {pc.absolute_max_drive_minutes}",
        )
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

    hc_ = req.hazard_contract
    if not hc_.m1e_actions_immutable:
        err("hazard_contract.m1e_actions_immutable", "M1E hazard actions must stay immutable")
    if hc_.site_improvement_willingness_overrides_hazard_actions:
        err("hazard_contract", "willingness to improve a site must never override a hazard action")
    if hc_.family_access_offsets_hazard_actions:
        err("hazard_contract", "family access must never offset a hazard action")
    if hc_.terrain_preference_overrides_hazard_actions:
        err("hazard_contract", "a terrain preference must never override a hazard action")

    ra = req.road_access
    check_obj("road_access.major_road", ra.major_road)
    pair(
        "road_access.legal_vehicle_access",
        ra.legal_vehicle_access.required,
        ra.legal_vehicle_access.importance,
        flag=True,
    )
    pair(
        "road_access.all_weather_vehicle_access",
        ra.all_weather_vehicle_access.required,
        ra.all_weather_vehicle_access.importance,
        flag=True,
    )
    # unpaved final access + all-weather access are NOT contradictory: all-weather concerns wet-season usability, not paving

    w = req.utilities.water
    if (
        w.require_municipal_or_PWA_service is True
        and w.accept_non_PWA_system_if_field_verified is True
    ):
        err("utilities.water", "requires municipal/PWA service but also accepts a non-PWA system")
    if w.require_municipal_or_PWA_service is True and w.well_water_acceptable is True:
        err("utilities.water", "requires municipal/PWA service but also accepts well water")

    wi = req.utilities.water
    if wi.importance is Importance.IRRELEVANT and (
        wi.must_be_verified_before_purchase is True
        or wi.accept_non_PWA_system_if_field_verified is True
    ):
        err("utilities.water", "importance IRRELEVANT but water requirements are set")
    if wi.must_be_verified_before_purchase is True and not _set(wi.importance):
        warn("utilities.water", "verification required but no importance is set")
    tc = req.utilities.telecom
    if tc.importance is Importance.IRRELEVANT and _set(tc.minimum_requirement):
        err("utilities.telecom", "importance IRRELEVANT but a minimum requirement is set")
    if tc.importance in (Importance.MUST, Importance.STRONG_PREFERENCE) and not _set(
        tc.minimum_requirement
    ):
        warn(
            "utilities.telecom",
            f"importance {tc.importance.value} but no minimum requirement is set yet",
        )
    if _set(tc.minimum_requirement) and not _set(tc.importance):
        warn("utilities.telecom", "minimum requirement set without an importance")

    ua = req.urban_access
    if ua.hard_limit_policy == "CASE_BY_CASE" and _set(
        ua.absolute_max_drive_time_to_major_city_services
    ):
        err("urban_access", "hard_limit_policy CASE_BY_CASE contradicts a fixed absolute maximum")
    if ua.hard_limit_policy == "FIXED" and not _set(
        ua.absolute_max_drive_time_to_major_city_services
    ):
        warn("urban_access", "hard_limit_policy FIXED but no absolute maximum is set yet")
    pair(
        "urban_access.preferred_drive_time_to_town_services",
        ua.preferred_drive_time_to_town_services,
        ua.preferred_drive_time_to_town_services_importance,
    )
    if (
        _set(ua.absolute_max_drive_time_to_major_city_services)
        and ua.absolute_max_drive_time_to_major_city_services < 0
    ):
        err("urban_access.absolute_max_drive_time_to_major_city_services", "negative value")

    el = req.utilities.electricity
    pair(
        "utilities.electricity.grid_service_required",
        el.grid_service_required,
        el.importance,
        flag=True,
    )

    lv = req.livability
    for name, tolerance in (
        ("avoid_industrial_nuisance", lv.industrial_nuisance_tolerance),
        ("avoid_nightlife_concentration", lv.tolerate_nightlife),
    ):
        a: AvoidPref = getattr(lv, name)
        pair(f"livability.{name}", a.value, a.importance, flag=True)
        if a.value is True and tolerance == "HIGH":
            err(f"livability.{name}", "avoidance preferred but the matching tolerance is HIGH")
    for name in ("avoid_mining_quarry_nuisance", "avoid_major_road_noise"):
        a = getattr(lv, name)
        pair(f"livability.{name}", a.value, a.importance, flag=True)
    pair(
        "livability.avoid_dense_urban_core",
        lv.avoid_dense_urban_core,
        lv.avoid_dense_urban_core_importance,
        flag=True,
    )
    if lv.avoid_dense_urban_core is True and lv.preferred_population_density == "URBAN":
        err("livability", "avoids the dense urban core but prefers URBAN density")

    ld = req.land
    pair("land.terrain_preference", ld.terrain_preference, ld.terrain_preference_importance)
    if ld.terrain_preference in ("GENTLE_ROLLING", "HILLY") and ld.terrain_tolerance == "FLAT_ONLY":
        err(
            "land",
            f"terrain preference {ld.terrain_preference} contradicts terrain tolerance FLAT_ONLY",
        )
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
    b = ld.land_purchase_budget
    for name in ("preferred_thb", "absolute_max_thb"):
        v = getattr(b, name)
        if _set(v) and v <= 0:
            err(f"land.land_purchase_budget.{name}", "a land price must be positive")
    if _set(b.preferred_thb) and _set(b.absolute_max_thb) and b.preferred_thb > b.absolute_max_thb:
        err(
            "land.land_purchase_budget",
            f"preferred {b.preferred_thb} > absolute maximum {b.absolute_max_thb}",
        )
    check_obj("land.land_purchase_budget", b)
    if _set(ld.house_construction_budget_thb) and ld.house_construction_budget_thb <= 0:
        err("land.house_construction_budget_thb", "a construction budget must be positive")
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
# Where verification would have to happen; NOT_SUPPORTED is not a failure of the requirement.
EVIDENCE_STAGES = (
    "REGIONAL_EVIDENCE",
    "EVIDENCE_MISSING",
    "PARCEL_VERIFICATION",
    "FIELD_VERIFICATION",
    "USER_REQUIREMENT_ONLY",
)


def load_capability(path: Path = CAPABILITY_PATH) -> dict[str, Any]:
    cap = yaml.safe_load(Path(path).read_text("utf-8"))
    for k, v in cap["capabilities"].items():
        if v["status"] not in CAPABILITY_STATUSES:
            raise ValueError(f"{k}: unknown capability status {v['status']}")
        if not v.get("reason"):
            raise ValueError(f"{k}: a capability needs a reason")
        if v.get("evidence_stage", "REGIONAL_EVIDENCE") not in EVIDENCE_STAGES:
            raise ValueError(f"{k}: unknown evidence stage {v['evidence_stage']}")
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
        keyed = ("major_road", "legal_vehicle_access", "all_weather_vehicle_access")
        return ".".join(parts[:2]) if parts[1] in keyed else path
    if parts[0] == "land" and parts[1] == "land_purchase_budget":
        return ".".join(parts[:2])
    if parts[0] == "utilities":
        return ".".join(parts[:2])
    if parts[0] == "urban_access":
        return path
    if parts[0] == "livability" and len(parts) == 3:
        return ".".join(parts[:2])  # avoid_* preference objects share one capability
    return path


def irrelevant_prefixes(req: Requirements) -> list[str]:
    """Dimensions the owner marked IRRELEVANT: ``<block>.importance`` or ``<name>_importance`` equal to IRRELEVANT."""
    out = []
    for path, value in leaves(req):
        if value is Importance.IRRELEVANT or value == "IRRELEVANT":
            out.append(
                path[: -len(".importance")]
                if path.endswith(".importance")
                else path[: -len("_importance")]
                if path.endswith("_importance")
                else path
            )
    return out


def evidence_matrix(req: Requirements, cap: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per requirement leaf (plus capability-only questions).

    USER_REQUIREMENT, DATA_CAPABILITY and EVALUATION_RULE stay separate columns. A dimension marked IRRELEVANT is
    reported as such (``NOT_APPLICABLE_IRRELEVANT``): it needs no evidence and is excluded from future evaluation, but its
    underlying capability is still shown for information.
    """
    rows: list[dict[str, Any]] = []
    caps = cap["capabilities"]
    irr = irrelevant_prefixes(req)
    for path, value in leaves(req):
        key = _capability_key(path)
        c = caps.get(key) or caps.get(path)
        if c is None:
            raise KeyError(f"no data-capability entry for requirement {path} (expected {key})")
        excluded = any(
            path == pre or path.startswith(pre + ".") or path == pre + "_importance" for pre in irr
        )
        if value == UNSET:
            state = "EXCLUDED_IRRELEVANT" if excluded else "UNSET"
        else:
            state = "EXCLUDED_IRRELEVANT" if excluded else "SET"
        shown = (
            "|".join(value)
            if isinstance(value, list)
            else value.value
            if hasattr(value, "value")
            else int(value)
            if isinstance(value, float) and value.is_integer()
            else value
        )
        rows.append({
            "requirement_path": path, "kind": "USER_REQUIREMENT", "user_requirement_value": shown, "requirement_state": state,
            "data_capability": "NOT_APPLICABLE_IRRELEVANT" if excluded else c["status"], "underlying_capability": c["status"],
            "evidence_stage": c.get("evidence_stage", "REGIONAL_EVIDENCE"), "capability_reason": c["reason"],
            "evidence_columns": "|".join(c.get("evidence_columns", [])), "limitations": " ".join(c.get("limitations", [])),
            "evaluation_rule": EVALUATION_RULE, "evaluation_use": "EXCLUDED_BY_USER" if excluded else "NONE_ACTIVE",
            "needs_user_input": value == UNSET and not excluded,
        })  # fmt: skip
    for key, c in cap.get("capability_only", {}).items():
        rows.append({
            "requirement_path": key, "kind": "CAPABILITY_ONLY_FUTURE_VERIFICATION", "user_requirement_value": "n/a", "requirement_state": "n/a",
            "data_capability": c["status"], "underlying_capability": c["status"], "evidence_stage": c.get("evidence_stage", "REGIONAL_EVIDENCE"),
            "capability_reason": c["reason"], "evidence_columns": "|".join(c.get("evidence_columns", [])), "limitations": " ".join(c.get("limitations", [])),
            "evaluation_rule": EVALUATION_RULE, "evaluation_use": "NONE_ACTIVE", "needs_user_input": False,
        })  # fmt: skip
    return rows


# -- closure summary -------------------------------------------------------------------------------------
def _block(path: str) -> str:
    parts = path.split(".")
    return (
        ".".join(parts[:-1])
        if len(parts) > 2 or (len(parts) == 2 and parts[0] in {"education", "healthcare"})
        else path
    )


def _group(rows: list[dict[str, Any]], with_value: bool = True) -> list[str]:
    out: dict[str, list[str]] = {}
    for r in rows:
        path = r["requirement_path"]
        sec = path.split(".")[0]
        label = path[len(sec) + 1 :]
        out.setdefault(sec, []).append(
            f"`{label}` = {r['user_requirement_value']}" if with_value else f"`{label}`"
        )
    return [f"- **{sec}**: " + "; ".join(items) for sec, items in out.items()]


def render_summary(req: Requirements, cap: dict[str, Any]) -> str:
    """Family Requirements v0.1 closure snapshot, generated from the config (never hand-edited, drift is tested)."""
    rows = [r for r in evidence_matrix(req, cap) if r["kind"] == "USER_REQUIREMENT"]
    active = [r for r in rows if r["requirement_state"] == "SET"]
    irrelevant = sorted({p for p in irrelevant_prefixes(req)})
    unset = [r for r in rows if r["requirement_state"] == "UNSET"]
    not_eval = [
        r
        for r in active
        if r["underlying_capability"] == "NOT_SUPPORTED"
        and r["evidence_stage"] != "USER_REQUIREMENT_ONLY"
    ]
    parcel = [
        r for r in active if r["evidence_stage"] in ("PARCEL_VERIFICATION", "FIELD_VERIFICATION")
    ]
    lines = [
        "# Family requirements v0.1 - closure summary",
        "",
        f"State: **{req.status.split()[0]}** (config version {req.version}). Calibrated, not complete: **an intentional UNSET is valid product truth.**",
        "Suitability scoring is **not authorised** (`family_suitability_scoring.allowed: false`) and every evaluation rule is `NOT_ACTIVE_UNTIL_SCORING_MILESTONE`.",
        "Generated by `python scripts/m2b0/write_summary.py` from `config/family-requirements.yaml` and `config/family-evidence-capability.yaml`.",
        "",
        "Hazard contract: M1E hazard actions are immutable; willingness to improve a site, a terrain preference and family access never override or offset them.",
        "",
        f"## A. Active user requirements ({len(active)} values)",
        "",
        *_group(active),
        "",
        f"## B. Explicitly irrelevant dimensions ({len(irrelevant)})",
        "",
        *[
            f"- `{p}` - excluded from future evaluation: no reward for proximity, no penalty for distance."
            for p in irrelevant
        ],
        "",
        f"## C. Intentionally UNSET / case-by-case ({len(unset)} values)",
        "",
        "Not missing work: the owner has not decided, or said to decide case by case. Nothing is filled in to look complete.",
        "",
        f"- **hard town/city maximum**: policy `{req.urban_access.hard_limit_policy}`; `urban_access.absolute_max_drive_time_to_major_city_services` stays UNSET",
        *_group(unset, with_value=False),
        "",
        f"## D. Active requirements currently not evaluable with regional evidence ({len(not_eval)} values)",
        "",
        "`NOT_SUPPORTED` describes the data, never the requirement; missing evidence triggers verification or new evidence work, not rejection.",
        "Tolerances and policies that are user requirements only (site-improvement willingness, the case-by-case town limit) need no evidence and are not listed here.",
        "",
        *_group(not_eval, with_value=False),
        "",
        f"## E. Requirements that must be verified at the parcel / in the field ({len(parcel)} values)",
        "",
        *_group(parcel, with_value=False),
        "",
    ]
    return "\n".join(lines)
