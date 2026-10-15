"""Per-cell seismic evidence (M1D): context metrics and a conservative screening interpretation.

Four concepts stay separate: FAULT_CONTEXT, EARTHQUAKE_HAZARD (the DMR model intensity
zones), HISTORICAL_SEISMICITY and GROUND_RESPONSE (not assessable here). Rules:

* distance to a fault trace is context; it can at most raise REQUIRES_SEISMIC_VERIFICATION
  and never creates strong concern alone; there is no fault distance score;
* strong concern needs >= ``strong_requires_families`` families at their strong tier;
* absence (no nearby fault, no nearby event, low zone) never lowers concern and never
  means safe; missing ground-response evidence stays an explicit limitation;
* slope/lowland strata and hydrogeomorphic results are never inputs (columns are selected
  by name, everything else is ignored) and inputs are never mutated.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from hearthmap.seismic.config import INTERPRETATION_STATES, SeismicConfig
from hearthmap.spatial.overlay import categorical_cell_fractions

TIER_NAMES = {0: "NONE", 1: "NOTABLE", 2: "STRONG_TIER"}


# ---------------------------------------------------------------- fault context


def fault_context(cells: np.ndarray, faults: gpd.GeoDataFrame, cfg: SeismicConfig) -> pd.DataFrame:
    """Distance/count context to mapped active-fault traces (descriptive only)."""
    n = len(cells)
    geoms = faults.geometry.values
    tree = shapely.STRtree(geoms)
    pairs, dist = tree.query_nearest(cells, return_distance=True, all_matches=False)
    nearest = np.full(n, -1, dtype=int)
    nearest[pairs[0]] = pairs[1]
    d = np.full(n, np.nan)
    d[pairs[0]] = dist
    out = pd.DataFrame(index=range(n))
    out["fault_nearest_distance_km"] = np.round(d / 1000.0, 3)
    ok = nearest >= 0

    def pick(col: str):
        vals = np.full(n, None, dtype=object)
        vals[ok] = faults[col].to_numpy()[nearest[ok]]
        return vals

    out["fault_nearest_zone"] = pick("F_ZONE_E")
    out["fault_nearest_name"] = pick("F_NAME_E")
    out["fault_nearest_type_source_native"] = pick("TYPE")
    mce = np.full(n, np.nan)
    mce[ok] = pd.to_numeric(faults["MCE"], errors="coerce").to_numpy()[nearest[ok]]
    out["fault_nearest_mce_source_native"] = mce  # publisher field; scale/units undocumented
    for r in cfg.reporting_radii_km:
        ci, _fi = tree.query(cells, predicate="dwithin", distance=r * 1000.0)
        out[f"fault_traces_within_{r:g}km"] = np.bincount(ci, minlength=n)
    ci, fi = tree.query(cells, predicate="dwithin", distance=20_000.0)
    zones = faults["F_ZONE_E"].to_numpy()
    lists = [set() for _ in range(n)]
    for c, f in zip(ci, fi, strict=True):
        lists[c].add(zones[f])
    out["fault_zones_within_20km"] = ["|".join(sorted(s)) for s in lists]
    out["fault_source"] = cfg.sources["faults"]["source_id"]
    out["fault_context_role"] = "FAULT_CONTEXT"
    return out


# ---------------------------------------------------------------- shaking context


def shaking_context(
    grid: gpd.GeoDataFrame,
    zones: gpd.GeoDataFrame,
    cfg: SeismicConfig,
    *,
    within: shapely.Geometry,
    coverage: np.ndarray,
) -> pd.DataFrame:
    """Area share of each DMR model intensity (MMI) zone per cell; publisher codes kept."""
    src = cfg.sources["intensity_zones"]
    out = categorical_cell_fractions(
        grid,
        zones,
        class_field=src["class_field"],
        classes=src["classes"],
        prefix="shaking",
        within=within,
        coverage=coverage,
    )
    out["shaking_source"] = src["source_id"]
    out["shaking_role"] = "EARTHQUAKE_HAZARD"
    return out


# ---------------------------------------------------------------- historical seismicity


def historical_context(
    cells: np.ndarray, catalogs: dict[str, gpd.GeoDataFrame], cfg: SeismicConfig
) -> pd.DataFrame:
    """Per-source event counts / maxima within radii and nearest-event distances.

    ``catalogs`` maps a short source name to point events (metric CRS) with ``magnitude``.
    Sources are never merged or deduplicated; counts are per source. Only
    ``hist_nearest_ge{M}_km`` (existence of an event) combines sources.
    """
    n = len(cells)
    out = pd.DataFrame(index=range(n))
    all_pts, all_mag = [], []
    for name, ev in catalogs.items():
        ev = ev[ev["magnitude"].notna()]
        geoms, mag = ev.geometry.values, ev["magnitude"].to_numpy(float)
        all_pts.append(geoms)
        all_mag.append(mag)
        tree = shapely.STRtree(geoms)
        for r in cfg.reporting_radii_km:
            ci, fi = tree.query(cells, predicate="dwithin", distance=r * 1000.0)
            out[f"hist_{name}_n_within_{r:g}km"] = np.bincount(ci, minlength=n)
            mx = np.full(n, np.nan)
            np.fmax.at(mx, ci, mag[fi])
            out[f"hist_{name}_max_mag_within_{r:g}km"] = mx
    pts = np.concatenate(all_pts) if all_pts else np.array([], dtype=object)
    mags = np.concatenate(all_mag) if all_mag else np.array([])
    for m in cfg.history_magnitude_thresholds:
        sel = mags >= m
        col = f"hist_nearest_ge{m:g}_km"
        if not sel.any():
            out[col] = np.nan
            continue
        tree = shapely.STRtree(pts[sel])
        pairs, dist = tree.query_nearest(cells, return_distance=True, all_matches=False)
        d = np.full(n, np.nan)
        d[pairs[0]] = dist / 1000.0
        out[col] = np.round(d, 3)
    out["hist_sources"] = "|".join(catalogs)
    return out


# ---------------------------------------------------------------- ground response


def ground_response_columns(n: int, cfg: SeismicConfig) -> pd.DataFrame:
    """Ground response is not assessable with the available data: explicit, never inferred."""
    g = cfg.ground_response
    return pd.DataFrame(
        {
            "ground_response_status": [g.status] * n,
            "ground_response_available_evidence": ["|".join(g.available_evidence)] * n,
            "ground_response_missing_evidence": ["|".join(g.missing_evidence)] * n,
        }
    )


# ---------------------------------------------------------------- interpretation


def seismic_input_columns(cfg: SeismicConfig) -> tuple[str, ...]:
    classes = cfg.sources["intensity_zones"]["classes"]
    return (
        "fault_nearest_distance_km",
        "shaking_assessed_fraction",
        *(f"shaking_class{c}_fraction" for c in classes),
        f"hist_nearest_ge{cfg.interpretation.history.magnitude:g}_km",
    )


def interpret_seismic(evidence: pd.DataFrame, cfg: SeismicConfig) -> pd.DataFrame:
    """Conservative, config-driven regional screening state with structured reasons.

    * Modelled hazard (DMR EQ_ZONE) can reach STRONG on its own when the top MMI class
      dominates the cell; a borderline share escalates only with positive corroboration.
    * Fault proximity and historical events are corroborating context: each alone is capped
      at REQUIRES_SEISMIC_VERIFICATION; their absence never lowers any state.
    * The families are not treated as statistically independent observations.

    Reads only :func:`seismic_input_columns`; the input frame is not modified.
    """
    cols = seismic_input_columns(cfg)
    missing = [c for c in cols if c not in evidence.columns]
    if missing:
        raise KeyError(f"missing seismic input columns: {missing}")
    d = evidence.loc[:, list(cols)].astype(float)
    n = len(d)
    it = cfg.interpretation
    classes = cfg.sources["intensity_zones"]["classes"]

    fd = d["fault_nearest_distance_km"].to_numpy()
    with np.errstate(invalid="ignore"):
        fault_t = np.where(
            fd <= it.fault.very_near_within_km, 2, np.where(fd <= it.fault.verify_within_km, 1, 0)
        )

    assessed = (
        d["shaking_assessed_fraction"].fillna(0).to_numpy() >= it.shaking.min_assessed_fraction
    )
    rank = classes.index(it.shaking.class_name)
    top = sum(d[f"shaking_class{c}_fraction"].fillna(0).to_numpy() for c in classes[rank:])
    model_t = np.where(
        assessed & (top >= it.shaking.strong_min_fraction),
        2,
        np.where(assessed & (top >= it.shaking.verify_min_fraction), 1, 0),
    )

    hd = d[f"hist_nearest_ge{it.history.magnitude:g}_km"].to_numpy()
    with np.errstate(invalid="ignore"):  # NaN (no event) compares False: never a signal
        hist_t = np.where(
            hd <= it.history.corroborate_within_km,
            2,
            np.where(hd <= it.history.verify_within_km, 1, 0),
        )

    corroborating = (fault_t == 2).astype(int) + (hist_t == 2).astype(int)
    need = it.shaking.escalate_borderline_with_corroborating_signals
    escalated = (model_t == 1) & (corroborating >= need) if need > 0 else np.zeros(n, dtype=bool)
    level = np.where(
        (model_t == 2) | escalated,
        2,
        np.where((fault_t >= 1) | (model_t >= 1) | (hist_t >= 1), 1, 0),
    )
    unresolved = ~assessed & (level == 0)
    state = np.where(
        unresolved,
        INTERPRETATION_STATES[3],
        np.where(
            level == 2,
            INTERPRETATION_STATES[2],
            np.where(level == 1, INTERPRETATION_STATES[1], INTERPRETATION_STATES[0]),
        ),
    ).astype(object)

    reasons: list[list[str]] = [[] for _ in range(n)]
    info: list[list[str]] = [[] for _ in range(n)]
    unres: list[list[str]] = [[] for _ in range(n)]

    def add(target, mask, code):
        for i in np.flatnonzero(mask):
            target[i].append(code)

    add(reasons, model_t == 2, "MODELLED_HAZARD_TOP_CLASS_DOMINANT")
    add(reasons, model_t == 1, "MODELLED_HAZARD_TOP_CLASS_PRESENT")
    add(reasons, escalated, "BORDERLINE_ESCALATED_BY_CORROBORATING_SIGNALS")
    add(reasons, fault_t >= 1, "FAULT_TRACE_WITHIN_VERIFY_DISTANCE")
    add(reasons, fault_t == 2, "FAULT_TRACE_VERY_NEAR")
    add(reasons, hist_t >= 1, "HISTORICAL_EVENT_NEAR")
    add(reasons, hist_t == 2, "HISTORICAL_EVENT_CORROBORATES")
    add(unres, ~assessed, "SHAKING_ZONE_NOT_ASSESSED")
    add(info, np.ones(n, bool), "GROUND_RESPONSE_NOT_ASSESSED")
    add(info, hist_t == 0, "NO_NEARBY_HISTORICAL_EVENT_RECORDED")
    add(info, assessed & (model_t == 0), "MODELLED_HAZARD_BELOW_TIER")

    out = pd.DataFrame(index=evidence.index)
    out["seismic_screening_interpretation"] = state
    out["fault_tier"] = [TIER_NAMES[int(v)] for v in fault_t]
    out["modelled_hazard_tier"] = [TIER_NAMES[int(v)] for v in model_t]
    out["history_tier"] = [TIER_NAMES[int(v)] for v in hist_t]
    out["corroborating_signals"] = corroborating
    out["seismic_reason_codes"] = ["|".join(c) for c in reasons]
    out["seismic_informational_codes"] = ["|".join(c) for c in info]
    out["seismic_unresolved_reasons"] = ["|".join(c) for c in unres]
    # regional completeness: fault + zones (if assessed) + catalogues; never site response
    out["seismic_evidence_completeness"] = (1 + assessed.astype(int) + 1 + 0) / 4.0
    out["seismic_decision_confidence"] = cfg.decision_confidence
    out["seismic_scope"] = "REGIONAL_SCREENING_NOT_SITE_ASSESSMENT"
    out["seismic_policy_version"] = cfg.seismic_version
    out["seismic_policy_status"] = cfg.status
    return out


# ---------------------------------------------------------------- explanation


def explain_seismic(
    cell_id: str, evidence: pd.Series, result: pd.Series, cfg: SeismicConfig
) -> str:
    """Deterministic explanation built only from structured reason codes and cell values."""
    it = cfg.interpretation
    values = {
        "fault_verify_km": it.fault.verify_within_km,
        "fault_strong_km": it.fault.very_near_within_km,
        "top_class": it.shaking.class_name,
        "model_verify_fraction": it.shaking.verify_min_fraction,
        "model_strong_fraction": it.shaking.strong_min_fraction,
        "history_magnitude": it.history.magnitude,
        "history_tier1_km": it.history.verify_within_km,
        "history_tier2_km": it.history.corroborate_within_km,
        "escalation_signals": it.shaking.escalate_borderline_with_corroborating_signals,
    }

    def render(field: str) -> list[str]:
        codes = [c for c in str(result[field]).split("|") if c]
        return [f"- {cfg.reason_codes[c].format(**values)}  [{c}]" for c in codes]

    fd = evidence.get("fault_nearest_distance_km", np.nan)
    parts = [
        f"CELL: {cell_id}",
        f"SEISMIC EVIDENCE v{cfg.seismic_version} ({cfg.status}, experimental, regional screening)",
        "",
        result["seismic_screening_interpretation"],
        f"evidence completeness: {result['seismic_evidence_completeness']:.2f} of 4 families "
        "(ground response is never assessed)",
        "",
        "WHY",
        *(
            render("seismic_reason_codes")
            or ["- no qualifying seismic signal in the implemented evidence families"]
        ),
        "",
        "CONTEXT (descriptive, not risk scores)",
        f"- nearest mapped active-fault trace: {fd:.1f} km ({evidence.get('fault_nearest_zone')})"
        if pd.notna(fd)
        else "- nearest mapped active-fault trace: unavailable",
        "",
        "DATA TO VERIFY",
        *render("seismic_unresolved_reasons"),
        *render("seismic_informational_codes"),
        "",
        "THIS DOES NOT MEAN",
        "- the cell is earthquake-safe or has no seismic risk",
        "- distance to a fault, or the absence of recorded events, indicates low hazard",
        "- site conditions (ground material, sediment, amplification, liquefaction) were assessed",
        "- a parcel/site seismic assessment has been done, or construction is approved",
    ]
    return "\n".join(parts)
