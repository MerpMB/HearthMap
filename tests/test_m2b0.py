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
    assert r.status == "AWAITING_USER_INPUT"


def test_every_requirement_is_unset_no_invented_defaults():
    r = load_requirements()
    ls = leaves(r)
    assert len(ls) == 65
    assert all(
        v == UNSET for _, v in ls
    )  # populated only with explicit user decisions; none given yet
    assert check_requirements(r) == []  # an all-UNSET file is consistent, with no warnings


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
        "minimum_all_weather_access_expectation",
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
        "budget_thb",
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
    assert any("negative value" in e for e in errors(with_(land__budget_thb=-5)))
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
    assert len(reqrows) == len(leaves(req)) == 65
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
        "road_access.minimum_all_weather_access_expectation",
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
