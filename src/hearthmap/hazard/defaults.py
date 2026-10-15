"""Selected provisional regional-screening defaults (M1D record).

The project owner selected the hydrogeomorphic profile and the flood-fusion policy that
serve as the current regional-screening defaults. They stay PROVISIONAL and are never
parcel-level truth until the remaining policy visual QA gates are PASSED. The record
carries a fingerprint of the selected thresholds so that any later change is visible.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml
from hearthmap.hazard.flood_fusion import FusionConfig, load_fusion_config
from hearthmap.hazard.policy import HazardPolicyConfig, load_policy_config
from hearthmap.qa.signoff import load_human_qa


class RegionalDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    status: Literal["PROVISIONAL"]
    decision_date: str
    decided_by: str
    hydrogeomorphic_profile: str
    flood_fusion_policy: str
    selected_for_provisional_screening: Literal[True]
    production_truth: Literal[False]
    provisional_until_visual_qa_passed: list[str]
    threshold_fingerprint: dict[str, str]
    rationale: dict[str, list[str]]
    not_claimed: list[str]
    retained_sensitivity_references: list[str]

    @model_validator(mode="after")
    def _guards(self) -> RegionalDefaults:
        text = json.dumps(self.rationale).lower()
        if "optimal" in text and "not" not in text:
            raise ValueError("BALANCED must not be described as scientifically optimal")
        return self


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def threshold_fingerprint(
    policy: HazardPolicyConfig,
    fusion: FusionConfig,
    defaults: RegionalDefaults | None = None,
    *,
    profile: str | None = None,
    flood: str | None = None,
) -> dict[str, str]:
    profile = profile or (defaults.hydrogeomorphic_profile if defaults else None)
    flood = flood or (defaults.flood_fusion_policy if defaults else None)
    prof = policy.profiles[profile].model_dump()
    rules = [r.model_dump() for r in fusion.rules_for(flood)]
    sha = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
    return {
        "hydrogeomorphic_profile_sha256": sha(_canonical(prof)),
        "flood_fusion_rules_sha256": sha(_canonical(rules)),
        "presence_min_fraction": str(fusion.presence_min_fraction),
    }


def load_regional_defaults(
    path: Path | str = "config/regional-screening-defaults.yaml",
) -> RegionalDefaults:
    try:
        d = RegionalDefaults.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid regional defaults {path}:\n{exc}") from exc
    policy, fusion = load_policy_config(), load_fusion_config()
    if d.hydrogeomorphic_profile not in policy.profiles:
        raise ConfigError(f"unknown hydrogeomorphic profile {d.hydrogeomorphic_profile}")
    if d.flood_fusion_policy not in fusion.candidates:
        raise ConfigError(f"unknown flood fusion policy {d.flood_fusion_policy}")
    qa = load_human_qa()
    for gate in d.provisional_until_visual_qa_passed:
        if gate not in qa.gates:
            raise ConfigError(f"unknown QA gate {gate}")
    return d


__all__ = ["RegionalDefaults", "load_regional_defaults", "threshold_fingerprint"]
