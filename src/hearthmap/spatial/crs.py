"""CRS validation and reprojection.

Policy (ADR-0002): source CRS is never guessed; measurement happens only in a
projected, metre-based CRS.
"""

from __future__ import annotations

import geopandas as gpd
from pyproj import CRS

WEB_MERCATOR_EPSG_CODES = frozenset({3857, 900913, 3785, 102100, 102113})


class MissingCRSError(ValueError):
    """A layer has no CRS metadata; we refuse to assume one."""


class DatumChangeError(ValueError):
    """A reprojection would change datum; it must go through ``reproject_recorded``."""


class NonMetricCRSError(ValueError):
    """An operation that measures distance/area was given a non-metric CRS."""


def as_crs(value: CRS | str | int) -> CRS:
    return CRS.from_user_input(value)


def is_metric_projected(crs: CRS | str | int) -> bool:
    """True if ``crs`` is projected and every axis is measured in metres."""
    crs = as_crs(crs)
    if not crs.is_projected:
        return False
    units = {axis.unit_name.lower() for axis in crs.axis_info}
    return bool(units) and units <= {"metre", "meter"}


def assert_metric_crs(crs: CRS | str | int, *, purpose: str = "measurement") -> CRS:
    """Raise unless ``crs`` is a metre-based projected CRS suitable for ``purpose``."""
    crs = as_crs(crs)
    if not is_metric_projected(crs):
        raise NonMetricCRSError(
            f"{purpose} requires a projected CRS in metres; got {crs.to_string()}"
        )
    if crs.to_epsg() in WEB_MERCATOR_EPSG_CODES:
        raise NonMetricCRSError(
            f"{purpose} must not use Web Mercator ({crs.to_string()}): scale is distorted"
        )
    return crs


def require_crs(gdf: gpd.GeoDataFrame, *, name: str = "layer") -> CRS:
    """Return the layer's CRS or raise :class:`MissingCRSError`."""
    if gdf.crs is None:
        raise MissingCRSError(
            f"{name} has no CRS. Determine the true CRS (and datum - e.g. WGS 84 vs "
            "Indian 1975) from the publisher's metadata; do not guess."
        )
    return gdf.crs


def same_crs(a: CRS | str | int, b: CRS | str | int) -> bool:
    return as_crs(a).equals(as_crs(b))


def datum_name(crs: CRS | str | int) -> str:
    geod = as_crs(crs).geodetic_crs
    return geod.datum.name if geod is not None and geod.datum is not None else "unknown"


def reproject(
    gdf: gpd.GeoDataFrame, target: CRS | str | int, *, name: str = "layer"
) -> gpd.GeoDataFrame:
    """Reproject within one datum (pure conversion); returns a copy.

    Raises :class:`MissingCRSError` without a source CRS and
    :class:`DatumChangeError` if the datum would change: datum
    transformations must use :func:`hearthmap.spatial.transform.reproject_recorded`
    so the chosen operation and its accuracy are recorded.
    """
    source = require_crs(gdf, name=name)
    target_crs = as_crs(target)
    if source.equals(target_crs):
        return gdf.copy()
    if datum_name(source) != datum_name(target_crs):
        raise DatumChangeError(
            f"{name}: {crs_label(source)} ({datum_name(source)}) -> {crs_label(target_crs)} "
            f"({datum_name(target_crs)}) changes datum; use reproject_recorded()"
        )
    return gdf.to_crs(target_crs)


def crs_label(crs: CRS | str | int | None) -> str | None:
    """Short, stable label for provenance ("EPSG:32647" when possible)."""
    if crs is None:
        return None
    crs = as_crs(crs)
    authority = crs.to_authority()
    if authority:
        return f"{authority[0]}:{authority[1]}"
    return crs.to_string()
