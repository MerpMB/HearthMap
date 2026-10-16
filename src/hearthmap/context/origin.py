# ruff: noqa: E501
"""Point semantics for grid cells: GRID_CENTROID vs AOI_ANALYSIS_POINT.

A routing or distance origin must describe the part of the cell that is inside the AOI (the AOI_ANALYTICAL_FOOTPRINT = GRID_FOOTPRINT intersect AOI).
For an edge cell whose nominal centroid lies outside that footprint, the origin is a deterministic point on the clipped footprint
(shapely point-on-surface). It is geographically neutral: it is never moved toward roads, services or administrative centres.
"""

from __future__ import annotations

import numpy as np
import shapely

GRID_CENTROID = "GRID_CENTROID"
AOI_REPRESENTATIVE_POINT = "AOI_REPRESENTATIVE_POINT"
INTERIOR = 1 - 1e-9


def analysis_points(
    cells: np.ndarray, coverage: np.ndarray, aoi: shapely.Geometry
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (xy, method, in_footprint) for every cell.

    ``xy`` is an (n, 2) array. Cells fully inside the AOI and partial cells whose centroid is inside GRID_FOOTPRINT intersect AOI keep the centroid
    (method GRID_CENTROID); other partial cells get the point-on-surface of the clipped footprint (AOI_REPRESENTATIVE_POINT).
    ``in_footprint`` states whether the nominal centroid lies inside the analytical footprint.
    """
    cen = shapely.centroid(cells)
    xy = shapely.get_coordinates(cen).copy()
    method = np.full(len(cells), GRID_CENTROID, dtype=object)
    in_fp = np.ones(len(cells), dtype=bool)
    partial = np.flatnonzero(coverage < INTERIOR)
    if len(partial):
        foot = shapely.intersection(cells[partial], aoi)
        inside = shapely.contains(foot, cen[partial])
        in_fp[partial] = inside
        move = partial[~inside]
        if len(move):
            pts = shapely.point_on_surface(foot[~inside])
            xy[move] = shapely.get_coordinates(pts)
            method[move] = AOI_REPRESENTATIVE_POINT
    return xy, method, in_fp


ORIGIN_SEMANTICS = "CANONICAL_AOI_ANALYSIS_POINT"
ORIGIN_COLUMNS = (
    "grid_centroid_lon",
    "grid_centroid_lat",
    "analysis_point_lon",
    "analysis_point_lat",
    "analysis_point_method",
    "aoi_coverage_fraction_of_cell",
)


def canonical_origins(cell_ids, cells: np.ndarray, coverage: np.ndarray, aoi: shapely.Geometry):
    """THE canonical cell-origin contract for every analytical accessibility or distance computation (M2A and M2D share it).

    Returns a DataFrame indexed like ``cell_ids`` with the canonical lon/lat columns (``ORIGIN_COLUMNS``) plus the projected coordinates
    ``grid_centroid_x/y`` and ``analysis_point_x/y`` (EPSG:32647) and ``origin_semantics``. Analytical code must route and measure from
    ``analysis_point_x/y``; ``grid_centroid_x/y`` exist only as context or as an explicit historical comparison.
    """
    import pandas as pd
    from pyproj import Transformer

    xy, method, _ = analysis_points(cells, coverage, aoi)
    cen = shapely.get_coordinates(shapely.centroid(cells))
    to_ll = Transformer.from_crs("EPSG:32647", "EPSG:4326", always_xy=True)
    glon, glat = to_ll.transform(cen[:, 0], cen[:, 1])
    alon, alat = to_ll.transform(xy[:, 0], xy[:, 1])
    return pd.DataFrame(
        {
            "cell_id": np.asarray(cell_ids),
            "grid_centroid_x": cen[:, 0],
            "grid_centroid_y": cen[:, 1],
            "analysis_point_x": xy[:, 0],
            "analysis_point_y": xy[:, 1],
            "grid_centroid_lon": np.round(glon, 6),
            "grid_centroid_lat": np.round(glat, 6),
            "analysis_point_lon": np.round(alon, 6),
            "analysis_point_lat": np.round(alat, 6),
            "analysis_point_method": method,
            "aoi_coverage_fraction_of_cell": np.round(coverage, 6),
            "origin_semantics": ORIGIN_SEMANTICS,
        }
    )


def load_canonical_origins(processed_dir):
    """Canonical origins for the M1A grid (sorted by cell_id), plus the AOI polygon. Returns (origins, grid, aoi)."""
    import geopandas as gpd

    grid = (
        gpd.read_file(processed_dir / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    prov = gpd.read_file(processed_dir / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    origins = canonical_origins(
        grid["cell_id"].to_numpy(),
        grid.geometry.to_numpy(),
        grid["coverage_fraction"].to_numpy(),
        aoi,
    )
    return origins, grid, aoi
