"""M2D human visual signoff record: PASSED for M2D only; no other gate and no scoring changes."""

from pathlib import Path

import yaml

from hearthmap.family.evaluability import load_plan

ROOT = Path(__file__).resolve().parents[1]
GATES = yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"]


def test_m2d_gate_is_passed_with_the_reported_review():
    g = GATES["m2d_human_visual_signoff"]
    assert g["status"] == "PASSED" and g["review_date"] == "2026-10-16"
    assert "no blocking systemic spatial anomaly" in g["result"]
    assert len(g["observations_reported"]) == 9
    assert g["family_scoring"] == "FAMILY_SCORING_ALLOWED remains false"


def test_known_limitations_are_recorded_and_not_marked_resolved():
    g = GATES["m2d_human_visual_signoff"]
    lims = " | ".join(g["known_non_blocking_limitations_not_resolved"])
    for needle in (
        "boundary limited",
        "stale/partial",
        "CORE vs BROADER",
        "exact facility geometry",
        "OSM completeness",
        "dense-urban-core",
        "land-market",
        "fiber/electricity/legal-access",
    ):
        assert needle in lims
    assert len(g["known_non_blocking_limitations_not_resolved"]) == 8


def test_visualization_backlog_item_is_recorded_and_open():
    item = GATES["m2d_human_visual_signoff"]["visualization_backlog"][0]
    assert item["id"] == "M2A-EDU-LEGEND-ACCOUNTING" and item["status"] == "OPEN_NON_BLOCKING"
    assert "4,413" in item["item"] and "legend" in item["item"]


def test_the_corrected_m2a_human_gate_is_not_passed_by_historical_images():
    assert GATES["m2a_human_visual_signoff"]["status"] == "PENDING"
    assert (
        "must NOT be used to mark the current corrected M2A human gate as PASSED"
        in GATES["m2d_human_visual_signoff"]["note"]
    )
    for k in (
        "m1c_human_visual_signoff",
        "m1c1_human_visual_signoff",
        "m1c2_human_visual_signoff",
        "m1c3_human_visual_signoff",
        "m1d_human_visual_signoff",
        "m1e_human_visual_signoff",
    ):
        assert GATES[k]["status"] == "PENDING", k  # nothing else is inferred from the M2D review
    assert (
        GATES["m1a1_human_visual_signoff"]["status"] == "PASSED"
        and GATES["m1b_human_visual_signoff"]["status"] == "PASSED"
    )


def test_scoring_stays_off():
    assert load_plan()["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
