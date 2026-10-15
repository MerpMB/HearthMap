"""M1C review maps: profile comparison, differences, unresolved evidence, reason codes,
largest concern regions. Neutral palette - nothing green, nothing reads as 'safe'."""

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

from hearthmap.hazard import connected_components

M1C = Path("outputs/m1c")
OUT = Path("outputs/m1c-review")
TAG = (
    "HearthMap M1C hydrogeomorphic screening - PROVISIONAL regional screening, no profile "
    "selected; not safe/buildable/rejected; human sign-off M1A.1 + M1B PENDING."
)
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
COLORS = ["#e0e0e0", "#fee391", "#ec7014", "#662506", "#bcbddc"]
LABELS = [
    "no major concern detected (NOT 'safe')",
    "requires verification",
    "strong regional concern",
    "regional deprioritize (NOT 'unbuildable')",
    "unresolved (insufficient evidence)",
]
RANK = {
    "NO_MAJOR_CONCERN_DETECTED": 0,
    "REQUIRES_VERIFICATION": 1,
    "STRONG_REGIONAL_CONCERN": 2,
    "REGIONAL_DEPRIORITIZE": 3,
}
SRC = (
    "M1C policy (config/hazard-policy.yaml) on M1B evidence: GISTDA flood 2005-2016, "
    "DMR landslide susceptibility/inventory, GLO-30 DSM"
)


