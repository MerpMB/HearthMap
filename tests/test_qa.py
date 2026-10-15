"""M1A.1 QA helpers. All geometry is SYNTHETIC."""

from __future__ import annotations

import io
import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import shapely
from pydantic import ValidationError
from shapely.geometry import Polygon, box

from hearthmap.qa import (
    RepairAuditRecord,
    ReviewLayerError,
    audit_repairs,
    category_area_combinations,
    category_cell_combinations,
    corroborate_zones,
    coverage_accounting,
    disagreement_zones,
    is_review_layer,
    mark_review_only,
    threshold_distribution,
    uncertainty_cells,
)
from hearthmap.qa.repair import summarise_repairs
from hearthmap.scoring import ComponentScore, ConstraintOutcome, HardConstraintResult
from hearthmap.spatial import GridSpec, generate_grid
from hearthmap.spatial.overlay import polygon_cell_metrics
from tests.fixtures import synthetic

UTM = "EPSG:32647"
X0, Y0 = synthetic.ORIGIN_X, synthetic.ORIGIN_Y
SPEC = GridSpec(cell_size_m=500, crs=UTM)


def _gdf(geoms, **cols):
    return gpd.GeoDataFrame(cols, geometry=geoms, crs=UTM)


# ======================================================== coverage invariant


@pytest.mark.parametrize(
    "fixture", [synthetic.l_shape, synthetic.offset_square, synthetic.two_regions]
)
def test_clipped_coverage_equals_boundary_area(fixture):
    boundary = fixture()
    grid = generate_grid(boundary, SPEC)
    acc = coverage_accounting(grid["coverage_fraction"], 500, boundary.union_all().area)
    assert acc.invariant_ok
    assert acc.raw_cell_footprint_area_m2 == len(grid) * 250_000
    assert acc.edge_overhang_area_m2 == pytest.approx(
        acc.raw_cell_footprint_area_m2 - acc.clipped_coverage_area_m2
    )
    assert abs(acc.coverage_difference_m2) <= acc.tolerance_m2


def test_offset_square_overhang_is_reported_not_called_grid_area():
    boundary = synthetic.offset_square(1000, 250)  # 9 cells touched, 1 km2 inside
    grid = generate_grid(boundary, SPEC)
    acc = coverage_accounting(grid["coverage_fraction"], 500, 1_000_000).as_km2()
    assert acc["raw_cell_footprint_area_km2"] == pytest.approx(2.25)
    assert acc["clipped_coverage_area_km2"] == pytest.approx(1.0)
    assert acc["edge_overhang_area_km2"] == pytest.approx(1.25)
    assert acc["full_cells"] == 1 and acc["partial_cells"] == 8
    assert "grid_area_km2" not in acc


def test_invariant_detects_wrong_coverage():
    acc = coverage_accounting(np.array([1.0, 0.5]), 500, 250_000 * 1.4)
    assert not acc.invariant_ok


def test_coverage_fraction_out_of_range_rejected():
    with pytest.raises(ValueError):
        coverage_accounting(np.array([1.2]), 500, 1.0)


# ======================================================== fraction distribution


def test_threshold_distribution_counts_area_not_touch():
    f = [0.0, 0.005, 0.05, 0.3, 0.6, 0.8, 0.95, 1.0]
    t = threshold_distribution(f).set_index("threshold")
    assert t.loc["> 0", "cells"] == 7
    assert t.loc[">= 0.01", "cells"] == 6
    assert t.loc[">= 0.1", "cells"] == 5
    assert t.loc[">= 0.25", "cells"] == 5
    assert t.loc[">= 0.5", "cells"] == 4
    assert t.loc[">= 0.75", "cells"] == 3
    assert t.loc[">= 0.9", "cells"] == 2


def test_threshold_distribution_rejects_nan():
    with pytest.raises(ValueError, match="NaN"):
        threshold_distribution([0.1, np.nan])


