"""M1C.3 flood evidence fusion contracts. All inputs are SYNTHETIC."""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from hearthmap.hazard import apply_policy, load_policy_config
from hearthmap.hazard.flood_fusion import (
    DISAGREEMENT_STATES,
    OBSERVED_YEAR_COUNT_DEFINITION,
    YEARS,
    FloodLadder,
    FusionConfig,
    YearState,
    build_ledger,
    evaluate_candidate,
    ledger_long,
    ledger_summary,
    load_fusion_config,
    slope_stratum,
    tabulate,
    to_policy_override,
)
from hearthmap.hazard.reconcile import COMMON_YEARS, CURRENT_YEARS, LEGACY_YEARS
from hearthmap.qa import load_human_qa
from tests.conftest import CONFIG_DIR
from tests.test_policy import cell as policy_cell

FCFG = load_fusion_config(CONFIG_DIR / "flood-fusion.yaml")
PCFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
PM = FCFG.presence_min_fraction
CANDS = ("FLOOD_CURRENT_PRIMARY", "FLOOD_ANY_SOURCE", "FLOOD_UNION_CONSERVATIVE")
PROFILES = ("CONSERVATIVE", "BALANCED", "PERMISSIVE")
RANK = {
    "NO_MAJOR_CONCERN_DETECTED": 0,
    "REQUIRES_VERIFICATION": 1,
    "STRONG_REGIONAL_CONCERN": 2,
    "REGIONAL_DEPRIORITIZE": 3,
}


def make_table(cells: list[dict]) -> pd.DataFrame:
    """cells: {"legacy": {year: frac}, "current": {year: frac}, "inter": {year: frac}}."""
    rows = []
    for i, c in enumerate(cells):
        r = {"cell_id": f"C{i}", "majority_pcode": "TH50", "clipped_area_km2": 0.25}
        for y in LEGACY_YEARS:
            r[f"legacy_flood_fraction_{y}"] = c.get("legacy", {}).get(y, 0.0)
        for y in CURRENT_YEARS:
            r[f"current_flood_fraction_{y}"] = c.get("current", {}).get(y, 0.0)
        for y in COMMON_YEARS:
            lg, cu = r[f"legacy_flood_fraction_{y}"], r[f"current_flood_fraction_{y}"]
            ix = c.get("inter", {}).get(y, min(lg, cu))
            r[f"intersection_fraction_{y}"] = ix
            r[f"legacy_only_fraction_{y}"] = lg - ix
            r[f"current_only_fraction_{y}"] = cu - ix
        rows.append(r)
    return pd.DataFrame(rows)


def ledger_of(*cells):
    return build_ledger(make_table(list(cells)), PM)


def levels(ledger):
    return {c: evaluate_candidate(ledger, FCFG, c).level for c in CANDS}


# ======================================================== ledger provenance


def test_ledger_states_follow_source_availability_by_era():
    led = ledger_of(
        {"legacy": {2007: 0.3, 2014: 0.4, 2016: 0.4}, "current": {2014: 0.4, 2016: 0.4, 2020: 0.5}}
    )
    s = dict(zip(YEARS, led.state[0], strict=True))
    assert s[2007] == YearState.OBSERVED_SINGLE_SOURCE_LEGACY
    assert s[2006] == YearState.NOT_OBSERVED_SINGLE_SOURCE
    assert s[2020] == YearState.OBSERVED_SINGLE_SOURCE_CURRENT
    assert s[2014] == YearState.OBSERVED_CONSENSUS
    assert s[2012] == YearState.NOT_OBSERVED_CONSENSUS
    avail = led.sources_available()
    assert avail[2008] == "legacy" and avail[2013] == "legacy+current" and avail[2019] == "current"
    # the source with no value in a year is NaN, never a silent zero
    assert np.isnan(led.current[0, YEARS.index(2008)]) and np.isnan(
        led.legacy[0, YEARS.index(2019)]
    )
    assert np.isnan(led.intersection[0, YEARS.index(2008)])
    long = ledger_long(led, pd.Series(["C0"]))
    row = long[long["year"] == 2014].iloc[0]
    assert (
        row["sources_available"] == "legacy+current" and row["sources_positive"] == "legacy+current"
    )
    for col in (
        "observed_flood_fraction",
        "legacy_fraction",
        "current_fraction",
        "agreement_state",
        "sources_available",
        "sources_positive",
    ):
        assert col in long.columns
    assert len(long) == len(YEARS)


