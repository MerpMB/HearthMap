"""M1C.3 review maps (outputs/m1c3-review/). Neutral palette - nothing green."""

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

from hearthmap.hazard.flood_fusion import (
    YEARS,
    build_ledger,
    evaluate_candidate,
    load_fusion_config,
)

OUT = Path("outputs/m1c3")
REVIEW = Path("outputs/m1c3-review")
TAG = (
    "HearthMap M1C.3 flood fusion - PROVISIONAL regional screening; no flood candidate and no "
    "profile selected; observed flooding only, absence of a polygon != no flood risk."
)
SRC = "GISTDA flood 2005-2016 (legacy, 1:50k) + 2011-2023 (current, 20 m): raw observational ledger"
LADDER = [
    "NO_MAJOR_OBSERVED_SIGNAL",
    "HISTORICAL_SIGNAL",
    "REQUIRES_FLOOD_VERIFICATION",
    "STRONG_FLOOD_SCREENING_CONCERN",
    "UNRESOLVED",
]
L_COL = ["#e0e0e0", "#bcd2e8", "#fee391", "#cc4c02", "#bcbddc"]
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
S_COL = ["#e0e0e0", "#fee391", "#ec7014", "#662506", "#bcbddc"]
POLICIES = [
    "V021_CURRENT_ONLY_REFERENCE",
    "FLOOD_CURRENT_PRIMARY",
    "FLOOD_ANY_SOURCE",
    "FLOOD_UNION_CONSERVATIVE",
]
PROFILES = ["CONSERVATIVE", "BALANCED", "PERMISSIVE"]


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


def cont(ax, grid, vals, title, label, cmap="Blues", vmax=1.0):
    arr, ext = grid_image(grid, vals)
    im = ax.imshow(
        arr, extent=ext, origin="lower", cmap=cmap, vmin=0, vmax=vmax, interpolation="nearest"
    )
    clean_axes(ax, title)
    plt.colorbar(im, ax=ax, shrink=0.6, label=label)


