"""Exact-combination accounting for overlapping screening categories.

Each unit of area (or each cell) is assigned to exactly ONE combination
(e.g. "reserve+park"), so the totals add up to the union and nothing is double
counted. Combinations are descriptive labels, never severity scores.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import combinations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from hearthmap.spatial.crs import assert_metric_crs, require_crs, same_crs


def _label(names: tuple[str, ...]) -> str:
    return "+".join(names) if names else "none"


def category_area_combinations(
    layers: Mapping[str, gpd.GeoDataFrame], *, within: shapely.Geometry | None = None
) -> pd.DataFrame:
    """Area (km²) of every exact category combination, optionally clipped to ``within``."""
    names = list(layers)
    crs = require_crs(next(iter(layers.values())))
    assert_metric_crs(crs, purpose="overlap accounting")
    unions = {}
    for n, g in layers.items():
        if not same_crs(require_crs(g, name=n), crs):
            raise ValueError(f"{n}: CRS differs; reproject first")
        u = shapely.union_all(g.geometry.values)
        unions[n] = u.intersection(within) if within is not None else u
    rows = []
    for k in range(len(names), 0, -1):
        for combo in combinations(names, k):
            geom = shapely.intersection_all([unions[n] for n in combo])
            others = [unions[n] for n in names if n not in combo]
            if others and not geom.is_empty:
                geom = geom.difference(shapely.union_all(others))
            rows.append(
                {"combination": _label(combo), "n_categories": k, "area_km2": geom.area / 1e6}
            )
    out = pd.DataFrame(rows)
    union_area = shapely.union_all(list(unions.values())).area / 1e6
    out["share_of_union"] = out["area_km2"] / union_area if union_area else 0.0
    return out


def category_cell_combinations(
    fractions: Mapping[str, np.ndarray], *, min_fraction: float = 0.0
) -> pd.DataFrame:
    """Cells per exact combination of categories with fraction > ``min_fraction``."""
    names = list(fractions)
    present = np.column_stack([np.asarray(fractions[n]) > min_fraction for n in names])
    labels = [_label(tuple(n for n, p in zip(names, row, strict=True) if p)) for row in present]
    s = pd.Series(labels).value_counts()
    return pd.DataFrame(
        {"combination": s.index, "cells": s.values, "share_of_cells": s.values / len(labels)}
    )
