# ruff: noqa: E501
"""M1E review maps (outputs/m1e-review/). Qualitative palettes only: the action categories are
different kinds of decision consequence, so there is no green-to-red 'safe to danger' scale."""

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

OUT = Path("outputs/m1e")
REVIEW = Path("outputs/m1e-review")
TAG = (
    "HearthMap M1E natural hazard integration - PROVISIONAL regional screening; actions are "
    "different kinds of consequence, not one safe-to-danger scale; ground response NOT assessed."
)
SRC = "Selected provisional hydrogeomorphic defaults (BALANCED + FLOOD_ANY_SOURCE) + experimental seismic evidence"
SEARCH = [
    "CONTINUE_SEARCH",
    "CONTINUE_SEARCH_WITH_AVOIDANCE_CAUTION",
    "DEPRIORITIZE_REGION",
    "UNRESOLVED",
]
SEARCH_COL = ["#9ecae1", "#fdae6b", "#756bb1", "#a6a6a6"]
STATES = [
    "NO_MAJOR_ACTION_TRIGGERED",
    "VERIFY_SITE",
    "ENGINEERING_MITIGATION_REQUIRED",
    "STRONG_AVOIDANCE_SIGNAL",
    "MULTIPLE_ACTIONS",
    "UNRESOLVED",
]
STATE_COL = ["#f7f7f7", "#fee391", "#74a9cf", "#756bb1", "#252525", "#a6a6a6"]
NAMES = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
    ax.set_xlabel("")
    ax.set_ylabel("")
    scalebar(ax)


def cat(ax, grid, codes, colors, labels, areas, title):
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
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777", label=f"{lab} ({a:,.0f} km2)")
            for c, lab, a in zip(colors, labels, areas, strict=True)
        ],
        fontsize=6.0,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
    )


def code_of(series, order):
    return series.map({k: i for i, k in enumerate(order)}).to_numpy(float)


def prov_bars(ax, a, mask_fn, title, color):
    vals = []
    for p in NAMES:
        m = (a["majority_pcode"] == p).to_numpy()
        vals.append(
            100
            * float(
                a["clipped_area_km2"].to_numpy()[mask_fn & m].sum()
                / a["clipped_area_km2"].to_numpy()[m].sum()
            )
        )
    ax.bar(list(NAMES.values()), vals, color=color, edgecolor="#555")
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v:.0f}%", ha="center", fontsize=8)
    ax.set_ylabel("% of province area", fontsize=8)
    ax.set_title(title, fontsize=8)