def test_source_native_fractions_are_retained_not_collapsed_to_booleans():
    led = ledger_of({"legacy": {2014: 0.37}, "current": {2014: 0.12}, "inter": {2014: 0.12}})
    j = YEARS.index(2014)
    assert led.legacy[0, j] == pytest.approx(0.37) and led.current[0, j] == pytest.approx(0.12)
    assert led.observed[0, j] == pytest.approx(0.37)  # spatial union, not a flag
    assert led.legacy_only[0, j] == pytest.approx(0.25)


# ======================================================== disagreement stays visible


def test_overlap_disagreement_survives_fusion():
    # the 2014 pattern: legacy maps flooding that the current product does not
    led = ledger_of({"legacy": {2014: 0.4, 2016: 0.3}, "current": {}})
    summ = ledger_summary(led, FCFG.reference_year).iloc[0]
    assert summ["has_overlap_product_disagreement"]
    assert summ["overlap_disagreement_years"] == "2014|2016"
    assert summ["overlap_disagreement_observed_years"] == 2
    assert summ["overlap_consensus_observed_years"] == 0
    j = YEARS.index(2014)
    assert led.state[0, j] == YearState.OBSERVED_LEGACY_ONLY_OVERLAP
    res = evaluate_candidate(led, FCFG, "FLOOD_ANY_SOURCE")
    assert res.source_disagreement[0]
    assert "FLOOD_PRODUCT_DISAGREEMENT_2011_2016" in res.reason_codes[0]
    assert res.level[0] >= 2  # at least REQUIRES_FLOOD_VERIFICATION


def test_union_geometry_does_not_erase_disagreement_metadata():
    led = ledger_of(
        {"legacy": {2014: 0.4}, "current": {2014: 0.1}, "inter": {2014: 0.1}},
        {"legacy": {2014: 0.4}, "current": {2014: 0.4}},
    )
    j = YEARS.index(2014)
    assert led.observed[0, j] == led.observed[1, j] == pytest.approx(0.4)  # same union...
    assert led.state[0, j] in DISAGREEMENT_STATES  # ...but the disagreement is kept
    assert led.state[1, j] == YearState.OBSERVED_CONSENSUS
    long = ledger_long(led, pd.Series(["A", "B"]))
    a = long[(long.cell_id == "A") & (long.year == 2014)].iloc[0]
    assert (
        a["legacy_only_fraction"] == pytest.approx(0.3)
        and a["agreement_state"] in DISAGREEMENT_STATES
    )
    summ = ledger_summary(led, FCFG.reference_year)
    assert list(summ["has_overlap_product_disagreement"]) == [True, False]


def test_mixed_disagreement_state():
    led = ledger_of({"legacy": {2013: 0.5}, "current": {2013: 0.5}, "inter": {2013: 0.3}})
    assert led.state[0, YEARS.index(2013)] == YearState.OBSERVED_OVERLAP_MIXED_DISAGREEMENT


# ======================================================== positive-only


def _random_cells(n, seed):
    rng = np.random.default_rng(seed)
    cells = []
    for _ in range(n):
        c = {"legacy": {}, "current": {}}
        for y in YEARS:
            if y in LEGACY_YEARS and rng.random() < 0.25:
                c["legacy"][y] = float(rng.choice([0.005, 0.03, 0.08, 0.2, 0.6]))
            if y in CURRENT_YEARS and rng.random() < 0.2:
                c["current"][y] = float(rng.choice([0.005, 0.03, 0.08, 0.2, 0.6]))
        cells.append(c)
    return cells


def test_legacy_positive_evidence_never_lowers_concern():
    base = _random_cells(300, 1)
    more = copy.deepcopy(base)
    rng = np.random.default_rng(2)
    for c in more:  # add extra legacy observations everywhere
        for y in rng.choice(list(LEGACY_YEARS), size=3, replace=False):
            c["legacy"][int(y)] = max(c["legacy"].get(int(y), 0.0), 0.3)
    lb, lm = levels(ledger_of(*base)), levels(ledger_of(*more))
    for cand in CANDS:
        assert (lm[cand] >= lb[cand]).all()