def test_reserve_fraction_aggregation_uses_intersection_area():
    grid = generate_grid(synthetic.aligned_square(1000), SPEC)  # 4 cells
    # Reserve: covers one full cell, half of another, and only touches a third's edge.
    reserve = _gdf([box(X0, Y0, X0 + 500, Y0 + 500), box(X0 + 500, Y0, X0 + 750, Y0 + 500)])
    m = polygon_cell_metrics(grid, reserve, prefix="reserve")
    fr = m["reserve_affected_area_fraction"].to_numpy()
    assert sorted(fr) == pytest.approx([0, 0, 0.5, 1.0])
    t = threshold_distribution(fr, covered_area_m2=fr * 250_000).set_index("threshold")
    assert t.loc["> 0", "cells"] == 2
    assert t.loc[">= 0.9", "share_of_covered_area"] == pytest.approx(1 / 1.5)


# ======================================================== category overlaps


def test_area_combinations_partition_the_union_without_double_counting():
    a = _gdf([box(0, 0, 2, 2)])
    b = _gdf([box(1, 0, 3, 2)])
    c = _gdf([box(1.5, 0, 2.5, 1)])
    t = category_area_combinations({"reserve": a, "park": b, "sanctuary": c}).set_index(
        "combination"
    )
    m2 = t["area_km2"] * 1e6
    assert m2["reserve+park+sanctuary"] == pytest.approx(0.5)
    assert m2["reserve+park"] == pytest.approx(1.5)
    assert m2["park+sanctuary"] == pytest.approx(0.5)
    assert m2["reserve"] == pytest.approx(2.0)
    assert m2["park"] == pytest.approx(1.5)
    assert m2["sanctuary"] == pytest.approx(0)
    assert m2["reserve+sanctuary"] == pytest.approx(0)
    assert m2.sum() == pytest.approx(6.0)  # union of the three = 3 x 2
    assert t["share_of_union"].sum() == pytest.approx(1.0)


def test_cell_combinations_assign_each_cell_once():
    t = category_cell_combinations(
        {
            "reserve": np.array([0.5, 0.0, 1.0, 0.0]),
            "park": np.array([0.2, 0.3, 0.0, 0.0]),
        }
    ).set_index("combination")
    assert t.loc["reserve+park", "cells"] == 1
    assert t.loc["park", "cells"] == 1
    assert t.loc["reserve", "cells"] == 1
    assert t.loc["none", "cells"] == 1
    assert t["cells"].sum() == 4


# ======================================================== boundary disagreement


def _province(geom, code="P1"):
    return _gdf([geom], code=[code])


def test_shifted_reference_yields_measured_offset_and_material_zone():
    primary = _province(box(X0, Y0, X0 + 3000, Y0 + 3000))
    reference = _province(box(X0, Y0, X0 + 3300, Y0 + 3000))  # east edge 300 m out
    grid = generate_grid(primary, SPEC)
    z = disagreement_zones(primary, reference, key="code", reference_name="ref", grid=grid)
    assert len(z) == 1
    zone = z.iloc[0]
    assert zone["kind"] == "reference_only"
    assert zone["max_offset_m"] == pytest.approx(300, abs=1)
    assert zone["area_km2"] == pytest.approx(0.9)
    assert bool(zone["material"])  # 300 m >= 250 m default
    assert zone["zone_id"] == "ref-0001"
    assert zone["affected_grid_cells"] == 0  # zone lies outside the primary grid


def test_thin_sliver_is_generalisation_not_material():
    primary = _province(box(X0, Y0, X0 + 3000, Y0 + 3000))
    reference = _province(box(X0, Y0, X0 + 3040, Y0 + 3000))
    z = disagreement_zones(primary, reference, key="code", reference_name="ref")
    assert z.iloc[0]["provisional_class"] == "LIKELY_SOURCE_GENERALIZATION"
    assert not bool(z.iloc[0]["material"])


def test_international_border_rule_is_provisional_and_explained():
    primary = _province(box(X0, Y0, X0 + 3000, Y0 + 3000))
    reference = _province(box(X0, Y0, X0 + 4500, Y0 + 3000))
    border = shapely.LineString([(X0 + 3000, Y0), (X0 + 3000, Y0 + 3000)])
    z = disagreement_zones(
        primary, reference, key="code", reference_name="ref", national_border=border
    )
    assert z.iloc[0]["provisional_class"] == "LIKELY_BORDER_INTERPRETATION"
    assert "international border" in z.iloc[0]["classification_rule"]


