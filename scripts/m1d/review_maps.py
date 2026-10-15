# ruff: noqa: E501
"""M1D review maps (outputs/m1d-review/). Verified data only; neutral palette, no green."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a1"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import PROCESSED
from plotting import clean_axes, grid_image, save, scalebar

OUT = Path("outputs/m1d")
REVIEW = Path("outputs/m1d-review")
GPKG = OUT / "seismic-evidence.gpkg"
TAG = (
    "HearthMap M1D seismic evidence - PROVISIONAL, experimental context; not a hazard model, "
    "not a score; ground response NOT assessed; absence of faults/events != earthquake-safe."
)
SRC = "DMR active-fault traces, DMR model intensity zones, DMR/TMD/USGS earthquake records"
S_NAMES = [
    "NO_MAJOR_SEISMIC_CONCERN_DETECTED",
    "REQUIRES_SEISMIC_VERIFICATION",
    "STRONG_SEISMIC_SCREENING_CONCERN",
    "UNRESOLVED",
]
S_COL = ["#e0e0e0", "#fee391", "#cc4c02", "#bcbddc"]
HYDRO = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
MMI_COL = {"IV": "#f7f7f7", "V": "#d9d9d9", "VI": "#969696", "VII": "#525252", "I-III": "#ffffff"}


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.set_xlabel("")
    ax.set_ylabel("")
    scalebar(ax)


def cat(ax, grid, codes, colors, labels, areas, title, legend=True):
    arr, ext = grid_image(grid, codes)
    cmap = ListedColormap(colors)
    ax.imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, len(colors)), cmap.N),
        interpolation="nearest",
    )
    clean_axes(ax, title)
    if legend:
        ax.legend(
            handles=[
                Patch(facecolor=c, edgecolor="#777", label=f"{lab} ({a:,.0f} km2)")
                for c, lab, a in zip(colors, labels, areas, strict=True)
            ],
            fontsize=6.0,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.01),
        )


def main() -> int:
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    ev = pd.read_parquet(OUT / "seismic-evidence.parquet")
    dg = pd.read_parquet(OUT / "hydro-seismic-diagnostic-cells.parquet")
    area = ev["clipped_area_km2"].to_numpy()
    faults = gpd.read_file(GPKG, layer="active_fault_traces_near_aoi")
    zones = gpd.read_file(GPKG, layer="intensity_zones_clipped_to_aoi")
    events = gpd.read_file(GPKG, layer="historical_events_within_100km")
    state = ev["seismic_screening_interpretation"]

    # ---- 1. active-fault context
    fig, axes = plt.subplots(1, 2, figsize=(16, 9.5))
    d = ev["fault_nearest_distance_km"].where(ev["fault_nearest_distance_km"] <= 50).to_numpy()
    arr, ext = grid_image(grid, d)
    im = axes[0].imshow(
        arr, extent=ext, origin="lower", cmap="Greys_r", vmin=0, vmax=50, interpolation="nearest"
    )
    clean_axes(
        axes[0], "Distance to nearest mapped DMR active-fault trace (descriptive context, km)"
    )
    plt.colorbar(
        im, ax=axes[0], shrink=0.6, label="km (blank > 50 km); distance is NOT a risk score"
    )
    zn = sorted(faults["F_ZONE_E"].unique())
    cmap = plt.get_cmap("tab20")
    for i, z in enumerate(zn):
        faults[faults["F_ZONE_E"] == z].plot(ax=axes[1], color=cmap(i % 20), linewidth=1.1)
    clean_axes(axes[1], "DMR active-fault traces by fault group (within 100 km of the AOI)")
    axes[1].legend(
        handles=[Patch(color=cmap(i % 20), label=z) for i, z in enumerate(zn)],
        fontsize=6,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=4,
    )
    for ax in axes:
        outline(ax, prov)
    save(
        fig,
        REVIEW / "active-fault-context.png",
        "DMR THA_DMR_ZONE_ACTIVEFAULT_WMS (640 traces)",
        TAG,
    )

    # ---- 2. earthquake intensity context
    fig, axes = plt.subplots(1, 2, figsize=(16, 9.5))
    cls = ["IV", "V", "VI", "VII"]
    for c in cls:
        sub = zones[zones["INTENSITY"] == c]
        if len(sub):
            sub.plot(ax=axes[0], color=MMI_COL[c], edgecolor="none")
    clean_axes(axes[0], "DMR model intensity zones (MMI classes), clipped to the AOI")
    cl_area = {c: float(zones[zones["INTENSITY"] == c].area.sum() / 1e6) for c in cls}
    axes[0].legend(
        handles=[
            Patch(facecolor=MMI_COL[c], edgecolor="#777", label=f"{c} ({cl_area[c]:,.0f} km2)")
            for c in cls
        ],
        fontsize=7,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=4,
    )
    f7 = ev["shaking_classVII_fraction"].where(ev["shaking_classVII_fraction"] > 0).to_numpy()
    arr, ext = grid_image(grid, f7)
    im = axes[1].imshow(
        arr, extent=ext, origin="lower", cmap="Greys", vmin=0, vmax=1, interpolation="nearest"
    )
    clean_axes(
        axes[1], "Share of each cell inside intensity zone VII (zone methodology undocumented)"
    )
    plt.colorbar(im, ax=axes[1], shrink=0.6, label="cell share in zone VII")
    for ax in axes:
        outline(ax, prov)
    save(
        fig,
        REVIEW / "earthquake-intensity-context.png",
        "DMR EQ_ZONE (427 polygons; 'model program', no scenario/return period)",
        TAG,
    )

    # ---- 3. historical seismicity
    fig, ax = plt.subplots(figsize=(10, 10))
    prov.boundary.plot(ax=ax, color="black", linewidth=0.7)
    marks = {
        "geohazard-events-dmr": ("o", "#d95f02", "DMR inventory (M>=3, 1994-2025)"),
        "usgs": ("^", "#4575b4", "USGS ComCat (M>=3, 1912-2026)"),
        "tmd": ("s", "#525252", "TMD felt-event list (1930-2026)"),
    }
    for cat_name, (mk, col, lab) in {
        "dmr": marks["geohazard-events-dmr"],
        "usgs": marks["usgs"],
        "tmd": marks["tmd"],
    }.items():
        sub = events[events["catalog"] == cat_name]
        ax.scatter(
            sub.geometry.x,
            sub.geometry.y,
            s=np.clip((sub["magnitude"] - 2) ** 2.4 * 3, 4, 220),
            marker=mk,
            facecolors="none",
            edgecolors=col,
            linewidths=0.9,
            label=f"{lab}: {len(sub)}",
        )
    ax.legend(fontsize=7, loc="lower left")
    clean_axes(
        ax,
        "Historical earthquake records within 100 km of the AOI (marker size ~ magnitude; sources not merged)",
    )
    ax.set_xlim(*ax.get_xlim())
    scalebar(ax)
    save(fig, REVIEW / "historical-seismicity.png", SRC, TAG)

    # ---- 4. seismic screening
    fig, axes = plt.subplots(1, 2, figsize=(16, 9.5))
    code = state.map({s: i for i, s in enumerate(S_NAMES)}).to_numpy(float)
    cat(
        axes[0],
        grid,
        code,
        S_COL,
        S_NAMES,
        [float(area[code == i].sum()) for i in range(4)],
        "Seismic screening interpretation v0.1 (experimental, not selected)",
    )
    fam = {"fault_tier": 0, "shaking_tier": 1, "history_tier": 2}
    tiers = np.zeros(len(ev))
    for f in fam:
        tiers += (ev[f] == "STRONG_TIER").to_numpy().astype(float)
    cat(
        axes[1],
        grid,
        tiers,
        ["#f0f0f0", "#fee391", "#ec7014", "#662506"],
        [
            "no strong-tier family",
            "1 family at strong tier",
            "2 families",
            "3 families (= strong concern)",
        ],
        [float(area[tiers == i].sum()) for i in range(4)],
        "How many evidence families reach their strong tier (fault <= 5 km, zone VII >= 50%, M>=5 event <= 25 km)",
    )
    for ax in axes:
        outline(ax, prov)
    save(fig, REVIEW / "seismic-screening.png", SRC, TAG)

    # ---- 5. hydrogeomorphic vs seismic
    hyd, sei = dg["hydro_regional_search_status"], dg["seismic_screening_interpretation"]
    fav = hyd == "NO_MAJOR_CONCERN_DETECTED"
    sm = sei.isin(["REQUIRES_SEISMIC_VERIFICATION", "STRONG_SEISMIC_SCREENING_CONCERN"])
    hc = hyd.isin(["STRONG_REGIONAL_CONCERN", "REGIONAL_DEPRIORITIZE"])
    sn = sei == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"
    code = np.select([fav & sm, hc & sn, fav & sn, hc & sm], [1, 2, 3, 4], 0).astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(17, 9.5), gridspec_kw={"width_ratios": [1.3, 1]})
    cat(
        axes[0],
        grid,
        code,
        ["#f0f0f0", "#d95f02", "#4575b4", "#bdbdbd", "#525252"],
        [
            "other combinations",
            "hydro: no major concern / seismic: verify or strong",
            "hydro: strong or deprioritize / seismic: none detected",
            "both: no major concern detected (NOT safe)",
            "both: concern",
        ],
        [float(area[code == i].sum()) for i in range(5)],
        "Hydrogeomorphic (BALANCED + FLOOD_ANY_SOURCE, provisional) vs seismic screening",
    )
    outline(axes[0], prov)
    ct = pd.read_csv(REVIEW / "hydro-vs-seismic-crosstab.csv")
    ct = (
        ct[(ct["scope"] == "AOI") & (ct["stratum"] == "ALL")]
        .pivot_table(index="hydro_status", columns="seismic_state", values="area_km2")
        .reindex(index=HYDRO, columns=S_NAMES)
        .fillna(0)
    )
    bottom = np.zeros(len(HYDRO))
    for s, c in zip(S_NAMES, S_COL, strict=True):
        axes[1].barh(
            range(len(HYDRO)), ct[s].to_numpy(), left=bottom, color=c, edgecolor="#777", label=s
        )
        bottom += ct[s].to_numpy()
    axes[1].set_yticks(range(len(HYDRO)), [h.replace("_", " ").lower() for h in HYDRO], fontsize=7)
    axes[1].set_xlabel("area (km2)", fontsize=8)
    axes[1].legend(fontsize=6.5, loc="lower right")
    axes[1].set_title(
        "Cross-tab (AOI): hydrogeomorphic status x seismic state (no combined score)", fontsize=8
    )
    save(
        fig,
        REVIEW / "hydrogeomorphic-vs-seismic.png",
        SRC + "; provisional defaults, production_truth = false",
        TAG,
    )

    # ---- 6. residential-lowland context
    low = pd.read_csv(REVIEW / "seismic-lowland-context.csv")
    strata = ["LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15", "ALL"]
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [1.3, 1]})
    strat = dg["slope_stratum_reporting_only"].to_numpy()
    code = np.zeros(len(ev))
    code = np.where(
        strat == "LOW_SLOPE_LE_5",
        state.map({s: i + 1 for i, s in enumerate(S_NAMES)}).to_numpy(float),
        0,
    )
    cat(
        axes[0],
        grid,
        code,
        ["#f0f0f0", "#bdbdbd", "#fee391", "#cc4c02", "#bcbddc"],
        [
            "not low-slope (> 5 deg)",
            "low-slope: no major seismic concern detected",
            "low-slope: requires verification",
            "low-slope: strong screening concern",
            "low-slope: unresolved",
        ],
        [float(area[code == i].sum()) for i in range(5)],
        "Seismic screening in low-slope (DSM p90 <= 5 deg) cells - reporting stratum only, not suitability",
    )
    outline(axes[0], prov)
    ax = axes[1]
    x = np.arange(len(strata))
    bottom = np.zeros(len(strata))
    for s, c in zip(S_NAMES[:3], S_COL[:3], strict=True):
        v = (
            np.array(
                [
                    low[(low["stratum"] == st) & (low["state"] == s)]["share_of_area"].iloc[0]
                    for st in strata
                ]
            )
            * 100
        )
        ax.bar(x, v, bottom=bottom, color=c, edgecolor="#777", label=s)
        bottom += v
    ax.set_xticks(x, strata, fontsize=7)
    ax.set_ylabel("% of stratum area", fontsize=8)
    ax.legend(fontsize=6.5)
    ax.set_title(
        "Seismic screening by slope stratum (stratification only; terrain never changes the state)",
        fontsize=8,
    )
    save(fig, REVIEW / "seismic-lowland-context.png", SRC, TAG)

    sizes = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.suffix == ".png"
    }
    (REVIEW / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
