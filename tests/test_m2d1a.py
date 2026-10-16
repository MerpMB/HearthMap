# ruff: noqa: E501
"""M2D.1a routing-coverage QA: weighting, modelled-population semantics, unchanged routing, no scoring."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from hearthmap.context.semantics import forbidden_columns
from hearthmap.context.stats import weighted_coverage
from hearthmap.family import load_config
from hearthmap.family.evaluability import load_plan

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
COV = ROOT / "outputs" / "m2d" / "tables" / "routing-coverage-weighted.csv"
REVIEW = ROOT / "outputs" / "m2d-review" / "routing-unresolved-settlement-overlap.csv"
needs_outputs = pytest.mark.skipif(
    not (ART.exists() and COV.exists() and REVIEW.exists()),
    reason="run build_context.py and routing_coverage_qa.py",
)


def test_population_weighted_and_area_weighted_coverage_are_not_conflated():
    routable = np.array([True, True, False, False])
    area = np.array([0.25, 0.25, 0.25, 0.25])
    pop = np.array([500.0, 480.0, 15.0, 5.0])  # mountain cells are empty, the valley is not
    a, p = weighted_coverage(area, routable), weighted_coverage(pop, routable)
    assert a["unresolved_share"] == pytest.approx(0.5)  # half the area...
    assert p["unresolved_share"] == pytest.approx(20 / 1000)  # ...but 2% of the modelled people
    assert a["unresolved_share"] != p["unresolved_share"]


def test_unresolved_quantity_is_kept_never_treated_as_zero():
    pop = np.array([100.0, 50.0, 25.0])
    r = weighted_coverage(pop, np.array([True, False, False]))
    assert r["unresolved"] == 75.0 and r["total"] == 175.0 and r["routable"] == 100.0
    assert r["unresolved_share"] == pytest.approx(75 / 175)
    # a cell without a route contributes its quantity to the unresolved side, not nothing
    assert weighted_coverage(pop, np.array([False, False, False]))["unresolved_share"] == 1.0
    assert np.isnan(
        weighted_coverage(np.zeros(3), np.array([True, False, True]))["unresolved_share"]
    )


def test_qa_script_recomputes_no_routing_and_writes_no_config():
    text = (ROOT / "scripts/m2d/routing_coverage_qa.py").read_text("utf-8")
    for banned in (
        "multi_source_dijkstra",
        "bounded_reach",
        "load_network",
        "reverse(",
        "snap(",
        "edge_time_s",
        'config/family-infrastructure.yaml", "w',
    ):
        assert banned not in text, banned
    assert "SNAP_M = 1000" in text
    assert (
        load_config()["travel_time"]["max_snap_distance_m"] == 1000
    )  # the snap radius is untouched
    assert "write_text" not in text.split("def main")[0]


def test_routing_configuration_fingerprint_is_unchanged():
    import hashlib

    cfg = load_config()
    fp = hashlib.sha256(json.dumps(cfg["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
    assert fp == "5c35e98882c3ac62"


def test_scoring_stays_off():
    assert load_plan()["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False


@needs_outputs
def test_weighted_table_states_modelled_population_and_separates_the_shares():
    cov = pd.read_csv(COV)
    assert set(cov["scope"]) == {"Chiang Mai", "Phayao", "Chiang Rai", "Whole AOI"}
    assert cov["population_semantics"].str.startswith("MODELLED_POPULATION_ESTIMATE").all()
    assert cov["built_up_aggregation"].str.contains("not a cell count").all()
    a = cov[cov["scope"] == "Whole AOI"].iloc[0]
    assert a["modelled_population_routable"] + a["modelled_population_unresolved"] == pytest.approx(
        a["modelled_population_total"], abs=2
    )
    assert a["built_up_m2_routable"] + a["built_up_m2_unresolved"] == pytest.approx(
        a["built_up_m2_total"], abs=2
    )
    # the practical gap is far smaller than the cell/area gap in mountainous terrain: the weightings are different quantities
    assert a["unresolved_population_share"] < a["unresolved_cell_share"] / 5
    assert a["unresolved_built_up_share"] < a["unresolved_area_share"] / 5
    # totals tie back to the artifact
    df = pd.read_parquet(ART)
    assert a["modelled_population_total"] == pytest.approx(
        df["population_worldpop2025_mass_aoi_clipped"].sum(), abs=2
    )
    assert a["built_up_m2_total"] == pytest.approx(df["built_ghsl2020_m2_aoi_clipped"].sum(), abs=2)
    assert int(a["cells_unresolved"]) == int(
        (df["service_convenience_store_unresolved_reason"] == "NO_ROAD_WITHIN_SNAP_DISTANCE").sum()
    )


@needs_outputs
def test_review_table_is_descriptive_with_no_score_rank_or_suitability_fields():
    t = pd.read_csv(REVIEW)
    assert forbidden_columns(t.columns) == []
    assert not [c for c in t.columns if "suitab" in c or "rank" in c or "score" in c]
    for col in (
        "grid_id",
        "province",
        "district",
        "modelled_population",
        "built_up_fraction",
        "distance_to_routable_network_m",
        "unresolved_reason",
    ):
        assert col in t.columns
    assert (
        t["unresolved_reason"].eq("NO_ROAD_WITHIN_SNAP_DISTANCE").all()
    )  # every row really is unresolved
    assert t["evidence_note"].str.contains("not routing failure").all()
    assert (t["modelled_population"].notna()).all()


@needs_outputs
def test_town_service_summaries_still_expose_every_denominator():
    st = pd.read_csv(ROOT / "outputs/m2d/tables/descriptive-statistics.csv")
    times = st[st["column"].str.startswith("drive_time_to_nearest_service_")]
    assert {
        "cells_resolved",
        "resolved_area_share",
        "cells_unresolved",
        "unresolved_area_share",
    } <= set(times.columns)
    assert times["statistic_population"].eq("MEDIAN_AMONG_ROUTABLE_CELLS_ONLY").all()
    ctx = pd.read_csv(ROOT / "outputs/m2d/tables/town-services-population-coverage-context.csv")
    assert ctx["note"].str.contains("not population-weighted").all()
    summary = json.loads((ROOT / "outputs/m2d/routing-coverage-qa-summary.json").read_text("utf-8"))
    assert (
        summary["routing_parameters_changed"] is False and summary["snap_distance_m_used"] == 1000
    )
    assert (
        summary["population_semantics"] == "MODELLED_POPULATION_ESTIMATE"
        and summary["town_service_summaries_expose_denominators"] is True
    )


@needs_outputs
def test_display_class_reference_is_labelled_descriptive_not_a_threshold():
    s = json.loads((ROOT / "outputs/m2d/routing-coverage-qa-summary.json").read_text("utf-8"))
    assert "not a policy threshold" in s["display_class_reference"]["note"]
    assert (
        "UNRESOLVED_SETTLEMENT_LIKE_FOR_REVIEW" in s["class_counts"]
    )  # a review label, never called routing failure
    assert not [k for k in s["class_counts"] if "FAIL" in k]
