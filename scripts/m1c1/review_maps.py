"""M1C.1 review maps (outputs/m1c1-review/). Neutral palette - nothing green."""

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

M1C1 = Path("outputs/m1c1")
BASE = Path("data/interim/m1c1/baseline-m1c-1d9a15c")
OUT = Path("outputs/m1c1-review")
TAG = (
    "HearthMap M1C.1 flood refresh - PROVISIONAL regional screening, no profile selected; "
    "not safe/buildable/rejected; observed flooding only, absence != no risk."
)
SRC_NEW = "GISTDA flood recurrence 2011-2023 (API, 20 m)"
SRC_OLD = "GISTDA repeated flooding 2005-2016 (1:50k)"
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
S_COL = ["#e0e0e0", "#fee391", "#ec7014", "#662506", "#bcbddc"]
S_LAB = [
    "no major concern detected (NOT 'safe')",
    "requires verification",
    "strong regional concern",
    "regional deprioritize (NOT 'unbuildable')",
    "unresolved (insufficient evidence)",
]
RANK = {s: i for i, s in enumerate(STATUSES[:4])}
FC = [
    "CONSISTENT_NO_MAJOR_SIGNAL",
    "CONSISTENT_CONCERN",
    "NEWER_DATA_INCREASES_CONCERN",
    "NEWER_DATA_DECREASES_CONCERN",
    "NOT_DIRECTLY_COMPARABLE",
]
FC_COL = ["#f0f0f0", "#969696", "#b2182b", "#2166ac", "#9e9ac8"]


def cat_map(ax, grid, codes, colors, labels, areas, title):
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
        fontsize=6.3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
    )


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.7)
    ax.set_xlabel("")
    ax.set_ylabel("")
    scalebar(ax)