def main() -> int:
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    a = pd.read_parquet(OUT / "natural-hazard-actions.parquet")
    area = a["clipped_area_km2"].to_numpy()

    # 1. search action under three integration policies
    fig, axes = plt.subplots(1, 3, figsize=(21, 9.5))
    for ax, (col, ttl) in zip(
        axes,
        (
            ("regional_search_action", "BALANCED_ACTION (reference mapping, not selected)"),
            ("regional_search_action__avoidance_first", "AVOIDANCE_FIRST"),
            ("regional_search_action__verification_first", "VERIFICATION_FIRST"),
        ),
        strict=True,
    ):
        c = code_of(a[col], SEARCH)
        cat(
            ax,
            grid,
            c,
            SEARCH_COL,
            SEARCH,
            [float(area[c == i].sum()) for i in range(4)],
            f"Regional search action - {ttl}",
        )
        outline(ax, prov)
    save(
        fig,
        REVIEW / "natural-hazard-search-action.png",
        SRC + "; seismic never enters the search action",
        TAG,
    )

    # 2. verification burden
    fig, axes = plt.subplots(1, 2, figsize=(15, 9), gridspec_kw={"width_ratios": [1.4, 1]})
    k = a["site_verification_burden_count"].to_numpy(float)
    cols = ["#f0f0f0", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    cat(
        axes[0],
        grid,
        np.clip(k, 0, 4),
        cols,
        ["0 families", "1 family", "2 families", "3 families", "4 families"],
        [float(area[np.clip(k, 0, 4) == i].sum()) for i in range(5)],
        "Number of hazard families that call for site verification (burden of information, not severity)",
    )
    outline(axes[0], prov)
    prov_bars(
        axes[1],
        a,
        (a["site_verification_action"] == "VERIFY_SITE_REQUIRED").to_numpy(),
        "Area requiring site verification (any family)",
        "#6baed6",
    )
    save(fig, REVIEW / "verification-burden.png", SRC, TAG)

    # 3. engineering mitigation
    fig, axes = plt.subplots(1, 2, figsize=(15, 9), gridspec_kw={"width_ratios": [1.4, 1]})
    m = (a["engineering_mitigation_action"] == "SEISMIC_DESIGN_REQUIRED").to_numpy().astype(float)
    cat(
        axes[0],
        grid,
        m,
        ["#f0f0f0", "#1d91c0"],
        [
            "no mitigation action triggered",
            "seismic design required (regional shaking zone VII dominant)",
        ],
        [float(area[m == 0].sum()), float(area[m == 1].sum())],
        "Engineering mitigation: seismic design matters here - NOT an instruction to leave the search area",
    )
    outline(axes[0], prov)
    prov_bars(axes[1], a, m.astype(bool), "Area where seismic design is required", "#1d91c0")
    save(fig, REVIEW / "engineering-mitigation.png", SRC, TAG)

    # 4. hydro vs seismic
    hy, se = a["hydro_status"], a["seismic_status"]
    strong = se == "STRONG_SEISMIC_SCREENING_CONCERN"
    code = np.select(
        [
            (hy == "NO_MAJOR_CONCERN_DETECTED") & strong,
            (hy == "REQUIRES_VERIFICATION") & strong,
            hy.isin(["STRONG_REGIONAL_CONCERN", "REGIONAL_DEPRIORITIZE"]) & strong,
            (hy == "UNRESOLVED") & strong,
            (hy == "NO_MAJOR_CONCERN_DETECTED") & (se == "REQUIRES_SEISMIC_VERIFICATION"),
            (hy == "NO_MAJOR_CONCERN_DETECTED") & (se == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"),
            (hy == "REGIONAL_DEPRIORITIZE") & (se == "NO_MAJOR_SEISMIC_CONCERN_DETECTED"),
        ],
        [1, 2, 3, 4, 5, 6, 7],
        0,
    ).astype(float)
    labs = [
        "other combinations",
        "hydro favourable + seismic strong",
        "hydro verification + seismic strong",
        "hydro strong/deprioritize + seismic strong",
        "hydro unresolved + seismic strong",
        "hydro favourable + seismic verification",
        "both: no major concern detected (NOT safe)",
        "hydro deprioritize + seismic none detected",
    ]
    cl = ["#f0f0f0", "#1d91c0", "#a6bddb", "#756bb1", "#a6a6a6", "#ffeda0", "#d9d9d9", "#fdae6b"]
    fig, ax = plt.subplots(figsize=(10.5, 10))
    cat(
        ax,
        grid,
        code,
        cl,
        labs,
        [float(area[code == i].sum()) for i in range(8)],
        "Hydrogeomorphic vs seismic: the two hazard families stay distinct (no combined score)",
    )
    outline(ax, prov)
    save(fig, REVIEW / "hydro-vs-seismic.png", SRC, TAG)

    # 5. multiple actions / integrated state
    fig, axes = plt.subplots(1, 2, figsize=(17, 9.5), gridspec_kw={"width_ratios": [1.4, 1]})
    c = code_of(a["natural_hazard_integrated_state"], STATES)
    cat(
        axes[0],
        grid,
        c,
        STATE_COL,
        STATES,
        [float(area[c == i].sum()) for i in range(6)],
        "Integrated action state (dimension-preserving; precedence documented, nothing averaged)",
    )
    outline(axes[0], prov)
    bottom = np.zeros(3)
    for s, col in zip(STATES, STATE_COL, strict=True):
        v = np.array(
            [
                100
                * float(
                    area[
                        (a["natural_hazard_integrated_state"] == s).to_numpy()
                        & (a["majority_pcode"] == p).to_numpy()
                    ].sum()
                    / area[(a["majority_pcode"] == p).to_numpy()].sum()
                )
                for p in NAMES
            ]
        )
        axes[1].bar(list(NAMES.values()), v, bottom=bottom, color=col, edgecolor="#555", label=s)
        bottom += v
    axes[1].legend(fontsize=6.5, loc="lower right")
    axes[1].set_ylabel("% of province area", fontsize=8)
    axes[1].set_title("Province differences (descriptive; no province is called safer)", fontsize=8)
    save(fig, REVIEW / "multiple-hazard-actions.png", SRC, TAG)

    # 6. unresolved hazard evidence
    fig, axes = plt.subplots(1, 2, figsize=(16, 9.5))
    comp = [
        "REGIONAL_COMPLETE_SITE_RESPONSE_MISSING",
        "PARTIAL_REGIONAL_EVIDENCE",
        "CRITICAL_REGIONAL_GAP",
    ]
    c = code_of(a["data_completeness"], comp)
    cat(
        axes[0],
        grid,
        c,
        ["#e0e0e0", "#bcbddc", "#54278f"],
        comp,
        [float(area[c == i].sum()) for i in range(3)],
        "Regional evidence completeness (ground response is missing in EVERY cell)",
    )
    outline(axes[0], prov)
    strat = pd.read_csv(REVIEW / "action-axis-distribution.csv")
    s = strat[
        (strat["axis"] == "data_completeness")
        & (strat["scope"] == "AOI")
        & (strat["stratum"].isin(["LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15"]))
    ]
    bottom = np.zeros(3)
    for v, col in zip(comp, ["#e0e0e0", "#bcbddc", "#54278f"], strict=True):
        vv = np.array(
            [
                100 * s[(s["stratum"] == st) & (s["value"] == v)]["share_of_scope_area"].iloc[0]
                for st in ["LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15"]
            ]
        )
        axes[1].bar(
            ["LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15"],
            vv,
            bottom=bottom,
            color=col,
            edgecolor="#555",
            label=v,
        )
        bottom += vv
    axes[1].legend(fontsize=6.5)
    axes[1].set_ylabel("% of stratum area", fontsize=8)
    axes[1].set_title("Landslide-coverage gap by slope stratum (reporting only)", fontsize=8)
    save(fig, REVIEW / "unresolved-hazard-evidence.png", SRC, TAG)

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
