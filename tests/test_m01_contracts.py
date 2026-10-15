"""M0.1 contracts: datum provenance, legal vs screening, ranking comparability,
overlay sampling and registry verification rules.
All geometry is SYNTHETIC."""

from __future__ import annotations

import geopandas as gpd
import pytest
from pydantic import ValidationError
from shapely.geometry import Point, box

from hearthmap.enums import Confidence
from hearthmap.provenance import DataSourceRegistry, PermittedUse, ProvenanceRecord
from hearthmap.scoring import (
    ComponentScore,
    ConstraintOutcome,
    EligibilityStatus,
    EvidenceClass,
    HardConstraintResult,
    ScoringInputError,
    ScoringModel,
    render_explanation,
)
from hearthmap.scoring.evidence import EvidenceAuthorityError, check_evidence_authority
from hearthmap.spatial import (
    GridSpec,
    TransformationSelectionError,
    generate_grid,
    plan_transformation,
    reproject_recorded,
)
from hearthmap.spatial.grid import cell_coverage
from hearthmap.spatial.overlay import polygon_cell_metrics
from tests.fixtures import synthetic

AOI = (97.3, 17.2, 100.9, 20.5)


# ======================================================== datum transformation


def test_indian1975_record_names_operation_code_and_accuracy():
    _, rec = plan_transformation("EPSG:24047", "EPSG:32647", area_of_interest=AOI)
    assert rec.datum_change
    assert rec.source_datum == "Indian 1975"
    assert "World Geodetic System 1984" in rec.target_datum
    assert rec.transformation_codes  # e.g. ["EPSG:1812"]
    assert all(c.startswith("EPSG:") for c in rec.transformation_codes)
    assert rec.accuracy_m is not None and rec.accuracy_m > 0
    assert len(rec.candidates) > 1  # alternatives existed ...
    assert rec.selection == "best_ranked"  # ... so the choice is recorded as such
    assert rec.proj_pipeline and rec.pyproj_version and rec.proj_version


def test_ballpark_operation_never_chosen_by_default():
    _, rec = plan_transformation("EPSG:24047", "EPSG:32647", area_of_interest=AOI)
    assert not any(s.ballpark for s in rec.steps)
    assert any("allpark" in c for c in rec.candidates)  # it was offered and refused


def test_pinned_operation_is_used_and_recorded():
    _, best = plan_transformation("EPSG:24047", "EPSG:32647", area_of_interest=AOI)
    alt_code = "EPSG:1304"
    assert alt_code not in best.transformation_codes
    _, rec = plan_transformation("EPSG:24047", "EPSG:32647", area_of_interest=AOI, pinned=alt_code)
    assert rec.selection == "pinned"
    assert rec.transformation_codes == [alt_code]


def test_unavailable_pinned_operation_raises():
    with pytest.raises(TransformationSelectionError, match="pinned"):
        plan_transformation("EPSG:24047", "EPSG:32647", pinned="EPSG:99999")


def test_same_datum_is_a_conversion_with_zero_accuracy_loss():
    _, rec = plan_transformation("EPSG:4326", "EPSG:32647", area_of_interest=AOI)
    assert not rec.datum_change
    assert rec.transformation_codes == []
    assert rec.accuracy_m == 0.0
    assert rec.selection == "only_candidate"


def test_alternative_operations_move_points_differently():
    pt = gpd.GeoDataFrame(geometry=[Point(500_000, 2_000_000)], crs="EPSG:24047")
    a, ra = reproject_recorded(pt, "EPSG:32647", area_of_interest=AOI, pinned="EPSG:1812")
    b, rb = reproject_recorded(pt, "EPSG:32647", area_of_interest=AOI, pinned="EPSG:1304")
    gap = a.geometry.iloc[0].distance(b.geometry.iloc[0])
    assert gap > 0.1  # choice of operation matters, hence must be recorded
    assert ra.transformation_codes != rb.transformation_codes


def test_transformation_record_roundtrips_through_provenance():
    _, rec = plan_transformation("EPSG:24047", "EPSG:32647", area_of_interest=AOI)
    prov = ProvenanceRecord(artifact_id="x", crs_transformations=[rec])
    back = ProvenanceRecord.from_json(prov.to_json())
    assert back.crs_transformations[0] == rec


