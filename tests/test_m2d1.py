# ruff: noqa: E501
"""M2D.1 evidence-semantics corrections: dependency, resolution guards, status semantics, denominators, candidate definitions."""

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

from hearthmap.context import industry as ind
from hearthmap.context.semantics import (
    CANDIDATE_DEFINITION,
    COLUMN_LINEAGE_RULES,
    SOURCE_SEMANTICS,
)
from hearthmap.context.services import CLUSTER_DEFINITIONS
from hearthmap.context.settlement import GridIndex, area_fraction
from hearthmap.context.stats import distribution_table, stat_with_denominator

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
needs_artifact = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="run scripts/m2d/build_context.py"
)


# -- WorldPop semantics and the WorldPop/GHSL dependency ----------------------------------------------------------
def test_worldpop_is_a_modelled_alpha_estimate_with_its_identifiers_preserved():
    w = SOURCE_SEMANTICS["population"]
    assert w["product_class"] == "MODELLED_POPULATION_ESTIMATE"
    assert w["is_not"] == "census-observed population"
    assert (w["estimate_year"], w["release"], w["version"], w["resolution_approx_m"]) == (
        2025,
        "R2025A",
        "v1",
        100,
    )
    assert (w["units"], w["crs"], w["product_status"], w["doi"]) == (
        "people per pixel",
        "EPSG:4326",
        "ALPHA",
        "10.5258/SOTON/WP00839",
    )


def test_worldpop_and_ghsl_are_recorded_as_partly_dependent_not_independent():
    w = SOURCE_SEMANTICS["population"]
    assert w["worldpop_depends_partly_on_ghsl"] is True
    assert (
        "NOT fully independent" in w["dependency_note"]
        and "not cross-source corroboration or validation" in w["dependency_note"]
    )
    lineage = {pat: lin for pat, lin in COLUMN_LINEAGE_RULES}
    assert lineage[r"^population_"]["worldpop_depends_partly_on_ghsl"] == "true"
    assert "not independent" in lineage[r"^built_"]["note"]
    assert "partly dependent" in lineage[r"^settlement_"]["note"]
    registry = (ROOT / "docs/research/data-source-registry.yaml").read_text("utf-8")
    assert "worldpop_depends_partly_on_ghsl = true" in registry
    for path in (
        "src/hearthmap/context/semantics.py",
        "scripts/m2d/build_context.py",
        "scripts/m2d/make_maps.py",
    ):
        text = (ROOT / path).read_text("utf-8")
        assert "INDEPENDENT_SOURCES" not in text.replace("NOT_INDEPENDENT", "")
        assert "between the two INDEPENDENT" not in text


# -- DIW semantics and the tambon resolution guard ---------------------------------------------------------------
def test_diw_inclusion_semantics_are_source_level_and_never_imply_active():
    d = SOURCE_SEMANTICS["diw"]
    assert d["row_level_status_field"] is False and d["row_level_coordinates"] is False
    assert d["record_status"] == "UNKNOWN"
    assert (
        "OUTSIDE industrial estates" in d["source_inclusion_semantics"]
        and "NOT documented" in d["source_inclusion_semantics"]
    )
    assert d["spatial_resolution"] == "TAMBON_ADMINISTRATIVE"


def test_tambon_context_columns_cannot_become_local_distance_or_buffer():
    lineage = {pat: lin for pat, lin in COLUMN_LINEAGE_RULES}
    for pat in (r"^diw_", r"^dpim_", r"^legacy_dpim_"):
        assert lineage[pat]["spatial_resolution"] == "TAMBON_ADMINISTRATIVE"
    assert "does not mean a factory is near" in lineage[r"^diw_"]["note"]
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    # every DIW/DPIM per-cell column that is created from a tambon table names its resolution
    created = set(
        re.findall(r'out\["((?:diw|dpim|legacy_dpim)_[a-z0-9_]*count[a-z0-9_]*)"\]', text)
    )
    assert created and all(c.endswith("tambon_context") for c in created), created
    assert not re.search(
        r'out\["(?:diw|dpim|legacy_dpim)_[a-z0-9_]*(?:distance|nearest|buffer|within|presence)',
        text,
    )


