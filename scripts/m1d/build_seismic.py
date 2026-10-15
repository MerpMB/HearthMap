"""M1D: seismic evidence build (fault context, shaking-zone context, historical seismicity).

Inputs: RAW DMR/TMD/USGS layers (acquire_dmr_seismic.py, acquire_seismicity.py), the 500 m
grid, M1B evidence (terrain strata for REPORTING only) and the selected provisional
hydrogeomorphic defaults (BALANCED + FLOOD_ANY_SOURCE) from outputs/m1c3.

Outputs: outputs/m1d/ (seismic-evidence.parquet, review GeoPackage, diagnostics) and
outputs/m1d-review/ (tables, QA, examples). No scalar Natural Hazard score, no ranking.
"""

from __future__ import annotations

import copy
import glob
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import AOI_LONLAT, CANONICAL, PROCESSED, PROVINCE_NAMES, source_ref

from hearthmap.enums import Confidence
from hearthmap.hazard import connected_components
from hearthmap.hazard.flood_fusion import slope_stratum, tabulate
from hearthmap.ingestion.readers import read_esrijson_pages
from hearthmap.provenance import ProvenanceRecord, current_code_version
from hearthmap.qa.repair import audit_repairs, summarise_repairs
from hearthmap.seismic import (
    INTERPRETATION_STATES,
    SeismicConfig,
    explain_seismic,
    fault_context,
    ground_response_columns,
    historical_context,
    interpret_seismic,
    load_seismic_config,
    parse_dmr_earthquakes,
    parse_tmd_statistics,
    parse_usgs_geojson,
    shaking_context,
)
from hearthmap.spatial import repair_geometries
from hearthmap.spatial.transform import reproject_recorded

