from __future__ import annotations

import math
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hearthmap.config import (
    ConfigError,
    CRSConfig,
    GridConfig,
    RegionsConfig,
    ScoringConfig,
    load_scoring,
)

# ------------------------------------------------------------ repository config


def test_repository_config_loads(project_config):
    assert [r.id for r in project_config.regions.enabled_regions] == [
        "chiang-rai",
        "chiang-mai",
        "phayao",
    ]
    assert project_config.spatial.crs.canonical == "EPSG:32647"
    assert project_config.spatial.grid.cell_size_m == 500
    assert project_config.scoring.status == "PROVISIONAL"


def test_repository_weights_match_provisional_model(project_config):
    weights = {d.id: d.weight for d in project_config.scoring.dimensions}
    assert weights == {
        "hazard_resilience": 25,
        "family_services": 20,
        "infrastructure": 15,
        "livability": 15,
        "value_potential": 15,
        "accessibility": 10,
    }
    assert math.isclose(sum(project_config.scoring.normalized_weights().values()), 1.0)


def test_repository_hard_constraints_have_no_invented_rules(project_config):
    # M0 must not pretend thresholds exist.
    assert project_config.scoring.hard_constraints
    assert all(not c.rule_defined for c in project_config.scoring.hard_constraints)


def test_repository_region_codes_are_not_claimed_verified(project_config):
    assert all(r.province_code_status != "VERIFIED" for r in project_config.regions.regions)


# ------------------------------------------------------------ weights


def test_weights_must_sum_to_declared_total(raw_scoring):
    raw_scoring["dimensions"][0]["weight"] = 26  # total 101
    with pytest.raises(ValidationError, match="sum to 101"):
        ScoringConfig.model_validate(raw_scoring)


def test_weights_without_declared_total_are_normalised(raw_scoring):
    raw_scoring["weights_total"] = None
    for d in raw_scoring["dimensions"]:
        d["weight"] = 1
    cfg = ScoringConfig.model_validate(raw_scoring)
    assert all(math.isclose(w, 1 / 6) for w in cfg.normalized_weights().values())


def test_negative_weight_rejected(raw_scoring):
    raw_scoring["weights_total"] = None
    raw_scoring["dimensions"][0]["weight"] = -5
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(raw_scoring)


def test_all_zero_weights_rejected(raw_scoring):
    raw_scoring["weights_total"] = None
    for d in raw_scoring["dimensions"]:
        d["weight"] = 0
    with pytest.raises(ValidationError, match="positive weight"):
        ScoringConfig.model_validate(raw_scoring)


def test_non_finite_weight_rejected(raw_scoring):
    raw_scoring["weights_total"] = None
    raw_scoring["dimensions"][0]["weight"] = float("inf")
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(raw_scoring)


def test_duplicate_dimension_rejected(raw_scoring):
    raw_scoring["weights_total"] = None
    raw_scoring["dimensions"].append(dict(raw_scoring["dimensions"][0]))
    with pytest.raises(ValidationError, match="duplicate dimension"):
        ScoringConfig.model_validate(raw_scoring)


def test_duplicate_constraint_rejected(raw_scoring):
    raw_scoring["hard_constraints"].append(dict(raw_scoring["hard_constraints"][0]))
    with pytest.raises(ValidationError, match="duplicate hard-constraint"):
        ScoringConfig.model_validate(raw_scoring)


def test_unknown_keys_rejected(raw_scoring):
    raw_scoring["dimensions"][0]["wieght"] = 3  # typo must not be silently ignored
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(raw_scoring)


def test_unknown_policy_rejected(raw_scoring):
    raw_scoring["policies"]["missing_component"] = "assume_average"
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate(raw_scoring)


# ------------------------------------------------------------ CRS / grid


def _crs(**overrides):
    base = {"canonical": "EPSG:32647", "interchange": "EPSG:4326", "display": "EPSG:3857"}
    return CRSConfig.model_validate(base | overrides)


def test_canonical_crs_must_be_metric_projected():
    with pytest.raises(ValidationError, match="projected CRS in metres"):
        _crs(canonical="EPSG:4326")


def test_canonical_crs_must_not_be_web_mercator():
    with pytest.raises(ValidationError, match="Web Mercator"):
        _crs(canonical="EPSG:3857")


def test_invalid_crs_string_rejected():
    with pytest.raises(ValidationError, match="not a recognised CRS"):
        _crs(display="EPSG:999999999")


def test_interchange_must_be_geographic():
    with pytest.raises(ValidationError, match="geographic"):
        _crs(interchange="EPSG:32647")


@pytest.mark.parametrize("size", [0, -500, 1e9])
def test_grid_cell_size_bounds(size):
    with pytest.raises(ValidationError):
        GridConfig(cell_size_m=size)


def test_grid_selection_mode_validated():
    with pytest.raises(ValidationError):
        GridConfig(cell_size_m=500, selection="nearest")


# ------------------------------------------------------------ regions


def test_regions_require_one_enabled(project_config):
    raw = project_config.regions.model_dump(mode="json")
    for r in raw["regions"]:
        r["enabled"] = False
    with pytest.raises(ValidationError, match="at least one region"):
        RegionsConfig.model_validate(raw)


def test_regions_reject_inverted_envelope(project_config):
    raw = project_config.regions.model_dump(mode="json")
    raw["study_area"]["sanity_envelope"]["bounds"] = [101.5, 16.5, 97.0, 21.0]
    with pytest.raises(ValidationError, match="min < max"):
        RegionsConfig.model_validate(raw)


# ------------------------------------------------------------ loader errors


def test_loader_wraps_validation_errors(tmp_path: Path, raw_scoring):
    raw_scoring["dimensions"] = []
    path = tmp_path / "scoring.yaml"
    path.write_text(yaml.safe_dump(raw_scoring), encoding="utf-8")
    with pytest.raises(ConfigError, match=r"scoring\.yaml"):
        load_scoring(path)


def test_loader_missing_file(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_scoring(tmp_path / "nope.yaml")


def test_loader_non_mapping(tmp_path: Path):
    path = tmp_path / "scoring.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_scoring(path)
