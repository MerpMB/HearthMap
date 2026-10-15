from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from hearthmap.enums import Confidence
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

H, M, L = Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW


def passes(*ids: str, confidence: Confidence = H) -> list[HardConstraintResult]:
    return [
        HardConstraintResult(
            constraint_id=i, outcome=ConstraintOutcome.PASS, reason="ok", confidence=confidence
        )
        for i in ids
    ]


def comp(dim: str, value: float | None, confidence: Confidence = H, **kw) -> ComponentScore:
    return ComponentScore(dimension_id=dim, value=value, confidence=confidence, **kw)


# ------------------------------------------------------------ arithmetic


def test_weighted_arithmetic(make_scoring_config):
    model = ScoringModel(make_scoring_config({"a": 50, "b": 30, "c": 20}))
    a = model.assess("u1", passes("flood", "slope"), [comp("a", 80), comp("b", 60), comp("c", 100)])
    assert a.status is EligibilityStatus.ELIGIBLE
    assert math.isclose(a.suitability_score, 0.5 * 80 + 0.3 * 60 + 0.2 * 100)  # 78
    assert a.coverage == pytest.approx(1.0)


def test_weights_are_normalised_regardless_of_scale(make_scoring_config):
    small = ScoringModel(make_scoring_config({"a": 5, "b": 3, "c": 2}))
    large = ScoringModel(make_scoring_config({"a": 500, "b": 300, "c": 200}))
    comps = [comp("a", 10), comp("b", 90), comp("c", 40)]
    s1 = small.assess("u", passes("flood", "slope"), comps).suitability_score
    s2 = large.assess("u", passes("flood", "slope"), comps).suitability_score
    assert math.isclose(s1, s2)
    assert math.isclose(sum(small.weights.values()), 1.0)


def test_changing_config_weights_changes_score(make_scoring_config):
    comps = [comp("a", 100), comp("b", 0)]
    heavy_a = ScoringModel(make_scoring_config({"a": 90, "b": 10}, constraints=[]))
    heavy_b = ScoringModel(make_scoring_config({"a": 10, "b": 90}, constraints=[]))
    assert heavy_a.assess("u", [], comps).suitability_score == pytest.approx(90)
    assert heavy_b.assess("u", [], comps).suitability_score == pytest.approx(10)


def test_zero_weight_dimension_does_not_block_or_contribute(make_scoring_config):
    model = ScoringModel(make_scoring_config({"a": 1, "b": 0}, constraints=[]))
    a = model.assess("u", [], [comp("a", 70)])  # b missing but weight 0
    assert a.suitability_score == pytest.approx(70)
    assert a.missing_components == []


def test_score_bounds(make_scoring_config):
    model = ScoringModel(make_scoring_config(constraints=[]))
    lo = model.assess("u", [], [comp("a", 0), comp("b", 0), comp("c", 0)])
    hi = model.assess("u", [], [comp("a", 100), comp("b", 100), comp("c", 100)])
    assert lo.suitability_score == pytest.approx(0)
    assert hi.suitability_score == pytest.approx(100)


@pytest.mark.parametrize("bad", [-1, 100.5, float("nan"), float("inf")])
def test_component_value_range_enforced(bad):
    with pytest.raises(ValidationError):
        ComponentScore(dimension_id="a", value=bad)


# ------------------------------------------------------------ exclusion


