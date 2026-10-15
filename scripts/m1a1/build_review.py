"""M1A.1: build the compact human spatial-QA review package.

outputs/m1a-review/  - README.md, PNG map excerpts, CSV tables, qa-summary.json and
                       hearthmap-m1a-review.gpkg (review-only subsets).

Descriptive QA only: nothing here modifies a boundary, scores, ranks or excludes.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).parent))
import analysis as an
from plotting import clean_axes, grid_image, save, scalebar, window

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, PROVINCE_NAMES

from hearthmap.provenance import current_code_version
from hearthmap.qa import mark_review_only

OUT = Path("outputs/m1a-review")
GPKG = OUT / "hearthmap-m1a-review.gpkg"
REF_STYLE = {
    "gistda-50k": {"color": "#d95f02", "ls": "--", "label": "GISTDA 1:50k (SECONDARY)"},
    "geoboundaries": {
        "color": "#7570b3",
        "ls": ":",
        "label": "geoBoundaries ADM1/OSM (VALIDATION_ONLY)",
    },
}
COD_STYLE = {"color": "black", "lw": 1.2}


def to_utm(lon: float, lat: float) -> tuple[float, float]:
    p = gpd.GeoSeries([shapely.Point(lon, lat)], crs="EPSG:4326").to_crs(CANONICAL).iloc[0]
    return p.x, p.y


def boundary_legend(ax, extra: list | None = None, loc: str = "upper right") -> None:
    handles = [Line2D([], [], color="black", lw=1.2, label="COD-AB province (PRIMARY, unchanged)")]
    handles += [
        Line2D([], [], color=s["color"], ls=s["ls"], lw=1.2, label=s["label"])
        for s in REF_STYLE.values()
    ]
    handles += extra or []
    ax.legend(handles=handles, fontsize=6.5, loc=loc, framealpha=0.9)


def plot_refs(ax, b: dict, pcodes=None, lw: float = 1.0) -> None:
    for name, gdf in (("gistda-50k", b["gistda"]), ("geoboundaries", b["geob"])):
        g = gdf if pcodes is None else gdf[gdf["adm1_pcode"].isin(pcodes)]
        s = REF_STYLE[name]
        g.boundary.plot(ax=ax, color=s["color"], linestyle=s["ls"], linewidth=lw, zorder=6)
    p = b["prov"] if pcodes is None else b["prov"][b["prov"]["adm1_pcode"].isin(pcodes)]
    p.boundary.plot(ax=ax, color=COD_STYLE["color"], linewidth=COD_STYLE["lw"], zorder=7)


# ---------------------------------------------------------------- figures


def fig_overview(b, ba, terrain) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 9))
    arr, ext = grid_image(
        b["grid"], terrain.set_index("cell_id").loc[b["grid"]["cell_id"], "elev_mean_m"].to_numpy()
    )
    im = ax.imshow(arr, extent=ext, origin="lower", cmap="Greys", alpha=0.55)
    b["dist"].boundary.plot(ax=ax, color="#999999", linewidth=0.3)
    plot_refs(ax, b, lw=0.8)
    z = ba["zones"][ba["zones"]["material"]]
    for name, s in REF_STYLE.items():
        z[z["reference_source"] == name].plot(ax=ax, color=s["color"], alpha=0.6, zorder=5)
    for _, r in b["prov"].iterrows():
        c = r.geometry.representative_point()
        ax.text(
            c.x,
            c.y,
            f"{r['adm1_name']} ({r['adm1_pcode']})",
            fontsize=9,
            weight="bold",
            ha="center",
            bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
        )
    clean_axes(
        ax,
        "M1A AOI: COD-AB provinces, independent references and material "
        f"disagreement zones (offset >= {an.MATERIAL_OFFSET_M:g} m)",
    )
    boundary_legend(
        ax,
        [
            Patch(color=s["color"], alpha=0.6, label=f"material zone vs {n}")
            for n, s in REF_STYLE.items()
        ],
        loc="lower right",
    )
    cb = fig.colorbar(im, ax=ax, shrink=0.45, pad=0.01)
    cb.set_label("background: mean DSM elevation per 500 m cell (m)", fontsize=7)
    scalebar(ax)
    save(
        fig,
        OUT / "overview.png",
        "COD-AB, GISTDA L05 1:50k, geoBoundaries THA ADM1, Copernicus GLO-30 (DSM)",
    )


def _zone_inset(ax, b, ba, zone, half=None) -> None:
    g = zone.geometry
    minx, miny, maxx, maxy = g.bounds
    half = half or max(maxx - minx, maxy - miny) * 0.65 + 750
    cx, cy = g.centroid.x, g.centroid.y
    window(ax, cx, cy, half)
    view = shapely.box(cx - half, cy - half, cx + half, cy + half)
    cells = b["grid"][b["grid"].intersects(view)]
    cells.boundary.plot(ax=ax, color="#dddddd", linewidth=0.3, zorder=1)
    style = REF_STYLE[zone["reference_source"]]
    gpd.GeoSeries([g], crs=CANONICAL).plot(ax=ax, color=style["color"], alpha=0.45, zorder=3)
    b["dist"][b["dist"].intersects(view)].boundary.plot(
        ax=ax, color="#aaaaaa", linewidth=0.4, zorder=2
    )
    plot_refs(ax, b, lw=1.1)
    window(ax, cx, cy, half)
    clean_axes(
        ax,
        f"{zone['zone_id']} · {zone['nearest_district']} · {zone['province_name']}\n"
        f"{zone['area_km2']:.1f} km², max offset {zone['max_offset_m'] / 1000:.1f} km, "
        f"{zone['border_type']} · {zone['provisional_class']} · "
        f"corroborated {zone['corroboration_fraction']:.0%}",
    )
    ax.title.set_fontsize(7.5)
    scalebar(ax, frac=0.3)


def fig_boundary_province(b, ba, pcode: str, fname: str, n_insets: int) -> None:
    z = ba["zones"]
    pz = z[(z["province"] == pcode) & z["material"]].sort_values("area_km2", ascending=False)
    # Largest GISTDA zones first (Thai government reference), then the largest geoBoundaries one.
    picks = pd.concat(
        [
            pz[pz["reference_source"] == "gistda-50k"].head(n_insets - 1),
            pz[pz["reference_source"] == "geoboundaries"].head(1),
        ]
    )
    picks = picks.drop_duplicates(subset=["zone_id"]).head(n_insets)
    ncol = 1 + int(np.ceil(len(picks) / 2))
    fig = plt.figure(figsize=(5.2 * ncol, 9))
    gs = fig.add_gridspec(2, ncol)
    ax0 = fig.add_subplot(gs[:, 0])
    prov = b["prov"][b["prov"]["adm1_pcode"] == pcode]
    others = b["prov"][b["prov"]["adm1_pcode"] != pcode]
    others.plot(ax=ax0, color="#f2f2f2", edgecolor="#cccccc", linewidth=0.5)
    b["dist"][b["dist"]["adm1_pcode"] == pcode].boundary.plot(
        ax=ax0, color="#bbbbbb", linewidth=0.4
    )
    for name, s in REF_STYLE.items():
        pz[pz["reference_source"] == name].plot(ax=ax0, color=s["color"], alpha=0.55, zorder=4)
    plot_refs(ax0, b, pcodes=[pcode], lw=0.9)
    minx, miny, maxx, maxy = prov.total_bounds
    pad = 8000
    ax0.set_xlim(minx - pad, maxx + pad)
    ax0.set_ylim(miny - pad, maxy + pad)
    for _, r in picks.iterrows():
        p = r.geometry.representative_point()
        ax0.annotate(
            r["zone_id"].split("-")[-1]
            if r["reference_source"] == "gistda-50k"
            else "gB-" + r["zone_id"].split("-")[-1],
            (p.x, p.y),
            fontsize=7,
            weight="bold",
            xytext=(6, 6),
            textcoords="offset points",
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1},
        )
    clean_axes(
        ax0,
        f"{PROVINCE_NAMES[pcode]} ({pcode}): material disagreement zones "
        f"(offset >= {an.MATERIAL_OFFSET_M:g} m)",
    )
    boundary_legend(
        ax0,
        [Patch(color=s["color"], alpha=0.55, label=f"zone vs {n}") for n, s in REF_STYLE.items()],
        loc="upper center",
    )
    ax0.get_legend().set_bbox_to_anchor((0.5, -0.02))
    scalebar(ax0)
    for i, (_, zone) in enumerate(picks.iterrows()):
        ax = fig.add_subplot(gs[i % 2, 1 + i // 2])
        _zone_inset(ax, b, ba, zone)
    save(
        fig,
        OUT / fname,
        "COD-AB admin1/2 (PRIMARY), GISTDA L05 1:50k, geoBoundaries ADM1; "
        "grid cells 500 m (light grey)",
    )


def fig_forest_overview(b, fa) -> None:
    pc = fa["per_cell"].set_index("cell_id").loc[b["grid"]["cell_id"]]
    fig = plt.figure(figsize=(18, 10))
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.05], hspace=0.35, wspace=0.12)
    ax1 = fig.add_subplot(gs[:, 0])
    arr, ext = grid_image(b["grid"], pc["reserve_area_fraction"].to_numpy())
    im = ax1.imshow(arr, extent=ext, origin="lower", cmap="YlGn", vmin=0, vmax=1)
    b["prov"].boundary.plot(ax=ax1, color="black", linewidth=0.8)
    clean_axes(
        ax1,
        "RFD reserve area fraction of each cell's in-AOI area\n"
        "(intersection area, not centroid; SCREENING / legal verification only)",
    )
    cb = fig.colorbar(im, ax=ax1, shrink=0.5, pad=0.01)
    cb.set_label("reserve_area_fraction", fontsize=7)
    scalebar(ax1)

    ax2 = fig.add_subplot(gs[:, 1])
    order = [
        "none",
        "reserve",
        "park",
        "sanctuary",
        "reserve+park",
        "reserve+sanctuary",
        "park+sanctuary",
        "reserve+park+sanctuary",
    ]
    colors = [
        "#e6e6e6",
        "#a6d96a",
        "#fdae61",
        "#abd9e9",
        "#1a9641",
        "#2c7bb6",
        "#d7191c",
        "#000000",
    ]
    code = pc["category_combination"].map({k: i for i, k in enumerate(order)}).to_numpy()
    arr, ext = grid_image(b["grid"], code.astype(float))
    cmap = ListedColormap(colors)
    ax2.imshow(
        arr,
        extent=ext,
        origin="lower",
        cmap=cmap,
        norm=BoundaryNorm(np.arange(-0.5, len(order)), cmap.N),
        interpolation="nearest",
    )
    b["prov"].boundary.plot(ax=ax2, color="black", linewidth=0.8)
    clean_axes(
        ax2,
        "Screening categories present in each cell (any overlap > 0)\n"
        "descriptive combinations - NOT a severity ranking",
    )
    counts = fa["combos_cells"].set_index("combination")["cells"]
    ax2.legend(
        handles=[
            Patch(facecolor=c, edgecolor="#777777", label=f"{k} ({int(counts.get(k, 0)):,} cells)")
            for k, c in zip(order, colors, strict=True)
        ],
        fontsize=6.5,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=2,
        framealpha=0.9,
    )
    scalebar(ax2)

    ax3 = fig.add_subplot(gs[0, 2])
    h = fa["histogram"].set_index("scope")
    bins = [c for c in h.columns if c.startswith("(")]
    x = np.arange(len(bins) + 1)
    width = 0.27
    for i, (scope, color) in enumerate(
        (("TH50", "#1b9e77"), ("TH56", "#d95f02"), ("TH57", "#7570b3"))
    ):
        vals = [h.loc[scope, "fraction_eq_0"]] + [h.loc[scope, c] for c in bins]
        ax3.bar(
            x + (i - 1) * width,
            vals,
            width,
            color=color,
            label=f"{PROVINCE_NAMES[scope]} ({scope})",
        )
    ax3.set_xticks(
        x, ["= 0"] + [c.replace("(", "").replace("]", "") for c in bins], fontsize=6, rotation=45
    )
    ax3.set_yscale("log")
    ax3.set_ylabel("cells (log scale)", fontsize=7)
    ax3.set_title("Histogram of reserve_area_fraction (per province)", fontsize=9)
    ax3.legend(fontsize=6.5)
    ax3.tick_params(labelsize=6.5)

    ax4 = fig.add_subplot(gs[1, 2])
    ax4.axis("off")
    d = fa["distribution"]
    tbl = d.pivot(index="threshold", columns="scope", values="share_of_cells")
    tbl = tbl.loc[d["threshold"].unique(), ["AOI", "TH50", "TH56", "TH57"]]
    t = ax4.table(
        cellText=[[f"{v:.1%}" for v in row] for row in tbl.to_numpy()],
        rowLabels=[f"fraction {i}" for i in tbl.index],
        colLabels=["AOI", "Chiang Mai", "Phayao", "Chiang Rai"],
        bbox=[0.28, 0.0, 0.72, 0.9],
    )
    t.auto_set_font_size(False)
    t.set_fontsize(7)
    ax4.set_title("Share of cells at or above each reserve-area threshold", fontsize=9)
    save(
        fig,
        OUT / "forest-coverage-overview.png",
        "RFD final_NRF_all_1221_620108 (2019 edition), MNRE national parks 2014 and wildlife "
        "sanctuaries via GISTDA; COD-AB AOI",
    )


def _pick_example(pc, lo, hi):
    s = pc[
        (pc["reserve_area_fraction"] > lo)
        & (pc["reserve_area_fraction"] <= hi)
        & (pc["coverage_fraction"] >= 0.999)
    ].sort_values("cell_id")
    return s.iloc[len(s) // 2] if len(s) else None


def fig_forest_examples(b, fa) -> pd.DataFrame:
    pc = fa["per_cell"]
    cases = [
        ("edge contact", 0.0, 0.01),
        ("small partial overlap", 0.05, 0.15),
        ("substantial overlap", 0.45, 0.55),
        ("nearly / fully covered", 0.995, 1.0),
    ]
    reserve = fa["layers"]["reserve"]
    grid = b["grid"].set_index("cell_id")
    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    picked = []
    for ax, (label, lo, hi) in zip(axes.ravel(), cases, strict=True):
        r = _pick_example(pc, lo, hi)
        cell = grid.loc[r["cell_id"]].geometry
        cx, cy = cell.centroid.x, cell.centroid.y
        view = shapely.box(cx - 1250, cy - 1250, cx + 1250, cy + 1250)
        reserve[reserve.intersects(view)].plot(
            ax=ax, color="#78c679", alpha=0.55, edgecolor="#238443", linewidth=1
        )
        grid[grid.intersects(view)].boundary.plot(ax=ax, color="#888888", linewidth=0.5)
        gpd.GeoSeries([cell], crs=CANONICAL).boundary.plot(ax=ax, color="red", linewidth=2)
        window(ax, cx, cy, 1250)
        clean_axes(
            ax,
            f"{label}: {r['cell_id']}\nreserve_area_fraction = "
            f"{r['reserve_area_fraction']:.4f}  ({r['category_combination']})",
        )
        scalebar(ax, frac=0.3)
        picked.append(
            {
                "example": label,
                "cell_id": r["cell_id"],
                "reserve_area_fraction": r["reserve_area_fraction"],
            }
        )
    axes[0, 0].legend(
        handles=[
            Patch(color="#78c679", alpha=0.55, label="RFD reserve polygon"),
            Line2D([], [], color="red", lw=2, label="example cell"),
            Line2D([], [], color="#888888", lw=0.5, label="500 m grid"),
        ],
        fontsize=7,
        loc="upper right",
    )
    save(
        fig,
        OUT / "forest-overlap-examples.png",
        "RFD reserve polygons (screening / legal verification only), 500 m grid",
    )
    return pd.DataFrame(picked)


def fig_flood_overview(b) -> None:
    ov = (
        gpd.read_file(
            PROCESSED / "overlays.gpkg", layer="screening_overlays_500m", ignore_geometry=True
        )
        .set_index("cell_id")
        .loc[b["grid"]["cell_id"]]
    )
    fig, axes = plt.subplots(1, 2, figsize=(14, 8.5))
    arr, ext = grid_image(b["grid"], ov["flood_obs_max_flood_freq"].to_numpy())
    cmap = plt.get_cmap("Blues", 9)
    im = axes[0].imshow(arr, extent=ext, origin="lower", cmap=cmap, vmin=0.5, vmax=9.5)
    cb = fig.colorbar(im, ax=axes[0], shrink=0.5, ticks=range(1, 10))
    cb.set_label("max years flooded (of 12, 2005-2016) among polygons in cell", fontsize=7)
    arr2, _ = grid_image(b["grid"], ov["flood_obs_affected_area_fraction"].to_numpy())
    im2 = axes[1].imshow(
        np.where(arr2 > 0, arr2, np.nan), extent=ext, origin="lower", cmap="PuBu", vmin=0, vmax=1
    )
    cb2 = fig.colorbar(im2, ax=axes[1], shrink=0.5)
    cb2.set_label("observed-flood affected area fraction (cells > 0 only)", fontsize=7)
    for ax, title in zip(
        axes,
        ("Max observed flood recurrence per cell", "Share of cell area ever observed flooded"),
        strict=True,
    ):
        b["prov"].boundary.plot(ax=ax, color="black", linewidth=0.8)
        clean_axes(
            ax,
            title + "\nHISTORICAL OBSERVED (satellite) - TEMPORARY evidence; "
            "blank != no flood risk",
        )
        scalebar(ax)
    save(
        fig,
        OUT / "flood-overview.png",
        "GISTDA repeated flooding 2005-2016 (1:50k), area-based cell overlay",
    )


def fig_flood_repairs(fr) -> pd.DataFrame:
    audit = fr["audit"].copy()
    before = fr["before"].set_index("objectid")
    picks = []
    picks.append(audit.sort_values("area_after_m2", ascending=False).iloc[0])
    picks.append(audit.sort_values("component_count_before", ascending=False).iloc[0])
    picks.append(audit.sort_values("flood_freq", ascending=False).iloc[0])
    polys = audit[audit["geometry_type_before"] == "Polygon"]
    if len(polys):
        picks.append(polys.sort_values("area_after_m2", ascending=False).iloc[0])
    picks = pd.DataFrame(picks).drop_duplicates("source_feature_id")
    fig, axes = plt.subplots(2, len(picks), figsize=(4.2 * len(picks), 8.5))
    for j, (_, r) in enumerate(picks.iterrows()):
        g = before.loc[r["source_feature_id"]].geometry
        fixed = shapely.make_valid(g)
        x, y = (float(v) for v in r["validity_reason_before"].split("[")[1].rstrip("]").split())
        for i, half in enumerate((None, 60.0)):
            ax = axes[i, j]
            gpd.GeoSeries([fixed], crs=CANONICAL).plot(ax=ax, color="#9ecae1", alpha=0.8)
            gpd.GeoSeries([g], crs=CANONICAL).boundary.plot(
                ax=ax, color="#d62728", linewidth=0.8, linestyle="--"
            )
            ax.plot(
                [x], [y], marker="o", markersize=9, markerfacecolor="none", markeredgecolor="black"
            )
            if half:
                window(ax, x, y, half)
                title = f"zoom ±{half:g} m at reported self-intersection"
            else:
                title = (
                    f"feature {r['source_feature_id']} (flood_freq {int(r['flood_freq'])})\n"
                    f"{r['geometry_type_before']}->{r['geometry_type_after']}, "
                    f"parts {r['component_count_before']}->{r['component_count_after']}, "
                    f"Δarea {r['absolute_area_delta_m2']:.1e} m²"
                )
            clean_axes(ax, title)
            ax.title.set_fontsize(7.5)
            scalebar(ax, frac=0.3)
    axes[0, 0].legend(
        handles=[
            Patch(color="#9ecae1", label="after make_valid"),
            Line2D([], [], color="#d62728", ls="--", label="before (invalid ring)"),
            Line2D(
                [],
                [],
                marker="o",
                color="black",
                ls="",
                markerfacecolor="none",
                label="reported self-intersection",
            ),
        ],
        fontsize=6.5,
        loc="upper left",
    )
    save(
        fig,
        OUT / "flood-repair-examples.png",
        "GISTDA repeated flooding 2005-2016; repair replayed with shapely.make_valid",
    )
    return picks


TERRAIN_WINDOWS = [
    ("Chiang Mai mountains (Doi Suthep / Mae Rim)", 98.90, 18.84),
    ("Heavily forested mountain (Doi Inthanon)", 98.49, 18.59),
    ("Chiang Rai lowland valley", 99.83, 19.91),
    ("Phayao (Kwan Phayao basin)", 99.89, 19.17),
]


def fig_terrain(b, terrain) -> None:
    t = terrain.set_index("cell_id").loc[b["grid"]["cell_id"]]
    lay = PROCESSED / "layers.gpkg"
    rivers = gpd.read_file(lay, layer="waterways", where="waterway = 'river'")
    roads = gpd.read_file(lay, layer="major_roads")
    elev, ext = grid_image(b["grid"], t["elev_mean_m"].to_numpy())
    slope, _ = grid_image(b["grid"], t["slope_gt15_fraction"].to_numpy())
    fig, axes = plt.subplots(2, 4, figsize=(18, 9.5))
    half = 15000
    for j, (title, lon, lat) in enumerate(TERRAIN_WINDOWS):
        cx, cy = to_utm(lon, lat)
        view = shapely.box(cx - half, cy - half, cx + half, cy + half)
        win_elev = elev  # full image, window via limits
        vals = t[b["grid"].set_index("cell_id").loc[t.index].intersects(view).to_numpy()]
        vmin, vmax = np.nanpercentile(vals["elev_mean_m"], [2, 98])
        for i, (arr, cmap, lim, lab) in enumerate(
            (
                (win_elev, "viridis", (vmin, vmax), "mean DSM elevation (m)"),
                (slope, "magma_r", (0, 1), "share of pixels with slope > 15°"),
            )
        ):
            ax = axes[i, j]
            im = ax.imshow(arr, extent=ext, origin="lower", cmap=cmap, vmin=lim[0], vmax=lim[1])
            rivers[rivers.intersects(view)].plot(ax=ax, color="#00bfff", linewidth=1.0)
            roads[roads.intersects(view)].plot(ax=ax, color="white", linewidth=0.7)
            b["prov"].boundary.plot(ax=ax, color="red", linewidth=0.8)
            window(ax, cx, cy, half)
            clean_axes(ax, title if i == 0 else None)
            cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.01)
            cb.set_label(lab, fontsize=6.5)
            cb.ax.tick_params(labelsize=6)
            scalebar(ax, frac=0.3)
    axes[0, 0].legend(
        handles=[
            Line2D([], [], color="#00bfff", label="OSM river"),
            Line2D([], [], color="white", label="OSM major road"),
            Line2D([], [], color="red", label="COD-AB province"),
        ],
        fontsize=6.5,
        loc="lower right",
        facecolor="#bbbbbb",
    )
    save(
        fig,
        OUT / "terrain-review.png",
        "Copernicus GLO-30 DSM terrain preview per 500 m cell "
        "(ANALYTICAL PREVIEW), OSM rivers/major roads for alignment check",
    )


# ---------------------------------------------------------------- outputs


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    b = an.load_base()
    print("boundary audit ...", flush=True)
    ba = an.boundary_audit(b)
    print("forest audit ...", flush=True)
    fa = an.forest_audit(b)
    print("flood repair audit ...", flush=True)
    fr = an.flood_repair_audit(b)
    de = an.dem_edge_cells(b)
    terrain = de["terrain"]
    mat = an.boundary_materiality(b, ba, fa, terrain)

    # ---- tables
    z = ba["zones"]
    zt = z[(z["area_km2"] >= 0.01) | z["material"]].copy()
    zt.insert(0, "rank", range(1, len(zt) + 1))
    zcols = [
        "rank",
        "zone_id",
        "province",
        "province_name",
        "reference_source",
        "kind",
        "nearest_district",
        "other_side",
        "lon",
        "lat",
        "border_type",
        "max_offset_m",
        "median_offset_m",
        "mean_width_m",
        "area_km2",
        "affected_grid_cells",
        "corroboration_fraction",
        "material",
        "provisional_class",
        "notes",
    ]
    zt[zcols].rename(columns={"area_km2": "symmetric_difference_area_km2"}).round(3).to_csv(
        OUT / "boundary-disagreements.csv", index=False
    )
    fa["distribution"].round(6).to_csv(OUT / "forest-coverage-summary.csv", index=False)
    fa["histogram"].to_csv(OUT / "forest-fraction-histogram.csv", index=False)
    combos = pd.concat(
        [
            fa["combos_area"].assign(basis="area (exact combination, no double counting)"),
            fa["combos_cells"].assign(scope="AOI", basis="cells (category fraction > 0)"),
        ],
        ignore_index=True,
    )
    combos.round(6).to_csv(OUT / "forest-category-overlaps.csv", index=False)
    fr["audit"].to_csv(OUT / "flood-repair-audit.csv", index=False)
    dcols = [
        "cell_id",
        "coverage_fraction",
        "clipped_area_m2",
        "clipped_mean_width_m",
        "expected_pixel_centres",
    ]
    de["cells"][dcols].round(4).to_csv(OUT / "dem-edge-cells.csv", index=False)
    mat.round(4).to_csv(OUT / "boundary-uncertainty-context.csv", index=False)

    # ---- figures
    print("figures ...", flush=True)
    fig_overview(b, ba, terrain)
    fig_boundary_province(b, ba, "TH50", "chiang-mai-boundary-disagreement.png", 5)
    fig_boundary_province(b, ba, "TH57", "chiang-rai-boundary-review.png", 3)
    fig_boundary_province(b, ba, "TH56", "phayao-boundary-review.png", 3)
    fig_forest_overview(b, fa)
    examples = fig_forest_examples(b, fa)
    fig_flood_overview(b)
    repair_picks = fig_flood_repairs(fr)
    fig_terrain(b, terrain)

    # ---- review GeoPackage (review-only subsets)
    print("review gpkg ...", flush=True)
    b["prov"].to_file(GPKG, layer="province_boundaries", driver="GPKG")
    refs = pd.concat(
        [b["gistda"].assign(reference="gistda-50k"), b["geob"].assign(reference="geoboundaries")],
        ignore_index=True,
    )
    mark_review_only(gpd.GeoDataFrame(refs, crs=CANONICAL), purpose="reference boundaries").to_file(
        GPKG, layer="reference_boundaries", driver="GPKG"
    )
    mark_review_only(zt[[*zcols, "geometry"]], purpose="boundary disagreement zones").to_file(
        GPKG, layer="boundary_disagreement_zones", driver="GPKG"
    )
    mark_review_only(
        ba["cells"], purpose="boundary uncertainty (edge-cell attribution caution)"
    ).to_file(GPKG, layer="boundary_uncertainty_review", driver="GPKG")
    pc = fa["per_cell"]
    fr_cells = b["grid"][["cell_id", "geometry"]].merge(
        pc[
            (
                pc[["reserve_area_fraction", "park_area_fraction", "sanctuary_area_fraction"]] > 0
            ).any(axis=1)
        ],
        on="cell_id",
    )
    mark_review_only(
        gpd.GeoDataFrame(fr_cells, crs=CANONICAL),
        purpose="forest/protected screening coverage (legal verification only)",
    ).to_file(GPKG, layer="forest_review", driver="GPKG")
    before = fr["before"].rename(columns={"objectid": "source_feature_id"})
    rep_before = before.merge(fr["audit"], on="source_feature_id").assign(state="before")
    rep_after = rep_before.copy()
    rep_after["geometry"] = shapely.make_valid(rep_after.geometry.values)
    rep_after["state"] = "after"
    rep = gpd.GeoDataFrame(pd.concat([rep_before, rep_after], ignore_index=True), crs=CANONICAL)
    rep = rep.drop(columns=["flood_freq_x"], errors="ignore")
    mark_review_only(rep, purpose="flood repair audit").to_file(
        GPKG, layer="flood_repair_review", driver="GPKG"
    )
    sel = b["grid"][
        b["grid"]["cell_id"].isin(set(examples["cell_id"]) | set(de["cells"]["cell_id"]))
    ]
    sel = sel.assign(
        selection=np.where(
            sel["cell_id"].isin(set(examples["cell_id"])),
            "forest example",
            "dem edge cell without pixel centre",
        )
    )
    mark_review_only(sel, purpose="selected review cells").to_file(
        GPKG, layer="selected_grid_cells", driver="GPKG"
    )

    # ---- summary
    grid_json = json.loads(Path("data/interim/m1a/validation/grid.json").read_text("utf-8"))
    gz = z[z["reference_source"] == "gistda-50k"]
    summary = {
        "milestone": "M1A.1 human spatial QA gate",
        "code_version": current_code_version(),
        "decision_use": "NONE - descriptive QA; no scores, ranks or exclusions",
        "boundaries": {
            "material_offset_threshold_m": an.MATERIAL_OFFSET_M,
            "zones_by_reference_class": z.groupby(["reference_source", "provisional_class"])
            .agg(zones=("zone_id", "size"), area_km2=("area_km2", "sum"))
            .round(3)
            .reset_index()
            .to_dict("records"),
            "gistda_top_zones": gz.head(10)[
                [
                    "zone_id",
                    "province",
                    "nearest_district",
                    "other_side",
                    "border_type",
                    "max_offset_m",
                    "area_km2",
                    "corroboration_fraction",
                    "provisional_class",
                ]
            ]
            .round(1)
            .to_dict("records"),
            "uncertainty_mask": ba["stats"],
            "materiality_context": mat.round(4).to_dict("records"),
        },
        "grid": {
            k: {
                kk: v[kk]
                for kk in (
                    "n_cells",
                    "raw_cell_footprint_area_km2",
                    "clipped_coverage_area_km2",
                    "boundary_area_km2",
                    "edge_overhang_area_km2",
                    "coverage_difference_km2",
                    "tolerance_km2",
                    "invariant_ok",
                )
            }
            for k, v in grid_json.items()
        },
        "forest": {
            "distribution": fa["distribution"].round(4).to_dict("records"),
            "category_area_combinations_AOI": fa["combos_area"][fa["combos_area"]["scope"] == "AOI"]
            .round(4)
            .to_dict("records"),
            "category_cell_combinations_AOI": fa["combos_cells"].round(4).to_dict("records"),
            "examples": examples.to_dict("records"),
        },
        "flood_repair": fr["summary"],
        "flood_repair_examples": repair_picks["source_feature_id"].tolist(),
        "flood_sources": {
            "flood-gistda-repeated-2005-2016": {"evidence_role": "TEMPORARY_HISTORICAL_EVIDENCE"},
            "flood-gistda-history": {
                "metadata_verified": True,
                "data_verified": False,
                "acquisition_status": "BLOCKED_CREDENTIAL_REQUIRED",
                "intended_role": "PRIMARY_HISTORICAL_FLOOD_EVIDENCE",
            },
        },
        "dem_edge_cells": de["summary"],
    }
    (OUT / "qa-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", "utf-8")
    sizes = {p.name: p.stat().st_size for p in sorted(OUT.iterdir())}
    (OUT / "file-sizes.json").write_text(json.dumps(sizes, indent=2) + "\n", "utf-8")
    print(json.dumps(sizes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
