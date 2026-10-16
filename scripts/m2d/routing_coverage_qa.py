# ruff: noqa: E501
"""M2D.1a: routing-coverage QA. Do unresolved cells (no connected road within 1 km) hold meaningful settlement?

Reads the existing artifact and the M2A.2 road-access context. It recomputes NO routing and changes no routing parameter (snap distance,
speeds, network). Population is a MODELLED_POPULATION_ESTIMATE (WorldPop R2025A, alpha); built-up is GHSL built-up surface in m2 per cell.
Output is QA context only: no suitability field, no ranking, no policy threshold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "m1a"))
from common import CANONICAL, PROCESSED  # noqa: E402

from hearthmap.context.settlement import GridIndex, assign_max_overlap  # noqa: E402
from hearthmap.context.stats import QUANTILES, weighted_coverage  # noqa: E402

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
PROV = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
TOP_N = 150
SNAP_M = 1000  # the existing, unchanged routing rule (config/family-infrastructure.yaml max_snap_distance_m)
DISPLAY_CLASSES = [
    "ROUTABLE_NO_SETTLEMENT_SIGNAL",
    "ROUTABLE_SETTLEMENT",
    "UNRESOLVED_LOW_SETTLEMENT_TERRAIN",
    "UNRESOLVED_SETTLEMENT_LIKE_FOR_REVIEW",
]
TIME_COLUMNS = [
    "drive_time_to_nearest_service_cluster_core_min",
    "drive_time_to_nearest_service_cluster_broader_min",
] + [
    f"drive_time_to_nearest_service_{c}_min"
    for c in (
        "convenience_store",
        "grocery_or_supermarket",
        "pharmacy",
        "fuel",
        "bank_or_financial",
        "market",
        "public_administration",
        "general_retail_or_service",
    )
]


def main() -> int:
    df = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    m2a = pd.read_parquet("outputs/m2a2/family-infrastructure-evidence.parquet")
    assert (df["cell_id"].to_numpy() == m2a["cell_id"].to_numpy()).all()
    n = len(df)
    # same flag the service routing used (the artifact rounds snap distance to 0.1 m, so re-deriving it from the rounded value could flip cells at exactly 1000 m)
    routable = (
        df["service_convenience_store_unresolved_reason"] != "NO_ROAD_WITHIN_SNAP_DISTANCE"
    ).to_numpy()
    pop = df["population_worldpop2025_count_500m"].to_numpy()
    built = df["built_ghsl2020_surface_m2_500m"].to_numpy()
    frac = df["built_ghsl2020_fraction_500m"].to_numpy()
    area = (df["coverage_fraction"] * 0.25).to_numpy()
    scopes = {
        **{name: (df["majority_pcode"] == pc).to_numpy() for pc, name in PROV.items()},
        "Whole AOI": np.ones(n, bool),
    }

    rows = []
    for scope, m in scopes.items():
        a = weighted_coverage(np.where(m, area, 0), routable)
        p = weighted_coverage(np.where(m, pop, 0), routable)
        b = weighted_coverage(np.where(m, built, 0), routable)
        cells_total, cells_unres = int(m.sum()), int((m & ~routable).sum())
        rows.append(
            {
                "scope": scope, "cells_total": cells_total, "cells_unresolved": cells_unres, "unresolved_cell_share": round(cells_unres / cells_total, 4),
                "area_total_km2": round(a["total"], 1), "area_unresolved_km2": round(a["unresolved"], 1), "unresolved_area_share": round(a["unresolved_share"], 4),
                "modelled_population_total": round(p["total"]), "modelled_population_routable": round(p["routable"]), "modelled_population_unresolved": round(p["unresolved"]), "unresolved_population_share": round(p["unresolved_share"], 4),
                "built_up_m2_total": round(b["total"]), "built_up_m2_routable": round(b["routable"]), "built_up_m2_unresolved": round(b["unresolved"]), "unresolved_built_up_share": round(b["unresolved_share"], 4),
                "population_semantics": "MODELLED_POPULATION_ESTIMATE (WorldPop R2025A alpha), not observed population",
                "built_up_aggregation": "sum of GHSL built-up surface m2 per cell (a mass), not a cell count",
                "weighting_note": "cell, area, population and built-up shares are different weightings; travel times are NOT population-weighted",
            }
        )  # fmt: skip
    cov = pd.DataFrame(rows)
    cov.to_csv(OUT / "tables" / "routing-coverage-weighted.csv", index=False)
    # old (full-cell context) vs corrected (AOI-clipped) shares: cell and area shares must not move
    pop_ctx = df["population_worldpop2025_count_500m_full_cell_context"].to_numpy()
    built_ctx = df["built_ghsl2020_surface_m2_500m_full_cell_context"].to_numpy()
    cmp_rows = []
    for scope, m in scopes.items():
        po = weighted_coverage(np.where(m, pop_ctx, 0), routable)["unresolved_share"]
        pn = weighted_coverage(np.where(m, pop, 0), routable)["unresolved_share"]
        bo = weighted_coverage(np.where(m, built_ctx, 0), routable)["unresolved_share"]
        bn = weighted_coverage(np.where(m, built, 0), routable)["unresolved_share"]
        row = cov[cov["scope"] == scope].iloc[0]
        cmp_rows.append(
            {
                "scope": scope,
                "unresolved_cell_share": row["unresolved_cell_share"],
                "unresolved_area_share": row["unresolved_area_share"],
                "unresolved_population_share_old_full_cell_context": round(po, 4),
                "unresolved_population_share_corrected_aoi_clipped": round(pn, 4),
                "unresolved_built_up_share_old_full_cell_context": round(bo, 4),
                "unresolved_built_up_share_corrected_aoi_clipped": round(bn, 4),
                "note": "cell and area shares are unchanged by AOI clipping; the corrected population and built-up shares replace the old figures",
            }
        )
    pd.DataFrame(cmp_rows).to_csv(
        OUT / "tables" / "routing-coverage-old-vs-aoi-clipped.csv", index=False
    )

    # reference for a DISPLAY class only: median of the routable cells' non-zero values (descriptive, not a policy threshold)
    ref_pop = float(np.median(pop[routable & (pop > 0)]))
    ref_built = float(np.median(built[routable & (built > 0)]))
    has_settle = (pop > 0) | (built > 0)
    unres = ~routable
    settle_like = unres & ((pop >= ref_pop) | (built >= ref_built))
    cls = np.select(
        [routable & has_settle, routable, settle_like, unres],
        [
            "ROUTABLE_SETTLEMENT",
            "ROUTABLE_NO_SETTLEMENT_SIGNAL",
            "UNRESOLVED_SETTLEMENT_LIKE_FOR_REVIEW",
            "UNRESOLVED_LOW_SETTLEMENT_TERRAIN",
        ],
        "",
    )

    dist = []
    for label, m in (
        ("ROUTABLE", routable),
        ("UNRESOLVED", unres),
        ("UNRESOLVED_SETTLEMENT_LIKE_FOR_REVIEW", settle_like),
    ):
        for col, v in (
            ("modelled_population_per_cell", pop),
            ("built_up_m2_per_cell", built),
            ("built_up_fraction", frac),
        ):
            x = v[m]
            d = {
                "cell_group": label,
                "variable": col,
                "n_cells": int(m.sum()),
                "share_with_nonzero": round(float((x > 0).mean()), 4),
            }
            for q in QUANTILES:
                d[f"p{int(q * 100)}"] = round(float(np.quantile(x, q)), 4)
            d["max"] = round(float(x.max()), 4)
            dist.append(d)
    pd.DataFrame(dist).to_csv(
        OUT / "tables" / "routing-unresolved-settlement-distributions.csv", index=False
    )

    # district for the review table: the ADM2 unit of the cell's OWN province that overlaps the cell most (authoritative COD hierarchy).
    # A centroid join against all of Thailand is NOT used for the label: edge cells keep only a fraction of their area inside the AOI, so
    # their centroid can lie in a neighbouring province (M2D.1b: Tha Wang Pha, Nan, for a cell that is 18% in Phayao's Pong district).
    adm2_all = gpd.read_file(
        next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip")),
        layer="tha_admin2",
    ).to_crs(CANONICAL)
    adm2 = adm2_all[adm2_all["adm1_pcode"].isin(PROV)].reset_index(drop=True)
    grid = (
        gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    d_ids, d_share, d_method = assign_max_overlap(
        grid.geometry.to_numpy(),
        grid["majority_pcode"].to_numpy(),
        adm2.geometry.to_numpy(),
        adm2["adm1_pcode"].to_numpy(),
        adm2["adm2_pcode"].to_numpy(),
        centroid_first=True,
    )
    lookup = adm2.set_index("adm2_pcode")
    district = lookup["adm2_name"].reindex(d_ids).fillna("").to_numpy()
    district_th = lookup["adm2_name1"].reindex(d_ids).fillna("").to_numpy()
    # explicit CONTEXT fields (never used as the administrative label): where the cell centroid falls nationwide
    cen_pts = grid.geometry.centroid
    cen = gpd.GeoDataFrame(geometry=cen_pts, crs=CANONICAL)
    j = gpd.sjoin(
        cen,
        adm2_all[["adm1_pcode", "adm1_name", "adm2_name", "geometry"]],
        how="left",
        predicate="within",
    )
    j = j[~j.index.duplicated()].reindex(range(n))
    centroid_adm1 = j["adm1_name"].fillna("outside Thailand / no unit").to_numpy()
    centroid_adm2 = j["adm2_name"].fillna("").to_numpy()
    centroid_in_reported_province = j["adm1_pcode"].to_numpy() == grid["majority_pcode"].to_numpy()
    lonlat = gpd.GeoSeries(cen_pts, crs=CANONICAL).to_crs(4326)
    clon, clat = lonlat.x.to_numpy(), lonlat.y.to_numpy()
    cov_frac = grid["coverage_fraction"].to_numpy()
    dsnap = df["road_snap_distance_m"].to_numpy()
    frag = m2a["road_any_fragment_distance_m"].to_numpy()
    ctx_road = m2a["road_access_context"].to_numpy()
    bands = pd.cut(
        dsnap, [1000, 2000, 5000, 10000, np.inf], labels=["1-2 km", "2-5 km", "5-10 km", ">10 km"]
    )
    cause = pd.DataFrame(
        {
            "group": np.where(
                settle_like[unres], "UNRESOLVED_SETTLEMENT_LIKE_FOR_REVIEW", "UNRESOLVED_OTHER"
            ),
            "road_access_context": ctx_road[unres],
            "distance_to_routable_network_band": bands[unres].astype(str),
            "modelled_population": pop[unres],
            "built_up_m2": built[unres],
        }
    )
    ct = (
        cause.groupby(["group", "road_access_context", "distance_to_routable_network_band"])
        .agg(
            cells=("group", "size"),
            modelled_population=("modelled_population", "sum"),
            built_up_m2=("built_up_m2", "sum"),
        )
        .reset_index()
    )
    ct[["modelled_population", "built_up_m2"]] = ct[["modelled_population", "built_up_m2"]].round()
    ct.to_csv(OUT / "tables" / "routing-unresolved-cause-summary.csv", index=False)

    # review table: highest-population and highest-built-up unresolved cells (descriptive; no suitability or ranking field)
    idx = np.where(unres)[0]
    top_pop = set(idx[np.argsort(-pop[idx])[:TOP_N]].tolist())
    top_built = set(idx[np.argsort(-built[idx])[:TOP_N]].tolist())
    sel = sorted(top_pop | top_built)
    review = pd.DataFrame(
        {
            "grid_id": df["cell_id"].to_numpy()[sel],
            "province": df["majority_pcode"].map(PROV).to_numpy()[sel],
            "province_pcode": df["majority_pcode"].to_numpy()[sel],
            "district_pcode": d_ids[sel],
            "district": district[sel],
            "district_th": district_th[sel],
            "district_assignment_method": d_method[sel],
            "district_overlap_share_of_cell": d_share[sel].round(3),
            "aoi_coverage_fraction_of_cell": cov_frac[sel].round(3),
            "cell_centroid_lon": clon[sel].round(5),
            "cell_centroid_lat": clat[sel].round(5),
            "centroid_in_reported_province": centroid_in_reported_province[sel],
            "centroid_nationwide_adm1_context": centroid_adm1[sel],
            "centroid_nationwide_adm2_context": centroid_adm2[sel],
            "modelled_population": pop[sel].round(1),
            "built_up_m2": built[sel].round(0),
            "built_up_fraction": frac[sel],
            "distance_to_routable_network_m": dsnap[sel].round(0),
            "distance_to_any_road_fragment_m": frag[sel].round(0),
            "road_access_context": ctx_road[sel],
            "unresolved_reason": df["service_convenience_store_unresolved_reason"].to_numpy()[sel],
            "in_top_population_list": [i in top_pop for i in sel],
            "in_top_built_up_list": [i in top_built for i in sel],
            "evidence_note": "QA context: modelled population (alpha) and GHSL built-up are AOI-CLIPPED (grid cell intersect AOI), so evidence outside the AOI is excluded; unresolved is not routing failure and not a rejection",
        }
    ).sort_values("modelled_population", ascending=False)
    review.to_csv(REVIEW / "routing-unresolved-settlement-overlap.csv", index=False)

    # town-service statistics keep their denominators; population coverage is added as QA context only
    st = pd.read_csv(OUT / "tables" / "descriptive-statistics.csv")
    times = st[st["column"].str.startswith("drive_time_to_nearest_service_")]
    need = {
        "cells_resolved",
        "resolved_area_share",
        "cells_unresolved",
        "unresolved_area_share",
        "statistic_population",
    }
    exposure_ok = need <= set(times.columns) and bool(
        times["statistic_population"].eq("MEDIAN_AMONG_ROUTABLE_CELLS_ONLY").all()
    )
    ctx = []
    for col in TIME_COLUMNS:
        res = df[col].notna().to_numpy()
        p = weighted_coverage(pop, res)
        ctx.append(
            {
                "column": col, "cells_with_a_route": int(res.sum()), "cells_total": n, "cells_without_route": int((~res).sum()),
                "modelled_population_in_cells_with_a_route": round(p["routable"]), "modelled_population_without_a_route": round(p["unresolved"]),
                "population_without_a_route_share": round(p["unresolved_share"], 4),
                "note": "population coverage is QA context; the travel time itself is not population-weighted",
            }
        )  # fmt: skip
    pd.DataFrame(ctx).to_csv(
        OUT / "tables" / "town-services-population-coverage-context.csv", index=False
    )

    summary = {
        "routing_parameters_changed": False,
        "snap_distance_m_used": SNAP_M,
        "population_semantics": "MODELLED_POPULATION_ESTIMATE",
        "display_class_reference": {"routable_nonzero_population_median": round(ref_pop, 2), "routable_nonzero_built_up_m2_median": round(ref_built, 1), "note": "descriptive reference for a display class, not a policy threshold"},
        "class_counts": pd.Series(cls).value_counts().to_dict(),
        "town_service_summaries_expose_denominators": exposure_ok,
        "aoi": cov[cov["scope"] == "Whole AOI"].iloc[0].to_dict(),
    }  # fmt: skip
    (OUT / "routing-coverage-qa-summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8"
    )

    # ---------------------------------------------------------------- map
    gi = GridIndex(df["cell_id"].tolist())
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries").to_crs(
        CANONICAL
    )
    extent = (gi.e0 * 500, (gi.e0 + gi.w) * 500, gi.n0 * 500, (gi.n0 + gi.h) * 500)
    colors = ["#f2f2f2", "#2c7fb8", "#bdbdbd", "#e31a1c"]
    arr = np.full((gi.h, gi.w), np.nan)
    arr[gi.row, gi.col] = (
        pd.Series(cls).map({k: i + 1 for i, k in enumerate(DISPLAY_CLASSES)}).to_numpy(dtype=float)
    )
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = axes[0]
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.imshow(
        arr,
        origin="lower",
        extent=extent,
        cmap=ListedColormap(colors),
        vmin=0.5,
        vmax=4.5,
        interpolation="nearest",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    a = cov[cov["scope"] == "Whole AOI"].iloc[0]
    ax.set_title(
        f"Routing gaps vs modelled settlement (QA only). Unresolved: {a['unresolved_cell_share']:.1%} of cells, {a['unresolved_area_share']:.1%} of area, {a['unresolved_population_share']:.1%} of modelled population, {a['unresolved_built_up_share']:.1%} of built-up m2",
        fontsize=8,
    )
    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=c, label=f"{k} ({int((cls == k).sum()):,})")
        for k, c in zip(DISPLAY_CLASSES, colors, strict=True)
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=7)
    sl = np.where(cls == DISPLAY_CLASSES[3])[0]
    ax.scatter(
        (gi.e0 + gi.col[sl] + 0.5) * 500,
        (gi.n0 + gi.row[sl] + 0.5) * 500,
        s=9,
        c="#e31a1c",
        edgecolors="black",
        linewidths=0.2,
    )  # enlarged so single cells are visible
    note = f"Settlement-like for review = unresolved and at/above the median of routable non-zero cells (modelled pop {ref_pop:.1f}, built-up {ref_built:.0f} m2). Display class only: not a threshold, not an automatic routing failure. Red markers enlarged."
    fig.text(0.01, 0.04, note, fontsize=7)
    ax2 = axes[1]
    ax2.set_title("Share of each quantity that sits in unresolved cells", fontsize=8)
    names = [*PROV.values(), "Whole AOI"]
    w = 0.2
    for k, (col, lab) in enumerate(
        (
            ("unresolved_cell_share", "cells"),
            ("unresolved_area_share", "area"),
            ("unresolved_population_share", "modelled population"),
            ("unresolved_built_up_share", "built-up m2"),
        )
    ):
        vals = [float(cov.loc[cov["scope"] == s, col].iloc[0]) for s in names]
        ax2.bar(np.arange(len(names)) + (k - 1.5) * w, vals, w, label=lab)
    ax2.set_xticks(np.arange(len(names)))
    ax2.set_xticklabels(names, fontsize=8)
    ax2.set_ylim(0, 0.6)
    ax2.legend(fontsize=7)
    fig.text(
        0.01,
        0.01,
        "QA visualisation only. Population = MODELLED_POPULATION_ESTIMATE (WorldPop R2025A alpha). Routing rule (1 km snap, frozen BASELINE_DRIVE_TIME network) unchanged. No scoring.",
        fontsize=7,
    )
    fig.savefig(REVIEW / "routing-unresolved-settlement-overlap.png", dpi=110, bbox_inches="tight")
    print(
        cov[
            [
                "scope",
                "unresolved_cell_share",
                "unresolved_area_share",
                "unresolved_population_share",
                "unresolved_built_up_share",
            ]
        ].to_string()
    )
    print(summary["class_counts"], "exposure_ok", exposure_ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
