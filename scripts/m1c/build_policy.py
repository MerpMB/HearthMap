"""M1C: evaluate the provisional hydrogeomorphic screening policy profiles.

Outputs (outputs/m1c/):
  policy-results.parquet            long table: cell x profile, evidence summary + policy
  hazard-screening-policy.gpkg      geometry + per-profile status/reasons (review)
  policy-statistics.json            status counts/area by profile x province/AOI
  profile-transitions.csv           how cells move between profiles
  candidate-threshold-sensitivity.csv
  reason-code-distribution.csv
  fragmentation-summary.csv, largest-components.csv
  example-explanations.md           deterministic, reason-code generated
No profile is selected; nothing changes eligibility; no exclusions.
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
    RegionalSearchStatus,
    apply_policy,
    connected_components,
    explain,
    load_policy_config,
)
from hearthmap.provenance import ProvenanceRecord, current_code_version

M1B = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs/m1b")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("outputs/m1c")
CELL_KM2 = 0.25
STATUSES = [s.value for s in RegionalSearchStatus]
SCOPES = ("AOI", "TH50", "TH56", "TH57")
EVIDENCE_KEEP = [
    "cell_id",
    "majority_pcode",
    "coverage_fraction",
    "clipped_area_km2",
    "flood_state",
    "landslide_state",
    "terrain_state",
    "overall_state",
    "flood_confidence",
    "landslide_confidence",
    "terrain_confidence",
    "interpretation_confidence",
    "evidence_completeness",
    "flood_dataset_evaluated",
    "flood_positive_evidence_present",
    "landslide_dataset_evaluated",
    "landslide_positive_evidence_present",
    "terrain_dataset_evaluated",
    "terrain_positive_evidence_present",
    "dist_major_waterway_m",
    "dist_any_waterway_m",
    "boundary_attribution_uncertain",
    "boundary_zone_ids",
]


def scope_masks(w: pd.DataFrame) -> dict[str, pd.Series]:
    return {"AOI": pd.Series(True, index=w.index)} | {
        p: w["majority_pcode"] == p for p in ("TH50", "TH56", "TH57")
    }


def main() -> int:
    cfg = load_policy_config()
    OUT.mkdir(parents=True, exist_ok=True)
    w = pd.read_parquet(M1B / "hazard-evidence.parquet")
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    assert (grid["cell_id"].to_numpy() == w["cell_id"].to_numpy()).all()
    masks = scope_masks(w)
    area = w["clipped_area_km2"]

    results = {}
    for prof in cfg.profiles:
        results[prof] = apply_policy(w, cfg, prof)
    long = pd.concat(
        [pd.concat([w[EVIDENCE_KEEP], r], axis=1) for r in results.values()], ignore_index=True
    )
    long.to_parquet(OUT / "policy-results.parquet", index=False)

    # ---------------- statistics per profile x scope x status
    stats = {
        "policy_version": cfg.policy_version,
        "status": cfg.status,
        "scope": cfg.scope,
        "default_profile": cfg.default_profile,
        "gates": cfg.gates.model_dump(),
        "profiles": {},
    }
    rows = []
    for prof, r in results.items():
        stats["profiles"][prof] = {}
        for scope, m in masks.items():
            entry = {}
            for st in STATUSES:
                sel = m & (r["regional_search_status"] == st)
                entry[st] = {
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 2),
                    "share_of_area": round(float(area[sel].sum() / area[m].sum()), 4),
                }
                rows.append(
                    {
                        "profile": prof,
                        "scope": scope,
                        "province": PROVINCE_NAMES.get(scope, "AOI"),
                        "status": st,
                        **entry[st],
                    }
                )
            comp = r.loc[m, "evidence_completeness_class"].value_counts().to_dict()
            entry["evidence_completeness_class"] = comp
            entry["hazard_verification_required"] = int(
                r.loc[m, "hazard_verification_required"].sum()
            )
            entry["data_verification_required"] = int(r.loc[m, "data_verification_required"].sum())
            stats["profiles"][prof][scope] = entry
    pd.DataFrame(rows).to_csv(OUT / "policy-status-by-scope.csv", index=False)

    # ---------------- transitions (reference: BALANCED)
    tr_rows = []
    for other in ("CONSERVATIVE", "PERMISSIVE"):
        ct = pd.crosstab(
            results["BALANCED"]["regional_search_status"],
            results[other]["regional_search_status"],
            values=area,
            aggfunc="sum",
        ).fillna(0)
        cc = pd.crosstab(
            results["BALANCED"]["regional_search_status"], results[other]["regional_search_status"]
        )
        for a in ct.index:
            for b in ct.columns:
                tr_rows.append(
                    {
                        "from_profile": "BALANCED",
                        "to_profile": other,
                        "from_status": a,
                        "to_status": b,
                        "cells": int(cc.loc[a, b]),
                        "area_km2": round(float(ct.loc[a, b]), 2),
                    }
                )
    trans = pd.DataFrame(tr_rows)
    trans.to_csv(OUT / "profile-transitions.csv", index=False)
    changed = {
        o: float(
            trans[(trans["to_profile"] == o) & (trans["from_status"] != trans["to_status"])][
                "area_km2"
            ].sum()
        )
        for o in ("CONSERVATIVE", "PERMISSIVE")
    }
    stats["transitions_changed_area_km2_vs_balanced"] = changed

    # ---------------- candidate threshold sensitivity (spec 4/5/7)
    fl = cfg.flood_source
    hp = w["landslide_class4_fraction"] + w["landslide_class5_fraction"]
    ls_unres = w["landslide_assessed_fraction"] < cfg.unresolved.landslide_min_assessed_fraction
    ter_unres = w["terrain_support_px"] < cfg.unresolved.terrain_min_support_px
    others = {
        "flood_recurrent_ge0.10": w["flood_years_ge3_area_fraction"] >= 0.10,
        "landslide_very_high_ge0.25": w["landslide_class5_fraction"] >= 0.25,
        "landslide_high_plus_ge0.50": hp >= 0.50,
        "terrain_p90_ge30": w["slope_p90_deg"] >= 30,
    }
    candidates = (
        [
            (
                f"FLOOD_YEARS_GE{k}_OF_{fl.record_years} ({fl.period}) FRACTION",
                w[f"flood_years_ge{k}_area_fraction"],
                t,
            )
            for k in (2, 3, 4, 5)
            for t in (0.05, 0.10, 0.25, 0.50)
        ]
        + [
            ("LANDSLIDE_VERY_HIGH_FRACTION", w["landslide_class5_fraction"], t)
            for t in (0.10, 0.25, 0.50, 0.75)
        ]
        + [("LANDSLIDE_HIGH_PLUS_VERY_HIGH_FRACTION", hp, t) for t in (0.25, 0.50, 0.75, 0.95)]
        + [("TERRAIN_DSM_SLOPE_P90_DEG", w["slope_p90_deg"], t) for t in (25, 30, 35, 40)]
    )
    srows = []
    for name, vals, t in candidates:
        hit = (vals >= t).fillna(False)
        for scope, m in masks.items():
            sel = hit & m
            row = {
                "candidate": name,
                "threshold": t,
                "scope": scope,
                "province": PROVINCE_NAMES.get(scope, "AOI"),
                "cells": int(sel.sum()),
                "area_km2": round(float(area[sel].sum()), 2),
                "share_of_area": round(float(area[sel].sum() / area[m].sum()), 4),
                "share_with_landslide_unresolved": round(float(ls_unres[sel].mean()), 4)
                if sel.any()
                else 0.0,
                "share_with_terrain_unresolved": round(float(ter_unres[sel].mean()), 4)
                if sel.any()
                else 0.0,
            }
            for k, o in others.items():
                row[f"also_{k}"] = (
                    round(float(o[sel].fillna(False).mean()), 4) if sel.any() else 0.0
                )
            srows.append(row)
    pd.DataFrame(srows).to_csv(OUT / "candidate-threshold-sensitivity.csv", index=False)

    # ---------------- reason codes
    rc_rows = []
    for prof, r in results.items():
        for col in ("hazard_reason_codes", "data_reason_codes", "unresolved_reasons"):
            codes = r[col].str.split("|").explode()
            codes = codes[codes.astype(bool)]
            for code, n in codes.value_counts().items():
                idx = codes[codes == code].index.unique()
                rc_rows.append(
                    {
                        "profile": prof,
                        "field": col,
                        "reason_code": code,
                        "cells": int(n),
                        "area_km2": round(float(area[idx].sum()), 2),
                    }
                )
    pd.DataFrame(rc_rows).to_csv(OUT / "reason-code-distribution.csv", index=False)

    # ---------------- fragmentation (diagnostic only)
    frag_rows, comp_rows = [], []
    lonlat = grid.geometry.centroid.to_crs("EPSG:4326")
    for prof, r in results.items():
        for label, sts in (
            ("DEPRIORITIZE", {"REGIONAL_DEPRIORITIZE"}),
            ("CONCERN_OR_DEPRIORITIZE", {"STRONG_REGIONAL_CONCERN", "REGIONAL_DEPRIORITIZE"}),
            ("UNRESOLVED", {"UNRESOLVED"}),
        ):
            sel = r["regional_search_status"].isin(sts).to_numpy()
            idx = np.flatnonzero(sel)
            if len(idx) == 0:
                frag_rows.append({"profile": prof, "set": label, "cells": 0, "components": 0})
                continue
            lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
            sizes = np.bincount(lab)
            comp_area = np.bincount(lab, weights=area.to_numpy()[idx])
            frag_rows.append(
                {
                    "profile": prof,
                    "set": label,
                    "cells": len(idx),
                    "area_km2": round(float(comp_area.sum()), 2),
                    "components": len(sizes),
                    "isolated_single_cells": int((sizes == 1).sum()),
                    "components_lt_1km2": int((comp_area < 1).sum()),
                    "median_component_km2": round(float(np.median(comp_area)), 3),
                    "largest_component_km2": round(float(comp_area.max()), 2),
                    "share_area_in_largest_10": round(
                        float(np.sort(comp_area)[-10:].sum() / comp_area.sum()), 4
                    ),
                }
            )
            for k in np.argsort(comp_area)[::-1][:10]:
                members = idx[lab == k]
                comp_rows.append(
                    {
                        "profile": prof,
                        "set": label,
                        "rank": len(comp_rows),
                        "component_area_km2": round(float(comp_area[k]), 2),
                        "cells": int(sizes[k]),
                        "lon": round(float(lonlat.x.iloc[members].mean()), 3),
                        "lat": round(float(lonlat.y.iloc[members].mean()), 3),
                        "majority_province": PROVINCE_NAMES.get(
                            w["majority_pcode"].iloc[members].mode().iloc[0], "?"
                        ),
                        "dominant_reason": results[prof]["hazard_reason_codes"]
                        .iloc[members]
                        .str.split("|")
                        .explode()
                        .replace("", np.nan)
                        .dropna()
                        .mode()
                        .iloc[0]
                        if label != "UNRESOLVED"
                        else "LANDSLIDE_NOT_ASSESSED/TERRAIN",
                    }
                )
    frag = pd.DataFrame(frag_rows)
    frag.to_csv(OUT / "fragmentation-summary.csv", index=False)
    comps = pd.DataFrame(comp_rows)
    comps["rank"] = comps.groupby(["profile", "set"]).cumcount() + 1
    comps.to_csv(OUT / "largest-components.csv", index=False)

    # ---------------- example explanations (deterministic picks)
    bal = results["BALANCED"]
    ex = []
    for st in STATUSES:
        cand = bal.index[bal["regional_search_status"] == st]
        if len(cand) == 0:
            continue
        i = sorted(cand, key=lambda k: w.loc[k, "cell_id"])[len(cand) // 2]
        ex.append(explain(w.loc[i, "cell_id"], w.loc[i], bal.loc[i], cfg))
    wpp = w.index[w["boundary_zone_ids"].str.contains("gistda-50k-0009")]
    if len(wpp):
        i = sorted(wpp, key=lambda k: w.loc[k, "cell_id"])[0]
        ex.append(
            "[Wiang Pa Pao boundary-uncertainty cell - attribution caution only]\n"
            + explain(w.loc[i, "cell_id"], w.loc[i], bal.loc[i], cfg)
        )
    (OUT / "example-explanations.md").write_text(
        "# Example explanations (BALANCED profile, deterministic picks)\n\n"
        + "\n\n".join(f"```text\n{e}\n```" for e in ex)
        + "\n",
        "utf-8",
    )

    # ---------------- GeoPackage for review
    g = gpd.GeoDataFrame(
        w[
            [
                "cell_id",
                "majority_pcode",
                "flood_state",
                "landslide_state",
                "terrain_state",
                "boundary_attribution_uncertain",
            ]
        ].copy(),
        geometry=grid.geometry.values,
        crs=CANONICAL,
    )
    for prof, r in results.items():
        k = prof.lower()
        g[f"{k}_status"] = r["regional_search_status"].to_numpy()
        g[f"{k}_reasons"] = r["hazard_reason_codes"].to_numpy()
        g[f"{k}_unresolved"] = r["unresolved_reasons"].to_numpy()
    g["policy_status"] = cfg.status
    g["policy_note"] = (
        "Regional screening only - not SAFE/BUILDABLE/REJECT/LEGAL; "
        "hydrogeomorphic scope; provisional"
    )
    gpkg = OUT / "hazard-screening-policy.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    g.to_file(gpkg, layer="hydrogeomorphic_screening_profiles", driver="GPKG")

    (OUT / "policy-statistics.json").write_text(
        json.dumps(stats | {"fragmentation": frag.to_dict("records")}, indent=2, default=str)
        + "\n",
        "utf-8",
    )
    rec = ProvenanceRecord(
        artifact_id="m1c-hydrogeomorphic-screening",
        artifact_path=gpkg.as_posix(),
        code_version=current_code_version(),
        sources=[
            source_ref(s, original_crs=c)
            for s, c in (
                ("flood-gistda-history", "EPSG:4326"),
                ("landslide-susceptibility-dmr", "EPSG:32647"),
                ("landslide-inventory-dmr", "EPSG:32647"),
                ("dem-copernicus-glo30", "EPSG:4326+EPSG:3855"),
            )
        ],
        normalized_crs=CANONICAL,
        method=f"config/hazard-policy.yaml {cfg.policy_version} ({cfg.status}) applied to M1B "
        "hazard evidence for profiles " + ", ".join(cfg.profiles),
        spatial_resolution="500 m cells",
        confidence=Confidence.LOW,
        limitations=[
            "Regional screening only; hydrogeomorphic scope; no profile selected.",
            f"Human visual sign-off M1A.1 {cfg.gates.m1a1_human_visual_signoff}, M1B "
            f"{cfg.gates.m1b_human_visual_signoff}; M1C review pack not confirmed reviewed.",
            f"Flood thresholds refer to {cfg.flood_source.source_id} {cfg.flood_source.period} "
            f"({cfg.flood_source.record_years} years); 2005-2016 is context only.",
        ],
    )
    rec.write_sidecar(gpkg)
    print(
        json.dumps(
            {
                p: {s: v["cells"] for s, v in stats["profiles"][p]["AOI"].items() if s in STATUSES}
                for p in cfg.profiles
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
