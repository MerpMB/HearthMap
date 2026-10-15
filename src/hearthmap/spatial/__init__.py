"""Spatial primitives: CRS handling, geometry checks, bounding boxes, grids."""

from hearthmap.spatial.bbox import BBox, within_envelope
from hearthmap.spatial.crs import (
    MissingCRSError,
    NonMetricCRSError,
    assert_metric_crs,
    crs_label,
    is_metric_projected,
    reproject,
    require_crs,
    same_crs,
)
from hearthmap.spatial.geometry import GeometryReport, check_geometries, repair_geometries
from hearthmap.spatial.grid import GridSpec, GridTooLargeError, generate_grid, snapped_extent

__all__ = [
    "BBox",
    "GeometryReport",
    "GridSpec",
    "GridTooLargeError",
    "MissingCRSError",
    "NonMetricCRSError",
    "assert_metric_crs",
    "check_geometries",
    "crs_label",
    "generate_grid",
    "is_metric_projected",
    "repair_geometries",
    "reproject",
    "require_crs",
    "same_crs",
    "snapped_extent",
    "within_envelope",
]
