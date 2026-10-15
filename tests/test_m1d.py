"""M1D seismic evidence contracts. All inputs are SYNTHETIC."""

from __future__ import annotations

import copy

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError
from shapely.geometry import LineString, Point, box

from hearthmap.hazard import apply_policy, load_policy_config
from hearthmap.hazard.defaults import load_regional_defaults, threshold_fingerprint
from hearthmap.hazard.flood_fusion import load_fusion_config
from hearthmap.qa import load_human_qa
from hearthmap.seismic import (
    INTERPRETATION_STATES,
    SeismicConfig,
    explain_seismic,
    fault_context,
    ground_response_columns,
    historical_context,
    interpret_seismic,
    load_seismic_config,
    parse_tmd_date,
    parse_tmd_magnitude,
    seismic_input_columns,
)
from tests.conftest import CONFIG_DIR
from tests.test_policy import cell as policy_cell

CFG = load_seismic_config(CONFIG_DIR / "seismic-evidence.yaml")
PCFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
CLASSES = CFG.sources["intensity_zones"]["classes"]
UTM = "EPSG:32647"


def sc(**o) -> dict:
    """One cell's seismic inputs; baseline = nothing notable, zones assessed."""
    base = {
        "fault_nearest_distance_km": 40.0,
        "shaking_assessed_fraction": 1.0,
        **{f"shaking_class{c}_fraction": 0.0 for c in CLASSES},
        f"hist_nearest_ge{CFG.interpretation.history.magnitude:g}_km": np.nan,
        "shaking_classV_fraction": 1.0,
    }
    return base | o


def run(*cells: dict) -> pd.DataFrame:
    return interpret_seismic(pd.DataFrame(list(cells)), CFG)


HIST = f"hist_nearest_ge{CFG.interpretation.history.magnitude:g}_km"


# ======================================================== config guards


def test_config_is_provisional_experimental_without_selected_policy():
    assert CFG.status == "PROVISIONAL" and CFG.experimental and CFG.default_policy is None
    assert CFG.interpretation.fault_alone_max_level == "VERIFY"
    assert CFG.interpretation.history_alone_max_level == "VERIFY"
    assert (
        CFG.ground_response.status == "NOT_ASSESSED" and not CFG.ground_response.available_evidence
    )


def test_forbidden_wording_and_fault_score_are_rejected():
    raw = yaml.safe_load((CONFIG_DIR / "seismic-evidence.yaml").read_text("utf-8"))
    bad = copy.deepcopy(raw)
    bad["reason_codes"]["EARTHQUAKE_SAFE_ZONE"] = "x"
    with pytest.raises(ValidationError):
        SeismicConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["interpretation"]["fault_distance_score"] = 1
    with pytest.raises(ValidationError):
        SeismicConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["default_policy"] = "BALANCED"
    with pytest.raises(ValidationError):
        SeismicConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["ground_response"]["available_evidence"] = ["slope"]
    with pytest.raises(ValidationError):
        SeismicConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    del bad["confidence"]["ground_response"]
    with pytest.raises(ValidationError):
        SeismicConfig.model_validate(bad)


def test_states_never_claim_safety():
    assert set(INTERPRETATION_STATES) == {
        "NO_MAJOR_SEISMIC_CONCERN_DETECTED",
        "REQUIRES_SEISMIC_VERIFICATION",
        "STRONG_SEISMIC_SCREENING_CONCERN",
        "UNRESOLVED",
    }
    for s in INTERPRETATION_STATES:
        assert not any(w in s for w in ("EARTHQUAKE_SAFE", "NO_EARTHQUAKE_RISK", "FAULT_SAFE"))
    for code in CFG.reason_codes:
        assert "SAFE" not in code.split("_")


def test_confidence_dimensions_stay_separate():
    for fam, dims in CFG.confidence.items():
        assert set(dims) == {
            "source",
            "methodology",
            "spatial_completeness",
            "temporal_completeness",
        }, fam
    assert CFG.decision_confidence == "LOW"


# ======================================================== fault distance


def test_fault_distance_alone_cannot_mean_safety():
    far = run(sc(fault_nearest_distance_km=500.0)).iloc[0]
    assert far["seismic_screening_interpretation"] == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"
    # that label is a screening term: the explanation says so and the codes never claim safety
    text = explain_seismic("X", pd.Series(sc(fault_nearest_distance_km=500.0)), far, CFG)
    assert "THIS DOES NOT MEAN" in text and "earthquake-safe" in text
    assert "GROUND_RESPONSE_NOT_ASSESSED" in far["seismic_informational_codes"]
    for col in far.index:
        assert "SAFE" not in str(far[col]).split("_")


