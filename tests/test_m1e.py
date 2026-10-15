"""M1E natural-hazard integration contracts. All inputs are SYNTHETIC."""

from __future__ import annotations

import copy
from dataclasses import fields
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from hearthmap.hazard import apply_policy, load_policy_config
from hearthmap.hazard.integration import (
    FAMILIES,
    HazardDimensions,
    IntegrationConfig,
    integrate,
    load_integration_config,
    parcel_checklist,
    scalar_hazard_score,
    to_suitability_dimensions,
)
from hearthmap.qa import load_human_qa
from hearthmap.seismic import ground_response_columns, interpret_seismic, load_seismic_config
from tests.conftest import CONFIG_DIR
from tests.test_policy import cell as policy_cell

CFG = load_integration_config(CONFIG_DIR / "hazard-integration.yaml")
PCFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
SCFG = load_seismic_config(CONFIG_DIR / "seismic-evidence.yaml")
CLASSES = SCFG.sources["intensity_zones"]["classes"]
HIST = f"hist_nearest_ge{SCFG.interpretation.history.magnitude:g}_km"
POLICIES = tuple(CFG.integration_policies)


def hydro(*cells: dict) -> pd.DataFrame:
    return apply_policy(pd.DataFrame([policy_cell(**c) for c in cells]), PCFG, "BALANCED")


def seis(*cells: dict) -> pd.DataFrame:
    rows = []
    for c in cells:
        base = {
            "fault_nearest_distance_km": 40.0,
            "shaking_assessed_fraction": 1.0,
            **{f"shaking_class{k}_fraction": 0.0 for k in CLASSES},
            "shaking_classV_fraction": 1.0,
            HIST: np.nan,
        }
        rows.append(base | c)
    df = pd.DataFrame(rows)
    out = interpret_seismic(df, SCFG)
    return pd.concat([out, ground_response_columns(len(df), SCFG)], axis=1)


STRONG_SEIS = {"shaking_classVII_fraction": 0.9, "shaking_classV_fraction": 0.1}
FLOOD_DEPRI = {
    "flood_years_ge3_area_fraction": 0.7,
    "flood_area_fraction": 0.7,
    "flood_distance_m": 0.0,
}
LANDSLIDE_DEPRI = {"landslide_class5_fraction": 0.7}


def run(h: dict, s: dict) -> pd.Series:
    return integrate(hydro(h), seis(s), CFG).iloc[0]


# ======================================================== config guards


def test_config_is_provisional_with_no_selected_policy_and_inactive_scoring():
    assert CFG.status == "PROVISIONAL" and CFG.default_integration_policy is None
    assert CFG.scoring_activated is False and CFG.future_suitability_contract["activated"] is False
    assert set(POLICIES) == {"AVOIDANCE_FIRST", "BALANCED_ACTION", "VERIFICATION_FIRST"}


def test_config_rejects_seismic_or_terrain_avoidance_and_active_scoring():
    raw = yaml.safe_load((CONFIG_DIR / "hazard-integration.yaml").read_text("utf-8"))
    for fam, sev in (
        ("seismic_shaking", "STRONG"),
        ("terrain", "VERIFY"),
        ("fault_context", "STRONG"),
    ):
        bad = copy.deepcopy(raw)
        bad["family_actions"][fam][sev] = "STRONG_AVOIDANCE_SIGNAL"
        with pytest.raises(ValidationError):
            IntegrationConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["family_actions"]["historical_seismicity"]["STRONG"] = "VERIFY_SITE"
    with pytest.raises(ValidationError):
        IntegrationConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["future_suitability_contract"]["activated"] = True
    with pytest.raises(ValidationError):
        IntegrationConfig.model_validate(bad)
    bad = copy.deepcopy(raw)
    bad["default_integration_policy"] = "BALANCED_ACTION"
    with pytest.raises(ValidationError):
        IntegrationConfig.model_validate(bad)


def test_response_taxonomy_distinguishes_avoid_verify_mitigate_context():
    r = {k: v["primary"] for k, v in CFG.rule_responses.items()}
    assert (
        r["flood_strong_recurrent"] == "AVOID" and r["landslide_strong_susceptibility"] == "AVOID"
    )
    assert r["terrain_steep_dsm_proxy"] == "VERIFY" and r["active_fault_proximity"] == "VERIFY"
    assert r["seismic_regional_shaking_class_vii"] == "MITIGATE"
    assert r["historical_earthquake_record"] == "CONTEXT"
    assert {"AVOID", "VERIFY", "MITIGATE", "CONTEXT"} <= set(CFG.response_classes)


