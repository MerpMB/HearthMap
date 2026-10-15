"""Spatial primitives: CRS handling, geometry checks, bounding boxes, grids."""

from hearthmap.spatial.bbox import BBox, within_envelope
from hearthmap.spatial.crs import (
    DatumChangeError,
    MissingCRSError,
    NonMetricCRSError,
    assert_metric_crs,
    crs_label,
    datum_name,
    is_metric_projected,
    reproject,
    require_crs,
    same_crs,
)
from hearthmap.spatial.geometry import GeometryReport, check_geometries, repair_geometries
from hearthmap.spatial.grid import GridSpec, GridTooLargeError, generate_grid, snapped_extent
from hearthmap.spatial.transform import (
    TransformationSelectionError,
    plan_transformation,
    reproject_recorded,
)

__all__ = [
    "BBox",
    "DatumChangeError",
    "GeometryReport",
    "GridSpec",
    "GridTooLargeError",
    "MissingCRSError",
    "NonMetricCRSError",
    "TransformationSelectionError",
    "assert_metric_crs",
    "check_geometries",
    "crs_label",
    "datum_name",
    "generate_grid",
    "is_metric_projected",
    "plan_transformation",
    "repair_geometries",
    "reproject",
    "reproject_recorded",
    "require_crs",
    "same_crs",
    "snapped_extent",
    "within_envelope",
]
