"""M1A stage: DEM validation + terrain ANALYTICAL PREVIEW (no suitability scoring).

* Statistics are computed on the native Copernicus grid (1 arc-second, EPSG:4326
  + EGM2008 heights) inside the AOI: nodata share, min/max, anomaly counts.
* Per-cell terrain preview: every native pixel centre is projected to EPSG:32647
  and binned into its 500 m cell (no resampling). Slope is computed on the
  native grid with geodesic pixel spacing (never in degree units).
* The DEM is a DSM: canopy and buildings inflate heights and bias slope.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.features
import shapely
from pyproj import Geod

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    AOI_LONLAT,
    CANONICAL,
    PROCESSED,
    VALIDATION,
    raw_source,
    source_ref,
    write_json,
    write_layer,
)

from hearthmap.enums import Confidence
from hearthmap.spatial.transform import plan_transformation

CELL = 500.0
MAX_PLAUSIBLE_M = 2600.0  # highest summit in Thailand is ~2,565 m
GEOD = Geod(ellps="WGS84")


def main() -> int:
    dem_dir, manifest = raw_source("dem-copernicus-glo30")
    aoi = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi_ll = aoi.to_crs("EPSG:4326").union_all()
    to_utm, tr = plan_transformation("EPSG:4326", CANONICAL, area_of_interest=AOI_LONLAT)
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    key_of = {(c, r): i for i, (c, r) in enumerate(zip(grid["col"], grid["row"], strict=True))}

    n = len(grid)
    acc = {k: np.zeros(n) for k in ("count", "sum", "slope_sum", "gt15", "gt30")}
    emin, emax, smax = np.full(n, np.inf), np.full(n, -np.inf), np.full(n, -np.inf)
    nodata_cells = np.zeros(n)
    tiles, tot = [], {"pixels_in_aoi": 0, "nodata_in_aoi": 0, "below_zero": 0, "above_max": 0}
    gmin, gmax = np.inf, -np.inf
    res_info = None

    for art in manifest.artifacts:
        path = dem_dir / art.stored_path
        with rasterio.open(path) as src:
            z = src.read(1).astype("float64")
            nod = src.nodata
            tf = src.transform
            if res_info is None:
                res_info = {
                    "pixel_size_deg": [tf.a, -tf.e],
                    "crs": src.crs.to_string(),
                    "dtype": src.dtypes[0],
                    "nodata": nod,
                    "area_or_point": src.tags().get("AREA_OR_POINT"),
                }
            bounds = src.bounds
        inside = (
            rasterio.features.geometry_mask(
                [aoi_ll.intersection(shapely.box(*bounds))],
                out_shape=z.shape,
                transform=tf,
                invert=True,
            )
            if aoi_ll.intersects(shapely.box(*bounds))
            else np.zeros(z.shape, bool)
        )
        valid = np.isfinite(z) & ((z != nod) if nod is not None else True)
        zin = z[inside & valid]
        stats = {
            "tile": art.stored_path,
            "sha256": art.sha256,
            "pixels_in_aoi": int(inside.sum()),
            "nodata_in_aoi": int((inside & ~valid).sum()),
            "min_m": float(zin.min()) if zin.size else None,
            "max_m": float(zin.max()) if zin.size else None,
            "below_zero": int((zin < 0).sum()),
            "above_max_plausible": int((zin > MAX_PLAUSIBLE_M).sum()),
            "geometry": shapely.box(*bounds),
        }
        tiles.append(stats)
        for k_src, k_dst in (
            ("pixels_in_aoi", "pixels_in_aoi"),
            ("nodata_in_aoi", "nodata_in_aoi"),
            ("below_zero", "below_zero"),
            ("above_max_plausible", "above_max"),
        ):
            tot[k_dst] += stats[k_src]
        if zin.size:
            gmin, gmax = min(gmin, zin.min()), max(gmax, zin.max())

        # Slope on the native grid with geodesic spacing per row.
        rows = z.shape[0]
        lat = tf.f + tf.e * (np.arange(rows) + 0.5)
        lon0 = tf.c + tf.a * 0.5
        _, _, dx = GEOD.inv(np.full(rows, lon0), lat, np.full(rows, lon0 + tf.a), lat)
        _, _, dy = GEOD.inv(np.full(rows, lon0), lat, np.full(rows, lon0), lat + tf.e)
        zz = np.where(valid, z, np.nan)
        gy, gx = np.gradient(zz)
        slope = np.degrees(np.arctan(np.hypot(gx / dx[:, None], gy / np.abs(dy)[:, None])))

        rr, cc = np.nonzero(inside)
        lon = tf.c + tf.a * (cc + 0.5)
        latp = tf.f + tf.e * (rr + 0.5)
        x, y = to_utm.transform(lon, latp)
        col = np.floor(x / CELL).astype(np.int64)
        row = np.floor(y / CELL).astype(np.int64)
        idx = np.array([key_of.get((a, b), -1) for a, b in zip(col, row, strict=True)])
        ok = idx >= 0
        idx, zv, sv = idx[ok], zz[rr[ok], cc[ok]], slope[rr[ok], cc[ok]]
        good = np.isfinite(zv)
        np.add.at(nodata_cells, idx[~good], 1)
        ig, zg, sg = idx[good], zv[good], sv[good]
        sfin = np.isfinite(sg)
        np.add.at(acc["count"], ig, 1)
        np.add.at(acc["sum"], ig, zg)
        np.add.at(acc["slope_sum"], ig[sfin], sg[sfin])
        np.add.at(acc["gt15"], ig[sfin], (sg[sfin] > 15).astype(float))
        np.add.at(acc["gt30"], ig[sfin], (sg[sfin] > 30).astype(float))
        np.minimum.at(emin, ig, zg)
        np.maximum.at(emax, ig, zg)
        np.maximum.at(smax, ig[sfin], sg[sfin])
        print(art.stored_path, stats["pixels_in_aoi"], stats["min_m"], stats["max_m"], flush=True)

    cnt = acc["count"]
    with np.errstate(invalid="ignore", divide="ignore"):
        terrain = pd.DataFrame(
            {
                "dem_pixel_count": cnt.astype(int),
                "dem_nodata_fraction": nodata_cells / np.maximum(cnt + nodata_cells, 1),
                "elev_min_m": np.where(cnt > 0, emin, np.nan),
                "elev_mean_m": np.where(cnt > 0, acc["sum"] / cnt, np.nan),
                "elev_max_m": np.where(cnt > 0, emax, np.nan),
                "slope_mean_deg": np.where(cnt > 0, acc["slope_sum"] / cnt, np.nan),
                "slope_max_deg": np.where(cnt > 0, smax, np.nan),
                "slope_gt15_fraction": np.where(cnt > 0, acc["gt15"] / cnt, np.nan),
                "slope_gt30_fraction": np.where(cnt > 0, acc["gt30"] / cnt, np.nan),
            }
        )
    preview = gpd.GeoDataFrame(
        pd.concat([grid[["cell_id", "coverage_fraction"]], terrain], axis=1),
        geometry=grid.geometry,
        crs=grid.crs,
    )
    preview["preview_label"] = "ANALYTICAL PREVIEW - DSM-derived, not a suitability score"

    report = {
        "stage": "VALIDATED",
        "source_id": "dem-copernicus-glo30",
        "tiles": [{k: v for k, v in t.items() if k != "geometry"} for t in tiles],
        "native": res_info,
        "aoi_totals": {
            **tot,
            "nodata_share": tot["nodata_in_aoi"] / max(tot["pixels_in_aoi"], 1),
            "min_m": float(gmin),
            "max_m": float(gmax),
        },
        "cells_without_dem_pixels": int((cnt == 0).sum()),
        "cell_pixel_count_min_median_max": [int(cnt.min()), float(np.median(cnt)), int(cnt.max())],
        "transformation_for_binning": tr.operation,
    }
    write_json(report, VALIDATION / "dem.json")

    ref = source_ref("dem-copernicus-glo30", original_crs="EPSG:4326+EPSG:3855")
    write_layer(
        gpd.GeoDataFrame(
            [{k: v for k, v in t.items()} for t in tiles], geometry="geometry", crs="EPSG:4326"
        ).to_crs(CANONICAL),
        PROCESSED / "dem.gpkg",
        "dem_preview_metadata",
        sources=[ref],
        method="Per-tile footprint and AOI statistics on the native grid.",
        resolution="1 arc-second (~30 m) native",
        confidence=Confidence.MEDIUM,
        limitations=["DSM, not bare earth."],
        transformations=[tr],
    )
    write_layer(
        preview,
        PROCESSED / "dem.gpkg",
        "terrain_preview_500m",
        sources=[ref],
        method="Native pixel centres binned into 500 m cells; slope from native grid with "
        "geodesic spacing (np.gradient, one-sided at tile edges).",
        resolution="Native ~30 m pixels summarised per 500 m cell",
        confidence=Confidence.LOW,
        limitations=[
            "ANALYTICAL PREVIEW for visual QA only - not a slope suitability score.",
            "Digital SURFACE model: forest canopy and buildings inflate heights; slope is "
            "biased at canopy edges and in villages.",
            "Slope at 1-pixel tile seams uses one-sided differences.",
        ],
        transformations=[tr],
    )
    print("dem OK", report["aoi_totals"], report["cells_without_dem_pixels"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
