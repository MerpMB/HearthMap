"""Grid generation. All boundaries are SYNTHETIC fixtures, not real provinces."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from hearthmap.spatial import (
    GridSpec,
    GridTooLargeError,
    MissingCRSError,
    NonMetricCRSError,
    generate_grid,
    reproject,
    snapped_extent,
)
from tests.fixtures import synthetic

SPEC = GridSpec(cell_size_m=500, crs="EPSG:32647")


def test_aligned_square_produces_exact_cells():
    grid = generate_grid(synthetic.aligned_square(2000), SPEC)
    assert len(grid) == 16  # 4 x 4; touching-only neighbours are not intersecting interiors
    assert grid.crs.to_epsg() == 32647
    assert grid.geometry.area.eq(250_000).all()
    assert grid["coverage_fraction"].eq(1.0).all()


def test_cell_ids_are_unique_stable_and_absolute():
    g1 = generate_grid(synthetic.aligned_square(2000), SPEC)
    g2 = generate_grid(synthetic.aligned_square(2000), SPEC)
    assert g1["cell_id"].is_unique
    assert list(g1["cell_id"]) == list(g2["cell_id"])
    # Origin cell: easting 500000/500 = 1000, northing 2000000/500 = 4000
    assert "G500-E001000-N004000" in set(g1["cell_id"])


def test_ids_consistent_across_overlapping_boundaries():
    small = generate_grid(synthetic.aligned_square(1000), SPEC)
    large = generate_grid(synthetic.aligned_square(2000), SPEC)
    assert set(small["cell_id"]) <= set(large["cell_id"])


def test_cells_are_aligned_to_cell_size():
    grid = generate_grid(synthetic.offset_square(1000, 250), SPEC)
    minx, miny, _, _ = grid.geometry.bounds.min()
    assert minx % 500 == 0 and miny % 500 == 0


def test_offset_square_intersects_selection_and_coverage():
    # 1 km square offset by 250 m touches a 3x3 block of 500 m cells.
    grid = generate_grid(synthetic.offset_square(1000, 250), SPEC)
    assert len(grid) == 9
    by_cov = sorted(grid["coverage_fraction"].round(4))
    assert by_cov == [0.25] * 4 + [0.5] * 4 + [1.0]
    total = (grid["coverage_fraction"] * 250_000).sum()
    assert total == pytest.approx(1_000_000)


def test_offset_square_centroid_selection():
    spec = GridSpec(cell_size_m=500, crs="EPSG:32647", selection="centroid_within")
    grid = generate_grid(synthetic.offset_square(1000, 250), spec)
    # Centroids at +250/+750/+1250 offsets: only those within [250, 1250] qualify,
    # boundary points included (covers) -> 3 x 3.
    assert len(grid) == 9
    spec_small = GridSpec(cell_size_m=500, crs="EPSG:32647", selection="centroid_within")
    grid_small = generate_grid(synthetic.offset_square(600, 300), spec_small)
    assert len(grid_small) == 1


def test_l_shape_excludes_notch():
    grid = generate_grid(synthetic.l_shape(), SPEC)
    # Area 5 km^2 = 20 full cells; notch (2x2 km = 16 cells) excluded.
    assert len(grid) == 20
    assert grid["coverage_fraction"].eq(1.0).all()


def test_multiple_features_are_unioned():
    grid = generate_grid(synthetic.two_regions(), SPEC)
    assert len(grid) == 8
    assert grid["cell_id"].is_unique


def test_geographic_input_is_reprojected():
    geo = reproject(synthetic.aligned_square(2000), "EPSG:4326")
    grid = generate_grid(geo, SPEC)
    assert grid.crs.to_epsg() == 32647
    # Reprojection round-off can leave sub-millimetre slivers in neighbouring
    # cells; coverage_fraction makes them visible instead of hiding them.
    assert (grid["coverage_fraction"] > 0.999).sum() == 16
    assert grid["coverage_fraction"].sum() == pytest.approx(16, abs=0.01)


def test_configurable_resolution():
    spec = GridSpec(cell_size_m=250, crs="EPSG:32647")
    grid = generate_grid(synthetic.aligned_square(2000), spec)
    assert len(grid) == 64
    assert grid["cell_id"].str.startswith("G250-").all()


def test_missing_crs_rejected():
    gdf = synthetic.aligned_square().set_crs(None, allow_override=True)
    with pytest.raises(MissingCRSError):
        generate_grid(gdf, SPEC)


def test_invalid_boundary_rejected_not_silently_fixed():
    with pytest.raises(ValueError, match="repair explicitly"):
        generate_grid(synthetic.bowtie(), SPEC)


def test_empty_boundary_rejected():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:32647")
    with pytest.raises(ValueError, match="empty"):
        generate_grid(empty, SPEC)


def test_point_boundary_rejected():
    pts = gpd.GeoDataFrame(geometry=[Point(500_000, 2_000_000)], crs="EPSG:32647")
    with pytest.raises(ValueError, match="zero area"):
        generate_grid(pts, SPEC)


def test_grid_spec_requires_metric_crs():
    with pytest.raises(NonMetricCRSError):
        GridSpec(cell_size_m=500, crs="EPSG:4326")


def test_grid_spec_rejects_bad_size():
    with pytest.raises(ValueError):
        GridSpec(cell_size_m=0, crs="EPSG:32647")


def test_max_cells_guard():
    spec = GridSpec(cell_size_m=500, crs="EPSG:32647", max_cells=10)
    with pytest.raises(GridTooLargeError):
        generate_grid(synthetic.aligned_square(2000), spec)


def test_snapped_extent():
    assert snapped_extent((250, 260, 1250, 1240), 500) == (0, 0, 1500, 1500)
    assert snapped_extent((0, 0, 1000, 1000), 500) == (0, 0, 1000, 1000)