def test_current_positive_evidence_never_lowers_concern():
    base = _random_cells(300, 3)
    more = copy.deepcopy(base)
    for c in more:
        c["current"][2021] = max(c["current"].get(2021, 0.0), 0.4)
    lb, lm = levels(ledger_of(*base)), levels(ledger_of(*more))
    for cand in CANDS:
        assert (lm[cand] >= lb[cand]).all()


def test_policy_status_never_lowered_by_added_flood_evidence():
    base = _random_cells(120, 4)
    more = copy.deepcopy(base)
    for c in more:
        c["legacy"][2008] = max(c["legacy"].get(2008, 0.0), 0.5)
    ev = pd.DataFrame([policy_cell()] * len(base))
    for cand in CANDS:
        for prof in PROFILES:
            a = apply_policy(
                ev, PCFG, prof, to_policy_override(evaluate_candidate(ledger_of(*base), FCFG, cand))
            )["regional_search_status"]
            b = apply_policy(
                ev, PCFG, prof, to_policy_override(evaluate_candidate(ledger_of(*more), FCFG, cand))
            )["regional_search_status"]
            assert (b.map(RANK) >= a.map(RANK)).all()


def test_absence_in_either_product_cannot_create_safety():
    led = ledger_of({}, {"legacy": {2008: 0.5}}, {"current": {2020: 0.5, 2021: 0.5}})
    for cand in CANDS:
        res = evaluate_candidate(led, FCFG, cand)
        assert res.state[0] == FloodLadder.NO_MAJOR_OBSERVED_SIGNAL  # a screening term only
        assert res.level[1] >= res.level[0] and res.level[2] >= res.level[0]
    states = {s.value for s in FloodLadder} | {s.value for s in YearState}
    for s in states:
        for w in ("SAFE", "NO_FLOOD_RISK", "SAFE_FROM_FLOOD", "LOW_RISK"):
            assert w not in s.split("_") and w not in s
    for rule_id in FCFG.reason_codes:
        assert "SAFE" not in rule_id
    ov = to_policy_override(evaluate_candidate(led, FCFG, "FLOOD_ANY_SOURCE"))
    assert ov.info_codes[0] == ["NO_OBSERVED_FLOOD_SIGNAL_IN_FUSED_RECORD"]
    pol = apply_policy(pd.DataFrame([policy_cell()] * 3), PCFG, "BALANCED", ov)
    assert pol["regional_search_status"].iloc[0] == "NO_MAJOR_CONCERN_DETECTED"


def test_not_observed_state_names_do_not_claim_no_flooding():
    names = [s.value for s in YearState if s.name.startswith("NOT_OBSERVED")]
    assert names and all(n.startswith("NOT_OBSERVED") for n in names)
    assert not any("NO_FLOOD" in n or "SAFE" in n for n in names)


def test_historical_signal_is_informational_not_a_concern_level():
    led = ledger_of({"legacy": {2006: 0.02}})
    res = evaluate_candidate(led, FCFG, "FLOOD_CURRENT_PRIMARY")
    assert res.state[0] == FloodLadder.HISTORICAL_SIGNAL
    ov = to_policy_override(res)
    assert ov.info_codes[0] == ["HISTORICAL_FLOOD_SIGNAL"]
    pol = apply_policy(pd.DataFrame([policy_cell()]), PCFG, "BALANCED", ov)
    assert pol["regional_search_status"].iloc[0] == "NO_MAJOR_CONCERN_DETECTED"


# ======================================================== annual count semantics


def test_observed_year_count_is_a_raw_observational_count():
    led = ledger_of(
        {"legacy": {2005: 0.2, 2009: 0.05, 2014: 0.3}, "current": {2014: 0.3, 2019: 0.1}}
    )
    s = ledger_summary(led, FCFG.reference_year).iloc[0]
    assert s["observed_year_count_total"] == 4
    assert s["legacy_era_observed_years"] == 2
    assert s["overlap_consensus_observed_years"] == 1
    assert s["current_era_observed_years"] == 1
    assert s["observed_year_count_semantics"] == "RAW_OBSERVATIONAL_COUNT_NOT_PROBABILITY"
    assert "NOT a probability" in OBSERVED_YEAR_COUNT_DEFINITION
    for col in ledger_summary(led, FCFG.reference_year).columns:
        assert "probab" not in col.lower() and "of_19" not in col.lower()


