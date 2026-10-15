"""Distribution of per-cell area fractions (no centroid membership)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

DEFAULT_THRESHOLDS = (0.0, 0.01, 0.10, 0.25, 0.50, 0.75, 0.90)


def threshold_distribution(
    fractions: Sequence[float] | np.ndarray,
    *,
    cell_area_m2: float | None = None,
    covered_area_m2: Sequence[float] | np.ndarray | None = None,
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> pd.DataFrame:
    """Cells whose fraction is ``> 0`` (first threshold, strict) or ``>= t``.

    Returns one row per threshold with cell counts and shares. If
    ``covered_area_m2`` (per-cell intersection area) is given, also the share of
    total covered area held by cells at or above the threshold.
    """
    f = np.asarray(fractions, dtype=float)
    if np.any(np.isnan(f)):
        raise ValueError("fractions contain NaN; decide explicitly how to treat unknowns")
    n = len(f)
    area = None if covered_area_m2 is None else np.asarray(covered_area_m2, dtype=float)
    rows = []
    for i, t in enumerate(thresholds):
        mask = f > t if (i == 0 and t == 0) else f >= t
        label = "> 0" if (i == 0 and t == 0) else f">= {t:g}"
        row = {
            "threshold": label,
            "cells": int(mask.sum()),
            "share_of_cells": float(mask.sum() / n) if n else 0.0,
        }
        if area is not None:
            tot = area.sum()
            row["covered_area_km2"] = float(area[mask].sum() / 1e6)
            row["share_of_covered_area"] = float(area[mask].sum() / tot) if tot else 0.0
        rows.append(row)
    return pd.DataFrame(rows)