def test_uncertainty_cells_are_review_only_and_refused_by_overlays():
    primary = _province(box(X0, Y0, X0 + 3000, Y0 + 3000))
    reference = _province(box(X0, Y0, X0 + 2600, Y0 + 3000))  # primary_only strip 400 m
    grid = generate_grid(primary, SPEC)
    z = disagreement_zones(primary, reference, key="code", reference_name="ref", grid=grid)
    cells = uncertainty_cells(grid, z)
    assert len(cells) == 6  # the 400 m strip touches one column of 6 cells
    assert cells["disagreement_fraction_ref"].to_numpy() == pytest.approx([0.8] * 6)
    review = mark_review_only(cells, purpose="boundary uncertainty")
    assert is_review_layer(review)
    assert set(review["decision_use"]) == {"NONE"}
    with pytest.raises(ReviewLayerError):
        polygon_cell_metrics(grid, review, prefix="boundary_uncertainty")
    # explicit QA use stays possible
    polygon_cell_metrics(grid, review, prefix="qa", allow_review=True)


def test_review_artifacts_cannot_be_cited_as_evidence():
    with pytest.raises(ValidationError, match="review artifacts"):
        ComponentScore(dimension_id="a", value=50, source_ids=["review:boundary_uncertainty"])
    with pytest.raises(ValidationError, match="review artifacts"):
        HardConstraintResult(
            constraint_id="x",
            outcome=ConstraintOutcome.UNKNOWN,
            reason="r",
            source_ids=["review:forest_review"],
        )


# ======================================================== repair audit


def _bowtie_layer():
    bow = Polygon([(X0, Y0), (X0 + 100, Y0 + 100), (X0 + 100, Y0), (X0, Y0 + 100)])
    ok = box(X0 + 200, Y0, X0 + 300, Y0 + 100)
    return _gdf([bow, ok], fid=[7, 8])


def test_repair_audit_records_changes_honestly():
    audit = audit_repairs(_bowtie_layer(), id_column="fid")
    assert len(audit) == 1  # only the invalid feature
    r = audit.iloc[0]
    assert r["source_feature_id"] == "7"
    assert "Self-intersection" in r["validity_reason_before"]
    assert r["geometry_type_after"] == "MultiPolygon"
    assert r["area_before_diagnostic_m2"] == pytest.approx(0.0)  # lobes cancel: diagnostic only
    assert r["area_after_m2"] == pytest.approx(5000.0)
    assert r["percent_area_delta"] is None or np.isnan(r["percent_area_delta"])
    assert r["component_count_after"] == 2
    assert not r["empty_after_repair"]


def test_repair_audit_serialises_roundtrip():
    audit = audit_repairs(_bowtie_layer(), id_column="fid")
    back = pd.read_csv(io.StringIO(audit.to_csv(index=False)), dtype={"source_feature_id": str})
    rec = RepairAuditRecord.model_validate(
        {
            k: (None if isinstance(v, float) and np.isnan(v) else v)
            for k, v in back.iloc[0].to_dict().items()
        }
    )
    assert rec.source_feature_id == "7"
    summary = summarise_repairs(audit, total_features=2)
    assert summary["repair_rate"] == 0.5
    assert summary["area_values_are_diagnostic"] is True
    json.dumps(summary)  # JSON-serialisable


def test_repair_audit_of_valid_layer_is_empty():
    audit = audit_repairs(_gdf([box(X0, Y0, X0 + 1, Y0 + 1)], fid=[1]), id_column="fid")
    assert audit.empty and "source_feature_id" in audit.columns


def test_corroboration_measures_line_agreement_not_area_overlap():
    primary = _province(box(X0, Y0, X0 + 3000, Y0 + 3000))
    ref_a = _province(box(X0, Y0, X0 + 3400, Y0 + 3000))  # east edge +400 m
    ref_b = _province(box(X0, Y0, X0 + 3420, Y0 + 3000))  # same alternative line (+420 m)
    ref_c = _province(box(X0, Y0, X0 + 5000, Y0 + 3000))  # zone overlaps, line far away
    za = disagreement_zones(primary, ref_a, key="code", reference_name="a")
    agree = corroborate_zones(za, primary, {"a": ref_a, "b": ref_b}, key="code")
    disagree = corroborate_zones(za, primary, {"a": ref_a, "c": ref_c}, key="code")
    assert agree[0] == pytest.approx(1.0)
    # Area overlap alone must not count: only the short shared top/bottom edges agree.
    assert disagree[0] < 0.5 < agree[0]