# ======================================================== legal vs screening


def _flag(cid: str, ec=EvidenceClass.REQUIRES_LEGAL_VERIFICATION) -> HardConstraintResult:
    return HardConstraintResult(
        constraint_id=cid,
        outcome=ConstraintOutcome.FLAG,
        reason="inside reserve polygon",
        evidence_class=ec,
        confidence=Confidence.LOW,
        source_ids=["forest-reserve-rfd"],
    )


def _pass(cid: str) -> HardConstraintResult:
    return HardConstraintResult(
        constraint_id=cid, outcome=ConstraintOutcome.PASS, reason="ok", confidence=Confidence.HIGH
    )


def _perfect(*dims: str) -> list[ComponentScore]:
    return [ComponentScore(dimension_id=d, value=100, confidence=Confidence.HIGH) for d in dims]


@pytest.mark.parametrize(
    "ec", [EvidenceClass.SCREENING_WARNING, EvidenceClass.REQUIRES_LEGAL_VERIFICATION]
)
@pytest.mark.parametrize("policy", ["unresolved", "exclude"])
def test_flag_never_becomes_exclusion(make_scoring_config, ec, policy):
    model = ScoringModel(make_scoring_config(unknown_hard_constraint=policy))
    a = model.assess("u", [_flag("flood", ec), _pass("slope")], _perfect("a", "b", "c"))
    assert a.status is EligibilityStatus.UNRESOLVED
    assert a.exclusion_reasons == []
    assert a.exclusion_basis is None
    assert [f.constraint_id for f in a.flags] == ["flood"]
    assert not a.rankable


def test_fail_requires_definitive_evidence_class():
    with pytest.raises(ValidationError, match="DEFINITIVE_EXCLUSION"):
        HardConstraintResult(
            constraint_id="x",
            outcome=ConstraintOutcome.FAIL,
            reason="r",
            evidence_class=EvidenceClass.SCREENING_WARNING,
        )
    with pytest.raises(ValidationError):
        HardConstraintResult(constraint_id="x", outcome=ConstraintOutcome.FAIL, reason="r")


def test_flag_cannot_claim_definitive():
    with pytest.raises(ValidationError, match="FLAG requires"):
        HardConstraintResult(
            constraint_id="x",
            outcome=ConstraintOutcome.FLAG,
            reason="r",
            evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
        )


def test_fail_rejected_where_constraint_forbids_definitive(make_scoring_config):
    model = ScoringModel(make_scoring_config(definitive=False))
    fail = HardConstraintResult(
        constraint_id="flood",
        outcome=ConstraintOutcome.FAIL,
        reason="r",
        evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
    )
    with pytest.raises(ScoringInputError, match="does not permit definitive"):
        model.assess("u", [fail], [])


def test_repository_legal_constraints_forbid_definitive(project_config):
    legal = {
        "protected_or_state_land",
        "restricted_land_rights",
        "incompatible_planning",
        "no_legal_access",
    }
    cfg = {c.id: c for c in project_config.scoring.hard_constraints}
    assert all(not cfg[c].definitive_exclusion_allowed for c in legal)


def test_strict_policy_exclusion_is_labelled_as_policy(make_scoring_config):
    model = ScoringModel(make_scoring_config(unknown_hard_constraint="exclude"))
    a = model.assess("u", [_pass("flood")], _perfect("a", "b", "c"))
    assert a.status is EligibilityStatus.EXCLUDED
    assert a.exclusion_basis == "conservative_policy"


def test_explanation_lists_flags_as_not_exclusions(make_scoring_config):
    cfg = make_scoring_config()
    a = ScoringModel(cfg).assess("u", [_flag("flood"), _pass("slope")], _perfect("a", "b", "c"))
    text = render_explanation(a, cfg)
    assert "REQUIRES VERIFICATION (not an exclusion)" in text
    assert "REQUIRES_LEGAL_VERIFICATION" in text
    assert "EXCLUDED BECAUSE" not in text


