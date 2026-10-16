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
