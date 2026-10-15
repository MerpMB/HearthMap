# ruff: noqa: E501
"""M2A: review maps and statistics. Accessibility scales (sequential, not green=good); verified data only.

Never ranks provinces and never combines evidence into a score.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import BoundaryNorm, ListedColormap

PROC = Path("data/processed")
REVIEW = Path("outputs/m2a-review")
PROV_NAMES = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
BINS = [0, 5, 15, 30, 60, 120]
SCOPES = ["AOI", "TH50", "TH56", "TH57"]
CATS = [
    "early_childhood_centre",
    "kindergarten",
    "primary_school",
    "secondary_school",
    "vocational_institution",
    "university",
    "primary_health_unit",
    "hospital",
    "higher_level_hospital",
]


def load():
    art = pd.read_parquet("outputs/m2a/family-infrastructure-evidence.parquet")
    grid = (
        gpd.read_file(PROC / "m1a" / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    assert (grid["cell_id"].to_numpy() == art["cell_id"].to_numpy()).all()
    c = shapely.get_coordinates(grid.geometry.centroid)
    ix = np.round((c[:, 0] - c[:, 0].min()) / 500).astype(int)
    iy = np.round((c[:, 1] - c[:, 1].min()) / 500).astype(int)
    prov = gpd.read_file(PROC / "m1a" / "boundaries.gpkg", layer="province_boundaries")
    edu = gpd.read_file(PROC / "m2a" / "facilities.gpkg", layer="education_facilities")
    hl = gpd.read_file(PROC / "m2a" / "facilities.gpkg", layer="health_facilities")
    major = gpd.read_file(PROC / "m1a" / "layers.gpkg", layer="major_roads")
    art["area_km2"] = 0.25 * art["coverage_fraction"].to_numpy()
    return art, ix, iy, c, prov, edu, hl, major


def raster(values, ix, iy, dtype=float):
    arr = np.full((iy.max() + 1, ix.max() + 1), np.nan, dtype=dtype)
    arr[iy, ix] = values
    return arr


def extent(c):
    return (c[:, 0].min() - 250, c[:, 0].max() + 250, c[:, 1].min() - 250, c[:, 1].max() + 250)


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.set_xticks([])
    ax.set_yticks([])


def time_panel(ax, art, col, ix, iy, c, prov, title):
    v = art[col].to_numpy(float)
    cmap = plt.get_cmap("viridis", len(BINS))
    norm = BoundaryNorm(BINS, cmap.N, extend="max")
    ext = extent(c)
    unresolved = raster(np.where(np.isnan(v), 1.0, np.nan), ix, iy)
    ax.imshow(
        unresolved,
        origin="lower",
        extent=ext,
        cmap=ListedColormap(["#c9c9c9"]),
        interpolation="nearest",
    )
    im = ax.imshow(
        raster(np.clip(v, 0, 119.9), ix, iy),
        origin="lower",
        extent=ext,
        cmap=cmap,
        norm=norm,
        interpolation="nearest",
    )
    outline(ax, prov)
    share = float(np.isnan(v).mean() * 100)
    ax.set_title(f"{title}\nunresolved (grey): {share:.1f}% of cells", fontsize=9)
    return im


def footer(fig, text):
    fig.text(0.01, 0.005, text, fontsize=7, color="#444")


def maps(art, ix, iy, c, prov, edu, hl, major):
    REVIEW.mkdir(parents=True, exist_ok=True)
    ext = extent(c)
    # 1 education facilities
    fig, ax = plt.subplots(figsize=(8, 9))
    outline(ax, prov)
    palette = {
        "EARLY_CHILDHOOD": "#1b9e77",
        "KINDERGARTEN": "#d95f02",
        "PRIMARY": "#7570b3",
        "LOWER_SECONDARY": "#e7298a",
        "VOCATIONAL": "#66a61e",
        "UNIVERSITY_TERTIARY": "#000000",
    }
    shown = edu[edu["coordinate_qa_status"] != "FAILED"]
    for lv, col in palette.items():
        sub = shown[shown["levels"].str.split("|").map(lambda s, lv=lv: lv in s)]
        sub.plot(
            ax=ax,
            color=col,
            markersize=3 if lv != "UNIVERSITY_TERTIARY" else 14,
            label=f"{lv} (n={len(sub)})",
            alpha=0.7,
        )
    ax.legend(fontsize=7, loc="lower left", title="derived level (DOPA 2021)", title_fontsize=7)
    failed = edu[edu["coordinate_qa_status"] == "FAILED"]
    ax.set_title(
        f"Education institutions: presence only, levels derived from names\n{len(shown)} plotted, {len(failed)} coordinate-QA failures not plotted (excluded, not corrected)",
        fontsize=9,
    )
    footer(
        fig,
        "Source: DOPA gis-02, budget year 2564 (BE) - STALE. Presence, not quality or capacity. Not a recommendation.",
    )
    fig.savefig(REVIEW / "education-facilities.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    # 2 education accessibility
    cols = [
        ("primary_school", "to nearest primary-level school"),
        ("secondary_school", "to nearest secondary school"),
        ("kindergarten", "to nearest kindergarten"),
        ("vocational_institution", "to nearest vocational institution"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 14))
    for ax, (cat, label) in zip(axes.ravel(), cols, strict=True):
        im = time_panel(
            ax,
            art,
            f"drive_time_to_nearest_{cat}_min",
            ix,
            iy,
            c,
            prov,
            f"BASELINE_DRIVE_TIME {label} (min)",
        )
    fig.colorbar(
        im, ax=axes, shrink=0.5, label="minutes (BASELINE_DRIVE_TIME, free-flow class speeds)"
    )
    footer(
        fig,
        "Accessibility scale (not good/bad). Stale 2021 facility data; levels derived; excludes traffic/weather/season.",
    )
    fig.savefig(REVIEW / "education-accessibility.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    # 3 healthcare accessibility
    fig, axes = plt.subplots(1, 3, figsize=(18, 8))
    for ax, (cat, label) in zip(
        axes,
        [
            ("primary_health_unit", "primary health unit"),
            ("hospital", "hospital (any government level)"),
            ("higher_level_hospital", "higher-level hospital"),
        ],
        strict=True,
    ):
        im = time_panel(
            ax,
            art,
            f"drive_time_to_nearest_{cat}_min",
            ix,
            iy,
            c,
            prov,
            f"BASELINE_DRIVE_TIME\nto nearest {label} (min)",
        )
    fig.colorbar(im, ax=axes, shrink=0.5, label="minutes (BASELINE_DRIVE_TIME)")
    footer(
        fig,
        "Higher-level hospital DEFERRED: no verified service-level source (all grey). Hospital presence is not emergency capability. Health data 2020 - STALE.",
    )
    fig.savefig(REVIEW / "healthcare-accessibility.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    # 4 road routing QA
    ctx = {
        "CONNECTED_ROAD_WITHIN_500M": 0,
        "CONNECTED_ROAD_500M_TO_1KM": 1,
        "ONLY_ISOLATED_ROAD_FRAGMENT_WITHIN_1KM": 2,
        "NO_ROAD_WITHIN_1KM": 3,
    }
    fig, ax = plt.subplots(figsize=(8, 9))
    cm = ListedColormap(["#4575b4", "#abd9e9", "#fdae61", "#d9d9d9"])
    ax.imshow(
        raster(art["road_access_context"].map(ctx).to_numpy(float), ix, iy),
        origin="lower",
        extent=ext,
        cmap=cm,
        vmin=-0.5,
        vmax=3.5,
        interpolation="nearest",
    )
    major.to_crs(prov.crs).plot(ax=ax, color="black", linewidth=0.3)
    outline(ax, prov)
    shares = (
        (art.groupby("road_access_context")["area_km2"].sum() / art["area_km2"].sum() * 100)
        .round(1)
        .to_dict()
    )
    ax.set_title(
        "Road-network routing QA (OSM extract): cell-centre snap to a routable road\n"
        + "; ".join(f"{k.replace('_', ' ').lower()} {v}%" for k, v in shares.items()),
        fontsize=8,
    )
    from matplotlib.patches import Patch

    ax.legend(
        handles=[Patch(color=cm(i), label=k) for k, i in ctx.items()], fontsize=7, loc="lower left"
    )
    footer(
        fig,
        "Black lines: OSM primary/trunk/secondary. OSM completeness varies; no track/service ways in the extract. Cells with no road within 1 km are unresolved, not 'no access'.",
    )
    fig.savefig(REVIEW / "road-network-routing-qa.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    # 5/6 water & electricity (state maps: every cell has the same evidence state)
    for name, col, note in (
        (
            "water-service-context",
            "water_service_context",
            "PWA service-area polygons were not published: every cell is NON_PWA_OR_UNKNOWN_SERVICE.\nThis does NOT mean no water (wells, municipal and village systems exist). Parcel verification required.",
        ),
        (
            "electricity-context",
            "electricity_service_potential",
            "PEA Power Map has no verified machine-readable endpoint: every cell is NOT_ASSESSED.\nPEA describes it as preliminary planning information; no obligation to serve. Parcel verification required.",
        ),
    ):
        fig, ax = plt.subplots(figsize=(8, 9))
        states = art[col].astype("category")
        ax.imshow(
            raster(states.cat.codes.to_numpy(float), ix, iy),
            origin="lower",
            extent=ext,
            cmap=ListedColormap(["#bdbdbd"]),
            vmin=-1,
            vmax=1,
            interpolation="nearest",
        )
        outline(ax, prov)
        ax.set_title(
            f"{name.replace('-', ' ').title()}: {', '.join(states.cat.categories)} (100% of cells)\n{note}",
            fontsize=8,
        )
        footer(
            fig,
            "Evidence-state map, not a coverage map: grey = no spatial evidence available in M2A.",
        )
        fig.savefig(REVIEW / f"{name}.png", dpi=110, bbox_inches="tight")
        plt.close(fig)
    # 7 completeness
    ed = {
        "ALL_PATHWAYS_ROUTED": 0,
        "PARTIAL_SOME_PATHWAYS_UNREACHABLE": 1,
        "UNRESOLVED_NO_ROAD_ACCESS": 2,
    }
    hc = {
        "HOSPITAL_AND_PRIMARY_UNIT_ROUTED_HIGHER_LEVEL_DEFERRED": 0,
        "PARTIAL": 1,
        "UNRESOLVED_NO_ROAD_ACCESS": 2,
    }
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    cm = ListedColormap(["#3b4cc0", "#f4a582", "#bdbdbd"])
    for ax, (col, mp, title) in zip(
        axes,
        [
            ("education_evidence_completeness", ed, "Education evidence completeness"),
            ("healthcare_evidence_completeness", hc, "Healthcare evidence completeness"),
        ],
        strict=True,
    ):
        ax.imshow(
            raster(art[col].map(mp).to_numpy(float), ix, iy),
            origin="lower",
            extent=ext,
            cmap=cm,
            vmin=-0.5,
            vmax=2.5,
            interpolation="nearest",
        )
        outline(ax, prov)
        sh = (art.groupby(col)["area_km2"].sum() / art["area_km2"].sum() * 100).round(1).to_dict()
        ax.set_title(
            title + "\n" + "; ".join(f"{k.lower()} {v}%" for k, v in sh.items()), fontsize=7
        )
        from matplotlib.patches import Patch

        ax.legend(
            handles=[Patch(color=cm(i), label=k) for k, i in mp.items()],
            fontsize=6,
            loc="lower left",
        )
    footer(
        fig,
        "Completeness of ROUTED EVIDENCE only - not a family or infrastructure score. Water, electricity and telecom are context states, see their own maps.",
    )
    fig.savefig(REVIEW / "family-infrastructure-completeness.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def wq(values: np.ndarray, weights: np.ndarray, qs=(0.1, 0.5, 0.9)):
    m = np.isfinite(values)
    if not m.any():
        return [None] * len(qs)
    v, w = values[m], weights[m]
    o = np.argsort(v)
    cw = np.cumsum(w[o]) / w.sum()
    return [float(v[o][np.searchsorted(cw, q)]) for q in qs]


def stats(art, edu, hl):
    rows = []
    for sc in SCOPES:
        a = art if sc == "AOI" else art[art["majority_pcode"] == sc]
        tot = a["area_km2"].sum()
        for cat in CATS:
            t = a[f"drive_time_to_nearest_{cat}_min"].to_numpy(float)
            p10, p50, p90 = wq(t, a["area_km2"].to_numpy())
            rows.append(
                {
                    "scope": sc,
                    "category": cat,
                    "area_km2": round(tot, 1),
                    "resolved_share_pct": round(
                        float(a.loc[np.isfinite(t), "area_km2"].sum() / tot * 100), 2
                    ),
                    "unresolved_share_pct": round(
                        float(a.loc[~np.isfinite(t), "area_km2"].sum() / tot * 100), 2
                    ),
                    "p10_min": p10,
                    "median_min": p50,
                    "p90_min": p90,
                }
            )
    st = pd.DataFrame(rows)
    st.to_csv(REVIEW / "travel-time-distribution.csv", index=False)
    # sensitivity
    srows = []
    for cat in ("primary_school", "secondary_school", "hospital"):
        for scen, col in (
            ("SLOW", f"drive_time_to_nearest_{cat}_slow_min"),
            ("BASE", f"drive_time_to_nearest_{cat}_min"),
            ("FAST", f"drive_time_to_nearest_{cat}_fast_min"),
        ):
            v = art[col].to_numpy(float)
            p10, p50, p90 = wq(v, art["area_km2"].to_numpy())
            srows.append(
                {
                    "category": cat,
                    "scenario": scen,
                    "median_min": p50,
                    "p90_min": p90,
                    "share_within_30min_pct": round(
                        float(art.loc[v <= 30, "area_km2"].sum() / art["area_km2"].sum() * 100), 2
                    ),
                }
            )
    pd.DataFrame(srows).to_csv(REVIEW / "speed-sensitivity.csv", index=False)
    # province context table
    crow = []
    for sc in SCOPES:
        a = art if sc == "AOI" else art[art["majority_pcode"] == sc]
        tot = a["area_km2"].sum()
        crow.append({"scope": sc, "cells": len(a), "area_km2": round(tot, 1)} | {f"road_{k.lower()}_pct": round(float(a.loc[a["road_access_context"] == k, "area_km2"].sum() / tot * 100), 2) for k in a["road_access_context"].unique()} | {
            "drr_rural_highway_within_1km_pct": round(float(a.loc[a["drr_rural_highway_within_1km"], "area_km2"].sum() / tot * 100), 2),
            "pwa_service_area_pct": round(float(a.loc[a["water_service_context"] == "PWA_SERVICE_AREA", "area_km2"].sum() / tot * 100), 2),
            "electricity_assessed_pct": round(float(a.loc[a["electricity_service_potential"] != "NOT_ASSESSED", "area_km2"].sum() / tot * 100), 2),
            "telecom_covered_pct": None,
            "education_incomplete_pct": round(float(a.loc[a["education_evidence_completeness"] != "ALL_PATHWAYS_ROUTED", "area_km2"].sum() / tot * 100), 2),
            "healthcare_hospital_and_primary_routed_pct": round(float(a.loc[a["healthcare_evidence_completeness"].str.startswith("HOSPITAL_AND"), "area_km2"].sum() / tot * 100), 2),
        })  # fmt: skip
    pd.DataFrame(crow).to_csv(REVIEW / "infrastructure-context-statistics.csv", index=False)
    # facilities per province
    prow = []
    for name, df, col in (("education", edu, "levels"), ("health", hl, "facility_class")):
        for pc in ("TH50", "TH56", "TH57"):
            s = df[df["stated_pcode"] == pc]
            prow.append(
                {
                    "domain": name,
                    "province": PROV_NAMES[pc],
                    "records": len(s),
                    "coordinate_qa_failed": int((s["coordinate_qa_status"] == "FAILED").sum()),
                    "coordinate_qa_flagged": int((s["coordinate_qa_status"] == "FLAGGED").sum()),
                    "types": json.dumps(s[col].value_counts().to_dict(), ensure_ascii=False),
                }
            )
    pd.DataFrame(prow).to_csv(
        REVIEW / "facility-counts-by-province.csv", index=False, encoding="utf-8-sig"
    )
    # pathways within bands (AOI / province, area share)
    brow = []
    for sc in SCOPES:
        a = art if sc == "AOI" else art[art["majority_pcode"] == sc]
        tot = a["area_km2"].sum()
        for b in (15, 30, 60):
            col = f"education_pathways_within_{b}min"
            dist = (a.groupby(col)["area_km2"].sum() / tot * 100).round(2).to_dict()
            brow.append(
                {"scope": sc, "band_min": b, "pathways_reachable_share_pct": json.dumps(dist)}
            )
    pd.DataFrame(brow).to_csv(REVIEW / "education-pathways-distribution.csv", index=False)
    return st


def main() -> int:
    art, ix, iy, c, prov, edu, hl, major = load()
    maps(art, ix, iy, c, prov, edu, hl, major)
    st = stats(art, edu, hl)
    print(st[st.scope == "AOI"].to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
