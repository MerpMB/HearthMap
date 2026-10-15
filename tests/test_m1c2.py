"""M1C.2 flood reconciliation + lowland semantics contracts. SYNTHETIC inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from hearthmap.hazard import apply_policy, explain, load_policy_config
from hearthmap.hazard.reconcile import (
    COMMON_YEARS,
    CommonPeriodClass,
    annual_accounting,
    cell_year_fractions,
    classify_common_period,
    common_year_pairs,
    distance_band,
    fraction_column,
    legacy_only_breakdown,
    temporal_flags,
)
from tests.conftest import CONFIG_DIR
from tests.test_policy import cell as policy_cell

PCFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
C = CommonPeriodClass


# ======================================================== annual fields never mixed


def test_fraction_columns_are_product_and_year_specific():
    assert fraction_column("legacy", 2008) == "legacy_flood_fraction_2008"
    assert fraction_column("current", 2020) == "current_flood_fraction_2020"
    with pytest.raises(ValueError):
        fraction_column("legacy", 2020)  # legacy has no 2020
    with pytest.raises(ValueError):
        fraction_column("current", 2008)  # current has no 2008
    with pytest.raises(ValueError):
        fraction_column("merged", 2012)


def test_common_year_pairs_only_pair_the_same_year():
    cols = [fraction_column("legacy", y) for y in range(2005, 2017)] + [
        fraction_column("current", y) for y in range(2011, 2024)
    ]
    pairs = common_year_pairs(reversed(cols))
    assert [y for y, _, _ in pairs] == list(COMMON_YEARS) == list(range(2011, 2017))
    for y, lc, cc in pairs:
        assert lc.endswith(str(y)) and cc.endswith(str(y))
        assert lc.startswith("legacy_") and cc.startswith("current_")
    with pytest.raises(ValueError):
        common_year_pairs(["legacy_flood_fraction_2019", "current_flood_fraction_2019"])


# ======================================================== accounting


def test_old_only_new_only_intersection_accounting():
    a = annual_accounting(10.0, 4.0, 3.0)
    assert a["legacy_only_km2"] == 7.0 and a["current_only_km2"] == 1.0
    assert a["union_km2"] == 11.0
    assert a["intersection_over_union"] == pytest.approx(3 / 11)
    assert a["legacy_captured_by_current"] == pytest.approx(0.3)
    assert a["current_captured_by_legacy"] == pytest.approx(0.75)
    assert a["legacy_only_km2"] + a["intersection_km2"] == a["legacy_km2"]
    with pytest.raises(ValueError):
        annual_accounting(2.0, 4.0, 3.0)  # intersection larger than legacy
    empty = annual_accounting(0.0, 5.0, 0.0)  # e.g. legacy 2015 in the AOI
    assert np.isnan(empty["legacy_captured_by_current"]) and empty["current_only_km2"] == 5.0


def test_cell_year_fractions_partition_each_product():
    r = cell_year_fractions(
        np.array([0.6, 0.0, 0.2]), np.array([0.4, 0.3, 0.2]), np.array([0.3, 0.0, 0.2])
    )
    assert np.allclose(r["intersection"] + r["legacy_only"], [0.6, 0.0, 0.2])
    assert np.allclose(r["intersection"] + r["current_only"], [0.4, 0.3, 0.2])
    with pytest.raises(ValueError):
        cell_year_fractions(np.array([0.1]), np.array([0.5]), np.array([0.2]))


# ======================================================== classes


def _years(rows):
    return pd.DataFrame(rows, columns=list(COMMON_YEARS))


def test_common_period_classes():
    z = [0.0] * 6
    leg = _years([z, [0.5, *z[1:]], [0.5, *z[1:]], z, [0.5, 0.0, 0, 0, 0, 0]])
    cur = _years([z, [0.4, *z[1:]], z, [0, 0.3, 0, 0, 0, 0], [0.5, 0.2, 0, 0, 0, 0]])
    out = classify_common_period(leg, cur, presence_min=0.01)
    assert list(out) == [
        C.AGREEMENT_NO_FLOOD,
        C.AGREEMENT_FLOOD,
        C.LEGACY_ONLY_IN_COMMON_PERIOD,
        C.CURRENT_ONLY_IN_COMMON_PERIOD,
        C.MIXED_COMMON_PERIOD_DISAGREEMENT,
    ]


def test_same_year_required_for_agreement():
    """Legacy 2011 and current 2012 in the same cell is disagreement, not agreement."""
    leg = _years([[0.5, 0, 0, 0, 0, 0]])
    cur = _years([[0, 0.5, 0, 0, 0, 0]])
    assert (
        classify_common_period(leg, cur, presence_min=0.01)[0] == C.MIXED_COMMON_PERIOD_DISAGREEMENT
    )
    with pytest.raises(ValueError):
        classify_common_period(leg, cur.set_axis(range(2012, 2018), axis=1), presence_min=0.01)


def test_temporal_evidence_stays_distinct_from_product_disagreement():
    z6 = _years([[0.0] * 6, [0.0] * 6])
    pre = pd.DataFrame({2008: [0.4, 0.0]})
    post = pd.DataFrame({2020: [0.0, 0.3]})
    flags = temporal_flags(pre, z6, z6, post, presence_min=0.01)
    assert list(flags) == ["LEGACY_PRE_2011_ONLY", "CURRENT_POST_2016_ONLY"]
    # the same cells are AGREEMENT_NO_FLOOD for the common period: no disagreement
    assert set(classify_common_period(z6, z6, presence_min=0.01)) == {C.AGREEMENT_NO_FLOOD}
    # a cell can carry a temporal flag AND a common-period disagreement class
    lcp = _years([[0.5, 0, 0, 0, 0, 0]])
    ccp = _years([[0.0] * 6])
    both = temporal_flags(
        pd.DataFrame({2008: [0.4]}), lcp, ccp, pd.DataFrame({2020: [0.3]}), presence_min=0.01
    )
    assert both[0] == "CURRENT_POST_2016_ONLY"  # legacy also seen in common period
    assert classify_common_period(lcp, ccp, presence_min=0.01)[0] == C.LEGACY_ONLY_IN_COMMON_PERIOD


def test_legacy_only_breakdown():
    out = legacy_only_breakdown([True, True, False, False], [False, True, True, False])
    assert list(out) == [
        "ONLY_2005_2010",
        "BOTH_2005_2010_AND_2011_2016",
        "ONLY_2011_2016",
        "NONE",
    ]


def test_distance_bands():
    out = distance_band(np.array([5, 20, 21, 300, 9999, np.inf]))
    assert list(out) == [
        "<= 20 m",
        "<= 20 m",
        "20-50 m",
        "250-500 m",
        "> 500 m",
        "no polygon in other product that year",
    ]


# ======================================================== legacy never reassurance


def test_legacy_absence_or_presence_never_lowers_policy_concern():
    flooded = policy_cell(
        flood_years_ge3_area_fraction=0.6, flood_area_fraction=0.6, flood_distance_m=0.0
    )
    for legacy in (0.0, 0.9):
        c = flooded | {
            "legacy_flood_2005_2016_area_fraction": legacy,
            "legacy_flood_2005_2016_years_ge3_area_fraction": legacy,
        }
        r = apply_policy(pd.DataFrame([c]), PCFG, "BALANCED").iloc[0]
        assert r["regional_search_status"] == "REGIONAL_DEPRIORITIZE"


# ======================================================== lowland semantics


def test_missing_landslide_assessment_is_separate_from_hazard_interpretation():
    lowland = policy_cell(landslide_assessed_fraction=0.0, slope_p90_deg=2.0)
    r = apply_policy(pd.DataFrame([lowland]), PCFG, "BALANCED").iloc[0]
    assert r["landslide_assessment_status"] == "NOT_ASSESSED"
    assert r["landslide_policy_level"] == "NOT_ASSESSED"  # never NONE / "low"
    assert r["hazard_interpretation"] == "NO_MAJOR_CONCERN_IN_ASSESSED_HAZARDS"
    assert r["assessed_hazards"] == "flood|terrain"
    assert r["data_completeness"] == "UNRESOLVED_CRITICAL"
    assert r["regional_search_status"] == "UNRESOLVED"  # status rule unchanged
    for col in r.index:
        assert "LOW_LANDSLIDE" not in str(r[col])
    text = explain("X", pd.Series(lowland), r, PCFG)
    assert "NOT low landslide susceptibility" in text


def test_missing_landslide_does_not_erase_flood_evidence():
    c = policy_cell(
        landslide_assessed_fraction=0.0,
        flood_years_ge3_area_fraction=0.3,
        flood_area_fraction=0.3,
        flood_distance_m=0.0,
    )
    r = apply_policy(pd.DataFrame([c]), PCFG, "BALANCED").iloc[0]
    assert r["regional_search_status"] == "STRONG_REGIONAL_CONCERN"
    assert r["hazard_interpretation"] == "STRONG_CONCERN"
    assert r["landslide_assessment_status"] == "NOT_ASSESSED"
    assert "LANDSLIDE_NOT_ASSESSED" in r["unresolved_reasons"]


def test_assessed_cells_report_assessed():
    r = apply_policy(pd.DataFrame([policy_cell()]), PCFG, "BALANCED").iloc[0]
    assert r["landslide_assessment_status"] == "ASSESSED"
    assert r["assessed_hazards"] == "flood|landslide|terrain"
    assert r["data_completeness"] == "COMPLETE"


# ======================================================== determinism


def test_reconciliation_functions_are_deterministic():
    rng = np.random.default_rng(1)
    leg = _years(rng.uniform(0, 0.2, (200, 6)))
    cur = _years(rng.uniform(0, 0.2, (200, 6)))
    a = classify_common_period(leg, cur, presence_min=0.05)
    b = classify_common_period(leg.copy(), cur.copy(), presence_min=0.05)
    assert (a == b).all()
    assert annual_accounting(5.0, 3.0, 1.0) == annual_accounting(5.0, 3.0, 1.0)