@needs_artifact
def test_artifact_has_no_distance_buffer_or_presence_columns_from_tambon_sources():
    df = pd.read_parquet(ARTIFACT)
    for c in df.columns:
        if c.startswith(("diw_", "dpim_", "legacy_dpim_")):
            assert not re.search(r"distance|nearest|buffer|within|presence|euclid|proximity", c), c
    assert df["diw_spatial_resolution"].eq("TAMBON_ADMINISTRATIVE").all()
    assert df["dpim_spatial_resolution"].eq("TAMBON_ADMINISTRATIVE").all()
    assert df["diw_record_status"].eq("UNKNOWN").all()
    assert not [
        c
        for c in df.columns
        if c.startswith("diw_") and "count" in c and not c.endswith("tambon_context")
    ]


# -- province-level mining and licence status ---------------------------------------------------------------------
def test_province_level_open_api_is_never_mapped_to_cells():
    assert SOURCE_SEMANTICS["dpim_open_api"] == {
        "spatial_resolution": "PROVINCE_ADMIN_CONTEXT",
        "may_be_mapped_to_cells": False,
    }
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    assert not re.search(
        r'out\["[a-z0-9_]*"\]\s*=\s*[^\n]*\bcur\b', text.replace("cur.groupby", "")
    )  # the open-API frame feeds the province table only


def test_licence_status_is_a_register_status_and_never_operating_status():
    payload = {"provinces": {"50": {"records": [
        {"factory_no": "A1", "province_code": "50", "province_name": "x", "tumbon_codes": "500206", "factory_status": "เปิดการ", "effective_date": "10/11/2542", "expire_date": "09/11/2552", "mineralName": None, "power_machine": None},
        {"factory_no": "A2", "province_code": "50", "province_name": "x", "tumbon_codes": "500206", "factory_status": None, "effective_date": "02/10/2545", "expire_date": "31/12/2600", "mineralName": None, "power_machine": None},
    ]}}}  # fmt: skip
    d = ind.dpim_export_frame(payload, "stone")
    assert d["is_current_operating_status"].eq(False).all()
    assert d["status_vocab"].tolist() == ["OPENED_REGISTER_STATUS", "STATUS_MISSING_IN_SOURCE"]
    assert all("OPERATING" not in v.replace("AWAITING_OPERATION", "") for v in d["status_vocab"])
    assert d.loc[0, "effective_date"] == pd.Timestamp(1999, 11, 10)  # Buddhist era converted
    assert (
        d.loc[0, "expire_date"] < pd.Timestamp(2026, 10, 16)
        and d.loc[0, "status_vocab"] == "OPENED_REGISTER_STATUS"
    )  # status and expiry can disagree and both are kept
    assert (
        d["tambon_pcode"].eq("TH500206").all()
        and d["spatial_resolution"].eq("TAMBON_ADMINISTRATIVE").all()
    )
    assert SOURCE_SEMANTICS["dpim_licences"]["licence_status_is_current_operating_status"] is False
    assert not any("OPERATING_STATUS" in v for v in ind.STONE_STATUS_EN.values()) and all(
        v.endswith("_REGISTER_STATUS") for v in ind.STONE_STATUS_EN.values() if "AWAITING" not in v
    )


def test_dpim_licence_script_removes_personal_fields_and_skips_the_forbidden_page():
    text = (ROOT / "scripts/m2d/acquire_dpim_licences.py").read_text("utf-8")
    assert 'PII = {"customerName", "tovCustomerName", "factory_name"}' in text
    assert text.index("rec.pop(k, None)") < text.index("target.write_text")
    assert "qry/quarry.php" in text and "NOT used" in text  # the 403 page is documented as not used