def test_temporal_bands_and_recency_are_exposed_without_decay():
    led = ledger_of(
        {"legacy": {2006: 0.3}},
        {"current": {2021: 0.3}},
        {"legacy": {2012: 0.3}, "current": {2012: 0.3}},
        {},
    )
    s = ledger_summary(led, FCFG.reference_year)
    assert list(s["most_recent_observed_band"]) == ["OLDER", "RECENT", "MID", "NONE"]
    assert list(s["most_recent_observed_year"].iloc[:3]) == [2006, 2021, 2012]
    assert list(s["years_since_most_recent_observation"].iloc[:3]) == [17, 2, 11]
    assert np.isnan(s["years_since_most_recent_observation"].iloc[3])
    assert s["recent_era_max_fraction"].iloc[1] == pytest.approx(0.3)
    assert s["historical_era_max_fraction"].iloc[0] == pytest.approx(0.3)
    with pytest.raises(ValidationError):  # no weights/decay in the schema
        raw = yaml.safe_load((CONFIG_DIR / "flood-fusion.yaml").read_text("utf-8"))
        raw["decay_weights"] = {"OLDER": 0.5}
        FusionConfig.model_validate(raw)


# ======================================================== candidates


def test_candidates_are_nested_so_concern_is_monotone_by_design():
    assert [FCFG.candidates[c].extends for c in CANDS] == [
        None,
        "FLOOD_CURRENT_PRIMARY",
        "FLOOD_ANY_SOURCE",
    ]
    lv = levels(ledger_of(*_random_cells(500, 5)))
    assert (lv["FLOOD_CURRENT_PRIMARY"] <= lv["FLOOD_ANY_SOURCE"]).all()
    assert (lv["FLOOD_ANY_SOURCE"] <= lv["FLOOD_UNION_CONSERVATIVE"]).all()
    assert (lv["FLOOD_CURRENT_PRIMARY"] < lv["FLOOD_UNION_CONSERVATIVE"]).any()


def test_candidate_semantics_on_known_cells():
    cases = {
        # legacy-only older flooding: current-primary -> verification flag, not strong
        "older_only": ({"legacy": {2006: 0.3}}, [2, 2, 2]),
        # two recent years >= 10%: strong for any-source and union, not for current-primary
        "recent_two": ({"current": {2019: 0.2, 2021: 0.2}}, [2, 3, 3]),
        # three current-product years >= 10%: strong everywhere
        "current_three": ({"current": {2018: 0.2, 2020: 0.2, 2022: 0.2}}, [3, 3, 3]),
        # one huge year in the legacy record: only the union candidate is strong
        "legacy_single_huge": ({"legacy": {2005: 0.7}}, [2, 2, 3]),
        # small fraction: historical signal only (union conservative also verifies at 5%)
        "tiny": ({"legacy": {2005: 0.02}}, [1, 1, 1]),
    }
    for name, (cell, expect) in cases.items():
        got = [int(evaluate_candidate(ledger_of(cell), FCFG, c).level[0]) for c in CANDS]
        assert got == expect, name


def test_unevaluated_cells_are_unresolved_not_clear():
    res = evaluate_candidate(
        ledger_of({}, {}), FCFG, "FLOOD_ANY_SOURCE", evaluated=np.array([True, False])
    )
    assert list(res.state) == ["NO_MAJOR_OBSERVED_SIGNAL", "UNRESOLVED"]


def test_rules_are_positive_only_and_candidates_not_preselected():
    for cand in FCFG.candidates.values():
        assert all(r.level in ("HISTORICAL", "VERIFY", "STRONG") for r in cand.rules)
    assert FCFG.default_candidate is None and FCFG.status == "PROVISIONAL"
    raw = yaml.safe_load((CONFIG_DIR / "flood-fusion.yaml").read_text("utf-8"))
    raw["default_candidate"] = "FLOOD_ANY_SOURCE"
    with pytest.raises(ValidationError):
        FusionConfig.model_validate(raw)
    raw = yaml.safe_load((CONFIG_DIR / "flood-fusion.yaml").read_text("utf-8"))
    raw["candidates"]["FLOOD_ANY_SOURCE"]["rules"][0]["id"] = "SAFE_FROM_FLOOD"
    with pytest.raises(ValidationError):
        FusionConfig.model_validate(raw)


