"""Geometry validity checks and explicit repair."""

from __future__ import annotations

from dataclasses import dataclass, field

import geopandas as gpd
import shapely


@dataclass(frozen=True)
class GeometryReport:
    total: int
    null: int
    empty: int
    invalid: int
    # Row label -> shapely's explanation, for invalid geometries only (first 50).
    invalid_reasons: dict[object, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.null == 0 and self.empty == 0 and self.invalid == 0

    def summary(self) -> str:
        return (
            f"{self.total} geometries: {self.null} null, {self.empty} empty, {self.invalid} invalid"
        )


def check_geometries(gdf: gpd.GeoDataFrame, *, max_reasons: int = 50) -> GeometryReport:
    geoms = gdf.geometry.array
    is_null = shapely.is_missing(geoms)
    is_empty = shapely.is_empty(geoms) & ~is_null
    present = ~is_null & ~is_empty
    is_valid = shapely.is_valid(geoms)
    invalid_mask = present & ~is_valid

    reasons: dict[object, str] = {}
    for label, geom in zip(gdf.index[invalid_mask], geoms[invalid_mask], strict=True):
        if len(reasons) >= max_reasons:
            break
        reasons[label] = shapely.is_valid_reason(geom)

    return GeometryReport(
        total=len(gdf),
        null=int(is_null.sum()),
        empty=int(is_empty.sum()),
        invalid=int(invalid_mask.sum()),
        invalid_reasons=reasons,
    )


def repair_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return a copy with invalid geometries passed through ``make_valid``.

    Repair changes data. Callers must record it as a provenance step
    (operation ``repair``) and should inspect the result: ``make_valid`` can
    change geometry types (e.g. polygon -> geometry collection).
    """
    out = gdf.copy()
    geoms = out.geometry.array
    invalid = ~shapely.is_valid(geoms) & ~shapely.is_missing(geoms)
    if invalid.any():
        out.loc[invalid, out.geometry.name] = shapely.make_valid(geoms[invalid])
    return out
