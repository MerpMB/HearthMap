# ruff: noqa: E501
"""M2C evaluability plan: what evidence each calibrated requirement needs, and where it may responsibly be used.

Planning only. Nothing here reads a grid cell, scores a place or ranks anything, and ``FAMILY_SCORING_ALLOWED`` is false.
Five evidence concepts (exists, resolution, freshness, completeness, evaluation safety) are kept apart, evaluability is an explicit
per-stage state, and priorities are DERIVED from importance and explicit factors (never typed in, never from ease of acquisition).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hearthmap.family.requirements import UNSET, Requirements, leaves

PLAN_PATH = Path("config/family-evaluability.yaml")
BACKLOG_PATH = Path("config/family-evidence-backlog.yaml")
STAGES = (
    "REGIONAL_SCREENING",
    "CANDIDATE_ZONE_COMPARISON",
    "PARCEL_SHORTLIST",
    "PRE_PURCHASE_VERIFICATION",
)
STATES = (
    "READY", "READY_WITH_LIMITATIONS", "PROXY_ONLY", "PARTIAL", "NOT_EVALUABLE", "PARCEL_VERIFICATION_ONLY",
    "FIELD_VERIFICATION_ONLY", "BLOCKED_BY_SOURCE_GAP", "INTENTIONALLY_NOT_USED",
)  # fmt: skip
EVIDENCE_EXISTS = ("YES", "PARTIAL", "NO")
FRESHNESS = ("CURRENT", "ACCEPTABLE", "STALE", "NONE")
COMPLETENESS = ("HIGH", "PARTIAL", "LOW", "NONE")
SAFETY = ("SAFE", "PARTIAL", "NOT_SAFE_REGIONALLY", "NOT_APPLICABLE")
GAPS = ("EVIDENCE", "CALIBRATION", "NONE")
PRIORITIES = (
    "P0",
    "P1",
    "P2",
    "P3",
    "NO_EVIDENCE_GAP",
    "NOT_APPLICABLE_IRRELEVANT",
    "NOT_PRIORITISED_REQUIREMENT_UNSET",
)
STAGE_RANK = {s: i for i, s in enumerate(STAGES)}
MISSING_EVIDENCE_POLICY = (
    "VERIFY_NOT_PASS"  # missing or unresolved evidence is never positive evidence
)
NO_EVALUATION = ("NOT_EVALUABLE", "BLOCKED_BY_SOURCE_GAP", "INTENTIONALLY_NOT_USED")
PRIORITY_RULES = (
    "IRRELEVANT importance -> NOT_APPLICABLE_IRRELEVANT (never prioritised).",
    "No evidence gap (or the gap is owner calibration, not data) -> NO_EVIDENCE_GAP.",
    "Importance UNSET / no requirement stated -> NOT_PRIORITISED_REQUIREMENT_UNSET.",
    "Otherwise the class follows the EARLIEST decision stage at which the evidence would shape the work: regional screening -> P0, candidate-zone comparison -> P1, parcel shortlist -> P2, pre-purchase verification -> P3.",
    "P0 additionally requires importance MUST or STRONG_PREFERENCE and that the evidence changes the regional search space; otherwise a regional item is P1 (a preference never blocks regional evaluation).",
    "Acquisition feasibility, cost of false positives/negatives and source quality are recorded for planning but never change the class: an easy dataset is not prioritised for being easy.",
)  # fmt: skip


class EvaluabilityError(ValueError):
    """The evaluability plan is inconsistent with the rules (nothing is repaired silently)."""


def _yn(v: Any) -> str:
    """YAML 1.1 turns bare YES/NO into booleans; normalise to the strings used here."""
    if v is True:
        return "YES"
    if v is False:
        return "NO"
    return str(v)


def load_plan(path: Path = PLAN_PATH) -> dict[str, Any]:
    plan = yaml.safe_load(Path(path).read_text("utf-8"))
    if plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is not False:
        raise EvaluabilityError("FAMILY_SCORING_ALLOWED must stay false in M2C")
    for e in plan["entries"]:
        e["evidence"]["exists"] = _yn(e["evidence"]["exists"])
    return plan


def load_backlog(path: Path = BACKLOG_PATH) -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text("utf-8"))


def leaf_value(req: Requirements, path: str) -> Any:
    for p, v in leaves(req):
        if p == path:
            return v.value if hasattr(v, "value") else v
    raise KeyError(path)


def entry_importance(req: Requirements, entry: dict[str, Any]) -> str | None:
    path = entry.get("importance_path")
    return None if not path else str(leaf_value(req, path))


def derive_priority(importance: str | None, factors: dict[str, Any]) -> tuple[str, str]:
    """(priority class, reason). Pure function of importance and the stated factors; feasibility never matters."""
    if importance == "IRRELEVANT":
        return (
            "NOT_APPLICABLE_IRRELEVANT",
            "marked IRRELEVANT by the owner: excluded from evaluation and prioritisation",
        )
    if factors["evidence_gap"] in ("NONE", "CALIBRATION"):
        why = (
            "evidence exists; the remaining step is owner calibration"
            if factors["evidence_gap"] == "CALIBRATION"
            else "no evidence gap blocks its use"
        )
        return "NO_EVIDENCE_GAP", why
    if importance in (None, UNSET):
        return (
            "NOT_PRIORITISED_REQUIREMENT_UNSET",
            "no requirement has been stated, so evidence for it is not prioritised",
        )
    base = STAGE_RANK[factors["earliest_decision_stage"]]
    if base == 0 and not (
        importance in ("MUST", "STRONG_PREFERENCE") and factors["changes_regional_search_space"]
    ):
        base = 1
    return (
        f"P{base}",
        f"importance {importance}; earliest decision stage {factors['earliest_decision_stage']}; changes regional search space: {factors['changes_regional_search_space']}",
    )


def covered(req: Requirements, plan: dict[str, Any]) -> tuple[set[str], set[str]]:
    """(leaf paths covered by at least one entry, all leaf paths)."""
    prefixes = [p for e in plan["entries"] for p in e["requirement_paths"]]
    allp = {p for p, _ in leaves(req)}
    return {p for p in allp if any(p.startswith(pre) for pre in prefixes)}, allp


def active_leaves(req: Requirements) -> list[str]:
    """Leaves with an explicit non-UNSET value whose dimension is not IRRELEVANT."""
    from hearthmap.family.requirements import irrelevant_prefixes

    irr = irrelevant_prefixes(req)
    out = []
    for p, v in leaves(req):
        if v == UNSET:
            continue
        if any(p == pre or p.startswith(pre + ".") or p == pre + "_importance" for pre in irr):
            continue
        out.append(p)
    return out


# -- validation ---------------------------------------------------------------------------------------------
def validate_plan(
    plan: dict[str, Any], req: Requirements, backlog: dict[str, Any] | None = None
) -> list[str]:
    errs: list[str] = []
    ids = [e["id"] for e in plan["entries"]]
    if len(set(ids)) != len(ids):
        errs.append("duplicate entry ids")
    if plan["scoring_gate"]["FAMILY_SCORING_ALLOWED"] is not False:
        errs.append("FAMILY_SCORING_ALLOWED must be false")
    by_id = {e["id"]: e for e in plan["entries"]}
    for e in plan["entries"]:
        i = e["id"]
        if "priority" in e:
            errs.append(f"{i}: priority must be derived, not typed in")
        ev = e["evidence"]
        for key, vocab in (
            ("exists", EVIDENCE_EXISTS),
            ("freshness", FRESHNESS),
            ("completeness", COMPLETENESS),
            ("safety", SAFETY),
        ):
            if ev[key] not in vocab:
                errs.append(f"{i}: evidence.{key} {ev[key]!r} not in {vocab}")
        if not ev.get("resolution") or not ev.get("safety_reason"):
            errs.append(f"{i}: evidence needs resolution and safety_reason")
        if set(e["stages"]) != set(STAGES):
            errs.append(f"{i}: stages must be exactly {STAGES}")
            continue
        if (
            e["priority_factors"]["evidence_gap"] not in GAPS
            or e["priority_factors"]["earliest_decision_stage"] not in STAGES
        ):
            errs.append(f"{i}: invalid priority factors")
        if not e.get("hazard_independent", True):
            errs.append(f"{i}: hazard_independent cannot be false")
        states = {s: e["stages"][s][0] for s in STAGES}
        for s, st in states.items():
            if st not in STATES:
                errs.append(f"{i}/{s}: unknown state {st}")
        # evidence vs state coherence: a column existing never makes a requirement ready
        for s, st in states.items():
            if st == "READY" and not (
                ev["exists"] == "YES"
                and ev["freshness"] in ("CURRENT", "ACCEPTABLE")
                and ev["completeness"] == "HIGH"
                and ev["safety"] == "SAFE"
            ):
                errs.append(f"{i}/{s}: READY needs existing, fresh, complete and safe evidence")
            if st == "READY_WITH_LIMITATIONS" and ev["exists"] != "YES":
                errs.append(f"{i}/{s}: READY_WITH_LIMITATIONS needs existing evidence")
            if st == "PARTIAL" and ev["exists"] == "NO":
                errs.append(f"{i}/{s}: PARTIAL with no evidence")
            if st in ("READY", "READY_WITH_LIMITATIONS", "PARTIAL") and ev["exists"] == "NO":
                errs.append(f"{i}/{s}: {st} with no evidence")
        if any(st == "PROXY_ONLY" for st in states.values()) and not e.get("proxy_semantics"):
            errs.append(f"{i}: PROXY_ONLY stages need proxy_semantics")
        if any(st == "INTENTIONALLY_NOT_USED" for st in states.values()) and not e.get(
            "intentionally_not_used_reason"
        ):
            errs.append(f"{i}: INTENTIONALLY_NOT_USED needs a reason")
        # parcel-only / field-only requirements cannot be evaluated regionally
        if e.get("parcel_only") or e.get("field_only"):
            if states["REGIONAL_SCREENING"] not in NO_EVALUATION:
                errs.append(
                    f"{i}: parcel/field requirement cannot be evaluated at REGIONAL_SCREENING ({states['REGIONAL_SCREENING']})"
                )
            if states["CANDIDATE_ZONE_COMPARISON"] not in (*NO_EVALUATION, "PROXY_ONLY"):
                errs.append(
                    f"{i}: parcel/field requirement at CANDIDATE_ZONE_COMPARISON may only be a labelled proxy"
                )
            ok = (
                ("PARCEL_VERIFICATION_ONLY", "FIELD_VERIFICATION_ONLY")
                if e.get("parcel_only")
                else ("FIELD_VERIFICATION_ONLY",)
            )
            for s in ("PARCEL_SHORTLIST", "PRE_PURCHASE_VERIFICATION"):
                if states[s] not in ok:
                    errs.append(f"{i}/{s}: must be {ok}, not {states[s]}")
        imp = entry_importance(req, e)
        if imp == "IRRELEVANT" and any(st != "INTENTIONALLY_NOT_USED" for st in states.values()):
            errs.append(
                f"{i}: IRRELEVANT requirements must be INTENTIONALLY_NOT_USED at every stage"
            )
        for k in (
            "allowed_use",
            "forbidden_use",
            "next_evidence_needed",
            "verification_stage",
            "why",
        ):
            if not e.get(k):
                errs.append(f"{i}: missing {k}")
        if e["verification_stage"] not in STAGES:
            errs.append(f"{i}: unknown verification_stage")
        low = e["allowed_use"].lower()
        if any(
            bad in low
            for bad in (
                "treat as pass",
                "assume pass",
                "missing evidence is a pass",
                "counts as satisfied",
            )
        ):
            errs.append(f"{i}: missing evidence must never be a pass")
    # coverage: every active requirement leaf (incl. every MUST) is addressed by some entry
    cov, _ = covered(req, plan)
    for p in active_leaves(req):
        if p not in cov:
            errs.append(
                f"active requirement {p} is not covered by any evaluability entry (it cannot silently disappear)"
            )
    # every MUST requirement must have an explicit later-stage verification state OR a regional-evaluation state
    for e in plan["entries"]:
        if entry_importance(req, e) == "MUST":
            states = [e["stages"][s][0] for s in STAGES]
            if not any(
                s
                in (
                    "READY",
                    "READY_WITH_LIMITATIONS",
                    "PARTIAL",
                    "PROXY_ONLY",
                    "PARCEL_VERIFICATION_ONLY",
                    "FIELD_VERIFICATION_ONLY",
                )
                for s in states
            ):
                errs.append(f"{e['id']}: a MUST has neither an evaluation nor a verification stage")
    # semantic guards for specific families
    alt = by_id.get("ALT-CHOICES")
    if not alt or alt.get("gate") is not False or alt.get("use_as") != "DECISION_CONTEXT":
        errs.append("ALT-CHOICES must exist as decision context with gate: false")
    elif alt["stages"]["REGIONAL_SCREENING"][0] != "INTENTIONALLY_NOT_USED":
        errs.append("ALT-CHOICES must not gate regional screening")
    fiber = by_id.get("FIBER")
    if not fiber or set(fiber.get("substitutes_not_accepted", [])) != {
        "MOBILE_4G",
        "MOBILE_5G",
        "FIXED_WIRELESS",
        "SATELLITE",
    }:
        errs.append("FIBER must name the substitutes that do not satisfy it")
    water = [i for i in by_id if i.startswith("WATER-")]
    if {"WATER-PWA", "WATER-LOCAL", "WATER-VILLAGE", "WATER-GROUND"} - set(water):
        errs.append("water needs separate PWA, local public, village and groundwater paths")
    elif set(by_id["WATER-GROUND"].get("groundwater_components", [])) != {
        "aquifer_potential",
        "expected_depth",
        "yield",
        "quality",
        "legal_and_drilling_constraints",
    }:
        errs.append(
            "WATER-GROUND must separate aquifer potential, depth, yield, quality and legal/drilling constraints"
        )
    if {
        "ROAD-A-NETWORK",
        "ROAD-B-LEGAL",
        "ROAD-C-ALLWEATHER",
        "ROAD-D-SURFACE",
        "ROAD-E-NOISE",
    } - set(by_id):
        errs.append(
            "road access needs five separate concepts (network, legal, all-weather, surface, noise)"
        )
    for i in ("NUIS-INDUSTRIAL", "NUIS-MINING", "NUIS-NIGHTLIFE", "ROAD-E-NOISE"):
        if i in by_id and by_id[i].get("buffer_authorised") is not False:
            errs.append(f"{i}: no buffer/exclusion distance is authorised")
    t = by_id.get("TERRAIN-PREF")
    if not t or t.get("numeric_slope_threshold_authorised") is not False:
        errs.append("TERRAIN-PREF must not authorise a numeric slope threshold")
    pa = by_id.get("PARCEL-AREA")
    if not pa or set(pa.get("area_concepts", [])) != {
        "NOMINAL_AREA",
        "USABLE_AREA",
        "BUILDABLE_AREA",
        "ACCESSIBLE_AREA",
    }:
        errs.append("PARCEL-AREA must keep nominal, usable, buildable and accessible area apart")
    sp = by_id.get("SETTLE-PEACE")
    if not sp or not sp.get("peace_is_multi_signal"):
        errs.append("SETTLE-PEACE must treat peacefulness as multi-signal")
    if backlog is not None:
        fams = {f["id"] for f in backlog["families"]}
        cited = {f for e in plan["entries"] for f in e.get("evidence_families", [])}
        if cited - fams:
            errs.append(f"entries cite unknown evidence families {sorted(cited - fams)}")
        if fams - cited:
            errs.append(f"backlog families not cited by any entry: {sorted(fams - cited)}")
    return errs


def check_plan(
    plan: dict[str, Any], req: Requirements, backlog: dict[str, Any] | None = None
) -> None:
    errs = validate_plan(plan, req, backlog)
    if errs:
        raise EvaluabilityError("; ".join(errs))


# -- permission matrix ---------------------------------------------------------------------------------------
def _allowed(state: str, e: dict[str, Any], stage: str) -> str:
    note = e["stages"][stage][1]
    if state in ("READY", "READY_WITH_LIMITATIONS", "PARTIAL"):
        return e["allowed_use"]
    if state == "PROXY_ONLY":
        return "PROXY ONLY (labelled, never verified): " + e["allowed_use"]
    if state in ("NOT_EVALUABLE", "BLOCKED_BY_SOURCE_GAP"):
        return "none at this stage; missing evidence triggers verification, never a pass"
    if state in ("PARCEL_VERIFICATION_ONLY", "FIELD_VERIFICATION_ONLY"):
        return f"verification step only: {note}"
    return f"none: excluded from evaluation ({e.get('intentionally_not_used_reason', 'not used')})"


def _forbidden(state: str, e: dict[str, Any]) -> str:
    base = e["forbidden_use"]
    extra = {
        "PROXY_ONLY": "presenting this proxy as verified evidence",
        "NOT_EVALUABLE": "treating missing evidence as positive evidence",
        "BLOCKED_BY_SOURCE_GAP": "treating missing evidence as positive evidence",
        "PARCEL_VERIFICATION_ONLY": "satisfying this with regional evidence",
        "FIELD_VERIFICATION_ONLY": "satisfying this with regional or desk evidence",
        "PARTIAL": "presenting partial evidence as complete",
        "READY_WITH_LIMITATIONS": "hiding the stated limitations",
    }.get(state)
    return f"{base}; {extra}" if extra else base


def permission_rows(plan: dict[str, Any], req: Requirements) -> list[dict[str, Any]]:
    """One row per (requirement entry, decision stage). Planning artifact: no geographic score columns."""
    rows: list[dict[str, Any]] = []
    for e in plan["entries"]:
        imp = entry_importance(req, e)
        prio, why = derive_priority(imp, e["priority_factors"])
        ev = e["evidence"]
        for stage in STAGES:
            state, note = e["stages"][stage]
            rows.append({
                "requirement_id": e["id"], "requirement_title": e["title"], "requirement_paths": "|".join(e["requirement_paths"]),
                "requirement_importance": imp if imp is not None else "n/a", "decision_stage": stage,
                "current_evidence": ev["safety_reason"], "evidence_exists": ev["exists"], "evidence_resolution": ev["resolution"],
                "evidence_freshness": ev["freshness"], "evidence_completeness": ev["completeness"], "evaluation_safety": ev["safety"],
                "evaluability_state": state, "allowed_use": _allowed(state, e, stage), "forbidden_use": _forbidden(state, e),
                "next_evidence_needed": e["next_evidence_needed"], "priority": prio, "priority_why": f"{why}. {e['why']}",
                "verification_stage": e["verification_stage"], "missing_evidence_policy": MISSING_EVIDENCE_POLICY,
                "evidence_families": "|".join(e.get("evidence_families", [])), "notes": note,
            })  # fmt: skip
    return rows


def gate_status(plan: dict[str, Any], req: Requirements) -> dict[str, Any]:
    """Which scoring-gate criteria are currently unmet. The gate stays closed regardless (FAMILY_SCORING_ALLOWED is false)."""
    unmet, met = [], []
    for e in plan["entries"]:
        prio, _ = derive_priority(entry_importance(req, e), e["priority_factors"])
        reg = e["stages"]["REGIONAL_SCREENING"][0]
        if prio == "P0" and reg in ("NOT_EVALUABLE", "BLOCKED_BY_SOURCE_GAP", "PARTIAL"):
            unmet.append(f"P0 evidence for {e['id']} is {reg} at REGIONAL_SCREENING")
    unmet.append(
        "the owner has not reviewed the interpretation of each evaluable requirement or authorised scoring"
    )
    musts = [e["id"] for e in plan["entries"] if entry_importance(req, e) == "MUST"]
    met.append(
        f"every MUST entry has an explicit evaluation or verification stage ({len(musts)} entries)"
    )
    met.append("missing evidence is never positive (policy VERIFY_NOT_PASS on every row)")
    met.append("hazard actions remain independent and immutable")
    return {"FAMILY_SCORING_ALLOWED": False, "unmet": unmet, "met": met}


def entry_priorities(plan: dict[str, Any], req: Requirements) -> dict[str, str]:
    return {
        e["id"]: derive_priority(entry_importance(req, e), e["priority_factors"])[0]
        for e in plan["entries"]
    }


def family_priority(plan: dict[str, Any], req: Requirements, fam: str) -> str:
    prios = [
        p
        for e in plan["entries"]
        if fam in e.get("evidence_families", [])
        for p in [derive_priority(entry_importance(req, e), e["priority_factors"])[0]]
        if p.startswith("P")
    ]
    return min(prios) if prios else "NO_PRIORITY_CLASS"


# -- documents ----------------------------------------------------------------------------------------------------------
def render_backlog_md(plan: dict[str, Any], backlog: dict[str, Any], req: Requirements) -> str:
    lines = [
        "# M2C evidence acquisition backlog",
        "",
        "Generated by `python scripts/m2c/build_plan.py` from `config/family-evidence-backlog.yaml` and `config/family-evaluability.yaml`. **Planning only:**",
        "candidate sources are listed, not verified or acquired, and nothing here is acquired merely because it is listed. Priorities are derived (see rules).",
        "",
        "## Priority classes and how they are derived",
        "",
        "- **P0** blocks responsible regional evaluation; **P1** high value for candidate comparison; **P2** important for the parcel shortlist; **P3** pre-purchase / field verification.",
        *[f"- {r}" for r in PRIORITY_RULES],
        "",
        "## Priority summary",
        "",
        "| Family | Priority | Requirements served (importance) | Why |",
        "|---|---|---|---|",
    ]
    fam_rows = []
    for f in backlog["families"]:
        pr = family_priority(plan, req, f["id"])
        ents = [e for e in plan["entries"] if f["id"] in e.get("evidence_families", [])]
        served = ", ".join(f"{e['id']} ({entry_importance(req, e) or 'n/a'})" for e in ents)
        why = " ".join(
            sorted(
                {
                    e["why"]
                    for e in ents
                    if derive_priority(entry_importance(req, e), e["priority_factors"])[0] == pr
                }
            )
        )
        fam_rows.append((pr, f, served, why))
    for pr, f, served, why in sorted(
        fam_rows, key=lambda x: (not x[0].startswith("P"), x[0], x[1]["id"])
    ):
        lines.append(f"| {f['id']} {f['name']} | {pr} | {served} | {why or '-'} |")
    lines.append("")
    for pr, f, served, _ in sorted(
        fam_rows, key=lambda x: (not x[0].startswith("P"), x[0], x[1]["id"])
    ):
        lines += [
            f"## {f['id']} - {f['name']}",
            "",
            f"- **Priority:** {pr}",
            f"- **Purpose:** {f['purpose']}",
            f"- **Requirement served:** {served}",
            f"- **Current state:** {f['current_state']}",
            "- **Candidate sources (listed, not verified):**",
        ]
        for c in f["candidate_sources"]:
            reg = f" (registry `{c['registry_id']}`)" if c.get("registry_id") else ""
            lines.append(f"  - {c['name']}{reg} - {c['status']}")
        lines += [
            "- **Known limitations:** " + "; ".join(f["known_limitations"]),
            f"- **Required resolution:** {f['required_resolution']}",
            f"- **Freshness expectation:** {f['freshness_expectation']}",
            f"- **Acquisition difficulty:** {f['acquisition_difficulty']} (does not affect priority)",
            f"- **Legal / licensing:** {f['legal_licensing']}",
            f"- **Proposed milestone:** {f['proposed_milestone']}",
            "",
        ]
    return "\n".join(lines)


def _names(plan: dict[str, Any], pred) -> list[str]:
    return [f"`{e['id']}` {e['title']}" for e in plan["entries"] if pred(e)]


def render_plan_md(plan: dict[str, Any], backlog: dict[str, Any], req: Requirements) -> str:
    g = gate_status(plan, req)
    pr = entry_priorities(plan, req)

    def st(e: dict[str, Any], s: str) -> str:
        return e["stages"][s][0]

    now = _names(plan, lambda e: st(e, "REGIONAL_SCREENING") in ("READY", "READY_WITH_LIMITATIONS"))
    cannot = _names(
        plan,
        lambda e: (
            st(e, "REGIONAL_SCREENING") in ("NOT_EVALUABLE", "BLOCKED_BY_SOURCE_GAP")
            and pr[e["id"]] != "NOT_APPLICABLE_IRRELEVANT"
        ),
    )
    approx = _names(
        plan,
        lambda e: (
            st(e, "REGIONAL_SCREENING") == "PARTIAL"
            or "PROXY_ONLY" in [e["stages"][s][0] for s in STAGES[:2]]
        ),
    )
    parcel = _names(plan, lambda e: bool(e.get("parcel_only") or e.get("field_only")))
    irrelevant = _names(plan, lambda e: pr[e["id"]] == "NOT_APPLICABLE_IRRELEVANT")
    by = {p: [e for e in plan["entries"] if pr[e["id"]] == p] for p in ("P0", "P1", "P2", "P3")}
    lines = [
        "# M2C evaluability plan",
        "",
        "Plain-language plan, generated from `config/family-evaluability.yaml`. **Planning only: scoring is not authorised (`FAMILY_SCORING_ALLOWED: false`),",
        "no evaluation rule is active, no evidence is acquired here, and M1E hazard actions stay independent.** The row-level detail is in",
        "`outputs/m2c/evaluation-permission-matrix.csv` (requirement x decision stage) and the acquisition plan is `docs/research/m2c-evidence-backlog.md`.",
        "",
        "Decision stages: REGIONAL_SCREENING, CANDIDATE_ZONE_COMPARISON, PARCEL_SHORTLIST, PRE_PURCHASE_VERIFICATION. For every requirement the plan keeps",
        "five evidence concepts apart (exists, resolution, freshness, completeness, evaluation safety) and gives a state per stage: a column existing in an artifact never makes a requirement READY.",
        "",
        "## 1. What HearthMap can evaluate now (regionally, with stated limitations)",
        "",
        *[f"- {n}" for n in now],
        "",
        "Cells with no road access or beyond the search limit stay unresolved, never passing. Facility type is not capability.",
        "",
        "## 2. What it cannot evaluate (regionally)",
        "",
        *[f"- {n}" for n in cannot],
        "",
        "Missing evidence triggers verification or new evidence work, never rejection and never a pass.",
        "",
        "## 3. What can be evaluated only approximately",
        "",
        *[f"- {n}" for n in approx],
        "",
        "Partial evidence (stale or pooled education) and labelled proxies (`PROXY_ONLY`) are never presented as verified.",
        "",
        "## 4. What must wait until parcel inspection",
        "",
        *[f"- {n}" for n in parcel],
        "",
        "These are satisfied only by parcel documents, provider/PEA confirmation or field verification, never by regional evidence.",
        "",
        "Explicitly irrelevant (excluded from evaluation and prioritisation): "
        + ", ".join(irrelevant)
        + ".",
        "",
        "## 5. What evidence to acquire next (derived priorities)",
        "",
        *[f"- {r}" for r in PRIORITY_RULES],
        "",
    ]
    for p, label in (
        ("P0", "P0 - blocks responsible regional evaluation"),
        ("P1", "P1 - high value for candidate comparison"),
        ("P2", "P2 - important for the parcel shortlist"),
        ("P3", "P3 - pre-purchase / field verification"),
    ):
        lines.append(f"### {label}")
        lines.append("")
        lines += [f"- `{e['id']}` {e['title']} - {e['why']}" for e in by[p]] or ["- (none)"]
        lines.append("")
    lines += [
        "The derived priorities broadly match the expected picture: town services, settlement intensity, current education and land-market evidence",
        "sit at P0/P1; nuisance families and noise at P1; electricity, fiber, legal access, all-weather access and water verification at P2/P3. The derivation is",
        "rule-based and independent of how easy a dataset is to obtain.",
        "",
        "## 6. Why scoring is still disabled",
        "",
        "`FAMILY_SCORING_ALLOWED` is false. Criteria not yet met:",
        "",
        *[f"- {u}" for u in g["unmet"]],
        "",
        "Criteria already satisfied by the plan:",
        "",
        *[f"- {m}" for m in g["met"]],
        "",
        "Scoring could become safe only when all of these hold (the owner must then explicitly authorise it):",
        "",
        *[f"- {c}" for c in plan["scoring_gate"]["criteria"]],
        "",
    ]
    return "\n".join(lines)