def main() -> int:
    fcfg = load_fusion_config()
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    s = pd.read_parquet(REVIEW / "flood-ledger-summary.parquet")
    area = s["clipped_area_km2"].to_numpy()
    n = len(grid)
    pm = fcfg.presence_min_fraction

    # ---- 1. annual source ledger summary
    by = pd.read_csv(OUT / "ledger-by-year.csv")
    obs = by[by["state"].str.startswith("OBSERVED_")]
    piv = obs.pivot_table(
        index="year",
        columns="state",
        values="observed_fraction_area_km2",
        aggfunc="sum",
        fill_value=0,
    ).reindex(list(YEARS), fill_value=0)
    colors = {
        "OBSERVED_SINGLE_SOURCE_LEGACY": "#8c6d31",
        "OBSERVED_CONSENSUS": "#636363",
        "OBSERVED_LEGACY_ONLY_OVERLAP": "#d95f02",
        "OBSERVED_CURRENT_ONLY_OVERLAP": "#4575b4",
        "OBSERVED_OVERLAP_MIXED_DISAGREEMENT": "#9e9ac8",
        "OBSERVED_SINGLE_SOURCE_CURRENT": "#2b8cbe",
    }
    fig, axes = plt.subplots(1, 2, figsize=(17, 8))
    ax = axes[0]
    bottom = np.zeros(len(YEARS))
    for st, c in colors.items():
        if st in piv.columns:
            ax.bar(
                YEARS,
                piv[st].to_numpy(),
                bottom=bottom,
                color=c,
                label=st.replace("_", " ").lower(),
            )
            bottom += piv[st].to_numpy()
    for x0, x1, lab in (
        (2004.5, 2010.5, "legacy only"),
        (2010.5, 2016.5, "both products"),
        (2016.5, 2023.5, "current only"),
    ):
        ax.axvline(x1, color="black", lw=0.6, ls=":")
        ax.text((x0 + x1) / 2, ax.get_ylim()[1] * 0.97, lab, ha="center", fontsize=8)
    ax.set_xticks(YEARS, YEARS, rotation=90, fontsize=7)
    ax.set_ylabel("mapped flooded area in AOI (km2, cell-clipped union)", fontsize=8)
    ax.set_title(
        "Annual observation ledger by source state (raw observations, not a homogeneous series)",
        fontsize=9,
    )
    ax.legend(fontsize=6.5, loc="upper right", bbox_to_anchor=(1.0, 0.9))
    ax.grid(axis="y", alpha=0.3)
    cont(
        axes[1],
        grid,
        s["observed_year_count_total"].where(s["observed_year_count_total"] > 0).to_numpy(float),
        "Years with observed flooding, 2005-2023 (count of mapped years)",
        "observed_year_count_total (blank = none; NOT a probability)",
        cmap="Greys",
        vmax=8,
    )
    outline(axes[1], prov)
    save(fig, REVIEW / "annual-source-ledger-summary.png", SRC, TAG)

    # ---- 2. recent vs historical
    fig, axes = plt.subplots(1, 3, figsize=(21, 8.5))
    rec, his = s["recent_era_max_fraction"], s["historical_era_max_fraction"]
    cont(
        axes[0],
        grid,
        rec.where(rec >= pm).to_numpy(float),
        "Max annual flooded share, RECENT era 2017-2023 (current product)",
        "share of cell",
    )
    cont(
        axes[1],
        grid,
        his.where(his >= pm).to_numpy(float),
        "Max annual flooded share, HISTORICAL 2005-2016 (legacy / both)",
        "share of cell",
        cmap="Oranges",
    )
    r, h = (rec >= pm).to_numpy(), (his >= pm).to_numpy()
    code = np.select([r & h, r, h], [3, 1, 2], 0).astype(float)
    cat(
        axes[2],
        grid,
        code,
        ["#f0f0f0", "#2b8cbe", "#d95f02", "#636363"],
        ["no observed flooding", "recent only", "historical only", "recent and historical"],
        [float(area[code == i].sum()) for i in range(4)],
        "Where the evidence lies in time (observed >= 1% of cell)",
    )
    for ax in axes:
        outline(ax, prov)
    save(fig, REVIEW / "recent-vs-historical-flood.png", SRC, TAG)

    # ---- 3. product disagreement
    fig, axes = plt.subplots(1, 2, figsize=(15, 9))
    mm = s["max_overlap_mismatch_fraction"]
    cont(
        axes[0],
        grid,
        mm.where(mm >= pm).to_numpy(float),
        "Largest 2011-2016 legacy/current mismatch in a cell-year (share of cell)",
        "mismatch fraction (blank < 1%)",
        cmap="Purples",
    )
    yrs = s["overlap_disagreement_years"]
    y14, y16 = yrs.str.contains("2014"), yrs.str.contains("2016")
    other = (yrs != "") & ~y14 & ~y16
    code = np.select([y14 & y16, y14, y16, other], [3, 1, 2, 4], 0).astype(float)
    cat(
        axes[1],
        grid,
        code,
        ["#f0f0f0", "#d95f02", "#4575b4", "#636363", "#9e9ac8"],
        ["no disagreement", "2014 only", "2016 only", "2014 and 2016", "other years"],
        [float(area[code == i].sum()) for i in range(5)],
        "Years in which the two products disagree (kept visible after fusion)",
    )
    for ax in axes:
        outline(ax, prov)
    save(fig, REVIEW / "product-disagreement.png", SRC, TAG)

    # ---- 4. flood-policy candidates (ladder)
    long = pd.read_parquet(OUT / "policy-results-long.parquet")
    status = {
        (p, q): g["regional_search_status"].to_numpy()
        for (p, q), g in long.groupby(["flood_policy", "profile"], sort=False)
    }
    cands = POLICIES[1:]
    # ladder states per candidate: recomputed from the same ledger the build used
    ledger = build_ledger(
        pd.read_parquet("outputs/m1c2-review/common-period-cell-comparison.parquet"), pm
    )
    ladder = {c: evaluate_candidate(ledger, fcfg, c).state for c in cands}
    fig, axes = plt.subplots(1, 3, figsize=(21, 9.5))
    for ax, c in zip(axes, cands, strict=True):
        st = ladder[c]
        code = pd.Series(st).map({k: i for i, k in enumerate(LADDER)}).to_numpy(float)
        cat(
            ax,
            grid,
            code,
            L_COL,
            LADDER,
            [float(area[st == k].sum()) for k in LADDER],
            f"{c} (provisional, not selected)",
        )
        outline(ax, prov)
    save(fig, REVIEW / "flood-policy-candidates.png", SRC, TAG)

    # ---- 5. policy-sensitive lowlands
    strat = s["slope_stratum_reporting_only"].to_numpy()
    sens = np.zeros(n, bool)
    for p in PROFILES:
        st = np.vstack([status[(c, p)] for c in cands])
        sens |= (st != st[0]).any(axis=0)
    cols = ["#f0f0f0", "#b2182b", "#ef8a62", "#6a51a3", "#969696"]
    names = [
        "not flood-sensitive",
        "sensitive: LOW_SLOPE <= 5 deg",
        "sensitive: GENTLE 5-15 deg",
        "sensitive: STEEP > 15 deg",
        "sensitive: terrain unknown",
    ]
    code = np.zeros(n)
    for i, k in enumerate(("LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15", "UNKNOWN"), 1):
        code[sens & (strat == k)] = i
    lw = pd.read_csv(REVIEW / "lowland-policy-sensitivity.csv")
    lw = lw[lw["measure"] == "overall_status_differs_across_flood_candidates:any_profile"]
    lw = lw[lw["stratum"].isin(["LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15"])]
    fig, axes = plt.subplots(1, 2, figsize=(17, 9), gridspec_kw={"width_ratios": [1.5, 1]})
    cat(
        axes[0],
        grid,
        code,
        cols,
        names,
        [float(area[code == i].sum()) for i in range(5)],
        "Cells whose overall screening outcome depends on the flood-fusion candidate "
        "(any hydrogeomorphic profile); slope strata are reporting-only",
    )
    outline(axes[0], prov)
    ax = axes[1]
    x = np.arange(len(lw))
    ax.bar(
        x - 0.2,
        lw["share_of_stratum_changed"] * 100,
        0.4,
        color="#525252",
        label="% of stratum area that is flood-sensitive",
    )
    ax.bar(
        x + 0.2,
        lw["stratum_share_of_aoi"] * 100,
        0.4,
        color="#bdbdbd",
        label="stratum as % of AOI area",
    )
    ax.set_xticks(x, lw["stratum"], fontsize=8)
    for xi, r in zip(x, lw["disproportion_ratio"], strict=True):
        ax.text(xi, 1, f"ratio {r}", ha="center", fontsize=8)
    ax.set_ylabel("%", fontsize=8)
    ax.legend(fontsize=7)
    ax.set_title(
        "Is flood-source sensitivity concentrated in low-slope land?\n"
        "(ratio > 1 = over-represented; slope strata are not suitability)",
        fontsize=9,
    )
    save(fig, REVIEW / "policy-sensitive-lowlands.png", SRC, TAG)

    # ---- 6. overall policy matrix
    fig, axes = plt.subplots(len(POLICIES), 3, figsize=(17, 28))
    for i, p in enumerate(POLICIES):
        for j, q in enumerate(PROFILES):
            st = status[(p, q)]
            code = pd.Series(st).map({k: v for v, k in enumerate(STATUSES)}).to_numpy(float)
            arr, ext = grid_image(grid, code)
            cmap = ListedColormap(S_COL)
            axes[i, j].imshow(
                arr,
                extent=ext,
                origin="lower",
                cmap=cmap,
                norm=BoundaryNorm(np.arange(-0.5, 5), cmap.N),
                interpolation="nearest",
            )
            dep = float(area[st == "REGIONAL_DEPRIORITIZE"].sum())
            strong = float(area[st == "STRONG_REGIONAL_CONCERN"].sum())
            clean_axes(
                axes[i, j], f"{p}\n{q}: deprioritize {dep:,.0f} km2, strong {strong:,.0f} km2"
            )
            axes[i, j].title.set_fontsize(7.5)
            prov.boundary.plot(ax=axes[i, j], color="black", linewidth=0.4)
    fig.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777", label=lab)
            for c, lab in zip(S_COL, STATUSES, strict=True)
        ],
        loc="lower center",
        ncol=5,
        fontsize=8,
    )
    save(
        fig,
        REVIEW / "overall-policy-matrix.png",
        SRC + "; rows = flood policy, columns = hydrogeomorphic profile",
        TAG,
    )

    sizes = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name not in ("README.md", "file-sizes.json")
    }
    (REVIEW / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
