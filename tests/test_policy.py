"""M1C hydrogeomorphic screening policy contracts. All inputs are SYNTHETIC."""

from __future__ import annotations

import copy

import numpy as np
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from hearthmap.hazard import (
    RegionalSearchStatus,
    apply_policy,
    connected_components,
    explain,
    load_policy_config,
)
from hearthmap.hazard.policy import FORBIDDEN_OUTCOME_WORDS, HazardPolicyConfig
from hearthmap.scoring import ComponentScore, ConstraintOutcome, HardConstraintResult, ScoringModel
from tests.conftest import CONFIG_DIR

CFG = load_policy_config(CONFIG_DIR / "hazard-policy.yaml")
PROFILES = ("CONSERVATIVE", "BALANCED", "PERMISSIVE")
S = RegionalSearchStatus


def cell(**o) -> dict:
    base = {
        "flood_area_fraction": 0.0,
        "flood_freq_ge2_area_fraction": 0.0,
        "flood_freq_ge3_area_fraction": 0.0,
        "flood_freq_ge5_area_fraction": 0.0,
        "flood_distance_m": 5000.0,
        "landslide_assessed_fraction": 1.0,
        "landslide_class3_fraction": 0.0,
        "landslide_class4_fraction": 0.0,
        "landslide_class5_fraction": 0.0,
        "landslide_inventory_points": 0,
        "landslide_inventory_distance_m": 9000.0,
        "terrain_support_px": 280.0,
        "slope_p90_deg": 3.0,
        # context (must never matter)
        "reserve_area_fraction": 0.0,
        "park_area_fraction": 0.0,
        "sanctuary_area_fraction": 0.0,
        "requires_legal_verification": False,
        "boundary_attribution_uncertain": False,
        "boundary_zone_ids": "",
        "dist_major_waterway_m": 3000.0,
        "dist_any_waterway_m": 800.0,
    }
    return base | o


def run(profile: str, *cells: dict) -> pd.DataFrame:
    return apply_policy(pd.DataFrame(list(cells)), CFG, profile)


# ======================================================== config / gates


def test_policy_is_provisional_without_default_while_gates_pending():
    assert CFG.status == "PROVISIONAL" and CFG.default_profile is None
    assert CFG.gates.m1a1_human_visual_signoff == "PENDING"
    assert CFG.gates.m1b_human_visual_signoff == "PENDING"
    assert CFG.scope == "HYDROGEOMORPHIC"


def _raw() -> dict:
    return copy.deepcopy(yaml.safe_load((CONFIG_DIR / "hazard-policy.yaml").read_text("utf-8")))


def test_default_profile_cannot_be_set_while_gates_pending():
    raw = _raw()
    raw["default_profile"] = "BALANCED"
    with pytest.raises(ValidationError, match="PENDING"):
        HazardPolicyConfig.model_validate(raw)
    raw = _raw()
    raw["status"] = "ACCEPTED"
    with pytest.raises(ValidationError, match="PENDING"):
        HazardPolicyConfig.model_validate(raw)


def test_terrain_may_never_deprioritize_alone_in_config():
    raw = _raw()
    raw["source_requirements"]["terrain"]["may_deprioritize_alone"] = True
    with pytest.raises(ValidationError, match="DSM terrain"):
        HazardPolicyConfig.model_validate(raw)


def test_flood_cannot_claim_contemporary_completeness():
    raw = _raw()
    raw["source_requirements"]["flood"]["contemporary_complete"] = True
    with pytest.raises(ValidationError, match="2016"):
        HazardPolicyConfig.model_validate(raw)


def test_outcome_vocabulary_has_no_safety_or_legal_words():
    for s in S:
        for word in FORBIDDEN_OUTCOME_WORDS:
            assert word not in s.value


# ======================================================== terrain


