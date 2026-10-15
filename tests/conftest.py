from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from hearthmap.config import ScoringConfig, load_project_config

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"
REGISTRY_PATH = REPO_ROOT / "docs" / "research" / "data-source-registry.yaml"


@pytest.fixture(scope="session")
def project_config():
    return load_project_config(CONFIG_DIR)


@pytest.fixture
def raw_scoring() -> dict[str, Any]:
    """Mutable copy of the repository scoring.yaml contents."""
    return copy.deepcopy(yaml.safe_load((CONFIG_DIR / "scoring.yaml").read_text(encoding="utf-8")))


@pytest.fixture
def make_scoring_config():
    """Small, explicit scoring config for arithmetic tests (independent of repo YAML)."""

    def _make(
        weights: dict[str, float] | None = None,
        constraints: list[str] | None = None,
        **policies: Any,
    ) -> ScoringConfig:
        weights = weights if weights is not None else {"a": 50, "b": 30, "c": 20}
        constraints = constraints if constraints is not None else ["flood", "slope"]
        return ScoringConfig.model_validate(
            {
                "schema_version": 1,
                "model_id": "test-model",
                "model_version": "0",
                "status": "PROVISIONAL",
                "dimensions": [
                    {"id": k, "label": k.upper(), "weight": v} for k, v in weights.items()
                ],
                "policies": policies,
                "hard_constraints": [
                    {"id": c, "label": c, "description": f"test constraint {c}"}
                    for c in constraints
                ],
            }
        )

    return _make