# ======================================================== policy matrix accounting


def test_policy_matrix_accounting_is_exhaustive():
    cells = _random_cells(400, 6)
    led = ledger_of(*cells)
    area = np.full(400, 0.25)
    ev = pd.DataFrame([policy_cell()] * 400)
    masks = {"AOI": np.ones(400, bool), "HALF": np.arange(400) < 200}
    statuses = [
        "NO_MAJOR_CONCERN_DETECTED",
        "REQUIRES_VERIFICATION",
        "STRONG_REGIONAL_CONCERN",
        "REGIONAL_DEPRIORITIZE",
        "UNRESOLVED",
    ]
    for cand in CANDS:
        ov = to_policy_override(evaluate_candidate(led, FCFG, cand))
        for prof in PROFILES:
            st = apply_policy(ev, PCFG, prof, ov)["regional_search_status"].to_numpy()
            t = tabulate(st, area, masks, statuses)
            for scope, m in masks.items():
                sub = t[t["scope"] == scope]
                assert sub["cells"].sum() == m.sum()
                assert sub["area_km2"].sum() == pytest.approx(area[m].sum())
                assert sub["share_of_area"].sum() == pytest.approx(1.0, abs=1e-3)


# ======================================================== lowland stratification


def test_lowland_stratification_cannot_influence_hazard_state():
    cells = _random_cells(60, 7)
    led = ledger_of(*cells)
    base = pd.DataFrame([policy_cell()] * 60)
    flat = base.assign(lowland_stratum="LOW_SLOPE_LE_5", slope_stratum="LOW_SLOPE_LE_5")
    steep = base.assign(lowland_stratum="STEEP_GT_15", slope_stratum="STEEP_GT_15")
    for cand in CANDS:
        ov = to_policy_override(evaluate_candidate(led, FCFG, cand))
        for prof in PROFILES:
            a = apply_policy(flat, PCFG, prof, ov)
            b = apply_policy(steep, PCFG, prof, ov)
            assert a.equals(b)
    assert {"lowland_stratum", "slope_stratum"} <= set(PCFG.prohibited_evidence_columns)
    assert FCFG.stratification.purpose == "reporting_only_not_suitability"


def test_slope_stratum_bands_and_unknown_support():
    out = slope_stratum(np.array([2.0, 5.0, 9.0, 30.0, 3.0]), np.array([50, 50, 50, 50, 0.2]))
    assert list(out) == [
        "LOW_SLOPE_LE_5",
        "LOW_SLOPE_LE_5",
        "GENTLE_5_15",
        "STEEP_GT_15",
        "UNKNOWN",
    ]


# ======================================================== human QA / determinism


def test_human_qa_gates_stay_truthful():
    q = load_human_qa(CONFIG_DIR / "human-qa.yaml")
    assert q.status("m1a1_human_visual_signoff") == "PASSED"
    assert q.status("m1b_human_visual_signoff") == "PASSED"
    for g in (
        "m1c_human_visual_signoff",
        "m1c1_human_visual_signoff",
        "m1c2_human_visual_signoff",
        "m1c3_human_visual_signoff",
    ):
        assert q.status(g) == "PENDING"
        assert q.gates[g].review_date is None and q.gates[g].reviewer_role is None
    assert PCFG.default_profile is None


def test_fusion_is_deterministic():
    cells = _random_cells(200, 8)
    a = evaluate_candidate(ledger_of(*cells), FCFG, "FLOOD_ANY_SOURCE")
    b = evaluate_candidate(ledger_of(*copy.deepcopy(cells)), FCFG, "FLOOD_ANY_SOURCE")
    assert (a.level == b.level).all() and a.reason_codes == b.reason_codes
    assert ledger_summary(ledger_of(*cells), 2023).equals(ledger_summary(ledger_of(*cells), 2023))