@pytest.mark.parametrize("profile", PROFILES)
def test_dsm_terrain_alone_cannot_deprioritize(profile):
    r = run(profile, cell(slope_p90_deg=70.0)).iloc[0]
    assert r["regional_search_status"] == S.REQUIRES_VERIFICATION
    assert r["terrain_policy_level"] == "VERIFY"
    assert "TERRAIN_STEEPNESS_PROXY_HIGH" in r["hazard_reason_codes"]


def test_terrain_corroboration_is_categorical_and_profile_controlled():
    c = cell(landslide_class5_fraction=0.3, slope_p90_deg=45.0)
    cons = run("CONSERVATIVE", c).iloc[0]
    bal = run("BALANCED", c).iloc[0]
    assert "LANDSLIDE_TERRAIN_CORROBORATED" in cons["hazard_reason_codes"]
    assert cons["regional_search_status"] == S.REGIONAL_DEPRIORITIZE  # escalates in CONSERVATIVE
    assert bal["regional_search_status"] == S.STRONG_REGIONAL_CONCERN  # no escalation in BALANCED


# ======================================================== landslide


@pytest.mark.parametrize("profile", PROFILES)
def test_missing_dmr_coverage_cannot_become_reassuring(profile):
    r = run(profile, cell(landslide_assessed_fraction=0.0, slope_p90_deg=1.0)).iloc[0]
    assert r["regional_search_status"] == S.UNRESOLVED
    assert r["evidence_completeness_class"] == "UNRESOLVED_CRITICAL"
    assert "LANDSLIDE_NOT_ASSESSED" in r["unresolved_reasons"]
    assert "landslide-susceptibility-dmr" in r["missing_or_incomplete_sources"]


def test_partially_assessed_is_unresolved_partial():
    r = run("BALANCED", cell(landslide_assessed_fraction=0.3)).iloc[0]
    assert r["regional_search_status"] == S.UNRESOLVED
    assert r["evidence_completeness_class"] == "UNRESOLVED_PARTIAL"


def test_positive_evidence_stays_visible_despite_incomplete_landslide():
    r = run(
        "BALANCED",
        cell(
            landslide_assessed_fraction=0.0,
            flood_freq_ge3_area_fraction=0.3,
            flood_area_fraction=0.4,
        ),
    ).iloc[0]
    assert r["regional_search_status"] == S.STRONG_REGIONAL_CONCERN
    assert r["unresolved_reasons"] == "LANDSLIDE_NOT_ASSESSED"
    assert r["data_verification_required"]


@pytest.mark.parametrize("profile", PROFILES)
def test_scar_absence_cannot_reduce_concern(profile):
    with_scar = run(
        profile,
        cell(
            landslide_class5_fraction=0.8,
            landslide_inventory_points=2,
            landslide_inventory_distance_m=0.0,
        ),
    ).iloc[0]
    without = run(profile, cell(landslide_class5_fraction=0.8)).iloc[0]
    order = [
        S.NO_MAJOR_CONCERN_DETECTED,
        S.REQUIRES_VERIFICATION,
        S.STRONG_REGIONAL_CONCERN,
        S.REGIONAL_DEPRIORITIZE,
    ]
    assert order.index(S(with_scar["regional_search_status"])) >= order.index(
        S(without["regional_search_status"])
    )
    # and a cell with no scar is never better than the same cell's susceptibility alone
    assert without["landslide_policy_level"] in ("STRONG", "DEPRIORITIZE")


def test_scar_raises_none_to_verification():
    r = run(
        "BALANCED", cell(landslide_inventory_points=1, landslide_inventory_distance_m=0.0)
    ).iloc[0]
    assert r["regional_search_status"] == S.REQUIRES_VERIFICATION
    assert "HISTORICAL_LANDSLIDE_SCAR_NEARBY" in r["hazard_reason_codes"]


def test_high_plus_very_high_split_is_not_mild():
    # 40% High + 40% Very High: neither class dominates, combined 80% must count
    r = run("BALANCED", cell(landslide_class4_fraction=0.4, landslide_class5_fraction=0.4)).iloc[0]
    assert r["regional_search_status"] == S.REGIONAL_DEPRIORITIZE
    assert "HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT" in r["hazard_reason_codes"]