# -- OSM geometry semantics --------------------------------------------------------------------------------------
def test_osm_polygons_and_points_are_distinct_classes_and_never_summed():
    payload = {"elements": [
        {"type": "way", "id": 1, "geometry": [{"lat": 19, "lon": 99}, {"lat": 19, "lon": 99.001}, {"lat": 19.001, "lon": 99.001}, {"lat": 19, "lon": 99}], "tags": {"man_made": "works"}},
        {"type": "node", "id": 2, "lat": 19, "lon": 99, "tags": {"man_made": "works"}},
        {"type": "way", "id": 3, "geometry": [{"lat": 19, "lon": 99}, {"lat": 19, "lon": 99.002}], "tags": {"landuse": "quarry"}},
    ]}  # fmt: skip
    g = ind.osm_industry_geometries(payload, "TH50").set_index("osm_id")
    assert g.loc["w1", "geometry_class"] == "POLYGON" and g.loc["n2", "geometry_class"] == "POINT"
    assert g.loc["w3", "geometry_class"] == "LINE"  # an open way is never an area
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    assert not re.search(
        r'out\["osm_(?:industrial|works)_feature_count', text
    )  # no single combined feature count
    assert (
        'f"osm_works_{cls.lower()}_count_within_' in text
        and "osm_industrial_landuse_polygon_fraction_of_nominal_grid_cell_aoi_clipped" in text
    )


def test_area_fraction_measures_polygons_as_polygons_and_merges_overlaps():
    ids = [f"G500-E{870 + c:06d}-N{3812 + r:06d}" for r in range(2) for c in range(2)]
    gi = GridIndex(ids)
    cells = np.array(
        [
            shapely.box(
                870 * 500 + c * 500,
                3812 * 500 + r * 500,
                870 * 500 + c * 500 + 500,
                3812 * 500 + r * 500 + 500,
            )
            for r in range(2)
            for c in range(2)
        ]
    )
    assert gi.locate(np.array([435250.0]), np.array([1906250.0]))[0] == 0
    p1 = shapely.box(435000, 1906000, 435250, 1906500)  # half of cell 0
    p2 = shapely.box(435000, 1906000, 435250, 1906500)  # the same area again: not counted twice
    f = area_fraction(cells, np.array([p1, p2]), 4)
    assert f[0] == pytest.approx(0.5) and f[1:].sum() == 0
    assert area_fraction(cells, np.array([]), 4).sum() == 0


@needs_artifact
def test_artifact_keeps_osm_point_and_polygon_columns_separate():
    df = pd.read_parquet(ARTIFACT)
    assert (
        "osm_works_point_count_within_1km_euclidean_context" in df
        and "osm_works_polygon_count_within_1km_euclidean_context" in df
    )
    assert not [c for c in df.columns if re.match(r"osm_(industrial|works)_feature_count", c)]
    for c in (
        "osm_industrial_landuse_polygon_fraction_of_nominal_grid_cell_aoi_clipped",
        "osm_quarry_polygon_fraction_of_nominal_grid_cell_aoi_clipped",
    ):
        assert df[c].between(0, 1).all()
    assert df["osm_quarry_geometry_presence_within_1km_euclidean_context"].dtype == bool


# -- routing denominators --------------------------------------------------------------------------------------
def test_routable_only_statistics_expose_their_denominator_and_are_not_aoi_wide():
    v = np.array([10.0, 20.0, np.nan, np.nan])
    resolved = np.array([True, True, False, False])
    area = np.array([0.25, 0.25, 0.25, 0.25])
    r = stat_with_denominator(
        v,
        resolved,
        area,
        "MEDIAN_AMONG_ROUTABLE_CELLS_ONLY",
        "AOI",
        "drive_time_to_nearest_service_x_min",
    )
    assert r["cells_total"] == 4 and r["cells_resolved"] == 2 and r["cells_unresolved"] == 2
    assert (
        r["resolved_cell_share"] == 0.5
        and r["resolved_area_share"] == 0.5
        and r["unresolved_area_share"] == 0.5
    )
    assert r["p50"] == 15.0 and r["statistic_population"] == "MEDIAN_AMONG_ROUTABLE_CELLS_ONLY"