def frac_map(ax, grid, vals, title, label):
    arr, ext = grid_image(grid, vals)
    im = ax.imshow(
        arr, extent=ext, origin="lower", cmap="Blues", vmin=0, vmax=1, interpolation="nearest"
    )
    clean_axes(ax, title)
    plt.colorbar(im, ax=ax, shrink=0.6, label=label)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    ev = pd.read_parquet(M1C1 / "evidence" / "hazard-evidence.parquet").set_index("cell_id")
    ev = ev.loc[grid["cell_id"]]
    area = ev["clipped_area_km2"].to_numpy()

    # ---- new flood evidence
    fig, axes = plt.subplots(1, 2, figsize=(15, 9.5))
    frac_map(
        axes[0],
        grid,
        ev["flood_area_fraction"].where(ev["flood_area_fraction"] > 0).to_numpy(),
        "Share of cell observed flooded at least once, 2011-2023",
        "flood_area_fraction (blank = none observed; NOT 'no risk')",
    )
    frac_map(
        axes[1],
        grid,
        ev["flood_years_ge3_area_fraction"]
        .where(ev["flood_years_ge3_area_fraction"] > 0)
        .to_numpy(),
        "Share of cell observed flooded in >= 3 of 13 years (2011-2023)",
        "flood_years_ge3_area_fraction",
    )
    for ax in axes:
        outline(ax, prov)
    save(fig, OUT / "new-flood-evidence.png", SRC_NEW, TAG)

    # ---- old vs new flood
    fc = pd.read_parquet(M1C1 / "flood-change-cells.parquet").set_index("cell_id")
    fc = fc.loc[grid["cell_id"]]
    code = fc["flood_change_class"].map({c: i for i, c in enumerate(FC)}).to_numpy(float)
    fig, axes = plt.subplots(1, 2, figsize=(15, 9.5))
    cat_map(
        axes[0],
        grid,
        code,
        FC_COL,
        FC,
        [float(area[code == i].sum()) for i in range(len(FC))],
        "Flood screening tier: 2005-2016 record vs 2011-2023 record",
    )
    d = (fc["flood_ge3_fraction_2011_2023"] - fc["flood_ge3_fraction_2005_2016"]).to_numpy()
    d = np.where(np.abs(d) < 0.01, np.nan, d)
    arr, ext = grid_image(grid, d)
    im = axes[1].imshow(
        arr, extent=ext, origin="lower", cmap="RdBu_r", vmin=-0.6, vmax=0.6, interpolation="nearest"
    )
    clean_axes(
        axes[1], "Recurrent-flood share: (>=3 of 13, 2011-2023) minus (>=3 of 12, 2005-2016)"
    )
    plt.colorbar(im, ax=axes[1], shrink=0.6, label="difference in cell share (|d| < 0.01 blank)")
    for ax in axes:
        outline(ax, prov)
    save(fig, OUT / "old-vs-new-flood.png", f"{SRC_OLD} vs {SRC_NEW}", TAG)

    # ---- policy maps
    po = pd.read_parquet(BASE / "policy-results.parquet")
    pn = pd.read_parquet(M1C1 / "policy" / "policy-results.parquet")

    def prof(df, p):
        return df[df["policy_profile"] == p].set_index("cell_id").loc[grid["cell_id"]]

    bn = prof(pn, "BALANCED")
    sb = bn["regional_search_status"]

    fig, ax = plt.subplots(figsize=(9, 9.5))
    cat_map(
        ax,
        grid,
        sb.map({s: i for i, s in enumerate(STATUSES)}).to_numpy(float),
        S_COL,
        S_LAB,
        [float(area[(sb == s).to_numpy()].sum()) for s in STATUSES],
        "BALANCED profile, refreshed flood evidence (provisional, not selected)",
    )
    outline(ax, prov)
    save(
        fig,
        OUT / "balanced-policy-refreshed.png",
        f"M1C policy {pn['policy_version'].iloc[0]} on {SRC_NEW}, DMR landslide, GLO-30 DSM",
        TAG,
    )

    cats = [
        "unchanged",
        "more concern after refresh",
        "less concern after refresh",
        "to/from UNRESOLVED",
    ]
    ccol = ["#f0f0f0", "#b2182b", "#2166ac", "#9e9ac8"]
    fig, axes = plt.subplots(1, 3, figsize=(21, 9.5))
    for ax, p in zip(axes, ("CONSERVATIVE", "BALANCED", "PERMISSIVE"), strict=True):
        a, b = prof(po, p)["regional_search_status"], prof(pn, p)["regional_search_status"]
        ra, rb = a.map(RANK), b.map(RANK)
        unres = (a != b) & ((a == "UNRESOLVED") | (b == "UNRESOLVED"))
        c = np.select([a == b, unres, rb > ra, rb < ra], [0, 3, 1, 2], 0).astype(float)
        cat_map(
            ax,
            grid,
            c,
            ccol,
            cats,
            [float(area[c == i].sum()) for i in range(4)],
            f"{p}: screening outcome change after flood refresh",
        )
        outline(ax, prov)
    save(
        fig,
        OUT / "flood-policy-change.png",
        f"M1C policy 0.1.0 ({SRC_OLD}) vs 0.2.0 ({SRC_NEW})",
        TAG,
    )

    # ---- profile change summary (bars)
    dist = pd.read_csv(M1C1 / "policy-refresh-distribution.csv")
    dist = dist[dist["scope"] == "AOI"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), sharey=True)
    for ax, p in zip(axes, ("CONSERVATIVE", "BALANCED", "PERMISSIVE"), strict=True):
        dd = dist[dist["profile"] == p].set_index("status").loc[STATUSES]
        y = np.arange(len(STATUSES))
        ax.barh(y + 0.2, dd["area_km2_before"], 0.4, color="#bdbdbd", label="before (2005-2016)")
        ax.barh(y - 0.2, dd["area_km2_after"], 0.4, color="#525252", label="after (2011-2023)")
        ax.set_yticks(y, [s.replace("_", " ").lower() for s in STATUSES], fontsize=7)
        ax.set_title(p, fontsize=10)
        ax.set_xlabel("area (km2)", fontsize=8)
        ax.grid(axis="x", alpha=0.3)
        for yi, (bv, av) in enumerate(
            zip(dd["area_km2_before"], dd["area_km2_after"], strict=True)
        ):
            ax.text(max(bv, av) * 1.01, yi, f"{av - bv:+,.0f}", va="center", fontsize=7)
    axes[0].legend(fontsize=7)
    save(fig, OUT / "profile-change-summary.png", "M1C policy before/after flood refresh", TAG)

    sizes = {p.name: p.stat().st_size for p in sorted(OUT.glob("*.png"))}
    (OUT / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
