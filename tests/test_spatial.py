"""CRS, geometry and bounding-box utilities. All geometry is SYNTHETIC."""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import Point

from hearthmap.spatial import (
    BBox,
    DatumChangeError,
    MissingCRSError,
    NonMetricCRSError,
    assert_metric_crs,
    check_geometries,
    crs_label,
    is_metric_projected,
    repair_geometries,
    reproject,
    reproject_recorded,
    require_crs,
    same_crs,
    within_envelope,
)
from hearthmap.validation import validate_layer
from tests.fixtures import synthetic

ENVELOPE = BBox(97.0, 16.5, 101.5, 21.0, crs="EPSG:4326")


# ------------------------------------------------------------ CRS


@pytest.mark.parametrize(
    ("crs", "expected"),
    [("EPSG:32647", True), ("EPSG:24047", True), ("EPSG:4326", False), ("EPSG:3857", True)],
)
def test_is_metric_projected(crs, expected):
    assert is_metric_projected(crs) is expected


def test_assert_metric_rejects_geographic_and_web_mercator():
    assert assert_metric_crs("EPSG:32647").to_epsg() == 32647
    with pytest.raises(NonMetricCRSError, match="metres"):
        assert_metric_crs("EPSG:4326")
    with pytest.raises(NonMetricCRSError, match="Web Mercator"):
        assert_metric_crs("EPSG:3857")


def test_require_crs_refuses_missing_crs():
    gdf = gpd.GeoDataFrame(geometry=[Point(0, 0)])
    with pytest.raises(MissingCRSError, match="do not guess"):
        require_crs(gdf, name="SYNTHETIC")


def test_reproject_roundtrip_preserves_geometry():
    square = synthetic.aligned_square()
    back = reproject(reproject(square, "EPSG:4326"), "EPSG:32647")
    assert same_crs(back.crs, "EPSG:32647")
    assert back.geometry.iloc[0].equals_exact(square.geometry.iloc[0], tolerance=1e-3)


def test_reproject_same_crs_returns_copy():
    square = synthetic.aligned_square()
    out = reproject(square, "EPSG:32647")
    assert out is not square
    assert out.geometry.iloc[0].equals(square.geometry.iloc[0])


def test_reproject_refuses_missing_crs():
    with pytest.raises(MissingCRSError):
        reproject(gpd.GeoDataFrame(geometry=[Point(0, 0)]), "EPSG:4326")


def test_indian_1975_is_not_silently_equal_to_wgs84_utm():
    # The classic Thai datum trap: same zone, different datum.
    assert not same_crs("EPSG:24047", "EPSG:32647")
    pt = gpd.GeoDataFrame(geometry=[Point(500_000, 2_000_000)], crs="EPSG:24047")
    with pytest.raises(DatumChangeError, match="reproject_recorded"):
        reproject(pt, "EPSG:32647")  # a datum change may never happen silently
    moved, record = reproject_recorded(pt, "EPSG:32647")
    shift = moved.geometry.iloc[0].distance(Point(500_000, 2_000_000))
    assert shift > 50  # datum shift is far larger than a rounding error
    assert record.datum_change


def test_crs_label():
    assert crs_label("EPSG:32647") == "EPSG:32647"
    assert crs_label(None) is None


def test_area_differs_between_utm_and_web_mercator():
    square = synthetic.aligned_square(1000)
    utm_area = square.geometry.area.iloc[0]
    merc_area = reproject(square, "EPSG:3857").geometry.area.iloc[0]
    assert utm_area == pytest.approx(1_000_000)
    assert merc_area / utm_area > 1.1  # why measurement in 3857 is forbidden


# ------------------------------------------------------------ geometry


def test_check_geometries_flags_invalid():
    report = check_geometries(synthetic.bowtie())
    assert report.invalid == 1
    assert not report.ok
    assert "Self-intersection" in next(iter(report.invalid_reasons.values()))


def test_check_geometries_flags_null_and_empty():
    gdf = gpd.GeoDataFrame(geometry=[None, Point(), Point(1, 1)], crs="EPSG:32647")
    report = check_geometries(gdf)
    assert (report.null, report.empty, report.invalid) == (1, 1, 0)


def test_repair_geometries_fixes_bowtie_without_mutating_input():
    bad = synthetic.bowtie()
    fixed = repair_geometries(bad)
    assert check_geometries(fixed).ok
    assert not check_geometries(bad).ok


# ------------------------------------------------------------ bbox / envelope


def test_bbox_transform_and_contains():
    square = synthetic.aligned_square()
    box_utm = BBox.from_gdf(square)
    box_geo = box_utm.to_crs("EPSG:4326")
    assert 98.9 < box_geo.minx < 99.1 and 18.0 < box_geo.miny < 18.2
    assert ENVELOPE.contains(box_utm)  # compared across CRSs
    assert within_envelope(square, ENVELOPE)


def test_envelope_catches_swapped_axes():
    lon, lat = 99.0, 18.5
    swapped = gpd.GeoDataFrame(geometry=[Point(lat, lon)], crs="EPSG:4326")
    assert not within_envelope(swapped, ENVELOPE)


def test_envelope_catches_mislabelled_crs():
    # UTM metres mislabelled as degrees would be wildly outside the envelope.
    square = synthetic.aligned_square().set_crs("EPSG:4326", allow_override=True)
    assert not ENVELOPE.intersects(BBox.from_gdf(square))


def test_bbox_rejects_bad_ordering():
    with pytest.raises(ValueError):
        BBox(10, 0, 0, 10, crs="EPSG:4326")


# ------------------------------------------------------------ layer validation


def test_validate_layer_ok():
    report = validate_layer(synthetic.aligned_square(), name="SYNTHETIC", envelope=ENVELOPE)
    assert report.ok, report.summary()
    assert report.crs == "EPSG:32647"


def test_validate_layer_reports_all_problems():
    gdf = synthetic.bowtie().set_crs(None, allow_override=True)
    report = validate_layer(gdf, envelope=ENVELOPE)
    assert not report.ok
    assert any("no CRS" in e for e in report.errors)
    assert any("geometry" in e for e in report.errors)


def test_validate_layer_warns_on_geographic_crs():
    gdf = reproject(synthetic.aligned_square(), "EPSG:4326")
    report = validate_layer(gdf, envelope=ENVELOPE)
    assert report.ok
    assert any("degrees" in w for w in report.warnings)