@needs_artifact
def test_every_service_time_statistic_states_its_denominator():
    st = pd.read_csv(ROOT / "outputs/m2d/tables/descriptive-statistics.csv")
    times = st[st["column"].str.startswith("drive_time_to_nearest_service_")]
    assert (
        len(times) > 0
        and times["statistic_population"].eq("MEDIAN_AMONG_ROUTABLE_CELLS_ONLY").all()
    )
    assert (times["cells_resolved"] < times["cells_total"]).all()
    assert {"cells_unresolved", "resolved_area_share", "unresolved_area_share"} <= set(
        times.columns
    )
    den = pd.read_csv(ROOT / "outputs/m2d/tables/routing-denominators.csv")
    aoi = den[den["scope"] == "Whole AOI"].iloc[0]
    assert aoi["cells_routable"] + aoi["cells_unresolved_no_road_within_1km"] == aoi["cells_total"]
    assert aoi["unresolved_area_share"] > 0.3


# -- candidate definitions and no thresholds ---------------------------------------------------------------------
def test_core_and_broader_are_candidate_definitions_and_neither_is_production():
    assert CANDIDATE_DEFINITION == "CANDIDATE_DEFINITION" and set(CLUSTER_DEFINITIONS) == {
        "CORE",
        "BROADER",
    }
    text = (ROOT / "scripts/m2d/build_context.py").read_text("utf-8")
    assert "_definition_status" in text and "production" not in text.lower().replace(
        "no production", ""
    )


@needs_artifact
def test_artifact_marks_clusters_as_candidates_and_keeps_the_sensitivity_visible():
    df = pd.read_parquet(ARTIFACT)
    assert df["service_cluster_core_definition_status"].eq(CANDIDATE_DEFINITION).all()
    assert df["service_cluster_broader_definition_status"].eq(CANDIDATE_DEFINITION).all()
    sens = pd.read_csv(ROOT / "outputs/m2d/tables/service-cluster-sensitivity.csv")
    aoi = sens[sens["scope"] == "Whole AOI"].iloc[0]
    assert (
        aoi["definition_status"] == CANDIDATE_DEFINITION
        and aoi["median_core_min"] > aoi["median_broader_min"]
    )
    assert (
        aoi["statistic_population"] == "AMONG_CELLS_ROUTABLE_FOR_BOTH_DEFINITIONS_ONLY"
        and aoi["cells_routable_for_both"] < aoi["cells_total"]
    )


def test_no_urban_core_threshold_exists_anywhere_in_the_m2d_code_or_artifact():
    for path in list((ROOT / "src/hearthmap/context").glob("*.py")) + list(
        (ROOT / "scripts/m2d").glob("*.py")
    ):
        text = path.read_text("utf-8")
        assert not re.search(
            r"dense_urban_core\w*\s*=|DENSE_URBAN_CORE\s*=|urban_core_threshold|is_urban_core|urban_core_class",
            text,
        ), path.name
    d = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [0.0, 0.0, 5.0, 9.0]})
    t = distribution_table(d, ["a", "b"], {"all": pd.Series([True] * 4)})
    assert not [c for c in t.columns if "threshold" in c or "class" in c or "score" in c]
    assert set(t["population"]) == {"ALL_CELLS", "CELLS_WITH_NONZERO_VALUE"}


@needs_artifact
def test_artifact_has_descriptive_poi_intensity_but_no_urban_core_variable():
    df = pd.read_parquet(ARTIFACT)
    assert "osm_service_poi_local_intensity_per_nominal_grid_cell_km2_mean_2p5km" in df
    assert not [c for c in df.columns if "urban_core" in c or "dense" in c or "peace" in c]
    dist = pd.read_csv(ROOT / "outputs/m2d/tables/urban-core-calibration-distributions.csv")
    assert dist["note"].str.contains("no quantile is a policy threshold").all()
    assert {
        "population_worldpop2025_intensity_per_nominal_grid_cell_km2",
        "built_ghsl2020_intensity_fraction_of_nominal_grid_cell",
        "road_intensity_osm_drivable_km_per_nominal_grid_cell_km2",
        "osm_service_poi_local_intensity_per_nominal_grid_cell_km2_mean_2p5km",
    } <= set(dist["column"])