def test_fault_distance_alone_cannot_create_strong_concern():
    for d in (0.0, 1.0, 4.9):
        r = run(sc(fault_nearest_distance_km=d)).iloc[0]
        assert r["seismic_screening_interpretation"] == "REQUIRES_SEISMIC_VERIFICATION"
        assert r["fault_tier"] == "STRONG_TIER" or d > 5
        assert r["corroborating_signals"] <= 1


def test_modelled_hazard_can_create_strong_concern_without_any_historical_event():
    """History is corroborating only: STRONG never depends on a catalogue entry."""
    dominant = sc(shaking_classVII_fraction=0.8, shaking_classV_fraction=0.2)
    for hist in (np.nan, 999.0, 10.0):  # absent, far, or nearby: same state
        r = run(dominant | {HIST: hist}).iloc[0]
        assert r["seismic_screening_interpretation"] == "STRONG_SEISMIC_SCREENING_CONCERN"
        assert "MODELLED_HAZARD_TOP_CLASS_DOMINANT" in r["seismic_reason_codes"]
    # no fault nearby either: modelled hazard alone is enough
    assert (
        run(dominant | {"fault_nearest_distance_km": 80.0}).iloc[0][
            "seismic_screening_interpretation"
        ]
        == "STRONG_SEISMIC_SCREENING_CONCERN"
    )


def test_fault_and_history_without_modelled_hazard_stay_verification():
    r = run(sc(fault_nearest_distance_km=1.0, **{HIST: 5.0})).iloc[0]
    assert r["seismic_screening_interpretation"] == "REQUIRES_SEISMIC_VERIFICATION"
    assert r["corroborating_signals"] == 2  # corroborating, not independent confirmation
    assert "STRONG" not in r["seismic_screening_interpretation"].split("_")[:1]


def test_borderline_modelled_hazard_escalates_only_with_positive_corroboration():
    border = sc(shaking_classVII_fraction=0.3, shaking_classV_fraction=0.7)
    plain = run(border).iloc[0]
    assert plain["modelled_hazard_tier"] == "NOTABLE"
    assert plain["seismic_screening_interpretation"] == "REQUIRES_SEISMIC_VERIFICATION"
    one = run(border | {"fault_nearest_distance_km": 2.0}).iloc[0]
    assert one["seismic_screening_interpretation"] == "REQUIRES_SEISMIC_VERIFICATION"
    two = run(border | {"fault_nearest_distance_km": 2.0, HIST: 10.0}).iloc[0]
    assert two["seismic_screening_interpretation"] == "STRONG_SEISMIC_SCREENING_CONCERN"
    assert "BORDERLINE_ESCALATED_BY_CORROBORATING_SIGNALS" in two["seismic_reason_codes"]
    # absence of the corroborating signals never lowers the (already verified) state
    assert plain["seismic_screening_interpretation"] == one["seismic_screening_interpretation"]


def test_eq_zone_basis_records_publisher_semantics_and_unknowns():
    basis = CFG.sources["intensity_zones"]["basis"]
    assert basis["kind"] == "PROBABILISTIC_PGA_HAZARD_DISPLAYED_AS_MMI_ZONES"
    assert basis["exceedance_probability"] == 0.10 and basis["exposure_period_years"] == 50
    assert "Sadigh" in basis["ground_motion_relation"]
    assert basis["pga_to_mmi_mapping_documented"] is False
    assert basis["map_scale_documented"] is False
    assert any("PGA to MMI" in u for u in basis["remaining_unknowns"])
    # both facts preserved: PGA-based analysis AND MMI display classes
    assert basis["displayed_classes"].startswith("MMI") and CLASSES == [
        "I-III",
        "IV",
        "V",
        "VI",
        "VII",
    ]


def test_corroborating_signals_are_not_multiplied_or_called_independent():
    text = (CONFIG_DIR / "seismic-evidence.yaml").read_text("utf-8").lower()
    assert "not independent" in text and "corroborating" in text
    r = run(sc(fault_nearest_distance_km=1.0, **{HIST: 5.0})).iloc[0]
    assert "independent" not in str(r.to_dict()).lower().replace("not independent", "")
    assert "probab" not in " ".join(c for c in r.index)


