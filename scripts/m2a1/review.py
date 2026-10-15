# ruff: noqa: E501
"""M2A.1 review maps. Accessibility change scales are diverging-neutral (not good/bad); verified data only."""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import TwoSlopeNorm

REVIEW = Path("outputs/m2a1-review")
PROC = Path("data/processed")
COL = {
    "MATCHED": "#2b83ba",
    "CONFLICT": "#d7191c",
    "POSSIBLE_MATCH": "#fdae61",
    "CURRENT_ONLY": "#7b3294",
    "LEGACY_ONLY": "#555555",
}


def foot(fig, t):
    fig.text(0.01, 0.005, t, fontsize=7, color="#444")


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> int:
    prov = gpd.read_file(PROC / "m1a" / "boundaries.gpkg", layer="province_boundaries")
    edu = gpd.read_file(PROC / "m2a1" / "facilities.gpkg", layer="education_facilities")
    hl = gpd.read_file(PROC / "m2a1" / "facilities.gpkg", layer="health_facilities")
    obec_only = gpd.read_file(PROC / "m2a1" / "facilities.gpkg", layer="education_obec_only")
    rec = pd.read_csv(REVIEW / "education-source-reconciliation.csv")
    rec_h = pd.read_csv(REVIEW / "healthcare-source-reconciliation.csv")
    old = pd.read_parquet("outputs/m2a/family-infrastructure-evidence.parquet")
    new = pd.read_parquet("outputs/m2a1/family-infrastructure-evidence.parquet")
    grid = (
        gpd.read_file(PROC / "m1a" / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    c = shapely.get_coordinates(grid.geometry.centroid)
    ix = np.round((c[:, 0] - c[:, 0].min()) / 500).astype(int)
    iy = np.round((c[:, 1] - c[:, 1].min()) / 500).astype(int)
    ext = (c[:, 0].min() - 250, c[:, 0].max() + 250, c[:, 1].min() - 250, c[:, 1].max() + 250)

    def raster(v):
        a = np.full((iy.max() + 1, ix.max() + 1), np.nan)
        a[iy, ix] = v
        return a

    # 1. education source comparison
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [1.3, 1]})
    ax = axes[0]
    outline(ax, prov)
    st = rec[rec.pair == "DOPA_2021_vs_OBEC_2020"]
    cs = st[st.side == "current_side"].set_index("rec_id")["status"]
    schools = edu[edu["facility_id"].isin(cs.index)].copy()
    schools["status"] = schools["facility_id"].map(cs)
    for s_, g in schools.groupby("status"):
        g.plot(
            ax=ax,
            color=COL[s_],
            markersize=4,
            label=f"DOPA school vs OBEC: {s_.lower()} ({len(g)})",
            alpha=0.8,
        )
    if len(obec_only):
        obec_only.plot(
            ax=ax,
            color=COL["LEGACY_ONLY"],
            marker="x",
            markersize=10,
            label=f"OBEC only (no DOPA counterpart) ({len(obec_only)})",
        )
    ax.legend(fontsize=7, loc="lower left")
    ax.set_title(
        "Education source comparison (both sources are STALE: DOPA 2021, OBEC 2020)", fontsize=9
    )
    ax = axes[1]
    sch = edu[edu["kind"] == "SCHOOL"]
    tab = (
        sch.groupby(
            [
                "stated_pcode",
                sch["normalization_method"]
                .str.startswith("AUTHORITATIVE")
                .map({True: "authoritative class range", False: "derived from name / sub-code"}),
            ]
        )
        .size()
        .unstack(fill_value=0)
    )
    tab.index = [
        {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}[i] for i in tab.index
    ]
    tab.plot(kind="bar", stacked=True, ax=ax, color=["#2b83ba", "#bdbdbd"], rot=0)
    ax.set_title("School level basis by province (M2A baseline: 100% derived)", fontsize=9)
    ax.set_ylabel("schools")
    foot(
        fig,
        "Matching = identical name (generic prefix ignored) within 300 m; nothing fuzzy-merged. Not-matched != closed or new.",
    )
    fig.savefig(REVIEW / "education-source-comparison.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # 2. healthcare source comparison
    fig, ax = plt.subplots(figsize=(8.5, 10))
    outline(ax, prov)
    hl_ok = hl[hl["coordinate_qa_status"] != "FAILED"]
    hl_ok.plot(
        ax=ax,
        color="#2b83ba",
        markersize=6,
        label=f"CITIZENinfo 2020 facilities ({len(hl_ok)})",
        alpha=0.7,
    )
    cs_h = rec_h[rec_h.side == "current_side"].set_index("rec_id")["status"]
    osm_h = gpd.read_file(PROC / "m2a1" / "facilities.gpkg", layer="osm_health_current")
    osm_h["status"] = osm_h["rec_id"].map(cs_h).fillna("UNNAMED_NOT_COMPARED")
    for s_, g in osm_h.groupby("status"):
        g.plot(
            ax=ax,
            color=COL.get(s_, "#999999"),
            marker="^",
            markersize=14,
            label=f"OSM 2026 vs CITIZENinfo: {s_.lower()} ({len(g)})",
            alpha=0.85,
        )
    foot(
        fig,
        "Hospital level: PARTIALLY_ASSESSED (HCODE not accessible). OSM current-only means a current object with no stale-register counterpart, not an official new facility.",
    )
    ax.set_title(
        "Healthcare source comparison: CITIZENinfo 2020 (primary, stale) vs OSM 2026 (validation)",
        fontsize=9,
    )
    ax.legend(fontsize=8, loc="lower left")
    fig.savefig(REVIEW / "healthcare-source-comparison.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # 3/4. accessibility change
    def delta_panel(ax, cat, title):
        d = new[f"drive_time_to_nearest_{cat}_min"].to_numpy(float) - old[
            f"drive_time_to_nearest_{cat}_min"
        ].to_numpy(float)
        ax.imshow(
            raster(np.where(np.isnan(d), 1.0, np.nan)),
            origin="lower",
            extent=ext,
            cmap=matplotlib.colors.ListedColormap(["#d0d0d0"]),
            interpolation="nearest",
        )
        lim = max(5.0, float(np.nanpercentile(np.abs(d), 99))) if np.isfinite(d).any() else 5.0
        im = ax.imshow(
            raster(d),
            origin="lower",
            extent=ext,
            cmap="PuOr",
            norm=TwoSlopeNorm(0, -lim, lim),
            interpolation="nearest",
        )
        outline(ax, prov)
        ax.set_title(
            f"{title}\nchanged cells {np.nansum(np.abs(d) > 1e-9) / max(1, np.isfinite(d).sum()) * 100:.1f}% of cells resolved in both",
            fontsize=8,
        )
        return im

    fig, axes = plt.subplots(1, 3, figsize=(19, 8))
    for ax, (cat, t) in zip(
        axes,
        [
            ("primary_school", "primary school"),
            ("secondary_school", "secondary school"),
            ("kindergarten", "kindergarten"),
        ],
        strict=True,
    ):
        im = delta_panel(ax, cat, f"Change in BASELINE_DRIVE_TIME to nearest {t} (min)")
    fig.colorbar(
        im,
        ax=axes,
        shrink=0.5,
        label="new - old (min): purple = longer, orange = shorter (neutral; not quality)",
    )
    foot(
        fig,
        "Same routing network and speeds (frozen). Change comes only from authoritative level reclassification of the same facility set.",
    )
    fig.savefig(REVIEW / "education-accessibility-change.png", dpi=105, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 8))
    for ax, (cat, t) in zip(
        axes,
        [("primary_health_unit", "primary health unit"), ("hospital", "hospital")],
        strict=True,
    ):
        im = delta_panel(ax, cat, f"Change in BASELINE_DRIVE_TIME to nearest {t} (min)")
    fig.colorbar(im, ax=axes, shrink=0.5, label="new - old (min)")
    foot(
        fig,
        "No change by construction: the primary health layer (CITIZENinfo 2020) was not replaced - no current accessible MoPH source.",
    )
    fig.savefig(REVIEW / "healthcare-accessibility-change.png", dpi=105, bbox_inches="tight")
    plt.close(fig)

    # 5. coordinate conflicts
    fig, ax = plt.subplots(figsize=(9, 10))
    outline(ax, prov)
    conf = edu[edu["obec_coordinate_conflict"]]
    ob = obec_only  # noqa: F841
    conf.plot(
        ax=ax,
        color=COL["CONFLICT"],
        markersize=10,
        label=f"DOPA school with OBEC same-name coordinates >300 m apart ({len(conf)})",
    )
    failed = edu[edu["coordinate_qa_status"] == "FAILED"]
    failed.plot(
        ax=ax,
        color="black",
        marker="x",
        markersize=12,
        label=f"DOPA coordinate-QA FAILED ({len(failed)})",
    )
    ax.legend(fontsize=8, loc="lower left")
    ax.set_title(
        "Facility coordinate conflicts and QA failures (flagged, never silently resolved)",
        fontsize=9,
    )
    foot(
        fig,
        "No coordinate was selected between sources: routing uses the primary-layer coordinate; the conflict distance is stored in obec_coordinate_difference_m.",
    )
    fig.savefig(REVIEW / "facility-coordinate-conflicts.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # 6. completeness
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    ec = (
        edu.groupby(edu["normalization_method"].str.replace("DERIVED_", "derived: ", regex=False))
        .size()
        .sort_values()
    )
    ec.plot(kind="barh", ax=axes[0], color="#6baed6")
    axes[0].set_title("Education normalisation method, all institutions", fontsize=9)
    a = pd.DataFrame(
        {
            "old": old["education_evidence_completeness"].value_counts(),
            "new": new["education_evidence_completeness"].value_counts(),
        }
    )
    a.plot(kind="bar", ax=axes[1], rot=10, color=["#bdbdbd", "#2b83ba"])
    axes[1].set_title("Education evidence completeness (cells)", fontsize=9)
    foot(
        fig,
        "Completeness of routed evidence only; hospital level PARTIALLY_ASSESSED; electricity NOT_ASSESSED; water NON_PWA_OR_UNKNOWN; telecom DEFERRED.",
    )
    fig.savefig(REVIEW / "m2a1-completeness.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
