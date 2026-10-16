# ruff: noqa: E501
"""M2D.1e: boundary-sensitive accessibility QA. QA only: no statistical correction, no policy buffer, no suitability semantics.

Asks whether cells near the AOI boundary systematically show longer service/facility times than interior cells because the destination catalogue stops at
the AOI provinces. Descriptive geometry only: distance from the analysis point to the AOI boundary, banded, and the parameter-free destination-catalogue
completeness state (BOUNDARY_LIMITED when leaving the AOI is faster than reaching the catalogued destination).
Writes tables and outputs/m2d-review/accessibility-boundary-context.png.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import shapely

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "m1a"))
from common import CANONICAL, PROCESSED  # noqa: E402

from hearthmap.context.boundary import (  # noqa: E402
    BOUNDARY_LIMITED,
    COMPLETE_WITHIN_AVAILABLE_CATALOG,
    SOURCE_COMPLETENESS_UNKNOWN,
)

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
BANDS_KM = [0, 0.5, 1, 2, 5, 10, 20, np.inf]
LABELS = ["0-0.5 km", "0.5-1 km", "1-2 km", "2-5 km", "5-10 km", "10-20 km", ">20 km"]
SERVICE = [
    "cluster_core",
    "cluster_broader",
    "convenience_store",
    "grocery_or_supermarket",
    "pharmacy",
]
EDU = ["kindergarten", "primary_school", "secondary_school"]
HEALTH = ["primary_health_unit", "hospital"]
CHECK_CELL = "G500-E001332-N004224"


def band_table(
    df: pd.DataFrame, family: str, items: list[str], time_col, comp_col, pop: np.ndarray
) -> pd.DataFrame:
    band = pd.cut(df["distance_to_aoi_boundary_m"] / 1000.0, BANDS_KM, labels=LABELS, right=False)
    rows = []
    for item in items:
        t = df[time_col(item)]
        comp = df[comp_col(item)]
        for b in LABELS:
            m = (band == b).to_numpy()
            ok = m & t.notna().to_numpy()
            rows.append(
                {
                    "family": family, "category": item, "distance_to_aoi_boundary_band": b, "cells": int(m.sum()), "cells_with_a_route": int(ok.sum()),
                    "share_of_cells_with_a_route": round(float(ok.sum() / m.sum()), 4) if m.sum() else np.nan,
                    "median_time_min_among_routed": round(float(t[ok].median()), 2) if ok.any() else np.nan,
                    "p90_time_min_among_routed": round(float(t[ok].quantile(0.9)), 2) if ok.any() else np.nan,
                    "share_boundary_limited_among_cells_with_a_route": round(float((comp[ok] == BOUNDARY_LIMITED).mean()), 4) if ok.any() else np.nan,
                    "share_boundary_limited_among_all_cells_in_band": round(float((comp[m] == BOUNDARY_LIMITED).mean()), 4) if m.any() else np.nan,
                    "share_complete_within_available_catalog_among_all_cells": round(float((comp[m] == COMPLETE_WITHIN_AVAILABLE_CATALOG).mean()), 4) if m.any() else np.nan,
                    "share_completeness_unknown_among_all_cells": round(float((comp[m] == SOURCE_COMPLETENESS_UNKNOWN).mean()), 4) if m.any() else np.nan,
                    "modelled_population_in_band": round(float(pop[m].sum())),
                    "statistic_population": "MEDIAN_AMONG_CELLS_WITH_A_ROUTE_ONLY",
                    "note": "QA only: no statistical correction; mountainous border terrain also lengthens times, so a gradient is not proof of truncation",
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def main() -> int:
    d = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    m = pd.read_parquet("outputs/m2a2-origin/family-infrastructure-evidence.parquet")
    pop = d["population_worldpop2025_mass_aoi_clipped"].to_numpy()
    assert (d["cell_id"].to_numpy() == m["cell_id"].to_numpy()).all()
    m = m.assign(distance_to_aoi_boundary_m=d["distance_to_aoi_boundary_m"].to_numpy())
    t_s = band_table(
        d,
        "town_services",
        SERVICE,
        lambda i: f"drive_time_to_nearest_service_{i}_min",
        lambda i: f"service_{i}_destination_catalog_completeness",
        pop,
    )
    t_e = band_table(
        m,
        "education",
        EDU,
        lambda i: f"drive_time_to_nearest_{i}_min",
        lambda i: f"{i}_destination_catalog_completeness",
        pop,
    )
    t_h = band_table(
        m,
        "healthcare",
        HEALTH,
        lambda i: f"drive_time_to_nearest_{i}_min",
        lambda i: f"{i}_destination_catalog_completeness",
        pop,
    )
    allt = pd.concat([t_s, t_e, t_h], ignore_index=True)
    allt.to_csv(OUT / "tables" / "accessibility-boundary-distance-bands.csv", index=False)
    # completeness summary for every town-service result (cells with a route and all cells)
    comp_rows = []
    for item in [
        *SERVICE,
        "market",
        "fuel",
        "bank_or_financial",
        "public_administration",
        "general_retail_or_service",
    ]:
        c = d[f"service_{item}_destination_catalog_completeness"]
        comp_rows.append(
            {
                "category": item,
                **{
                    k: int((c == k).sum())
                    for k in (
                        COMPLETE_WITHIN_AVAILABLE_CATALOG,
                        BOUNDARY_LIMITED,
                        SOURCE_COMPLETENESS_UNKNOWN,
                    )
                },
            }
        )
    pd.DataFrame(comp_rows).to_csv(
        OUT / "tables" / "town-service-destination-completeness.csv", index=False
    )
    print(
        allt[allt["category"].isin(["cluster_core", "primary_school", "hospital"])][
            [
                "family",
                "category",
                "distance_to_aoi_boundary_band",
                "cells",
                "cells_with_a_route",
                "median_time_min_among_routed",
                "share_boundary_limited_among_cells_with_a_route",
            ]
        ].to_string()
    )

    # ---------------------------------------------------------------- map
    gi_e = d["cell_id"].str.extract(r"E(\d+)-N(\d+)").astype(int)
    e, n = gi_e[0].to_numpy(), gi_e[1].to_numpy()
    x, y = (e + 0.5) * 500, (n + 0.5) * 500
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries").to_crs(
        CANONICAL
    )
    aoi = shapely.union_all(prov.geometry.to_numpy())
    comp = d["service_cluster_core_destination_catalog_completeness"].to_numpy()
    colors = {
        COMPLETE_WITHIN_AVAILABLE_CATALOG: "#2c7fb8",
        BOUNDARY_LIMITED: "#e31a1c",
        SOURCE_COMPLETENESS_UNKNOWN: "#d9d9d9",
    }
    sv = pd.read_csv("data/processed/m2d/service_pois.csv")
    edu = gpd.read_file("data/processed/m2a2/facilities.gpkg", layer="education_facilities").to_crs(
        CANONICAL
    )
    edu = edu[edu["coordinate_qa_status"] != "FAILED"]
    hl = gpd.read_file("data/processed/m2a2/facilities.gpkg", layer="health_facilities").to_crs(
        CANONICAL
    )
    moved = (d["analysis_point_method"] != "GRID_CENTROID").to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(18, 9), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    gpd.GeoSeries(prov.geometry.to_numpy(), crs=CANONICAL).boundary.plot(
        ax=ax, color="black", linewidth=0.6
    )
    for k, col in colors.items():
        mk = comp == k
        ax.scatter(
            x[mk], y[mk], s=0.6, c=col, linewidths=0, label=f"CORE cluster: {k} ({int(mk.sum()):,})"
        )
    ax.scatter(
        x[moved],
        y[moved],
        s=6,
        marker="x",
        c="black",
        linewidths=0.4,
        label=f"edge origin replaced by AOI analysis point ({int(moved.sum()):,})",
    )
    ax.legend(loc="lower left", fontsize=7, markerscale=6)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(
        "Destination-catalogue completeness of the CORE town-service result. BOUNDARY_LIMITED = leaving the AOI is faster than reaching the catalogued destination (an outside destination could be nearer)",
        fontsize=7,
    )
    # zoom: the checked cell's border region
    ax2 = axes[1]
    ee, nn = (int(v) for v in CHECK_CELL.replace("G500-E", "").split("-N"))
    cx, cy = (ee + 0.5) * 500, (nn + 0.5) * 500
    half = 12000
    win = shapely.box(cx - half, cy - half, cx + half, cy + half)
    gpd.GeoSeries([shapely.intersection(aoi, win)], crs=CANONICAL).plot(
        ax=ax2, color="#fff7ec", edgecolor="black", linewidth=0.8
    )
    inw = (x > cx - half) & (x < cx + half) & (y > cy - half) & (y < cy + half)
    for k, col in colors.items():
        mk = inw & (comp == k)
        ax2.scatter(x[mk], y[mk], s=10, c=col, linewidths=0)
    sx = (
        (sv["x"] > cx - half)
        & (sv["x"] < cx + half)
        & (sv["y"] > cy - half)
        & (sv["y"] < cy + half)
    )
    ax2.scatter(
        sv.loc[sx, "x"],
        sv.loc[sx, "y"],
        s=22,
        marker="^",
        c="#238b45",
        edgecolors="black",
        linewidths=0.3,
        label="town-service POIs (destinations in the catalogue)",
    )
    ec = edu.geometry.get_coordinates()
    ex = (
        (ec["x"] > cx - half)
        & (ec["x"] < cx + half)
        & (ec["y"] > cy - half)
        & (ec["y"] < cy + half)
    )
    ax2.scatter(
        ec.loc[ex, "x"], ec.loc[ex, "y"], s=14, marker="s", c="#6a51a3", label="schools (catalogue)"
    )
    hc = hl.geometry.get_coordinates()
    hx = (
        (hc["x"] > cx - half)
        & (hc["x"] < cx + half)
        & (hc["y"] > cy - half)
        & (hc["y"] < cy + half)
    )
    ax2.scatter(
        hc.loc[hx, "x"],
        hc.loc[hx, "y"],
        s=40,
        marker="P",
        c="#cb181d",
        edgecolors="black",
        linewidths=0.4,
        label="health facilities (catalogue)",
    )
    i = int(np.flatnonzero(d["cell_id"].to_numpy() == CHECK_CELL)[0])
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:4326", CANONICAL, always_xy=True)
    ax_, ay_ = tr.transform(d["analysis_point_lon"].iloc[i], d["analysis_point_lat"].iloc[i])
    ax2.scatter(
        [ax_],
        [ay_],
        s=120,
        marker="*",
        c="gold",
        edgecolors="black",
        label=f"{CHECK_CELL} analysis point (AOI part)",
    )
    ax2.set_xlim(cx - half, cx + half)
    ax2.set_ylim(cy - half, cy + half)
    ax2.set_aspect("equal")
    ax2.set_xticks([])
    ax2.set_yticks([])
    ax2.legend(loc="lower left", fontsize=7)
    ax2.set_title(
        "24 km window at the Phayao / Nan border: the catalogues stop at the AOI provinces (white area = outside the AOI: no destination records, though the road network reaches into it)",
        fontsize=7,
    )
    fig.text(
        0.01,
        0.01,
        "QA only: no suitability semantics, no policy buffer, no statistical correction. ORIGIN_EXTENT, NETWORK_EXTENT, DESTINATION_CATALOG_EXTENT and FEATURE_CONTEXT_EXTENT are different concepts. See docs/research/m2d1e-accessibility-contract-unification.md.",
        fontsize=7,
    )
    fig.savefig(REVIEW / "accessibility-boundary-context.png", dpi=110, bbox_inches="tight")
    return 0


if __name__ == "__main__":
    sys.exit(main())