# ======================================================== seismic cannot deprioritize / cancel


def test_seismic_strong_alone_cannot_regional_deprioritize():
    clean = {}  # hydro: nothing flagged
    for name in POLICIES:
        h, s = hydro(clean), seis(STRONG_SEIS)
        out = integrate(h, s, CFG).iloc[0]
        assert s["seismic_screening_interpretation"].iloc[0] == "STRONG_SEISMIC_SCREENING_CONCERN"
        col = (
            "regional_search_action"
            if name == CFG.reference_policy_for_main_outputs
            else f"regional_search_action__{name.lower()}"
        )
        assert out[col] != "DEPRIORITIZE_REGION"
        assert out[col] == "CONTINUE_SEARCH"
    assert out["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED"
    assert "SEISMIC_SHAKING_DOES_NOT_DEPRIORITIZE_REGION" in out["reason_codes"]


def test_seismic_mildness_cannot_cancel_flood_concern():
    states = []
    for s in ({}, {"fault_nearest_distance_km": 2.0}, STRONG_SEIS):
        out = run(FLOOD_DEPRI, s)
        states.append(out["regional_search_action"])
        assert out["flood_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL"
        assert out["flood_response_class"] == "AVOID"
    assert set(states) == {"DEPRIORITIZE_REGION"}  # mild (none), verify and strong seismic alike


def test_seismic_mildness_cannot_cancel_landslide_concern():
    states = {run(LANDSLIDE_DEPRI, s)["regional_search_action"] for s in ({}, STRONG_SEIS)}
    assert states == {"DEPRIORITIZE_REGION"}
    assert run(LANDSLIDE_DEPRI, {})["landslide_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL"


def test_seismic_never_changes_regional_search_action_for_any_hydro_scenario():
    rng = np.random.default_rng(5)
    hs = [
        {
            "flood_years_ge3_area_fraction": float(rng.choice([0, 0.05, 0.2, 0.7])),
            "flood_area_fraction": float(rng.choice([0, 0.2, 0.7])),
            "landslide_class5_fraction": float(rng.choice([0, 0.3, 0.7])),
            "landslide_assessed_fraction": float(rng.choice([1.0, 0.0])),
            "slope_p90_deg": float(rng.choice([3.0, 32.0])),
        }
        for _ in range(150)
    ]
    h = hydro(*hs)
    none = integrate(h, seis(*[{}] * len(hs)), CFG)
    strong = integrate(h, seis(*[STRONG_SEIS] * len(hs)), CFG)
    for col in [c for c in none.columns if c.startswith("regional_search_action")]:
        assert (none[col] == strong[col]).all(), col
    # engineering mitigation never feeds back into search eligibility
    assert (strong["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED").all()
    assert (none["engineering_mitigation_action"] == "NONE_TRIGGERED").all()


# ======================================================== both meanings preserved


def test_hydro_favourable_plus_seismic_strong_preserves_both_meanings():
    out = run({}, STRONG_SEIS)
    assert out["regional_search_action"] == "CONTINUE_SEARCH"
    assert out["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED"
    assert out["natural_hazard_integrated_state"] == "ENGINEERING_MITIGATION_REQUIRED"
    for fam in ("flood", "landslide", "terrain"):
        assert out[f"{fam}_severity"] == "NONE"
        assert out[f"{fam}_recommended_action"] == "NO_MAJOR_ACTION_TRIGGERED"
    assert out["seismic_shaking_severity"] == "STRONG"
    assert "ENGINEERING_MITIGATION_REQUIRED" in out["hazard_action_set"]
    # not averaged into some middle value: no numeric hazard column exists
    assert not any(
        "score" in c.lower() for c in integrate(hydro({}), seis(STRONG_SEIS), CFG).columns
    )


def test_avoidance_and_mitigation_remain_distinct_actions():
    avoid_only = run(FLOOD_DEPRI, {})
    mit_only = run({}, STRONG_SEIS)
    both = run(FLOOD_DEPRI, STRONG_SEIS)
    assert avoid_only["natural_hazard_integrated_state"] == "STRONG_AVOIDANCE_SIGNAL"
    assert avoid_only["engineering_mitigation_action"] == "NONE_TRIGGERED"
    assert mit_only["natural_hazard_integrated_state"] == "ENGINEERING_MITIGATION_REQUIRED"
    assert mit_only["regional_search_action"] == "CONTINUE_SEARCH"
    assert both["natural_hazard_integrated_state"] == "MULTIPLE_ACTIONS"
    assert {"STRONG_AVOIDANCE_SIGNAL", "ENGINEERING_MITIGATION_REQUIRED"} <= set(
        both["hazard_action_set"].split("|")
    )


def test_terrain_fault_and_history_cannot_create_avoidance():
    out = run({"slope_p90_deg": 38.0}, {"fault_nearest_distance_km": 1.0, HIST: 5.0})
    assert out["terrain_recommended_action"] == "VERIFY_SITE"
    assert out["fault_context_recommended_action"] == "VERIFY_SITE"
    assert out["historical_seismicity_recommended_action"] == "CONTEXT_ONLY"
    assert "STRONG_AVOIDANCE_SIGNAL" not in out["hazard_action_set"]
    assert out["regional_search_action"] == "CONTINUE_SEARCH"
    assert out["site_verification_action"] == "VERIFY_SITE_REQUIRED"


def test_integration_policies_only_translate_hydro_outcomes():
    flood_strong = {"flood_years_ge3_area_fraction": 0.2, "flood_area_fraction": 0.2}
    out = run(flood_strong, STRONG_SEIS)
    assert out["flood_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL"
    assert out["regional_search_action"] == "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION"
    assert out["regional_search_action__avoidance_first"] == "DEPRIORITIZE_REGION"
    assert (
        out["regional_search_action__verification_first"]
        == "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION"
    )
    # AVOIDANCE_FIRST deprioritizes a superset of the reference mapping
    rng = np.random.default_rng(2)
    hs = [
        {
            "flood_years_ge3_area_fraction": float(rng.choice([0, 0.2, 0.7])),
            "landslide_class5_fraction": float(rng.choice([0, 0.3, 0.7])),
        }
        for _ in range(120)
    ]
    df = integrate(hydro(*hs), seis(*[{}] * len(hs)), CFG)
    ref = df["regional_search_action"] == "DEPRIORITIZE_REGION"
    av = df["regional_search_action__avoidance_first"] == "DEPRIORITIZE_REGION"
    assert (av | ~ref).all()


# ======================================================== unresolved / ground response


def test_ground_response_unknown_remains_visible_everywhere():
    df = integrate(hydro({}, FLOOD_DEPRI), seis({}, STRONG_SEIS), CFG)
    assert (df["ground_response_status"] == "NOT_ASSESSED").all()
    assert (df["site_response_investigation"] == "REQUIRED_FOR_ANY_PARCEL").all()
    assert df["reason_codes"].str.contains("integration:GROUND_RESPONSE_NOT_ASSESSED").all()
    assert df["data_completeness"].str.contains("SITE_RESPONSE_MISSING").any()
    assert (~df["production_truth"]).all() and df["selected_for_provisional_screening"].all()


def test_unresolved_hydro_evidence_stays_unresolved_despite_seismic_results():
    out = run({"landslide_assessed_fraction": 0.0}, STRONG_SEIS)
    assert out["landslide_recommended_action"] == "UNRESOLVED"
    assert out["landslide_confidence"] == "UNKNOWN"
    assert out["data_completeness"] == "CRITICAL_REGIONAL_GAP"
    assert out["regional_search_action"] == "UNRESOLVED"  # seismic cannot resolve it
    assert out["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED"


def test_absence_is_never_high_confidence():
    out = run({}, {})
    for fam in FAMILIES:
        assert out[f"{fam}_confidence"] in ("LOW", "UNKNOWN")
    assert out["natural_hazard_integrated_state"] == "NO_MAJOR_ACTION_TRIGGERED"
    assert "SAFE" not in " ".join(str(v) for v in out.to_dict().values()).replace("NOT_SAFE", "")


# ======================================================== determinism / handoff / future contract


def test_integration_is_deterministic_with_stable_reason_codes():
    h, s = hydro({}, FLOOD_DEPRI, LANDSLIDE_DEPRI), seis(STRONG_SEIS, {}, STRONG_SEIS)
    a, b = integrate(h, s, CFG), integrate(h.copy(), s.copy(), CFG)
    assert a.equals(b)
    assert all(
        c.startswith(
            (
                "flood:",
                "landslide:",
                "seismic_shaking:",
                "fault_context:",
                "historical_seismicity:",
                "integration:",
                "terrain:",
            )
        )
        for c in "|".join(a["reason_codes"]).split("|")
        if c
    )


def test_parcel_handoff_is_a_contract_not_a_check():
    out = run(FLOOD_DEPRI, STRONG_SEIS)
    items = parcel_checklist(out, CFG)
    for need in (
        "obtain_local_flood_history",
        "check_road_and_drainage_elevation",
        "verify_fault_and_site_geology",
        "evaluate_seismic_structural_requirements",
        "assess_liquefaction_and_site_amplification_where_relevant",
        "parcel_specific_site_response_investigation",
    ):
        assert need in items
    assert parcel_checklist(run({}, {}), CFG) == ["parcel_specific_site_response_investigation"]


def test_future_scoring_interface_cannot_collapse_actions_silently():
    out = run(FLOOD_DEPRI, STRONG_SEIS)
    dims = to_suitability_dimensions(out, CFG)
    assert [f.name for f in fields(HazardDimensions)] == [
        "hazard_search_eligibility",
        "hazard_verification_burden",
        "hazard_engineering_burden",
        "hazard_uncertainty",
    ]
    assert dims.hazard_search_eligibility == "DEPRIORITIZED"
    assert dims.hazard_engineering_burden == "SEISMIC_DESIGN_REQUIRED"
    with pytest.raises(TypeError):
        float(dims)
    with pytest.raises(NotImplementedError):
        scalar_hazard_score(dims)
    assert not any("score" in f.name for f in fields(HazardDimensions))
    contract = CFG.future_suitability_contract
    assert "scalar_hazard_score_0_100" in contract["forbidden"] and contract["activated"] is False
    # the suitability scoring engine does not consume the integration layer
    src = Path("src/hearthmap/scoring")
    assert not any("integration" in p.read_text("utf-8") for p in src.glob("*.py"))


def test_human_qa_gates_stay_truthful():
    q = load_human_qa(CONFIG_DIR / "human-qa.yaml")
    assert q.status("m1a1_human_visual_signoff") == "PASSED"
    assert q.status("m1b_human_visual_signoff") == "PASSED"
    for g in ("m1c", "m1c1", "m1c2", "m1c3", "m1d"):
        assert q.status(f"{g}_human_visual_signoff") == "PENDING", g
    assert PCFG.default_profile is None


def test_verification_burden_distribution_reconciles_to_its_reported_total():
    """M1E.1 accounting invariant: the flag and the trigger count are one population."""
    rng = np.random.default_rng(11)
    hs = [
        {
            "flood_years_ge3_area_fraction": float(rng.choice([0, 0.05, 0.2])),
            "flood_area_fraction": float(rng.choice([0, 0.2])),
            "slope_p90_deg": float(rng.choice([3.0, 32.0])),
            "landslide_class5_fraction": float(rng.choice([0, 0.3])),
        }
        for _ in range(300)
    ]
    ss = [
        {
            "fault_nearest_distance_km": float(rng.choice([2.0, 8.0, 40.0])),
            HIST: float(rng.choice([np.nan, 10.0, 40.0])),
            "shaking_classVII_fraction": float(rng.choice([0, 0.3, 0.9])),
            "shaking_classV_fraction": 0.0,
        }
        for _ in range(300)
    ]
    df = integrate(hydro(*hs), seis(*ss), CFG)
    flag = df["site_verification_action"] == "VERIFY_SITE_REQUIRED"
    k = df["site_verification_burden_count"]
    assert (flag == (k >= 1)).all()  # no cell flagged with 0 triggers, none counted but unflagged
    dist = k.value_counts()
    assert dist.sum() == len(df) and dist[dist.index >= 1].sum() == flag.sum()
    assert (df.loc[k == 0, "site_verification_families"] == "").all()
    # a history-only seismic verification is attributed, not dropped
    hist_only = run({}, {HIST: 10.0})
    assert hist_only["site_verification_action"] == "VERIFY_SITE_REQUIRED"
    assert hist_only["site_verification_burden_count"] == 1
    assert hist_only["site_verification_families"] == "seismic_state"
