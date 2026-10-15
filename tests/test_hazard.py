"""M1B hazard evidence contracts. All inputs are SYNTHETIC."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from shapely.geometry import box

from hearthmap.hazard import (
    CONTEXT_COLUMNS,
    HazardState,
    experimental_candidates,
    interpret,
    load_hazard_config,
    threshold_sensitivity,
)
from hearthmap.qa import ReviewLayerError, mark_review_only
from hearthmap.scoring import (
    ComponentScore,
    ConstraintOutcome,
    EligibilityStatus,
    HardConstraintResult,
    ScoringModel,
)
from hearthmap.spatial import GridSpec, generate_grid
from hearthmap.spatial.overlay import categorical_cell_fractions
from tests.conftest import CONFIG_DIR
from tests.fixtures import synthetic

CFG = load_hazard_config(CONFIG_DIR / "hazard.yaml")
UTM = "EPSG:32647"
X0, Y0 = synthetic.ORIGIN_X, synthetic.ORIGIN_Y


def cell(**overrides) -> dict:
    """Baseline: assessed everywhere, no hazard evidence at all."""
    base = {
        "flood_area_fraction": 0.0,
        "flood_freq_ge3_area_fraction": 0.0,
        "flood_distance_m": 5000.0,
        "flood_assessed": True,
        "landslide_assessed_fraction": 1.0,
        "landslide_class3_fraction": 0.0,
        "landslide_class4_fraction": 0.0,
        "landslide_class5_fraction": 0.0,
        "landslide_inventory_points": 0,
        "terrain_support_px": 280.0,
        "slope_p90_deg": 3.0,
        "boundary_attribution_uncertain": False,
        "boundary_zone_ids": "",
        "reserve_area_fraction": 0.0,
        "park_area_fraction": 0.0,
        "sanctuary_area_fraction": 0.0,
        "requires_legal_verification": False,
    }
    return base | overrides


def run(*cells: dict) -> pd.DataFrame:
    return interpret(pd.DataFrame(list(cells)), CFG)


# ======================================================== config / gate


def test_config_is_provisional_and_gate_pending():
    assert CFG.status == "PROVISIONAL"
    assert CFG.gates.m1a1_human_visual_signoff == "PENDING"


# ======================================================== absence != safety


def test_flood_absence_is_not_safety():
    r = run(cell()).iloc[0]
    assert r["flood_state"] == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED
    assert "NOT evidence of no flood risk" in r["flood_reason"]
    assert r["flood_confidence"] == "LOW"  # absence of observation is weak evidence
    # No state or reason may call a cell safe (the disclaimer note is checked separately).
    for v in r.drop("interpretation_note").astype(str):
        assert "SAFE" not in v.upper()
    assert "not 'safe'" in r["interpretation_note"]


def test_states_vocabulary_has_no_safe_or_low_risk():
    assert {s.value for s in HazardState} == {
        "HIGH_HAZARD_EVIDENCE",
        "CAUTION",
        "NO_HIGH_HAZARD_EVIDENCE_DETECTED",
        "UNRESOLVED",
    }


# ======================================================== severity not averaged


def test_severe_landslide_is_not_averaged_away_by_flood_absence():
    r = run(cell(landslide_class5_fraction=0.9, landslide_class4_fraction=0.1)).iloc[0]
    assert r["landslide_state"] == HazardState.HIGH_HAZARD_EVIDENCE
    assert r["flood_state"] == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED
    assert r["overall_state"] == HazardState.HIGH_HAZARD_EVIDENCE
    assert r["high_hazards"] == "landslide"


def test_each_hazard_kept_independently():
    r = run(
        cell(flood_freq_ge3_area_fraction=0.5, flood_area_fraction=0.6, slope_p90_deg=25.0)
    ).iloc[0]
    assert r["flood_state"] == HazardState.HIGH_HAZARD_EVIDENCE
    assert r["terrain_state"] == HazardState.CAUTION
    assert r["landslide_state"] == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED
    assert r["high_hazards"] == "flood" and r["caution_hazards"] == "terrain"


# ======================================================== incomplete evidence


def test_unassessed_landslide_makes_cell_unresolved():
    r = run(cell(landslide_assessed_fraction=0.0)).iloc[0]
    assert r["landslide_state"] == HazardState.UNRESOLVED
    assert r["overall_state"] == HazardState.UNRESOLVED
    assert r["evidence_completeness"] == pytest.approx(2 / 3)
    assert r["interpretation_confidence"] == "UNKNOWN"


def test_high_evidence_stays_visible_even_when_other_hazards_unresolved():
    r = run(
        cell(
            landslide_assessed_fraction=0.0,
            flood_freq_ge3_area_fraction=0.3,
            flood_area_fraction=0.4,
        )
    ).iloc[0]
    assert r["overall_state"] == HazardState.HIGH_HAZARD_EVIDENCE
    assert r["unresolved_hazards"] == "landslide"


def test_partially_assessed_cell_with_very_high_class_is_high_not_unresolved():
    r = run(cell(landslide_assessed_fraction=0.3, landslide_class5_fraction=0.3)).iloc[0]
    assert r["landslide_state"] == HazardState.HIGH_HAZARD_EVIDENCE


def test_terrain_without_support_is_unresolved():
    r = run(cell(terrain_support_px=0.4, slope_p90_deg=np.nan)).iloc[0]
    assert r["terrain_state"] == HazardState.UNRESOLVED
    r2 = run(cell(terrain_support_px=5.0)).iloc[0]
    assert bool(r2["terrain_low_support"])


def test_terrain_interpretation_always_states_dsm_limitation():
    r = run(cell(slope_p90_deg=40.0)).iloc[0]
    assert r["terrain_state"] == HazardState.HIGH_HAZARD_EVIDENCE
    assert "DSM" in r["terrain_reason"] and r["terrain_confidence"] == "LOW"


# ======================================================== context independence


@pytest.mark.parametrize(
    "ctx",
    [
        {"boundary_attribution_uncertain": True, "boundary_zone_ids": "gistda-50k-0009"},
        {
            "reserve_area_fraction": 1.0,
            "park_area_fraction": 1.0,
            "requires_legal_verification": True,
        },
    ],
)
def test_context_never_changes_hazard_interpretation(ctx):
    for base in (cell(), cell(landslide_class5_fraction=0.5), cell(landslide_assessed_fraction=0)):
        a = run(base)
        b = run(base | ctx)
        pd.testing.assert_frame_equal(a, b)


def test_interpretation_inputs_exclude_context_columns():
    from hearthmap.hazard import INTERPRETATION_INPUTS

    assert not set(INTERPRETATION_INPUTS) & set(CONTEXT_COLUMNS)


def test_boundary_uncertainty_layer_remains_review_only():
    grid = generate_grid(synthetic.aligned_square(1000), GridSpec(cell_size_m=500, crs=UTM))
    mask = mark_review_only(grid.iloc[:1], purpose="boundary uncertainty")
    with pytest.raises(ReviewLayerError):
        categorical_cell_fractions(grid, mask.assign(k=1), class_field="k", classes=[1], prefix="x")


# ======================================================== experimental exclusions


def test_experimental_candidates_are_flagged_and_not_eligibility():
    df = pd.DataFrame([cell(landslide_class5_fraction=0.8, slope_p90_deg=50.0)] * 2)
    df["flood_freq_ge3_area_fraction"] = [0.0, 0.6]
    df["evidence_completeness"] = [1.0, 0.5]
    ex = experimental_candidates(df, CFG)
    assert ex["experimental"].all() and not ex["affects_eligibility"].any()
    assert not ex["feeds_scoring"].any()
    assert ex["SEVERE_LANDSLIDE_EVIDENCE@0.75"].all()
    assert list(ex["STRONG_RECURRENT_FLOOD_EVIDENCE@0.5"]) == [False, True]
    assert list(ex["INSUFFICIENT_HAZARD_DATA@<0.67"]) == [False, True]


def test_experimental_candidates_cannot_enter_scoring(make_scoring_config):
    with pytest.raises(ValidationError, match="experimental"):
        HardConstraintResult(
            constraint_id="flood",
            outcome=ConstraintOutcome.UNKNOWN,
            reason="r",
            source_ids=["experimental:SEVERE_LANDSLIDE_EVIDENCE"],
        )
    with pytest.raises(ValidationError, match="experimental"):
        ComponentScore(dimension_id="a", value=10, source_ids=["experimental:x"])
    # and computing candidates leaves an assessment untouched
    model = ScoringModel(make_scoring_config())
    before = model.assess("u", [], [ComponentScore(dimension_id=d, value=50) for d in "abc"])
    experimental_candidates(
        pd.DataFrame([cell(landslide_class5_fraction=1.0)]).assign(evidence_completeness=1.0), CFG
    )
    after = model.assess("u", [], [ComponentScore(dimension_id=d, value=50) for d in "abc"])
    assert before == after and before.status is EligibilityStatus.UNRESOLVED


# ======================================================== sensitivity


def test_threshold_sensitivity_accounting():
    v = pd.Series([0.0, 0.1, 0.3, 0.6, np.nan])
    area = pd.Series([0.25, 0.25, 0.25, 0.1, 0.25])
    prov = pd.Series(["A", "A", "B", "B", "B"])
    t = threshold_sensitivity(
        v, [0.1, 0.5], area_km2=area, groups={"A": prov == "A", "B": prov == "B"}
    )
    aoi = t[t["scope"] == "AOI"].set_index("threshold")
    assert aoi.loc[">= 0.1", "cells"] == 3 and aoi.loc[">= 0.5", "cells"] == 1
    assert aoi.loc[">= 0.1", "area_km2"] == pytest.approx(0.6)
    assert aoi.loc[">= 0.1", "unknown_cells"] == 1  # NaN is never silently 'affected'
    b = t[t["scope"] == "B"].set_index("threshold")
    assert b.loc[">= 0.1", "cells"] == 2
    assert b.loc[">= 0.1", "share_of_area"] == pytest.approx(0.35 / 0.6)
    # monotone: stricter threshold never affects more cells
    assert (aoi["cells"].diff().dropna() <= 0).all()


def test_threshold_sensitivity_below_mode():
    v = pd.Series([1.0, 0.5, 0.2])
    t = threshold_sensitivity(v, [0.67], area_km2=pd.Series([1.0, 1.0, 1.0]), groups={}, below=True)
    assert t.iloc[0]["cells"] == 2


# ======================================================== landslide class fractions


def test_landslide_class_fractions_preserve_publisher_codes_and_use_area():
    grid = generate_grid(synthetic.aligned_square(500), GridSpec(cell_size_m=500, crs=UTM))
    polys = gpd.GeoDataFrame(
        {"gridcode": [2, 5]},
        geometry=[box(X0, Y0, X0 + 350, Y0 + 500), box(X0 + 350, Y0, X0 + 500, Y0 + 500)],
        crs=UTM,
    )
    out = categorical_cell_fractions(
        grid, polys, class_field="gridcode", classes=[1, 2, 3, 4, 5], prefix="ls"
    ).iloc[0]
    assert out["ls_class2_fraction"] == pytest.approx(0.7)
    assert out["ls_class5_fraction"] == pytest.approx(0.3)  # off-centroid strip still counted
    assert out["ls_class1_fraction"] == 0
    assert out["ls_max_class"] == 5 and out["ls_dominant_class"] == 2
    assert out["ls_assessed_fraction"] == pytest.approx(1.0)
    assert out["ls_class_distribution"] == "2:0.700;5:0.300"


def test_landslide_unassessed_area_stays_unassessed():
    grid = generate_grid(synthetic.aligned_square(500), GridSpec(cell_size_m=500, crs=UTM))
    polys = gpd.GeoDataFrame({"gridcode": [3]}, geometry=[box(X0, Y0, X0 + 100, Y0 + 500)], crs=UTM)
    out = categorical_cell_fractions(
        grid, polys, class_field="gridcode", classes=[1, 2, 3, 4, 5], prefix="ls"
    ).iloc[0]
    assert out["ls_assessed_fraction"] == pytest.approx(0.2)  # 80% NOT assessed, not 'class 1'
    assert out["ls_class1_fraction"] == 0


def test_edge_touching_class_polygon_is_not_counted():
    grid = generate_grid(synthetic.aligned_square(500), GridSpec(cell_size_m=500, crs=UTM))
    polys = gpd.GeoDataFrame(
        {"gridcode": [5]}, geometry=[box(X0 + 500, Y0, X0 + 900, Y0 + 500)], crs=UTM
    )
    out = categorical_cell_fractions(
        grid, polys, class_field="gridcode", classes=[5], prefix="ls"
    ).iloc[0]
    assert out["ls_class5_fraction"] == 0 and np.isnan(out["ls_max_class"])
