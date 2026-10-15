"""Regular analysis-grid generation.

The grid is a regional decision surface (docs/architecture/spatial-model.md).
Cells are squares aligned to multiples of the cell size in a metric CRS, so a
cell id is stable across runs and region subsets for the same CRS and size.

No boundary geometry is ever created here: the caller supplies boundaries from
an acquired dataset (or, in tests, explicitly synthetic geometry).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import geopandas as gpd
import numpy as np
import shapely

from hearthmap.spatial.crs import assert_metric_crs, reproject, require_crs
from hearthmap.spatial.geometry import check_geometries

Selection = Literal["intersects", "centroid_within"]


class GridTooLargeError(ValueError):
    """The requested grid would exceed the configured cell limit."""


@dataclass(frozen=True)
class GridSpec:
    cell_size_m: float
    crs: str
    selection: Selection = "intersects"
    id_prefix: str = "G"
    max_cells: int = 2_000_000
    compute_coverage: bool = True

    def __post_init__(self) -> None:
        if not (self.cell_size_m > 0 and math.isfinite(self.cell_size_m)):
            raise ValueError(f"cell_size_m must be a positive number, got {self.cell_size_m}")
        if self.selection not in ("intersects", "centroid_within"):
            raise ValueError(f"unknown selection mode: {self.selection!r}")
        assert_metric_crs(self.crs, purpose="grid generation")


def snapped_extent(
    bounds: tuple[float, float, float, float], cell_size: float
) -> tuple[float, float, float, float]:
    """Expand ``bounds`` outward to the nearest multiples of ``cell_size``."""
    minx, miny, maxx, maxy = bounds
    return (
        math.floor(minx / cell_size) * cell_size,
        math.floor(miny / cell_size) * cell_size,
        math.ceil(maxx / cell_size) * cell_size,
        math.ceil(maxy / cell_size) * cell_size,
    )


def cell_id(prefix: str, cell_size: float, col: int, row: int) -> str:
    size = f"{cell_size:g}"
    return f"{prefix}{size}-E{col:06d}-N{row:06d}"


def generate_grid(boundary: gpd.GeoDataFrame, spec: GridSpec) -> gpd.GeoDataFrame:
    """Generate grid cells covering ``boundary``.

    Args:
        boundary: polygon layer with a CRS (any CRS; it is reprojected to ``spec.crs``).
        spec: grid parameters.

    Returns:
        GeoDataFrame in ``spec.crs`` with columns ``cell_id``, ``col``, ``row``,
        optionally ``coverage_fraction`` (share of the cell inside the boundary),
        and ``geometry``.

    Raises:
        MissingCRSError: boundary has no CRS.
        ValueError: boundary is empty or has invalid/null geometries.
        GridTooLargeError: the candidate grid would exceed ``spec.max_cells``.
    """
    require_crs(boundary, name="boundary")
    if boundary.empty:
        raise ValueError("boundary layer is empty")
    report = check_geometries(boundary)
    if not report.ok:
        raise ValueError(
            f"boundary geometries are not clean ({report.summary()}); "
            "repair explicitly (and record provenance) before generating a grid"
        )

    projected = reproject(boundary, spec.crs, name="boundary")
    area = projected.union_all()
    if area.area <= 0:
        raise ValueError("boundary has zero area; polygon geometry is required")

    size = spec.cell_size_m
    minx, miny, maxx, maxy = snapped_extent(tuple(area.bounds), size)
    col0, row0 = round(minx / size), round(miny / size)
    ncols, nrows = round((maxx - minx) / size), round((maxy - miny) / size)
    if ncols * nrows > spec.max_cells:
        raise GridTooLargeError(
            f"candidate grid has {ncols * nrows:,} cells (> max_cells={spec.max_cells:,}); "
            "check the CRS units and cell size"
        )

    cols, rows = np.meshgrid(
        np.arange(col0, col0 + ncols, dtype=np.int64),
        np.arange(row0, row0 + nrows, dtype=np.int64),
    )
    cols, rows = cols.ravel(), rows.ravel()
    x0, y0 = cols * size, rows * size
    cells = shapely.box(x0, y0, x0 + size, y0 + size)

    shapely.prepare(area)
    if spec.selection == "intersects":
        # Interiors must overlap: cells that merely share an edge/corner are excluded.
        keep = shapely.intersects(area, cells) & ~shapely.touches(area, cells)
    else:
        keep = shapely.covers(area, shapely.centroid(cells))
    cells, cols, rows = cells[keep], cols[keep], rows[keep]

    data: dict[str, object] = {
        "cell_id": [
            cell_id(spec.id_prefix, size, int(c), int(r)) for c, r in zip(cols, rows, strict=True)
        ],
        "col": cols,
        "row": rows,
    }
    if spec.compute_coverage:
        data["coverage_fraction"] = np.clip(
            shapely.area(shapely.intersection(cells, area)) / (size * size), 0.0, 1.0
        )

    return gpd.GeoDataFrame(data, geometry=cells, crs=spec.crs)
