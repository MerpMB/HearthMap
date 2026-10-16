# ruff: noqa: E501
"""M2D.1d: edge-cell analysis origin and local-vs-external context semantics."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import shapely
import yaml

from hearthmap.context.origin import AOI_REPRESENTATIVE_POINT, GRID_CENTROID, analysis_points
from hearthmap.context.semantics import (
    COLUMN_LINEAGE_RULES,
    EXTERNAL_ACCESS_CONTEXT,
    EXTERNAL_INFLUENCE_CONTEXT,
    LOCAL_AOI_EVIDENCE,
    forbidden_columns,
)
from hearthmap.context.settlement import area_fraction, clip_polygons_to_aoi
from hearthmap.family import load_config
from hearthmap.family.evaluability import load_plan

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
needs_artifact = pytest.mark.skipif(not ART.exists(), reason="run scripts/m2d/build_context.py")
RULES = {pat: lin for pat, lin in COLUMN_LINEAGE_RULES}


# -- analysis points (pure geometry) ---------------------------------------------------------------------------
def _cells():
    interior = shapely.box(0, 0, 500, 500)
    edge_valid = shapely.box(
        1000, 0, 1500, 500
    )  # AOI covers its left 60% -> centroid (1250) is inside
    edge_out = shapely.box(
        2000, 0, 2500, 500
    )  # AOI covers only the left 20% -> centroid (2250) is outside
    aoi = shapely.box(-10, -10, 1400, 600).union(shapely.box(1990, -10, 2100, 600))
    cells = np.array([interior, edge_valid, edge_out])
    cov = np.array(
        [
            1.0,
            shapely.intersection(edge_valid, aoi).area / 250000,
            shapely.intersection(edge_out, aoi).area / 250000,
        ]
    )
    return cells, cov, aoi


def test_interior_and_valid_edge_cells_keep_their_centroid_and_outside_centroids_move_inside():
    cells, cov, aoi = _cells()
    xy, method, in_fp = analysis_points(cells, cov, aoi)
    assert method.tolist() == [GRID_CENTROID, GRID_CENTROID, AOI_REPRESENTATIVE_POINT]
    assert np.allclose(xy[0], [250, 250]) and np.allclose(xy[1], [1250, 250])  # untouched
    assert in_fp.tolist() == [True, True, False]
    foot = shapely.intersection(cells[2], aoi)
    p = shapely.points(xy[2])
    assert shapely.contains(foot, p)  # inside GRID_FOOTPRINT intersect AOI
    assert not shapely.contains(
        foot, shapely.centroid(cells[2])
    )  # the nominal centroid is NOT a valid analytical origin
    assert xy[2][0] < 2100  # lies in the AOI part (x 2000..2100)


def test_analysis_point_is_deterministic_and_geographically_neutral():
    cells, cov, aoi = _cells()
    a = analysis_points(cells, cov, aoi)[0]
    b = analysis_points(cells.copy(), cov.copy(), aoi)[0]
    assert np.array_equal(a, b)
    src = (ROOT / "src/hearthmap/context/origin.py").read_text("utf-8")
    assert "point_on_surface" in src
    imports = [ln for ln in src.splitlines() if ln.startswith(("import ", "from "))]
    assert set(imports) <= {
        "from __future__ import annotations",
        "import numpy as np",
        "import shapely",
    }  # no network, facility or admin data can influence the point


def test_the_build_uses_the_analysis_point_as_the_only_routing_and_distance_origin():
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    assert "cen, ap_method, _ = analysis_points(" in text
    assert "snap(cen, net.xy, routable)" in text and "euclid_counts(cen_pts" in text
    assert (
        "snap(grid_cen_xy, net.xy, routable)" in text
    )  # the nominal centroid appears ONLY as the saved comparison, never as the artifact origin
    assert text.count("grid_cen_xy") <= 6


# -- built artifact ------------------------------------------------------------------------------------------------
@needs_artifact
def test_every_analysis_point_lies_inside_its_aoi_analytical_footprint():
    import geopandas as gpd
    from pyproj import Transformer

    df = pd.read_parquet(ART)
    prov = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    grid = (
        gpd.read_file(ROOT / "data/processed/m1a/grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    assert (grid["cell_id"].to_numpy() == df["cell_id"].to_numpy()).all()
    partial = np.flatnonzero(df["coverage_fraction"].to_numpy() < 1 - 1e-9)
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True).transform(
        df["analysis_point_lon"].to_numpy()[partial], df["analysis_point_lat"].to_numpy()[partial]
    )
    foot = shapely.intersection(grid.geometry.to_numpy()[partial], aoi)
    pts = shapely.points(np.column_stack([x, y]))
    assert shapely.dwithin(
        foot, pts, 0.5
    ).all()  # inside (0.5 m tolerance for the 1e-6 degree rounding of the stored coordinates)


@needs_artifact
def test_interior_cells_keep_the_grid_centroid_and_the_method_vocabulary_is_closed():
    df = pd.read_parquet(ART)
    interior = df["coverage_fraction"] >= 1 - 1e-9
    assert (df.loc[interior, "analysis_point_method"] == GRID_CENTROID).all()
    assert np.array_equal(
        df.loc[interior, "analysis_point_lon"], df.loc[interior, "grid_centroid_lon"]
    )
    assert np.array_equal(
        df.loc[interior, "analysis_point_lat"], df.loc[interior, "grid_centroid_lat"]
    )
    assert set(df["analysis_point_method"]) == {GRID_CENTROID, AOI_REPRESENTATIVE_POINT}
    moved = df["analysis_point_method"] == AOI_REPRESENTATIVE_POINT
    assert 0 < moved.sum() < 4729 and (df.loc[moved, "coverage_fraction"] < 1).all()
    same = (df.loc[moved, "analysis_point_lon"] == df.loc[moved, "grid_centroid_lon"]) & (
        df.loc[moved, "analysis_point_lat"] == df.loc[moved, "grid_centroid_lat"]
    )
    assert not same.any()  # the original centroid is preserved separately and never overwritten


@needs_artifact
def test_interior_accessibility_is_unchanged_and_scope_is_measured():
    s = json.loads((ROOT / "outputs/m2d/edge-origin-summary.json").read_text("utf-8"))
    assert s["interior_cells_with_changed_origin"] == 0
    assert (
        s["interior_cells_with_any_changed_service_time"] == 0
        and s["interior_snap_distance_changed"] == 0
    )
    assert (
        s["partial_cells"]
        == s["partial_cells_with_centroid_inside_aoi_footprint"]
        + s["partial_cells_with_centroid_outside_aoi_footprint"]
    )
    assert (
        s["cells_whose_routing_origin_changes"]
        == s["partial_cells_with_centroid_outside_aoi_footprint"]
        == s["cells_whose_euclidean_distance_origin_changes"]
    )
    assert (
        "administrative_fallback_cells_m2d1b_for_comparison" in s
    )  # measured separately, not assumed equal


@needs_artifact
def test_routing_parameters_remain_frozen():
    df = pd.read_parquet(ART)
    cfg = load_config()
    assert (
        hashlib.sha256(json.dumps(cfg["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
        == "5c35e98882c3ac62"
    )
    assert cfg["travel_time"]["max_snap_distance_m"] == 1000
    assert df["routing_config_fingerprint"].eq("5c35e98882c3ac62").all()
    assert (
        df.loc[df["road_snap_distance_m"] <= 999.9, "road_access_context"]
        == "CONNECTED_ROAD_WITHIN_SNAP_DISTANCE"
    ).all()


@needs_artifact
def test_the_checked_cell_no_longer_routes_from_nan():
    t = pd.read_csv(ROOT / "outputs/m2d-review/edge-cell-analysis-origin.csv")
    c = t[t["grid_id"] == "G500-E001332-N004224"].iloc[0]
    assert c["analysis_point_method"] == AOI_REPRESENTATIVE_POINT and (
        c["province"],
        c["district"],
    ) == ("Phayao", "Pong")
    assert (c["grid_centroid_lon"], c["grid_centroid_lat"]) != (
        c["analysis_point_lon"],
        c["analysis_point_lat"],
    )
    assert c["aoi_coverage_fraction_of_cell"] < 0.2
    assert forbidden_columns(t.columns) == []


# -- local vs external semantics ---------------------------------------------------------------------------------
def test_semantic_classes_are_assigned_to_the_local_and_external_fields():
    assert (
        RULES[r"^osm_service_poi_"]["evidence_type"] == "LOCAL_SERVICE_PRESENCE"
        and RULES[r"^osm_service_poi_"]["semantic_class"] == LOCAL_AOI_EVIDENCE
    )
    svc = next(v for k, v in RULES.items() if k.startswith(r"^(service_|drive_time"))
    assert (
        svc["evidence_type"].startswith("ACCESSIBLE_SERVICE_DESTINATION")
        and svc["semantic_class"] == EXTERNAL_ACCESS_CONTEXT
    )
    assert "absent from the extract" in svc["note"] and svc["origin"] == "AOI_ANALYSIS_POINT"
    road = RULES[r"^road_(length|intensity)_"]
    assert (
        road["evidence_type"] == "LOCAL_ROAD_CONTEXT"
        and road["semantic_class"] == LOCAL_AOI_EVIDENCE
        and "ROUTING_NETWORK_EXTENT" in road["note"]
    )
    poly = RULES[r"^osm_(industrial|quarry)_.*polygon_fraction_of_nominal_grid_cell_aoi_clipped$"]
    assert (
        poly["semantic_class"] == LOCAL_AOI_EVIDENCE
        and poly["evidence_type"] == "LOCAL_POLYGON_OCCUPANCY_AOI_CLIPPED"
    )
    for pat in (r"^osm_(industrial|works)_", r"^osm_quarry_", r"^nightlife_"):
        assert (
            RULES[pat]["semantic_class"] == EXTERNAL_INFLUENCE_CONTEXT
            and RULES[pat]["origin"] == "AOI_ANALYSIS_POINT"
        )
    assert "no nuisance distance or buffer is activated" in RULES[r"^osm_quarry_"]["note"]


def test_local_polygon_occupancy_cannot_come_from_a_polygon_wholly_outside_the_aoi():
    aoi = shapely.box(0, 0, 1000, 1000)
    cell = np.array([shapely.box(800, 0, 1300, 500)])  # an edge cell: AOI covers x 800..1000
    outside_only = np.array(
        [shapely.box(1100, 100, 1250, 300)]
    )  # lies in the part of the cell that is outside the AOI
    assert clip_polygons_to_aoi(outside_only, aoi).size == 0
    assert area_fraction(cell, clip_polygons_to_aoi(outside_only, aoi), 1)[0] == 0.0
    # the nominal-cell view WITHOUT clipping would have counted it (this is the error being prevented)
    assert area_fraction(cell, outside_only, 1)[0] > 0
    straddling = np.array([shapely.box(900, 100, 1100, 300)])
    clipped = clip_polygons_to_aoi(straddling, aoi)
    assert area_fraction(cell, clipped, 1)[0] == pytest.approx(
        (100 * 200) / 250000
    )  # only the in-AOI half is local


def test_nominal_grid_intensity_is_never_labelled_as_aoi_footprint_density():
    text = " ".join(p for p, _ in COLUMN_LINEAGE_RULES)
    assert "density_within_aoi_footprint" not in text and "fraction_of_aoi_footprint" not in text
    inten = next(v for k, v in RULES.items() if k == r"^(population|built)_.*intensity_")
    assert (
        inten["evidence_type"] == "INTENSITY_PER_NOMINAL_GRID_CELL"
        and "nominal 0.25 km2 grid cell" in inten["denominator"]
        and "not a density within the AOI footprint" in inten["note"]
    )
    mass = RULES[r"^(population_worldpop2025_mass_aoi_clipped|built_ghsl2020_m2_aoi_clipped)$"]
    assert (
        mass["evidence_type"] == "AOI_CLIPPED_MASS"
        and "POPULATION_MASS_AOI_CLIPPED" in mass["mass_class"]
        and "BUILT_UP_M2_AOI_CLIPPED" in mass["mass_class"]
    )
    for path in list((ROOT / "scripts/m2d").glob("*.py")) + list(
        (ROOT / "src/hearthmap/context").glob("*.py")
    ):
        t = path.read_text("utf-8")
        assert not re.search(r"(population|built)_[a-z0-9_]*density_per_km2", t), (
            path.name
        )  # the old ambiguous names are gone
        assert "value / tiny" not in t.lower() and "sliver_area" not in t


@needs_artifact
def test_artifact_column_names_state_mass_intensity_and_locality():
    df = pd.read_parquet(ART)
    cols = set(df.columns)
    assert {
        "population_worldpop2025_mass_aoi_clipped",
        "built_ghsl2020_m2_aoi_clipped",
        "population_worldpop2025_intensity_per_nominal_grid_cell_km2",
        "built_ghsl2020_intensity_fraction_of_nominal_grid_cell",
    } <= cols
    assert not [c for c in cols if re.search(r"(population|built|road)_.*density", c)]
    assert {
        "road_length_osm_drivable_km_aoi_clipped_500m",
        "road_length_osm_drivable_km_full_cell_context",
        "osm_service_poi_local_count_aoi_clipped_500m",
    } <= cols
    lin = json.loads(
        (ROOT / "outputs/m2d/regional-context-evidence.columns.json").read_text("utf-8")
    )
    assert set(lin) == cols
    assert (
        lin["road_length_osm_drivable_km_full_cell_context"]["evidence_type"]
        == "FULL_CELL_CONTEXT_ONLY"
    )
    assert forbidden_columns(df.columns) == []


@needs_artifact
def test_local_road_length_is_clipped_to_the_aoi_while_the_routing_network_extends_beyond_it():
    import geopandas as gpd

    df = pd.read_parquet(ART)
    interior = df["coverage_fraction"] >= 1 - 1e-9
    loc, full = (
        df["road_length_osm_drivable_km_aoi_clipped_500m"],
        df["road_length_osm_drivable_km_full_cell_context"],
    )
    assert (loc <= full + 1e-9).all()
    assert np.allclose(
        loc[interior], full[interior], atol=0.002
    )  # interior cells: local == whole cell (midpoint rule; rounding to 3 decimals)
    assert (
        loc[~interior] < full[~interior] - 1e-9
    ).any()  # some edge cell had road outside the AOI
    prov = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    z = np.load(ROOT / "data/processed/m2a/network.npz")
    outside = ~shapely.contains_xy(aoi, z["xy"][:, 0], z["xy"][:, 1])
    assert (
        outside.sum() > 1000
    )  # the routing graph is not clipped to the AOI: routes can cross the boundary
    assert "ROUTING_NETWORK_EXTENT" in df["evidence_road_semantics"].iloc[0]


@needs_artifact
def test_local_poi_counts_exclude_outside_aoi_pois_while_routing_may_use_them():
    import geopandas as gpd

    df = pd.read_parquet(ART)
    prov = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    sv = pd.read_csv(ROOT / "data/processed/m2d/service_pois.csv")
    inside = shapely.contains_xy(aoi, sv["x"].to_numpy(), sv["y"].to_numpy())
    total_local = int(df["osm_service_poi_local_count_aoi_clipped_500m"].sum())
    assert (
        total_local <= int(inside.sum()) < len(sv) + 1
    )  # at most the POIs inside the AOI (grid cells hold every AOI point)
    assert total_local >= int(inside.sum()) - 5
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    assert (
        "sv_in_aoi" in text and "pidx[(pidx >= 0) & sv_in_aoi]" in text
    )  # local presence filters by the AOI
    assert (
        'if r["routed"]:' in text and "comp_nodes.setdefault" in text
    )  # routing destinations are NOT filtered by the AOI
    assert (
        "ACCESSIBLE_SERVICE_DESTINATION" in df["evidence_service_semantics"].iloc[0]
        and "LOCAL_SERVICE_PRESENCE" in df["evidence_service_semantics"].iloc[0]
    )
    assert df["service_components_with_a_route"].max() == 8


@needs_artifact
def test_local_industrial_and_quarry_occupancy_is_aoi_clipped_in_the_artifact():
    df = pd.read_parquet(ART)
    for c in (
        "osm_industrial_landuse_polygon_fraction_of_nominal_grid_cell_aoi_clipped",
        "osm_quarry_polygon_fraction_of_nominal_grid_cell_aoi_clipped",
    ):
        assert df[c].between(0, 1).all()
        edge = df["coverage_fraction"] < 1
        assert (
            df.loc[edge, c] <= df.loc[edge, "coverage_fraction"] + 1e-3
        ).all()  # occupancy cannot exceed the AOI part of the cell
    assert "EXTERNAL_INFLUENCE_CONTEXT" in df["osm_industrial_geometry_basis"].iloc[0]


# -- M1A overlay audit -------------------------------------------------------------------------------------------
@needs_artifact
def test_m1a_overlay_audit_is_reported_and_nothing_downstream_consumes_it():
    p = ROOT / "outputs/m2d/tables/m1a-overlay-edge-audit.csv"
    if not p.exists():
        pytest.skip("run scripts/m2d/m1a_overlay_audit.py")
    a = pd.read_csv(p)
    assert len(a) == 4 and a["consumed_by_active_downstream_decision"].str.startswith("NO").all()
    assert (
        a["partial_cells_with_feature_in_full_cell"]
        >= a["partial_cells_affected_ONLY_by_features_outside_the_aoi"]
    ).all()
    for sub in ("scripts/m1b", "scripts/m1c", "scripts/m1d", "scripts/m1e", "scripts/m2a"):
        for f in (ROOT / sub).rglob("*.py"):
            assert "screening_overlays_500m" not in f.read_text("utf-8"), (
                f.name
            )  # no active decision reads the M1A overlay table


# -- gates --------------------------------------------------------------------------------------------------------
def test_no_scoring_and_hazards_and_requirements_stay_immutable():
    assert load_plan()["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    pinned = {
        "hazard": "b04fb8cc9a256b3eb9d0384e7933bed790fec590a3441af36df2007b7cfe68fe",
        "hazard-policy": "a270dc3b5618b89a14a44dc3ff12da8e0a1cbd64b657191b03233845f6fb8acd",
        "hazard-integration": "0213e85349e77c20ec47127e30e59357d3767627bebc463228d6cfc926b05dd7",
        "flood-fusion": "5d908eafe965fdbe445a5eabaa0d733a866f690c1c2335870de4496b26463f44",
        "seismic-evidence": "649a7d141c693ed9d737877e856e74a0de75e69253871d013576a5a5d4b05c44",
        "family-requirements": "a4673aa9aa275c85a39b038b7bd67d2990183c07b89c65d6ebe6df77094f2dc7",
    }
    for name, digest in pinned.items():
        assert (
            hashlib.sha256(
                (ROOT / f"config/{name}.yaml").read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
            == digest
        ), name
    assert (
        yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"][
            "m2d_human_visual_signoff"
        ]["status"]
        == "PENDING"
    )
