"""SYNTHETIC test geometry. NOT real boundaries of any place.

Shapes are simple squares/L-shapes placed at round UTM 47N coordinates so they
fall inside the study-area sanity envelope. They exist only to exercise code.
Every GeoDataFrame produced here carries ``synthetic=True`` and a name starting
with ``SYNTHETIC``.
"""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import Polygon, box

UTM47N = "EPSG:32647"

# A round-number origin (~99.0E, ~18.1N). Chosen for convenience, not meaning.
ORIGIN_X = 500_000.0
ORIGIN_Y = 2_000_000.0


def _frame(geoms: list[Polygon], names: list[str], crs: str = UTM47N) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"name": names, "synthetic": [True] * len(geoms)}, geometry=geoms, crs=crs
    )


def aligned_square(size_m: float = 2_000.0) -> gpd.GeoDataFrame:
    """Square whose corners sit exactly on 500 m grid lines."""
    geom = box(ORIGIN_X, ORIGIN_Y, ORIGIN_X + size_m, ORIGIN_Y + size_m)
    return _frame([geom], ["SYNTHETIC aligned square"])


def offset_square(size_m: float = 1_000.0, offset_m: float = 250.0) -> gpd.GeoDataFrame:
    """Square shifted off the grid lines, so it straddles cells."""
    x, y = ORIGIN_X + offset_m, ORIGIN_Y + offset_m
    return _frame([box(x, y, x + size_m, y + size_m)], ["SYNTHETIC offset square"])


def l_shape() -> gpd.GeoDataFrame:
    """L-shaped polygon (3 km x 3 km with the top-right 2 km x 2 km removed)."""
    x, y = ORIGIN_X, ORIGIN_Y
    geom = Polygon(
        [
            (x, y),
            (x + 3000, y),
            (x + 3000, y + 1000),
            (x + 1000, y + 1000),
            (x + 1000, y + 3000),
            (x, y + 3000),
        ]
    )
    return _frame([geom], ["SYNTHETIC L-shape"])


def two_regions() -> gpd.GeoDataFrame:
    """Two adjacent synthetic 'regions' sharing an edge."""
    a = box(ORIGIN_X, ORIGIN_Y, ORIGIN_X + 1000, ORIGIN_Y + 1000)
    b = box(ORIGIN_X + 1000, ORIGIN_Y, ORIGIN_X + 2000, ORIGIN_Y + 1000)
    return _frame([a, b], ["SYNTHETIC region A", "SYNTHETIC region B"])


def bowtie() -> gpd.GeoDataFrame:
    """Self-intersecting (invalid) polygon."""
    x, y = ORIGIN_X, ORIGIN_Y
    geom = Polygon([(x, y), (x + 1000, y + 1000), (x + 1000, y), (x, y + 1000)])
    return _frame([geom], ["SYNTHETIC bowtie (invalid)"])