SYNTHETIC_VERIFIED = {
    "id": "test-src",
    "name": "SYNTHETIC verified source",
    "category": "flood",
    "priority": "must_have",
    "verification_status": "VERIFIED",
    "role": "PRIMARY",
    "permitted_uses": ["REGIONAL_SCREENING"],
    "publisher": "SYNTHETIC publisher",
    "dataset_title": "SYNTHETIC dataset",
    "landing_page": "https://example.invalid/landing",
    "data_endpoint": "https://example.invalid/data",
    "format": "GeoJSON",
    "source_crs": "EPSG:4326",
    "license_or_usage_notes": "SYNTHETIC licence",
    "verification_evidence": "SYNTHETIC: opened sample",
    "last_verified": "2026-01-01",
    "local_raw_path": "data/raw/test-src/v1/",
    "processing_status": "PROCESSED",
}


def _registry_with(entry_overrides: dict) -> DataSourceRegistry:
    entry = {**SYNTHETIC_VERIFIED, **entry_overrides}
    return DataSourceRegistry.model_validate({"schema_version": 1, "sources": [entry]})


def _fail(src: str) -> HardConstraintResult:
    return HardConstraintResult(
        constraint_id="flood",
        outcome=ConstraintOutcome.FAIL,
        reason="r",
        evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
        source_ids=[src],
    )


def test_fail_on_screening_only_source_is_refused():
    reg = _registry_with({"permitted_uses": ["REGIONAL_SCREENING", "LEGAL_WARNING_ONLY"]})
    with pytest.raises(EvidenceAuthorityError, match="not verified for hard exclusion"):
        check_evidence_authority([_fail("test-src")], reg)


def test_fail_on_unregistered_source_is_refused():
    reg = _registry_with({})
    with pytest.raises(EvidenceAuthorityError):
        check_evidence_authority([_fail("nowhere")], reg)


def test_fail_on_exclusion_grade_source_is_accepted():
    reg = _registry_with({"permitted_uses": ["POTENTIAL_HARD_EXCLUSION"]})
    check_evidence_authority([_fail("test-src")], reg)
    assert reg.permits("test-src", PermittedUse.POTENTIAL_HARD_EXCLUSION)


def test_flags_need_no_exclusion_authority():
    reg = _registry_with({})
    check_evidence_authority([_flag("flood")], reg)


# ======================================================== ranking comparability


def test_complete_eligible_score_is_rankable(make_scoring_config):
    m = ScoringModel(make_scoring_config())
    a = m.assess("u", [_pass("flood"), _pass("slope")], _perfect("a", "b", "c"))
    assert a.rankable and a.score_basis == "complete"


def test_renormalised_score_is_not_rankable(make_scoring_config):
    m = ScoringModel(
        make_scoring_config(missing_component="renormalize", min_component_coverage=0.5)
    )
    a = m.assess("u", [_pass("flood"), _pass("slope")], _perfect("a", "b"))
    assert a.suitability_score is not None
    assert a.score_basis == "renormalized"
    assert not a.rankable


def test_rank_never_mixes_incomplete_with_complete(make_scoring_config):
    m = ScoringModel(
        make_scoring_config(missing_component="renormalize", min_component_coverage=0.5)
    )
    ok = [_pass("flood"), _pass("slope")]
    complete = m.assess(
        "complete",
        ok,
        [ComponentScore(dimension_id=d, value=60, confidence=Confidence.HIGH) for d in "abc"],
    )
    partial = m.assess("partial", ok, _perfect("a", "b"))  # 100 on fewer dimensions
    unresolved = m.assess("unresolved", [_pass("flood")], _perfect("a", "b", "c"))
    ranked = m.rank([partial, unresolved, complete])
    assert [a.unit_id for a in ranked] == ["complete"]


def test_experimental_mode_ranks_incomplete_with_warning(make_scoring_config):
    m = ScoringModel(
        make_scoring_config(
            missing_component="renormalize",
            min_component_coverage=0.5,
            allow_incomplete_ranking=True,
        )
    )
    partial = m.assess("partial", [_pass("flood"), _pass("slope")], _perfect("a", "b"))
    assert partial.rankable
    assert any("EXPERIMENTAL" in n for n in partial.notes)


