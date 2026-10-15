"""Flood record reconciliation (M1C.2): legacy 2005-2016 vs current 2011-2023.

Pure functions over per-cell / per-year areas. Products are never mixed: every
annual column names its product and year, and comparisons pair columns only
when both products observed the SAME year. Nothing here treats either product
as ground truth, and absence in one product is never reassurance.
"""

from __future__ import annotations

import itertools
import re
from enum import StrEnum

import numpy as np
import pandas as pd

LEGACY = "legacy"  # GISTDA repeated flooding 2005-2016 (1:50k)
CURRENT = "current"  # GISTDA flood recurrence 2011-2023 (API, 20 m)
LEGACY_YEARS = tuple(range(2005, 2017))
CURRENT_YEARS = tuple(range(2011, 2024))
COMMON_YEARS = tuple(sorted(set(LEGACY_YEARS) & set(CURRENT_YEARS)))  # 2011..2016
LEGACY_ONLY_YEARS = tuple(y for y in LEGACY_YEARS if y not in COMMON_YEARS)  # 2005..2010
CURRENT_ONLY_YEARS = tuple(y for y in CURRENT_YEARS if y not in COMMON_YEARS)  # 2017..2023
_COL = re.compile(r"^(legacy|current)_flood_fraction_(\d{4})$")


class CommonPeriodClass(StrEnum):
    AGREEMENT_NO_FLOOD = "AGREEMENT_NO_FLOOD"
    AGREEMENT_FLOOD = "AGREEMENT_FLOOD"
    LEGACY_ONLY_IN_COMMON_PERIOD = "LEGACY_ONLY_IN_COMMON_PERIOD"
    CURRENT_ONLY_IN_COMMON_PERIOD = "CURRENT_ONLY_IN_COMMON_PERIOD"
    MIXED_COMMON_PERIOD_DISAGREEMENT = "MIXED_COMMON_PERIOD_DISAGREEMENT"


class TemporalFlag(StrEnum):
    """Evidence outside the common period - temporal, NOT product disagreement."""

    LEGACY_PRE_2011_ONLY = "LEGACY_PRE_2011_ONLY"
    CURRENT_POST_2016_ONLY = "CURRENT_POST_2016_ONLY"


def fraction_column(product: str, year: int) -> str:
    if product not in (LEGACY, CURRENT):
        raise ValueError(f"unknown product {product!r}")
    valid = LEGACY_YEARS if product == LEGACY else CURRENT_YEARS
    if year not in valid:
        raise ValueError(f"{product} has no native value for {year}")
    return f"{product}_flood_fraction_{year}"


def parse_fraction_column(col: str) -> tuple[str, int]:
    m = _COL.match(col)
    if not m:
        raise ValueError(f"not an annual flood fraction column: {col}")
    return m.group(1), int(m.group(2))


def common_year_pairs(columns) -> list[tuple[int, str, str]]:
    """(year, legacy_col, current_col) for every year BOTH products observed.

    Raises if a pair would mix years or if a column claims a year its product
    does not have natively.
    """
    by = {LEGACY: {}, CURRENT: {}}
    for c in columns:
        if _COL.match(c):
            p, y = parse_fraction_column(c)
            fraction_column(p, y)  # validates the year against the product
            by[p][y] = c
    pairs = []
    for y in sorted(set(by[LEGACY]) & set(by[CURRENT])):
        lc, cc = by[LEGACY][y], by[CURRENT][y]
        assert parse_fraction_column(lc)[1] == parse_fraction_column(cc)[1] == y
        pairs.append((y, lc, cc))
    return pairs


def annual_accounting(legacy_km2: float, current_km2: float, intersection_km2: float) -> dict:
    """Area accounting for one year: old-only, new-only, union and agreement shares."""
    tol = 1e-6 * max(legacy_km2, current_km2, 1.0)
    if intersection_km2 < -tol or intersection_km2 > min(legacy_km2, current_km2) + tol:
        raise ValueError("intersection must lie in [0, min(legacy, current)]")
    inter = min(max(intersection_km2, 0.0), legacy_km2, current_km2)
    union = legacy_km2 + current_km2 - inter
    return {
        "legacy_km2": legacy_km2,
        "current_km2": current_km2,
        "intersection_km2": inter,
        "legacy_only_km2": legacy_km2 - inter,
        "current_only_km2": current_km2 - inter,
        "union_km2": union,
        "intersection_over_union": inter / union if union > 0 else np.nan,
        "legacy_captured_by_current": inter / legacy_km2 if legacy_km2 > 0 else np.nan,
        "current_captured_by_legacy": inter / current_km2 if current_km2 > 0 else np.nan,
        "current_over_legacy_area": current_km2 / legacy_km2 if legacy_km2 > 0 else np.nan,
    }


