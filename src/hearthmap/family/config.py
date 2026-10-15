"""Loader for config/family-infrastructure.yaml (plain dict wrapper with a few guards)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("config/family-infrastructure.yaml")
REFERENCE_PATH = Path("config/healthcare-reference-levels.yaml")


class FamilyConfig(dict):
    """The parsed configuration; behaves as a dict."""

    @property
    def speeds(self) -> dict[str, float]:
        return {k: float(v) for k, v in self["travel_time"]["speeds_kmh"].items()}

    @property
    def bands(self) -> list[int]:
        return [int(b) for b in self["travel_time"]["bands_min"]]


def load_config(path: Path = CONFIG_PATH) -> FamilyConfig:
    cfg: dict[str, Any] = yaml.safe_load(Path(path).read_text("utf-8"))
    if cfg["travel_time"]["name"] != "BASELINE_DRIVE_TIME":
        raise ValueError(
            "travel time must be named BASELINE_DRIVE_TIME (it is not an actual commute time)"
        )
    return FamilyConfig(cfg)


def load_reference_levels(path: Path = REFERENCE_PATH) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(Path(path).read_text("utf-8")) or {}
    out: dict[str, dict[str, Any]] = {}
    for e in data.get("reference_list") or []:
        if not (e.get("facility_official_id") and e.get("level") and e.get("source")):
            raise ValueError(f"reference level entries need id, level and source: {e}")
        out[str(e["facility_official_id"])] = e
    return out