def test_regional_scope_is_explicit_in_outputs_and_explanations():
    inputs = pd.DataFrame([sc()])
    res = interpret_seismic(inputs, CFG)
    assert res["seismic_scope"].iloc[0] == "REGIONAL_SCREENING_NOT_SITE_ASSESSMENT"
    text = explain_seismic("X", inputs.iloc[0], res.iloc[0], CFG)
    assert "regional screening" in text and "parcel/site seismic assessment" in text


def test_fault_context_is_descriptive_with_no_score_column():
    cells = np.array([box(0, 0, 500, 500), box(30_000, 0, 30_500, 500)])
    faults = gpd.GeoDataFrame(
        {
            "F_ZONE_E": ["A", "B"],
            "F_NAME_E": ["a", "b"],
            "TYPE": ["Normal", "Strike-Slip"],
            "MCE": [6.5, 7.0],
            "LENGTH_KM": [10.0, 20.0],
        },
        geometry=[LineString([(1000, 0), (1000, 10_000)]), LineString([(80_000, 0), (80_000, 5)])],
        crs=UTM,
    )
    fc = fault_context(cells, faults, CFG)
    assert fc["fault_nearest_distance_km"].iloc[0] == pytest.approx(0.5)
    assert fc["fault_nearest_zone"].iloc[0] == "A"
    assert fc["fault_traces_within_5km"].tolist() == [1, 0]
    assert fc["fault_zones_within_20km"].tolist() == ["A", ""]
    assert not any("score" in c for c in fc.columns)


# ======================================================== historical events


def test_historical_event_absence_cannot_lower_concern():
    flagged = sc(fault_nearest_distance_km=2.0)
    base = run(flagged).iloc[0]["seismic_screening_interpretation"]
    for absent in (np.nan, 999.0):
        r = run(flagged | {HIST: absent}).iloc[0]
        assert r["seismic_screening_interpretation"] == base == "REQUIRES_SEISMIC_VERIFICATION"
    quiet = run(sc(**{HIST: np.nan})).iloc[0]
    assert quiet["seismic_screening_interpretation"] == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"
    assert "NO_NEARBY_HISTORICAL_EVENT_RECORDED" in quiet["seismic_informational_codes"]
    # an event can only raise concern
    assert run(flagged | {HIST: 30.0}).iloc[0]["history_tier"] == "NOTABLE"


def test_event_signals_never_reduce_any_family_when_added():
    rng = np.random.default_rng(3)
    cells = [
        sc(
            fault_nearest_distance_km=float(rng.uniform(0, 60)),
            shaking_classVII_fraction=float(rng.choice([0, 0.3, 0.8])),
            shaking_classV_fraction=0.0,
            **{HIST: float(rng.choice([np.nan, 80, 40, 10]))},
        )
        for _ in range(200)
    ]
    rank = {s: i for i, s in enumerate(INTERPRETATION_STATES)}
    base = run(*cells)["seismic_screening_interpretation"].map(rank)
    more = run(*[c | {HIST: 1.0} for c in cells])["seismic_screening_interpretation"].map(rank)
    unresolved = rank["UNRESOLVED"]
    ok = (more >= base) | (base == unresolved)
    assert ok.all()


def test_historical_context_counts_per_source_and_nearest_event():
    cells = np.array([box(0, 0, 500, 500)])
    mk = lambda xs, ms: gpd.GeoDataFrame(  # noqa: E731
        {"magnitude": ms}, geometry=[Point(x, 250) for x in xs], crs=UTM
    )
    hc = historical_context(
        cells, {"a": mk([2000, 60_000], [5.2, 6.1]), "b": mk([3000], [3.4])}, CFG
    )
    assert hc["hist_a_n_within_5km"].iloc[0] == 1 and hc["hist_a_n_within_50km"].iloc[0] == 1
    assert hc["hist_a_max_mag_within_5km"].iloc[0] == pytest.approx(5.2)
    assert hc["hist_b_n_within_5km"].iloc[0] == 1
    assert hc["hist_nearest_ge5_km"].iloc[0] == pytest.approx(1.5)  # across sources, existence only
    assert hc["hist_nearest_ge6_km"].iloc[0] == pytest.approx(59.5)


