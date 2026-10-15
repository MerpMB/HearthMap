"""M1B review package: compact maps + README for human review of hazard evidence.

Colour policy: NO_HIGH_HAZARD_EVIDENCE_DETECTED is neutral grey (never green -
it is not "safe"); UNRESOLVED is a distinct light purple; CAUTION orange; HIGH
dark red. Continuous indicators use sequential colormaps.
"""

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
from common import PROCESSED, PROVINCE_NAMES
from plotting import clean_axes, grid_image, save, scalebar

from hearthmap.provenance import current_code_version

M1B = Path("outputs/m1b")
OUT = Path("outputs/m1b-review")
TAG = (
    "HearthMap M1B hazard EVIDENCE review - provisional, not a decision; "
    "no-evidence != safe; M1A.1 human sign-off PENDING."
)
STATES = ["NO_HIGH_HAZARD_EVIDENCE_DETECTED", "CAUTION", "HIGH_HAZARD_EVIDENCE", "UNRESOLVED"]
STATE_COLORS = ["#d9d9d9", "#fdae61", "#a50f15", "#bcbddc"]
STATE_LABELS = [
    "no high-hazard evidence detected (NOT 'safe')",
    "caution",
    "high hazard evidence",
    "unresolved / insufficient evidence",
]


def state_map(ax, grid, series, title):
    code = series.map({s: i for i, s in enumerate(STATES)}).to_numpy().astype(float)
    arr, ext = grid_image(grid, code)
    cmap = ListedColormap(STATE_COLORS)
    ax.imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, 4), cmap.N),
        interpolation="nearest",
    )
    clean_axes(ax, title)
    counts = series.value_counts()
    ax.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777777", label=f"{lab} ({int(counts.get(s, 0)):,})")
            for s, c, lab in zip(STATES, STATE_COLORS, STATE_LABELS, strict=True)
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=1,
    )


