# ruff: noqa: E501
"""M1E: Natural Hazard integration - per-cell decision actions, combinations, province reporting.

Inputs: the selected PROVISIONAL regional defaults (hydrogeomorphic BALANCED + flood-fusion
FLOOD_ANY_SOURCE, recomputed from the M1B/M1C.2 evidence with their unchanged thresholds) and
the experimental M1D seismic evidence. No scalar hazard score, no suitability, no ranking.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, PROVINCE_NAMES, source_ref

from hearthmap.enums import Confidence
from hearthmap.hazard import (
    apply_policy,
    build_ledger,
    connected_components,
    evaluate_candidate,
    integrate,
    load_fusion_config,
    load_integration_config,
    load_policy_config,
    parcel_checklist,
    slope_stratum,
    to_policy_override,
)
from hearthmap.hazard.defaults import load_regional_defaults
from hearthmap.hazard.integration import (
    COMPLETENESS,
    FAMILIES,
    INTEGRATED_STATES,
    SEARCH_ACTIONS,
)
from hearthmap.provenance import ProvenanceRecord, current_code_version

OUT = Path("outputs/m1e")
REVIEW = Path("outputs/m1e-review")
EVIDENCE = Path("outputs/m1c1/evidence/hazard-evidence.parquet")
LEDGER_TABLE = Path("outputs/m1c2-review/common-period-cell-comparison.parquet")
SEISMIC = Path("outputs/m1d/seismic-evidence.parquet")
HYDRO_ORDER = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
SEIS_ORDER = [
    "NO_MAJOR_SEISMIC_CONCERN_DETECTED",
    "REQUIRES_SEISMIC_VERIFICATION",
    "STRONG_SEISMIC_SCREENING_CONCERN",
    "UNRESOLVED",
]
STRATA = {
    "ALL": None,
    "LOW_SLOPE_LE_5": ["LOW_SLOPE_LE_5"],
    "GENTLE_5_15": ["GENTLE_5_15"],
    "LOW_OR_GENTLE_LE_15": ["LOW_SLOPE_LE_5", "GENTLE_5_15"],
    "STEEP_GT_15": ["STEEP_GT_15"],
}


def log(m: str) -> None:
    print(m, flush=True)


def components(grid, cent, mask, area, label, n=5):
    idx = np.flatnonzero(mask)
    if not len(idx):
        return [], {"combo": label, "components": 0}
    lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
    ca = np.bincount(lab, weights=area[idx])
    sizes = np.bincount(lab)
    rows = []
    for rank, k in enumerate(np.argsort(ca)[::-1][:n], 1):
        m = idx[lab == k]
        rows.append(
            {
                "combo": label,
                "rank": rank,
                "area_km2": round(float(ca[k]), 1),
                "cells": int(sizes[k]),
                "lon": round(float(cent.x.iloc[m].mean()), 3),
                "lat": round(float(cent.y.iloc[m].mean()), 3),
                "majority_province": PROVINCE_NAMES.get(
                    grid["majority_pcode"].iloc[m].mode().iloc[0]
                ),
            }
        )
    return rows, {
        "combo": label,
        "components": len(ca),
        "isolated_single_cells": int((sizes == 1).sum()),
        "largest_component_km2": round(float(ca.max()), 1),
        "share_area_in_largest_5": round(float(np.sort(ca)[::-1][:5].sum() / ca.sum()), 3),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    icfg, pcfg, fcfg = load_integration_config(), load_policy_config(), load_fusion_config()
    defaults = load_regional_defaults()
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    ev = pd.read_parquet(EVIDENCE)
    seis = pd.read_parquet(SEISMIC)
    if (
        not (ev["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all()
        or not (seis["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all()
    ):
        raise ValueError("cell order differs between grid, evidence and seismic tables")
    n = len(grid)
    area = ev["clipped_area_km2"].to_numpy()
    pcode = grid["majority_pcode"].to_numpy()
    cent = grid.geometry.centroid.to_crs("EPSG:4326")

    # ---- selected provisional hydrogeomorphic defaults (thresholds unchanged)
    ledger = build_ledger(pd.read_parquet(LEDGER_TABLE), fcfg.presence_min_fraction)
    flood = evaluate_candidate(ledger, fcfg, defaults.flood_fusion_policy)
    hydro = apply_policy(
        ev, pcfg, defaults.hydrogeomorphic_profile, flood_override=to_policy_override(flood)
    )
    m1c3 = pd.read_parquet("outputs/m1c3/policy-results-long.parquet")
    ref = m1c3[
        (m1c3["flood_policy"] == defaults.flood_fusion_policy)
        & (m1c3["profile"] == defaults.hydrogeomorphic_profile)
    ].set_index("cell_id")
    assert (
        ref.loc[grid["cell_id"], "regional_search_status"].to_numpy()
        == hydro["regional_search_status"].to_numpy()
    ).all(), "recomputed defaults differ from the M1C.3 results"
    log("hydrogeomorphic defaults reproduced")

    res = integrate(hydro.reset_index(drop=True), seis.reset_index(drop=True), icfg)
    strat = slope_stratum(ev["slope_p90_deg"].to_numpy(), ev["terrain_support_px"].to_numpy())

    # ---- per-cell artifact
    cols_front = pd.DataFrame(
        {
            "cell_id": grid["cell_id"].to_numpy(),
            "majority_pcode": pcode,
            "clipped_area_km2": area,
            "hydro_status": hydro["regional_search_status"].to_numpy(),
            "flood_status": flood.state,
            "landslide_status": hydro["landslide_policy_level"].to_numpy(),
            "terrain_status": hydro["terrain_policy_level"].to_numpy(),
            "seismic_status": seis["seismic_screening_interpretation"].to_numpy(),
            "fault_nearest_distance_km": seis["fault_nearest_distance_km"].to_numpy(),
            "fault_nearest_zone": seis["fault_nearest_zone"].to_numpy(),
            "shaking_dominant_class": seis["shaking_dominant_class"].to_numpy(),
        }
    )
    final = pd.concat([cols_front, res], axis=1)
    keyc = [
        "flood_recommended_action",
        "landslide_recommended_action",
        "terrain_recommended_action",
        "seismic_shaking_recommended_action",
        "fault_context_recommended_action",
        "engineering_mitigation_action",
    ]
    cache: dict[tuple, str] = {}
    chk = []
    for tup, row in zip(
        final[keyc].itertuples(index=False, name=None), final[keyc].to_dict("records"), strict=True
    ):
        if tup not in cache:
            cache[tup] = "|".join(parcel_checklist(pd.Series(row), icfg))
        chk.append(cache[tup])
    final["parcel_handoff_checklist"] = chk
    final.to_parquet(OUT / "natural-hazard-actions.parquet", index=False)
    log("per-cell artifact written")

    masks = {"AOI": np.ones(n, bool)} | {p: pcode == p for p in ("TH50", "TH56", "TH57")}
    smask = {s: (np.ones(n, bool) if v is None else np.isin(strat, v)) for s, v in STRATA.items()}
    act = final

    def share(mask, m):
        return round(float(area[mask & m].sum() / area[m].sum()), 4)

    # ---- province / AOI action areas
    avoid = np.zeros(n, bool)
    for f in FAMILIES:
        avoid |= (act[f"{f}_recommended_action"] == "STRONG_AVOIDANCE_SIGNAL").to_numpy()
    state = act["natural_hazard_integrated_state"].to_numpy()
    measures = {
        "avoidance_signal": avoid,
        "regional_search_deprioritize_region (BALANCED_ACTION reference)": (
            act["regional_search_action"] == "DEPRIORITIZE_REGION"
        ).to_numpy(),
        "regional_search_continue_with_avoidance_caution": (
            act["regional_search_action"] == "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION"
        ).to_numpy(),
        "regional_search_unresolved": (act["regional_search_action"] == "UNRESOLVED").to_numpy(),
        "site_verification_required": (
            act["site_verification_action"] == "VERIFY_SITE_REQUIRED"
        ).to_numpy(),
        "engineering_mitigation_required": (
            act["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED"
        ).to_numpy(),
        "multiple_actions_state": state == "MULTIPLE_ACTIONS",
        "partial_regional_evidence": (
            act["data_completeness"] == "PARTIAL_REGIONAL_EVIDENCE"
        ).to_numpy(),
        "critical_regional_gap": (act["data_completeness"] == "CRITICAL_REGIONAL_GAP").to_numpy(),
        "no_major_action_triggered": state == "NO_MAJOR_ACTION_TRIGGERED",
    }
    rows = []
    for name, mk in measures.items():
        for scope, m in masks.items():
            rows.append(
                {
                    "measure": name,
                    "scope": scope,
                    "province": PROVINCE_NAMES.get(scope, "AOI"),
                    "cells": int((mk & m).sum()),
                    "area_km2": round(float(area[mk & m].sum()), 1),
                    "share_of_scope_area": share(mk, m),
                }
            )
    pd.DataFrame(rows).to_csv(REVIEW / "province-action-areas.csv", index=False)

    # ---- integrated state distribution (by scope and stratum)
    srows = []
    for scope, m in masks.items():
        for sname, sm in smask.items():
            if scope != "AOI" and sname != "ALL":
                continue
            for s in INTEGRATED_STATES:
                mk = state == s
                srows.append(
                    {
                        "scope": scope,
                        "stratum": sname,
                        "state": s,
                        "cells": int((mk & m & sm).sum()),
                        "area_km2": round(float(area[mk & m & sm].sum()), 1),
                        "share_of_scope_area": round(
                            float(area[mk & m & sm].sum() / area[m & sm].sum()), 4
                        ),
                    }
                )
    pd.DataFrame(srows).to_csv(REVIEW / "integrated-state-distribution.csv", index=False)

    # ---- per-axis distributions with strata (lowland reporting only)
    arows = []
    axes = {
        "regional_search_action": SEARCH_ACTIONS,
        "site_verification_action": ("NONE_TRIGGERED", "VERIFY_SITE_REQUIRED"),
        "engineering_mitigation_action": ("NONE_TRIGGERED", "SEISMIC_DESIGN_REQUIRED"),
        "data_completeness": COMPLETENESS,
    }
    for axis, vals in axes.items():
        for scope, m in masks.items():
            for sname, sm in smask.items():
                if scope != "AOI" and sname != "ALL":
                    continue
                for v in vals:
                    mk = (act[axis] == v).to_numpy()
                    arows.append(
                        {
                            "axis": axis,
                            "value": v,
                            "scope": scope,
                            "stratum": sname,
                            "cells": int((mk & m & sm).sum()),
                            "area_km2": round(float(area[mk & m & sm].sum()), 1),
                            "share_of_scope_area": round(
                                float(area[mk & m & sm].sum() / area[m & sm].sum()), 4
                            ),
                        }
                    )
    pd.DataFrame(arows).to_csv(REVIEW / "action-axis-distribution.csv", index=False)

    # ---- verification burden distribution
    brow = []
    for k in range(0, 8):
        mk = (act["site_verification_burden_count"] == k).to_numpy()
        for scope, m in masks.items():
            brow.append(
                {
                    "verification_triggers": k,
                    "scope": scope,
                    "cells": int((mk & m).sum()),
                    "area_km2": round(float(area[mk & m].sum()), 1),
                    "share_of_scope_area": share(mk, m),
                }
            )
    bdf = pd.DataFrame(brow)
    # accounting invariant (M1E.1): the distribution reconciles to the reported total
    aoi_b = bdf[bdf["scope"] == "AOI"]
    flagged_area = float(
        area[(act["site_verification_action"] == "VERIFY_SITE_REQUIRED").to_numpy()].sum()
    )
    assert abs(aoi_b["area_km2"].sum() - area.sum()) < 1.0, (
        "burden distribution does not cover the AOI"
    )
    assert abs(aoi_b[aoi_b["verification_triggers"] >= 1]["area_km2"].sum() - flagged_area) < 1.0, (
        "triggers >= 1 must equal the area flagged VERIFY_SITE_REQUIRED"
    )
    bdf.to_csv(REVIEW / "verification-burden-distribution.csv", index=False)

    # ---- per-family action distribution
    frows = []
    for f in FAMILIES:
        for a in sorted(act[f"{f}_recommended_action"].unique()):
            mk = (act[f"{f}_recommended_action"] == a).to_numpy()
            for scope, m in masks.items():
                frows.append(
                    {
                        "family": f,
                        "action": a,
                        "scope": scope,
                        "cells": int((mk & m).sum()),
                        "area_km2": round(float(area[mk & m].sum()), 1),
                        "share_of_scope_area": share(mk, m),
                    }
                )
    pd.DataFrame(frows).to_csv(REVIEW / "family-action-distribution.csv", index=False)

    # ---- integration policy sensitivity
    prow = []
    pol_cols = {
        "BALANCED_ACTION": "regional_search_action",
        "AVOIDANCE_FIRST": "regional_search_action__avoidance_first",
        "VERIFICATION_FIRST": "regional_search_action__verification_first",
    }
    for pname, col in pol_cols.items():
        for scope, m in masks.items():
            for v in SEARCH_ACTIONS:
                mk = (act[col] == v).to_numpy()
                prow.append(
                    {
                        "integration_policy": pname,
                        "scope": scope,
                        "province": PROVINCE_NAMES.get(scope, "AOI"),
                        "search_action": v,
                        "cells": int((mk & m).sum()),
                        "area_km2": round(float(area[mk & m].sum()), 1),
                        "share_of_scope_area": share(mk, m),
                    }
                )
    pd.DataFrame(prow).to_csv(REVIEW / "integration-policy-comparison.csv", index=False)
    trows = []
    names = list(pol_cols)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            ch = (act[pol_cols[a]] != act[pol_cols[b]]).to_numpy()
            trows.append(
                {
                    "policy_a": a,
                    "policy_b": b,
                    "cells_changed": int(ch.sum()),
                    "area_changed_km2": round(float(area[ch].sum()), 1),
                    "share_of_aoi": round(float(area[ch].sum() / area.sum()), 4),
                }
            )
    pd.DataFrame(trows).to_csv(REVIEW / "integration-policy-differences.csv", index=False)

    # ---- cross-family combinations
    hy = act["hydro_status"].to_numpy()
    se = act["seismic_status"].to_numpy()
    combos = {
        "hydro favourable + seismic strong": (hy == "NO_MAJOR_CONCERN_DETECTED")
        & (se == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro requires verification + seismic strong": (hy == "REQUIRES_VERIFICATION")
        & (se == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro strong concern + seismic strong": (hy == "STRONG_REGIONAL_CONCERN")
        & (se == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro deprioritize + seismic strong": (hy == "REGIONAL_DEPRIORITIZE")
        & (se == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro unresolved + seismic strong": (hy == "UNRESOLVED")
        & (se == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro favourable + seismic verification": (hy == "NO_MAJOR_CONCERN_DETECTED")
        & (se == "REQUIRES_SEISMIC_VERIFICATION"),
        "hydro favourable + seismic none detected": (hy == "NO_MAJOR_CONCERN_DETECTED")
        & (se == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"),
        "hydro deprioritize + seismic none detected": (hy == "REGIONAL_DEPRIORITIZE")
        & (se == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"),
    }
    crow, comp_rows, comp_sum = [], [], []
    for label, mk in combos.items():
        row = {
            "combo": label,
            "cells": int(mk.sum()),
            "area_km2": round(float(area[mk].sum()), 1),
            "share_of_aoi": share(mk, masks["AOI"]),
        }
        for scope in ("TH50", "TH56", "TH57"):
            row[f"{PROVINCE_NAMES[scope]}_km2"] = round(float(area[mk & masks[scope]].sum()), 1)
        for sname in ("LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15"):
            row[f"{sname}_km2"] = round(float(area[mk & smask[sname]].sum()), 1)
        crow.append(row)
        r, s = components(grid, cent, mk, area, label)
        comp_rows += r
        comp_sum.append(s)
    pd.DataFrame(crow).to_csv(REVIEW / "cross-family-combinations.csv", index=False)
    pd.DataFrame(comp_rows).to_csv(REVIEW / "cross-family-largest-regions.csv", index=False)
    pd.DataFrame(comp_sum).to_csv(REVIEW / "cross-family-component-summary.csv", index=False)

    # ---- characterise hydro favourable + seismic strong
    fs = combos["hydro favourable + seismic strong"]
    codes = seis["seismic_reason_codes"].astype(str)
    char = {
        "area_km2": round(float(area[fs].sum()), 1),
        "cells": int(fs.sum()),
        "provinces_km2": {
            PROVINCE_NAMES[p]: round(float(area[fs & masks[p]].sum()), 1)
            for p in ("TH50", "TH56", "TH57")
        },
        "province_share_of_province_area": {
            PROVINCE_NAMES[p]: share(fs, masks[p]) for p in ("TH50", "TH56", "TH57")
        },
        "strata_km2": {s: round(float(area[fs & m].sum()), 1) for s, m in smask.items()},
        "share_modelled_dominant_class": round(
            float(codes[fs].str.contains("MODELLED_HAZARD_TOP_CLASS_DOMINANT").mean()), 3
        ),
        "share_escalated_borderline": round(
            float(codes[fs].str.contains("BORDERLINE_ESCALATED").mean()), 3
        ),
        "share_fault_within_5km": round(
            float((seis["fault_nearest_distance_km"].to_numpy()[fs] <= 5).mean()), 3
        ),
        "share_historical_event_corroborating": round(
            float(codes[fs].str.contains("HISTORICAL_EVENT_CORROBORATES").mean()), 3
        ),
        "median_dsm_elevation_m": round(float(np.median(ev["elev_median_m"].to_numpy()[fs])), 1),
        "nearest_fault_zone_share": pd.Series(seis["fault_nearest_zone"].to_numpy()[fs])
        .value_counts(normalize=True)
        .head(6)
        .round(3)
        .to_dict(),
        "flood_ladder_states": pd.Series(flood.state[fs]).value_counts().to_dict(),
        "landslide_assessed_share": round(
            float((ev["landslide_assessed_fraction"].to_numpy()[fs] >= 0.5).mean()), 3
        ),
        "site_verification_required_share": round(
            float(
                (act["site_verification_action"].to_numpy()[fs] == "VERIFY_SITE_REQUIRED").mean()
            ),
            3,
        ),
        "note": "descriptive only; not called unsuitable: seismic mitigation is a design/site-response matter, not removal from the search",
    }

    # ---- parcel handoff templates (distinct action profiles)
    prof = (
        act.groupby("parcel_handoff_checklist")
        .agg(cells=("cell_id", "size"), area_km2=("clipped_area_km2", "sum"))
        .round(1)
        .reset_index()
    )
    prof["checklist_items"] = prof["parcel_handoff_checklist"].str.split("|").str.len()
    prof.sort_values("area_km2", ascending=False).to_csv(
        REVIEW / "parcel-handoff-profiles.csv", index=False
    )

    # ---- unresolved evidence
    urows = []
    for name, mk in {
        "landslide not assessed (DMR coverage)": (
            act["landslide_recommended_action"] == "UNRESOLVED"
        ).to_numpy(),
        "terrain support insufficient": (
            act["terrain_recommended_action"] == "UNRESOLVED"
        ).to_numpy(),
        "seismic zones not assessed": (
            act["seismic_shaking_recommended_action"] == "UNRESOLVED"
        ).to_numpy(),
        "regional search action unresolved": (
            act["regional_search_action"] == "UNRESOLVED"
        ).to_numpy(),
        "ground response not assessed (all cells)": np.ones(n, bool),
    }.items():
        for scope, m in masks.items():
            urows.append(
                {
                    "unresolved": name,
                    "scope": scope,
                    "cells": int((mk & m).sum()),
                    "area_km2": round(float(area[mk & m].sum()), 1),
                    "share_of_scope_area": share(mk, m),
                }
            )
    pd.DataFrame(urows).to_csv(REVIEW / "unresolved-evidence.csv", index=False)

    # ---- examples
    ex = ["# Example integrated cells (decision axes preserved)", ""]
    for label, mk in (
        ("hydro favourable + seismic strong", combos["hydro favourable + seismic strong"]),
        ("multiple actions", state == "MULTIPLE_ACTIONS"),
        (
            "hydro deprioritize + seismic none detected",
            combos["hydro deprioritize + seismic none detected"],
        ),
        ("hydro unresolved", hy == "UNRESOLVED"),
    ):
        idx = np.flatnonzero(mk)
        if len(idx):
            r = act.iloc[idx[len(idx) // 2]]
            ex += (
                [f"## {label}", "", "```text"]
                + [
                    f"{c}: {r[c]}"
                    for c in (
                        "cell_id",
                        "hydro_status",
                        "flood_status",
                        "landslide_status",
                        "terrain_status",
                        "seismic_status",
                        "regional_search_action",
                        "site_verification_action",
                        "engineering_mitigation_action",
                        "data_completeness",
                        "ground_response_status",
                        "natural_hazard_integrated_state",
                        "hazard_action_set",
                        "reason_codes",
                        "parcel_handoff_checklist",
                    )
                ]
                + ["```", ""]
            )
    (REVIEW / "example-cells.md").write_text("\n".join(ex), "utf-8")

    stats = {
        "integration_version": icfg.integration_version,
        "status": icfg.status,
        "selected_provisional_defaults": {
            "hydrogeomorphic_profile": defaults.hydrogeomorphic_profile,
            "flood_fusion_policy": defaults.flood_fusion_policy,
            "selected_for_provisional_screening": True,
            "production_truth": False,
        },
        "integrated_state_area_km2": {
            s: round(float(area[state == s].sum()), 1) for s in INTEGRATED_STATES
        },
        "hydro_favourable_seismic_strong": char,
        "component_summaries": comp_sum,
    }
    (REVIEW / "integration-statistics.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", "utf-8"
    )
    pq = OUT / "natural-hazard-actions.parquet"
    rec = ProvenanceRecord(
        artifact_id="m1e-natural-hazard-actions",
        artifact_path=pq.as_posix(),
        code_version=current_code_version(),
        sources=[
            source_ref("flood-gistda-history", original_crs="EPSG:4326"),
            source_ref("flood-gistda-repeated-2005-2016", original_crs="EPSG:3857"),
            source_ref("landslide-susceptibility-dmr", original_crs="EPSG:32647"),
            source_ref("landslide-inventory-dmr", original_crs="EPSG:32647"),
            source_ref("dem-copernicus-glo30", original_crs="EPSG:4326+EPSG:3855"),
            source_ref("seismic-active-faults-dmr", original_crs="EPSG:32647"),
            source_ref("seismic-intensity-zones-dmr", original_crs="EPSG:32647"),
            source_ref("geohazard-events-dmr", original_crs="EPSG:32647"),
            source_ref("seismic-felt-events-tmd", original_crs="EPSG:4326"),
            source_ref("seismicity-usgs-comcat", original_crs="EPSG:4326"),
        ],
        normalized_crs=CANONICAL,
        method=f"config/hazard-integration.yaml {icfg.integration_version} ({icfg.status}): per-family "
        "severity/confidence/action/reason codes from the selected provisional hydrogeomorphic defaults "
        "(BALANCED + FLOOD_ANY_SOURCE) and experimental seismic evidence; separate decision axes, no averaging.",
        spatial_resolution="500 m cells",
        confidence=Confidence.LOW,
        limitations=[
            "Provisional regional screening; production_truth false; not a parcel/site hazard assessment.",
            "No scalar hazard score; actions are not comparable as 'better/worse'.",
            "Ground response (site amplification, liquefaction, geotechnics) is not assessed anywhere.",
            "M1C-M1E visual QA gates are PENDING.",
        ],
    )
    rec.write_sidecar(pq)
    log(
        json.dumps(
            {
                "state_area": stats["integrated_state_area_km2"],
                "hydro_fav_seismic_strong": {
                    k: char[k] for k in ("area_km2", "provinces_km2", "strata_km2")
                },
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