# ======================================================== flood


@pytest.mark.parametrize("profile", PROFILES)
def test_flood_absence_is_not_flood_safety(profile):
    r = run(profile, cell()).iloc[0]
    assert r["regional_search_status"] == S.NO_MAJOR_CONCERN_DETECTED
    assert "NO_OBSERVED_FLOOD_IN_RECORD" in r["informational_codes"]
    text = explain("X", pd.Series(cell()), r, CFG)
    assert "not evidence of no flood risk" in text
    assert "THIS DOES NOT MEAN" in text and "unsafe or safe" in text


# ======================================================== multi-hazard


@pytest.mark.parametrize("profile", PROFILES)
def test_severe_single_hazard_is_not_averaged_away(profile):
    r = run(profile, cell(landslide_class5_fraction=1.0, landslide_class4_fraction=0.0)).iloc[0]
    assert r["regional_search_status"] == S.REGIONAL_DEPRIORITIZE
    assert r["flood_policy_level"] == "NONE"


def test_multiple_strong_hazards_escalate_where_configured():
    c = cell(
        flood_freq_ge3_area_fraction=0.2, flood_area_fraction=0.3, landslide_class5_fraction=0.3
    )
    assert run("BALANCED", c).iloc[0]["regional_search_status"] == S.REGIONAL_DEPRIORITIZE
    assert "MULTIPLE_STRONG_HAZARD_SIGNALS" in run("BALANCED", c).iloc[0]["hazard_reason_codes"]
    perm = run(
        "PERMISSIVE",
        cell(
            flood_freq_ge3_area_fraction=0.3, flood_area_fraction=0.3, landslide_class5_fraction=0.6
        ),
    ).iloc[0]
    assert perm["regional_search_status"] == S.STRONG_REGIONAL_CONCERN


# ======================================================== context independence


@pytest.mark.parametrize(
    "ctx",
    [
        {
            "reserve_area_fraction": 1.0,
            "park_area_fraction": 1.0,
            "requires_legal_verification": True,
        },
        {"boundary_attribution_uncertain": True, "boundary_zone_ids": "gistda-50k-0009"},
        {"dist_major_waterway_m": 0.0, "dist_any_waterway_m": 0.0},
        {"dist_major_waterway_m": 99999.0, "dist_any_waterway_m": 99999.0},
    ],
)
@pytest.mark.parametrize("profile", PROFILES)
def test_context_never_changes_policy(ctx, profile):
    for base in (
        cell(),
        cell(landslide_class5_fraction=0.6),
        cell(landslide_assessed_fraction=0),
        cell(flood_freq_ge3_area_fraction=0.6, flood_area_fraction=0.6),
    ):
        pd.testing.assert_frame_equal(run(profile, base), run(profile, base | ctx))


def test_forest_or_legal_columns_cannot_be_configured_as_policy_inputs():
    raw = _raw()
    raw["prohibited_evidence_columns"].append("slope_p90_deg")  # simulate a conflict
    with pytest.raises(ValidationError, match="prohibited"):
        HazardPolicyConfig.model_validate(raw)


# ======================================================== eligibility / scoring separation


