"""Grid overlay metrics (sampling contract, docs/architecture/spatial-model.md §4.1).

The 500 m grid is a decision surface, not the resolution of the data. Overlays
therefore keep *area-based* metrics per cell instead of sampling at centroids:
a narrow but severe feature crossing a cell is recorded even when it misses
the cell centre.

Metrics produced for polygon features:

* ``<p>_affected_area_fraction`` - share of the cell area covered by the union
  of intersecting features (overlaps are not double counted), 0..1
* ``<p>_max_<value>`` - maximum of ``value_column`` among intersecting features
* ``<p>_feature_count`` - number of intersecting features

Cells with no intersecting feature get fraction 0, count 0 and a null max. A
zero fraction means "no mapped feature", never "no hazard": absence of
evidence is interpreted by the data-quality rules, not here.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from hearthmap.spatial.crs import assert_metric_crs, require_crs, same_crs


def polygon_cell_metrics(
    grid: gpd.GeoDataFrame,
    features: gpd.GeoDataFrame,
    *,
    prefix: str,
    value_column: str | None = None,
    id_column: str = "cell_id",
) -> pd.DataFrame:
    """Area-based overlay of polygon ``features`` onto ``grid`` cells.

    Both layers must share one metric CRS. Returns a DataFrame indexed like
    ``grid`` (one row per cell).
    """
    crs = require_crs(grid, name="grid")
    assert_metric_crs(crs, purpose="overlay")
    if not same_crs(crs, require_crs(features, name=prefix)):
        raise ValueError(f"{prefix}: features CRS differs from grid CRS; reproject first")

    cells = grid.geometry.values
    feats = features.geometry.values
    tree = shapely.STRtree(feats)
    cell_idx, feat_idx = tree.query(cells, predicate="intersects")

    out = pd.DataFrame(index=grid.index)
    out[f"{prefix}_affected_area_fraction"] = 0.0
    out[f"{prefix}_feature_count"] = 0
    if value_column is not None:
        out[f"{prefix}_max_{value_column}"] = np.nan
    if len(cell_idx) == 0:
        return out

    pieces = shapely.intersection(cells[cell_idx], feats[feat_idx])
    pairs = pd.DataFrame({"cell": cell_idx, "feat": feat_idx, "piece": pieces})
    # Keep only areal overlaps (touching edges/corners produce lines/points).
    pairs = pairs[shapely.area(pairs["piece"].values) > 0]
    if pairs.empty:
        return out

    unions = pairs.groupby("cell")["piece"].apply(lambda g: shapely.union_all(g.values))
    cell_area = shapely.area(cells[unions.index.values])
    frac = np.clip(shapely.area(unions.values) / cell_area, 0.0, 1.0)
    pos = grid.index[unions.index.values]
    out.loc[pos, f"{prefix}_affected_area_fraction"] = frac
    counts = pairs.groupby("cell")["feat"].nunique()
    out.loc[grid.index[counts.index.values], f"{prefix}_feature_count"] = counts.values
    if value_column is not None:
        pairs["value"] = features[value_column].to_numpy()[pairs["feat"].to_numpy()]
        mx = pairs.groupby("cell")["value"].max()
        out.loc[grid.index[mx.index.values], f"{prefix}_max_{value_column}"] = mx.values
    return out
