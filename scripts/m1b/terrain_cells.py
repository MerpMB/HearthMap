"""M1B terrain indicators per 500 m cell (support-aware, ADR-0009).

Processed in blocks of grid cells. For each block the DEM tiles are mosaicked
with a halo (so slope at tile seams uses true neighbours), Horn slope is
computed with geodesic per-row spacing, and every pixel is split across the
cells it overlaps; partial edge cells are clipped exactly to their in-AOI part.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Geod, Transformer
from rasterio.merge import merge

from hearthmap.terrain import clip_weights, horn_slope_degrees, pixel_cell_weights
from hearthmap.terrain.zonal import weighted_cell_stats

GEOD = Geod(ellps="WGS84")
CELL = 500.0
BLOCK = 80  # cells per block side (40 km)
HALO_DEG = 0.003


def terrain_indicators(
    grid, aoi, tile_paths, *, min_support: float, slope_thresholds: list[float], progress=print
) -> pd.DataFrame:
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
    to_ll = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)
    cols = grid["col"].to_numpy()
    rows = grid["row"].to_numpy()
    c0, r0 = cols.min(), rows.min()
    lookup = np.full((rows.max() - r0 + 1, cols.max() - c0 + 1), -1, dtype=np.int64)
    lookup[rows - r0, cols - c0] = np.arange(len(grid))
    partial = np.flatnonzero(grid["coverage_fraction"].to_numpy() < 1 - 1e-9)
    pieces_all = dict(
        zip(partial.tolist(), shapely.intersection(grid.geometry.values[partial], aoi), strict=True)
    )
    srcs = [rasterio.open(p) for p in tile_paths]
    results = []
    try:
        for bc in range(c0, cols.max() + 1, BLOCK):
            for br in range(r0, rows.max() + 1, BLOCK):
                sel = (cols >= bc) & (cols < bc + BLOCK) & (rows >= br) & (rows < br + BLOCK)
                if not sel.any():
                    continue
                cell_ids = np.flatnonzero(sel)
                local = np.full(len(grid), -1, dtype=np.int64)
                local[cell_ids] = np.arange(len(cell_ids))
                x0, y0 = bc * CELL, br * CELL
                x1, y1 = (bc + BLOCK) * CELL, (br + BLOCK) * CELL
                w, s, e, n = to_ll.transform_bounds(x0, y0, x1, y1, densify_pts=21)
                bounds = (w - HALO_DEG, s - HALO_DEG, e + HALO_DEG, n + HALO_DEG)
                z, tf = merge(srcs, bounds=bounds, nodata=np.nan, dtype="float32")
                z = z[0].astype("float64")
                nr, nc = z.shape
                lat = tf.f + tf.e * (np.arange(nr) + 0.5)
                lon0 = tf.c + tf.a * 0.5
                _, _, dx = GEOD.inv(np.full(nr, lon0), lat, np.full(nr, lon0 + tf.a), lat)
                _, _, dy = GEOD.inv(np.full(nr, lon0), lat, np.full(nr, lon0), lat + tf.e)
                dy_mean = float(np.mean(dy))
                slope = horn_slope_degrees(z, dx, dy_mean)
                rr, cc = np.mgrid[0:nr, 0:nc]
                lonp = tf.c + tf.a * (cc.ravel() + 0.5)
                latp = tf.f + tf.e * (rr.ravel() + 0.5)
                x, y = to_utm.transform(lonp, latp)
                hw = dx[rr.ravel()] / 2
                hh = np.full(x.shape, dy_mean / 2)
                inside = (x >= x0 - 60) & (x <= x1 + 60) & (y >= y0 - 60) & (y <= y1 + 60)
                x, y, hw, hh = x[inside], y[inside], hw[inside], hh[inside]
                zv, sv = z.ravel()[inside], slope.ravel()[inside]
                pi, pc, pr, pw = pixel_cell_weights(x, y, hw, hh, CELL)
                gi = np.full(len(pi), -1, dtype=np.int64)
                ok = (
                    (pc >= c0)
                    & (pc - c0 < lookup.shape[1])
                    & (pr >= r0)
                    & (pr - r0 < lookup.shape[0])
                )
                gi[ok] = lookup[pr[ok] - r0, pc[ok] - c0]
                keep = gi >= 0
                keep &= local[np.where(gi >= 0, gi, 0)] >= 0
                pi, gi, pw = pi[keep], gi[keep], pw[keep]
                pieces = {int(k): pieces_all[int(k)] for k in np.intersect1d(gi, partial)}
                pw = clip_weights(pi, gi, pw, x, y, hw, hh, pieces)
                li = local[gi]
                nb = len(cell_ids)
                pix_area = (2 * hw[pi]) * (2 * hh[pi])
                support_area = np.bincount(li, weights=pw * pix_area, minlength=nb)
                el = weighted_cell_stats(
                    li,
                    pw,
                    zv[pi],
                    n_cells=nb,
                    quantiles=(0.5,),
                    min_support=min_support,
                    prefix="elev",
                )
                sl = weighted_cell_stats(
                    li,
                    pw,
                    sv[pi],
                    n_cells=nb,
                    quantiles=(0.5, 0.9, 0.98),
                    thresholds=slope_thresholds,
                    min_support=min_support,
                    prefix="slope",
                )
                block = pd.concat([el, sl], axis=1)
                block["terrain_support_area_m2"] = support_area
                block.index = cell_ids
                results.append(block)
                progress(f"terrain block c{bc} r{br}: {nb} cells, {len(pi):,} pixel-cell entries")
    finally:
        for s_ in srcs:
            s_.close()
    out = pd.concat(results).sort_index()
    clipped = grid["coverage_fraction"].to_numpy() * CELL**2
    out = out.reindex(range(len(grid)))
    res = pd.DataFrame(index=grid.index)
    res["terrain_support_px"] = out["elev_support_px"].to_numpy()
    res["terrain_support_area_fraction"] = np.clip(
        out["terrain_support_area_m2"].to_numpy() / clipped, 0, None
    )
    res["elev_min_m"] = out["elev_min"].to_numpy()
    res["elev_median_m"] = out["elev_p50"].to_numpy()
    res["elev_max_m"] = out["elev_max"].to_numpy()
    res["slope_median_deg"] = out["slope_p50"].to_numpy()
    res["slope_p90_deg"] = out["slope_p90"].to_numpy()
    res["slope_p98_deg"] = out["slope_p98"].to_numpy()
    res["slope_max_raw_deg"] = out["slope_max"].to_numpy()
    for t in slope_thresholds:
        res[f"slope_gt{t:g}_fraction"] = out[f"slope_gt{t:g}_fraction"].to_numpy()
    return res
