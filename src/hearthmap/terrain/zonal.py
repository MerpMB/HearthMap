"""Support-aware zonal statistics onto an aligned square grid (ADR-0009).

Each source pixel is treated as an axis-aligned rectangle in the grid CRS
(centre ``x, y`` and half-extents ``hw, hh`` in metres) and contributes to every
grid cell it overlaps with weight = overlap area / pixel area. Pixels are
never assigned by centre alone, so sliver cells receive the evidence that
actually touches them.

Pixel rectangles ignore the small rotation between a geographic pixel and the
UTM grid (meridian convergence, < 1 degree over the AOI); this is documented,
not hidden.

Partial cells: if ``clip_pieces`` maps a cell index to its in-AOI geometry, the
weights of pixels in that cell are multiplied by the share of the pixel
rectangle inside that piece (exact, via shapely).

Statistics per cell (weighted): support (sum of weights, in pixels), min, max,
quantiles. A cell's statistics are UNKNOWN (NaN) when support < ``min_support``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd
import shapely


def pixel_cell_weights(
    x: np.ndarray,
    y: np.ndarray,
    hw: np.ndarray | float,
    hh: np.ndarray | float,
    cell_size: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split each pixel rectangle across the (up to 4) cells it overlaps.

    Returns (pixel_index, col, row, weight) with weights summing to 1 per pixel.
    Requires pixels smaller than a cell.
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    hw = np.broadcast_to(np.asarray(hw, float), x.shape)
    hh = np.broadcast_to(np.asarray(hh, float), y.shape)
    if np.any(2 * hw > cell_size) or np.any(2 * hh > cell_size):
        raise ValueError("pixels must be smaller than grid cells")
    x0, x1 = x - hw, x + hw
    y0, y1 = y - hh, y + hh
    c0 = np.floor(x0 / cell_size).astype(np.int64)
    c1 = np.floor(np.nextafter(x1, -np.inf) / cell_size).astype(np.int64)
    r0 = np.floor(y0 / cell_size).astype(np.int64)
    r1 = np.floor(np.nextafter(y1, -np.inf) / cell_size).astype(np.int64)
    split_x = np.minimum((c0 + 1) * cell_size, x1)
    wx0 = (split_x - x0) / (x1 - x0)
    wx1 = 1.0 - wx0
    split_y = np.minimum((r0 + 1) * cell_size, y1)
    wy0 = (split_y - y0) / (y1 - y0)
    wy1 = 1.0 - wy0
    idx = np.arange(len(x))
    parts = []
    # wx0 == 1 (and wx1 == 0) when the pixel lies within one column; same for rows,
    # so zero-weight combinations are simply dropped.
    for cc, wx in ((c0, wx0), (c1, wx1)):
        for rr, wy in ((r0, wy0), (r1, wy1)):
            w = wx * wy
            keep = w > 1e-15
            parts.append((idx[keep], cc[keep], rr[keep], w[keep]))
    pi = np.concatenate([p[0] for p in parts])
    cc = np.concatenate([p[1] for p in parts])
    rr = np.concatenate([p[2] for p in parts])
    ww = np.concatenate([p[3] for p in parts])
    return pi, cc, rr, ww


def clip_weights(
    pixel_index: np.ndarray,
    cell_index: np.ndarray,
    weights: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    hw: np.ndarray,
    hh: np.ndarray,
    clip_pieces: Mapping[int, shapely.Geometry],
) -> np.ndarray:
    """Multiply weights of entries in clipped cells by the pixel share inside the piece."""
    w = weights.copy()
    sel = np.flatnonzero(np.isin(cell_index, np.fromiter(clip_pieces.keys(), int)))
    if len(sel) == 0:
        return w
    p = pixel_index[sel]
    rects = shapely.box(x[p] - hw[p], y[p] - hh[p], x[p] + hw[p], y[p] + hh[p])
    pieces = np.array([clip_pieces[int(c)] for c in cell_index[sel]], dtype=object)
    inside = shapely.area(shapely.intersection(rects, pieces)) / shapely.area(rects)
    # The cell share of the pixel is already in w; inside-share of the pixel cannot exceed it.
    w[sel] = np.minimum(w[sel], inside)
    return w


def weighted_cell_stats(
    cell_index: np.ndarray,
    weights: np.ndarray,
    values: np.ndarray,
    *,
    n_cells: int,
    quantiles: Sequence[float] = (0.5, 0.9),
    thresholds: Sequence[float] = (),
    min_support: float = 1.0,
    prefix: str = "v",
) -> pd.DataFrame:
    """Weighted per-cell statistics; NaN values do not count towards support."""
    v = np.asarray(values, float)
    ok = np.isfinite(v) & (weights > 0)
    ci, w, v = cell_index[ok], weights[ok], v[ok]
    out = pd.DataFrame(index=pd.RangeIndex(n_cells))
    support = np.bincount(ci, weights=w, minlength=n_cells)
    out[f"{prefix}_support_px"] = support
    order = np.lexsort((v, ci))
    ci, w, v = ci[order], w[order], v[order]
    starts = np.searchsorted(ci, np.arange(n_cells), side="left")
    ends = np.searchsorted(ci, np.arange(n_cells), side="right")
    has = ends > starts
    mn = np.full(n_cells, np.nan)
    mx = np.full(n_cells, np.nan)
    mn[has] = v[starts[has]]
    mx[has] = v[ends[has] - 1]
    out[f"{prefix}_min"] = mn
    out[f"{prefix}_max"] = mx
    cumw = np.cumsum(w)
    base = np.where(starts > 0, cumw[np.maximum(starts - 1, 0)], 0.0)
    for q in quantiles:
        res = np.full(n_cells, np.nan)
        target = base + q * support
        pos = np.searchsorted(cumw, target - 1e-12, side="left")
        pos = np.clip(pos, starts, np.maximum(ends - 1, starts))
        res[has] = v[pos[has]]
        out[f"{prefix}_p{round(q * 100):02d}"] = res
    with np.errstate(invalid="ignore", divide="ignore"):
        for t in thresholds:
            above = np.bincount(ci[v > t], weights=w[v > t], minlength=n_cells)
            out[f"{prefix}_gt{t:g}_fraction"] = np.where(support > 0, above / support, np.nan)
    weak = support < min_support
    stat_cols = [c for c in out.columns if c != f"{prefix}_support_px"]
    out.loc[weak, stat_cols] = np.nan
    return out
