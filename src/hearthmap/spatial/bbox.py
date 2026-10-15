"""Bounding boxes with an attached CRS, and envelope sanity checks."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
from pyproj import CRS, Transformer

from hearthmap.spatial.crs import as_crs, require_crs


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float
    crs: str

    def __post_init__(self) -> None:
        if not (self.minx <= self.maxx and self.miny <= self.maxy):
            raise ValueError(f"invalid bbox ordering: {self}")

    @classmethod
    def from_gdf(cls, gdf: gpd.GeoDataFrame, *, name: str = "layer") -> BBox:
        crs = require_crs(gdf, name=name)
        if gdf.empty:
            raise ValueError(f"{name} is empty; it has no bounding box")
        minx, miny, maxx, maxy = (float(v) for v in gdf.total_bounds)
        return cls(minx, miny, maxx, maxy, crs.to_string())

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return (self.minx, self.miny, self.maxx, self.maxy)

    def to_crs(self, target: CRS | str | int, *, densify_pts: int = 21) -> BBox:
        """Transform the box; densified edges so the result encloses the original."""
        target_crs = as_crs(target)
        transformer = Transformer.from_crs(as_crs(self.crs), target_crs, always_xy=True)
        minx, miny, maxx, maxy = transformer.transform_bounds(*self.bounds, densify_pts=densify_pts)
        return BBox(minx, miny, maxx, maxy, target_crs.to_string())

    def _aligned(self, other: BBox) -> BBox:
        return other if as_crs(other.crs).equals(as_crs(self.crs)) else other.to_crs(self.crs)

    def contains(self, other: BBox) -> bool:
        o = self._aligned(other)
        return (
            self.minx <= o.minx
            and self.miny <= o.miny
            and o.maxx <= self.maxx
            and o.maxy <= self.maxy
        )

    def intersects(self, other: BBox) -> bool:
        o = self._aligned(other)
        return not (
            o.maxx < self.minx or o.minx > self.maxx or o.maxy < self.miny or o.miny > self.maxy
        )


def within_envelope(gdf: gpd.GeoDataFrame, envelope: BBox, *, name: str = "layer") -> bool:
    """True if the layer's extent lies entirely inside ``envelope``.

    Intended to catch gross CRS mistakes (swapped axes, wrong datum or zone),
    not to test fine-grained containment.
    """
    return envelope.contains(BBox.from_gdf(gdf, name=name))