def cell_year_fractions(
    legacy: np.ndarray, current: np.ndarray, intersection: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-cell fractions for ONE year: intersection, legacy-only, current-only."""
    legacy, current, intersection = map(np.asarray, (legacy, current, intersection))
    if np.any(intersection > np.minimum(legacy, current) + 1e-9):
        raise ValueError("cell intersection exceeds a product's own fraction")
    inter = np.clip(intersection, 0, None)
    return {
        "intersection": inter,
        "legacy_only": np.clip(legacy - inter, 0, None),
        "current_only": np.clip(current - inter, 0, None),
    }


def classify_common_period(
    legacy: pd.DataFrame, current: pd.DataFrame, *, presence_min: float
) -> np.ndarray:
    """Cell class over the common years from per-year presence (fraction >= presence_min).

    ``legacy`` and ``current`` hold one column per common year, aligned by year.
    """
    if list(legacy.columns) != list(current.columns):
        raise ValueError("legacy and current must be aligned on the same years")
    lp = legacy.to_numpy() >= presence_min
    cp = current.to_numpy() >= presence_min
    both = (lp & cp).any(axis=1)
    lonly = (lp & ~cp).any(axis=1)
    conly = (cp & ~lp).any(axis=1)
    out = np.full(len(legacy), CommonPeriodClass.MIXED_COMMON_PERIOD_DISAGREEMENT.value, object)
    out[~both & ~lonly & ~conly] = CommonPeriodClass.AGREEMENT_NO_FLOOD.value
    out[both & ~lonly & ~conly] = CommonPeriodClass.AGREEMENT_FLOOD.value
    out[~both & lonly & ~conly] = CommonPeriodClass.LEGACY_ONLY_IN_COMMON_PERIOD.value
    out[~both & ~lonly & conly] = CommonPeriodClass.CURRENT_ONLY_IN_COMMON_PERIOD.value
    return out


def temporal_flags(
    legacy_pre: pd.DataFrame,
    legacy_common: pd.DataFrame,
    current_common: pd.DataFrame,
    current_post: pd.DataFrame,
    *,
    presence_min: float,
) -> np.ndarray:
    """'|'-joined TemporalFlag values; independent of the common-period class."""

    def any_(df):
        return (df.to_numpy() >= presence_min).any(axis=1)

    pre = any_(legacy_pre) & ~any_(legacy_common)
    post = any_(current_post) & ~any_(current_common)
    return np.array(
        [
            "|".join(
                f.value
                for f, on in (
                    (TemporalFlag.LEGACY_PRE_2011_ONLY, a),
                    (TemporalFlag.CURRENT_POST_2016_ONLY, b),
                )
                if on
            )
            for a, b in zip(pre, post, strict=True)
        ],
        dtype=object,
    )


def legacy_only_breakdown(legacy_pre_any: np.ndarray, legacy_common_any: np.ndarray) -> np.ndarray:
    """For cells flooded only in the legacy record: when did the legacy record see it?"""
    a, b = np.asarray(legacy_pre_any, bool), np.asarray(legacy_common_any, bool)
    return np.select(
        [a & b, a & ~b, ~a & b],
        ["BOTH_2005_2010_AND_2011_2016", "ONLY_2005_2010", "ONLY_2011_2016"],
        "NONE",
    )


def distance_band(d: np.ndarray, edges=(20, 50, 100, 250, 500)) -> np.ndarray:
    """Distance (m) of disagreement area to the other product's polygon, banded."""
    d = np.asarray(d, float)
    labels = (
        [f"<= {edges[0]} m"]
        + [f"{a}-{b} m" for a, b in itertools.pairwise(edges)]
        + [f"> {edges[-1]} m"]
    )
    idx = np.searchsorted(np.asarray(edges, float), d, side="left")
    out = np.array(labels, dtype=object)[np.clip(idx, 0, len(labels) - 1)]
    out[~np.isfinite(d)] = "no polygon in other product that year"
    return out