# ======================================================== terrain independence


def test_flat_terrain_cannot_reduce_seismic_concern():
    cells = [
        sc(
            fault_nearest_distance_km=2.0,
            shaking_classVII_fraction=0.9,
            shaking_classV_fraction=0.0,
            **{HIST: 5.0},
        ),
        sc(),
    ]
    plain = pd.DataFrame(cells)
    for slope, stratum in ((1.0, "LOW_SLOPE_LE_5"), (45.0, "STEEP_GT_15")):
        a = interpret_seismic(
            plain.assign(slope_p90_deg=slope, lowland_stratum=stratum, slope_stratum=stratum), CFG
        )
        b = interpret_seismic(plain, CFG)
        assert a.equals(b)
    assert {"slope_p90_deg", "lowland_stratum", "slope_stratum"} <= set(
        CFG.prohibited_evidence_columns
    )
    assert not set(seismic_input_columns(CFG)) & set(CFG.prohibited_evidence_columns)


def test_flat_terrain_is_not_positive_seismic_evidence():
    flat = run(sc(), sc())  # identical cells; terrain is not even an input
    assert (flat["seismic_screening_interpretation"] == "NO_MAJOR_SEISMIC_CONCERN_DETECTED").all()
    assert not any("slope" in c or "terrain" in c for c in seismic_input_columns(CFG))


# ======================================================== independence from hydrogeomorphic


def test_hydrogeomorphic_policy_cannot_alter_seismic_evidence():
    inputs = pd.DataFrame([sc(fault_nearest_distance_km=2.0), sc()])
    before = interpret_seismic(inputs, CFG)
    snapshot = inputs.copy(deep=True)
    for prof in ("CONSERVATIVE", "BALANCED", "PERMISSIVE"):
        apply_policy(
            pd.DataFrame([policy_cell(), policy_cell(landslide_class5_fraction=0.9)]), PCFG, prof
        )
    assert interpret_seismic(inputs, CFG).equals(before) and inputs.equals(snapshot)
    # hydrogeomorphic result columns are never read even if present and extreme
    polluted = inputs.assign(
        regional_search_status="REGIONAL_DEPRIORITIZE",
        hazard_interpretation="STRONG_CONCERN",
        flood_fusion_state="X",
    )
    assert interpret_seismic(polluted, CFG).equals(before)


def test_seismic_evidence_cannot_mutate_hydrogeomorphic_policy():
    ev = pd.DataFrame([policy_cell(), policy_cell(landslide_class5_fraction=0.6)])
    before = {p: apply_policy(ev, PCFG, p) for p in ("CONSERVATIVE", "BALANCED", "PERMISSIVE")}
    ev_snapshot = ev.copy(deep=True)
    interpret_seismic(pd.DataFrame([sc(fault_nearest_distance_km=0.0)] * 2), CFG)
    after = {p: apply_policy(ev, PCFG, p) for p in before}
    for p in before:
        assert before[p].equals(after[p])
    assert ev.equals(ev_snapshot)
    # seismic columns are not hydrogeomorphic policy inputs
    from hearthmap.hazard.policy import POLICY_INPUTS

    assert not [c for c in POLICY_INPUTS if "seismic" in c or "fault" in c or "shaking" in c]
    seismic_only = ev.assign(
        seismic_screening_interpretation="STRONG_SEISMIC_SCREENING_CONCERN",
        fault_nearest_distance_km=0.0,
    )
    assert apply_policy(seismic_only, PCFG, "BALANCED").equals(before["BALANCED"])


# ======================================================== ground response


def test_missing_ground_response_stays_explicit():
    gr = ground_response_columns(3, CFG)
    assert (gr["ground_response_status"] == "NOT_ASSESSED").all()
    assert (gr["ground_response_available_evidence"] == "").all()
    missing = gr["ground_response_missing_evidence"].iloc[0].split("|")
    for needed in (
        "liquefaction_susceptibility",
        "site_amplification_and_vs30",
        "sediment_thickness_and_basin_effects",
        "local_geology_and_ground_material",
        "parcel_level_geotechnical_conditions",
    ):
        assert needed in missing
    r = run(sc(), sc(fault_nearest_distance_km=1.0))
    assert r["seismic_informational_codes"].str.contains("GROUND_RESPONSE_NOT_ASSESSED").all()
    assert (r["seismic_evidence_completeness"] < 1.0).all()  # never complete without site effects
    assert (r["seismic_decision_confidence"] == "LOW").all()


