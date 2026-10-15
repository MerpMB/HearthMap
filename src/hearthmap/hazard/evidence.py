"""Per-cell hazard evidence schema, provisional interpretation and experimental rules.

Evidence levels (docs/product/hazard-evidence-model.md):

    RAW_EVIDENCE                       source features / pixels as acquired
    DERIVED_INDICATOR                  per-cell measurements (fractions, distances, quantiles)
    PROVISIONAL_HAZARD_INTERPRETATION  rule-labelled states per hazard (this module)
    DECISION_RULE                      NOT implemented in M1B (gate pending)

Interpretation reads ONLY hazard indicator columns. Context columns (boundary
uncertainty, legal screening) are carried alongside but can never change a
hazard state - this is enforced by column selection and tested.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from enum import StrEnum

import numpy as np
import pandas as pd

from hearthmap.enums import EXPERIMENTAL_SOURCE_PREFIX, Confidence  # noqa: F401 (re-export)
from hearthmap.hazard.config import HazardConfig


class EvidenceLevel(StrEnum):
    RAW_EVIDENCE = "RAW_EVIDENCE"
    DERIVED_INDICATOR = "DERIVED_INDICATOR"
    PROVISIONAL_HAZARD_INTERPRETATION = "PROVISIONAL_HAZARD_INTERPRETATION"
    DECISION_RULE = "DECISION_RULE"


class HazardState(StrEnum):
    HIGH_HAZARD_EVIDENCE = "HIGH_HAZARD_EVIDENCE"
    CAUTION = "CAUTION"
    # Deliberately not "LOW" or "SAFE": absence of detected evidence only.
    NO_HIGH_HAZARD_EVIDENCE_DETECTED = "NO_HIGH_HAZARD_EVIDENCE_DETECTED"
    UNRESOLVED = "UNRESOLVED"


HAZARDS = ("flood", "landslide", "terrain")

# Indicator columns each hazard interpretation may read. Nothing else.
FLOOD_COLUMNS = (
    "flood_area_fraction",
    "flood_freq_ge3_area_fraction",
    "flood_distance_m",
    "flood_assessed",
)
LANDSLIDE_COLUMNS = (
    "landslide_assessed_fraction",
    "landslide_class3_fraction",
    "landslide_class4_fraction",
    "landslide_class5_fraction",
    "landslide_inventory_points",
)
TERRAIN_COLUMNS = ("terrain_support_px", "slope_p90_deg")
INTERPRETATION_INPUTS = FLOOD_COLUMNS + LANDSLIDE_COLUMNS + TERRAIN_COLUMNS
CONTEXT_COLUMNS = (
    "boundary_attribution_uncertain",
    "boundary_zone_ids",
    "reserve_area_fraction",
    "park_area_fraction",
    "sanctuary_area_fraction",
    "requires_legal_verification",
)

_SEVERITY = {
    HazardState.HIGH_HAZARD_EVIDENCE: 3,
    HazardState.UNRESOLVED: 2,
    HazardState.CAUTION: 1,
    HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED: 0,
}


def _states(conds: list[tuple[np.ndarray, HazardState, str]], n: int):
    state = np.full(n, HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED.value, dtype=object)
    reason = np.full(n, "", dtype=object)
    done = np.zeros(n, bool)
    for cond, st, why in conds:
        m = np.asarray(cond, bool) & ~done
        state[m] = st.value
        reason[m] = why
        done |= m
    return state, reason


def interpret(indicators: pd.DataFrame, cfg: HazardConfig) -> pd.DataFrame:
    """Per-hazard provisional states with reasons and confidence, plus a categorical
    multi-hazard view in which severe evidence always stays visible (no averaging)."""
    missing = [c for c in INTERPRETATION_INPUTS if c not in indicators.columns]
    if missing:
        raise KeyError(f"missing indicator columns: {missing}")
    d = indicators.loc[:, list(INTERPRETATION_INPUTS)]  # context columns are never read
    n = len(d)
    out = pd.DataFrame(index=indicators.index)

    # ---------------- flood (historical observed, temporary evidence)
    f = cfg.flood.interpretation
    st, why = _states(
        [
            (
                ~d["flood_assessed"].astype(bool),
                HazardState.UNRESOLVED,
                "outside flood source extent",
            ),
            (
                d["flood_freq_ge3_area_fraction"] >= f.high_min_area_fraction,
                HazardState.HIGH_HAZARD_EVIDENCE,
                f">= {f.high_min_area_fraction:.0%} of cell observed flooded in >= "
                f"{f.high_recurrence_years} of 12 years (2005-2016)",
            ),
            (
                d["flood_area_fraction"] >= f.caution_min_area_fraction,
                HazardState.CAUTION,
                f">= {f.caution_min_area_fraction:.0%} of cell observed flooded at least once",
            ),
            (
                d["flood_distance_m"] <= f.caution_distance_m,
                HazardState.CAUTION,
                f"observed flooding within {f.caution_distance_m:g} m",
            ),
        ],
        n,
    )
    why = np.where(
        st == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED.value,
        "no observed flooding 2005-2016 in or near cell (NOT evidence of no "
        "flood risk: flash floods and cloud-covered events are missed)",
        why,
    )
    out["flood_state"], out["flood_reason"] = st, why
    out["flood_confidence"] = np.select(
        [
            st == HazardState.UNRESOLVED.value,
            st == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED.value,
        ],
        [Confidence.UNKNOWN.value, Confidence.LOW.value],
        Confidence.MEDIUM.value,
    )

    # ---------------- landslide (DMR susceptibility + inventory)
    ls = cfg.landslide
    li = ls.interpretation
    assessed = d["landslide_assessed_fraction"].fillna(0)
    hi = d["landslide_class4_fraction"].fillna(0) + d["landslide_class5_fraction"].fillna(0)
    med = hi + d["landslide_class3_fraction"].fillna(0)
    inv = d["landslide_inventory_points"].fillna(0)
    st, why = _states(
        [
            (
                d["landslide_class5_fraction"].fillna(0) >= li.high_very_high_min_fraction,
                HazardState.HIGH_HAZARD_EVIDENCE,
                f">= {li.high_very_high_min_fraction:.0%} of cell in DMR 'Very High' "
                "susceptibility",
            ),
            (
                hi >= li.high_high_or_above_min_fraction,
                HazardState.HIGH_HAZARD_EVIDENCE,
                f">= {li.high_high_or_above_min_fraction:.0%} of cell in DMR 'High' or 'Very High'",
            ),
            (
                assessed < ls.min_assessed_fraction,
                HazardState.UNRESOLVED,
                f"DMR susceptibility covers < {ls.min_assessed_fraction:.0%} of cell "
                "(not assessed)",
            ),
            (
                hi >= li.caution_high_or_above_min_fraction,
                HazardState.CAUTION,
                "part of cell in DMR 'High'/'Very High' susceptibility",
            ),
            (
                med >= li.caution_medium_or_above_min_fraction,
                HazardState.CAUTION,
                f">= {li.caution_medium_or_above_min_fraction:.0%} of cell 'Medium' or above",
            ),
            (
                inv >= li.caution_inventory_points,
                HazardState.CAUTION,
                "mapped historical landslide scar(s) in cell",
            ),
        ],
        n,
    )
    why = np.where(
        st == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED.value,
        "assessed by DMR as mostly 'Very Low'/'Low' and no mapped scars "
        "(susceptibility, not a guarantee)",
        why,
    )
    out["landslide_state"], out["landslide_reason"] = st, why
    out["landslide_confidence"] = np.select(
        [st == HazardState.UNRESOLVED.value, assessed >= 0.9],
        [Confidence.UNKNOWN.value, Confidence.MEDIUM.value],
        Confidence.LOW.value,
    )

    # ---------------- terrain (DSM slope)
    t = cfg.terrain
    ti = t.interpretation
    sup = d["terrain_support_px"].fillna(0)
    p90 = d["slope_p90_deg"]
    st, why = _states(
        [
            (
                sup < t.min_support_px,
                HazardState.UNRESOLVED,
                f"terrain support < {t.min_support_px:g} pixel (ADR-0009)",
            ),
            (
                p90 >= ti.high_slope_p90_deg,
                HazardState.HIGH_HAZARD_EVIDENCE,
                f"DSM slope p90 >= {ti.high_slope_p90_deg:g} deg",
            ),
            (
                p90 >= ti.caution_slope_p90_deg,
                HazardState.CAUTION,
                f"DSM slope p90 >= {ti.caution_slope_p90_deg:g} deg",
            ),
        ],
        n,
    )
    why = np.where(
        st == HazardState.NO_HIGH_HAZARD_EVIDENCE_DETECTED.value,
        f"DSM slope p90 < {ti.caution_slope_p90_deg:g} deg",
        why,
    )
    why = np.where(
        st != HazardState.UNRESOLVED.value,
        why + " [DSM: canopy/buildings bias slope; not ground slope]",
        why,
    )
    out["terrain_state"], out["terrain_reason"] = st, why
    out["terrain_confidence"] = np.where(
        st == HazardState.UNRESOLVED.value, Confidence.UNKNOWN.value, Confidence.LOW.value
    )
    out["terrain_low_support"] = (sup >= t.min_support_px) & (sup < t.low_support_px)

    # ---------------- categorical multi-hazard view (no averaging)
    sev = np.column_stack(
        [out[f"{h}_state"].map(lambda s: _SEVERITY[HazardState(s)]).to_numpy() for h in HAZARDS]
    )
    worst = sev.max(axis=1)
    inv_sev = {v: k for k, v in _SEVERITY.items()}
    out["overall_state"] = [inv_sev[int(v)].value for v in worst]
    out["high_hazards"] = [
        "|".join(h for h, s in zip(HAZARDS, row, strict=True) if s == 3) for row in sev
    ]
    out["caution_hazards"] = [
        "|".join(h for h, s in zip(HAZARDS, row, strict=True) if s == 1) for row in sev
    ]
    out["unresolved_hazards"] = [
        "|".join(h for h, s in zip(HAZARDS, row, strict=True) if s == 2) for row in sev
    ]
    out["evidence_completeness"] = (sev != 2).sum(axis=1) / len(HAZARDS)
    confs = np.column_stack([out[f"{h}_confidence"].to_numpy() for h in HAZARDS])
    out["interpretation_confidence"] = [
        Confidence.weakest(Confidence(c) for c in row).value for row in confs
    ]
    out["interpretation_level"] = EvidenceLevel.PROVISIONAL_HAZARD_INTERPRETATION.value
    out["interpretation_note"] = (
        "Provisional evidence interpretation. NO_HIGH_HAZARD_EVIDENCE_DETECTED is not 'safe'. "
        "Not a decision rule; M1A.1 human visual sign-off "
        f"{cfg.gates.m1a1_human_visual_signoff}."
    )
    return out


def experimental_candidates(indicators: pd.DataFrame, cfg: HazardConfig) -> pd.DataFrame:
    """Boolean flag per (reason tag, threshold). EXPERIMENTAL: never affects eligibility."""
    out = pd.DataFrame(index=indicators.index)
    for tag, rule in cfg.experimental_exclusion_candidates.items():
        v = indicators[rule.field]
        for thr in rule.thresholds or []:
            out[f"{tag}@{thr:g}"] = (v >= thr).fillna(False).to_numpy()
        for thr in rule.thresholds_below or []:
            out[f"{tag}@<{thr:g}"] = (v < thr).fillna(True).to_numpy()
    out["experimental"] = True
    out["affects_eligibility"] = False
    out["feeds_scoring"] = False
    return out


def threshold_sensitivity(
    values: pd.Series,
    thresholds: Iterable[float],
    *,
    area_km2: pd.Series,
    groups: Mapping[str, pd.Series],
    below: bool = False,
    unknown_counts_as: bool | None = None,
) -> pd.DataFrame:
    """Cells and area affected per threshold, by group (e.g. province) and AOI.

    NaN values are reported separately (``unknown_cells``) and are not counted as
    affected unless ``unknown_counts_as`` is True.
    """
    rows = []
    scopes = {"AOI": pd.Series(True, index=values.index)} | {k: v for k, v in groups.items()}
    for thr in thresholds:
        hit = values < thr if below else values >= thr
        if unknown_counts_as is not None:
            hit = hit | (values.isna() & unknown_counts_as)
        for scope, mask in scopes.items():
            m = mask.astype(bool)
            sel = m & hit.fillna(False)
            rows.append(
                {
                    "threshold": f"{'<' if below else '>='} {thr:g}",
                    "scope": scope,
                    "cells": int(sel.sum()),
                    "share_of_cells": float(sel.sum() / m.sum()) if m.sum() else 0.0,
                    "area_km2": float(area_km2[sel].sum()),
                    "share_of_area": float(area_km2[sel].sum() / area_km2[m].sum())
                    if area_km2[m].sum()
                    else 0.0,
                    "unknown_cells": int((m & values.isna()).sum()),
                }
            )
    return pd.DataFrame(rows)