def status_map(ax, grid, status, title, counts_area):
    code = status.map({s: i for i, s in enumerate(STATUSES)}).to_numpy(float)
    arr, ext = grid_image(grid, code)
    cmap = ListedColormap(COLORS)
    ax.imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, 5), cmap.N),
        interpolation="nearest",
    )
    clean_axes(ax, title)
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777", label=f"{lab} ({counts_area[s]:,.0f} km2)")
            for s, c, lab in zip(STATUSES, COLORS, LABELS, strict=True)
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    res = pd.read_parquet(M1C / "policy-results.parquet")
    prof = {
        p: g.set_index("cell_id").loc[grid["cell_id"]] for p, g in res.groupby("policy_profile")
    }
    area = prof["BALANCED"]["clipped_area_km2"]

    # ---- three profiles
    fig, axes = plt.subplots(1, 3, figsize=(21, 9.5))
    for ax, p in zip(axes, ("CONSERVATIVE", "BALANCED", "PERMISSIVE"), strict=True):
        st = prof[p]["regional_search_status"]
        status_map(
            ax,
            grid,
            st,
            f"{p} profile (provisional, not selected)",
            {s: float(area[st == s].sum()) for s in STATUSES},
        )
        outline(ax, prov)
    save(fig, OUT / "policy-profiles-comparison.png", SRC, TAG)

    # ---- differences vs BALANCED
    fig, axes = plt.subplots(1, 2, figsize=(15, 9.5))
    cats = [
        "same",
        "more concern than BALANCED",
        "less concern than BALANCED",
        "to/from UNRESOLVED",
    ]
    ccol = ["#f0f0f0", "#b2182b", "#2166ac", "#9e9ac8"]
    for ax, p in zip(axes, ("CONSERVATIVE", "PERMISSIVE"), strict=True):
        a = prof["BALANCED"]["regional_search_status"]
        b = prof[p]["regional_search_status"]
        unres = (a == "UNRESOLVED") | (b == "UNRESOLVED")
        ra, rb = a.map(RANK), b.map(RANK)
        code = np.select([a == b, unres, rb > ra, rb < ra], [0, 3, 1, 2], 0).astype(float)
        arr, ext = grid_image(grid, code)
        cmap = ListedColormap(ccol)
        ax.imshow(
            arr,
            extent=ext,
            origin="lower",
            cmap=cmap,
            norm=BoundaryNorm(np.arange(-0.5, 4), cmap.N),
            interpolation="nearest",
        )
        clean_axes(ax, f"{p} vs BALANCED: where the screening outcome changes")
        ax.legend(
            handles=[
                Patch(
                    facecolor=c,
                    edgecolor="#777",
                    label=f"{k} ({float(area[code == i].sum()):,.0f} km2)",
                )
                for i, (k, c) in enumerate(zip(cats, ccol, strict=True))
            ],
            fontsize=6.5,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.01),
        )
        outline(ax, prov)
    save(fig, OUT / "profile-differences.png", SRC, TAG)

    # ---- unresolved / incomplete evidence (BALANCED)
    b = prof["BALANCED"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 9.5))
    comp = ["COMPLETE", "UNRESOLVED_PARTIAL", "UNRESOLVED_CRITICAL"]
    arr, ext = grid_image(
        grid,
        b["evidence_completeness_class"].map({c: i for i, c in enumerate(comp)}).to_numpy(float),
    )
    cmap = ListedColormap(["#f0f0f0", "#bcbddc", "#54278f"])
    axes[0].imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, 3), cmap.N),
        interpolation="nearest",
    )
    clean_axes(axes[0], "Evidence completeness (landslide coverage / terrain support)")
    axes[0].legend(
        handles=[
            Patch(
                facecolor=c,
                edgecolor="#777",
                label=f"{k} ({float(area[b['evidence_completeness_class'] == k].sum()):,.0f} km2)",
            )
            for k, c in zip(comp, cmap.colors, strict=True)
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
    )
    inc = b["evidence_completeness_class"] != "COMPLETE"
    st = b["regional_search_status"].where(inc)
    status_map(
        axes[1],
        grid,
        st,
        "Screening outcome of cells with INCOMPLETE evidence (BALANCED)",
        {s: float(area[inc & (b["regional_search_status"] == s)].sum()) for s in STATUSES},
    )
    for ax in axes:
        outline(ax, prov)
    save(
        fig,
        OUT / "unresolved-evidence.png",
        SRC + "; incomplete = landslide not assessed by DMR or terrain support < 1 px",
        TAG,
    )

    # ---- reason codes
    rc = pd.read_csv(M1C / "reason-code-distribution.csv")
    piv = rc.pivot_table(
        index="reason_code", columns="profile", values="area_km2", aggfunc="sum"
    ).fillna(0)
    piv = piv.loc[piv["BALANCED"].sort_values().index, ["PERMISSIVE", "BALANCED", "CONSERVATIVE"]]
    fig, ax = plt.subplots(figsize=(11, 7))
    y = np.arange(len(piv))
    for i, (p, c) in enumerate(zip(piv.columns, ["#bdbdbd", "#737373", "#252525"], strict=True)):
        ax.barh(y + (i - 1) * 0.27, piv[p], 0.27, color=c, label=p)
    ax.set_yticks(y, piv.index, fontsize=7)
    ax.set_xlabel(
        "area of cells carrying the code (km2; a cell can carry several codes)", fontsize=8
    )
    ax.legend(fontsize=8)
    ax.set_title("Reason-code distribution by profile", fontsize=10)
    ax.grid(axis="x", alpha=0.3)
    save(fig, OUT / "reason-code-distribution.png", SRC, TAG)

    # ---- largest deprioritized regions (BALANCED)
    fig, ax = plt.subplots(figsize=(9, 9.5))
    sel = (b["regional_search_status"] == "REGIONAL_DEPRIORITIZE").to_numpy()
    idx = np.flatnonzero(sel)
    lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
    comp_area = np.bincount(lab, weights=area.to_numpy()[idx])
    top = np.argsort(comp_area)[::-1][:10]
    code = np.full(len(grid), np.nan)
    code[idx] = 10
    for rank, k in enumerate(top):
        code[idx[lab == k]] = rank
    arr, ext = grid_image(grid, code)
    cmap = ListedColormap((*plt.get_cmap("tab10").colors, (0.75, 0.75, 0.75)))
    ax.imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, 11.5), cmap.N),
        interpolation="nearest",
    )
    cent = grid.geometry.centroid
    for rank, k in enumerate(top):
        m = idx[lab == k]
        ax.text(
            cent.x.iloc[m].mean(),
            cent.y.iloc[m].mean(),
            f"{rank + 1}\n{comp_area[k]:.0f} km2",
            fontsize=7,
            ha="center",
            weight="bold",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 1},
        )
    clean_axes(
        ax,
        f"BALANCED: 10 largest contiguous REGIONAL_DEPRIORITIZE regions "
        f"(of {len(comp_area):,} components; grey = smaller)",
    )
    outline(ax, prov)
    save(fig, OUT / "largest-deprioritized-regions.png", SRC + "; 4-connected cells", TAG)

    sizes = {p.name: p.stat().st_size for p in sorted(OUT.glob("*.png"))}
    (OUT / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
