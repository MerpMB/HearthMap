# ruff: noqa: E501
"""Aggregate lon/lat rasters onto the canonical 500 m grid (EPSG:32647), and descriptive neighbourhood smoothing.

Pixel centres are reprojected to the canonical CRS and binned into grid cells, so sums are conserved except at the AOI edge.
Smoothing is a plain box mean over neighbouring cells (a context window), not a model.
"""

from __future__ import annotations

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

CELL_M = 500.0
CELL_KM2 = CELL_M * CELL_M / 1e6


class GridIndex:
    """Maps projected coordinates to the position of a cell in the sorted grid table (cell ids encode E/N indices)."""

    def __init__(self, cell_ids: list[str]) -> None:
        e = np.array([int(c.split("-")[1][1:]) for c in cell_ids])
        n = np.array([int(c.split("-")[2][1:]) for c in cell_ids])
        self.e0, self.n0 = int(e.min()), int(n.min())
        self.w, self.h = int(e.max() - self.e0 + 1), int(n.max() - self.n0 + 1)
        self.lookup = np.full((self.h, self.w), -1, dtype=np.int64)
        self.lookup[n - self.n0, e - self.e0] = np.arange(len(cell_ids))
        self.col, self.row = e - self.e0, n - self.n0

    def locate(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        c = np.floor(x / CELL_M).astype(np.int64) - self.e0
        r = np.floor(y / CELL_M).astype(np.int64) - self.n0
        ok = (c >= 0) & (c < self.w) & (r >= 0) & (r < self.h)
        out = np.full(len(x), -1, dtype=np.int64)
        out[ok] = self.lookup[r[ok], c[ok]]
        return out

    def smooth_mean(self, values: np.ndarray, radius_cells: int) -> np.ndarray:
        """Box mean over the (2r+1)^2 window using only grid cells that exist; missing cells are not zeros."""
        v = np.zeros((self.h + 2 * radius_cells + 1, self.w + 2 * radius_cells + 1))
        c = np.zeros_like(v)
        r0 = radius_cells
        v[self.row + r0 + 1, self.col + r0 + 1] = np.nan_to_num(values)
        c[self.row + r0 + 1, self.col + r0 + 1] = np.isfinite(values)

        def box(a: np.ndarray) -> np.ndarray:
            s = a.cumsum(0).cumsum(1)
            k = 2 * radius_cells + 1
            return s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k]

        sv, sc = box(v), box(c)
        rr, cc = self.row, self.col
        return sv[rr, cc] / np.maximum(sc[rr, cc], 1)


def aggregate_to_grid(
    sources: list[str],
    gi: GridIndex,
    bounds_lonlat: tuple[float, float, float, float],
    n_cells: int,
    nodata: float | None = None,
) -> tuple[np.ndarray, int]:
    """Sum raster values per grid cell. Returns (sums, number of pixels used). ``sources`` are rasterio-readable paths (several tiles allowed)."""
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
    sums = np.zeros(n_cells)
    used = 0
    w, s, e, n = bounds_lonlat
    for src in sources:
        with rasterio.open(src) as ds:
            bx0, by0, bx1, by1 = ds.bounds
            x0, y0, x1, y1 = max(w, bx0), max(s, by0), min(e, bx1), min(n, by1)
            if x0 >= x1 or y0 >= y1:
                continue
            win = from_bounds(x0, y0, x1, y1, ds.transform).round_offsets().round_lengths()
            arr = ds.read(1, window=win).astype("float64")
            t = ds.window_transform(win)
            rows, cols = np.mgrid[0 : arr.shape[0], 0 : arr.shape[1]]
            lon = t.c + (cols + 0.5) * t.a
            lat = t.f + (rows + 0.5) * t.e
            nd = nodata if nodata is not None else ds.nodata
            keep = (
                np.isfinite(arr)
                & ((arr != nd) if nd is not None else True)
                & (arr > 0)
                & (lon >= w)
                & (lon < e)
                & (lat >= s)
                & (lat < n)
            )
            x, y = tr.transform(lon[keep], lat[keep])
            idx = gi.locate(np.asarray(x), np.asarray(y))
            ok = idx >= 0
            np.add.at(sums, idx[ok], arr[keep][ok])
            used += int(ok.sum())
    return sums, used
