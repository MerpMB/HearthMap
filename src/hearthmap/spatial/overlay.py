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
    allow_review: bool = False,
) -> pd.DataFrame:
    """Area-based overlay of polygon ``features`` onto ``grid`` cells.

    Both layers must share one metric CRS. Returns a DataFrame indexed like
    ``grid`` (one row per cell). Review-only layers (``review_only`` column,
    M1A.1) are refused unless ``allow_review`` is set for QA diagnostics.
    """
    from hearthmap.qa.review import assert_not_review_layer

    if not allow_review:
        assert_not_review_layer(features, name=prefix)
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


def categorical_cell_fractions(
    grid: gpd.GeoDataFrame,
    features: gpd.GeoDataFrame,
    *,
    class_field: str,
    classes: list,
    prefix: str,
    within: shapely.Geometry | None = None,
    coverage: np.ndarray | None = None,
) -> pd.DataFrame:
    """Area share of each publisher class within each cell (no centroid sampling).

    Classes keep the publisher's original codes (never renumbered). Fractions are
    relative to the cell's in-``within`` area when ``within``/``coverage`` are
    given, otherwise to the full cell. Returns per-class fractions,
    ``<p>_assessed_fraction`` (sum), ``<p>_max_class`` (highest code present with
    area > 0), ``<p>_dominant_class`` (largest area; ties -> higher code) and
    ``<p>_class_distribution`` (compact "code:fraction" string).
    """
    from hearthmap.qa.review import assert_not_review_layer
    from hearthmap.spatial.grid import cell_coverage

    assert_not_review_layer(features, name=prefix)
    crs = require_crs(grid, name="grid")
    assert_metric_crs(crs, purpose="categorical overlay")
    if not same_crs(crs, require_crs(features, name=prefix)):
        raise ValueError(f"{prefix}: features CRS differs from grid CRS; reproject first")
    cells = grid.geometry.values
    size = float(np.sqrt(shapely.area(cells[0])))
    base = np.ones(len(grid)) if coverage is None else np.asarray(coverage, float)
    out = pd.DataFrame(index=grid.index)
    fr = {}
    for code in classes:
        geom = shapely.union_all(features.loc[features[class_field] == code].geometry.values)
        if within is not None:
            geom = geom.intersection(within)
        cov = cell_coverage(cells, geom, size) if not geom.is_empty else np.zeros(len(grid))
        fr[code] = np.divide(cov, base, out=np.zeros(len(grid)), where=base > 0).clip(0, 1)
        out[f"{prefix}_class{code}_fraction"] = fr[code]
    mat = np.column_stack([fr[c] for c in classes])
    out[f"{prefix}_assessed_fraction"] = mat.sum(axis=1).clip(0, 1)
    present = mat > 1e-12
    codes = np.array(classes)
    any_present = present.any(axis=1)
    max_idx = np.where(present, np.arange(len(classes)), -1).max(axis=1)
    out[f"{prefix}_max_class"] = np.where(any_present, codes[np.maximum(max_idx, 0)], np.nan)
    # ties -> higher code: reverse argmax
    dom_idx = len(classes) - 1 - np.argmax(mat[:, ::-1], axis=1)
    out[f"{prefix}_dominant_class"] = np.where(any_present, codes[dom_idx], np.nan)
    out[f"{prefix}_class_distribution"] = [
        ";".join(f"{c}:{v:.3f}" for c, v in zip(classes, row, strict=True) if v > 1e-12)
        for row in mat
    ]
    return out
