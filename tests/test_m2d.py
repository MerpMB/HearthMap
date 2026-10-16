# ruff: noqa: E501
"""M2D Wave-1 regional-context evidence: semantics, classification, aggregation, source handling, gates."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin

from hearthmap.context import SCOPE_STATEMENTS, forbidden_columns
from hearthmap.context import industry as ind
from hearthmap.context import services as svc
from hearthmap.context.semantics import COLUMN_LINEAGE_RULES
from hearthmap.context.settlement import GridIndex, aggregate_to_grid
from hearthmap.family.evaluability import load_plan
from hearthmap.provenance.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"


# -- vocabulary guards -------------------------------------------------------------------------------------------
def test_forbidden_columns_detects_scores_ranks_and_verdicts():
    bad = [
        "family_score",
        "peacefulness_score",
        "urban_penalty",
        "rank",
        "pass_fail",
        "town_services_score",
        "livability_index_verdict",
    ]
    assert set(forbidden_columns(bad)) == set(bad)
    ok = [
        "population_worldpop2025_density_per_km2",
        "service_cluster_core_definition",
        "nightlife_candidate_count_within_1km_euclidean_context",
        "diw_evidence_basis",
    ]
    assert forbidden_columns(ok) == []


def test_scope_statements_keep_the_required_distinctions():
    assert "not peacefulness" in SCOPE_STATEMENTS["population"]
    assert "not a building count and not population" in SCOPE_STATEMENTS["built_form"]
    assert "35-minute" in SCOPE_STATEMENTS["services"]
    assert "FACTORY_PRESENT is not NUISANCE_CONFIRMED" in SCOPE_STATEMENTS["industry"]
    assert "expired concession is not an active mine" in SCOPE_STATEMENTS["mining"]
    assert "restaurants are not nightlife" in SCOPE_STATEMENTS["nightlife"]
    assert "Natural Hazard scope" in SCOPE_STATEMENTS["hazard"]


# -- town services -----------------------------------------------------------------------------------------------
def test_classification_keeps_components_apart_and_nightlife_separate():
    assert svc.classify_tags({"shop": "supermarket"}) == ("GROCERY_OR_SUPERMARKET", None)
    assert svc.classify_tags({"shop": "convenience"}) == (
        "CONVENIENCE_STORE",
        None,
    )  # never merged with grocery
    assert svc.classify_tags({"amenity": "pharmacy"}) == ("PHARMACY", None)
    assert svc.classify_tags({"healthcare": "pharmacy"}) == ("PHARMACY", None)
    assert svc.classify_tags({"amenity": "atm"}) == ("BANK_OR_FINANCIAL", None)
    assert svc.classify_tags({"office": "government"}) == ("PUBLIC_ADMINISTRATION", None)
    assert svc.classify_tags({"amenity": "nightclub"}) == (
        None,
        "NIGHTCLUB",
    )  # nightlife is never a service component
    assert svc.classify_tags({"amenity": "restaurant"}) == (
        None,
        None,
    )  # restaurants are not nightlife
    assert svc.classify_tags({"amenity": "cafe"}) == (None, None)
    assert len(set(svc.COMPONENTS)) == len(svc.COMPONENTS) == 8
    assert "NIGHTLIFE" not in "".join(svc.COMPONENTS)


def test_same_component_duplicates_collapse_but_other_components_do_not():
    df = pd.DataFrame({"component": ["PHARMACY", "PHARMACY", "FUEL"]})
    xy = np.array(
        [[0.0, 0.0], [10.0, 0.0], [5.0, 0.0]]
    )  # two pharmacies 10 m apart, a fuel station between them
    keep = svc.dedup_same_component(df, xy)
    assert keep.tolist().count(True) == 2
    assert bool(keep.iloc[2])  # a different component at the same place is a different service


def test_cluster_definitions_are_exposed_and_need_distinct_components():
    assert set(svc.CLUSTER_DEFINITIONS) == {"CORE", "BROADER"}
    comps = ["PHARMACY", "FUEL", "MARKET", "BANK_OR_FINANCIAL", "PHARMACY"]
    df = pd.DataFrame({"component": comps})
    xy = np.array([[0, 0], [100, 0], [200, 0], [300, 0], [5000, 0]], dtype=float)
    core = svc.cluster_labels(df, xy, svc.CLUSTER_DEFINITIONS["CORE"])
    assert (core[:4] >= 0).all() and (core[:4] == core[0]).all() and core[4] == -1
    # many POIs of ONE component are not a service cluster
    df2 = pd.DataFrame({"component": ["PHARMACY"] * 6})
    xy2 = np.array([[i * 50.0, 0] for i in range(6)])
    assert (svc.cluster_labels(df2, xy2, svc.CLUSTER_DEFINITIONS["BROADER"]) == -1).all()
    # BROADER links farther and needs fewer components than CORE
    assert svc.CLUSTER_DEFINITIONS["BROADER"]["link_m"] > svc.CLUSTER_DEFINITIONS["CORE"]["link_m"]
    assert (
        svc.CLUSTER_DEFINITIONS["BROADER"]["min_distinct_components"]
        < svc.CLUSTER_DEFINITIONS["CORE"]["min_distinct_components"]
    )


def test_overpass_parse_drops_untagged_and_keeps_provenance_columns():
    payload = {"elements": [
        {"type": "node", "id": 1, "lat": 18.8, "lon": 98.9, "tags": {"shop": "convenience", "name": "7-Eleven"}},
        {"type": "way", "id": 2, "center": {"lat": 18.8, "lon": 98.9}, "tags": {"amenity": "bar"}},
        {"type": "node", "id": 3, "lat": 18.8, "lon": 98.9, "tags": {"amenity": "restaurant"}},
    ]}  # fmt: skip
    df = svc.parse_overpass(payload, "TH50")
    assert len(df) == 2
    assert df.loc[df["osm_id"] == "n1", "component"].iloc[0] == "CONVENIENCE_STORE"
    assert df.loc[df["osm_id"] == "w2", "nightlife_subtype"].iloc[0] == "BAR"
    assert df.loc[df["osm_id"] == "w2", "component"].isna().all()


# -- settlement aggregation --------------------------------------------------------------------------------------
def _gi(n: int = 4) -> GridIndex:
    ids = [f"G500-E{870 + c:06d}-N{3812 + r:06d}" for r in range(n) for c in range(n)]
    return GridIndex(ids)


def test_grid_index_locates_cells_and_ignores_outside_points():
    gi = _gi()
    x = np.array([870 * 500 + 10.0, 873 * 500 + 499.0, 5000.0])
    y = np.array([3812 * 500 + 10.0, 3815 * 500 + 499.0, 5000.0])
    idx = gi.locate(x, y)
    assert idx[0] == 0 and idx[1] == 15 and idx[2] == -1


def test_smoothing_uses_only_existing_cells_and_conserves_a_flat_field():
    gi = _gi()
    flat = np.full(16, 4.0)
    assert np.allclose(gi.smooth_mean(flat, 1), 4.0)  # edges are not diluted by zeros
    spike = np.zeros(16)
    spike[5] = 9.0
    assert gi.smooth_mean(spike, 1)[5] == pytest.approx(
        1.0
    )  # 9 over a 3x3 window of existing cells


def test_raster_aggregation_conserves_the_sum_and_skips_nodata(tmp_path):
    # a 10x10 pixel raster over a small lon/lat patch; one nodata pixel must not be counted
    t = from_origin(99.0, 19.0, 0.001, 0.001)
    arr = np.full((10, 10), 2.0, dtype="float32")
    arr[0, 0] = -99999
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
        nodata=-99999,
    ) as ds:
        ds.write(arr, 1)
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True).transform(99.005, 18.995)
    e0, n0 = int(x // 500), int(y // 500)
    ids = [f"G500-E{e0 + c - 2:06d}-N{n0 + r - 2:06d}" for r in range(5) for c in range(5)]
    gi = GridIndex(ids)
    sums, used = aggregate_to_grid([str(path)], gi, (98.99, 18.98, 99.02, 19.02), 25)
    assert used == 99
    assert sums.sum() == pytest.approx(198.0)


# -- DIW / DPIM / OSM industry ----------------------------------------------------------------------------------
def _diw_frame(rows):
    cols = [
        "เลขทะเบียนโรงงานเดิม",
        "fid",
        "รหัสประเภท",
        "ประเภทโรงงาน",
        "จำพวก",
        "ปีที่อนุญาต",
        "ชื่อโรงงาน",
        "ประกอบกิจการ",
        "จังหวัด",
        "อำเภอ",
        "ตำบล",
        "เงินทุนรวม (ล้านบาท)",
        "คนงานรวม",
        "แรงม้า",
        "หมวดอุตสาหกรรม",
    ]
    return pd.DataFrame(rows, columns=cols)


def test_diw_register_has_no_coordinates_or_status_and_converts_the_buddhist_year():
    f = _diw_frame([
        ["a", 1001, 301, "การโม่ บด หรือย่อยหิน", 3, 2550, "x", "y", "เชียงใหม่", "แม่ริม", "ริมใต้", 1.0, 10, 50.0, "g"],
        ["b", 1002, 1001, "ขนม", 3, 2560, "x", "y", "กรุงเทพมหานคร", "บางรัก", "สี่พระยา", 1.0, 10, 50.0, "g"],
    ])  # fmt: skip
    d = ind.load_diw({"factype3": f})
    assert len(d) == 1  # outside the AOI provinces
    r = d.iloc[0]
    assert r["licence_year_ce"] == 2007
    assert r["extraction_type"] == "STONE_CRUSHING_OR_GRINDING"
    assert (
        r["operating_status"] == "NOT_PROVIDED_BY_REGISTER"
        and r["coordinates"] == "NOT_PROVIDED_BY_REGISTER"
    )
    assert not any(c in d.columns for c in ("lat", "lon", "x", "y", "geometry"))


def test_diw_dedupes_by_fid_across_files_and_flags_waste_membership():
    row = [
        "a",
        2001,
        105,
        "คัดแยก",
        3,
        2560,
        "x",
        "y",
        "เชียงราย",
        "เมืองเชียงราย",
        "รอบเวียง",
        1.0,
        10,
        50.0,
        "g",
    ]
    d = ind.load_diw({"factype3": _diw_frame([row]), "factype101-105-106": _diw_frame([row])})
    assert len(d) == 1 and bool(d["is_waste_or_recycling"].iloc[0])


def test_dpim_current_never_calls_an_expired_concession_active_and_has_no_pii():
    payload = {"detail": {"data": [
        {"license_id": "1", "license_no": "n1", "province_code": "50", "province_name": "เชียงใหม่", "rai": "10", "ngan": "2", "wa": "0", "expire_dt": "2046-05-06 00:00:00", "wid_concession_flag": "N", "sur_concession_flag": "N"},
        {"license_id": "2", "license_no": "n2", "province_code": "57", "province_name": "เชียงราย", "rai": "5", "ngan": "0", "wa": "0", "expire_dt": "2015-01-01 00:00:00", "wid_concession_flag": "N", "sur_concession_flag": "N"},
        {"license_id": "3", "license_no": "n3", "province_code": "10", "province_name": "กรุงเทพ", "rai": "5", "ngan": "0", "wa": "0", "expire_dt": None, "wid_concession_flag": "N", "sur_concession_flag": "N"},
        {"license_id": "4", "license_no": "n4", "province_code": "56", "province_name": "พะเยา", "rai": "5", "ngan": "0", "wa": "0", "expire_dt": "2040-01-01 00:00:00", "wid_concession_flag": "Y", "sur_concession_flag": "N"},
    ]}}  # fmt: skip
    d = ind.dpim_current(payload, date(2026, 10, 16)).set_index("license_id")
    assert d.loc["1", "date_status"] == "UNEXPIRED_BY_DATE"
    assert d.loc["2", "date_status"] == "EXPIRED_BY_DATE"
    assert d.loc["4", "date_status"] == "REVOKED_OR_SURRENDERED_FLAG"
    assert "3" not in d.index  # outside the AOI
    assert d.loc["1", "area_rai"] == pytest.approx(10.5)
    assert not any(c in d.columns for c in ("name", "tax_no", "customer_id"))
    assert not any("active" in v.lower() or "operating" in v.lower() for v in d["date_status"])


def test_dpim_acquisition_script_strips_personal_fields_before_storage():
    text = (ROOT / "scripts/m2d/acquire_dpim.py").read_text("utf-8")
    assert 'PII = ("name", "tax_no", "customer_id")' in text
    assert text.index("row.pop(k, None)") < text.index("target.write_text")


def test_dpim_legacy_is_labelled_legacy_context():
    df = pd.DataFrame(
        {
            "จังหวัด": ["เชียงใหม่"],
            "อำเภอ": ["ฝาง"],
            "ตำบล": ["เวียง"],
            "ชนิดแร่": ["หินปูน"],
            "สถานะประทานบัตร": ["สิ้นอายุ"],
            "พื้นที่ (ไร่)": [10],
        }
    )
    out = ind.dpim_legacy(df)
    assert out["evidence_class"].tolist() == ["LEGACY_CONTEXT"]


def test_osm_industry_kinds_are_distinct_and_lifecycle_is_recorded():
    payload = {"elements": [
        {"type": "way", "id": 1, "center": {"lat": 19, "lon": 99}, "tags": {"landuse": "quarry"}},
        {"type": "way", "id": 2, "center": {"lat": 19, "lon": 99}, "tags": {"landuse": "industrial"}},
        {"type": "node", "id": 3, "lat": 19, "lon": 99, "tags": {"man_made": "works", "disused": "yes"}},
        {"type": "node", "id": 4, "lat": 19, "lon": 99, "tags": {"industrial": "factory"}},
    ]}  # fmt: skip
    d = ind.osm_industry_frame(payload, "TH50").set_index("osm_id")
    assert d.loc["w1", "kind"] == "OSM_QUARRY" and d.loc["w2", "kind"] == "OSM_INDUSTRIAL_LANDUSE"
    assert d.loc["n3", "kind"] == "OSM_WORKS" and d.loc["n3", "lifecycle_tag"] == "disused"
    assert d.loc["n4", "kind"] == "OSM_INDUSTRIAL_OTHER"


# -- gates, registry, secrets -----------------------------------------------------------------------------------
def test_gates_scoring_stays_off_and_m2d_signoff_is_pending():
    qa = yaml.safe_load((ROOT / "config/human-qa.yaml").read_text("utf-8"))["gates"]
    assert qa["m2d_human_visual_signoff"]["status"] == "PENDING"
    assert qa["m2d_human_visual_signoff"]["review_date"] is None
    assert qa["m2a_human_visual_signoff"]["status"] == "PENDING"
    plan = load_plan()
    assert plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False


def test_land_price_gap_is_not_downgraded_and_nuisance_buffers_stay_unauthorised():
    from hearthmap.family.evaluability import entry_priorities
    from hearthmap.family.requirements import load_requirements

    plan = load_plan()
    pr = entry_priorities(plan, load_requirements())
    assert pr["LAND-PRICE"] == "P0"
    ents = {e["id"]: e for e in plan["entries"]}
    for eid in ("NUIS-INDUSTRIAL", "NUIS-MINING", "NUIS-NIGHTLIFE"):
        assert ents[eid]["buffer_authorised"] is False
        assert ents[eid]["stages"]["REGIONAL_SCREENING"][0] == "NOT_EVALUABLE"
    for eid in ("TOWN-SERVICES", "SETTLE-PEACE", "NUIS-INDUSTRIAL", "NUIS-MINING"):
        assert all(s[0] != "READY" for s in ents[eid]["stages"].values()), (
            eid
        )  # data loaded never makes a requirement READY
    assert ents["SETTLE-PEACE"]["peace_is_multi_signal"] is True


def test_registry_records_wave1_sources_and_defers_gistda_buildings():
    reg = {s.id: s for s in load_registry(ROOT / "docs/research/data-source-registry.yaml").sources}
    for sid in (
        "population-worldpop-r2025a",
        "builtup-ghsl-r2023a",
        "osm-service-pois-aoi",
        "osm-industry-aoi",
        "industry-diw-factories",
        "mining-dpim-concessions",
    ):
        assert reg[sid].verification_status.value == "VERIFIED", sid
    g = reg["buildings-gistda-footprint"]
    assert (
        g.verification_status.value == "CANDIDATE"
        and g.acquisition_status.value == "DEFERRED"
        and g.local_raw_path is None
    )
    assert reg["mining-dpim-stone-crushing-licences"].verification_status.value == "NEEDS_RESEARCH"
    assert "OFFICIAL_APPRAISAL_CONTEXT" in (reg["land-value-treasury-appraisal"].notes or "")
    assert "coordinates" in reg["industry-diw-factories"].known_limitations[0]
    assert "population" in reg["population-worldpop-r2025a"].analytical_suitability.lower()


def test_m2d_scripts_never_print_or_store_the_gistda_key():
    text = (ROOT / "scripts/m2d/assess_gistda_buildings.py").read_text("utf-8")
    assert 'assert "api_key" not in text.lower()' in text
    for p in (ROOT / "scripts/m2d").glob("*.py"):
        src = p.read_text("utf-8")
        assert not re.search(r"print\([^)]*reveal\(\)", src), p.name
        assert not re.search(r"AIza|[A-Za-z0-9]{40,}", src), p.name
    assessment = ROOT / "outputs/m2d-review/gistda-buildings-assessment.json"
    if assessment.exists():
        body = assessment.read_text("utf-8").lower()
        assert "api_key" not in body and json.loads(body)["decision"] == "deferred"


def test_every_artifact_column_pattern_has_lineage_and_none_is_a_score():
    for pat, lin in COLUMN_LINEAGE_RULES:
        assert lin["family"] and lin["sources"] and lin["evidence_type"]
        assert not forbidden_columns([pat.strip("^$()").split("|")[0]])
    families = {lin["family"] for _, lin in COLUMN_LINEAGE_RULES}
    assert {
        "SETTLEMENT",
        "TOWN_SERVICES",
        "NIGHTLIFE_CANDIDATES",
        "INDUSTRY",
        "MINING_QUARRY",
    } <= families


# -- built artifact (skipped when outputs are not built) ----------------------------------------------------------
needs_artifact = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="run scripts/m2d/build_context.py"
)


@needs_artifact
def test_artifact_has_no_score_columns_full_lineage_and_separate_signals():
    df = pd.read_parquet(ARTIFACT)
    assert forbidden_columns(df.columns) == []
    lineage = json.loads(
        ARTIFACT.with_name("regional-context-evidence.columns.json").read_text("utf-8")
    )
    assert set(lineage) == set(df.columns)
    assert df["cell_id"].is_unique and len(df) == 162073
    assert (
        "population_worldpop2025_density_per_km2" in df and "built_ghsl2020_fraction_500m" in df
    )  # POPULATION_INTENSITY != BUILT_FORM_INTENSITY
    assert df["built_ghsl2020_fraction_500m"].between(0, 1).all()
    assert (df["population_worldpop2025_count_500m"] >= 0).all()
    assert df["routing_basis"].eq("BASELINE_DRIVE_TIME").all()


@needs_artifact
def test_artifact_unresolved_routes_are_nan_with_a_reason_never_zero():
    df = pd.read_parquet(ARTIFACT)
    for comp in svc.COMPONENTS:
        c = comp.lower()
        t = df[f"drive_time_to_nearest_service_{c}_min"]
        un = ~df[f"route_available_service_{c}"]
        assert t[un].isna().all()
        assert df.loc[un, f"service_{c}_unresolved_reason"].ne("").all()
        assert (t[~un] >= 0).all()


@needs_artifact
def test_artifact_diw_basis_is_tambon_level_and_legacy_is_labelled():
    df = pd.read_parquet(ARTIFACT)
    assert df["diw_evidence_basis"].eq("TAMBON_LEVEL_NO_COORDINATES_NO_OPERATING_STATUS").all()
    assert df["legacy_dpim_evidence_class"].eq("LEGACY_CONTEXT_2016_NOT_CURRENT").all()
    assert not [c for c in df.columns if "buffer" in c or "exclusion" in c]


@needs_artifact
def test_artifact_cluster_definitions_are_both_present_and_neither_is_selected():
    df = pd.read_parquet(ARTIFACT)
    assert {
        "drive_time_to_nearest_service_cluster_core_min",
        "drive_time_to_nearest_service_cluster_broader_min",
    } <= set(df.columns)
    assert not [c for c in df.columns if "production" in c or "selected" in c]


def test_osm_industry_ways_with_only_bounds_use_the_box_midpoint():
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 9,
                "bounds": {"minlat": 19.0, "minlon": 99.0, "maxlat": 19.002, "maxlon": 99.004},
                "tags": {"landuse": "quarry"},
            }
        ]
    }  # `out bb` replaces `center`, so the midpoint must be derived, never dropped
    d = ind.osm_industry_frame(payload, "TH50")
    assert len(d) == 1
    assert d["lat"].iloc[0] == pytest.approx(19.001) and d["lon"].iloc[0] == pytest.approx(99.002)
    assert d["bbox_diagonal_m"].iloc[0] > 400