def test_failed_constraint_excludes_with_null_score(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    results = [
        HardConstraintResult(
            constraint_id="flood",
            outcome=ConstraintOutcome.FAIL,
            evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
            reason="inside observed floodway",
            confidence=M,
            source_ids=["flood-src"],
        ),
        *passes("slope"),
    ]
    perfect = [comp("a", 100), comp("b", 100), comp("c", 100)]
    a = model.assess("u", results, perfect)
    assert a.status is EligibilityStatus.EXCLUDED
    assert a.suitability_score is None  # never negative points, never a number
    assert [r.constraint_id for r in a.exclusion_reasons] == ["flood"]
    assert a.confidence is M  # confidence in the exclusion itself
    assert "flood-src" in a.source_ids
    assert not a.eligible


def test_excluded_unit_keeps_components_for_explanation_only(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    fail = HardConstraintResult(
        constraint_id="slope",
        outcome=ConstraintOutcome.FAIL,
        evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
        reason="steep",
    )
    a = model.assess("u", [fail, *passes("flood")], [comp("a", 90)])
    assert a.suitability_score is None
    assert a.components["a"].value == 90


def test_multiple_failures_all_reported(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    fails = [
        HardConstraintResult(
            constraint_id=c,
            outcome=ConstraintOutcome.FAIL,
            evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
            reason=c,
        )
        for c in ("flood", "slope")
    ]
    a = model.assess("u", fails, [])
    assert {r.constraint_id for r in a.exclusion_reasons} == {"flood", "slope"}


def test_missing_constraint_result_is_unknown_not_pass(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    a = model.assess("u", passes("flood"), [comp("a", 80), comp("b", 80), comp("c", 80)])
    assert a.status is EligibilityStatus.UNRESOLVED
    assert [r.constraint_id for r in a.unresolved_constraints] == ["slope"]
    assert a.suitability_score == pytest.approx(80)  # provisional, flagged
    assert a.confidence is Confidence.UNKNOWN
    assert any("provisional" in n for n in a.notes)


def test_strict_policy_excludes_unknown_constraints(make_scoring_config):
    model = ScoringModel(make_scoring_config(unknown_hard_constraint="exclude"))
    a = model.assess("u", passes("flood"), [comp("a", 80), comp("b", 80), comp("c", 80)])
    assert a.status is EligibilityStatus.EXCLUDED
    assert a.suitability_score is None
    assert [r.constraint_id for r in a.exclusion_reasons] == ["slope"]


def test_failure_takes_precedence_over_unknown(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    fail = HardConstraintResult(
        constraint_id="flood",
        outcome=ConstraintOutcome.FAIL,
        evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
        reason="x",
    )
    a = model.assess("u", [fail], [])
    assert a.status is EligibilityStatus.EXCLUDED
    assert [r.constraint_id for r in a.exclusion_reasons] == ["flood"]


def test_disabled_constraint_is_ignored(make_scoring_config):
    cfg = make_scoring_config()
    raw = cfg.model_dump()
    raw["hard_constraints"][1]["enabled"] = False  # slope disabled
    model = ScoringModel(type(cfg).model_validate(raw))
    a = model.assess("u", passes("flood"), [comp("a", 50), comp("b", 50), comp("c", 50)])
    assert a.status is EligibilityStatus.ELIGIBLE


def test_unknown_constraint_id_rejected(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    with pytest.raises(ScoringInputError, match="undefined hard constraints"):
        model.assess("u", passes("flood", "slope", "volcano"), [])


def test_duplicate_constraint_result_rejected(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    with pytest.raises(ScoringInputError, match="duplicate"):
        model.assess("u", passes("flood", "flood", "slope"), [])


def test_unknown_dimension_rejected(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    with pytest.raises(ScoringInputError, match="undefined dimensions"):
        model.assess("u", passes("flood", "slope"), [comp("zzz", 50)])


# ------------------------------------------------------------ missing components


def test_missing_component_null_total_by_default(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    a = model.assess("u", passes("flood", "slope"), [comp("a", 90), comp("b", None)])
    assert a.status is EligibilityStatus.ELIGIBLE
    assert a.suitability_score is None
    assert a.missing_components == ["b", "c"]
    assert a.coverage == pytest.approx(0.5)


def test_missing_component_renormalize(make_scoring_config):
    model = ScoringModel(
        make_scoring_config(missing_component="renormalize", min_component_coverage=0.7)
    )
    a = model.assess("u", passes("flood", "slope"), [comp("a", 90), comp("b", 40)])
    # weights a=.5, b=.3 available -> (45 + 12) / 0.8
    assert a.suitability_score == pytest.approx(71.25)
    assert a.coverage == pytest.approx(0.8)
    assert a.missing_components == ["c"]


def test_renormalize_respects_min_coverage(make_scoring_config):
    model = ScoringModel(
        make_scoring_config(missing_component="renormalize", min_component_coverage=0.9)
    )
    a = model.assess("u", passes("flood", "slope"), [comp("a", 90), comp("b", 40)])
    assert a.suitability_score is None


# ------------------------------------------------------------ confidence


def test_confidence_ordering_and_weakest_link():
    assert Confidence.weakest([H, M, L]) is L
    assert Confidence.weakest([H, Confidence.UNKNOWN]) is Confidence.UNKNOWN
    assert Confidence.weakest([]) is Confidence.UNKNOWN
    assert Confidence.UNKNOWN.rank < L.rank < M.rank < H.rank


def test_assessment_confidence_is_weakest_contributing(make_scoring_config):
    model = ScoringModel(make_scoring_config())
    a = model.assess(
        "u", passes("flood", "slope"), [comp("a", 50, H), comp("b", 50, L), comp("c", 50, M)]
    )
    assert a.confidence is L


# ------------------------------------------------------------ explanation


def test_explanation_contains_contract_sections(make_scoring_config):
    cfg = make_scoring_config()
    model = ScoringModel(cfg)
    a = model.assess(
        "SYNTH-1",
        passes("flood"),
        [
            comp("a", 96, reasons=["outside known flood extents"], source_ids=["src-a"]),
            comp("b", 83, M, concerns=["water coverage not confirmed"]),
            comp("c", 70),
        ],
    )
    text = render_explanation(a, cfg)
    for section in ("STATUS", "TOTAL", "COMPONENTS", "CONFIDENCE", "WHY", "CONCERNS", "SOURCES"):
        assert section in text
    assert "UNRESOLVED" in text
    assert "+ outside known flood extents" in text
    assert "- water coverage not confirmed" in text
    assert "slope not resolved" in text
    assert "src-a" in text


def test_explanation_for_excluded_unit_shows_no_total(make_scoring_config):
    cfg = make_scoring_config()
    fail = HardConstraintResult(
        constraint_id="flood",
        outcome=ConstraintOutcome.FAIL,
        evidence_class=EvidenceClass.DEFINITIVE_EXCLUSION,
        reason="floodway",
    )
    text = render_explanation(ScoringModel(cfg).assess("u", [fail], []), cfg)
    assert "EXCLUDED" in text
    assert "n/a" in text
    assert "x flood: floodway" in text


def test_repository_scoring_config_drives_engine(project_config):
    model = ScoringModel(project_config.scoring)
    dims = project_config.scoring.dimension_ids
    a = model.assess("u", [], [comp(d, 50) for d in dims])
    # Every real constraint is unevaluated in M0, so nothing can be ELIGIBLE.
    assert a.status is EligibilityStatus.UNRESOLVED
    assert len(a.unresolved_constraints) == len(project_config.scoring.hard_constraints)
    assert a.suitability_score == pytest.approx(50)