def test_unresolved_when_zone_not_assessed_and_nothing_else_found():
    r = run(
        sc(shaking_assessed_fraction=0.1),
        sc(shaking_assessed_fraction=0.1, fault_nearest_distance_km=3.0),
    )
    assert r["seismic_screening_interpretation"].tolist() == [
        "UNRESOLVED",
        "REQUIRES_SEISMIC_VERIFICATION",
    ]  # positive evidence stays visible
    assert all("SHAKING_ZONE_NOT_ASSESSED" in v for v in r["seismic_unresolved_reasons"])


# ======================================================== determinism and explanations


def test_reason_code_explanations_are_deterministic():
    inputs = pd.DataFrame(
        [
            sc(
                fault_nearest_distance_km=1.0,
                shaking_classVII_fraction=0.9,
                shaking_classV_fraction=0.0,
                **{HIST: 5.0},
            )
        ]
    )
    res = interpret_seismic(inputs, CFG)
    a = explain_seismic("C1", inputs.iloc[0], res.iloc[0], CFG)
    b = explain_seismic(
        "C1", inputs.copy().iloc[0], interpret_seismic(inputs.copy(), CFG).iloc[0], CFG
    )
    assert a == b
    for code in res.iloc[0]["seismic_reason_codes"].split("|"):
        assert f"[{code}]" in a and code in CFG.reason_codes
    assert "ground" in a.lower() and "THIS DOES NOT MEAN" in a


def test_missing_input_columns_raise():
    with pytest.raises(KeyError):
        interpret_seismic(pd.DataFrame([{"fault_nearest_distance_km": 1.0}]), CFG)


# ======================================================== catalogue parsing


def test_tmd_date_and_magnitude_parsing():
    assert parse_tmd_date("22 กรกฎาคม 2569") == (2026, (2026, 7, 22), "DAY")
    assert parse_tmd_date("20 ก.พ.51")[0] == 2008
    assert parse_tmd_date("624 ปี ก่อน ค.ศ.")[0] == -624
    assert parse_tmd_date("???")[2] == "UNPARSED"
    assert parse_tmd_magnitude("5.3 Mb") == (5.3, "MAGNITUDE")
    assert parse_tmd_magnitude("VI MM") == (6.0, "MM_INTENSITY")
    assert np.isnan(parse_tmd_magnitude("-")[0])


# ======================================================== selected provisional defaults


def test_selected_defaults_are_recorded_provisional_and_not_truth():
    d = load_regional_defaults(CONFIG_DIR / "regional-screening-defaults.yaml")
    assert (d.hydrogeomorphic_profile, d.flood_fusion_policy) == ("BALANCED", "FLOOD_ANY_SOURCE")
    assert d.selected_for_provisional_screening is True and d.production_truth is False
    assert d.status == "PROVISIONAL"
    assert "scientifically optimal" in d.not_claimed
    assert set(d.retained_sensitivity_references) >= {
        "CONSERVATIVE",
        "PERMISSIVE",
        "FLOOD_CURRENT_PRIMARY",
        "FLOOD_UNION_CONSERVATIVE",
    }
    qa = load_human_qa(CONFIG_DIR / "human-qa.yaml")
    for gate in d.provisional_until_visual_qa_passed:
        assert qa.status(gate) == "PENDING"
    assert qa.status("m1a1_human_visual_signoff") == "PASSED"
    assert qa.status("m1b_human_visual_signoff") == "PASSED"


def test_selected_thresholds_are_unchanged_since_selection():
    d = load_regional_defaults(CONFIG_DIR / "regional-screening-defaults.yaml")
    now = threshold_fingerprint(PCFG, load_fusion_config(CONFIG_DIR / "flood-fusion.yaml"), d)
    assert now == d.threshold_fingerprint
    # other profiles/candidates still exist as sensitivity references
    assert {"CONSERVATIVE", "BALANCED", "PERMISSIVE"} <= set(PCFG.profiles)
    assert {"FLOOD_CURRENT_PRIMARY", "FLOOD_ANY_SOURCE", "FLOOD_UNION_CONSERVATIVE"} <= set(
        load_fusion_config(CONFIG_DIR / "flood-fusion.yaml").candidates
    )
    assert PCFG.default_profile is None  # selection is recorded, engine config unchanged
