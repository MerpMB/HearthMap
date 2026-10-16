# ruff: noqa: E501
"""M2B.0: requirements contract, conflict detection and the evidence matrix (no scoring)."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest
import yaml

from hearthmap.family.requirements import (
    EVALUATION_RULE,
    UNSET,
    Importance,
    RequirementConflict,
    Requirements,
    check_requirements,
    evidence_matrix,
    leaves,
    load_capability,
    load_requirements,
    validate_requirements,
)

ARTIFACT = Path("outputs/m2a2/family-infrastructure-evidence.parquet")


def base() -> dict:
    return yaml.safe_load(Path("config/family-requirements.yaml").read_text("utf-8"))


def with_(**path_values) -> Requirements:
    d = base()
    for dotted, v in path_values.items():
        node = d
        parts = dotted.split("__")
        for p in parts[:-1]:
            node = node[p]
        node[parts[-1]] = v
    return Requirements(**d)


# -- state and defaults ---------------------------------------------------------------------------------
def test_project_state_allows_calibration_and_forbids_scoring():
    r = load_requirements()
    ps = r.project_state
    assert ps.family_infrastructure_evidence == {
        "healthcare": "adequate_for_calibration",
        "education": "partial_and_stale",
        "routing": "adequate_for_calibration",
    }
    assert ps.requirement_calibration == {"allowed": True} and ps.family_suitability_scoring == {
        "allowed": False
    }
    assert "education register remains incomplete" in ps.reason
    assert r.status == "FAMILY_REQUIREMENTS_V0_1_CALIBRATED"


PASS_1 = {
    "education.kindergarten.importance": "PREFERENCE",
    "education.kindergarten.preferred_max_drive_minutes": 15,
    "education.kindergarten.absolute_max_drive_minutes": 25,
    "education.primary.importance": "MUST",
    "education.primary.preferred_max_drive_minutes": 15,
    "education.primary.absolute_max_drive_minutes": 25,
    "education.lower_secondary.importance": "MUST",
    "education.lower_secondary.preferred_max_drive_minutes": 20,
    "education.lower_secondary.absolute_max_drive_minutes": 30,
    "education.upper_secondary.importance": "STRONG_PREFERENCE",
    "education.upper_secondary.preferred_max_drive_minutes": 25,
    "education.upper_secondary.absolute_max_drive_minutes": 40,
    "healthcare.hospital.importance": "MUST",
    "healthcare.hospital.preferred_max_drive_minutes": 20,
    "healthcare.hospital.absolute_max_drive_minutes": 35,
    "healthcare.regional_or_referral_hospital.importance": "STRONG_PREFERENCE",
    "healthcare.regional_or_referral_hospital.preferred_max_drive_minutes": 45,
    "healthcare.regional_or_referral_hospital.absolute_max_drive_minutes": 75,
    "urban_access.preferred_drive_time_to_town_services": 35,
    "urban_access.preferred_drive_time_to_town_services_importance": "STRONG_PREFERENCE",
    "livability.avoid_dense_urban_core": True,
    "livability.avoid_dense_urban_core_importance": "STRONG_PREFERENCE",
}


PASS_2 = {
    "land.land_purchase_budget.absolute_max_thb": 500000,
    "land.land_purchase_budget.importance": "MUST",
    "road_access.legal_vehicle_access.required": True,
    "road_access.legal_vehicle_access.importance": "MUST",
    "road_access.all_weather_vehicle_access.required": True,
    "road_access.all_weather_vehicle_access.importance": "MUST",
    "road_access.tolerate_unpaved_local_access": True,
    "utilities.water.importance": "MUST",
    "utilities.water.must_be_verified_before_purchase": True,
    "utilities.water.accept_non_PWA_system_if_field_verified": True,
    "utilities.water.require_municipal_or_PWA_service": False,
    "utilities.telecom.minimum_requirement": "FIXED_FIBER",
    "utilities.telecom.importance": "MUST",
    "utilities.telecom.verification_stage": "BEFORE_PURCHASE",
    "utilities.telecom.substitutes_not_accepted": ["MOBILE_4G", "MOBILE_5G", "FIXED_WIRELESS", "SATELLITE"],
    "urban_access.hard_limit_policy": "CASE_BY_CASE",
    "land.willingness_to_improve_drainage": True,
    "land.willingness_to_build_retaining_structures": True,
    "land.willingness_to_grade_or_fill": True,
}  # fmt: skip
PASS_3 = {
    "healthcare.primary_healthcare.importance": "PREFERENCE",
    "healthcare.primary_healthcare.preferred_max_drive_minutes": 15,
    "utilities.electricity.grid_service_required": True,
    "utilities.electricity.importance": "MUST",
    "utilities.electricity.verification_stage": "BEFORE_PURCHASE",
    "utilities.electricity.must_be_verified_before_purchase": True,
    "utilities.electricity.tolerate_regional_uncertainty_during_screening": True,
    "utilities.water.well_water_acceptable": True,
    "land.terrain_preference": "GENTLE_ROLLING",
    "land.terrain_preference_importance": "PREFERENCE",
    "urban_access.airport_importance": "IRRELEVANT",
    "education.university.importance": "IRRELEVANT",
    "education.vocational.importance": "IRRELEVANT",
    "livability.avoid_industrial_nuisance.value": True,
    "livability.avoid_industrial_nuisance.importance": "STRONG_PREFERENCE",
    "livability.avoid_mining_quarry_nuisance.value": True,
    "livability.avoid_mining_quarry_nuisance.importance": "STRONG_PREFERENCE",
    "livability.avoid_major_road_noise.value": True,
    "livability.avoid_major_road_noise.importance": "STRONG_PREFERENCE",
    "livability.avoid_nightlife_concentration.value": True,
    "livability.avoid_nightlife_concentration.importance": "STRONG_PREFERENCE",
}  # fmt: skip
EXPECTED = PASS_1 | PASS_2 | PASS_3


def plain(v):
    return v.value if hasattr(v, "value") else v


def test_only_the_explicit_input_decisions_of_passes_1_to_3_are_set():
    r = load_requirements()
    ls = leaves(r)
    assert len(ls) == 97
    got = {p: plain(v) for p, v in ls if v != UNSET}
    assert got == EXPECTED  # exactly the decisions given, nothing inferred
    assert len(PASS_1) == 22 and len(PASS_2) == 19 and len(PASS_3) == 21
    assert r.status == "FAMILY_REQUIREMENTS_V0_1_CALIBRATED"
    assert check_requirements(r) == []  # consistent and no warnings


def test_everything_not_decided_stays_unset():
    r = load_requirements()
    unset = {p for p, v in leaves(r) if v == UNSET}
    must_stay = [
        "education.university.preferred_max_drive_minutes",
        "education.kindergarten.minimum_choices_within_preferred_time", "education.primary.minimum_choices_within_preferred_time",
        "education.lower_secondary.minimum_choices_within_preferred_time", "education.upper_secondary.minimum_choices_within_preferred_time",
        "healthcare.primary_healthcare.absolute_max_drive_minutes",
        "redundancy.number_of_primary_schools_within_time.minimum_count", "redundancy.number_of_secondary_schools_within_time.minimum_count",
        "redundancy.number_of_hospitals_within_time.minimum_count", "urban_access.absolute_max_drive_time_to_major_city_services",
        "urban_access.shopping_daily_services_importance",
        "road_access.major_road.importance", "road_access.major_road.maximum_baseline_drive_time_to_major_road",
        "road_access.route_redundancy_importance",
        "livability.preferred_population_density", "livability.tolerate_tourism_activity", "livability.tolerate_nightlife",
        "livability.industrial_nuisance_tolerance", "livability.agricultural_surroundings_preference",
        "livability.avoid_industrial_nuisance.buffer_distance_m", "livability.avoid_mining_quarry_nuisance.buffer_distance_m",
        "livability.avoid_major_road_noise.buffer_distance_m", "livability.avoid_nightlife_concentration.buffer_distance_m",
        "land.land_purchase_budget.preferred_thb", "land.house_construction_budget_thb",
        "land.preferred_area_rai", "land.minimum_area_rai", "land.maximum_area_rai", "land.terrain_tolerance",
    ]  # fmt: skip
    assert set(must_stay) <= unset
    assert (
        len(unset) == 35
    )  # 34 open items + the university time that sits inside an IRRELEVANT dimension
    assert not any(
        "quality" in p or "trauma" in p or "emergency" in p for p, _ in leaves(r)
    )  # not requirements at all


def test_choice_diversity_is_decision_context_not_a_gate():
    r = load_requirements()
    for name in ("kindergarten", "primary", "lower_secondary", "upper_secondary"):
        assert (
            getattr(r.education, name).minimum_choices_within_preferred_time == UNSET
        )  # no fixed minimum number of schools
    red = r.redundancy
    for item in (
        red.number_of_primary_schools_within_time,
        red.number_of_secondary_schools_within_time,
        red.number_of_hospitals_within_time,
    ):
        assert (
            item.minimum_count == UNSET
            and item.importance == UNSET
            and item.within_minutes == UNSET
        )
    # a single reachable institution inside the preferred band is perfectly consistent with these requirements
    assert not [
        i for i in validate_requirements(r) if "choice" in i.message.lower() or "redundan" in i.path
    ]
    assert "DECISION CONTEXT" in Path("config/family-requirements.yaml").read_text("utf-8")


def test_town_access_has_no_invented_absolute_maximum_and_pairs_are_validated():
    r = load_requirements()
    assert r.urban_access.preferred_drive_time_to_town_services == 35
    assert (
        r.urban_access.absolute_max_drive_time_to_major_city_services == UNSET
    )  # a different item, not set
    irrelevant = with_(livability__avoid_dense_urban_core_importance="IRRELEVANT")
    assert any("IRRELEVANT but a requirement value is set" in e for e in errors(irrelevant))
    no_imp = with_(urban_access__preferred_drive_time_to_town_services_importance=UNSET)
    assert any(
        i.severity == "WARNING" and "without an importance" in i.message
        for i in validate_requirements(no_imp)
    )
    assert not errors(no_imp)


def test_enabling_scoring_is_a_validation_error():
    r = with_(project_state__family_suitability_scoring__allowed=True)
    assert any("scoring must stay disabled" in i.message for i in validate_requirements(r))
    with pytest.raises(RequirementConflict):
        check_requirements(r)


def test_a_misspelt_requirement_key_is_rejected_not_defaulted():
    d = base()
    d["education"]["primary"]["prefered_max_drive_minutes"] = 15
    with pytest.raises(ValueError):
        Requirements(**d)


def test_required_sections_and_fields_exist():
    r = load_requirements()
    e = r.education
    for stage in (e.kindergarten, e.primary, e.lower_secondary, e.upper_secondary):
        assert {
            "importance",
            "preferred_max_drive_minutes",
            "absolute_max_drive_minutes",
            "minimum_choices_within_preferred_time",
        } <= set(type(stage).model_fields)
    assert set(type(e.vocational).model_fields) == {"importance"} and {
        "importance",
        "preferred_max_drive_minutes",
    } == set(type(e.university).model_fields)
    assert set(type(r.healthcare).model_fields) == {
        "primary_healthcare",
        "hospital",
        "regional_or_referral_hospital",
    }
    assert not any(
        "trauma" in p or "emergency" in p for p, _ in leaves(r)
    )  # capability is a future verification question
    assert set(type(r.redundancy).model_fields) == {
        "number_of_primary_schools_within_time",
        "number_of_secondary_schools_within_time",
        "number_of_hospitals_within_time",
    }
    assert {
        "tolerate_unpaved_local_access",
        "legal_vehicle_access",
        "all_weather_vehicle_access",
        "route_redundancy_importance",
        "major_road",
    } == set(type(r.road_access).model_fields)
    assert set(type(r.utilities).model_fields) == {"electricity", "water", "telecom"}
    assert {"airport_importance", "shopping_daily_services_importance"} <= set(
        type(r.urban_access).model_fields
    )
    assert {
        "preferred_population_density",
        "avoid_dense_urban_core",
        "industrial_nuisance_tolerance",
    } <= set(type(r.livability).model_fields)
    assert {
        "land_purchase_budget",
        "house_construction_budget_thb",
        "willingness_to_grade_or_fill",
        "terrain_tolerance",
        "willingness_to_improve_drainage",
        "willingness_to_build_retaining_structures",
    } <= set(type(r.land).model_fields)


# -- conflict detection ---------------------------------------------------------------------------------
def test_a_consistent_filled_requirement_passes():
    r = with_(
        education__primary={"importance": "MUST", "preferred_max_drive_minutes": 10, "absolute_max_drive_minutes": 20, "minimum_choices_within_preferred_time": 2},
        land__minimum_area_rai=1, land__maximum_area_rai=3, land__preferred_area_rai=2,
    )  # fmt: skip
    assert [i for i in validate_requirements(r) if i.severity == "ERROR"] == []


def errors(r: Requirements) -> list[str]:
    return [f"{i.path}: {i.message}" for i in validate_requirements(r) if i.severity == "ERROR"]


def test_preferred_time_above_absolute_maximum_fails():
    r = with_(
        education__primary={
            "importance": "MUST",
            "preferred_max_drive_minutes": 30,
            "absolute_max_drive_minutes": 20,
            "minimum_choices_within_preferred_time": UNSET,
        }
    )
    assert any("preferred time 30" in e for e in errors(r))
    h = with_(
        healthcare__hospital={
            "importance": "MUST",
            "preferred_max_drive_minutes": 60,
            "absolute_max_drive_minutes": 45,
        }
    )
    assert any("> absolute maximum" in e for e in errors(h))


def test_minimum_choices_below_one_fails_and_needs_a_preferred_time():
    r = with_(
        education__kindergarten={
            "importance": "PREFERENCE",
            "preferred_max_drive_minutes": 15,
            "absolute_max_drive_minutes": UNSET,
            "minimum_choices_within_preferred_time": 0,
        }
    )
    assert any("at least 1" in e for e in errors(r))
    r2 = with_(
        education__kindergarten={
            "importance": "PREFERENCE",
            "preferred_max_drive_minutes": UNSET,
            "absolute_max_drive_minutes": UNSET,
            "minimum_choices_within_preferred_time": 2,
        }
    )
    assert any("preferred time, which is UNSET" in e for e in errors(r2))


def test_irrelevant_item_with_thresholds_fails():
    r = with_(education__university={"importance": "IRRELEVANT", "preferred_max_drive_minutes": 45})
    assert any("IRRELEVANT but thresholds are set" in e for e in errors(r))
    with pytest.raises(RequirementConflict):
        check_requirements(r)


def test_other_contradictions_fail_and_nothing_is_normalised():
    assert any(
        "accepts a non-PWA" in e
        for e in errors(
            with_(
                utilities__water={
                    "accept_non_PWA_system_if_field_verified": True,
                    "require_municipal_or_PWA_service": True,
                    "well_water_acceptable": UNSET,
                }
            )
        )
    )
    assert any(
        "accepts well water" in e
        for e in errors(
            with_(
                utilities__water={
                    "accept_non_PWA_system_if_field_verified": UNSET,
                    "require_municipal_or_PWA_service": True,
                    "well_water_acceptable": True,
                }
            )
        )
    )
    assert any(
        "minimum area" in e
        for e in errors(with_(land__minimum_area_rai=5, land__maximum_area_rai=2))
    )
    assert any(
        "prefers URBAN" in e
        for e in errors(
            with_(
                livability__avoid_dense_urban_core=True,
                livability__preferred_population_density="URBAN",
            )
        )
    )
    assert any(
        "count below 1" in e
        for e in errors(
            with_(
                redundancy__number_of_hospitals_within_time={
                    "importance": "PREFERENCE",
                    "minimum_count": 0,
                    "within_minutes": 30,
                }
            )
        )
    )
    assert any(
        "set together" in e
        for e in errors(
            with_(
                redundancy__number_of_hospitals_within_time={
                    "importance": "PREFERENCE",
                    "minimum_count": 2,
                    "within_minutes": UNSET,
                }
            )
        )
    )
    assert any("negative value" in e for e in errors(with_(land__house_construction_budget_thb=-5)))
    assert any(
        "preferred 600000.0 > absolute maximum" in e
        for e in errors(
            with_(
                land__land_purchase_budget={
                    "preferred_thb": 600000,
                    "absolute_max_thb": 500000,
                    "importance": "MUST",
                }
            )
        )
    )
    assert any(
        "CASE_BY_CASE contradicts" in e
        for e in errors(with_(urban_access__absolute_max_drive_time_to_major_city_services=60))
    )
    bad = with_(
        education__primary={
            "importance": "MUST",
            "preferred_max_drive_minutes": 30,
            "absolute_max_drive_minutes": 20,
            "minimum_choices_within_preferred_time": UNSET,
        }
    )
    with pytest.raises(RequirementConflict):
        check_requirements(bad)
    assert (
        bad.education.primary.preferred_max_drive_minutes == 30
        and bad.education.primary.absolute_max_drive_minutes == 20
    )  # never repaired


def test_incomplete_but_consistent_requirements_only_warn():
    r = with_(
        education__primary={
            "importance": "MUST",
            "preferred_max_drive_minutes": UNSET,
            "absolute_max_drive_minutes": UNSET,
            "minimum_choices_within_preferred_time": UNSET,
        }
    )
    issues = validate_requirements(r)
    assert not [i for i in issues if i.severity == "ERROR"] and any(
        "no threshold is set yet" in i.message for i in issues
    )
    assert check_requirements(r)  # returns the warnings, does not raise


def test_importance_vocabulary_is_fixed():
    with pytest.raises(ValueError):
        with_(education__primary={"importance": "CRITICAL"})
    for v in ("MUST", "STRONG_PREFERENCE", "PREFERENCE", "NICE_TO_HAVE", "IRRELEVANT"):
        with_(education__vocational={"importance": v})


# -- evidence matrix -----------------------------------------------------------------------------------
def test_matrix_covers_every_requirement_and_keeps_three_concepts_separate():
    req, cap = load_requirements(), load_capability()
    rows = evidence_matrix(req, cap)
    reqrows = [r for r in rows if r["kind"] == "USER_REQUIREMENT"]
    assert len(reqrows) == len(leaves(req)) == 97
    assert {r["requirement_path"] for r in reqrows} == {p for p, _ in leaves(req)}
    assert all(
        r["evaluation_rule"] == EVALUATION_RULE for r in rows
    )  # EVALUATION_RULE is not active anywhere
    assert {"user_requirement_value", "data_capability", "evaluation_rule"} <= set(rows[0])
    assert not [k for k in rows[0] if "score" in k.lower() or "rank" in k.lower()]


def test_missing_data_never_rewrites_the_user_preference():
    cap = load_capability()
    r = with_(
        education__primary={
            "importance": "MUST",
            "preferred_max_drive_minutes": 10,
            "absolute_max_drive_minutes": 20,
            "minimum_choices_within_preferred_time": 2,
        },
        utilities__telecom={
            "minimum_requirement": "FIXED_BROADBAND",
            "verification_stage": "SHORTLIST",
        },
    )
    rows = {x["requirement_path"]: x for x in evidence_matrix(r, cap)}
    assert rows["education.primary.preferred_max_drive_minutes"]["user_requirement_value"] == 10
    assert (
        rows["education.primary.preferred_max_drive_minutes"]["data_capability"]
        == "PARTIALLY_SUPPORTED"
    )  # data is partial, the requirement stays 10
    assert (
        rows["utilities.telecom.minimum_requirement"]["user_requirement_value"] == "FIXED_BROADBAND"
    )
    assert rows["utilities.telecom.minimum_requirement"]["data_capability"] == "NOT_SUPPORTED"
    assert rows["education.primary.preferred_max_drive_minutes"]["needs_user_input"] is False


def test_newly_filled_requirements_keep_their_values_and_honest_support_status():
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    for path, value in PASS_1.items():
        assert (
            plain(rows[path]["user_requirement_value"]) == value
        )  # no preference was modified because of evidence gaps
        assert (
            rows[path]["needs_user_input"] is False
            and rows[path]["evaluation_rule"] == EVALUATION_RULE
        )
    assert all(
        rows[p]["data_capability"] == "PARTIALLY_SUPPORTED"
        for p in PASS_1
        if p.startswith("education.")
    )  # education stays partial
    assert all(
        rows[p]["data_capability"] == "SUPPORTED_WITH_LIMITATIONS"
        for p in PASS_1
        if p.startswith("healthcare.")
    )
    assert all(
        rows[p]["data_capability"] == "NOT_SUPPORTED"
        for p in PASS_1
        if p.startswith(("urban_access.", "livability."))
    )
    scoring = load_requirements().project_state.family_suitability_scoring
    assert scoring == {"allowed": False}


def test_capability_statuses_are_honest_about_current_evidence():
    cap = load_capability()["capabilities"]
    only = load_capability()["capability_only"]
    assert all(
        cap[k]["status"] == "PARTIALLY_SUPPORTED" for k in cap if k.startswith("education.")
    )  # register is stale/partial
    assert cap["healthcare.regional_or_referral_hospital"]["status"] == "SUPPORTED_WITH_LIMITATIONS"
    assert cap["healthcare.hospital"]["status"] == "SUPPORTED_WITH_LIMITATIONS"
    for k in (
        "road_access.tolerate_unpaved_local_access",
        "road_access.legal_vehicle_access",
        "road_access.all_weather_vehicle_access",
        "utilities.electricity",
        "utilities.water",
        "utilities.telecom",
    ):
        assert cap[k]["status"] == "NOT_SUPPORTED"
    assert (
        only["school_quality"]["status"] == "NOT_SUPPORTED"
        and only["emergency_trauma_icu_capability"]["status"] == "NOT_SUPPORTED"
    )
    assert not any(
        v["status"] == "SUPPORTED" for v in {**cap, **only}.values()
    )  # nothing is fully supported yet


def test_evidence_columns_exist_in_the_m2a_artifact():
    if not ARTIFACT.exists():
        pytest.skip("M2A.2 artifact not built")
    cols = set(pd.read_parquet(ARTIFACT).columns)
    cap = load_capability()
    for k, v in {**cap["capabilities"], **cap["capability_only"]}.items():
        missing = [c for c in v.get("evidence_columns", []) if c not in cols]
        assert not missing, f"{k}: {missing}"


def test_education_source_backlog_stays_open_and_unmerged():
    cap = load_capability()
    opts = {o["id"]: o for o in cap["education_source_options"]["options"]}
    assert cap["education_source_options"]["combine_in_m2b0"] is False
    assert opts["moe-ckan-per-school-resource"]["state"] == "TEMPORARILY_UNREACHABLE"
    assert {
        "dopa-2021",
        "obec-2563",
        "dla-school-list-2569",
        "opec-private-school-current",
        "vocational-current",
        "osm-validation",
    } <= set(opts)


def test_m2b0_has_no_scoring_code_and_reads_no_grid():
    src = Path("src/hearthmap/family/requirements.py").read_text("utf-8")
    tree = ast.parse(src)
    imported = {
        n.module.split(".")[0]
        if isinstance(n, ast.ImportFrom) and n.module
        else a.name.split(".")[0]
        for n in ast.walk(tree)
        for a in (getattr(n, "names", []) or [None])
        if (isinstance(n, ast.Import | ast.ImportFrom) and a is not None)
        or isinstance(n, ast.ImportFrom)
    }
    assert not imported & {
        "numpy",
        "pandas",
        "geopandas",
        "shapely",
        "rasterio",
    }  # nothing here can touch cells
    assert "def score" not in src and "rank_" not in src


# -- input pass 2 --------------------------------------------------------------------------------------
def test_land_ceiling_is_the_land_purchase_price_only_and_invents_no_preferred_budget():
    b = load_requirements().land
    assert (
        b.land_purchase_budget.absolute_max_thb == 500000
        and b.land_purchase_budget.importance == Importance.MUST
    )
    assert (
        b.land_purchase_budget.preferred_thb == UNSET
    )  # no preferred budget below the ceiling was invented
    assert (
        b.house_construction_budget_thb == UNSET
    )  # the ceiling says nothing about construction cost
    assert (b.preferred_area_rai, b.minimum_area_rai, b.maximum_area_rai) == (
        UNSET,
        UNSET,
        UNSET,
    )  # no rai/ngan inferred
    assert "budget_thb" not in {
        p.split(".")[-1] for p, _ in leaves(load_requirements())
    }  # the ambiguous old field is gone
    assert "BARE LAND" in Path("config/family-requirements.yaml").read_text("utf-8")


def test_access_requirements_are_must_but_not_provable_regionally():
    r = load_requirements().road_access
    assert (
        r.legal_vehicle_access.required is True
        and r.legal_vehicle_access.importance == Importance.MUST
    )
    assert (
        r.all_weather_vehicle_access.required is True
        and r.all_weather_vehicle_access.importance == Importance.MUST
    )
    assert (
        r.tolerate_unpaved_local_access is True
    )  # an unpaved final access is acceptable if it stays usable
    assert (
        r.major_road.maximum_baseline_drive_time_to_major_road == UNSET
    )  # no major-road threshold inferred
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    for k in (
        "road_access.legal_vehicle_access.required",
        "road_access.all_weather_vehicle_access.required",
    ):
        assert (
            rows[k]["data_capability"] == "NOT_SUPPORTED"
            and rows[k]["evidence_stage"] == "PARCEL_VERIFICATION"
        )
    assert (
        rows["road_access.tolerate_unpaved_local_access"]["evidence_stage"] == "FIELD_VERIFICATION"
    )
    assert not [
        i for i in validate_requirements(load_requirements()) if i.path.startswith("road_access")
    ]  # unpaved + all-weather is not a contradiction


def test_water_accepts_non_pwa_only_after_field_verification_and_well_water_is_allowed():
    w = load_requirements().utilities.water
    assert (
        w.require_municipal_or_PWA_service is False
        and w.accept_non_PWA_system_if_field_verified is True
    )
    assert w.must_be_verified_before_purchase is True and w.importance == Importance.MUST
    assert (
        w.well_water_acceptable is True
    )  # input pass 3: groundwater is an acceptable possible source
    assert (
        w.require_municipal_or_PWA_service is False
    )  # the earlier water requirements are unchanged
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    r = rows["utilities.water.accept_non_PWA_system_if_field_verified"]
    assert r["data_capability"] == "NOT_SUPPORTED" and r["evidence_stage"] == "FIELD_VERIFICATION"
    assert (
        "NOT confirmation" in r["capability_reason"]
    )  # outside PWA never becomes 'acceptable water confirmed'


def test_fiber_is_a_must_that_missing_evidence_cannot_weaken():
    t = load_requirements().utilities.telecom
    assert (
        t.minimum_requirement == "FIXED_FIBER"
        and t.importance == Importance.MUST
        and t.verification_stage == "BEFORE_PURCHASE"
    )
    assert (
        t.minimum_requirement != "FIXED_BROADBAND"
    )  # fixed fiber is distinguished from generic broadband
    assert set(t.substitutes_not_accepted) == {
        "MOBILE_4G",
        "MOBILE_5G",
        "FIXED_WIRELESS",
        "SATELLITE",
    }
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    m = rows["utilities.telecom.minimum_requirement"]
    assert (
        m["data_capability"] == "NOT_SUPPORTED" and m["user_requirement_value"] == "FIXED_FIBER"
    )  # evidence gap, requirement intact
    assert rows["utilities.telecom.importance"]["user_requirement_value"] == "MUST"
    assert any(
        "IRRELEVANT but a minimum requirement is set" in e
        for e in errors(
            with_(
                utilities__telecom={
                    "minimum_requirement": "FIXED_FIBER",
                    "importance": "IRRELEVANT",
                }
            )
        )
    )


def test_town_limit_is_case_by_case_and_shopping_has_no_separate_threshold():
    r = load_requirements()
    ua = r.urban_access
    assert (
        ua.preferred_drive_time_to_town_services == 35
        and ua.preferred_drive_time_to_town_services_importance == Importance.STRONG_PREFERENCE
    )  # pass 1 preserved
    assert (
        ua.absolute_max_drive_time_to_major_city_services == UNSET
        and ua.hard_limit_policy == "CASE_BY_CASE"
    )  # 'case by case' is not a number
    assert (
        ua.shopping_daily_services_importance == UNSET
    )  # no independently invented daily-essentials threshold
    assert not any("shopping" in p and isinstance(v, float) for p, v in leaves(r))
    rows = {x["requirement_path"]: x for x in evidence_matrix(r, load_capability())}
    assert rows["urban_access.hard_limit_policy"]["evidence_stage"] == "USER_REQUIREMENT_ONLY"


def test_site_improvement_willingness_is_permissive_user_requirement_only_and_never_overrides_hazards():
    r = load_requirements()
    land = r.land
    assert (
        land.willingness_to_improve_drainage is True
        and land.willingness_to_build_retaining_structures is True
        and land.willingness_to_grade_or_fill is True
    )
    assert land.terrain_tolerance == UNSET  # not inferred from willingness to improve
    assert not any(
        "allowance" in p or "improvement_budget" in p for p, _ in leaves(r)
    )  # no financial allowance invented
    hc = r.hazard_contract
    assert (
        hc.m1e_actions_immutable
        and not hc.site_improvement_willingness_overrides_hazard_actions
        and not hc.family_access_offsets_hazard_actions
    )
    rows = {x["requirement_path"]: x for x in evidence_matrix(r, load_capability())}
    for k in (
        "land.willingness_to_improve_drainage",
        "land.willingness_to_build_retaining_structures",
        "land.willingness_to_grade_or_fill",
    ):
        assert (
            rows[k]["evidence_stage"] == "USER_REQUIREMENT_ONLY"
            and rows[k]["user_requirement_value"] is True
        )
    for field in (
        "site_improvement_willingness_overrides_hazard_actions",
        "family_access_offsets_hazard_actions",
    ):
        bad = base()
        bad["hazard_contract"][field] = True
        with pytest.raises(RequirementConflict):
            check_requirements(Requirements(**bad))
    bad = base()
    bad["hazard_contract"]["m1e_actions_immutable"] = False
    with pytest.raises(RequirementConflict):
        check_requirements(Requirements(**bad))


def test_not_supported_is_not_failure_and_no_hazard_columns_enter_the_matrix():
    rows = evidence_matrix(load_requirements(), load_capability())
    assert all(
        r["evaluation_rule"] == EVALUATION_RULE for r in rows
    )  # every evaluation rule stays inactive
    assert not any(
        "flood" in r["requirement_path"]
        or "landslide" in r["requirement_path"]
        or "hazard" in r["requirement_path"]
        for r in rows
    )
    assert {r["evidence_stage"] for r in rows} <= {
        "REGIONAL_EVIDENCE",
        "EVIDENCE_MISSING",
        "PARCEL_VERIFICATION",
        "FIELD_VERIFICATION",
        "USER_REQUIREMENT_ONLY",
    }
    assert [i for i in validate_requirements(load_requirements()) if i.severity == "ERROR"] == []


# -- input pass 3 / closure --------------------------------------------------------------------------
def test_grid_electricity_is_a_must_verified_before_purchase_and_missing_evidence_only_triggers_verification():
    e = load_requirements().utilities.electricity
    assert (
        e.grid_service_required is True
        and e.importance == Importance.MUST
        and e.verification_stage == "BEFORE_PURCHASE"
    )
    assert (
        e.must_be_verified_before_purchase is True
        and e.tolerate_regional_uncertainty_during_screening is True
    )  # verify, never reject
    assert not any(
        k in type(e).model_fields
        for k in ("capacity", "transformer", "phase", "connection_cost", "reliability")
    )  # nothing inferred
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    r = rows["utilities.electricity.grid_service_required"]
    assert (
        r["data_capability"] == "NOT_SUPPORTED"
        and r["evidence_stage"] == "PARCEL_VERIFICATION"
        and r["user_requirement_value"] is True
    )
    assert "never rejection" in r["capability_reason"]
    assert any(
        i.severity == "ERROR"
        for i in validate_requirements(
            with_(
                utilities__electricity={"grid_service_required": True, "importance": "IRRELEVANT"}
            )
        )
    )


def test_primary_healthcare_is_a_preference_not_a_gate_and_hospital_rules_are_unchanged():
    h = load_requirements().healthcare
    assert (
        h.primary_healthcare.preferred_max_drive_minutes == 15
        and h.primary_healthcare.importance == Importance.PREFERENCE
    )
    assert h.primary_healthcare.absolute_max_drive_minutes == UNSET  # not a hard gate
    assert (
        h.hospital.importance,
        h.hospital.preferred_max_drive_minutes,
        h.hospital.absolute_max_drive_minutes,
    ) == (Importance.MUST, 20, 35)
    assert (
        h.regional_or_referral_hospital.importance,
        h.regional_or_referral_hospital.preferred_max_drive_minutes,
        h.regional_or_referral_hospital.absolute_max_drive_minutes,
    ) == (Importance.STRONG_PREFERENCE, 45, 75)
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    assert (
        rows["healthcare.primary_healthcare.preferred_max_drive_minutes"]["data_capability"]
        == "SUPPORTED_WITH_LIMITATIONS"
    )


def test_terrain_preference_is_non_numeric_and_subordinate_to_hazards():
    ld = load_requirements().land
    assert (
        ld.terrain_preference == "GENTLE_ROLLING"
        and ld.terrain_preference_importance == Importance.PREFERENCE
    )
    assert (
        ld.terrain_tolerance == UNSET
    )  # not 'steep is acceptable' and not 'any slope is acceptable'
    assert not any(
        "slope" in p or "degree" in p for p, _ in leaves(load_requirements())
    )  # no slope-degree range invented
    assert any(
        "contradicts terrain tolerance" in e
        for e in errors(with_(land__terrain_tolerance="FLAT_ONLY"))
    )  # a preference conflicting with a stated tolerance fails
    bad = base()
    bad["hazard_contract"]["terrain_preference_overrides_hazard_actions"] = True
    with pytest.raises(RequirementConflict):
        check_requirements(Requirements(**bad))
    assert load_requirements().hazard_contract.terrain_preference_overrides_hazard_actions is False
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    assert (
        rows["land.terrain_preference"]["data_capability"] == "PARTIALLY_SUPPORTED"
        and rows["land.terrain_preference"]["evaluation_rule"] == EVALUATION_RULE
    )


def test_irrelevant_dimensions_are_excluded_from_evaluation_in_the_matrix():
    r = load_requirements()
    assert r.urban_access.airport_importance == Importance.IRRELEVANT
    assert (
        r.education.university.importance == Importance.IRRELEVANT
        and r.education.vocational.importance == Importance.IRRELEVANT
    )
    rows = {x["requirement_path"]: x for x in evidence_matrix(r, load_capability())}
    for k in (
        "urban_access.airport_importance",
        "education.university.importance",
        "education.university.preferred_max_drive_minutes",
        "education.vocational.importance",
    ):
        assert (
            rows[k]["data_capability"] == "NOT_APPLICABLE_IRRELEVANT"
            and rows[k]["evaluation_use"] == "EXCLUDED_BY_USER"
            and rows[k]["needs_user_input"] is False
        )
    assert (
        rows["education.university.importance"]["underlying_capability"] == "PARTIALLY_SUPPORTED"
    )  # still shown for information
    assert [k for k, v in rows.items() if v["evaluation_use"] == "EXCLUDED_BY_USER"] == [
        k
        for k in rows
        if k
        in (
            "education.vocational.importance",
            "education.university.importance",
            "education.university.preferred_max_drive_minutes",
            "urban_access.airport_importance",
        )
    ]
    # an IRRELEVANT dimension that still carries a threshold is a contradiction
    assert any(
        "IRRELEVANT but thresholds are set" in e
        for e in errors(
            with_(
                education__university={
                    "importance": "IRRELEVANT",
                    "preferred_max_drive_minutes": 45,
                }
            )
        )
    )


def test_nuisance_avoidances_are_preferences_without_buffers_or_hard_exclusions():
    lv = load_requirements().livability
    for name in (
        "avoid_industrial_nuisance",
        "avoid_mining_quarry_nuisance",
        "avoid_major_road_noise",
        "avoid_nightlife_concentration",
    ):
        a = getattr(lv, name)
        assert (
            a.value is True and a.importance == Importance.STRONG_PREFERENCE
        )  # preference, not MUST
        assert a.buffer_distance_m == UNSET  # no exclusion distance was supplied
    assert "hard_exclusion" not in " ".join(p for p, _ in leaves(load_requirements()))
    rows = {
        x["requirement_path"]: x for x in evidence_matrix(load_requirements(), load_capability())
    }
    for name in (
        "industrial_nuisance",
        "mining_quarry_nuisance",
        "major_road_noise",
        "nightlife_concentration",
    ):
        r = rows[f"livability.avoid_{name}.value"]
        assert r["data_capability"] == "NOT_SUPPORTED" and r["evidence_stage"] == "EVIDENCE_MISSING"
    assert (
        "not automatically a nuisance"
        in rows["livability.avoid_industrial_nuisance.value"]["capability_reason"]
    )
    assert (
        "not the existence of restaurants"
        in rows["livability.avoid_nightlife_concentration.value"]["capability_reason"]
    )
    assert any(
        "matching tolerance is HIGH" in e
        for e in errors(with_(livability__tolerate_nightlife="HIGH"))
    )


def test_major_road_access_and_major_road_noise_stay_separate_concepts():
    r = load_requirements()
    access = {p for p, _ in leaves(r) if p.startswith("road_access.major_road")}
    noise = {p for p, _ in leaves(r) if p.startswith("livability.avoid_major_road_noise")}
    assert access and noise and not access & noise
    assert (
        r.road_access.major_road.maximum_baseline_drive_time_to_major_road == UNSET
    )  # access threshold still unset
    assert r.livability.avoid_major_road_noise.value is True
    rows = {x["requirement_path"]: x for x in evidence_matrix(r, load_capability())}
    assert (
        "different concept" in rows["livability.avoid_major_road_noise.value"]["capability_reason"]
    )


SUMMARY = Path("docs/product/family-requirements-v0.1-summary.md")


def test_closure_summary_is_generated_from_the_config_and_separates_the_five_groups():
    from hearthmap.family.requirements import render_summary

    text = render_summary(load_requirements(), load_capability())
    assert SUMMARY.read_text("utf-8").strip() == text.strip()  # no drift from the config
    for heading in (
        "## A. Active user requirements",
        "## B. Explicitly irrelevant dimensions",
        "## C. Intentionally UNSET / case-by-case",
        "## D. Active requirements currently not evaluable",
        "## E. Requirements that must be verified at the parcel",
    ):
        assert heading in text
    assert "FAMILY_REQUIREMENTS_V0_1_CALIBRATED" in text and "not authorised" in text
    assert "intentional UNSET is valid product truth" in text
    b = text.split("## B.")[1].split("## C.")[0]
    assert (
        "education.university" in b and "education.vocational" in b and "urban_access.airport" in b
    )
    d = text.split("## D.")[1].split("## E.")[0]
    assert (
        "willingness_to_improve_drainage" not in d
    )  # user-requirement-only tolerances are not 'missing evidence'
