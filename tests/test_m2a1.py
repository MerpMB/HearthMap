# ruff: noqa: E501
"""M2A.1 facility refresh: roles, reconciliation, authoritative classification, frozen routing."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from hearthmap.family import classify_education, load_config
from hearthmap.family.reconcile import (
    FacilitySource,
    compose_primary,
    health_comparison_name,
    reconcile,
    summarise,
)
from hearthmap.family.taxonomy import levels_from_class_range, resolve_levels

CFG = load_config()
NEW = Path("outputs/m2a1/family-infrastructure-evidence.parquet")
OLD = Path("outputs/m2a/family-infrastructure-evidence.parquet")
FROZEN_ROUTING_FINGERPRINT = (
    "5c35e98882c3ac62"  # sha256 of config travel_time (BASELINE_DRIVE_TIME) at M2A acceptance
)

STALE = FacilitySource("stale register", 2021, "FALLBACK", current=False)
CURRENT = FacilitySource("current validation", 2026, "CURRENT_VALIDATION", current=True)
AUTH = FacilitySource("authoritative classes", 2020, "AUTHORITATIVE_CLASSIFICATION", current=False)


def frame(rows):
    return pd.DataFrame(rows, columns=["rec_id", "name", "x", "y"])


# -- source roles ---------------------------------------------------------------------------------------
def test_current_source_cannot_be_silently_mixed_with_stale():
    primary = frame([("a", "โรงเรียนบ้านสัน", 0, 0)])
    other = frame([("o1", "โรงเรียนใหม่", 5000, 5000)])
    out = compose_primary(primary, STALE, {"osm": (other, CURRENT)})
    assert list(out["rec_id"]) == ["a"]  # validation rows are never appended to the primary layer
    with pytest.raises(
        ValueError
    ):  # a second primary-type source would mix stale and current silently
        compose_primary(
            primary, STALE, {"other": (other, FacilitySource("x", 2026, "FALLBACK", True))}
        )
    with pytest.raises(ValueError):
        compose_primary(
            primary, FacilitySource("x", 2026, "CURRENT_VALIDATION", True), {}
        )  # validation data cannot be the layer


def test_source_roles_are_preserved_on_the_layer():
    primary = frame([("a", "x", 0, 0)])
    out = compose_primary(primary, STALE, {"auth": (primary, AUTH)})
    assert (
        out["primary_source_role"].iloc[0] == "FALLBACK"
        and not out["primary_source_current"].iloc[0]
    )
    assert out["primary_source_vintage_year"].iloc[0] == 2021
    with pytest.raises(ValueError):
        FacilitySource("bad", 2026, "TRUTH", True)


# -- reconciliation -------------------------------------------------------------------------------------
def test_reconciliation_current_only_legacy_only_possible_and_conflict_keep_evidence():
    cur = frame([
        ("c_match", "โรงเรียนบ้านสัน", 0, 0),
        ("c_only", "โรงเรียนใหม่ทั้งหมด", 20000, 20000),
        ("c_conflict", "โรงเรียนบ้านไกล", 100, 100),
        ("c_possible", "โรงเรียนชื่อใหม่", 9000, 9000),
    ])  # fmt: skip
    leg = frame([
        ("l_match", "บ้านสัน", 40, 30),  # generic prefix ignored, within 300 m
        ("l_only", "โรงเรียนปิดไปแล้ว", 50000, 50000),
        ("l_conflict", "บ้านไกล", 1500, 100),  # same name, coordinates disagree
        ("l_possible", "โรงเรียนชื่อเก่า", 9050, 9000),  # different name 50 m away: not merged
    ])  # fmt: skip
    r = reconcile(cur, leg)
    s = r[r.side == "current_side"].set_index("rec_id")
    assert (
        s.loc["c_match", "status"] == "MATCHED"
        and s.loc["c_match", "evidence"] == "IDENTICAL_NAME_WITHIN_RADIUS"
    )
    assert s.loc["c_only", "status"] == "CURRENT_ONLY"
    assert (
        s.loc["c_conflict", "status"] == "CONFLICT" and s.loc["c_conflict", "distance_m"] > 1000
    )  # disagreement is visible
    assert (
        s.loc["c_possible", "status"] == "POSSIBLE_MATCH"
        and s.loc["c_possible", "counterpart_rec_id"] == "l_possible"
    )
    leg_only = r[(r.side == "legacy_side")]
    assert set(leg_only[leg_only.status == "LEGACY_ONLY"]["rec_id"]) == {
        "l_only"
    }  # stale-only stays stale-only, not 'closed'
    sm = summarise(r)
    assert (
        sm["current_side_matched"] == 1
        and sm["legacy_side_only"] == 1
        and sm["match_rate_pct"] == 25.0
    )


def test_same_name_far_away_is_a_different_school_not_a_conflict():
    r = reconcile(frame([("c", "โรงเรียนบ้านสันติสุข", 0, 0)]), frame([("l", "บ้านสันติสุข", 50000, 0)]))
    assert r[r.side == "current_side"].iloc[0]["status"] == "CURRENT_ONLY"


def test_official_id_matches_first_and_coordinate_conflict_is_flagged_not_resolved():
    cur, leg = frame([("c", "ชื่อ ก", 0, 0)]), frame([("l", "ชื่อ ข", 3000, 0)])
    cur["oid"], leg["oid"] = "123", "123"
    r = reconcile(cur, leg, id_col_current="oid", id_col_legacy="oid")
    row = r[r.side == "current_side"].iloc[0]
    assert (
        row["evidence"] == "OFFICIAL_ID"
        and row["status"] == "CONFLICT"
        and row["distance_m"] == 3000
    )  # not silently picked


def test_health_names_compare_on_the_facility_core():
    assert health_comparison_name(
        "โรงพยาบาลส่งเสริมสุขภาพตำบลบ้านกอกหม่น ตำบลสันปูเลย จังหวัดเชียงใหม่"
    ) == health_comparison_name("รพ.สต.บ้านกอกหม่น")


# -- classification -------------------------------------------------------------------------------------
def test_authoritative_classification_outranks_name_inference():
    derived = classify_education("โรงเรียนบ้านสันถนน", "2050", CFG)  # name implies PRIMARY (LOW)
    assert derived["levels"] == ["PRIMARY"]
    res = resolve_levels(derived, levels_from_class_range("ม.1", "ม.6"), "ม.1-ม.6")
    assert res["normalized_levels"] == [
        "LOWER_SECONDARY",
        "UPPER_SECONDARY",
    ]  # the source field wins
    assert (
        res["normalization_method"] == "AUTHORITATIVE_CLASS_RANGE"
        and res["derived"] is False
        and res["source_native_levels"] == "ม.1-ม.6"
    )
    fallback = resolve_levels(derived, None)
    assert fallback["derived"] is True and fallback["normalization_method"].startswith("DERIVED_")


def test_class_range_mapping_and_unknown_stays_unknown():
    assert levels_from_class_range("อ.2", "ม.3") == ["KINDERGARTEN", "PRIMARY", "LOWER_SECONDARY"]
    assert levels_from_class_range("ป.1", "ป.6") == ["PRIMARY"]
    assert levels_from_class_range("ม.4", "ม.6") == ["UPPER_SECONDARY"]
    assert levels_from_class_range("0", "0") == ["UNKNOWN"] and levels_from_class_range(
        None, "ป.6"
    ) == ["UNKNOWN"]
    assert (
        resolve_levels(
            {"levels": ["UNKNOWN"], "level_basis": "NONE", "level_confidence": "NONE"}, ["UNKNOWN"]
        )["normalization_method"]
        == "UNKNOWN"
    )


# -- artifacts ------------------------------------------------------------------------------------------
def need(path: Path) -> pd.DataFrame:
    if not path.exists():
        pytest.skip(f"{path} not built")
    return pd.read_parquet(path)


def test_inaccessible_hospital_level_fields_remain_unresolved():
    new = need(NEW)
    assert new["hospital_level_status"].str.startswith("PARTIALLY_ASSESSED").all()
    assert not new[
        "route_available_higher_level_hospital"
    ].any()  # no accessible authoritative level => nothing computed
    assert (
        new["higher_level_hospital_unresolved_reason"]
        == "CATEGORY_DEFERRED_NO_VERIFIED_CLASSIFICATION"
    ).all()
    facilities = Path("data/processed/m2a1/facilities.gpkg")
    if facilities.exists():
        import geopandas as gpd

        hl = gpd.read_file(facilities, layer="health_facilities")
        assert (
            not hl["facility_class"]
            .isin(["REGIONAL_OR_TERTIARY_HOSPITAL", "GENERAL_HOSPITAL", "COMMUNITY_HOSPITAL"])
            .any()
        )
        assert hl["capabilities_source_supported"].fillna("").eq("").all()  # no capability inferred


def test_refreshing_facilities_cannot_change_routing_assumptions():
    fp = hashlib.sha256(json.dumps(CFG["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
    assert (
        fp == FROZEN_ROUTING_FINGERPRINT
    )  # speeds, bands, snap distance, search limit and name are frozen
    new = need(NEW)
    assert new["routing_config_fingerprint"].unique().tolist() == [FROZEN_ROUTING_FINGERPRINT]
    assert new["routing_basis"].eq("BASELINE_DRIVE_TIME").all()
    old = need(OLD)
    # the road-derived context does not depend on facilities and must be identical
    for c in ("road_snap_distance_m", "road_access_context", "nearest_major_road_distance_m"):
        pd.testing.assert_series_equal(old[c], new[c])


def test_refresh_keeps_unresolved_cells_unresolved_and_euclid_diagnostic():
    new = need(NEW)
    for c in [
        x[len("route_available_") :] for x in new.columns if x.startswith("route_available_")
    ]:
        failed = ~new[f"route_available_{c}"]
        assert new.loc[failed, f"drive_time_to_nearest_{c}_min"].isna().all()
        assert f"euclidean_distance_to_nearest_{c}_km_diagnostic" in new.columns
    assert not [c for c in new.columns if "score" in c.lower()]


def test_hazard_actions_remain_immutable_after_refresh():
    m1e = Path("outputs/m1e/natural-hazard-actions.parquet")
    new = need(NEW)
    if not m1e.exists():
        pytest.skip("m1e not built")
    haz = pd.read_parquet(m1e)
    action_cols = [
        c
        for c in haz.columns
        if c.endswith("_action") or c.startswith("natural_hazard") or c == "hazard_action_set"
    ]
    assert action_cols and not set(action_cols) & set(new.columns)
    merged = haz.merge(new, on="cell_id", how="left", suffixes=("", "_fam"))
    for c in action_cols:
        assert merged[c].equals(haz[c])
    assert set(haz["cell_id"]) == set(new["cell_id"]) and new["cell_id"].is_unique  # same cells; row order is irrelevant
