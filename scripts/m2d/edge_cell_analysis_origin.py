# ruff: noqa: E501
"""M2D.1d: edge-cell analysis-origin QA (GRID_CENTROID vs AOI_ANALYSIS_POINT) and its accessibility impact.

Compares, for the SAME frozen routing (1 km snap, speeds, graph, bands), the nominal grid-centroid origin (saved by build_context as comparison columns)
with the AOI analysis point now used in the artifact. Interior cells never change. Writes the origin CSV/PNG and impact tables; no score, no rank.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "m1a"))
from common import CANONICAL, PROCESSED  # noqa: E402

from hearthmap.context.services import COMPONENTS  # noqa: E402
from hearthmap.context.settlement import GridIndex  # noqa: E402

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
PROV = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
CHECK_CELL = "G500-E001332-N004224"
LABELS = ["cluster_core", "cluster_broader", *[c.lower() for c in COMPONENTS]]
EQ_TOL = 0.005  # minutes: times are stored to 0.01 min


def main() -> int:
    df = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    cmp_ = pd.read_parquet("data/processed/m2d/routing_cache_cmp.parquet")
    assert len(cmp_) == len(df)
    cov = df["coverage_fraction"].to_numpy()
    partial = cov < 1 - 1e-9
    moved = (df["analysis_point_method"] != "GRID_CENTROID").to_numpy()
    new_ok = (
        df["service_convenience_store_unresolved_reason"] != "NO_ROAD_WITHIN_SNAP_DISTANCE"
    ).to_numpy()
    old_snap = cmp_["nominal_centroid_snap_distance_m"].to_numpy()
    old_ok = old_snap <= 1000
    pop = df["population_worldpop2025_mass_aoi_clipped"].to_numpy()

    # ---------------------------------------------------------------- scope (measured, not assumed)
    scope = {
        "total_cells": len(df),
        "partial_cells": int(partial.sum()),
        "partial_cells_with_centroid_inside_aoi_footprint": int((partial & ~moved).sum()),
        "partial_cells_with_centroid_outside_aoi_footprint": int((partial & moved).sum()),
        "cells_whose_routing_origin_changes": int(moved.sum()),
        "cells_whose_euclidean_distance_origin_changes": int(moved.sum()),
        "administrative_fallback_cells_m2d1b_for_comparison": int(
            (df["diw_tambon_assignment_method"] == "MAX_OVERLAP_WITHIN_OWN_GROUP").sum()
        ),
        "interior_cells": int((~partial).sum()),
        "interior_cells_with_changed_origin": int((moved & ~partial).sum()),
        "modelled_population_in_cells_with_changed_origin_aoi_clipped": round(
            float(pop[moved].sum()), 1
        ),
        "built_up_m2_in_cells_with_changed_origin_aoi_clipped": round(
            float(df["built_ghsl2020_m2_aoi_clipped"].to_numpy()[moved].sum()), 0
        ),
    }
    # interior-cell invariance of every routing value (the comparison columns are computed from the SAME frozen routing at the nominal centroid)
    inter = ~partial
    inv = {}
    for lab in LABELS:
        old = cmp_[f"nominal_centroid_time_{lab}_min"].to_numpy()
        new = df[f"drive_time_to_nearest_service_{lab}_min"].to_numpy()
        both_nan = np.isnan(old) & np.isnan(new)
        inv[lab] = int((inter & ~(both_nan | (np.abs(old - new) < EQ_TOL))).sum())
    scope["interior_cells_with_any_changed_service_time"] = int(sum(inv.values()))
    scope["interior_snap_distance_changed"] = int(
        (inter & (np.abs(old_snap - df["road_snap_distance_m"].to_numpy()) > 0.05)).sum()
    )

    # ---------------------------------------------------------------- accessibility impact among the affected cells
    rows = [
        {"metric": "network_snap_route_origin_resolved", "category": cat, "cells": n}
        for cat, n in (
            ("unchanged_resolved", int((moved & old_ok & new_ok).sum())),
            ("unchanged_unresolved", int((moved & ~old_ok & ~new_ok).sum())),
            ("became_unresolved", int((moved & old_ok & ~new_ok).sum())),
            ("became_resolved", int((moved & ~old_ok & new_ok).sum())),
        )
    ]
    snap_delta = (df["road_snap_distance_m"].to_numpy() - old_snap)[moved & old_ok & new_ok]
    impact = []
    for lab in LABELS:
        old = cmp_[f"nominal_centroid_time_{lab}_min"].to_numpy()
        new = df[f"drive_time_to_nearest_service_{lab}_min"].to_numpy()
        o_ok, n_ok = ~np.isnan(old), ~np.isnan(new)
        same = moved & ((~o_ok & ~n_ok) | (o_ok & n_ok & (np.abs(old - new) < EQ_TOL)))
        both = moved & o_ok & n_ok
        chg = both & (np.abs(old - new) >= EQ_TOL)
        d = (new - old)[chg]
        impact.append(
            {
                "metric": f"drive_time_to_nearest_service_{lab}_min",
                "affected_cells": int(moved.sum()),
                "unchanged": int(same.sum()),
                "changed_still_resolved": int(chg.sum()),
                "became_unresolved": int((moved & o_ok & ~n_ok).sum()),
                "became_resolved": int((moved & ~o_ok & n_ok).sum()),
                "delta_min_median_among_changed": round(float(np.median(d)), 2)
                if len(d)
                else np.nan,
                "delta_min_p10": round(float(np.quantile(d, 0.1)), 2) if len(d) else np.nan,
                "delta_min_p90": round(float(np.quantile(d, 0.9)), 2) if len(d) else np.nan,
                "affected_population_aoi_clipped": round(float(pop[moved].sum()), 1),
                "note": "statistics are over the affected edge cells only, not whole-AOI medians; delta = corrected origin minus nominal centroid origin",
            }
        )
    pd.DataFrame(rows).to_csv(
        OUT / "tables" / "edge-origin-route-resolution-impact.csv", index=False
    )
    pd.DataFrame(impact).to_csv(
        OUT / "tables" / "edge-origin-accessibility-impact.csv", index=False
    )

    # ---------------------------------------------------------------- per-cell origin CSV
    adm2 = gpd.read_file(
        next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip")),
        layer="tha_admin2",
    )
    names = adm2.drop_duplicates("adm2_pcode").set_index("adm2_pcode")["adm2_name"]
    dist_code = df["diw_tambon_pcode"].str[:6]
    t = pd.DataFrame(
        {
            "grid_id": df["cell_id"],
            "province": df["majority_pcode"].map(PROV),
            "district": dist_code.map(names).fillna(""),
            "aoi_coverage_fraction_of_cell": cov.round(4),
            "grid_centroid_lon": df["grid_centroid_lon"],
            "grid_centroid_lat": df["grid_centroid_lat"],
            "analysis_point_lon": df["analysis_point_lon"],
            "analysis_point_lat": df["analysis_point_lat"],
            "analysis_point_method": df["analysis_point_method"],
            "old_snap_distance_m": old_snap.round(1),
            "new_snap_distance_m": df["road_snap_distance_m"],
            "old_route_origin_resolved": old_ok,
            "new_route_origin_resolved": new_ok,
        }
    )
    for lab in (
        "cluster_core",
        "cluster_broader",
        "convenience_store",
        "grocery_or_supermarket",
        "pharmacy",
    ):
        t[f"old_time_{lab}_min"] = cmp_[f"nominal_centroid_time_{lab}_min"].to_numpy()
        t[f"new_time_{lab}_min"] = df[f"drive_time_to_nearest_service_{lab}_min"]
    t["origin_state"] = np.where(
        ~partial,
        "INTERIOR_CENTROID_ORIGIN",
        np.where(
            moved, "EDGE_ORIGIN_REPLACED_WITH_AOI_REPRESENTATIVE_POINT", "EDGE_CENTROID_STILL_VALID"
        ),
    )
    t[moved].sort_values("grid_id").to_csv(REVIEW / "edge-cell-analysis-origin.csv", index=False)

    c = t[t["grid_id"] == CHECK_CELL].iloc[0]
    checked = {k: (v.item() if hasattr(v, "item") else v) for k, v in c.items()}
    scope["checked_cell"] = checked
    scope["route_resolution_among_affected"] = {r["category"]: r["cells"] for r in rows}
    scope["snap_distance_delta_m_among_resolved_both_median"] = (
        round(float(np.median(snap_delta)), 1) if len(snap_delta) else None
    )
    (OUT / "edge-origin-summary.json").write_text(
        json.dumps(scope, indent=1, default=str) + "\n", "utf-8"
    )
    print(
        json.dumps({k: v for k, v in scope.items() if k != "checked_cell"}, indent=1, default=str)
    )
    print(json.dumps(checked, indent=1, default=str))

    # ---------------------------------------------------------------- map
    gi = GridIndex(df["cell_id"].tolist())
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries").to_crs(
        CANONICAL
    )
    extent = (gi.e0 * 500, (gi.e0 + gi.w) * 500, gi.n0 * 500, (gi.n0 + gi.h) * 500)
    state = np.where(~partial, 1, np.where(moved, 3, 2))
    arr = np.full((gi.h, gi.w), np.nan)
    arr[gi.row, gi.col] = state
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    prov.boundary.plot(ax=ax, color="black", linewidth=0.5)
    ax.imshow(
        arr,
        origin="lower",
        extent=extent,
        cmap=ListedColormap(["#d9d9d9", "#2c7fb8", "#e31a1c"]),
        vmin=0.5,
        vmax=3.5,
        interpolation="nearest",
    )
    pe, pn = (gi.e0 + gi.col[partial] + 0.5) * 500, (gi.n0 + gi.row[partial] + 0.5) * 500
    mv = moved[partial]
    ax.scatter(pe[~mv], pn[~mv], s=5, c="#2c7fb8", linewidths=0)
    ax.scatter(
        pe[mv], pn[mv], s=5, c="#e31a1c", linewidths=0
    )  # partial cells drawn enlarged so they are visible at AOI scale
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        f"Analysis origin of each cell. Edge cells: {int(partial.sum()):,} partial; centroid still valid {int((partial & ~moved).sum()):,}; replaced {int(moved.sum()):,} (partial cells drawn enlarged)",
        fontsize=8,
    )
    ax.legend(
        handles=[plt.Rectangle((0, 0), 1, 1, fc=c_, label=l_) for c_, l_ in (("#d9d9d9", "interior: GRID_CENTROID origin"), ("#2c7fb8", "edge: centroid still inside the AOI footprint"), ("#e31a1c", "edge: origin replaced by AOI representative point"))],
        loc="lower left", fontsize=7,
    )  # fmt: skip
    # zoom on the checked cell
    ax2 = axes[1]
    i = int(np.flatnonzero(df["cell_id"].to_numpy() == CHECK_CELL)[0])
    e, n = (int(x[1:]) for x in CHECK_CELL.split("-")[1:])
    box = shapely.box(e * 500, n * 500, (e + 1) * 500, (n + 1) * 500)
    win = box.buffer(1200)
    aoi = shapely.union_all(prov.geometry.to_numpy())
    gpd.GeoSeries([shapely.intersection(aoi, win)], crs=CANONICAL).plot(
        ax=ax2, color="#fdd0a2", alpha=0.6
    )
    gpd.GeoSeries([box], crs=CANONICAL).boundary.plot(ax=ax2, color="black", linewidth=1.2)
    gpd.GeoSeries([shapely.intersection(box, aoi)], crs=CANONICAL).plot(
        ax=ax2, color="#e31a1c", alpha=0.35
    )
    gx, gy = (e + 0.5) * 500, (n + 0.5) * 500
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4326", CANONICAL, always_xy=True)
    ax_, ay_ = tr.transform(df["analysis_point_lon"].iloc[i], df["analysis_point_lat"].iloc[i])
    ax2.scatter(
        [gx], [gy], marker="x", c="black", s=70, label="nominal GRID_CENTROID (outside the AOI)"
    )
    ax2.scatter(
        [ax_],
        [ay_],
        marker="o",
        c="#e31a1c",
        s=70,
        edgecolors="black",
        label="AOI_ANALYSIS_POINT (inside GRID_FOOTPRINT intersect AOI)",
    )
    ax2.set_xlim(win.bounds[0], win.bounds[2])
    ax2.set_ylim(win.bounds[1], win.bounds[3])
    ax2.set_aspect("equal")
    ax2.set_xticks([])
    ax2.set_yticks([])
    ax2.legend(fontsize=7, loc="lower left")
    ax2.set_title(
        f"{CHECK_CELL}: AOI covers {cov[i]:.1%} of the 500 m cell (shaded = AOI; red = analytical footprint)",
        fontsize=8,
    )
    fig.text(
        0.01,
        0.01,
        "QA only: origins are geographically neutral (never moved toward roads or services); no suitability semantics. Partial cells are clipped to the AOI; a sliver is not a full 500 m footprint.",
        fontsize=7,
    )
    fig.savefig(REVIEW / "edge-cell-analysis-origin.png", dpi=110, bbox_inches="tight")
    return 0


if __name__ == "__main__":
    sys.exit(main())