OUT = Path("outputs/m1d")
REVIEW = Path("outputs/m1d-review")
EVIDENCE_M1B = Path("outputs/m1c1/evidence/hazard-evidence.parquet")
HYDRO_LONG = Path("outputs/m1c3/policy-results-long.parquet")
SELECTED = {"hydrogeomorphic_profile": "BALANCED", "flood_fusion_policy": "FLOOD_ANY_SOURCE"}
HYDRO_ORDER = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
BANDS = [
    ("<= 5 km", 0, 5),
    ("5-10 km", 5, 10),
    ("10-20 km", 10, 20),
    ("20-50 km", 20, 50),
    ("> 50 km", 50, np.inf),
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


def raw_dir_of(source_id: str) -> Path:
    return Path(glob.glob(f"data/raw/{source_id}/*/")[0])


def points(df: pd.DataFrame, name: str):
    ok = df[df["coords_available"] & df["magnitude"].notna()].copy()
    g = gpd.GeoDataFrame(ok, geometry=gpd.points_from_xy(ok["lon"], ok["lat"]), crs="EPSG:4326")
    out, rec = reproject_recorded(g, CANONICAL, name=name, area_of_interest=AOI_LONLAT)
    return out, rec


def variant(cfg: SeismicConfig, **edits) -> SeismicConfig:
    raw = copy.deepcopy(cfg.model_dump())
    for path, val in edits.items():
        node = raw
        keys = path.split("__")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = val
    return SeismicConfig.model_validate(raw)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    cfg = load_seismic_config()
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.values)
    n = len(grid)
    cov = grid["coverage_fraction"].to_numpy()
    cells = grid.geometry.values
    m1b = pd.read_parquet(EVIDENCE_M1B)
    if not (m1b["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all():
        raise ValueError("M1B evidence cell order differs from the grid")
    area = m1b["clipped_area_km2"].to_numpy()
    pcode = grid["majority_pcode"].to_numpy()
    qa: dict = {}
    transformations = []

    # ------------------------------------------------ faults: read, QA
    faults = read_esrijson_pages(raw_dir_of("seismic-active-faults-dmr"), "page")
    fq = {
        "features": len(faults),
        "crs": str(faults.crs),
        "geometry_types": faults.geom_type.value_counts().to_dict(),
        "valid": int(faults.is_valid.sum()),
        "empty": int(faults.is_empty.sum()),
        "exact_duplicate_geometries": int(
            pd.Series(shapely.to_wkb(faults.geometry.values)).duplicated().sum()
        ),
        "fault_zones": faults["F_ZONE_E"].value_counts().to_dict(),
        "type_values": faults["TYPE"].value_counts().to_dict(),
        "mce_range": [float(faults["MCE"].min()), float(faults["MCE"].max())],
        "length_km_range": [
            round(float(faults["LENGTH_KM"].min()), 3),
            round(float(faults["LENGTH_KM"].max()), 1),
        ],
        "length_attr_vs_geometry_ratio_median": round(
            float((faults["LENGTH_KM"] / (faults.geometry.length / 1000)).median()), 4
        ),
    }
    comp = {}
    for c in faults.columns:
        if c == "geometry":
            continue
        s = faults[c]
        txt = s.astype(str).str.strip()
        comp[c] = {
            "non_null": int(s.notna().sum()),
            "blank_or_zero_placeholder": int(
                (s.notna() & txt.isin(["", "0", "0.0", "None"])).sum()
            ),
            "populated": int((s.notna() & ~txt.isin(["", "0", "0.0", "None"])).sum()),
            "unique": int(s.nunique()),
        }
    fq["attribute_completeness"] = comp
    qa["faults"] = fq
    faults = faults[faults.geometry.notna() & ~faults.is_empty].reset_index(drop=True)
    near = faults.distance(aoi) <= 100_000
    fq["traces_within_100km_of_aoi"] = int(near.sum())
    fq["length_inside_aoi_km"] = round(float(faults.intersection(aoi).length.sum() / 1000), 1)

    # ------------------------------------------------ intensity zones: read, repair audit, QA
    zones = read_esrijson_pages(raw_dir_of("seismic-intensity-zones-dmr"), "page")
    zones = zones.assign(fid=zones["OBJECTID"])
    audit = audit_repairs(zones, id_column="fid")
    qa["intensity_zones_repair"] = summarise_repairs(audit, total_features=len(zones))
    audit.to_csv(OUT / "intensity-zones-repair-audit.csv", index=False)
    zones = repair_geometries(zones)
    zones = zones.explode(index_parts=False)
    zones = zones[zones.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    tree = shapely.STRtree(zones.geometry.values)
    a, b = tree.query(zones.geometry.values, predicate="intersects")
    k = a < b
    ov = shapely.area(
        shapely.intersection(zones.geometry.values[a[k]], zones.geometry.values[b[k]])
    )
    clip_a = shapely.area(shapely.intersection(zones.geometry.values, aoi)) / 1e6
    zq = {
        "features_raw": 427,
        "features_after_repair_explode": len(zones),
        "crs": str(zones.crs),
        "classes": zones["INTENSITY"].value_counts().to_dict(),
        "intensity_vs_description_pairs": zones.groupby(["INTENSITY", "INTEN_T"])
        .size()
        .reset_index()
        .astype(str)
        .values.tolist(),
        "pairwise_overlap_area_m2": float(ov.sum()),
        "aoi_area_km2": float(aoi.area / 1e6),
        "aoi_covered_km2": float(clip_a.sum()),
        "aoi_class_area_km2": {
            c: round(float(clip_a[(zones["INTENSITY"] == c).to_numpy()].sum()), 1)
            for c in cfg.sources["intensity_zones"]["classes"]
        },
    }
    qa["intensity_zones"] = zq
    log("faults/zones read")

    # ------------------------------------------------ catalogues
    dmr_raw = read_esrijson_pages(raw_dir_of("geohazard-events-dmr"), "page")
    cat_frames = {
        "dmr": parse_dmr_earthquakes(dmr_raw),
        "tmd": parse_tmd_statistics(next(raw_dir_of("seismic-felt-events-tmd").glob("*.xls"))),
        "usgs": parse_usgs_geojson(next(raw_dir_of("seismicity-usgs-comcat").glob("*.geojson"))),
    }
    cats = {}
    cat_summary = []
    for name, df in cat_frames.items():
        pts, tr = points(df, name)
        cats[name] = pts
        transformations.append(tr)
        w = pts[pts.geometry.distance(aoi) <= 100_000]
        row = {
            "source": name,
            "records": len(df),
            "with_coordinates": int(df["coords_available"].sum()),
            "with_magnitude": int(df["magnitude"].notna().sum()),
            "usable_points": len(pts),
            "year_min": int(pts["event_year"].min()),
            "year_max": int(pts["event_year"].max()),
            "within_100km_of_aoi": len(w),
        }
        for m in cfg.history_magnitude_thresholds:
            row[f"within_100km_ge_M{m:g}"] = int((w["magnitude"] >= m).sum())
        cat_summary.append(row)
        if name == "tmd":
            row["note"] = (
                "records without coordinates (chronicles, intensity-only, unparsed) are excluded "
                f"from spatial metrics: {len(df) - int(df['coords_available'].sum())}"
            )
    pd.DataFrame(cat_summary).to_csv(REVIEW / "historical-seismicity-summary.csv", index=False)
    qa["catalogues"] = cat_summary
    log("catalogues parsed")

    # ------------------------------------------------ evidence
    fc = fault_context(cells, faults, cfg)
    sc = shaking_context(grid, zones, cfg, within=aoi, coverage=cov)
    hc = historical_context(cells, cats, cfg)
    gr = ground_response_columns(n, cfg)
    base = pd.concat([fc, sc, hc, gr], axis=1)
    interp = interpret_seismic(base, cfg)
    ev = pd.concat(
        [
            pd.DataFrame(
                {
                    "cell_id": grid["cell_id"].to_numpy(),
                    "majority_pcode": pcode,
                    "clipped_area_km2": area,
                }
            ),
            base,
            interp,
        ],
        axis=1,
    )
    ev.to_parquet(OUT / "seismic-evidence.parquet", index=False)
    log("evidence built")

    # validation: DMR "tambon within 20 km of active faults" listing vs our traces
    tb = read_esrijson_pages(raw_dir_of("seismic-tambon-near-faults-dmr"), "page")
    tb = tb[tb.geometry.notna()]
    tbt = shapely.STRtree(faults.geometry.values)
    _p, d = tbt.query_nearest(tb.geometry.values, return_distance=True, all_matches=False)
    qa["tambon_listing_validation"] = {
        "points": len(tb),
        "within_20km_of_nearest_trace_share": round(float((d <= 20000).mean()), 4),
        "within_25km_share": round(float((d <= 25000).mean()), 4),
        "median_distance_km": round(float(np.median(d) / 1000), 2),
        "max_distance_km": round(float(d.max() / 1000), 2),
        "note": "a proximity LISTING (not a hazard surface); used only to check trace geometry",
    }

    # ------------------------------------------------ strata + selected hydrogeomorphic defaults
    strat = slope_stratum(m1b["slope_p90_deg"].to_numpy(), m1b["terrain_support_px"].to_numpy())
    hy = pd.read_parquet(HYDRO_LONG)
    hy = hy[
        (hy["flood_policy"] == SELECTED["flood_fusion_policy"])
        & (hy["profile"] == SELECTED["hydrogeomorphic_profile"])
    ].set_index("cell_id")
    hydro = hy.loc[grid["cell_id"], "regional_search_status"].to_numpy()
    diag = pd.DataFrame(
        {
            "cell_id": grid["cell_id"].to_numpy(),
            "majority_pcode": pcode,
            "clipped_area_km2": area,
            "slope_stratum_reporting_only": strat,
            "hydro_regional_search_status": hydro,
            "seismic_screening_interpretation": interp[
                "seismic_screening_interpretation"
            ].to_numpy(),
            "selected_hydrogeomorphic_profile": SELECTED["hydrogeomorphic_profile"],
            "selected_flood_fusion_policy": SELECTED["flood_fusion_policy"],
            "selected_for_provisional_screening": True,
            "production_truth": False,
        }
    )
    diag.to_parquet(OUT / "hydro-seismic-diagnostic-cells.parquet", index=False)
    masks = {"AOI": np.ones(n, bool)} | {p: pcode == p for p in ("TH50", "TH56", "TH57")}
    smask = {s: (np.ones(n, bool) if v is None else np.isin(strat, v)) for s, v in STRATA.items()}
    state = interp["seismic_screening_interpretation"].to_numpy()

    # ------------------------------------------------ distributions
    t = tabulate(state, area, masks, list(INTERPRETATION_STATES))
    t["province"] = t["scope"].map(PROVINCE_NAMES).fillna("AOI")
    t.to_csv(REVIEW / "seismic-interpretation-distribution.csv", index=False)
    rows = []
    for s, m in smask.items():
        x = tabulate(state, area, {s: m}, list(INTERPRETATION_STATES))
        rows.append(x.rename(columns={"scope": "stratum"}))
    low = pd.concat(rows, ignore_index=True)
    low.to_csv(REVIEW / "seismic-lowland-context.csv", index=False)
    # intensity class area by province and stratum
    cls = cfg.sources["intensity_zones"]["classes"]
    crow = []
    for scope, m in masks.items():
        for c in cls:
            f = sc[f"shaking_class{c}_fraction"].to_numpy()
            crow.append(
                {
                    "scope": scope,
                    "province": PROVINCE_NAMES.get(scope, "AOI"),
                    "stratum": "ALL",
                    "class": c,
                    "area_km2": round(float((f * area)[m].sum()), 1),
                    "share_of_scope_area": round(float((f * area)[m].sum() / area[m].sum()), 4),
                    "cells_dominant": int(
                        ((sc["shaking_dominant_class"] == c).to_numpy() & m).sum()
                    ),
                }
            )
    for s, m in smask.items():
        if s == "ALL":
            continue
        for c in cls:
            f = sc[f"shaking_class{c}_fraction"].to_numpy()
            crow.append(
                {
                    "scope": "AOI",
                    "province": "AOI",
                    "stratum": s,
                    "class": c,
                    "area_km2": round(float((f * area)[m].sum()), 1),
                    "share_of_scope_area": round(float((f * area)[m].sum() / area[m].sum()), 4),
                    "cells_dominant": int(
                        ((sc["shaking_dominant_class"] == c).to_numpy() & m).sum()
                    ),
                }
            )
    pd.DataFrame(crow).to_csv(REVIEW / "intensity-class-area.csv", index=False)
    # distance bands of cells (context only)
    d = fc["fault_nearest_distance_km"].to_numpy()
    brow = []
    for scope, m in masks.items():
        for label, lo, hi in BANDS:
            sel = m & (d > lo if lo > 0 else d >= 0) & (d <= hi)
            brow.append(
                {
                    "scope": scope,
                    "province": PROVINCE_NAMES.get(scope, "AOI"),
                    "stratum": "ALL",
                    "band": label,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 1),
                    "share_of_scope_area": round(float(area[sel].sum() / area[m].sum()), 4),
                }
            )
    for s, m in smask.items():
        if s == "ALL":
            continue
        for label, lo, hi in BANDS:
            sel = m & (d > lo if lo > 0 else d >= 0) & (d <= hi)
            brow.append(
                {
                    "scope": "AOI",
                    "province": "AOI",
                    "stratum": s,
                    "band": label,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 1),
                    "share_of_scope_area": round(float(area[sel].sum() / area[m].sum()), 4),
                }
            )
    pd.DataFrame(brow).to_csv(REVIEW / "fault-distance-bands.csv", index=False)

    # ------------------------------------------------ fault regional context (per province)
    prow = []
    for _, pr in prov.iterrows():
        poly = pr.geometry
        buf = poly.buffer(20_000)
        inter = faults.geometry.intersection(poly)
        in_buf = faults.geometry.intersection(buf)
        for zone, g in faults.assign(
            inside=inter.length / 1000, near=in_buf.length / 1000, hits=(inter.length > 0)
        ).groupby("F_ZONE_E"):
            if g["near"].sum() <= 0:
                continue
            prow.append(
                {
                    "province": pr["adm1_name"],
                    "fault_zone": zone,
                    "traces_intersecting_province": int(g["hits"].sum()),
                    "trace_length_inside_km": round(float(g["inside"].sum()), 1),
                    "trace_length_within_20km_buffer_km": round(float(g["near"].sum()), 1),
                    "max_MCE_source_native": float(g["MCE"].max()),
                }
            )
    pd.DataFrame(prow).sort_values(
        ["province", "trace_length_inside_km"], ascending=[True, False]
    ).to_csv(REVIEW / "fault-regional-context.csv", index=False)

    # ------------------------------------------------ cross-tab: hydrogeomorphic x seismic
    ct = []
    for scope, m in masks.items():
        for s, sm in smask.items():
            if scope != "AOI" and s != "ALL":
                continue
            mm = m & sm
            for h in HYDRO_ORDER:
                for z in INTERPRETATION_STATES:
                    sel = mm & (hydro == h) & (state == z)
                    ct.append(
                        {
                            "scope": scope,
                            "stratum": s,
                            "hydro_status": h,
                            "seismic_state": z,
                            "cells": int(sel.sum()),
                            "area_km2": round(float(area[sel].sum()), 1),
                        }
                    )
    pd.DataFrame(ct).to_csv(REVIEW / "hydro-vs-seismic-crosstab.csv", index=False)
    fav = hydro == "NO_MAJOR_CONCERN_DETECTED"
    seis_meaning = np.isin(
        state, ["REQUIRES_SEISMIC_VERIFICATION", "STRONG_SEISMIC_SCREENING_CONCERN"]
    )
    hyd_concern = np.isin(hydro, ["STRONG_REGIONAL_CONCERN", "REGIONAL_DEPRIORITIZE"])
    seis_none = state == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"
    dis = {
        "hydro_favourable_seismic_meaningful": fav & seis_meaning,
        "hydro_favourable_seismic_strong": fav & (state == "STRONG_SEISMIC_SCREENING_CONCERN"),
        "hydro_concern_seismic_none_detected": hyd_concern & seis_none,
        "hydro_favourable_and_seismic_none_detected": fav & seis_none,
    }
    drow = []
    for name, mk in dis.items():
        for scope, m in masks.items():
            for s, sm in smask.items():
                if scope != "AOI" and s != "ALL":
                    continue
                sel = mk & m & sm
                drow.append(
                    {
                        "pattern": name,
                        "scope": scope,
                        "stratum": s,
                        "cells": int(sel.sum()),
                        "area_km2": round(float(area[sel].sum()), 1),
                        "share_of_scope_area": round(float(area[sel].sum() / area[m & sm].sum()), 4)
                        if (m & sm).any()
                        else None,
                    }
                )
    pd.DataFrame(drow).to_csv(REVIEW / "hydro-seismic-disagreement.csv", index=False)

    # ------------------------------------------------ experimental sensitivity (not a selection)
    variants = {
        "BASE": cfg,
        "fault_verify_5km": variant(
            cfg,
            interpretation__fault__verify_within_km=5.0,
            interpretation__fault__strong_tier_within_km=5.0,
        ),
        "fault_verify_20km": variant(cfg, interpretation__fault__verify_within_km=20.0),
        "shaking_tier1_VI": variant(cfg, interpretation__shaking__class_tier1="VI"),
        "shaking_fractions_0.75": variant(
            cfg,
            interpretation__shaking__tier1_min_fraction=0.75,
            interpretation__shaking__tier2_min_fraction=0.75,
        ),
        "history_M4_within_50": variant(cfg, interpretation__history__magnitude=4.0),
        "history_M6_within_50": variant(cfg, interpretation__history__magnitude=6.0),
        "history_tier1_100km": variant(cfg, interpretation__history__tier1_within_km=100.0),
        "strong_needs_2_families": variant(cfg, interpretation__strong_requires_families=2),
    }
    srow = []
    for name, vc in variants.items():
        r = interpret_seismic(base, vc)["seismic_screening_interpretation"].to_numpy()
        for scope, m in masks.items():
            for z in INTERPRETATION_STATES:
                sel = m & (r == z)
                srow.append(
                    {
                        "variant": name,
                        "scope": scope,
                        "state": z,
                        "cells": int(sel.sum()),
                        "area_km2": round(float(area[sel].sum()), 1),
                        "share_of_area": round(float(area[sel].sum() / area[m].sum()), 4),
                        "experimental": True,
                    }
                )
    pd.DataFrame(srow).to_csv(REVIEW / "seismic-sensitivity.csv", index=False)

    # family signal areas per tier
    fam = []
    for f in ("fault_tier", "shaking_tier", "history_tier"):
        for tier in ("NONE", "NOTABLE", "STRONG_TIER"):
            sel = (interp[f] == tier).to_numpy()
            fam.append(
                {
                    "family": f,
                    "tier": tier,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 1),
                }
            )
    pd.DataFrame(fam).to_csv(REVIEW / "seismic-family-tiers.csv", index=False)
    pd.DataFrame(
        [{"family": k, **v} for k, v in cfg.confidence.items()]
        + [
            {
                "family": "decision (per cell)",
                "source": "-",
                "methodology": "-",
                "spatial_completeness": "-",
                "temporal_completeness": cfg.decision_confidence,
            }
        ]
    ).to_csv(REVIEW / "source-confidence.csv", index=False)

    # ------------------------------------------------ sensitive/strong regions
    ex = []
    strong_idx = np.flatnonzero(state == "STRONG_SEISMIC_SCREENING_CONCERN")
    if len(strong_idx):
        lab = connected_components(
            grid["col"].to_numpy()[strong_idx], grid["row"].to_numpy()[strong_idx]
        )
        ca = np.bincount(lab, weights=area[strong_idx])
        cent = grid.geometry.centroid.to_crs("EPSG:4326")
        for rank, kk in enumerate(np.argsort(ca)[::-1][:15], 1):
            mm = strong_idx[lab == kk]
            ex.append(
                {
                    "rank": rank,
                    "area_km2": round(float(ca[kk]), 1),
                    "cells": len(mm),
                    "lon": round(float(cent.x.iloc[mm].mean()), 3),
                    "lat": round(float(cent.y.iloc[mm].mean()), 3),
                    "majority_province": PROVINCE_NAMES.get(pd.Series(pcode[mm]).mode().iloc[0]),
                    "nearest_zone": pd.Series(fc["fault_nearest_zone"].to_numpy()[mm])
                    .mode()
                    .iloc[0],
                    "share_low_slope": round(float((strat[mm] == "LOW_SLOPE_LE_5").mean()), 3),
                }
            )
    pd.DataFrame(ex).to_csv(REVIEW / "strong-seismic-regions.csv", index=False)

    # ------------------------------------------------ example explanations
    picks = {}
    for label, mask in (
        ("STRONG (>= 2 strong-tier families)", state == "STRONG_SEISMIC_SCREENING_CONCERN"),
        (
            "VERIFY by fault proximity only",
            (interp["fault_tier"] != "NONE").to_numpy()
            & (interp["shaking_tier"] == "NONE").to_numpy()
            & (interp["history_tier"] == "NONE").to_numpy(),
        ),
        (
            "VERIFY by intensity zone only",
            (interp["shaking_tier"] != "NONE").to_numpy()
            & (interp["fault_tier"] == "NONE").to_numpy()
            & (interp["history_tier"] == "NONE").to_numpy(),
        ),
        (
            "NO MAJOR SEISMIC CONCERN DETECTED (not safe)",
            state == "NO_MAJOR_SEISMIC_CONCERN_DETECTED",
        ),
        ("UNRESOLVED", state == "UNRESOLVED"),
        (
            "low-slope cell",
            (strat == "LOW_SLOPE_LE_5") & (state != "NO_MAJOR_SEISMIC_CONCERN_DETECTED"),
        ),
    ):
        idx = np.flatnonzero(mask)
        if len(idx):
            picks[label] = int(idx[len(idx) // 2])
    lines = ["# Example seismic explanations (generated from reason codes)", ""]
    for label, i in picks.items():
        lines += [
            f"## {label}",
            "",
            "```text",
            explain_seismic(grid["cell_id"].iloc[i], ev.iloc[i], interp.iloc[i], cfg),
            "```",
            "",
        ]
    (REVIEW / "example-explanations.md").write_text("\n".join(lines), "utf-8")

    # ------------------------------------------------ review GeoPackage
    gpkg = OUT / "seismic-evidence.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    keep = [
        "cell_id",
        "majority_pcode",
        "seismic_screening_interpretation",
        "fault_tier",
        "shaking_tier",
        "history_tier",
        "strong_tier_families",
        "seismic_reason_codes",
        "seismic_unresolved_reasons",
        "fault_nearest_distance_km",
        "fault_nearest_zone",
        "shaking_dominant_class",
        "shaking_max_class",
        "hist_nearest_ge5_km",
        "seismic_evidence_completeness",
        "ground_response_status",
    ]
    g = gpd.GeoDataFrame(ev[keep], geometry=cells, crs=CANONICAL)
    g.to_file(gpkg, layer="seismic_evidence_cells", driver="GPKG")
    faults[near].drop(columns=[c for c in faults.columns if faults[c].isna().all()]).to_file(
        gpkg, layer="active_fault_traces_near_aoi", driver="GPKG"
    )
    zc = zones.copy()
    zc["geometry"] = shapely.intersection(zc.geometry.values, aoi)
    zc = zc[~zc.is_empty][["EQ_ZONE_ID", "INTENSITY", "geometry"]]
    zc.to_file(gpkg, layer="intensity_zones_clipped_to_aoi", driver="GPKG")
    allpts = pd.concat([c.assign(catalog=k) for k, c in cats.items()], ignore_index=True)
    allpts = gpd.GeoDataFrame(allpts, geometry="geometry", crs=CANONICAL)
    allpts = allpts[allpts.geometry.distance(aoi) <= 100_000]
    allpts["event_time_utc"] = allpts["event_time_utc"].astype(str)
    allpts.to_file(gpkg, layer="historical_events_within_100km", driver="GPKG")

    # ------------------------------------------------ statistics + provenance
    stats = {
        "seismic_version": cfg.seismic_version,
        "status": cfg.status,
        "selected_provisional_defaults": SELECTED
        | {"selected_for_provisional_screening": True, "production_truth": False},
        "interpretation_area_km2_aoi": {
            z: round(float(area[state == z].sum()), 1) for z in INTERPRETATION_STATES
        },
        "interpretation_cells_aoi": {z: int((state == z).sum()) for z in INTERPRETATION_STATES},
        "fault_nearest_distance_km_quantiles": {
            str(q): round(float(np.nanquantile(d, q)), 2) for q in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)
        },
        "strata_area_km2": {s: round(float(area[m].sum()), 1) for s, m in smask.items()},
        "qa": qa,
    }
    (REVIEW / "seismic-statistics.json").write_text(
        json.dumps(stats, indent=2, default=str, ensure_ascii=False) + "\n", "utf-8"
    )
    rec = ProvenanceRecord(
        artifact_id="m1d-seismic-evidence",
        artifact_path=gpkg.as_posix(),
        code_version=current_code_version(),
        sources=[
            source_ref("seismic-active-faults-dmr", original_crs="EPSG:32647"),
            source_ref("seismic-intensity-zones-dmr", original_crs="EPSG:32647"),
            source_ref("geohazard-events-dmr", original_crs="EPSG:32647"),
            source_ref("seismic-felt-events-tmd", original_crs="EPSG:4326"),
            source_ref("seismicity-usgs-comcat", original_crs="EPSG:4326"),
            source_ref("seismic-tambon-near-faults-dmr", original_crs="EPSG:32647"),
        ],
        normalized_crs=CANONICAL,
        method=f"config/seismic-evidence.yaml {cfg.seismic_version} ({cfg.status}, experimental): "
        "distance/count context to DMR active-fault traces, area share of DMR model intensity "
        "zones, per-source historical-event metrics, explicit ground-response limitation, "
        "multi-family conservative screening state.",
        spatial_resolution="500 m cells; fault traces and intensity zones of undocumented scale",
        confidence=Confidence.LOW,
        limitations=[
            "Evidence engineering, not a seismic hazard model: no fault distance score, no scalar "
            "Natural Hazard score, no ranking.",
            "DMR intensity-zone methodology is undocumented (a 'model program'); licence forbids "
            "commercial use and legal reference.",
            "Historical catalogues are incomplete and not deduplicated; absence of events is not "
            "evidence of low hazard.",
            "Ground response (site class, sediment, amplification, liquefaction) is not assessed.",
            "Slope strata are reporting-only and never an input.",
        ],
        crs_transformations=transformations,
    )
    rec.write_sidecar(gpkg)
    log(
        json.dumps(
            {
                k: stats[k]
                for k in ("interpretation_area_km2_aoi", "fault_nearest_distance_km_quantiles")
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
