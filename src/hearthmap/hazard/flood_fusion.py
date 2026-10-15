"""Flood evidence fusion (M1C.3): source-aware annual ledger and candidate flood ladders.

The ledger holds, for every grid cell and year 2005-2023, the source-native flooded
fractions of the two GISTDA products and their per-year agreement. It is a raw
OBSERVATIONAL record, never a homogeneous statistical series:

    2005-2010   legacy product only
    2011-2016   both products (agreement is auditable)
    2017-2023   current product only

``observed_year_count_total`` is the number of calendar years in which at least one
available GISTDA product mapped observed flooding. It is not a probability, a
return period or a recurrence estimate.

Principles enforced here (and tested):

* Source-native fractions are kept; presence is derived, never stored instead.
* Product disagreement (2011-2016) stays visible; the fused ``observed`` fraction is a
  spatial union used for screening, and disagreement metadata is never dropped.
* Rules are positive-only: they can raise concern, never lower it. A missing polygon in
  either product is never evidence that flooding did not occur.
* No decay weights: old evidence stays; ``most_recent_observed_year`` and
  ``years_since_most_recent_observation`` are exposed instead.
* The slope stratum is for reporting only and is never read by any rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml
from hearthmap.hazard.policy import FloodOverride
from hearthmap.hazard.policy import Level as PolicyLevel
from hearthmap.hazard.reconcile import (
    COMMON_YEARS,
    CURRENT,
    CURRENT_YEARS,
    LEGACY,
    LEGACY_YEARS,
    fraction_column,
)

YEARS = tuple(range(2005, 2024))
OBSERVED_YEAR_COUNT_DEFINITION = (
    "number of calendar years in which at least one available GISTDA product mapped "
    "observed flooding (>= presence_min_fraction of the cell); a raw observational count, "
    "NOT a probability, return period or homogeneous recurrence series"
)
FORBIDDEN_FLOOD_WORDS = ("NO_FLOOD_RISK", "SAFE_FROM_FLOOD", "SAFE", "LOW_FLOOD_RISK", "LOW_RISK")
_TOL = 1e-12


class YearState(StrEnum):
    OBSERVED_CONSENSUS = "OBSERVED_CONSENSUS"
    OBSERVED_LEGACY_ONLY_OVERLAP = "OBSERVED_LEGACY_ONLY_OVERLAP"
    OBSERVED_CURRENT_ONLY_OVERLAP = "OBSERVED_CURRENT_ONLY_OVERLAP"
    OBSERVED_OVERLAP_MIXED_DISAGREEMENT = "OBSERVED_OVERLAP_MIXED_DISAGREEMENT"
    OBSERVED_SINGLE_SOURCE_LEGACY = "OBSERVED_SINGLE_SOURCE_LEGACY"
    OBSERVED_SINGLE_SOURCE_CURRENT = "OBSERVED_SINGLE_SOURCE_CURRENT"
    # "not observed" = no polygon mapped by the available product(s); NOT "did not flood"
    NOT_OBSERVED_CONSENSUS = "NOT_OBSERVED_CONSENSUS"
    NOT_OBSERVED_SINGLE_SOURCE = "NOT_OBSERVED_SINGLE_SOURCE"


DISAGREEMENT_STATES = frozenset(
    {
        YearState.OBSERVED_LEGACY_ONLY_OVERLAP.value,
        YearState.OBSERVED_CURRENT_ONLY_OVERLAP.value,
        YearState.OBSERVED_OVERLAP_MIXED_DISAGREEMENT.value,
    }
)


class FloodLevel(IntEnum):
    NONE = 0
    HISTORICAL = 1
    VERIFY = 2
    STRONG = 3


class FloodLadder(StrEnum):
    NO_MAJOR_OBSERVED_SIGNAL = "NO_MAJOR_OBSERVED_SIGNAL"
    HISTORICAL_SIGNAL = "HISTORICAL_SIGNAL"
    REQUIRES_FLOOD_VERIFICATION = "REQUIRES_FLOOD_VERIFICATION"
    STRONG_FLOOD_SCREENING_CONCERN = "STRONG_FLOOD_SCREENING_CONCERN"
    UNRESOLVED = "UNRESOLVED"


_LADDER_FOR_LEVEL = {
    FloodLevel.NONE: FloodLadder.NO_MAJOR_OBSERVED_SIGNAL,
    FloodLevel.HISTORICAL: FloodLadder.HISTORICAL_SIGNAL,
    FloodLevel.VERIFY: FloodLadder.REQUIRES_FLOOD_VERIFICATION,
    FloodLevel.STRONG: FloodLadder.STRONG_FLOOD_SCREENING_CONCERN,
}
# Mapping into the hydrogeomorphic policy: a historical signal is informational only.
_POLICY_LEVEL = {
    FloodLevel.NONE: PolicyLevel.NONE,
    FloodLevel.HISTORICAL: PolicyLevel.NONE,
    FloodLevel.VERIFY: PolicyLevel.VERIFY,
    FloodLevel.STRONG: PolicyLevel.STRONG,
}

METRICS = (
    "observed_fraction",
    "legacy_fraction",
    "current_fraction",
    "intersection_fraction",
    "legacy_only_fraction",
    "current_only_fraction",
    "mismatch_fraction",
    "legacy_exclusive_fraction",
)


# ---------------------------------------------------------------- config


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Rule(_M):
    id: str
    level: Literal["HISTORICAL", "VERIFY", "STRONG"]
    metric: Literal[
        "observed_fraction",
        "legacy_fraction",
        "current_fraction",
        "intersection_fraction",
        "legacy_only_fraction",
        "current_only_fraction",
        "mismatch_fraction",
        "legacy_exclusive_fraction",
    ]
    years: tuple[int, int]
    min_years: int = Field(ge=1)
    min_fraction: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _years_ok(self) -> Rule:
        a, b = self.years
        if not (YEARS[0] <= a <= b <= YEARS[-1]):
            raise ValueError(
                f"rule {self.id}: years {self.years} outside the ledger {YEARS[0]}-{YEARS[-1]}"
            )
        if self.min_years > b - a + 1:
            raise ValueError(f"rule {self.id}: min_years exceeds the year window")
        return self


class Candidate(_M):
    description: str
    extends: str | None
    rules: list[Rule]


class Stratification(_M):
    purpose: Literal["reporting_only_not_suitability"]
    slope_p90_bands_deg: tuple[float, float]


class FusionConfig(_M):
    schema_version: Literal[1]
    fusion_id: str
    fusion_version: str
    status: Literal["PROVISIONAL"]
    default_candidate: None
    presence_min_fraction: float = Field(gt=0, lt=1)
    reference_year: int
    sources: dict
    eras: dict[str, tuple[int, int]]
    stratification: Stratification
    candidates: dict[str, Candidate]
    reason_codes: dict[str, str]

    @model_validator(mode="after")
    def _guards(self) -> FusionConfig:
        names = list(self.candidates)
        for cid, cand in self.candidates.items():
            if cand.extends is not None and cand.extends not in self.candidates:
                raise ValueError(f"{cid} extends unknown candidate {cand.extends}")
        for cid in names:  # extends chains must be acyclic
            seen, cur = set(), cid
            while cur is not None:
                if cur in seen:
                    raise ValueError(f"cyclic extends at {cur}")
                seen.add(cur)
                cur = self.candidates[cur].extends
        texts = [
            *names,
            *self.reason_codes,
            *(r.id for c in self.candidates.values() for r in c.rules),
        ]
        for t in texts:
            for w in FORBIDDEN_FLOOD_WORDS:
                if w in t.split("_") or t.startswith(w + "_") or t == w:
                    raise ValueError(f"{t} uses forbidden wording {w}")
        if "NO_FLOOD_RISK" in " ".join(texts) or "SAFE_FROM_FLOOD" in " ".join(texts):
            raise ValueError("flood labels must never claim absence of flood risk")
        missing = {
            r.id for c in self.candidates.values() for r in c.rules if r.id not in self.reason_codes
        }
        if missing:
            raise ValueError(f"rules without a reason_codes template: {sorted(missing)}")
        return self

    def rules_for(self, candidate: str) -> list[Rule]:
        """Own rules plus every inherited rule (candidates are nested by construction)."""
        out: list[Rule] = []
        cur: str | None = candidate
        while cur is not None:
            out = [*self.candidates[cur].rules, *out]
            cur = self.candidates[cur].extends
        return out


def load_fusion_config(path: Path | str = "config/flood-fusion.yaml") -> FusionConfig:
    try:
        return FusionConfig.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid flood fusion config {path}:\n{exc}") from exc


# ---------------------------------------------------------------- ledger


@dataclass(frozen=True)
class FloodLedger:
    """(cells x years) source-native fractions and per-year agreement states."""

    years: tuple[int, ...]
    presence_min: float
    legacy: np.ndarray  # NaN where the legacy product has no value for that year
    current: np.ndarray  # NaN where the current product has no value for that year
    intersection: np.ndarray  # NaN outside the common years
    legacy_only: np.ndarray
    current_only: np.ndarray
    observed: np.ndarray  # fused spatial union fraction (never NaN)
    state: np.ndarray  # (cells x years) object array of YearState values
    sources_positive: np.ndarray  # (cells x years) object array

    @property
    def n_cells(self) -> int:
        return self.legacy.shape[0]

    def sources_available(self) -> dict[int, str]:
        return {
            y: "legacy+current"
            if y in COMMON_YEARS
            else ("legacy" if y in LEGACY_YEARS else "current")
            for y in self.years
        }

    def window(self, a: int, b: int) -> np.ndarray:
        return np.array([i for i, y in enumerate(self.years) if a <= y <= b], dtype=int)

    def metric(self, name: str) -> np.ndarray:
        if name == "observed_fraction":
            return self.observed
        if name == "legacy_fraction":
            return self.legacy
        if name == "current_fraction":
            return self.current
        if name == "intersection_fraction":
            return self.intersection
        if name == "legacy_only_fraction":
            return self.legacy_only
        if name == "current_only_fraction":
            return self.current_only
        if name == "mismatch_fraction":
            return self.legacy_only + self.current_only  # NaN outside the common years
        if name == "legacy_exclusive_fraction":
            # what ONLY the legacy product maps: its own area outside the common years'
            # agreement (legacy-only share in 2011-2016; legacy fraction in 2005-2010)
            out = np.full_like(self.legacy, np.nan)
            for i, y in enumerate(self.years):
                if y in COMMON_YEARS:
                    out[:, i] = self.legacy_only[:, i]
                elif y in LEGACY_YEARS:
                    out[:, i] = self.legacy[:, i]
            return out
        raise KeyError(name)


def build_ledger(table: pd.DataFrame, presence_min: float, *, tol: float = 1e-6) -> FloodLedger:
    """Build the ledger from the M1C.2 per-cell annual comparison table."""
    n, ny = len(table), len(YEARS)
    nan = lambda: np.full((n, ny), np.nan)  # noqa: E731
    legacy, current, inter, lo, co = nan(), nan(), nan(), nan(), nan()
    for j, y in enumerate(YEARS):
        if y in LEGACY_YEARS:
            legacy[:, j] = table[fraction_column(LEGACY, y)].to_numpy(float)
        if y in CURRENT_YEARS:
            current[:, j] = table[fraction_column(CURRENT, y)].to_numpy(float)
        if y in COMMON_YEARS:
            inter[:, j] = table[f"intersection_fraction_{y}"].to_numpy(float)
            lo[:, j] = table[f"legacy_only_fraction_{y}"].to_numpy(float)
            co[:, j] = table[f"current_only_fraction_{y}"].to_numpy(float)
            if np.nanmax(np.abs(inter[:, j] + lo[:, j] - legacy[:, j]), initial=0) > tol:
                raise ValueError(f"{y}: intersection + legacy_only != legacy fraction")
            if np.nanmax(np.abs(inter[:, j] + co[:, j] - current[:, j]), initial=0) > tol:
                raise ValueError(f"{y}: intersection + current_only != current fraction")
    observed = np.where(
        ~np.isnan(inter),
        inter + lo + co,
        np.where(~np.isnan(legacy), legacy, current),
    ).clip(0, 1)
    pm = presence_min - _TOL
    state = np.empty((n, ny), dtype=object)
    pos_src = np.empty((n, ny), dtype=object)
    for j, y in enumerate(YEARS):
        obs = observed[:, j] >= pm
        if y in COMMON_YEARS:
            lflag, cflag = lo[:, j] >= pm, co[:, j] >= pm
            s = np.full(n, YearState.NOT_OBSERVED_CONSENSUS.value, dtype=object)
            s[obs & ~lflag & ~cflag] = YearState.OBSERVED_CONSENSUS.value
            s[obs & lflag & ~cflag] = YearState.OBSERVED_LEGACY_ONLY_OVERLAP.value
            s[obs & ~lflag & cflag] = YearState.OBSERVED_CURRENT_ONLY_OVERLAP.value
            s[obs & lflag & cflag] = YearState.OBSERVED_OVERLAP_MIXED_DISAGREEMENT.value
            lp, cp = legacy[:, j] >= pm, current[:, j] >= pm
            ps = np.select([lp & cp, lp, cp], ["legacy+current", "legacy", "current"], "none")
        elif y in LEGACY_YEARS:
            s = np.where(
                obs,
                YearState.OBSERVED_SINGLE_SOURCE_LEGACY.value,
                YearState.NOT_OBSERVED_SINGLE_SOURCE.value,
            ).astype(object)
            ps = np.where(obs, "legacy", "none")
        else:
            s = np.where(
                obs,
                YearState.OBSERVED_SINGLE_SOURCE_CURRENT.value,
                YearState.NOT_OBSERVED_SINGLE_SOURCE.value,
            ).astype(object)
            ps = np.where(obs, "current", "none")
        state[:, j], pos_src[:, j] = s, ps
    return FloodLedger(
        YEARS, presence_min, legacy, current, inter, lo, co, observed, state, pos_src
    )


def ledger_long(ledger: FloodLedger, cell_ids: pd.Series) -> pd.DataFrame:
    """One row per cell-year with the fields the ledger is defined to retain."""
    n, ny = ledger.n_cells, len(ledger.years)
    avail = ledger.sources_available()
    f32 = lambda a: a.reshape(-1).astype("float32")  # noqa: E731
    return pd.DataFrame(
        {
            "cell_id": np.repeat(cell_ids.to_numpy(), ny),
            "year": np.tile(np.array(ledger.years, dtype="int16"), n),
            "observed_flood_fraction": f32(ledger.observed),
            "legacy_fraction": f32(ledger.legacy),
            "current_fraction": f32(ledger.current),
            "intersection_fraction": f32(ledger.intersection),
            "legacy_only_fraction": f32(ledger.legacy_only),
            "current_only_fraction": f32(ledger.current_only),
            "agreement_state": ledger.state.reshape(-1),
            "sources_available": np.tile(np.array([avail[y] for y in ledger.years]), n),
            "sources_positive": ledger.sources_positive.reshape(-1),
        }
    )


def ledger_summary(ledger: FloodLedger, reference_year: int) -> pd.DataFrame:
    """Per-cell source-aware summaries (see OBSERVED_YEAR_COUNT_DEFINITION)."""
    years = np.array(ledger.years)
    observed_state = np.vectorize(lambda s: s.startswith("OBSERVED_"), otypes=[bool])(ledger.state)
    disagree = np.vectorize(lambda s: s in DISAGREEMENT_STATES, otypes=[bool])(ledger.state)
    consensus = ledger.state == YearState.OBSERVED_CONSENSUS.value

    def cols(a: int, b: int):
        return (years >= a) & (years <= b)

    older, mid, recent = cols(2005, 2010), cols(2011, 2016), cols(2017, 2023)
    first = np.where(observed_state.any(axis=1), years[observed_state.argmax(axis=1)], np.nan)
    last_idx = observed_state.shape[1] - 1 - observed_state[:, ::-1].argmax(axis=1)
    last = np.where(observed_state.any(axis=1), years[last_idx], np.nan)
    out = pd.DataFrame(index=np.arange(ledger.n_cells))
    out["observed_year_count_total"] = observed_state.sum(axis=1)
    out["observed_year_count_semantics"] = "RAW_OBSERVATIONAL_COUNT_NOT_PROBABILITY"
    out["legacy_era_observed_years"] = observed_state[:, older].sum(axis=1)
    out["overlap_consensus_observed_years"] = consensus[:, mid].sum(axis=1)
    out["overlap_disagreement_observed_years"] = disagree[:, mid].sum(axis=1)
    out["current_era_observed_years"] = observed_state[:, recent].sum(axis=1)
    out["most_recent_observed_year"] = last
    out["oldest_observed_year"] = first
    out["years_since_most_recent_observation"] = reference_year - last
    out["most_recent_observed_band"] = np.select(
        [np.isnan(last), last >= 2017, last >= 2011], ["NONE", "RECENT", "MID"], "OLDER"
    )
    out["max_annual_flood_fraction"] = ledger.observed.max(axis=1)
    out["recent_era_max_fraction"] = ledger.observed[:, recent].max(axis=1)
    out["mid_era_max_fraction"] = ledger.observed[:, mid].max(axis=1)
    out["older_era_max_fraction"] = ledger.observed[:, older].max(axis=1)
    out["historical_era_max_fraction"] = ledger.observed[:, older | mid].max(axis=1)
    out["has_overlap_product_disagreement"] = disagree[:, mid].any(axis=1)
    out["max_overlap_mismatch_fraction"] = np.nanmax(
        ledger.metric("mismatch_fraction")[:, mid], axis=1
    )
    out["overlap_disagreement_years"] = [
        "|".join(str(y) for y in years[mid & row]) for row in disagree
    ]
    return out


# ---------------------------------------------------------------- candidate evaluation


@dataclass(frozen=True)
class FloodResult:
    candidate: str
    level: np.ndarray  # FloodLevel ints
    state: np.ndarray  # FloodLadder strings
    reason_codes: list[list[str]]
    source_disagreement: np.ndarray

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "flood_policy_id": self.candidate,
                "flood_fusion_state": self.state,
                "flood_fusion_level": self.level,
                "flood_fusion_reason_codes": ["|".join(c) for c in self.reason_codes],
                "flood_source_disagreement": self.source_disagreement,
            }
        )


def rule_hits(ledger: FloodLedger, rule: Rule) -> np.ndarray:
    """Cells for which the rule fires. NaN (metric unavailable that year) never counts."""
    m = ledger.metric(rule.metric)[:, ledger.window(*rule.years)]
    with np.errstate(invalid="ignore"):
        ok = m >= rule.min_fraction - _TOL
    return ok.sum(axis=1) >= rule.min_years


def evaluate_candidate(
    ledger: FloodLedger,
    cfg: FusionConfig,
    candidate: str,
    *,
    evaluated: np.ndarray | None = None,
) -> FloodResult:
    """Positive-only ladder: the level is the maximum over all fired rules."""
    n = ledger.n_cells
    level = np.zeros(n, dtype=int)
    codes: list[list[str]] = [[] for _ in range(n)]
    for rule in cfg.rules_for(candidate):
        hit = rule_hits(ledger, rule)
        level = np.where(hit, np.maximum(level, FloodLevel[rule.level].value), level)
        for i in np.flatnonzero(hit):
            if rule.id not in codes[i]:
                codes[i].append(rule.id)
    state = np.array([_LADDER_FOR_LEVEL[FloodLevel(int(v))].value for v in level], dtype=object)
    if evaluated is not None:
        evaluated = np.asarray(evaluated, bool)
        state[~evaluated] = FloodLadder.UNRESOLVED.value
    disagreement = np.vectorize(lambda s: s in DISAGREEMENT_STATES, otypes=[bool])(ledger.state)
    pm_cols = ledger.window(2011, 2016)
    return FloodResult(candidate, level, state, codes, disagreement[:, pm_cols].any(axis=1))


def to_policy_override(result: FloodResult) -> FloodOverride:
    """Hand a fused flood ladder to the hydrogeomorphic policy (positive-only)."""
    pl = np.array([_POLICY_LEVEL[FloodLevel(int(v))] for v in result.level], dtype=int)
    info = []
    for lvl, st in zip(result.level, result.state, strict=True):
        if st == FloodLadder.UNRESOLVED.value:
            info.append(["FLOOD_NOT_EVALUATED"])
        elif lvl == FloodLevel.HISTORICAL:
            info.append(["HISTORICAL_FLOOD_SIGNAL"])
        elif lvl == FloodLevel.NONE:
            info.append(["NO_OBSERVED_FLOOD_SIGNAL_IN_FUSED_RECORD"])
        else:
            info.append([])
    hazard = [
        c if lvl >= FloodLevel.VERIFY else []
        for c, lvl in zip(result.reason_codes, result.level, strict=True)
    ]
    return FloodOverride(
        policy_id=result.candidate,
        level=pl,
        hazard_codes=hazard,
        info_codes=info,
        state=result.state,
    )


# ---------------------------------------------------------------- reporting-only stratum

SLOPE_STRATA = ("LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15", "UNKNOWN")


def slope_stratum(
    slope_p90_deg: np.ndarray, terrain_support_px: np.ndarray, bands: tuple[float, float] = (5, 15)
) -> np.ndarray:
    """REPORTING ONLY stratum of DSM slope p90. Never an input to a hazard state and
    never a suitability criterion; cells without terrain support are UNKNOWN."""
    s = np.asarray(slope_p90_deg, float)
    sup = np.asarray(terrain_support_px, float)
    lo, hi = bands
    return np.select(
        [np.isnan(s) | (sup < 1.0), s <= lo, s <= hi],
        ["UNKNOWN", "LOW_SLOPE_LE_5", "GENTLE_5_15"],
        "STEEP_GT_15",
    ).astype(object)


def tabulate(
    state: np.ndarray, area_km2: np.ndarray, masks: dict[str, np.ndarray], states: list[str]
) -> pd.DataFrame:
    """Cells and area per state and scope; every cell falls in exactly one state."""
    state = np.asarray(state)
    rows = []
    for scope, m in masks.items():
        m = np.asarray(m, bool)
        total = float(area_km2[m].sum())
        for s in states:
            sel = m & (state == s)
            rows.append(
                {
                    "scope": scope,
                    "state": s,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area_km2[sel].sum()), 2),
                    "share_of_area": round(float(area_km2[sel].sum() / total), 4) if total else 0.0,
                }
            )
    return pd.DataFrame(rows)
