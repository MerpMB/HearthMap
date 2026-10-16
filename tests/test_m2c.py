# ruff: noqa: E501
"""M2C: evidence-gap and evaluability plan (planning only; no scoring)."""

from __future__ import annotations

import copy
from pathlib import Path

import pandas as pd
import pytest
import yaml

from hearthmap.family.evaluability import (
    STAGES,
    STATES,
    EvaluabilityError,
    active_leaves,
    check_plan,
    covered,
    derive_priority,
    entry_importance,
    entry_priorities,
    family_priority,
    gate_status,
    load_backlog,
    load_plan,
    permission_rows,
    render_backlog_md,
    render_plan_md,
    validate_plan,
)
from hearthmap.family.requirements import load_requirements
from hearthmap.provenance import load_registry

REQ = load_requirements()
PLAN = load_plan()
BACKLOG = load_backlog()


def plan_copy():
    return copy.deepcopy(PLAN)


def entry(plan, eid):
    return next(e for e in plan["entries"] if e["id"] == eid)


def errors(plan):
    return validate_plan(plan, REQ, BACKLOG)


# -- the real plan -------------------------------------------------------------------------------------
def test_the_plan_is_consistent_and_scoring_is_off():
    assert errors(PLAN) == []
    check_plan(PLAN, REQ, BACKLOG)
    assert PLAN["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is False
    g = gate_status(PLAN, REQ)
    assert g["FAMILY_SCORING_ALLOWED"] is False and g["unmet"]  # the gate stays closed and says why


def test_loader_refuses_to_enable_scoring(tmp_path):
    bad = yaml.safe_load(Path("config/family-evaluability.yaml").read_text("utf-8"))
    bad["scoring_gate"]["FAMILY_SCORING_ALLOWED"] = True
    f = tmp_path / "p.yaml"
    f.write_text(yaml.safe_dump(bad, allow_unicode=True), "utf-8")
    with pytest.raises(EvaluabilityError):
        load_plan(f)


def test_five_evidence_concepts_stay_separate_and_the_state_vocabulary_is_fixed():
    rows = permission_rows(PLAN, REQ)
    for col in (
        "evidence_exists",
        "evidence_resolution",
        "evidence_freshness",
        "evidence_completeness",
        "evaluation_safety",
        "evaluability_state",
    ):
        assert col in rows[0]
    assert set(STATES) == {
        "READY",
        "READY_WITH_LIMITATIONS",
        "PROXY_ONLY",
        "PARTIAL",
        "NOT_EVALUABLE",
        "PARCEL_VERIFICATION_ONLY",
        "FIELD_VERIFICATION_ONLY",
        "BLOCKED_BY_SOURCE_GAP",
        "INTENTIONALLY_NOT_USED",
    }
    assert "VERIFIED" not in STATES  # nothing in the plan can be 'verified' by regional evidence
    assert not [
        c for c in rows[0] if "score" in c.lower() or "rank" in c.lower()
    ]  # no geographic score columns
    assert len(rows) == len(PLAN["entries"]) * len(STAGES) and {
        r["decision_stage"] for r in rows
    } == set(STAGES)


def test_no_requirement_is_ready_merely_because_a_column_exists():
    assert not [
        r for r in permission_rows(PLAN, REQ) if r["evaluability_state"] == "READY"
    ]  # nothing meets the READY bar yet
    bad = plan_copy()
    e = entry(bad, "EDU-PRIMARY")
    e["stages"]["REGIONAL_SCREENING"][0] = "READY"  # evidence is stale and partial
    assert any("READY needs existing, fresh, complete and safe evidence" in x for x in errors(bad))


# -- coverage: MUST requirements cannot silently disappear ------------------------------------------------
def test_every_active_requirement_is_covered_and_every_must_has_a_stage():
    cov, _ = covered(REQ, PLAN)
    assert [p for p in active_leaves(REQ) if p not in cov] == []
    musts = [e["id"] for e in PLAN["entries"] if entry_importance(REQ, e) == "MUST"]
    assert {
        "EDU-PRIMARY",
        "EDU-LOWSEC",
        "HC-HOSPITAL",
        "LAND-PRICE",
        "ELEC-GRID",
        "FIBER",
        "ROAD-B-LEGAL",
        "ROAD-C-ALLWEATHER",
    } <= set(musts)


def test_dropping_an_unsupported_must_entry_is_an_error():
    for victim, leaf in (
        ("FIBER", "utilities.telecom.minimum_requirement"),
        ("LAND-PRICE", "land.land_purchase_budget.absolute_max_thb"),
        ("ELEC-GRID", "utilities.electricity.grid_service_required"),
        ("ROAD-B-LEGAL", "road_access.legal_vehicle_access.required"),
    ):
        bad = plan_copy()
        bad["entries"] = [e for e in bad["entries"] if e["id"] != victim]
        assert any(f"active requirement {leaf}" in x for x in errors(bad)), victim


def test_a_must_needs_an_evaluation_or_verification_stage():
    bad = plan_copy()
    e = entry(bad, "FIBER")
    for s in STAGES:
        e["stages"][s][0] = "NOT_EVALUABLE"
    assert any("neither an evaluation nor a verification stage" in x for x in errors(bad)) or any(
        "must be" in x for x in errors(bad)
    )


# -- parcel-only / field-only / proxy semantics ----------------------------------------------------------------
def test_parcel_only_requirements_cannot_be_evaluated_regionally():
    for eid in ("ROAD-B-LEGAL", "ELEC-GRID", "FIBER", "PARCEL-AREA"):
        bad = plan_copy()
        entry(bad, eid)["stages"]["REGIONAL_SCREENING"][0] = "PARTIAL"
        assert any("cannot be evaluated at REGIONAL_SCREENING" in x for x in errors(bad)), eid
    legal = entry(PLAN, "ROAD-B-LEGAL")
    assert (
        legal["stages"]["REGIONAL_SCREENING"][0] == "NOT_EVALUABLE"
        and legal["stages"]["PARCEL_SHORTLIST"][0] == "PARCEL_VERIFICATION_ONLY"
    )


def test_field_verification_cannot_be_satisfied_by_regional_evidence():
    for eid in ("WATER-GROUND", "WATER-VILLAGE", "ROAD-C-ALLWEATHER", "ROAD-D-SURFACE"):
        bad = plan_copy()
        entry(bad, eid)["stages"]["PRE_PURCHASE_VERIFICATION"][0] = "PARTIAL"
        assert any(
            "PRE_PURCHASE_VERIFICATION" in x and "FIELD_VERIFICATION_ONLY" in x for x in errors(bad)
        ), eid
    rows = [
        r
        for r in permission_rows(PLAN, REQ)
        if r["evaluability_state"] == "FIELD_VERIFICATION_ONLY"
    ]
    assert rows and all(
        "satisfying this with regional or desk evidence" in r["forbidden_use"] for r in rows
    )


def test_proxy_only_is_always_labelled_and_never_verified():
    rows = [r for r in permission_rows(PLAN, REQ) if r["evaluability_state"] == "PROXY_ONLY"]
    assert rows
    for r in rows:
        assert r["allowed_use"].startswith("PROXY ONLY (labelled, never verified)")
        assert "presenting this proxy as verified evidence" in r["forbidden_use"]
    bad = plan_copy()
    del entry(bad, "LAND-PRICE")["proxy_semantics"]
    assert any("PROXY_ONLY stages need proxy_semantics" in x for x in errors(bad))
    for eid in (
        "LAND-PRICE",
        "FIBER",
        "ELEC-GRID",
        "ROAD-C-ALLWEATHER",
        "ROAD-E-NOISE",
        "NUIS-NIGHTLIFE",
        "WATER-GROUND",
    ):
        assert entry(PLAN, eid)["proxy_semantics"]


def test_missing_evidence_never_becomes_positive_evidence():
    rows = permission_rows(PLAN, REQ)
    assert {r["missing_evidence_policy"] for r in rows} == {"VERIFY_NOT_PASS"}
    for r in [
        r for r in rows if r["evaluability_state"] in ("NOT_EVALUABLE", "BLOCKED_BY_SOURCE_GAP")
    ]:
        assert (
            r["allowed_use"].startswith("none at this stage")
            and "treating missing evidence as positive evidence" in r["forbidden_use"]
        )
    for e in PLAN["entries"]:
        if e["evidence"]["exists"] == "NO":
            assert not {s[0] for s in e["stages"].values()} & {
                "READY",
                "READY_WITH_LIMITATIONS",
                "PARTIAL",
            }
    bad = plan_copy()
    entry(bad, "TOWN-SERVICES")["stages"]["REGIONAL_SCREENING"][0] = (
        "PARTIAL"  # no evidence exists at all
    )
    assert any("PARTIAL with no evidence" in x for x in errors(bad))
    bad = plan_copy()
    entry(bad, "FIBER")["allowed_use"] = "assume pass when coverage data is missing"
    assert any("missing evidence must never be a pass" in x for x in errors(bad))


def test_fiber_is_not_satisfied_by_mobile_and_water_and_road_concepts_stay_separate():
    assert set(entry(PLAN, "FIBER")["substitutes_not_accepted"]) == {
        "MOBILE_4G",
        "MOBILE_5G",
        "FIXED_WIRELESS",
        "SATELLITE",
    }
    assert {"WATER-PWA", "WATER-LOCAL", "WATER-VILLAGE", "WATER-GROUND"} <= {
        e["id"] for e in PLAN["entries"]
    }
    assert set(entry(PLAN, "WATER-GROUND")["groundwater_components"]) == {
        "aquifer_potential",
        "expected_depth",
        "yield",
        "quality",
        "legal_and_drilling_constraints",
    }
    assert {
        "ROAD-A-NETWORK",
        "ROAD-B-LEGAL",
        "ROAD-C-ALLWEATHER",
        "ROAD-D-SURFACE",
        "ROAD-E-NOISE",
    } <= {e["id"] for e in PLAN["entries"]}
    assert (
        entry(PLAN, "ROAD-E-NOISE")["requirement_paths"]
        != entry(PLAN, "ROAD-A-NETWORK")["requirement_paths"]
    )  # access != noise exposure
    bad = plan_copy()
    bad["entries"] = [e for e in bad["entries"] if e["id"] != "ROAD-E-NOISE"]
    assert any("five separate concepts" in x for x in errors(bad))


def test_nuisance_terrain_and_parcel_area_semantics_are_guarded():
    for eid in ("NUIS-INDUSTRIAL", "NUIS-MINING", "NUIS-NIGHTLIFE", "ROAD-E-NOISE"):
        bad = plan_copy()
        entry(bad, eid)["buffer_authorised"] = True
        assert any("no buffer/exclusion distance is authorised" in x for x in errors(bad)), eid
    bad = plan_copy()
    entry(bad, "TERRAIN-PREF")["numeric_slope_threshold_authorised"] = True
    assert any("numeric slope threshold" in x for x in errors(bad))
    assert set(entry(PLAN, "PARCEL-AREA")["area_concepts"]) == {
        "NOMINAL_AREA",
        "USABLE_AREA",
        "BUILDABLE_AREA",
        "ACCESSIBLE_AREA",
    }
    assert entry(PLAN, "SETTLE-PEACE")["peace_is_multi_signal"] is True


# -- inactive / irrelevant / alternatives ----------------------------------------------------------------------
def test_irrelevant_requirements_never_affect_priority():
    aggressive = {
        "earliest_decision_stage": "REGIONAL_SCREENING",
        "changes_regional_search_space": True,
        "evidence_gap": "EVIDENCE",
        "regional_evidence_feasible": True,
        "feasibility": "HIGH",
        "false_positive_cost": "HIGH",
        "false_negative_cost": "HIGH",
    }
    assert derive_priority("IRRELEVANT", aggressive)[0] == "NOT_APPLICABLE_IRRELEVANT"
    pr = entry_priorities(PLAN, REQ)
    assert {pr[i] for i in ("IRR-AIRPORT", "IRR-UNIVERSITY", "IRR-VOCATIONAL")} == {
        "NOT_APPLICABLE_IRRELEVANT"
    }
    assert not [
        r
        for r in permission_rows(PLAN, REQ)
        if r["requirement_id"].startswith("IRR-")
        and r["evaluability_state"] != "INTENTIONALLY_NOT_USED"
    ]
    bad = plan_copy()
    entry(bad, "IRR-AIRPORT")["stages"]["REGIONAL_SCREENING"][0] = "PARTIAL"
    assert any("IRRELEVANT requirements must be INTENTIONALLY_NOT_USED" in x for x in errors(bad))
    text = render_backlog_md(PLAN, BACKLOG, REQ)
    assert (
        "IRR-AIRPORT" not in text.split("## EF-01")[0]
    )  # irrelevant items never enter the prioritised backlog summary


def test_inactive_unset_requirements_are_not_prioritised():
    pr = entry_priorities(PLAN, REQ)
    assert (
        pr["PARCEL-AREA"] == "NOT_PRIORITISED_REQUIREMENT_UNSET"
        and pr["HC-CAPABILITY"] == "NOT_PRIORITISED_REQUIREMENT_UNSET"
    )
    assert entry_importance(REQ, entry(PLAN, "PARCEL-AREA")) is None


def test_education_and_healthcare_alternatives_are_context_not_gates():
    alt = entry(PLAN, "ALT-CHOICES")
    assert (
        alt["gate"] is False
        and alt["use_as"] == "DECISION_CONTEXT"
        and alt["stages"]["REGIONAL_SCREENING"][0] == "INTENTIONALLY_NOT_USED"
    )
    assert "minimum-choice gate or score" in alt["forbidden_use"]
    bad = plan_copy()
    entry(bad, "ALT-CHOICES")["gate"] = True
    assert any("decision context with gate: false" in x for x in errors(bad))
    bad = plan_copy()
    entry(bad, "ALT-CHOICES")["stages"]["REGIONAL_SCREENING"][0] = "PARTIAL"
    assert any("must not gate regional screening" in x for x in errors(bad))


def test_hazard_actions_cannot_be_overridden_by_any_requirement_or_evidence_state():
    assert "immutable" in PLAN["hazard_contract"]
    bad = plan_copy()
    entry(bad, "TERRAIN-PREF")["hazard_independent"] = False
    assert any("hazard_independent cannot be false" in x for x in errors(bad))
    rows = permission_rows(PLAN, REQ)
    assert not [c for c in rows[0] if "hazard" in c.lower()]  # no hazard column can be altered here
    site = entry(PLAN, "SITE-IMPROVE")
    assert "overriding, cancelling or softening any M1E hazard action" in site["forbidden_use"]
    assert "never overrides hazard truth" in site["intentionally_not_used_reason"]


# -- priority derivation ------------------------------------------------------------------------------------------
def test_priority_is_derived_from_importance_and_stage_not_from_ease():
    f = {
        "earliest_decision_stage": "REGIONAL_SCREENING",
        "changes_regional_search_space": True,
        "evidence_gap": "EVIDENCE",
        "regional_evidence_feasible": True,
        "feasibility": "LOW",
        "false_positive_cost": "LOW",
        "false_negative_cost": "LOW",
    }
    assert (
        derive_priority("MUST", f)[0] == "P0" and derive_priority("STRONG_PREFERENCE", f)[0] == "P0"
    )
    assert (
        derive_priority("PREFERENCE", f)[0] == "P1"
    )  # a preference never blocks regional evaluation
    assert derive_priority("MUST", {**f, "changes_regional_search_space": False})[0] == "P1"
    for feas in ("LOW", "MEDIUM", "HIGH"):
        assert (
            derive_priority("MUST", {**f, "feasibility": feas})[0] == "P0"
        )  # ease of acquisition never changes the class
    assert derive_priority("MUST", {**f, "earliest_decision_stage": "PARCEL_SHORTLIST"})[0] == "P2"
    assert (
        derive_priority("MUST", {**f, "earliest_decision_stage": "PRE_PURCHASE_VERIFICATION"})[0]
        == "P3"
    )
    assert derive_priority("MUST", {**f, "evidence_gap": "NONE"})[0] == "NO_EVIDENCE_GAP"
    assert derive_priority("UNSET", f)[0] == "NOT_PRIORITISED_REQUIREMENT_UNSET"
    bad = plan_copy()
    entry(bad, "FIBER")["priority"] = "P0"
    assert any("priority must be derived" in x for x in errors(bad))


def test_derived_priorities_broadly_match_the_expected_picture():
    pr = entry_priorities(PLAN, REQ)
    for i in (
        "TOWN-SERVICES",
        "SETTLE-PEACE",
        "LAND-PRICE",
        "EDU-PRIMARY",
        "EDU-LOWSEC",
        "EDU-UPSEC",
    ):
        assert pr[i] == "P0", i
    for i in ("EDU-KG", "NUIS-INDUSTRIAL", "NUIS-MINING", "NUIS-NIGHTLIFE", "ROAD-E-NOISE"):
        assert pr[i] == "P1", i
    for i in ("FIBER", "ELEC-GRID", "ROAD-B-LEGAL", "ROAD-C-ALLWEATHER"):
        assert pr[i] == "P2", i
    for i in ("WATER-GROUND", "WATER-VILLAGE", "WATER-LOCAL"):
        assert pr[i] == "P3", i
    for i in ("HC-HOSPITAL", "HC-REGIONAL", "HC-PRIMARY", "TERRAIN-PREF"):
        assert pr[i] == "NO_EVIDENCE_GAP", (
            i
        )  # existing evidence is adequate (or the gap is calibration)


# -- backlog and documents ----------------------------------------------------------------------------------------
def test_backlog_families_are_complete_and_registry_references_exist():
    required = {
        "id",
        "name",
        "purpose",
        "current_state",
        "candidate_sources",
        "known_limitations",
        "required_resolution",
        "freshness_expectation",
        "acquisition_difficulty",
        "legal_licensing",
        "proposed_milestone",
    }
    reg = load_registry()
    for f in BACKLOG["families"]:
        assert required <= set(f), f["id"]
        assert "priority" not in f  # derived, never typed
        for c in f["candidate_sources"]:
            if c.get("registry_id"):
                assert c["registry_id"] in reg, c
    families = {f["id"] for f in BACKLOG["families"]}
    assert {
        "EF-01",
        "EF-02",
        "EF-03",
        "EF-04",
        "EF-05",
        "EF-06",
        "EF-07",
        "EF-08",
        "EF-09",
        "EF-10",
        "EF-11",
        "EF-12",
        "EF-13",
        "EF-14",
        "EF-15",
        "EF-16",
    } == families
    assert (
        family_priority(PLAN, REQ, "EF-01") == "P0"
        and family_priority(PLAN, REQ, "EF-07") == "P2"
        and family_priority(PLAN, REQ, "EF-14") == "NO_PRIORITY_CLASS"
    )
    assert not any(
        "acquired" in str(c.get("status", "")).lower() and c.get("registry_id") is None
        for f in BACKLOG["families"]
        for c in f["candidate_sources"]
        if "CANDIDATE" in c["status"]
    )


def test_generated_documents_do_not_drift_and_state_the_scoring_gate():
    plan_doc = Path("docs/product/m2c-evaluability-plan.md")
    backlog_doc = Path("docs/research/m2c-evidence-backlog.md")
    assert plan_doc.read_text("utf-8").strip() == render_plan_md(PLAN, BACKLOG, REQ).strip()
    assert backlog_doc.read_text("utf-8").strip() == render_backlog_md(PLAN, BACKLOG, REQ).strip()
    text = plan_doc.read_text("utf-8")
    for h in (
        "## 1. What HearthMap can evaluate now",
        "## 2. What it cannot evaluate",
        "## 3. What can be evaluated only approximately",
        "## 4. What must wait until parcel inspection",
        "## 5. What evidence to acquire next",
        "## 6. Why scoring is still disabled",
    ):
        assert h in text
    assert "FAMILY_SCORING_ALLOWED" in text and "no evidence is acquired here" in text


def test_matrix_file_matches_the_plan_when_built():
    f = Path("outputs/m2c/evaluation-permission-matrix.csv")
    if not f.exists():
        pytest.skip("matrix not built")
    d = pd.read_csv(f, encoding="utf-8-sig")
    assert len(d) == len(permission_rows(PLAN, REQ)) and not [
        c for c in d.columns if "score" in c.lower()
    ]
    for col in (
        "requirement_id",
        "requirement_importance",
        "decision_stage",
        "current_evidence",
        "evidence_resolution",
        "evidence_freshness",
        "evidence_completeness",
        "evaluability_state",
        "allowed_use",
        "forbidden_use",
        "next_evidence_needed",
        "priority",
        "verification_stage",
        "notes",
    ):
        assert col in d.columns
