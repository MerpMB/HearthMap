"""Natural Hazard integration (M1E): hazard-family outcomes -> decision ACTIONS, no scalar score.

Every family (flood, landslide, terrain proxy, seismic shaking, fault context, historical
seismicity) independently yields severity, confidence, recommended action and reason codes.
The integration layer only *adds* decision axes on top of them:

    regional_search_action       what to do with the search area (hydrogeomorphic only)
    site_verification_action     whether site information must be verified
    engineering_mitigation_action  whether design mitigation matters (seismic)
    data_completeness            regional evidence completeness (site response always missing)

Rules enforced here (and tested): seismic results never change the regional search action;
seismic mildness can never cancel flood or landslide evidence; avoidance and mitigation stay
distinct; engineering mitigation never changes search eligibility; unknown ground response
stays visible; nothing is averaged and no hazard score can be produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from hearthmap.config.loader import ConfigError, load_yaml

FAMILIES = (
    "flood",
    "landslide",
    "terrain",
    "seismic_shaking",
    "fault_context",
    "historical_seismicity",
)
HYDRO_FAMILIES = ("flood", "landslide", "terrain")
SEARCH_ACTIONS = (
    "CONTINUE_SEARCH",
    "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION",
    "DEPRIORITIZE_REGION",
    "UNRESOLVED",
)
COMPLETENESS = (
    "REGIONAL_COMPLETE_SITE_RESPONSE_MISSING",
    "PARTIAL_REGIONAL_EVIDENCE",
    "CRITICAL_REGIONAL_GAP",
)
INTEGRATED_STATES = (
    "NO_MAJOR_ACTION_TRIGGERED",
    "VERIFY_SITE",
    "ENGINEERING_MITIGATION_REQUIRED",
    "STRONG_AVOIDANCE_SIGNAL",
    "MULTIPLE_ACTIONS",
    "UNRESOLVED",
)
FORBIDDEN_WORDS = ("HAZARD_SCORE", "SAFE", "NO_RISK")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntegrationConfig(_M):
    schema_version: Literal[1]
    integration_id: str
    integration_version: str
    status: Literal["PROVISIONAL"]
    default_integration_policy: None
    scoring_activated: Literal[False]
    actions: list[str]
    response_classes: list[str]
    rule_responses: dict[str, dict]
    family_actions: dict[str, dict[str, str]]
    family_response_class: dict[str, dict[str, str]]
    confidence: dict[str, dict[str, str]]
    hydro_code_families: dict
    integration_policies: dict[str, dict]
    reference_policy_for_main_outputs: str
    parcel_handoff: dict[str, list[str]]
    future_suitability_contract: dict
    prohibited_evidence_columns: list[str]
    reason_codes: dict[str, str]

    @model_validator(mode="after")
    def _guards(self) -> IntegrationConfig:
        if set(self.family_actions) != set(FAMILIES):
            raise ValueError("every hazard family needs its own action mapping")
        for fam, mp in self.family_actions.items():
            for sev, act in mp.items():
                if act not in self.actions:
                    raise ValueError(f"{fam}/{sev}: unknown action {act}")
        for fam in ("terrain", "fault_context", "historical_seismicity"):
            if "STRONG_AVOIDANCE_SIGNAL" in self.family_actions[fam].values():
                raise ValueError(f"{fam} may never produce a strong avoidance signal")
        for fam in ("seismic_shaking", "fault_context", "historical_seismicity"):
            if "STRONG_AVOIDANCE_SIGNAL" in self.family_actions[fam].values():
                raise ValueError("seismic families do not create regional avoidance in v0.1")
        if self.family_actions["historical_seismicity"].get("STRONG") not in (
            "CONTEXT_ONLY",
            "NO_MAJOR_ACTION_TRIGGERED",
        ):
            raise ValueError("historical seismicity is corroborating context only")
        if self.family_actions["fault_context"].get("STRONG") not in (
            "VERIFY_SITE",
            "NO_MAJOR_ACTION_TRIGGERED",
        ):
            raise ValueError("fault proximity is verification at most")
        for rule, r in self.rule_responses.items():
            if r["primary"] not in self.response_classes:
                raise ValueError(f"{rule}: unknown response class")
        if self.reference_policy_for_main_outputs not in self.integration_policies:
            raise ValueError("unknown reference integration policy")
        if self.future_suitability_contract.get("activated") is not False:
            raise ValueError("the future suitability contract must not be activated in M1E")
        text = " ".join(self.reason_codes).upper()
        if any(w in text for w in ("SAFE_", "HAZARD_SCORE")):
            raise ValueError("reason codes must not claim safety or define a hazard score")
        return self


def load_integration_config(
    path: Path | str = "config/hazard-integration.yaml",
) -> IntegrationConfig:
    try:
        return IntegrationConfig.model_validate(load_yaml(Path(path)))
    except ValidationError as exc:
        raise ConfigError(f"invalid hazard integration config {path}:\n{exc}") from exc


# ---------------------------------------------------------------- inputs

HYDRO_INPUTS = (
    "regional_search_status",
    "flood_policy_level",
    "landslide_policy_level",
    "terrain_policy_level",
    "hazard_reason_codes",
    "unresolved_reasons",
    "evidence_completeness_class",
    "landslide_assessment_status",
)
SEISMIC_INPUTS = (
    "seismic_screening_interpretation",
    "fault_tier",
    "modelled_hazard_tier",
    "history_tier",
    "seismic_reason_codes",
    "seismic_unresolved_reasons",
    "ground_response_status",
)
_SEV = {"NONE": "NONE", "VERIFY": "VERIFY", "STRONG": "STRONG", "DEPRIORITIZE": "STRONG"}


def _split(codes: pd.Series) -> list[list[str]]:
    return [[c for c in str(v).split("|") if c and c != "nan"] for v in codes]


def _hydro_family_codes(codes: list[list[str]], cfg: IntegrationConfig) -> dict[str, list[str]]:
    hf = cfg.hydro_code_families
    out = {f: [] for f in (*HYDRO_FAMILIES, "multi")}
    for row in codes:
        buckets = {f: [] for f in out}
        for c in row:
            if c in hf["flood"] or c.startswith(hf["flood_prefix"]):
                buckets["flood"].append(c)
            elif c in hf["landslide"]:
                buckets["landslide"].append(c)
            elif c in hf["terrain"]:
                buckets["terrain"].append(c)
            elif c in hf["multi"]:
                buckets["multi"].append(c)
        for f in out:
            out[f].append("|".join(buckets[f]))
    return out


def family_assessments(
    hydro: pd.DataFrame, seismic: pd.DataFrame, cfg: IntegrationConfig
) -> pd.DataFrame:
    """Independent per-family severity / confidence / action / response / reason codes.

    ``hydro`` is the output of the selected hydrogeomorphic policy (``apply_policy``) and
    ``seismic`` the M1D evidence; inputs are not modified and no other column is read.
    """
    for need, frame in ((HYDRO_INPUTS, hydro), (SEISMIC_INPUTS, seismic)):
        miss = [c for c in need if c not in frame.columns]
        if miss:
            raise KeyError(f"missing integration input columns: {miss}")
    if len(hydro) != len(seismic):
        raise ValueError("hydrogeomorphic and seismic inputs must cover the same cells")
    n = len(hydro)
    out = pd.DataFrame(index=range(n))
    hcodes = _hydro_family_codes(_split(hydro["hazard_reason_codes"]), cfg)

    def put(fam: str, severity: np.ndarray, positive: np.ndarray, assessed: np.ndarray, codes):
        sev = np.asarray(severity, dtype=object)
        out[f"{fam}_severity"] = sev
        out[f"{fam}_recommended_action"] = [cfg.family_actions[fam][s] for s in sev]
        out[f"{fam}_response_class"] = [cfg.family_response_class[fam].get(s, "NONE") for s in sev]
        cf = cfg.confidence[fam]
        out[f"{fam}_confidence"] = np.where(
            ~assessed,
            cf.get("not_assessed", "UNKNOWN"),
            np.where(positive, cf["positive"], cf["absent"]),
        )
        out[f"{fam}_reason_codes"] = codes

    ones = np.ones(n, dtype=bool)
    fl = np.array([_SEV[s] for s in hydro["flood_policy_level"]], dtype=object)
    put("flood", fl, fl != "NONE", ones, hcodes["flood"])
    raw = hydro["landslide_policy_level"].to_numpy()
    ls = np.array([_SEV.get(s, s) for s in raw], dtype=object)  # NOT_ASSESSED stays visible
    ls_assessed = ls != "NOT_ASSESSED"
    put("landslide", ls, ~np.isin(ls, ["NONE", "NOT_ASSESSED"]), ls_assessed, hcodes["landslide"])
    te = np.array([_SEV[s] for s in hydro["terrain_policy_level"]], dtype=object)
    te_unres = (
        hydro["unresolved_reasons"]
        .astype(str)
        .str.contains("TERRAIN_SUPPORT_INSUFFICIENT")
        .to_numpy()
    )
    te = np.where(te_unres & (te == "NONE"), "UNRESOLVED", te)
    put("terrain", te, np.isin(te, ["VERIFY"]), ~te_unres, hcodes["terrain"])

    sr = seismic["seismic_reason_codes"].astype(str)
    mh = seismic["modelled_hazard_tier"].to_numpy()
    escalated = sr.str.contains("BORDERLINE_ESCALATED_BY_CORROBORATING_SIGNALS").to_numpy()
    shaking = np.where(
        (mh == "STRONG_TIER") | escalated, "STRONG", np.where(mh == "NOTABLE", "VERIFY", "NONE")
    )
    zone_unres = (
        seismic["seismic_unresolved_reasons"]
        .astype(str)
        .str.contains("SHAKING_ZONE_NOT_ASSESSED")
        .to_numpy()
    )
    shaking = np.where(zone_unres & (shaking == "NONE"), "UNRESOLVED", shaking)
    sc = _split(sr)
    sh_codes = [
        "|".join(c for c in row if c.startswith(("MODELLED_HAZARD", "BORDERLINE"))) for row in sc
    ]
    put("seismic_shaking", shaking, shaking != "NONE", ~zone_unres, sh_codes)
    ft = seismic["fault_tier"].to_numpy()
    fault = np.where(ft == "STRONG_TIER", "STRONG", np.where(ft == "NOTABLE", "VERIFY", "NONE"))
    put(
        "fault_context",
        fault,
        fault != "NONE",
        ones,
        ["|".join(c for c in row if c.startswith("FAULT_")) for row in sc],
    )
    ht = seismic["history_tier"].to_numpy()
    hist = np.where(ht == "STRONG_TIER", "STRONG", np.where(ht == "NOTABLE", "VERIFY", "NONE"))
    put(
        "historical_seismicity",
        hist,
        hist != "NONE",
        ones,
        ["|".join(c for c in row if c.startswith("HISTORICAL_")) for row in sc],
    )
    return out


# ---------------------------------------------------------------- integration


def _search_action(
    fam: pd.DataFrame, hydro_status: np.ndarray, policy: str, cfg: IntegrationConfig
) -> np.ndarray:
    """Regional search action from HYDROGEOMORPHIC outcomes only (seismic never enters)."""
    how = cfg.integration_policies[policy]["deprioritize_when"]
    avoid_fl = (fam["flood_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL").to_numpy()
    avoid_ls = (fam["landslide_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL").to_numpy()
    any_avoid = avoid_fl | avoid_ls
    if how == "hydro_status_deprioritize":
        depri = hydro_status == "REGIONAL_DEPRIORITIZE"
    elif how == "any_hydro_avoidance_signal":
        depri = any_avoid | (hydro_status == "REGIONAL_DEPRIORITIZE")
    elif how == "multiple_hydro_avoidance_signals":
        depri = avoid_fl & avoid_ls
    else:
        raise ValueError(f"unknown deprioritization rule {how}")
    unresolved = hydro_status == "UNRESOLVED"
    return np.where(
        depri,
        "DEPRIORITIZE_REGION",
        np.where(
            unresolved,
            "UNRESOLVED",
            np.where(any_avoid, "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION", "CONTINUE_SEARCH"),
        ),
    )


def integrate(hydro: pd.DataFrame, seismic: pd.DataFrame, cfg: IntegrationConfig) -> pd.DataFrame:
    """Per-cell decision axes + dimension-preserving integrated state (never averaged)."""
    fam = family_assessments(hydro, seismic, cfg)
    n = len(fam)
    out = fam.copy()
    hs = hydro["regional_search_status"].to_numpy()
    ref = cfg.reference_policy_for_main_outputs
    for name in cfg.integration_policies:
        col = "regional_search_action" if name == ref else f"regional_search_action__{name.lower()}"
        out[col] = _search_action(fam, hs, name, cfg)
    acts = {f: fam[f"{f}_recommended_action"].to_numpy() for f in FAMILIES}
    verify = np.vstack([acts[f] == "VERIFY_SITE" for f in FAMILIES])
    avoid = np.vstack([acts[f] == "STRONG_AVOIDANCE_SIGNAL" for f in FAMILIES]).any(axis=0)
    mitigate = np.vstack([acts[f] == "ENGINEERING_MITIGATION_REQUIRED" for f in FAMILIES]).any(
        axis=0
    )
    unres_family = np.vstack([acts[f] == "UNRESOLVED" for f in FAMILIES]).any(axis=0)
    seis_state = seismic["seismic_screening_interpretation"].to_numpy()
    # Verification TRIGGERS: a family whose action is VERIFY_SITE, plus the seismic screening
    # state itself when it requires verification without any seismic family action doing so
    # (the M1D state also verifies on a nearby recorded event, which the history family
    # reports as CONTEXT_ONLY). The flag and the trigger count describe the same population:
    # flag == (trigger count >= 1), by construction (M1E.1 accounting correction).
    state_only = np.isin(seis_state, ["REQUIRES_SEISMIC_VERIFICATION"]) & ~verify.any(axis=0)
    verify_any = verify.any(axis=0) | state_only
    out["site_verification_action"] = np.where(verify_any, "VERIFY_SITE_REQUIRED", "NONE_TRIGGERED")
    out["site_verification_families"] = [
        "|".join(
            [f for f, v in zip(FAMILIES, col, strict=True) if v] + (["seismic_state"] if so else [])
        )
        for col, so in zip(verify.T, state_only, strict=True)
    ]
    out["site_verification_burden_count"] = verify.sum(axis=0) + state_only.astype(int)
    out["engineering_mitigation_action"] = np.where(
        mitigate, "SEISMIC_DESIGN_REQUIRED", "NONE_TRIGGERED"
    )
    out["ground_response_status"] = seismic["ground_response_status"].to_numpy()
    out["site_response_investigation"] = "REQUIRED_FOR_ANY_PARCEL"
    comp = hydro["evidence_completeness_class"].to_numpy()
    out["data_completeness"] = np.where(
        comp == "UNRESOLVED_CRITICAL",
        "CRITICAL_REGIONAL_GAP",
        np.where(
            (comp == "UNRESOLVED_PARTIAL") | unres_family,
            "PARTIAL_REGIONAL_EVIDENCE",
            "REGIONAL_COMPLETE_SITE_RESPONSE_MISSING",
        ),
    )
    triggered = [
        "|".join(
            a
            for a, m in (
                ("STRONG_AVOIDANCE_SIGNAL", av),
                ("ENGINEERING_MITIGATION_REQUIRED", mi),
                ("VERIFY_SITE", ve),
                ("UNRESOLVED_EVIDENCE", un),
            )
            if m
        )
        for av, mi, ve, un in zip(
            avoid, mitigate, verify_any, unres_family | (hs == "UNRESOLVED"), strict=True
        )
    ]
    out["hazard_action_set"] = triggered
    out["hazard_action_type_count"] = [len([t for t in s.split("|") if t]) for s in triggered]
    hydro_unres = hs == "UNRESOLVED"
    out["natural_hazard_integrated_state"] = np.select(
        [avoid & mitigate, avoid, mitigate, hydro_unres, verify_any],
        [
            "MULTIPLE_ACTIONS",
            "STRONG_AVOIDANCE_SIGNAL",
            "ENGINEERING_MITIGATION_REQUIRED",
            "UNRESOLVED",
            "VERIFY_SITE",
        ],
        "NO_MAJOR_ACTION_TRIGGERED",
    )
    all_codes = []
    for i in range(n):
        parts = []
        for f in FAMILIES:
            for c in str(fam[f"{f}_reason_codes"].iloc[i]).split("|"):
                if c:
                    parts.append(f"{f}:{c}")
        if mitigate[i]:
            parts.append("integration:SEISMIC_SHAKING_DOES_NOT_DEPRIORITIZE_REGION")
        parts.append("integration:GROUND_RESPONSE_NOT_ASSESSED")
        all_codes.append("|".join(parts))
    out["reason_codes"] = all_codes
    out["unresolved_reasons"] = [
        "|".join(x for x in (a, b) if x and x != "nan")
        for a, b in zip(
            hydro["unresolved_reasons"].astype(str),
            seismic["seismic_unresolved_reasons"].astype(str),
            strict=True,
        )
    ]
    out["integration_version"] = cfg.integration_version
    out["integration_status"] = cfg.status
    out["selected_for_provisional_screening"] = True
    out["production_truth"] = False
    return out


# ---------------------------------------------------------------- parcel handoff


def parcel_checklist(row: pd.Series, cfg: IntegrationConfig) -> list[str]:
    """Contract: the due-diligence items a shortlisted parcel in this cell would inherit.

    Nothing is checked here; this only names what a later parcel stage must do.
    """
    ph = cfg.parcel_handoff
    items: list[str] = []

    def add(key: str):
        for it in ph[key]:
            if it not in items:
                items.append(it)

    if row["flood_recommended_action"] in ("VERIFY_SITE", "STRONG_AVOIDANCE_SIGNAL"):
        add("flood_verify_or_strong")
    if row["landslide_recommended_action"] in ("VERIFY_SITE", "STRONG_AVOIDANCE_SIGNAL"):
        add("landslide_verify_or_strong")
    if row["terrain_recommended_action"] == "VERIFY_SITE":
        add("terrain_verify")
    if (
        row["seismic_shaking_recommended_action"] == "VERIFY_SITE"
        or row["fault_context_recommended_action"] == "VERIFY_SITE"
    ):
        add("seismic_verify_or_strong")
    if row["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED":
        add("seismic_verify_or_strong")
        add("seismic_mitigation")
    add("always")
    return items


# ---------------------------------------------------------------- future suitability contract


@dataclass(frozen=True)
class HazardDimensions:
    """Designed (NOT activated) interface for the future land-suitability model.

    The four dimensions are kept separate; there is deliberately no scalar view.
    """

    hazard_search_eligibility: str
    hazard_verification_burden: str
    hazard_engineering_burden: str
    hazard_uncertainty: str

    def __float__(self):  # pragma: no cover - guard
        raise TypeError("hazard dimensions cannot be collapsed to a number")

    __int__ = __float__


def to_suitability_dimensions(row: pd.Series, cfg: IntegrationConfig) -> HazardDimensions:
    """Map one integrated cell to the future contract. Inactive: for design/testing only."""
    if cfg.scoring_activated:  # pragma: no cover - config validator keeps this False
        raise RuntimeError("scoring activation requires an explicit future milestone")
    elig = {
        "CONTINUE_SEARCH": "SEARCHABLE",
        "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION": "SEARCHABLE_WITH_CAUTION",
        "DEPRIORITIZE_REGION": "DEPRIORITIZED",
        "UNRESOLVED": "UNRESOLVED",
    }[row["regional_search_action"]]
    k = int(row["site_verification_burden_count"])
    burden = "NONE" if k == 0 else "LOW" if k == 1 else "MODERATE" if k == 2 else "HIGH"
    eng = (
        "SEISMIC_DESIGN_REQUIRED"
        if row["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED"
        else "NONE"
    )
    return HazardDimensions(elig, burden, eng, row["data_completeness"])


def scalar_hazard_score(*_args, **_kwargs):
    """Deliberately unavailable: Natural Hazard Resilience is not a 0-100 score."""
    raise NotImplementedError(
        "no scalar hazard score exists: use the separate dimensions with their action semantics"
    )
