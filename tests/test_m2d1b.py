# ruff: noqa: E501
"""M2D.1b administrative label integrity: a district label must always be a valid unit of the reported province."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely

from hearthmap.context.settlement import assign_max_overlap

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "outputs" / "m2d" / "regional-context-evidence.parquet"
REVIEW = ROOT / "outputs" / "m2d-review" / "routing-unresolved-settlement-overlap.csv"
COD = next((ROOT / "data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip"), None)
needs_outputs = pytest.mark.skipif(
    not (ART.exists() and REVIEW.exists() and COD),
    reason="run build_context.py and routing_coverage_qa.py",
)


def test_edge_cell_takes_its_own_province_unit_never_a_neighbouring_one():
    # province A (x 0..10) and province B (x 10..20); the cell straddles the border with 18% in A and 82% in B, so its CENTROID is in B
    cells = np.array(
        [shapely.box(9.0, 0, 15.5, 1)]
    )  # 15.4% in A (x 9..10), centroid x=12.25 is in B
    polys = np.array([shapely.box(0, 0, 10, 1), shapely.box(10, 0, 20, 1)])
    ids, share, _ = assign_max_overlap(
        cells, np.array(["A"]), polys, np.array(["A", "B"]), np.array(["unitA", "unitB"])
    )
    assert ids[0] == "unitA"  # the unit of the cell's own province, although the centroid lies in B
    assert 0.1 < share[0] < 0.2


def test_cell_without_an_overlapping_unit_in_its_province_is_unknown_not_a_neighbour_label():
    cells = np.array([shapely.box(12, 0, 13, 1)])
    polys = np.array([shapely.box(0, 0, 10, 1), shapely.box(10, 0, 20, 1)])
    ids, share, _ = assign_max_overlap(
        cells, np.array(["A"]), polys, np.array(["A", "B"]), np.array(["unitA", "unitB"])
    )
    assert ids[0] == "" and share[0] == 0.0


def test_largest_overlap_wins_within_the_province_and_edge_touching_does_not_count():
    cells = np.array([shapely.box(4, 0, 6, 1), shapely.box(10, 0, 11, 1)])
    polys = np.array([shapely.box(0, 0, 5.5, 1), shapely.box(5.5, 0, 10, 1)])
    ids, _, _ = assign_max_overlap(
        cells, np.array(["A", "A"]), polys, np.array(["A", "A"]), np.array(["u1", "u2"])
    )
    assert ids[0] == "u1"  # 1.5 of 2 inside u1
    assert ids[1] == ""  # only touches u2's edge: no overlap


@needs_outputs
def test_every_reported_district_province_pair_is_a_valid_administrative_pair():
    adm2 = gpd.read_file(COD, layer="tha_admin2")[
        ["adm2_pcode", "adm2_name", "adm1_pcode", "adm1_name"]
    ].drop_duplicates()
    h = adm2.set_index("adm2_pcode")
    t = pd.read_csv(REVIEW)
    assert len(t) > 0 and t["district_pcode"].notna().all()
    for _, r in t.iterrows():
        assert r["district_pcode"] in h.index, r["district_pcode"]
        unit = h.loc[r["district_pcode"]]
        assert unit["adm1_pcode"] == r["province_pcode"], (
            r["grid_id"],
            r["province"],
            r["district"],
        )  # district belongs to the reported province
        assert unit["adm1_name"] == r["province"] and unit["adm2_name"] == r["district"]
        assert r["district_pcode"].startswith(r["province_pcode"])


@needs_outputs
def test_nearest_or_nationwide_place_labels_live_only_in_explicit_context_fields():
    t = pd.read_csv(REVIEW)
    ctx = [c for c in t.columns if c.startswith("centroid_nationwide_")]
    assert ctx and all(c.endswith("_context") for c in ctx)
    outside = t[~t["centroid_in_reported_province"]]
    assert (
        len(outside) > 0
    )  # the QA set does contain edge cells whose centroid is in another province or outside Thailand
    # such a cell's context label may differ from its administrative district, and the district field is never the context label
    assert (outside["district"] != outside["centroid_nationwide_adm2_context"].fillna("")).all()
    assert not t["district"].isin(["Tha Wang Pha"]).any()  # Nan province, outside the AOI
    edge = t[t["grid_id"] == "G500-E001332-N004224"].iloc[0]
    assert (edge["province"], edge["district"]) == ("Phayao", "Pong") and edge[
        "centroid_nationwide_adm1_context"
    ] == "Nan"
    assert edge["aoi_coverage_fraction_of_cell"] < 0.2 and "AOI-CLIPPED" in edge["evidence_note"]


@needs_outputs
def test_tambon_context_is_always_a_tambon_of_the_cells_own_province():
    df = pd.read_parquet(ART)
    assert (
        df["diw_tambon_pcode"] != ""
    ).all()  # edge cells are no longer left blank (which showed as 0 factories)
    assert (df["diw_tambon_pcode"].str[:4] == df["majority_pcode"]).all()
    assert df["dpim_tambon_pcode"].equals(df["diw_tambon_pcode"])
    assert df["diw_tambon_overlap_share_of_cell"].between(0, 1).all()


@needs_outputs
def test_totals_are_the_aoi_clipped_totals_after_m2d1c_and_routing_is_unchanged():
    df = pd.read_parquet(ART)
    assert df["population_worldpop2025_count_500m"].sum() == pytest.approx(3341405.0, abs=5.0)
    assert df["built_ghsl2020_surface_m2_500m"].sum() == pytest.approx(330408622, rel=0.001)
    assert df["routing_config_fingerprint"].eq("5c35e98882c3ac62").all()


def test_centroid_first_keeps_ordinary_cells_and_falls_back_only_for_edge_cells():
    polys = np.array([shapely.box(0, 0, 10, 1), shapely.box(10, 0, 20, 1)])
    cells = np.array(
        [shapely.box(2, 0, 3, 1), shapely.box(9.0, 0, 15.5, 1)]
    )  # ordinary cell in A; edge cell with centroid in B
    ids, _, method = assign_max_overlap(
        cells,
        np.array(["A", "A"]),
        polys,
        np.array(["A", "B"]),
        np.array(["unitA", "unitB"]),
        centroid_first=True,
    )
    assert ids.tolist() == ["unitA", "unitA"]
    assert method.tolist() == ["CENTROID_IN_OWN_GROUP_UNIT", "MAX_OVERLAP_WITHIN_OWN_GROUP"]


@needs_outputs
def test_artifact_records_the_tambon_assignment_method_and_only_edge_cells_use_the_fallback():
    df = pd.read_parquet(ART)
    assert set(df["diw_tambon_assignment_method"]) <= {
        "CENTROID_IN_OWN_GROUP_UNIT",
        "MAX_OVERLAP_WITHIN_OWN_GROUP",
    }
    fb = df["diw_tambon_assignment_method"] == "MAX_OVERLAP_WITHIN_OWN_GROUP"
    assert 0 < fb.sum() < 3000 and df.loc[fb, "coverage_fraction"].mean() < 0.5
