# ruff: noqa: E501
"""M2A family & infrastructure evidence: semantics that must never silently change."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hearthmap.family import (
    FORBIDDEN_FIELDS,
    build_network,
    classify_education,
    classify_health,
    coordinate_flags,
    deduplicate,
    electricity_context,
    freshness,
    load_config,
    multi_source_dijkstra,
    telecom_context,
    water_context,
)
from hearthmap.family.config import load_reference_levels
from hearthmap.family.routing import reverse

CFG = load_config()
ARTIFACT = Path("outputs/m2a/family-infrastructure-evidence.parquet")


def way(coords, hw="residential", oneway=None):
    xy = np.array(coords, dtype=float)
    keys = (xy[:, 0] * 10).astype(np.int64) * (1 << 28) + (xy[:, 1] * 10).astype(np.int64)
    return {"keys": keys, "xy": xy, "highway": hw, "oneway": oneway}


def two_islands():
    """A 3-node line (0,0)-(1000,0)-(2000,0) plus an isolated 2-node fragment far away."""
    return build_network(
        [
            way([(0, 0), (1000, 0), (2000, 0)], "secondary"),
            way([(50000, 0), (51000, 0)], "residential"),
        ]
    )


# -- taxonomy ---------------------------------------------------------------------------------------------
def test_education_native_type_preserved_and_multi_level_possible():
    r = classify_education("โรงเรียนอนุบาลสุขเจริญวิทยาคม", "2120", CFG)
    assert r["native_type"] == "2120"  # source-native code is untouched
    assert {"KINDERGARTEN", "LOWER_SECONDARY", "UPPER_SECONDARY"} <= set(
        r["levels"]
    )  # several levels allowed
    assert r["derived"] is True and r["level_basis"] != "NONE"


def test_education_levels_are_marked_derived_and_confidence_qualified():
    r = classify_education("โรงเรียนบ้านสันถนน", "2050", CFG)
    assert (
        r["levels"] == ["PRIMARY"] and r["level_confidence"] == "LOW"
    )  # name gives no level: default, LOW
    assert classify_education("มหาวิทยาลัยเทคโนโลยีราชมงคลล้านนา", "2010", CFG)["levels"] == [
        "UNIVERSITY_TERTIARY"
    ]  # not 'vocational'
    assert classify_education("ศูนย์พัฒนาเด็กเล็กบ้านท่า", "2170", CFG)["levels"] == ["EARLY_CHILDHOOD"]
    assert classify_education("ห้องสมุดโรงเรียนบ้านแม่", "2200", CFG)["levels"] == [
        "OTHER"
    ]  # a library is not a schooling pathway
    assert classify_education("???", None, CFG)["levels"] == ["UNKNOWN"]


def test_school_presence_is_not_quality():
    r = classify_education("โรงเรียนบ้านสันถนน", "2050", CFG)
    assert not set(FORBIDDEN_FIELDS) & set(r)
    assert set(CFG["forbidden_fields"]) == set(FORBIDDEN_FIELDS)  # config and code agree
    assert {"school_quality_score", "best_school", "good_school"} <= set(FORBIDDEN_FIELDS)
    if ARTIFACT.exists():
        assert not set(FORBIDDEN_FIELDS) & set(pd.read_parquet(ARTIFACT).columns)


def test_hospital_presence_is_not_unsupported_capability():
    for name, ministry in (
        ("โรงพยาบาลนครพิงค์ จังหวัดเชียงใหม่", "กระทรวงสาธารณสุข"),
        ("โรงพยาบาลมหาวิทยาลัย", "กระทรวงอุดมศึกษา วิทยาศาสตร์ วิจัยและนวัตกรรม (U)"),
    ):
        r = classify_health(name, "1", ministry, "x", CFG)
        assert r["capabilities_source_supported"] == []  # never inferred from the word 'hospital'
        assert r["facility_class"] not in {
            "EMERGENCY_CAPABLE_FACILITY",
            "REGIONAL_OR_TERTIARY_HOSPITAL",
            "GENERAL_HOSPITAL",
            "COMMUNITY_HOSPITAL",
        }
    assert (
        classify_health("โรงพยาบาลส่งเสริมสุขภาพตำบลบ้านโป่ง", "2", "กระทรวงสาธารณสุข", "x", CFG)[
            "facility_class"
        ]
        == "PRIMARY_HEALTH_UNIT"
    )
    assert (
        classify_health("โรงพยาบาลสวนปรุง", "3", "กระทรวงสาธารณสุข", "x", CFG)["facility_class"]
        == "SPECIALISED_HOSPITAL"
    )


def test_higher_level_requires_an_authoritative_reference_not_a_name():
    assert load_reference_levels() == {}  # none verified in M2A
    r = classify_health("โรงพยาบาลเชียงรายประชานุเคราะห์", "9", "กระทรวงสาธารณสุข", "x", CFG)
    assert r["facility_class"] == "HOSPITAL_UNSPECIFIED_LEVEL"
    ref = {
        "9": {
            "facility_official_id": "9",
            "level": "REGIONAL_OR_TERTIARY_HOSPITAL",
            "source": "doc",
        }
    }
    r2 = classify_health("โรงพยาบาลเชียงรายประชานุเคราะห์", "9", "กระทรวงสาธารณสุข", "x", CFG, ref)
    assert r2["facility_class"] == "REGIONAL_OR_TERTIARY_HOSPITAL" and r2["derived"] is False


# -- coordinate QA and dedup ------------------------------------------------------------------------------
def test_coordinate_qa_flags_without_modifying_coordinates():
    lon = pd.Series(
        [99.123456, 0.0, np.nan, 180.123456, 18.812345, 99.223456, 99.323456, 99.323456, 99.323456]
    )
    lat = pd.Series(
        [18.812345, 0.0, np.nan, 18.812345, 99.123456, 18.812345, 18.912345, 18.912345, 18.912345]
    )
    names = pd.Series(list("abcdefghi"))
    before = (lon.copy(), lat.copy())
    inside_aoi = pd.Series([True] * 9)
    stated_ok = pd.Series([True, False, True, False, True, True, True, True, True])
    f = coordinate_flags(lon, lat, names, CFG, inside_aoi, stated_ok)
    assert f.loc[1, "ZERO_COORDINATE"] and f.loc[1, "coordinate_qa_status"] == "FAILED"
    assert f.loc[2, "MISSING_COORDINATE"]
    assert f.loc[3, "OUTSIDE_THAILAND"] and f.loc[3, "coordinate_qa_status"] == "FAILED"
    assert f.loc[4, "SWAPPED_LAT_LON"]  # lat/lon swapped
    assert f.loc[0, "coordinate_qa_status"] == "PASS"
    assert f.loc[
        6:8, "DUPLICATE_COORDINATE_MULTI_INSTITUTION"
    ].all()  # 3 institutions on one exact point
    assert f.loc[6, "coordinate_qa_status"] == "FLAGGED"
    pd.testing.assert_series_equal(lon, before[0])
    pd.testing.assert_series_equal(lat, before[1])  # never corrected


def test_outside_stated_province_is_failed():
    f = coordinate_flags(
        pd.Series([99.123456]),
        pd.Series([18.812345]),
        pd.Series(["a"]),
        CFG,
        pd.Series([True]),
        pd.Series([False]),
    )
    assert f.loc[0, "OUTSIDE_STATED_PROVINCE"] and f.loc[0, "coordinate_qa_status"] == "FAILED"


def test_deduplication_is_deterministic_and_never_fuzzy():
    rows = [
        {"source_id": "a", "name": "โรงเรียน บ้านสัน", "x": 0.0, "y": 0.0},
        {
            "source_id": "b",
            "name": "โรงเรียนบ้านสัน​",
            "x": 20.0,
            "y": 0.0,
        },  # identical after normalisation, 20 m apart
        {
            "source_id": "c",
            "name": "โรงเรียนบ้านสัน",
            "x": 5000.0,
            "y": 0.0,
        },  # same name far away: different institution
        {
            "source_id": "d",
            "name": "โรงเรียนบ้านสนั",
            "x": 0.0,
            "y": 5.0,
        },  # near-identical typo: NOT merged (no fuzzy matching)
    ]
    out1 = deduplicate(pd.DataFrame(rows), 100.0)
    out2 = deduplicate(pd.DataFrame(rows[::-1]), 100.0)
    assert len(out1) == 3
    assert list(out1["facility_id"]) == list(out2["facility_id"])  # order-independent ids
    merged = out1[out1["n_merged"] == 2].iloc[0]
    assert set(merged["merged_source_ids"].split("|")) == {"a", "b"}  # contributing ids retained
    assert (
        merged["merge_evidence"].startswith("IDENTICAL_NAME_WITHIN_")
        and merged["dedup_status"] == "MERGED"
    )


# -- routing ---------------------------------------------------------------------------------------------
def times(net, sources, multiplier=1.0):
    r = reverse(net)
    return multi_source_dijkstra(
        r, r.edge_time_s(CFG.speeds, multiplier), np.array(sources), np.arange(len(sources))
    )


def test_routing_failures_stay_unresolved_never_filled_in():
    net = two_islands()
    far = int(np.argmin(np.abs(net.xy[:, 0] - 2000)))
    isolated = int(np.argmax(net.xy[:, 0]))
    t, d, lab = times(net, [int(np.argmin(net.xy[:, 0]))])
    assert np.isfinite(t[far]) and np.isinf(t[isolated])  # disconnected fragment -> unreachable
    assert lab[isolated] == -1 and np.isinf(d[isolated])  # no label, no distance, no substitute


def test_travel_time_uses_explicit_class_speeds_and_is_named_baseline():
    assert CFG["travel_time"]["name"] == "BASELINE_DRIVE_TIME"
    net = two_islands()
    t, _, _ = times(net, [int(np.argmin(net.xy[:, 0]))])
    far = int(np.argmin(np.abs(net.xy[:, 0] - 2000)))
    assert t[far] == pytest.approx(
        2000 / (CFG.speeds["secondary"] / 3.6)
    )  # length / explicit speed
    ts, _, _ = times(net, [int(np.argmin(net.xy[:, 0]))], CFG["travel_time"]["sensitivity"]["SLOW"])
    assert ts[far] == pytest.approx(
        t[far] / CFG["travel_time"]["sensitivity"]["SLOW"]
    )  # sensitivity is exposed
    with pytest.raises(ValueError):
        net.edge_time_s({"primary": 60.0})  # a missing class assumption is an error, not a default


def test_one_way_edges_are_respected():
    net = build_network([way([(0, 0), (1000, 0)], "primary", "yes")])
    a, b = int(np.argmin(net.xy[:, 0])), int(np.argmax(net.xy[:, 0]))
    to_b = times(net, [b])[0]  # travel TO b along the one-way direction a->b
    to_a = times(net, [a])[0]
    assert np.isfinite(to_b[a]) and np.isinf(to_a[b])


def test_euclidean_distance_is_labelled_diagnostic_and_never_fills_routing():
    if not ARTIFACT.exists():
        pytest.skip("artifact not built")
    df = pd.read_parquet(ARTIFACT)
    cats = [c[len("route_available_") :] for c in df.columns if c.startswith("route_available_")]
    assert cats
    for c in cats:
        assert f"euclidean_distance_to_nearest_{c}_km_diagnostic" in df.columns
        failed = ~df[f"route_available_{c}"]
        assert (
            df.loc[failed, f"drive_time_to_nearest_{c}_min"].isna().all()
        )  # no time where routing failed
        assert df.loc[failed, f"network_distance_to_nearest_{c}_km"].isna().all()
        assert (df.loc[failed, f"{c}_unresolved_reason"] != "").all()  # the reason is recorded
        assert (df.loc[failed, f"nearest_{c}_id"] == "").all()


# -- infrastructure semantics ----------------------------------------------------------------------------
def test_outside_pwa_is_not_no_water():
    for state in (None, False):
        w = water_context(state)
        assert w["water_service_context"] == "NON_PWA_OR_UNKNOWN_SERVICE"
        assert "NO_WATER" not in str(w) and w["water_service_verification_required"] is True
    assert water_context(True)["water_service_context"] == "PWA_SERVICE_AREA"
    assert (
        water_context(True)["water_service_verification_required"] is True
    )  # even inside, the parcel connection is verified


def test_pea_planning_is_not_guaranteed_electricity():
    for flag in (False, True):
        e = electricity_context(flag)
        assert e["electricity_service_potential"] in {"REGIONAL_SERVICE_POTENTIAL", "NOT_ASSESSED"}
        assert (
            "PARCEL_ELECTRICITY_AVAILABLE" not in str(e)
            and e["electricity_parcel_verification_required"] is True
        )


def test_telecom_is_deferred_without_spatial_evidence():
    t = telecom_context(False)
    assert t["telecom_evidence"].startswith("DEFERRED") and t["telecom_resolution"] == "NONE"


def test_stale_data_is_flagged():
    old = freshness("2021-12-31", "2026-10-16", "Annual", CFG["freshness"]["stale_after_years"])
    new = freshness("2026-10-15", "2026-10-16", "Continuous", CFG["freshness"]["stale_after_years"])
    assert old["freshness_status"] == "STALE" and new["freshness_status"] == "CURRENT"
    assert old["source_date"] and old["verification_date"] and old["expected_update_frequency"]


# -- hazard handoff -------------------------------------------------------------------------------------
def test_family_evidence_cannot_override_hazard_actions():
    m1e = Path("outputs/m1e/natural-hazard-actions.parquet")
    if not (ARTIFACT.exists() and m1e.exists()):
        pytest.skip("artifacts not built")
    fam, haz = pd.read_parquet(ARTIFACT), pd.read_parquet(m1e)
    action_cols = [
        c
        for c in haz.columns
        if c.endswith("_action") or c.startswith("natural_hazard") or c == "hazard_action_set"
    ]
    assert action_cols
    assert not set(action_cols) & set(
        fam.columns
    )  # M2A carries no hazard action and cannot rewrite one
    merged = haz.merge(fam, on="cell_id", how="left", suffixes=("", "_fam"))
    for c in action_cols:
        assert merged[c].equals(
            haz[c]
        )  # joining family evidence leaves every hazard action untouched
    assert len(fam) == len(haz) and fam["cell_id"].is_unique


def test_artifact_has_required_primitives_and_no_total_score():
    if not ARTIFACT.exists():
        pytest.skip("artifact not built")
    df = pd.read_parquet(ARTIFACT)
    for c in ("primary_school", "secondary_school", "hospital", "higher_level_hospital"):
        for suffix in (
            "drive_time_to_nearest_{}_min",
            "network_distance_to_nearest_{}_km",
            "route_available_{}",
            "nearest_{}_id",
        ):
            assert suffix.format(c) in df.columns
    assert not [c for c in df.columns if "score" in c.lower()]
    assert df["routing_basis"].eq("BASELINE_DRIVE_TIME").all()
    assert (
        df["higher_level_hospital_unresolved_reason"][~df["route_available_higher_level_hospital"]]
        == "CATEGORY_DEFERRED_NO_VERIFIED_CLASSIFICATION"
    ).all()