# -- evaluability, scoring, hazards, GISTDA ------------------------------------------------------------------------
def test_evaluability_states_follow_the_correction_and_nothing_becomes_ready():
    plan = yaml.safe_load((ROOT / "config/family-evaluability.yaml").read_text("utf-8"))
    ents = {e["id"]: e for e in plan["entries"]}
    st = lambda eid, stage: ents[eid]["stages"][stage][0]  # noqa: E731
    assert (
        st("SETTLE-PEACE", "REGIONAL_SCREENING") == "PROXY_ONLY"
        and st("SETTLE-PEACE", "CANDIDATE_ZONE_COMPARISON") == "PROXY_ONLY"
    )
    assert st("TOWN-SERVICES", "REGIONAL_SCREENING") == "READY_WITH_LIMITATIONS"
    assert (
        "COMPONENT ACCESSIBILITY ONLY" in ents["TOWN-SERVICES"]["stages"]["REGIONAL_SCREENING"][1]
        and "not yet defined" in ents["TOWN-SERVICES"]["stages"]["REGIONAL_SCREENING"][1]
    )
    assert (
        st("NUIS-INDUSTRIAL", "CANDIDATE_ZONE_COMPARISON") == "PROXY_ONLY"
        and st("NUIS-MINING", "CANDIDATE_ZONE_COMPARISON") == "PROXY_ONLY"
    )
    assert st("NUIS-NIGHTLIFE", "CANDIDATE_ZONE_COMPARISON") == "PROXY_ONLY"
    for e in plan["entries"]:
        assert all(s[0] != "READY" for s in e["stages"].values()), e["id"]
    assert plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    assert (
        yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"][
            "m2d_human_visual_signoff"
        ]["status"]
        == "PASSED"
    )


def test_hazard_and_requirement_configs_are_immutable():
    pinned = {
        "hazard": "b04fb8cc9a256b3eb9d0384e7933bed790fec590a3441af36df2007b7cfe68fe",
        "hazard-policy": "a270dc3b5618b89a14a44dc3ff12da8e0a1cbd64b657191b03233845f6fb8acd",
        "hazard-integration": "0213e85349e77c20ec47127e30e59357d3767627bebc463228d6cfc926b05dd7",
        "flood-fusion": "5d908eafe965fdbe445a5eabaa0d733a866f690c1c2335870de4496b26463f44",
        "seismic-evidence": "649a7d141c693ed9d737877e856e74a0de75e69253871d013576a5a5d4b05c44",
        "family-requirements": "a4673aa9aa275c85a39b038b7bd67d2990183c07b89c65d6ebe6df77094f2dc7",
    }
    for name, digest in pinned.items():
        data = (ROOT / f"config/{name}.yaml").read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == digest, (
            f"{name}.yaml changed: M2D.1 may not change hazard actions or user requirements"
        )


def test_gistda_stays_deferred_and_no_m2d1_script_calls_the_gistda_api():
    for path in (ROOT / "scripts/m2d").glob("*.py"):
        if path.name == "assess_gistda_buildings.py":
            continue
        text = path.read_text("utf-8")
        assert "api-gateway.gistda" not in text and "GISTDA_API_KEY" not in text, path.name
    reg = yaml.safe_load((ROOT / "docs/research/data-source-registry.yaml").read_text("utf-8"))[
        "sources"
    ]
    g = next(x for x in reg if x["id"] == "buildings-gistda-footprint")
    assert g["verification_status"] == "CANDIDATE" and g["acquisition_status"] == "DEFERRED"


@needs_artifact
def test_lineage_json_records_spatial_resolution_for_every_column():
    df = pd.read_parquet(ARTIFACT)
    lin = json.loads(
        (ROOT / "outputs/m2d/regional-context-evidence.columns.json").read_text("utf-8")
    )
    assert set(lin) == set(df.columns) and all(v["spatial_resolution"] for v in lin.values())
    assert df["population_product_class"].eq("MODELLED_POPULATION_ESTIMATE").all()
    assert df["population_worldpop_depends_partly_on_ghsl"].all()
    assert "PARTLY_DEPENDENT" in df["evidence_settlement_state"].iloc[0]
    src = json.loads(
        (ROOT / "outputs/m2d/regional-context-evidence.sources.json").read_text("utf-8")
    )
    assert src["population"]["worldpop_depends_partly_on_ghsl"] is True