def cont_map(fig, ax, grid, values, title, cmap, label, vmin=None, vmax=None, nan_note=None):
    arr, ext = grid_image(grid, np.asarray(values, float))
    im = ax.imshow(
        arr, extent=ext, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest"
    )
    clean_axes(ax, title)
    cb = fig.colorbar(im, ax=ax, shrink=0.55, pad=0.01)
    cb.set_label(label, fontsize=7)
    cb.ax.tick_params(labelsize=6.5)
    if nan_note:
        ax.text(
            0.01,
            0.01,
            nan_note,
            transform=ax.transAxes,
            fontsize=6.5,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
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
    w = pd.read_parquet(M1B / "hazard-evidence.parquet").set_index("cell_id").loc[grid["cell_id"]]
    sens = pd.read_csv(M1B / "threshold-sensitivity.csv")

    # ---- flood
    fig, ax = plt.subplots(1, 2, figsize=(15, 9))
    cont_map(
        fig,
        ax[0],
        grid,
        w["flood_freq_ge3_area_fraction"].where(w["flood_freq_ge3_area_fraction"] > 0),
        "Share of cell observed flooded in >= 3 of 12 years (2005-2016)",
        "Blues",
        "flood_freq_ge3_area_fraction (blank = none observed)",
        0,
        1,
    )
    state_map(ax[1], grid, w["flood_state"], "Provisional flood interpretation")
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "flood-evidence.png",
        "GISTDA repeated flooding 2005-2016 (TEMPORARY "
        "historical observed evidence; misses flash floods and cloud-covered events)",
        TAG,
    )

    # ---- landslide
    fig, ax = plt.subplots(1, 2, figsize=(15, 9))
    mx = w["landslide_max_class"].where(w["landslide_assessed_fraction"] >= 0.5)
    arr, ext = grid_image(grid, mx.to_numpy(float))
    cmap = ListedColormap(["#ffffcc", "#c2e699", "#fdae61", "#e6550d", "#7f2704"])
    ax[0].imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(0.5, 6), cmap.N),
        interpolation="nearest",
    )
    clean_axes(ax[0], "Highest DMR susceptibility class present in cell (publisher classes)")
    ax[0].legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777", label=f"{k} {lab}")
            for k, c, lab in zip(
                range(1, 6),
                cmap.colors,
                ["Very Low", "Low", "Medium", "High", "Very High"],
                strict=True,
            )
        ]
        + [
            Patch(
                facecolor="white",
                edgecolor="#777",
                label="blank = < 50% of cell assessed by DMR (NOT 'very low')",
            )
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=2,
    )
    state_map(
        ax[1],
        grid,
        w["landslide_state"],
        "Provisional landslide interpretation (susceptibility + mapped scars)",
    )
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "landslide-evidence.png",
        "DMR landslide susceptibility (~1 km, methodology "
        "not published) and DMR landslide inventory (uneven coverage)",
        TAG,
    )

    # ---- terrain
    fig, ax = plt.subplots(1, 3, figsize=(20, 9))
    cont_map(
        fig,
        ax[0],
        grid,
        w["slope_p90_deg"],
        "DSM slope p90 per cell (robust high)",
        "magma_r",
        "degrees (DSM: canopy/buildings bias)",
        0,
        50,
    )
    cont_map(
        fig,
        ax[1],
        grid,
        w["slope_median_deg"],
        "DSM slope median per cell",
        "magma_r",
        "degrees",
        0,
        40,
    )
    sup = w["terrain_support_px"].to_numpy()
    cls = np.select([sup < 1, sup < 10], [2.0, 1.0], 0.0)
    arr, ext = grid_image(grid, cls)
    cmap = ListedColormap(["#f0f0f0", "#fd8d3c", "#54278f"])
    ax[2].imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5], cmap.N),
        interpolation="nearest",
    )
    weak = grid.geometry.centroid[sup < 10]
    ax[2].scatter(weak.x, weak.y, s=4, c=np.where(sup[sup < 10] < 1, "#54278f", "#fd8d3c"))
    clean_axes(ax[2], "Terrain support (ADR-0009): weak cells drawn as dots (they are tiny)")
    ax[2].legend(
        handles=[
            Patch(color="#f0f0f0", label=f">= 10 px ({int((sup >= 10).sum()):,})"),
            Patch(
                color="#fd8d3c",
                label=f"1-10 px LOW_SUPPORT ({int(((sup >= 1) & (sup < 10)).sum()):,})",
            ),
            Patch(color="#54278f", label=f"< 1 px UNKNOWN ({int((sup < 1).sum()):,})"),
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
    )
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "terrain-slope-support.png",
        "Copernicus GLO-30 DSM, Horn slope with "
        "geodesic spacing, support-aware weighted statistics",
        TAG,
    )

    # ---- waterways
    fig, ax = plt.subplots(1, 2, figsize=(15, 9))
    cont_map(
        fig,
        ax[0],
        grid,
        w["dist_any_waterway_m"] / 1000,
        "Distance to nearest mapped OSM waterway (any class)",
        "viridis_r",
        "km (mapped only)",
        0,
        10,
    )
    total = w[
        ["waterway_river_length_m", "waterway_canal_length_m", "waterway_stream_length_m"]
    ].sum(axis=1)
    cont_map(
        fig,
        ax[1],
        grid,
        (total / 1000).where(total > 0),
        "Mapped waterway length inside cell",
        "Blues",
        "km per 0.25 km2 cell (blank = none mapped, not none present)",
        0,
        2,
    )
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "waterway-context.png",
        "OpenStreetMap waterways (ODbL); completeness varies "
        "by province; distance to water is NOT flood safety",
        TAG,
    )

    # ---- multi-hazard
    fig, ax = plt.subplots(1, 2, figsize=(15, 9))
    state_map(
        ax[0],
        grid,
        w["overall_state"],
        "Categorical multi-hazard view (worst state wins; no averaging)",
    )
    combos = [
        "",
        "flood",
        "landslide",
        "terrain",
        "landslide|terrain",
        "flood|landslide",
        "flood|terrain",
        "flood|landslide|terrain",
    ]
    colors = [
        "#f7f7f7",
        "#2171b5",
        "#a50f15",
        "#6a51a3",
        "#000000",
        "#f781bf",
        "#41ab5d",
        "#ffff33",
    ]
    code = w["high_hazards"].map({c: i for i, c in enumerate(combos)}).fillna(0).to_numpy(float)
    arr, ext = grid_image(grid, code)
    cmap = ListedColormap(colors)
    ax[1].imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, len(combos)), cmap.N),
        interpolation="nearest",
    )
    cnt = w["high_hazards"].value_counts()
    ax[1].legend(
        handles=[
            Patch(
                facecolor=c,
                edgecolor="#777",
                label=f"{k or 'no HIGH evidence'} ({int(cnt.get(k, 0)):,})",
            )
            for k, c in zip(combos, colors, strict=True)
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=2,
    )
    clean_axes(ax[1], "Which hazards have HIGH evidence (combinations kept separate)")
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "multi-hazard-evidence.png",
        "flood (GISTDA 2005-2016), landslide (DMR), "
        "terrain (GLO-30 DSM); provisional rules config/hazard.yaml",
        TAG,
    )

    # ---- unknown / incomplete
    fig, ax = plt.subplots(1, 2, figsize=(15, 9))
    cont_map(
        fig,
        ax[0],
        grid,
        w["evidence_completeness"],
        "Evidence completeness (share of flood/landslide/terrain resolved)",
        "cividis",
        "completeness",
        0,
        1,
    )
    uh = w["unresolved_hazards"].replace("", "none")
    opts = ["none", "landslide", "terrain", "landslide|terrain"]
    arr, ext = grid_image(
        grid, uh.map({o: i for i, o in enumerate(opts)}).fillna(0).to_numpy(float)
    )
    cmap = ListedColormap(["#f7f7f7", "#bcbddc", "#54278f", "#000000"])
    ax[1].imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, 4), cmap.N),
        interpolation="nearest",
    )
    cnt = uh.value_counts()
    ax[1].legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777", label=f"{o} ({int(cnt.get(o, 0)):,})")
            for o, c in zip(opts, cmap.colors, strict=True)
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=2,
    )
    clean_axes(ax[1], "Which hazard is unresolved (landslide: outside DMR coverage)")
    for a in ax:
        outline(a, prov)
    save(
        fig,
        OUT / "unknown-incomplete-evidence.png",
        "evidence completeness per cell; unassessed is never treated as low hazard",
        TAG,
    )

    # ---- sensitivity
    rules = sens["candidate_rule"].unique()
    fig, axes = plt.subplots(1, len(rules), figsize=(5 * len(rules), 4.5))
    pcolor = {"AOI": "black", "TH50": "#1b9e77", "TH56": "#d95f02", "TH57": "#7570b3"}
    for ax_, rule in zip(axes, rules, strict=True):
        s = sens[sens["candidate_rule"] == rule]
        for scope, g in s.groupby("scope", sort=False):
            g = g.copy()
            g["thr"] = g["threshold"].str.extract(r"([-\d.]+)").astype(float)
            g = g.sort_values("thr")
            ax_.plot(
                g["thr"],
                100 * g["share_of_area"],
                marker="o",
                color=pcolor[scope],
                label=PROVINCE_NAMES.get(scope, "AOI"),
            )
        ax_.set_title(
            f"{rule}\n({s['field'].iloc[0]} {s['threshold'].iloc[0].split()[0]} t)", fontsize=8
        )
        ax_.set_xlabel("threshold t", fontsize=7)
        ax_.set_ylabel("% of in-AOI area flagged", fontsize=7)
        ax_.tick_params(labelsize=7)
        ax_.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.suptitle(
        "EXPERIMENTAL exclusion-candidate sensitivity - no threshold selected; "
        "flags never affect eligibility",
        fontsize=10,
    )
    save(
        fig,
        OUT / "experimental-exclusion-sensitivity.png",
        "outputs/m1b/"
        "threshold-sensitivity.csv (majority-province attribution; see boundary caveat)",
        TAG,
    )

    sizes = {p.name: p.stat().st_size for p in sorted(OUT.glob("*.png"))}
    (OUT / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1), current_code_version())
    return 0


if __name__ == "__main__":
    sys.exit(main())
