# ruff: noqa: E501
"""Aggregate lon/lat rasters onto the canonical 500 m grid (EPSG:32647), and descriptive neighbourhood smoothing.

Pixel centres are reprojected to the canonical CRS and binned into grid cells, so sums are conserved except at the AOI edge.
Smoothing is a plain box mean over neighbouring cells (a context window), not a model.
"""

from __future__ import annotations

import numpy as np
import rasterio
import shapely
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


def aoi_pixel_weights(
    lon: np.ndarray,
    lat: np.ndarray,
    half_w: float,
    half_h: float,
    aoi_ll: shapely.Geometry,
    sub: int = 8,
) -> np.ndarray:
    """Share (0..1) of each pixel FOOTPRINT that lies inside the AOI (lon/lat polygon).

    Pixels whose centre and four corners agree are fully in (1) or fully out (0); mixed pixels are sampled on a ``sub`` x ``sub`` point lattice.
    """
    shapely.prepare(aoi_ll)
    centre = shapely.contains_xy(aoi_ll, lon, lat)
    corners = [
        shapely.contains_xy(aoi_ll, lon + sx * half_w, lat + sy * half_h)
        for sx in (-1, 1)
        for sy in (-1, 1)
    ]
    all_in = centre & np.logical_and.reduce(corners)
    all_out = ~centre & ~np.logical_or.reduce(corners)
    w = all_in.astype(float)
    mixed = ~(all_in | all_out)
    if mixed.any():
        offs = (np.arange(sub) + 0.5) / sub - 0.5
        px = lon[mixed][:, None, None] + 2 * half_w * offs[None, :, None] + 0 * offs[None, None, :]
        py = lat[mixed][:, None, None] + 2 * half_h * offs[None, None, :] + 0 * offs[None, :, None]
        inside = shapely.contains_xy(aoi_ll, px.ravel(), py.ravel()).reshape(-1, sub * sub)
        w[mixed] = inside.mean(axis=1)
    return w


def aggregate_to_grid_aoi(
    sources: list[str],
    gi: GridIndex,
    bounds_lonlat: tuple[float, float, float, float],
    n_cells: int,
    aoi_ll: shapely.Geometry,
    nodata: float | None = None,
) -> tuple[np.ndarray, np.ndarray, int, float]:
    """Sum raster values per grid cell twice: over the FULL cell (context only) and over the AOI-clipped footprint.

    A pixel belongs to the cell that holds its centre (the rule used by ``aggregate_to_grid``); its AOI-clipped contribution is the pixel value
    times the share of the pixel footprint inside the AOI. Pixel values are conserved totals (people, m2), so that share of the footprint is the
    share of the value under a uniform-within-pixel assumption. Fully interior cells keep exactly their full-cell value.
    Returns (full_cell_sums, aoi_clipped_sums, pixels_used, aoi_clipped_value_of_pixels_whose_centre_is_in_no_grid_cell).
    The last number is a closure check: it should be about zero because the grid covers the AOI.
    """
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
    full = np.zeros(n_cells)
    clipped = np.zeros(n_cells)
    used = 0
    dropped = 0.0
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
            lo, la, val = lon[keep], lat[keep], arr[keep]
            x, y = tr.transform(lo, la)
            idx = gi.locate(np.asarray(x), np.asarray(y))
            wt = aoi_pixel_weights(lo, la, abs(t.a) / 2, abs(t.e) / 2, aoi_ll)
            ok = idx >= 0
            np.add.at(full, idx[ok], val[ok])
            np.add.at(clipped, idx[ok], val[ok] * wt[ok])
            dropped += float((val[~ok] * wt[~ok]).sum())
            used += int(ok.sum())
    return full, clipped, used, dropped


def area_fraction(cells: np.ndarray, polys: np.ndarray, n_cells: int) -> np.ndarray:
    """Share of each 500 m cell covered by the given polygons (overlaps between polygons are merged first)."""
    out = np.zeros(n_cells)
    if len(polys) == 0:
        return out
    merged = shapely.unary_union(polys)
    tree = shapely.STRtree(cells)
    ci = tree.query(merged, predicate="intersects")
    inter = shapely.area(shapely.intersection(cells[ci], merged))
    out[ci] = np.clip(inter / shapely.area(cells[ci]), 0, 1)
    return out


def assign_max_overlap(
    cells: np.ndarray,
    cell_group: np.ndarray,
    polys: np.ndarray,
    poly_group: np.ndarray,
    poly_ids: np.ndarray,
    centroid_first: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Administrative unit of each cell, restricted to units of the cell's OWN group (province).

    With ``centroid_first`` a cell keeps the own-group unit that contains its centroid (this preserves the usual assignment for
    ordinary cells); only cells whose centroid is NOT in an own-group unit fall back to the own-group unit that overlaps the cell most.
    A centroid join alone mislabels edge cells: the grid keeps cells that only partly cover the AOI, so their centroid can lie in a
    neighbouring province or outside Thailand. Cells with no own-group unit overlapping them get "" (unknown, never a neighbour label).

    Returns (ids, overlap_share_of_cell, method).
    """
    polys = shapely.make_valid(polys)
    tree = shapely.STRtree(polys)
    n = len(cells)
    ids = np.full(n, "", dtype=object)
    share = np.zeros(n)
    method = np.full(n, "NO_OVERLAPPING_UNIT_IN_OWN_GROUP", dtype=object)
    done = np.zeros(n, dtype=bool)
    if centroid_first:
        ci, pi = tree.query(shapely.centroid(cells), predicate="within")
        keep = cell_group[ci] == poly_group[pi]
        ci, pi = ci[keep], pi[keep]
        ids[ci], method[ci] = poly_ids[pi], "CENTROID_IN_OWN_GROUP_UNIT"
        done[ci] = True
        share[ci] = shapely.area(shapely.intersection(cells[ci], polys[pi])) / shapely.area(
            cells[ci]
        )
    ci, pi = tree.query(cells, predicate="intersects")
    keep = (cell_group[ci] == poly_group[pi]) & ~done[ci]
    ci, pi = ci[keep], pi[keep]
    inter = shapely.area(shapely.intersection(cells[ci], polys[pi]))
    pos = inter > 0  # a unit that only touches the cell edge is not an overlap
    ci, pi, inter = ci[pos], pi[pos], inter[pos]
    if len(ci):
        order = np.lexsort((-inter, ci))  # per cell, largest overlap first
        ci, pi, inter = ci[order], pi[order], inter[order]
        first = np.r_[True, ci[1:] != ci[:-1]]
        ids[ci[first]] = poly_ids[pi[first]]
        share[ci[first]] = inter[first] / shapely.area(cells[ci[first]])
        method[ci[first]] = "MAX_OVERLAP_WITHIN_OWN_GROUP"
    return ids, share, method
