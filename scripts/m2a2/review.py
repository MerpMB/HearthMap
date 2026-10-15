# ruff: noqa: E501
"""M2A.2 review maps (evidence only; change scales are neutral, not good/bad)."""

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
from matplotlib.colors import BoundaryNorm, ListedColormap, TwoSlopeNorm

REVIEW = Path("outputs/m2a2-review")
PROC = Path("data/processed")
CLS_COL = {
    "PRIMARY_HEALTH_UNIT": "#9ecae1",
    "COMMUNITY_HOSPITAL": "#3182bd",
    "GENERAL_HOSPITAL": "#e6550d",
    "REGIONAL_REFERRAL_HOSPITAL": "#a50f15",
    "UNIVERSITY_HOSPITAL": "#6a51a3",
    "SPECIALISED_HOSPITAL": "#8c6d31",
    "HOSPITAL_UNSPECIFIED_LEVEL": "#636363",
    "OTHER_NON_SERVICE_POINT": "#bdbdbd",
}


def foot(fig, t):
    fig.text(0.01, 0.005, t, fontsize=7, color="#444")


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.set_xticks([])
    ax.set_yticks([])


def main() -> int:
    prov = gpd.read_file(PROC / "m1a" / "boundaries.gpkg", layer="province_boundaries")
    hl = gpd.read_file(PROC / "m2a2" / "facilities.gpkg", layer="health_facilities")
    cit = gpd.read_file(PROC / "m2a" / "facilities.gpkg", layer="health_facilities")
    osm = gpd.read_file(PROC / "m2a1" / "facilities.gpkg", layer="osm_health_current")
    rec = pd.read_csv(REVIEW / "healthcare-source-reconciliation.csv")
    prev = pd.read_parquet("outputs/m2a1/family-infrastructure-evidence.parquet")
    new = pd.read_parquet("outputs/m2a2/family-infrastructure-evidence.parquet")
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

    # 1. source comparison
    fig, ax = plt.subplots(figsize=(8.5, 10))
    outline(ax, prov)
    for k, col in CLS_COL.items():
        g = hl[hl["facility_class"] == k]
        if len(g):
            g.plot(
                ax=ax,
                color=col,
                markersize=4 if k.startswith("PRIMARY") else 22,
                label=f"MoPH 2026 {k.lower()} ({len(g)})",
                alpha=0.85,
            )
    st = rec[rec.pair == "MoPH_update68_2026_vs_CITIZENinfo_2020"]
    legacy_only = set(st[(st.side == "legacy_side") & (st.status == "LEGACY_ONLY")]["rec_id"])
    lo = cit[cit["facility_id"].isin(legacy_only)]
    if len(lo):
        lo.plot(
            ax=ax,
            color="black",
            marker="x",
            markersize=14,
            label=f"CITIZENinfo 2020 only - no MoPH counterpart ({len(lo)})",
        )
    so = rec[
        (rec.pair == "OSM_2026_vs_MoPH_update68_2026")
        & (rec.side == "current_side")
        & (rec.status == "CURRENT_ONLY")
    ]
    oo = osm[osm["rec_id"].isin(so["rec_id"])]
    if len(oo):
        oo.plot(
            ax=ax,
            facecolor="none",
            edgecolor="#d95f02",
            marker="o",
            markersize=26,
            label=f"OSM 2026 only - no MoPH counterpart ({len(oo)})",
        )
    ax.legend(fontsize=7, loc="lower left")
    ax.set_title(
        "Healthcare source comparison: MoPH public layer (2026, primary) vs CITIZENinfo (2020) and OSM (2026)",
        fontsize=9,
    )
    foot(
        fig,
        "Class = MoPH source type/level field. Not-matched is not closure or opening. No emergency/ICU/specialist capability is stated or assigned.",
    )
    fig.savefig(REVIEW / "healthcare-source-comparison.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # 2. accessibility change + higher-level map
    def delta(ax, cat, title):
        d = new[f"drive_time_to_nearest_{cat}_min"].to_numpy(float) - prev[
            f"drive_time_to_nearest_{cat}_min"
        ].to_numpy(float)
        ax.imshow(
            raster(np.where(np.isnan(d), 1.0, np.nan)),
            origin="lower",
            extent=ext,
            cmap=ListedColormap(["#d0d0d0"]),
            interpolation="nearest",
        )
        lim = max(3.0, float(np.nanpercentile(np.abs(d), 99))) if np.isfinite(d).any() else 3.0
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
            f"{title}\nchanged cells {np.nansum(np.abs(d) > 1e-9) / max(1, np.isfinite(d).sum()) * 100:.1f}%",
            fontsize=8,
        )
        return im

    fig, axes = plt.subplots(1, 3, figsize=(19, 8))
    im = delta(axes[0], "hospital", "Change: drive time to nearest hospital (min)")
    delta(axes[1], "primary_health_unit", "Change: drive time to nearest primary health unit (min)")
    bins = [0, 15, 30, 60, 120, 240]
    cmap = plt.get_cmap("viridis", len(bins))
    v = new["drive_time_to_nearest_higher_level_hospital_min"].to_numpy(float)
    axes[2].imshow(
        raster(np.where(np.isnan(v), 1.0, np.nan)),
        origin="lower",
        extent=ext,
        cmap=ListedColormap(["#d0d0d0"]),
        interpolation="nearest",
    )
    axes[2].imshow(
        raster(np.clip(v, 0, 239)),
        origin="lower",
        extent=ext,
        cmap=cmap,
        norm=BoundaryNorm(bins, cmap.N, extend="max"),
        interpolation="nearest",
    )
    outline(axes[2], prov)
    axes[2].set_title(
        f"Drive time to nearest HIGHER-LEVEL hospital (min; source type = regional hospital)\nunresolved (grey) {np.isnan(v).mean() * 100:.1f}% of cells",
        fontsize=8,
    )
    fig.colorbar(
        im,
        ax=axes[:2],
        shrink=0.5,
        label="new - old (min): purple longer, orange shorter (neutral)",
    )
    foot(
        fig,
        "Same frozen routing. Higher-level = source type = regional hospital (2 hospitals); this is a source classification, not a service guarantee.",
    )
    fig.savefig(REVIEW / "healthcare-accessibility-change.png", dpi=105, bbox_inches="tight")
    plt.close(fig)

    # 3. coordinate conflicts
    fig, ax = plt.subplots(figsize=(8.5, 10))
    outline(ax, prov)
    conf = hl[hl["geometry_attribute_conflict"]]
    conf.plot(
        ax=ax,
        color="#d7191c",
        markersize=10,
        label=f"MoPH geometry vs lat/lon attribute > 100 m ({len(conf)})",
    )
    cs = st[st.side == "current_side"]
    cc = hl[hl["facility_id"].isin(cs[cs.status == "CONFLICT"]["rec_id"])]
    cc.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#7b3294",
        markersize=40,
        label=f"same name, location differs from CITIZENinfo 2020 ({len(cc)})",
    )
    ax.legend(fontsize=8, loc="lower left")
    ax.set_title(
        "Facility coordinate conflicts (flagged; layer geometry used, attribute coordinates kept)",
        fontsize=9,
    )
    foot(
        fig,
        "Geometry agrees better with an independent source (median 36 m vs 363 m among conflicting records), so it is used; no conflict is silently resolved.",
    )
    fig.savefig(REVIEW / "facility-coordinate-conflicts.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    # 4. classes / freshness
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    hl["facility_class"].value_counts().sort_values().plot(kind="barh", ax=axes[0], color="#6baed6")
    axes[0].set_title("Facility class (source typecode/level)", fontsize=9)
    hl["class_basis"].value_counts().sort_values().plot(kind="barh", ax=axes[1], color="#74c476")
    axes[1].set_title("Class basis", fontsize=9)
    hl["source_record_date"].str[:4].value_counts().sort_index().plot(
        kind="bar", ax=axes[2], color="#fd8d3c", rot=0
    )
    axes[2].set_title("Record date (Last_update_infile) by year", fontsize=9)
    foot(
        fig,
        "Layer last edited 2026-09-09 but most records carry 2023 record dates: location/class are as current as the source, not newer.",
    )
    fig.savefig(REVIEW / "healthcare-classes-and-freshness.png", dpi=110, bbox_inches="tight")
    plt.close(fig)

    # 5. source state board
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.axis("off")
    rows = [
        [
            "MOE current school register",
            "SOURCE_EXISTS_AGENT_BLOCKED",
            "manual import ready (data/manual/moe-register-current)",
            "education stays DOPA 2021 + OBEC 2020 classes",
        ],
        [
            "MoPH HCODE",
            "SOURCE_EXISTS_AGENT_BLOCKED",
            "manual import ready; no bot-challenge bypass",
            "not needed for location/class",
        ],
        [
            "MoPH public hospital layer (update68)",
            "SOURCE_EXISTS_AGENT_ACCESSIBLE",
            "acquired automatically",
            "PRIMARY health layer (2026)",
        ],
        ["MoPH update69 / CITIZENinfo / OSM", "ACCESSIBLE", "acquired", "cross-checks"],
    ]
    t = ax.table(
        cellText=rows,
        colLabels=["source", "state", "acquisition path", "effect"],
        loc="center",
        cellLoc="left",
    )
    t.auto_set_font_size(False)
    t.set_fontsize(8)
    t.scale(1, 2.2)
    ax.set_title("M2A.2 source-state board", fontsize=10)
    fig.savefig(REVIEW / "m2a2-source-state-board.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
