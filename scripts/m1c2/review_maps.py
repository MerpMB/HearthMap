"""M1C.2 review maps (outputs/m1c2-review/). Neutral palette; no reassuring green."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a1"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import PROCESSED
from plotting import clean_axes, grid_image, save, scalebar

from hearthmap.hazard.reconcile import COMMON_YEARS, CommonPeriodClass

REVIEW = Path("outputs/m1c2-review")
OUT = Path("outputs/m1c2")
TAG = (
    "HearthMap M1C.2 flood reconciliation - descriptive comparison of two GISTDA products; "
    "neither is ground truth; absence of a polygon != no flood risk."
)
SRC = (
    "GISTDA repeated flooding 2005-2016 (1:50k, legacy) vs GISTDA flood recurrence 2011-2023 (20 m)"
)
CLASSES = [c.value for c in CommonPeriodClass]
C_COL = ["#f0f0f0", "#636363", "#d95f02", "#4575b4", "#9e9ac8"]


def outline(ax, prov):
    prov.boundary.plot(ax=ax, color="black", linewidth=0.7)
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
        fontsize=6.3,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
    )


def main() -> int:
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    t = pd.read_parquet(REVIEW / "common-period-cell-comparison.parquet").set_index("cell_id")
    t = t.loc[grid["cell_id"]]
    area = t["clipped_area_km2"].to_numpy()
    cls = t["common_period_class"]

    # ---- common-period agreement
    fig, axes = plt.subplots(1, 2, figsize=(15, 9.5))
    code = cls.map({c: i for i, c in enumerate(CLASSES)}).to_numpy(float)
    cat(
        axes[0],
        grid,
        code,
        C_COL,
        CLASSES,
        [float(area[code == i].sum()) for i in range(5)],
        "Per-cell agreement over the common years 2011-2016 (presence >= 1% of cell)",
    )
    iou = t["common_period_cell_iou"].to_numpy()
    arr, ext = grid_image(grid, iou)
    im = axes[1].imshow(
        arr, extent=ext, origin="lower", cmap="Greys", vmin=0, vmax=1, interpolation="nearest"
    )
    clean_axes(axes[1], "Cell intersection / union of flooded area, summed over 2011-2016")
    plt.colorbar(im, ax=axes[1], shrink=0.6, label="IoU (blank = no flood in either product)")
    for ax in axes:
        outline(ax, prov)
    save(fig, REVIEW / "common-period-agreement.png", SRC, TAG)

    # ---- legacy-only / current-only fractions (summed over common years)
    for name, col_prefix, title, cmap in (
        (
            "legacy-only-common-period.png",
            "legacy_only_fraction",
            "Area seen ONLY by the legacy product, 2011-2016 (sum of yearly cell shares)",
            "Oranges",
        ),
        (
            "current-only-common-period.png",
            "current_only_fraction",
            "Area seen ONLY by the current product, 2011-2016 (sum of yearly cell shares)",
            "Purples",
        ),
    ):
        v = t[[f"{col_prefix}_{y}" for y in COMMON_YEARS]].sum(axis=1).to_numpy()
        v = np.where(v > 0.005, v, np.nan)
        fig, ax = plt.subplots(figsize=(9, 9.5))
        arr, ext = grid_image(grid, v)
        im = ax.imshow(
            arr, extent=ext, origin="lower", cmap=cmap, vmin=0, vmax=1.5, interpolation="nearest"
        )
        clean_axes(ax, title)
        plt.colorbar(im, ax=ax, shrink=0.6, label="cell-share-years (blank < 0.005)")
        outline(ax, prov)
        save(fig, REVIEW / name, SRC, TAG)

    # ---- year by year
    ann = pd.read_csv(REVIEW / "annual-comparison.csv")
    ann = ann[ann["year"].astype(str).str.len() == 4].copy()
    ann["year"] = ann["year"].astype(int)
    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    for j, (s, label) in enumerate(
        (("AOI", "AOI"), ("TH50", "Chiang Mai"), ("TH56", "Phayao"), ("TH57", "Chiang Rai"))
    ):
        a = ann[ann["scope"] == s].set_index("year").loc[list(COMMON_YEARS)]
        x = np.arange(len(COMMON_YEARS))
        ax = axes[0, j]
        ax.bar(x - 0.2, a["legacy_only_km2"], 0.4, color="#d95f02", label="legacy only")
        ax.bar(
            x - 0.2,
            a["intersection_km2"],
            0.4,
            bottom=a["legacy_only_km2"],
            color="#636363",
            label="both",
        )
        ax.bar(x + 0.2, a["current_only_km2"], 0.4, color="#4575b4", label="current only")
        ax.bar(x + 0.2, a["intersection_km2"], 0.4, bottom=a["current_only_km2"], color="#636363")
        ax.set_xticks(x, COMMON_YEARS, fontsize=7)
        ax.set_title(f"{label}: flooded area by year (left legacy, right current)", fontsize=8)
        ax.set_ylabel("km2", fontsize=7)
        ax.grid(axis="y", alpha=0.3)
        if j == 0:
            ax.legend(fontsize=7)
        ax2 = axes[1, j]
        for c, st, lab in (
            ("intersection_over_union", "-o", "intersection / union"),
            ("legacy_captured_by_current", "--s", "legacy captured by current"),
            ("current_captured_by_legacy", ":^", "current captured by legacy"),
        ):
            ax2.plot(x, a[c], st, color="#252525", label=lab, ms=4)
        ax2.set_xticks(x, COMMON_YEARS, fontsize=7)
        ax2.set_ylim(0, 1)
        ax2.set_title(f"{label}: agreement metrics (blank = undefined)", fontsize=8)
        ax2.grid(alpha=0.3)
        if j == 0:
            ax2.legend(fontsize=7)
    save(fig, REVIEW / "year-by-year-agreement.png", SRC, TAG)

    # ---- largest disagreement regions + four detailed examples
    ex = pd.read_csv(OUT / "example-components.csv")
    regions = pd.read_csv(REVIEW / "largest-disagreement-regions.csv")
    leg = gpd.read_file(
        PROCESSED / "layers.gpkg",
        layer="flood_recurrence",
        columns=[f"year{y}" for y in COMMON_YEARS],
    )
    cur = gpd.read_file(
        "data/processed/m1c1/flood.gpkg",
        layer="flood_recurrence_2011_2023",
        columns=[f"y{y}" for y in COMMON_YEARS],
    )
    leg = leg[leg[[f"year{y}" for y in COMMON_YEARS]].sum(axis=1) > 0]
    cur = cur[cur[[f"y{y}" for y in COMMON_YEARS]].sum(axis=1) > 0]
    fig = plt.figure(figsize=(20, 11))
    ax0 = fig.add_subplot(1, 3, 1)
    cat(
        ax0,
        grid,
        code,
        C_COL,
        CLASSES,
        [float(area[code == i].sum()) for i in range(5)],
        "Common-period classes; boxes = examples A-D",
    )
    outline(ax0, prov)
    gi = grid.set_index("cell_id")
    order = [
        "LEGACY_ONLY_IN_COMMON_PERIOD",
        "CURRENT_ONLY_IN_COMMON_PERIOD",
        "AGREEMENT_FLOOD",
        "MIXED_COMMON_PERIOD_DISAGREEMENT",
    ]
    for i, c in enumerate(order):
        row = ex[ex["class"] == c]
        if row.empty:
            continue
        ids = row["component_cells"].iloc[0].split(";")
        geom = shapely.union_all(gi.loc[ids].geometry.values)
        x0, y0, x1, y1 = geom.bounds
        pad = max(x1 - x0, y1 - y0) * 0.15 + 1000
        box = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)
        ax0.add_patch(
            plt.Rectangle(
                (box[0], box[1]),
                box[2] - box[0],
                box[3] - box[1],
                fill=False,
                edgecolor="black",
                linewidth=1.2,
            )
        )
        ax0.text(box[0], box[3], "ABCD"[i], fontsize=10, weight="bold")
        ax = fig.add_subplot(2, 3, [2, 3, 5, 6][i])
        win = shapely.box(*box)
        lw = leg[leg.intersects(win)]
        cw = cur[cur.intersects(win)]
        cw.plot(ax=ax, facecolor="#4575b4", edgecolor="none", alpha=0.55)
        lw.plot(ax=ax, facecolor="none", edgecolor="#d95f02", linewidth=0.6)
        gpd.GeoSeries([geom]).boundary.plot(ax=ax, color="black", linewidth=1.0)
        ax.set_xlim(box[0], box[2])
        ax.set_ylim(box[1], box[3])
        km2 = regions.loc[(regions["class"] == c) & (regions["rank"] == 1), "area_km2"]
        clean_axes(ax, f"{'ABCD'[i]}: largest {c} component ({float(km2.iloc[0]):.1f} km2)")
        scalebar(ax)
        if i == 0:
            ax.legend(
                handles=[
                    Patch(
                        facecolor="#4575b4",
                        alpha=0.55,
                        label="current, flooded in any 2011-2016 year",
                    ),
                    Patch(
                        facecolor="none",
                        edgecolor="#d95f02",
                        label="legacy, flooded in any 2011-2016 year",
                    ),
                    Patch(facecolor="none", edgecolor="black", label="component cells"),
                ],
                fontsize=6.5,
                loc="lower right",
            )
    save(fig, REVIEW / "largest-disagreement-regions.png", SRC, TAG)

    sizes = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name != "README.md"
    }
    (REVIEW / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
