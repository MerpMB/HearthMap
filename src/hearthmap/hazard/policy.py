"""Hydrogeomorphic Hazard Screening policy v0.1 (M1C) - regional screening only.

Decision ladder (``regional_search_status``):

    NO_MAJOR_CONCERN_DETECTED  within the implemented datasets/thresholds, no major
                               hydrogeomorphic concern was detected (NOT "safe")
    REQUIRES_VERIFICATION      a hazard concern and/or a data-quality issue to verify
    STRONG_REGIONAL_CONCERN    strong evidence for at least one hazard
    REGIONAL_DEPRIORITIZE      spend search effort elsewhere unless there is a
                               compelling reason (NOT unsafe / unbuildable)
    UNRESOLVED                 evidence too incomplete for a screening statement

Exact rule (per profile, all thresholds in config/hazard-policy.yaml):

1. Each hazard gets a concern level NONE < VERIFY < STRONG < DEPRIORITIZE:
   flood      recurrent-flood fraction = share of the cell observed flooded in >=
              min_years_flooded of the primary record's years (source, period and
              record length in source_requirements.flood; checked against the
              evidence). DEPRIORITIZE if >= deprioritize_min_fraction,
              STRONG if >= strong_min_fraction, VERIFY if any observed flooding
              >= verify_min_fraction or within verify_distance_m.
   landslide  DEPRIORITIZE if Very High >= very_high_deprioritize or High+Very High
              >= high_plus_deprioritize; STRONG likewise with *_strong; VERIFY if
              High+ >= verify_high_plus or Medium+ >= verify_medium_plus. Mapped scars
              (within scar_within_m) can only RAISE: NONE -> VERIFY, and
              STRONG -> DEPRIORITIZE if scar_escalates_strong.
   terrain    VERIFY if DSM slope p90 >= verify_slope_p90_deg. Terrain is capped at
              VERIFY: it never produces STRONG or DEPRIORITIZE on its own.
2. Corroboration (categorical, dependency UNKNOWN): landslide >= STRONG and slope p90
   >= corroborate_slope_p90_deg adds LANDSLIDE_TERRAIN_CORROBORATED and, only if
   corroboration_escalates_landslide, raises landslide STRONG -> DEPRIORITIZE.
3. Multi-hazard: base = max level (never an average). If flood and landslide are
   both >= STRONG and escalate_flood_and_landslide_strong: DEPRIORITIZE with
   MULTIPLE_STRONG_HAZARD_SIGNALS.
4. Incompleteness: landslide not evaluated (assessed < min) or terrain support < min
   makes the cell UNRESOLVED unless base >= VERIFY - severe/positive evidence stays
   visible and the unresolved reasons are still recorded. UNRESOLVED_CRITICAL when
   a core source has essentially no coverage, otherwise UNRESOLVED_PARTIAL.
5. Mapping: DEPRIORITIZE -> REGIONAL_DEPRIORITIZE, STRONG -> STRONG_REGIONAL_CONCERN,
   VERIFY -> REQUIRES_VERIFICATION, NONE -> NO_MAJOR_CONCERN_DETECTED.

The policy reads only ``POLICY_INPUTS``; forest/legal, boundary and waterway
context can never change an outcome. It never touches ``eligible``.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml


class RegionalSearchStatus(StrEnum):
    NO_MAJOR_CONCERN_DETECTED = "NO_MAJOR_CONCERN_DETECTED"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"
    STRONG_REGIONAL_CONCERN = "STRONG_REGIONAL_CONCERN"
    REGIONAL_DEPRIORITIZE = "REGIONAL_DEPRIORITIZE"
    UNRESOLVED = "UNRESOLVED"


FORBIDDEN_OUTCOME_WORDS = ("SAFE", "BUILDABLE", "FINAL_REJECT", "LEGAL_EXCLUSION", "LOW_RISK")


class Level(IntEnum):
    NONE = 0
    VERIFY = 1
    STRONG = 2
    DEPRIORITIZE = 3


class LandslideAssessment(StrEnum):
    ASSESSED = "ASSESSED"
    PARTIALLY_ASSESSED = "PARTIALLY_ASSESSED"
    NOT_ASSESSED = "NOT_ASSESSED"  # outside DMR coverage - never "low susceptibility"


# What the ASSESSED hazards indicate, independent of data completeness.
_INTERPRETATION_FOR_LEVEL = {
    Level.NONE: "NO_MAJOR_CONCERN_IN_ASSESSED_HAZARDS",
    Level.VERIFY: "CONCERN_REQUIRING_VERIFICATION",
    Level.STRONG: "STRONG_CONCERN",
    Level.DEPRIORITIZE: "DEPRIORITIZATION_LEVEL_CONCERN",
}

_STATUS_FOR_LEVEL = {
    Level.NONE: RegionalSearchStatus.NO_MAJOR_CONCERN_DETECTED,
    Level.VERIFY: RegionalSearchStatus.REQUIRES_VERIFICATION,
    Level.STRONG: RegionalSearchStatus.STRONG_REGIONAL_CONCERN,
    Level.DEPRIORITIZE: RegionalSearchStatus.REGIONAL_DEPRIORITIZE,
}

POLICY_INPUTS = (
    "flood_area_fraction",
    "flood_years_ge2_area_fraction",
    "flood_years_ge3_area_fraction",
    "flood_years_ge4_area_fraction",
    "flood_years_ge5_area_fraction",
    "flood_distance_m",
    "landslide_assessed_fraction",
    "landslide_class3_fraction",
    "landslide_class4_fraction",
    "landslide_class5_fraction",
    "landslide_inventory_points",
    "landslide_inventory_distance_m",
    "terrain_support_px",
    "slope_p90_deg",
)


# ---------------------------------------------------------------- config


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FloodRule(_M):
    # observed flooded in >= this many years of FloodSourceRequirement.record_years
    min_years_flooded: Literal[2, 3, 4, 5]
    strong_min_fraction: float = Field(gt=0, le=1)
    deprioritize_min_fraction: float = Field(gt=0, le=1)
    verify_min_fraction: float = Field(gt=0, le=1)
    verify_distance_m: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> FloodRule:
        if (
            not self.verify_min_fraction
            <= self.strong_min_fraction
            <= self.deprioritize_min_fraction
        ):
            raise ValueError("flood thresholds must satisfy verify <= strong <= deprioritize")
        return self


class LandslideRule(_M):
    very_high_strong: float = Field(gt=0, le=1)
    very_high_deprioritize: float = Field(gt=0, le=1)
    high_plus_strong: float = Field(gt=0, le=1)
    high_plus_deprioritize: float = Field(gt=0, le=1)
    verify_high_plus: float = Field(gt=0, le=1)
    verify_medium_plus: float = Field(gt=0, le=1)
    scar_within_m: float = Field(ge=0)
    scar_escalates_strong: bool

    @model_validator(mode="after")
    def _ordered(self) -> LandslideRule:
        if not (
            self.very_high_strong <= self.very_high_deprioritize
            and self.high_plus_strong <= self.high_plus_deprioritize
        ):
            raise ValueError("landslide thresholds must satisfy strong <= deprioritize")
        return self


class TerrainRule(_M):
    verify_slope_p90_deg: float = Field(gt=0, lt=90)
    corroborate_slope_p90_deg: float = Field(gt=0, lt=90)
    corroboration_escalates_landslide: bool


class MultiRule(_M):
    escalate_flood_and_landslide_strong: bool


class Profile(_M):
    flood: FloodRule
    landslide: LandslideRule
    terrain: TerrainRule
    multi_hazard: MultiRule


class Unresolved(_M):
    landslide_min_assessed_fraction: float = Field(gt=0, le=1)
    landslide_critical_assessed_fraction: float = Field(ge=0, le=1)
    terrain_min_support_px: float = Field(gt=0)
    terrain_low_support_px: float = Field(gt=0)


class FloodSourceRequirement(_M):
    """The flood record the thresholds refer to - stated, never implied."""

    source_id: str
    evidence_role: Literal["PRIMARY_HISTORICAL_FLOOD_EVIDENCE"]
    period: str
    record_years: int = Field(ge=1)
    source_native_metric: str
    derived_threshold_semantics: str
    contemporary_complete: Literal[False]
    corroborating_source: dict


class PolicyGates(_M):
    m1a1_human_visual_signoff: Literal["PENDING", "PASSED"]
    m1b_human_visual_signoff: Literal["PENDING", "PASSED"]


class HazardPolicyConfig(_M):
    schema_version: Literal[1]
    policy_id: str
    policy_version: str
    status: Literal["PROVISIONAL", "ACCEPTED"]
    scope: Literal["HYDROGEOMORPHIC"]
    default_profile: str | None
    gates: PolicyGates
    source_requirements: dict
    dependencies: dict
    prohibited_evidence_columns: list[str]
    prohibited_source_prefixes: list[str]
    unresolved: Unresolved
    profiles: dict[str, Profile]
    reason_codes: dict[str, str]

    @model_validator(mode="after")
    def _guards(self) -> HazardPolicyConfig:
        overlap = set(self.prohibited_evidence_columns) & set(POLICY_INPUTS)
        if overlap:
            raise ValueError(f"policy inputs include prohibited evidence: {sorted(overlap)}")
        gates_open = (
            self.gates.m1a1_human_visual_signoff == "PENDING"
            or self.gates.m1b_human_visual_signoff == "PENDING"
        )
        if gates_open and (self.status != "PROVISIONAL" or self.default_profile is not None):
            raise ValueError(
                "while a human visual gate is PENDING the policy must stay "
                "PROVISIONAL with no default profile"
            )
        if self.default_profile is not None and self.default_profile not in self.profiles:
            raise ValueError(f"unknown default_profile {self.default_profile}")
        if self.source_requirements.get("terrain", {}).get("may_deprioritize_alone") is not False:
            raise ValueError("DSM terrain may never deprioritize alone in v0.1")
        fl = self.flood_source  # validates the flood requirement block
        for name, prof in self.profiles.items():
            if prof.flood.min_years_flooded > fl.record_years:
                raise ValueError(f"{name}: min_years_flooded exceeds the flood record length")
        for word in FORBIDDEN_OUTCOME_WORDS:
            for code in self.reason_codes:
                if word in code.split("_") or code.startswith(word):
                    raise ValueError(f"reason code {code} uses forbidden wording {word}")
        return self

    @property
    def flood_source(self) -> FloodSourceRequirement:
        return FloodSourceRequirement.model_validate(self.source_requirements.get("flood", {}))


def check_flood_evidence(evidence: pd.DataFrame, cfg: HazardPolicyConfig) -> None:
    """The evidence must come from the flood record the thresholds were written for."""
    fl = cfg.flood_source
    expected = {
        "flood_source_id": fl.source_id,
        "flood_evidence_period": fl.period,
        "flood_record_years": fl.record_years,
    }
    for col, want in expected.items():
        if col not in evidence.columns:
            raise KeyError(f"evidence lacks flood semantic column {col}")
        got = set(pd.unique(evidence[col]))
        if got != {want}:
            raise ValueError(
                f"{col} = {sorted(map(str, got))} but the policy expects {want!r}; "
                "refusing to reuse flood thresholds with a different meaning"
            )


def load_policy_config(path: Path | str = "config/hazard-policy.yaml") -> HazardPolicyConfig:
    try:
        return HazardPolicyConfig.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid hazard policy {path}:\n{exc}") from exc


# ---------------------------------------------------------------- engine


def _codes_append(codes: list[list[str]], mask: np.ndarray, code: str) -> None:
    for i in np.flatnonzero(mask):
        codes[i].append(code)


def apply_policy(
    evidence: pd.DataFrame, cfg: HazardPolicyConfig, profile_name: str
) -> pd.DataFrame:
    """Evaluate one profile. Returns policy columns indexed like ``evidence``."""
    missing = [c for c in POLICY_INPUTS if c not in evidence.columns]
    if missing:
        raise KeyError(f"missing policy input columns: {missing}")
    if profile_name not in cfg.profiles:
        raise KeyError(f"unknown profile {profile_name}")
    check_flood_evidence(evidence, cfg)
    p = cfg.profiles[profile_name]
    u = cfg.unresolved
    d = evidence.loc[:, list(POLICY_INPUTS)].astype(float)  # context columns are never read
    n = len(d)
    hazard_codes: list[list[str]] = [[] for _ in range(n)]
    data_codes: list[list[str]] = [[] for _ in range(n)]
    unresolved_codes: list[list[str]] = [[] for _ in range(n)]
    info_codes: list[list[str]] = [[] for _ in range(n)]

    # ---- flood
    fr = d[f"flood_years_ge{p.flood.min_years_flooded}_area_fraction"].fillna(0).to_numpy()
    fa = d["flood_area_fraction"].fillna(0).to_numpy()
    fd = d["flood_distance_m"].to_numpy()
    flood = np.full(n, Level.NONE, dtype=int)
    m_dep = fr >= p.flood.deprioritize_min_fraction
    m_str = ~m_dep & (fr >= p.flood.strong_min_fraction)
    m_ver = (
        (flood == Level.NONE)
        & ~m_dep
        & ~m_str
        & ((fa >= p.flood.verify_min_fraction) | (fd <= p.flood.verify_distance_m))
    )
    flood[m_dep], flood[m_str], flood[m_ver] = Level.DEPRIORITIZE, Level.STRONG, Level.VERIFY
    _codes_append(hazard_codes, m_dep, "RECURRENT_FLOOD_SUBSTANTIAL_COVERAGE")
    _codes_append(hazard_codes, m_str, "STRONG_RECURRENT_FLOOD_EVIDENCE")
    _codes_append(hazard_codes, m_ver, "OBSERVED_FLOOD_EVIDENCE")
    _codes_append(info_codes, flood == Level.NONE, "NO_OBSERVED_FLOOD_IN_RECORD")

    # ---- landslide
    c3 = d["landslide_class3_fraction"].fillna(0).to_numpy()
    c4 = d["landslide_class4_fraction"].fillna(0).to_numpy()
    c5 = d["landslide_class5_fraction"].fillna(0).to_numpy()
    hp, mp = c4 + c5, c3 + c4 + c5
    assessed = d["landslide_assessed_fraction"].fillna(0).to_numpy()
    pts = d["landslide_inventory_points"].fillna(0).to_numpy()
    sdist = d["landslide_inventory_distance_m"].to_numpy()
    scar = (pts > 0) | (sdist <= p.landslide.scar_within_m)
    lr = p.landslide
    ls = np.full(n, Level.NONE, dtype=int)
    vh_dep, hp_dep = c5 >= lr.very_high_deprioritize, hp >= lr.high_plus_deprioritize
    vh_str, hp_str = c5 >= lr.very_high_strong, hp >= lr.high_plus_strong
    dep = vh_dep | hp_dep
    strong = ~dep & (vh_str | hp_str)
    ver = ~dep & ~strong & ((hp >= lr.verify_high_plus) | (mp >= lr.verify_medium_plus))
    ls[dep], ls[strong], ls[ver] = Level.DEPRIORITIZE, Level.STRONG, Level.VERIFY
    _codes_append(hazard_codes, vh_dep, "VERY_HIGH_LANDSLIDE_SUSCEPTIBILITY_DOMINANT")
    _codes_append(hazard_codes, hp_dep & ~vh_dep, "HIGH_VERY_HIGH_SUSCEPTIBILITY_DOMINANT")
    _codes_append(hazard_codes, strong, "STRONG_LANDSLIDE_SUSCEPTIBILITY_EVIDENCE")
    _codes_append(hazard_codes, ver, "LANDSLIDE_SUSCEPTIBILITY_BELOW_DEPRIORITIZATION")
    # scars only raise concern, never lower it
    scar_up = scar & (ls == Level.NONE)
    ls[scar_up] = Level.VERIFY
    _codes_append(hazard_codes, scar, "HISTORICAL_LANDSLIDE_SCAR_NEARBY")
    scar_esc = scar & (ls == Level.STRONG) & lr.scar_escalates_strong
    ls[scar_esc] = Level.DEPRIORITIZE
    _codes_append(
        hazard_codes, scar & (ls >= Level.STRONG), "SCAR_CORROBORATES_LANDSLIDE_SUSCEPTIBILITY"
    )

    # ---- terrain (DSM proxy; capped at VERIFY)
    sup = d["terrain_support_px"].fillna(0).to_numpy()
    p90 = d["slope_p90_deg"].to_numpy()
    with np.errstate(invalid="ignore"):
        steep = np.nan_to_num(p90, nan=-1) >= p.terrain.verify_slope_p90_deg
        corrob = np.nan_to_num(p90, nan=-1) >= p.terrain.corroborate_slope_p90_deg
    terrain = np.where(steep, Level.VERIFY, Level.NONE).astype(int)
    _codes_append(hazard_codes, steep, "TERRAIN_STEEPNESS_PROXY_HIGH")
    corr = corrob & (ls >= Level.STRONG)
    _codes_append(hazard_codes, corr, "LANDSLIDE_TERRAIN_CORROBORATED")
    if p.terrain.corroboration_escalates_landslide:
        ls[corr & (ls == Level.STRONG)] = Level.DEPRIORITIZE

    # ---- data quality and completeness
    ls_unres = assessed < u.landslide_min_assessed_fraction
    ls_critical = assessed < u.landslide_critical_assessed_fraction
    ter_unres = sup < u.terrain_min_support_px
    low_sup = (sup >= u.terrain_min_support_px) & (sup < u.terrain_low_support_px)
    partial = (assessed >= u.landslide_min_assessed_fraction) & (assessed < 1 - 1e-9)
    _codes_append(unresolved_codes, ls_unres, "LANDSLIDE_NOT_ASSESSED")
    _codes_append(unresolved_codes, ter_unres, "TERRAIN_SUPPORT_INSUFFICIENT")
    _codes_append(data_codes, low_sup, "LOW_TERRAIN_SUPPORT")
    _codes_append(data_codes, partial, "PARTIAL_LANDSLIDE_COVERAGE")

    # ---- combination (categorical; never averaged)
    base = np.maximum.reduce([flood, ls, terrain])
    multi = (
        (flood >= Level.STRONG)
        & (ls >= Level.STRONG)
        & p.multi_hazard.escalate_flood_and_landslide_strong
    )
    base = np.where(multi, Level.DEPRIORITIZE, base)
    _codes_append(hazard_codes, multi, "MULTIPLE_STRONG_HAZARD_SIGNALS")
    unresolved = ls_unres | ter_unres
    status = np.array([_STATUS_FOR_LEVEL[Level(int(b))].value for b in base], dtype=object)
    no_info = unresolved & (base == Level.NONE)
    status[no_info] = RegionalSearchStatus.UNRESOLVED.value
    completeness = np.where(
        ~unresolved,
        "COMPLETE",
        np.where(ls_critical | ter_unres, "UNRESOLVED_CRITICAL", "UNRESOLVED_PARTIAL"),
    )

    # M1C.2: keep three things apart - what the ASSESSED hazards say, how complete
    # the data is, and whether DMR assessed landslide susceptibility at all. A cell
    # outside DMR coverage is NOT_ASSESSED for landslide (never "low"), while its
    # flood/terrain interpretation stays available.
    ls_status = np.where(
        ls_unres,
        LandslideAssessment.NOT_ASSESSED.value,
        np.where(
            partial,
            LandslideAssessment.PARTIALLY_ASSESSED.value,
            LandslideAssessment.ASSESSED.value,
        ),
    )
    interp = np.array([_INTERPRETATION_FOR_LEVEL[Level(int(b))] for b in base], dtype=object)
    assessed = [
        "|".join(h for h, ok in (("flood", True), ("landslide", not a), ("terrain", not t)) if ok)
        for a, t in zip(ls_unres, ter_unres, strict=True)
    ]

    out = pd.DataFrame(index=evidence.index)
    out["regional_search_status"] = status
    out["hazard_interpretation"] = interp
    out["assessed_hazards"] = assessed
    out["data_completeness"] = completeness
    out["landslide_assessment_status"] = ls_status
    out["flood_policy_level"] = [Level(int(v)).name for v in flood]
    out["landslide_policy_level"] = np.where(
        ls_unres & (ls == Level.NONE),
        "NOT_ASSESSED",
        [Level(int(v)).name for v in ls],
    )
    out["terrain_policy_level"] = [Level(int(v)).name for v in terrain]
    out["hazard_verification_required"] = base >= Level.VERIFY
    out["data_verification_required"] = low_sup | partial | unresolved
    out["evidence_completeness_class"] = completeness
    out["hazard_reason_codes"] = ["|".join(c) for c in hazard_codes]
    out["data_reason_codes"] = ["|".join(c) for c in data_codes]
    out["unresolved_reasons"] = ["|".join(c) for c in unresolved_codes]
    out["missing_or_incomplete_sources"] = [
        "|".join(
            s for s, f in (("landslide-susceptibility-dmr", a), ("dem-copernicus-glo30", b)) if f
        )
        for a, b in zip(ls_unres, ter_unres, strict=True)
    ]
    out["informational_codes"] = ["|".join(c) for c in info_codes]
    out["policy_profile"] = profile_name
    out["policy_version"] = cfg.policy_version
    out["policy_status"] = cfg.status
    out["policy_scope"] = cfg.scope
    return out


# ---------------------------------------------------------------- explanation


_LANDSLIDE_LINE = {
    "NOT_ASSESSED": "Not assessed by DMR in this cell - this is missing evidence, NOT low "
    "landslide susceptibility; flood/terrain interpretation still applies",
    "PARTIALLY_ASSESSED": "DMR susceptibility covers only part of the cell",
    "ASSESSED": "DMR susceptibility assessed",
}

_THIS_DOES_NOT_MEAN = (
    "THIS DOES NOT MEAN\n- the parcel is unsafe or safe\n- construction is impossible or "
    "approved\n- no site survey is required\n- natural hazards other than flood/landslide/"
    "terrain (e.g. earthquakes, active faults, wildfire) were assessed"
)


def explain(cell_id: str, evidence: pd.Series, policy: pd.Series, cfg: HazardPolicyConfig) -> str:
    """Deterministic explanation built only from structured reason codes and values."""
    p = cfg.profiles[policy["policy_profile"]]
    fl = cfg.flood_source
    values = {
        k: (float(evidence[k]) if pd.notna(evidence.get(k)) else float("nan"))
        for k in POLICY_INPUTS
    }
    values |= {
        "flood_years": p.flood.min_years_flooded,
        "flood_record_years": fl.record_years,
        "flood_period": fl.period,
        "flood_recurrent_fraction": values[
            f"flood_years_ge{p.flood.min_years_flooded}_area_fraction"
        ],
        "landslide_high_plus_fraction": values["landslide_class4_fraction"]
        + values["landslide_class5_fraction"],
        "landslide_medium_plus_fraction": values["landslide_class3_fraction"]
        + values["landslide_class4_fraction"]
        + values["landslide_class5_fraction"],
        "landslide_inventory_points": int(values["landslide_inventory_points"])
        if values["landslide_inventory_points"] == values["landslide_inventory_points"]
        else 0,
    }

    def render(field: str) -> list[str]:
        codes = [c for c in str(policy[field]).split("|") if c]
        return [f"- {cfg.reason_codes[c].format(**values)}  [{c}]" for c in codes]

    flood_line = (
        f"No strong historical recurrence detected in the {fl.period} record "
        "(not evidence of no flood risk)"
        if policy["flood_policy_level"] in ("NONE", "VERIFY")
        else f"Strong historical recurrence in the {fl.period} record"
    )
    parts = [
        f"CELL: {cell_id}",
        f"PROFILE: {policy['policy_profile']} (policy {policy['policy_version']}, "
        f"{policy['policy_status']})",
        "",
        "HYDROGEOMORPHIC SCREENING",
        policy["regional_search_status"],
        f"evidence completeness: {policy['evidence_completeness_class']}",
        "",
        "WHY",
        *(
            render("hazard_reason_codes")
            or [
                "- no major hydrogeomorphic concern detected "
                "within implemented datasets and thresholds"
            ]
        ),
        "",
        "FLOOD",
        flood_line,
        "",
        "LANDSLIDE",
        _LANDSLIDE_LINE.get(
            policy.get("landslide_assessment_status", ""),
            "DMR susceptibility assessed",
        ),
    ]
    if policy["data_reason_codes"] or policy["unresolved_reasons"]:
        parts += ["", "DATA TO VERIFY", *render("data_reason_codes"), *render("unresolved_reasons")]
    parts += [
        "",
        "UNCERTAINTY",
        "- terrain from Copernicus GLO-30 is a DSM (canopy/buildings), not ground slope",
        "- DMR susceptibility methodology is not published; it is susceptibility, not "
        "probability of failure",
        f"- flood evidence is satellite-observed {fl.period} only ({fl.source_id})",
        "",
        _THIS_DOES_NOT_MEAN,
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------- spatial structure


def connected_components(cols: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """4-connected (edge-sharing) component labels for a set of grid cells.

    Union-find over (col, row). Labels are 0..k-1 ordered by first appearance.
    Diagnostic only - nothing is smoothed or removed.
    """
    cols = np.asarray(cols, np.int64)
    rows = np.asarray(rows, np.int64)
    n = len(cols)
    index = {(int(c), int(r)): i for i, (c, r) in enumerate(zip(cols, rows, strict=True))}
    parent = np.arange(n)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, (c, r) in enumerate(zip(cols, rows, strict=True)):
        for nb in ((int(c) + 1, int(r)), (int(c), int(r) + 1)):
            j = index.get(nb)
            if j is not None:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    roots = np.array([find(i) for i in range(n)])
    _, labels = np.unique(roots, return_inverse=True)
    return labels
