# ruff: noqa: E501
"""M2D.1c edge-cell AOI evidence accounting: evidence outside the AOI never enters AOI analytical values or totals."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
import shapely
import yaml
from rasterio.transform import from_origin

from hearthmap.context.semantics import COLUMN_LINEAGE_RULES, forbidden_columns
from hearthmap.context.settlement import GridIndex, aggregate_to_grid_aoi, aoi_pixel_weights
from hearthmap.family import load_config
from hearthmap.family.evaluability import load_plan

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
needs_artifact = pytest.mark.skipif(not ART.exists(), reason="run scripts/m2d/build_context.py")


def _raster(tmp_path: Path, value: float = 10.0) -> Path:
    # 10 x 10 pixels of 0.001 degrees, every pixel holds `value`
    t = from_origin(99.0, 19.0, 0.001, 0.001)
    path = tmp_path / "r.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=t,
        nodata=-1,
    ) as ds:
        ds.write(np.full((10, 10), value, dtype="float32"), 1)
    return path


def _grid_for(path: Path) -> tuple[GridIndex, int]:
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True).transform(99.005, 18.995)
    e0, n0 = int(x // 500), int(y // 500)
    ids = [f"G500-E{e0 + c - 3:06d}-N{n0 + r - 3:06d}" for r in range(7) for c in range(7)]
    return GridIndex(ids), len(ids)


def test_pixel_weight_is_the_footprint_share_inside_the_aoi():
    aoi = shapely.box(
        99.0, 18.9, 99.0045, 19.1
    )  # covers pixels x 99.000..99.004 fully and half of the pixel 99.004..99.005
    lon = np.array([99.0005, 99.0045, 99.0085])
    lat = np.array([18.9995, 18.9995, 18.9995])
    w = aoi_pixel_weights(lon, lat, 0.0005, 0.0005, aoi)
    assert w[0] == 1.0 and w[2] == 0.0 and w[1] == pytest.approx(0.5, abs=0.02)


def test_evidence_outside_the_aoi_cannot_contribute_to_the_aoi_total(tmp_path):
    path = _raster(tmp_path)
    gi, n = _grid_for(path)
    aoi_half = shapely.box(98.9, 18.9, 99.005, 19.1)  # the western half of the raster is the AOI
    full, clipped, _, dropped = aggregate_to_grid_aoi(
        [str(path)], gi, (98.99, 18.98, 99.02, 19.02), n, aoi_half
    )
    assert full.sum() == pytest.approx(1000.0)  # 100 pixels x 10
    assert clipped.sum() + dropped == pytest.approx(500.0, rel=0.03)  # only the AOI half counts
    assert clipped.sum() < full.sum()
    none = aggregate_to_grid_aoi(
        [str(path)], gi, (98.99, 18.98, 99.02, 19.02), n, shapely.box(10, 10, 11, 11)
    )
    assert none[1].sum() == 0.0 and none[0].sum() == pytest.approx(
        1000.0
    )  # full-cell context is not AOI evidence


def test_fully_inside_aoi_leaves_every_cell_unchanged(tmp_path):
    path = _raster(tmp_path)
    gi, n = _grid_for(path)
    full, clipped, _, dropped = aggregate_to_grid_aoi(
        [str(path)], gi, (98.99, 18.98, 99.02, 19.02), n, shapely.box(98.0, 18.0, 100.0, 20.0)
    )
    assert np.array_equal(full, clipped) and dropped == 0.0


def test_edge_clipping_follows_the_pixels_not_the_coverage_fraction(tmp_path):
    # a raster whose dense pixels all sit on the outside half: scaling by coverage would wrongly keep half of the value
    t = from_origin(99.0, 19.0, 0.001, 0.001)
    arr = np.zeros((10, 10), dtype="float32")
    arr[:, 5:] = 20.0  # the eastern half holds everything
    path = tmp_path / "skew.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=t,
        nodata=-1,
    ) as ds:
        ds.write(arr, 1)
    gi, n = _grid_for(path)
    aoi_west = shapely.box(98.9, 18.9, 99.005, 19.1)
    full, clipped, _, dropped = aggregate_to_grid_aoi(
        [str(path)], gi, (98.99, 18.98, 99.02, 19.02), n, aoi_west
    )
    assert clipped.sum() + dropped == pytest.approx(
        0.0, abs=1e-6
    )  # nothing populated inside the AOI, so nothing may be attributed to it
    assert full.sum() == pytest.approx(1000.0)


def test_code_never_scales_a_full_cell_value_by_coverage_fraction_and_never_derives_from_context_columns():
    for path in (ROOT / "scripts/m2d").glob("*.py"):
        text = path.read_text("utf-8")
        assert not re.search(r"full_cell\w*\s*\*\s*\w*coverage", text), path.name
        assert not re.search(r"coverage\w*\s*\*\s*\w*full_cell", text), path.name
    allowed = {"build_context.py", "edge_cell_aoi_accounting.py", "routing_coverage_qa.py"}
    for path in (ROOT / "scripts/m2d").glob("*.py"):
        if path.name not in allowed:
            assert "full_cell_context" not in path.read_text("utf-8"), path.name
    qa = (ROOT / "scripts/m2d/routing_coverage_qa.py").read_text("utf-8")
    assert (
        'pop = df["population_worldpop2025_mass_aoi_clipped"]' in qa
        and 'built = df["built_ghsl2020_m2_aoi_clipped"]' in qa
    )  # QA uses the clipped analytical columns
    for line in [
        ln for ln in qa.splitlines() if "full_cell_context" in ln
    ]:  # only in the explicit old-vs-corrected comparison
        assert any(
            k in line for k in ("pop_ctx", "built_ctx", "_old_full_cell_context", "old (full-cell")
        ), line


def test_lineage_marks_full_cell_columns_as_context_only_and_primary_columns_as_aoi_footprint():
    rules = {pat: lin for pat, lin in COLUMN_LINEAGE_RULES}
    ctx = rules[r"^(population|built)_.*_full_cell_context$"]
    assert (
        ctx["evidence_type"] == "FULL_CELL_CONTEXT_ONLY"
        and ctx["evidence_footprint"] == "GRID_FOOTPRINT"
    )
    assert (
        rules[r"^population_"]["evidence_footprint"] == "AOI_ANALYTICAL_FOOTPRINT"
        and rules[r"^built_"]["evidence_footprint"] == "AOI_ANALYTICAL_FOOTPRINT"
    )
    pats = [p for p, _ in COLUMN_LINEAGE_RULES]
    assert (
        pats.index(r"^(population|built)_.*_full_cell_context$")
        < pats.index(r"^population_")
        < pats.index(r"^built_")
    )  # the context rule wins first


@needs_artifact
def test_interior_cells_keep_their_values_and_edge_cells_do_not_exceed_the_full_cell():
    df = pd.read_parquet(ART)
    interior = df["coverage_fraction"] >= 1 - 1e-9
    assert interior.sum() > 150_000
    assert np.array_equal(
        df.loc[interior, "population_worldpop2025_mass_aoi_clipped"],
        df.loc[interior, "population_worldpop2025_mass_full_cell_context"],
    )
    assert np.array_equal(
        df.loc[interior, "built_ghsl2020_m2_aoi_clipped"],
        df.loc[interior, "built_ghsl2020_m2_full_cell_context"],
    )
    assert (
        df["population_worldpop2025_mass_aoi_clipped"]
        <= df["population_worldpop2025_mass_full_cell_context"] + 1e-6
    ).all()
    assert (
        df["built_ghsl2020_m2_aoi_clipped"] <= df["built_ghsl2020_m2_full_cell_context"] + 1e-6
    ).all()
    assert (
        df.loc[~interior, "population_worldpop2025_mass_aoi_clipped"]
        < df.loc[~interior, "population_worldpop2025_mass_full_cell_context"] - 1e-6
    ).any()
    assert forbidden_columns(df.columns) == []


@needs_artifact
def test_edge_cell_footprint_equals_grid_intersect_aoi_coverage():
    import geopandas as gpd

    prov = gpd.read_file(ROOT / "data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    grid = gpd.read_file(ROOT / "data/processed/m1a/grid.gpkg", layer="analysis_grid_500m")
    edge = grid[grid["coverage_fraction"] < 1 - 1e-9].sample(150, random_state=3)
    cov = shapely.area(shapely.intersection(edge.geometry.to_numpy(), aoi)) / shapely.area(
        edge.geometry.to_numpy()
    )
    assert (
        np.abs(cov - edge["coverage_fraction"].to_numpy()).max() < 1e-9
    )  # AOI_ANALYTICAL_FOOTPRINT = GRID_FOOTPRINT intersect AOI


@needs_artifact
def test_aoi_totals_use_clipped_evidence_and_state_old_vs_new():
    df = pd.read_parquet(ART)
    t = pd.read_csv(ROOT / "outputs/m2d/tables/aoi-evidence-totals-old-vs-clipped.csv").set_index(
        "quantity"
    )
    pop = t.loc["WorldPop modelled population (people)"]
    built = t.loc["GHSL built-up surface (km2)"]
    assert pop["new_aoi_clipped_total"] == pytest.approx(
        df["population_worldpop2025_mass_aoi_clipped"].sum(), abs=1
    )
    assert pop["old_full_cell_grid_total_context_only"] == pytest.approx(
        df["population_worldpop2025_mass_full_cell_context"].sum(), abs=1
    )
    assert built["new_aoi_clipped_total"] == pytest.approx(
        df["built_ghsl2020_m2_aoi_clipped"].sum() / 1e6, abs=0.001
    )
    for r in (pop, built):
        assert r["absolute_difference"] == pytest.approx(
            r["old_full_cell_grid_total_context_only"] - r["new_aoi_clipped_total"], abs=0.002
        )
        assert 0 < r["percentage_difference_of_old"] < 2
        assert "NOT an AOI total" in r["definition"]
    assert (
        pop["closure_check_value_of_clipped_pixels_in_no_grid_cell"] < 10
    )  # the grid covers the AOI: next to nothing is lost


@needs_artifact
def test_routing_qa_uses_clipped_values_and_cell_area_shares_are_unchanged():
    cmp_ = pd.read_csv(ROOT / "outputs/m2d/tables/routing-coverage-old-vs-aoi-clipped.csv")
    w = pd.read_csv(ROOT / "outputs/m2d/tables/routing-coverage-weighted.csv")
    aoi = w[w["scope"] == "Whole AOI"].iloc[0]
    df = pd.read_parquet(ART)
    assert aoi["modelled_population_total"] == pytest.approx(
        df["population_worldpop2025_mass_aoi_clipped"].sum(), abs=2
    )
    assert aoi["built_up_m2_total"] == pytest.approx(
        df["built_ghsl2020_m2_aoi_clipped"].sum(), abs=2
    )
    # 0.4299 before the M2D.1d origin correction (44 more cells became routable); the area share is unchanged
    assert aoi["unresolved_cell_share"] == pytest.approx(0.4296, abs=1e-4)
    assert aoi["unresolved_area_share"] == pytest.approx(0.4265, abs=1e-4)
    row = cmp_[cmp_["scope"] == "Whole AOI"].iloc[0]
    assert row["unresolved_population_share_corrected_aoi_clipped"] == pytest.approx(
        aoi["unresolved_population_share"], abs=1e-4
    )
    assert (
        row["unresolved_population_share_corrected_aoi_clipped"]
        != row["unresolved_population_share_old_full_cell_context"]
    )
    assert cmp_["note"].str.contains("cell and area shares are unchanged").all()


@needs_artifact
def test_edge_cell_table_and_the_checked_cell():
    t = pd.read_csv(ROOT / "outputs/m2d-review/edge-cell-aoi-accounting.csv")
    for col in (
        "grid_id",
        "aoi_coverage_fraction_of_cell",
        "province",
        "district",
        "full_cell_modelled_population",
        "aoi_clipped_modelled_population",
        "population_removed_outside_aoi",
        "full_cell_built_up_m2",
        "aoi_clipped_built_up_m2",
        "built_up_removed_outside_aoi",
    ):
        assert col in t.columns
    assert forbidden_columns(t.columns) == [] and not [
        c for c in t.columns if "rank" in c or "score" in c
    ]
    assert (t["aoi_coverage_fraction_of_cell"] < 1).all() and (
        (t["population_removed_outside_aoi"] > 0) | (t["built_up_removed_outside_aoi"] > 0)
    ).all()
    assert t["province"].notna().all() and t["district"].ne("").all()
    c = t[t["grid_id"] == "G500-E001332-N004224"].iloc[0]
    assert (
        c["full_cell_modelled_population"] == pytest.approx(294.89, abs=0.01)
        and c["aoi_clipped_modelled_population"] < 0.15 * c["full_cell_modelled_population"]
    )
    assert c["aoi_clipped_built_up_m2"] < 0.15 * c["full_cell_built_up_m2"] and (
        c["province"],
        c["district"],
    ) == ("Phayao", "Pong")
    s = json.loads((ROOT / "outputs/m2d/edge-cell-aoi-accounting-summary.json").read_text("utf-8"))
    assert (
        s["interior"]["interior_population_max_abs_difference"] == 0.0
        and s["interior"]["interior_built_up_max_abs_difference_m2"] == 0.0
    )


def test_audit_table_classifies_every_field_with_a_valid_class():
    d = pd.read_csv(ROOT / "docs/research/m2d1c-aoi-evidence-audit.csv")
    assert set(d["class"]) <= {
        "AOI_CLIPPED_ALREADY",
        "FULL_CELL_CONTEXT_ONLY",
        "POTENTIALLY_AFFECTED",
        "NOT_APPLICABLE",
    }
    joined = " ".join(d["field"])
    for needle in ("worldpop", "ghsl", "terrain", "flood", "road_"):
        assert needle in joined.lower()
    assert (
        d.loc[d["field"].str.contains("full_cell_context"), "class"] == "FULL_CELL_CONTEXT_ONLY"
    ).all()
    assert (ROOT / "docs/architecture/grid-footprint-semantics.md").read_text("utf-8").count(
        "AOI_ANALYTICAL_FOOTPRINT"
    ) >= 1


def test_no_scoring_unchanged_routing_and_immutable_hazards():
    assert load_plan()["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    cfg = load_config()
    assert (
        hashlib.sha256(json.dumps(cfg["travel_time"], sort_keys=True).encode()).hexdigest()[:16]
        == "5c35e98882c3ac62"
        and cfg["travel_time"]["max_snap_distance_m"] == 1000
    )
    pinned = {
        "hazard": "b04fb8cc9a256b3eb9d0384e7933bed790fec590a3441af36df2007b7cfe68fe",
        "hazard-policy": "a270dc3b5618b89a14a44dc3ff12da8e0a1cbd64b657191b03233845f6fb8acd",
        "hazard-integration": "0213e85349e77c20ec47127e30e59357d3767627bebc463228d6cfc926b05dd7",
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


@needs_artifact
def test_population_stays_a_modelled_estimate_and_other_columns_are_unchanged_semantically():
    df = pd.read_parquet(ART)
    assert df["population_product_class"].eq("MODELLED_POPULATION_ESTIMATE").all()
    assert df["routing_config_fingerprint"].eq("5c35e98882c3ac62").all()
    assert "AOI_ANALYTICAL_FOOTPRINT" in df["evidence_settlement_footprint"].iloc[0]