def test_repository_config_disables_incomplete_ranking(project_config):
    assert project_config.scoring.policies.allow_incomplete_ranking is False


# ======================================================== overlay / sampling


SPEC = GridSpec(cell_size_m=500, crs="EPSG:32647")


def _features(geoms, **cols):
    return gpd.GeoDataFrame(cols, geometry=geoms, crs="EPSG:32647")


def test_narrow_off_centroid_hazard_is_not_lost():
    grid = generate_grid(synthetic.aligned_square(500), SPEC)  # one cell
    x, y = synthetic.ORIGIN_X, synthetic.ORIGIN_Y
    strip = box(x, y, x + 500, y + 10)  # 10 m wide along the cell edge, far from centroid
    m = polygon_cell_metrics(grid, _features([strip], sev=[9]), prefix="h", value_column="sev")
    assert not strip.contains(grid.geometry.iloc[0].centroid)
    assert m["h_affected_area_fraction"].iloc[0] == pytest.approx(0.02)
    assert m["h_max_sev"].iloc[0] == 9
    assert m["h_feature_count"].iloc[0] == 1


def test_overlapping_features_are_not_double_counted():
    grid = generate_grid(synthetic.aligned_square(500), SPEC)
    x, y = synthetic.ORIGIN_X, synthetic.ORIGIN_Y
    a = box(x, y, x + 300, y + 500)
    b = box(x + 200, y, x + 500, y + 500)
    m = polygon_cell_metrics(grid, _features([a, b], v=[1, 4]), prefix="f", value_column="v")
    assert m["f_affected_area_fraction"].iloc[0] == pytest.approx(1.0)
    assert m["f_max_v"].iloc[0] == 4


def test_edge_touching_feature_does_not_count():
    grid = generate_grid(synthetic.aligned_square(500), SPEC)
    x, y = synthetic.ORIGIN_X, synthetic.ORIGIN_Y
    neighbour = box(x + 500, y, x + 1000, y + 500)
    m = polygon_cell_metrics(grid, _features([neighbour]), prefix="f")
    assert m["f_affected_area_fraction"].iloc[0] == 0
    assert m["f_feature_count"].iloc[0] == 0


def test_no_feature_gives_zero_fraction_and_null_max():
    grid = generate_grid(synthetic.aligned_square(1000), SPEC)
    far = box(0, 0, 10, 10)
    m = polygon_cell_metrics(grid, _features([far], v=[3]), prefix="f", value_column="v")
    assert (m["f_affected_area_fraction"] == 0).all()
    assert m["f_max_v"].isna().all()


def test_overlay_requires_matching_crs():
    grid = generate_grid(synthetic.aligned_square(500), SPEC)
    other = gpd.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")
    with pytest.raises(ValueError, match="CRS"):
        polygon_cell_metrics(grid, other, prefix="f")


def test_cell_coverage_matches_direct_intersection_on_l_shape():
    grid = generate_grid(synthetic.l_shape(), GridSpec(cell_size_m=250, crs="EPSG:32647"))
    area = synthetic.l_shape().geometry.iloc[0]
    fast = cell_coverage(grid.geometry.values, area, 250, tile_factor=3)
    direct = grid.geometry.intersection(area).area.to_numpy() / 250**2
    assert fast == pytest.approx(direct)


# ======================================================== registry verification state


@pytest.mark.parametrize(
    "field",
    [
        "landing_page",
        "data_endpoint",
        "source_crs",
        "license_or_usage_notes",
        "verification_evidence",
        "last_verified",
        "permitted_uses",
    ],
)
def test_verified_entry_requires_full_verification_record(field):
    with pytest.raises(ValidationError, match="VERIFIED entries require"):
        _registry_with({field: [] if field == "permitted_uses" else None})


def test_synthetic_verified_entry_is_valid():
    assert "test-src" in _registry_with({})


def test_legal_warning_source_cannot_verify_parcels():
    with pytest.raises(ValidationError, match="cannot verify parcels"):
        _registry_with({"permitted_uses": ["LEGAL_WARNING_ONLY", "PARCEL_LEGAL_VERIFICATION"]})