def test_policy_cannot_mutate_eligibility(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    comps = [ComponentScore(dimension_id=d, value=50) for d in "abc"]
    before = model.assess("u", [], comps)
    out = run("CONSERVATIVE", cell(landslide_class5_fraction=1.0))
    after = model.assess("u", [], comps)
    assert before == after
    assert "eligible" not in out.columns and "regional_search_status" in out.columns


def test_provisional_policy_cannot_become_scoring_evidence():
    with pytest.raises(ValidationError, match="provisional screening policy"):
        HardConstraintResult(
            constraint_id="flood_unacceptable",
            outcome=ConstraintOutcome.UNKNOWN,
            reason="r",
            source_ids=["policy:BALANCED:REGIONAL_DEPRIORITIZE"],
        )
    with pytest.raises(ValidationError, match="provisional screening policy"):
        ComponentScore(dimension_id="hazard_resilience", value=0, source_ids=["policy:x"])


# ======================================================== explanation / profiles


def test_explanation_is_deterministic_and_code_driven():
    c = cell(landslide_class5_fraction=0.61, slope_p90_deg=40.0)
    r = run("BALANCED", c).iloc[0]
    a = explain("G500-E1-N1", pd.Series(c), r, CFG)
    b = explain("G500-E1-N1", pd.Series(c), r, CFG)
    assert a == b
    assert "DMR 'Very High' susceptibility covers 61% of the cell" in a
    assert "[VERY_HIGH_LANDSLIDE_SUSCEPTIBILITY_DOMINANT]" in a
    assert "DSM" in a and "methodology is not published" in a


def test_every_emitted_reason_code_has_a_template():
    cells = [
        cell(),
        cell(
            landslide_class5_fraction=0.6,
            landslide_inventory_points=1,
            landslide_inventory_distance_m=0,
            slope_p90_deg=50,
        ),
        cell(flood_freq_ge3_area_fraction=0.8, flood_area_fraction=0.9),
        cell(landslide_assessed_fraction=0.2, terrain_support_px=0.5),
        cell(landslide_assessed_fraction=0.7, terrain_support_px=5),
    ]
    for prof in PROFILES:
        out = run(prof, *cells)
        for col in (
            "hazard_reason_codes",
            "data_reason_codes",
            "unresolved_reasons",
            "informational_codes",
        ):
            for codes in out[col]:
                for code in filter(None, codes.split("|")):
                    assert code in CFG.reason_codes


def test_profiles_obey_configuration_thresholds():
    # flood recurrent fraction 0.15: CONSERVATIVE (strong .05, dep .25) STRONG;
    # BALANCED (strong .10) STRONG; PERMISSIVE (strong .25) only VERIFY
    c = cell(flood_freq_ge3_area_fraction=0.15, flood_area_fraction=0.15)
    got = {p: run(p, c).iloc[0]["flood_policy_level"] for p in PROFILES}
    assert got == {"CONSERVATIVE": "STRONG", "BALANCED": "STRONG", "PERMISSIVE": "VERIFY"}
    c2 = cell(flood_freq_ge3_area_fraction=0.3, flood_area_fraction=0.3)
    assert run("CONSERVATIVE", c2).iloc[0]["flood_policy_level"] == "DEPRIORITIZE"


def test_profiles_are_monotone_on_a_grid_of_cases():
    rng = np.random.default_rng(0)
    cases = [
        cell(
            flood_freq_ge3_area_fraction=a,
            flood_area_fraction=a,
            landslide_class4_fraction=b,
            landslide_class5_fraction=c,
            slope_p90_deg=s,
        )
        for a, b, c, s in rng.uniform([0, 0, 0, 0], [1, 0.5, 0.5, 60], size=(200, 4))
    ]
    rank = {
        S.NO_MAJOR_CONCERN_DETECTED: 0,
        S.REQUIRES_VERIFICATION: 1,
        S.STRONG_REGIONAL_CONCERN: 2,
        S.REGIONAL_DEPRIORITIZE: 3,
    }
    r = {p: run(p, *cases)["regional_search_status"].map(lambda v: rank[S(v)]) for p in PROFILES}
    assert (r["CONSERVATIVE"] >= r["BALANCED"]).all()
    assert (r["BALANCED"] >= r["PERMISSIVE"]).all()


# ======================================================== spatial structure


def test_connected_components_four_neighbour():
    cols = np.array([0, 1, 1, 5, 5, 7])
    rows = np.array([0, 0, 1, 5, 6, 7])  # (7,7) touches (5,6)? no; diagonal never joins
    labels = connected_components(cols, rows)
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4]
    assert len(set(labels)) == 3
    diag = connected_components(np.array([0, 1]), np.array([0, 1]))
    assert diag[0] != diag[1]
