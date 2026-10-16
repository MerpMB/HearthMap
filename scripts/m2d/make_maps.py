# ruff: noqa: E501
"""M2D.1: human-review maps for the Wave-1 regional-context evidence (descriptive, no scoring, no thresholds)."""

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
from matplotlib.colors import LogNorm
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED

from hearthmap.context.settlement import GridIndex

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
PROC = Path("data/processed/m2d")
NOTE = "Evidence only - not a score, no thresholds. Cells are 500 m. See docs/research/m2d-wave1-findings.md and m2d1-semantics-review.md."
# orientation points for HUMAN calibration only (chosen for familiarity, not a classification of any kind)
REFERENCE_TOWNS = {
    "Chiang Mai (old city)": (98.9853, 18.7883),
    "Chiang Rai (centre)": (99.8310, 19.9072),
    "Phayao (centre)": (99.9019, 19.1664),
    "Fang": (99.2139, 19.9167),
    "Mae Sai": (99.8783, 20.4276),
    "Chiang Khong": (100.4097, 20.2605),
}


def main() -> int:
    df = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    gi = GridIndex(df["cell_id"].tolist())
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries").to_crs(
        CANONICAL
    )
    extent = (gi.e0 * 500, (gi.e0 + gi.w) * 500, gi.n0 * 500, (gi.n0 + gi.h) * 500)
    a3 = gpd.read_file(
        next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip")),
        layer="tha_admin3",
    )
    a3 = a3[a3["adm1_pcode"].isin(["TH50", "TH56", "TH57"])].to_crs(CANONICAL)
    tam = pd.read_csv(OUT / "tables" / "tambon-industry-mining-context.csv")
    a3 = a3.merge(
        tam.drop(columns=["adm1_name", "adm2_name", "adm3_name", "adm3_name1"]),
        on="adm3_pcode",
        how="left",
    )

    def raster(values) -> np.ndarray:
        a = np.full((gi.h, gi.w), np.nan)
        a[gi.row, gi.col] = np.asarray(values, dtype=float)
        return a

    def base(title: str, size=(9, 10)):
        fig, ax = plt.subplots(figsize=size)
        ax.set_title(title, fontsize=9)
        prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.text(0.01, 0.01, NOTE, fontsize=7)
        return fig, ax

    def show(ax, values, cmap, label, norm=None, vmin=None, vmax=None):
        im = ax.imshow(
            raster(values),
            origin="lower",
            extent=extent,
            cmap=cmap,
            norm=norm,
            vmin=vmin,
            vmax=vmax,
            interpolation="nearest",
        )
        plt.colorbar(im, ax=ax, shrink=0.6, label=label)

    def save(fig, name):
        fig.savefig(REVIEW / f"{name}.png", dpi=110, bbox_inches="tight")
        plt.close(fig)

    # 1-2 population and built form
    pd_ = df["population_worldpop2025_density_per_km2"].replace(0, np.nan).to_numpy()
    fig, ax = base(
        "Population intensity: WorldPop R2025A (MODELLED_POPULATION_ESTIMATE, alpha release; NOT observed population, NOT peacefulness)"
    )
    show(
        ax, pd_, "viridis", "modelled people / km2 (log)", norm=LogNorm(vmin=1, vmax=np.nanmax(pd_))
    )
    save(fig, "population-intensity")
    b = df["built_ghsl2020_fraction_500m"].replace(0, np.nan).to_numpy()
    fig, ax = base(
        "Built-form intensity: GHS-BUILT-S 2020 built-up surface fraction (satellite-derived; NOT a building count, NOT population)"
    )
    show(ax, b, "magma_r", "built-up fraction of cell", vmin=0, vmax=1)
    save(fig, "built-form-intensity")

    # 3 relationship and dependency note
    cls = df["settlement_signal_agreement_class"]
    order = ["NO_SIGNAL", *sorted(c for c in cls.unique() if c != "NO_SIGNAL")]
    codes = cls.map({c: i for i, c in enumerate(order)}).to_numpy()
    fig, ax = base(
        "Population vs built form: descriptive agreement of terciles. PARTLY DEPENDENT sources - not independent corroboration",
        size=(11, 10),
    )
    show(ax, codes, "tab20", "class index")
    ax.text(
        0.01,
        0.99,
        "DEPENDENCY NOTE: WorldPop R2025A uses GHSL built-settlement layers (and building footprints)\nas covariates, so a high rank correlation (see build-summary.json) is NOT validation.\nClasses: "
        + "; ".join(f"{i}={c}" for i, c in enumerate(order)),
        transform=ax.transAxes,
        va="top",
        fontsize=5.5,
        bbox={"fc": "white", "alpha": 0.85},
    )
    save(fig, "population-vs-built-form-dependency")

    # 4 service components
    sv = pd.read_csv(PROC / "service_pois.csv")
    fig, ax = base(
        "Town-service components (OSM POIs, kept separate; absence of a POI is not absence of a service)"
    )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    for comp, g in sv.groupby("component"):
        ax.scatter(g["x"], g["y"], s=3, label=f"{comp} ({len(g)})", alpha=0.8)
    ax.legend(fontsize=6, loc="lower left", markerscale=3)
    save(fig, "town-services-components")

    # 5 CORE vs BROADER sensitivity (+ paired difference)
    tc, tb = (
        df["drive_time_to_nearest_service_cluster_core_min"],
        df["drive_time_to_nearest_service_cluster_broader_min"],
    )
    sens = pd.read_csv(OUT / "tables" / "service-cluster-sensitivity.csv")
    aoi = sens[sens["scope"] == "Whole AOI"].iloc[0]
    fig, axes = plt.subplots(1, 3, figsize=(21, 8))
    for ax, vals, ttl, cm, kw in (
        (
            axes[0],
            tc,
            "CORE (CANDIDATE_DEFINITION): >=4 components, 400 m links",
            "cividis_r",
            {"vmin": 0, "vmax": 90},
        ),
        (
            axes[1],
            tb,
            "BROADER (CANDIDATE_DEFINITION): >=3 components, 800 m links",
            "cividis_r",
            {"vmin": 0, "vmax": 90},
        ),
        (
            axes[2],
            tc - tb,
            "Paired difference CORE minus BROADER (min), cells routable for both",
            "RdBu_r",
            {"vmin": -40, "vmax": 40},
        ),
    ):
        prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
        im = ax.imshow(
            raster(vals), origin="lower", extent=extent, cmap=cm, interpolation="nearest", **kw
        )
        ax.set_title(ttl, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.colorbar(im, ax=ax, shrink=0.6, label="minutes (BASELINE_DRIVE_TIME)")
    fig.suptitle(
        f"CORE vs BROADER sensitivity. Among the {int(aoi['cells_routable_for_both']):,} of {int(aoi['cells_total']):,} cells routable for both ({aoi['routable_cell_share']:.0%}): median CORE {aoi['median_core_min']} min, BROADER {aoi['median_broader_min']} min, paired difference median {aoi['median_of_paired_difference_core_minus_broader_min']} min. Neither definition is selected.",
        fontsize=9,
    )
    fig.text(
        0.01,
        0.01,
        "Blank = unresolved (no connected road within 1 km), not zero. " + NOTE,
        fontsize=7,
    )
    save(fig, "town-services-cluster-sensitivity")

    # 6 routing unresolved coverage
    den = pd.read_csv(OUT / "tables" / "routing-denominators.csv")
    aoi_d = den[den["scope"] == "Whole AOI"].iloc[0]
    fig, ax = base(
        f"Routing coverage: {aoi_d['cells_routable']:,.0f} of {aoi_d['cells_total']:,.0f} cells have a connected road within 1 km ({aoi_d['routable_cell_share']:.1%} of cells, {aoi_d['routable_area_share']:.1%} of area). Unresolved: {aoi_d['unresolved_area_share']:.1%} of area."
    )
    show(
        ax,
        (df["road_snap_distance_m"] <= 1000).astype(float),
        "RdYlGn",
        "1 = routable, 0 = unresolved (NaN, not zero)",
        vmin=0,
        vmax=1,
    )
    save(fig, "routing-unresolved-coverage")

    # 7 DIW tambon context (administrative geometry, not a proximity surface)
    fig, ax = base(
        "DIW registered factories per TAMBON (administrative context; NOT point locations; record_status UNKNOWN; outside industrial estates)"
    )
    a3.plot(
        ax=ax,
        column="diw_registered_factories",
        cmap="OrRd",
        legend=True,
        legend_kwds={"shrink": 0.6, "label": "DIW register entries recorded in tambon"},
        linewidth=0.1,
        edgecolor="grey",
        missing_kwds={"color": "whitesmoke"},
    )
    save(fig, "diw-tambon-factory-context")

    # 8 OSM industrial context with geometry
    og = pd.read_csv(PROC / "osm_industry_geometries.csv")
    og["geometry"] = shapely.from_wkt(og["wkt"])
    ogg = gpd.GeoDataFrame(og, geometry="geometry", crs=CANONICAL)
    fig, ax = base(
        "OSM industrial context WITH geometry: polygons drawn as polygons, points as points (not combined into one count)",
        size=(10, 10),
    )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    colors = {
        "OSM_INDUSTRIAL_LANDUSE": "#1f77b4",
        "OSM_WORKS": "#d62728",
        "OSM_QUARRY": "#2ca02c",
        "OSM_INDUSTRIAL_OTHER": "#ff7f0e",
    }
    handles = []
    for kind, g in ogg.groupby("kind"):
        poly = g[g["geometry_class"] == "POLYGON"]
        pts = g[g["geometry_class"] == "POINT"]
        if len(poly):
            poly.buffer(120).plot(
                ax=ax, color=colors[kind], alpha=0.6
            )  # drawn slightly enlarged so small polygons are visible
            handles.append(
                plt.Rectangle((0, 0), 1, 1, fc=colors[kind], label=f"{kind} polygons ({len(poly)})")
            )
        if len(pts):
            pts.plot(ax=ax, color=colors[kind], markersize=18, marker="^")
            handles.append(
                plt.Line2D(
                    [],
                    [],
                    marker="^",
                    color=colors[kind],
                    ls="",
                    label=f"{kind} points ({len(pts)})",
                )
            )
    ax.legend(handles=handles, fontsize=6, loc="lower left")
    save(fig, "osm-industrial-context")

    # 9-10 DPIM mining / stone-crushing context (tambon admin level)
    stone = pd.read_csv(OUT / "tables" / "dpim-stone-crushing-licences-aoi.csv")
    fig, ax = base(
        "DPIM stone-crushing / grinding licence records per TAMBON (register status, NOT current operation; tambon resolution, no coordinates)"
    )
    a3.plot(ax=ax, color="whitesmoke", linewidth=0.1, edgecolor="lightgrey")
    a3[a3["dpim_stone_crushing_licences"] > 0].plot(
        ax=ax,
        column="dpim_stone_crushing_licences",
        cmap="Purples",
        legend=True,
        legend_kwds={"shrink": 0.6, "label": "licence records (any status)"},
        linewidth=0.2,
        edgecolor="grey",
    )
    a3[a3["dpim_stone_crushing_opened_register_status"] > 0].boundary.plot(
        ax=ax, color="red", linewidth=1.0
    )
    q = ogg[(ogg["kind"] == "OSM_QUARRY")]
    q.buffer(150).plot(ax=ax, color="#2ca02c", alpha=0.8)
    ax.legend(
        handles=[
            plt.Line2D(
                [],
                [],
                color="red",
                label=f"tambon with a licence in 'opened' register status ({int((stone['status_vocab'] == 'OPENED_REGISTER_STATUS').sum())} licences)",
            ),
            plt.Rectangle(
                (0, 0),
                1,
                1,
                fc="#2ca02c",
                label=f"OSM quarry geometries ({len(q)}, enlarged for visibility)",
            ),
        ],
        fontsize=7,
        loc="lower left",
    )
    save(fig, "stone-crushing-licence-context")

    fig, ax = base(
        "Mining / quarry context: DPIM concessions (tambon, register status), DIW extraction-type records (tambon), OSM quarry geometry. 2016 legacy outlined (LEGACY_CONTEXT)"
    )
    a3.plot(ax=ax, color="whitesmoke", linewidth=0.1, edgecolor="lightgrey")
    a3[a3["diw_extraction_related"] > 0].plot(
        ax=ax, color="#fdd49e", linewidth=0.1, edgecolor="grey"
    )
    a3[a3["dpim_concessions_unexpired_register_status"] > 0].plot(
        ax=ax, color="#9e9ac8", linewidth=0.1, edgecolor="grey"
    )
    a3[a3["legacy_dpim_2016_concessions"] > 0].boundary.plot(
        ax=ax, color="purple", linewidth=0.5, linestyle=":"
    )
    q.buffer(150).plot(ax=ax, color="#2ca02c", alpha=0.9)
    ax.legend(
        handles=[
            plt.Rectangle(
                (0, 0), 1, 1, fc="#fdd49e", label="tambon with DIW extraction-type (301-304) record"
            ),
            plt.Rectangle(
                (0, 0),
                1,
                1,
                fc="#9e9ac8",
                label="tambon with a DPIM concession in unexpired/renewed register status",
            ),
            plt.Line2D(
                [], [], color="purple", ls=":", label="tambon with a 2016 DPIM concession (legacy)"
            ),
            plt.Rectangle((0, 0), 1, 1, fc="#2ca02c", label="OSM quarry geometry (enlarged)"),
        ],
        fontsize=7,
        loc="lower left",
    )
    save(fig, "dpim-mining-quarry-context")

    # 11 overall evidence completeness
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    state = df["evidence_service_routing_state"].astype("category")
    for ax, vals, title, cm in (
        (
            axes[0],
            state.cat.codes.where(state.cat.codes >= 0).to_numpy().astype(float),
            "Service routing evidence state: "
            + ", ".join(f"{i}={c}" for i, c in enumerate(state.cat.categories)),
            "tab10",
        ),
        (
            axes[1],
            df["service_components_with_a_route"].to_numpy().astype(float),
            "Service components with a route (of 8; 0 where unresolved)",
            "viridis",
        ),
    ):
        prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
        im = ax.imshow(
            raster(vals), origin="lower", extent=extent, cmap=cm, interpolation="nearest"
        )
        ax.set_title(title, fontsize=7)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.colorbar(im, ax=ax, shrink=0.6)
    fig.text(0.01, 0.01, NOTE, fontsize=7)
    save(fig, "evidence-completeness")

    # 12 urban-core calibration panels: separate variables, shared reference windows, NO combination and NO threshold
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
    variables = [
        ("population_worldpop2025_density_per_km2", "modelled people / km2", "viridis", True),
        ("built_ghsl2020_fraction_500m", "built-up fraction", "magma_r", False),
        ("road_density_osm_drivable_km_per_km2", "road km / km2", "cividis", False),
        (
            "osm_service_poi_density_per_km2_mean_2p5km",
            "OSM service POIs / km2 (2.5 km mean; completeness uneven)",
            "plasma",
            False,
        ),
    ]
    fig, axes = plt.subplots(
        len(REFERENCE_TOWNS), len(variables), figsize=(14, 3.3 * len(REFERENCE_TOWNS))
    )
    for r, (name, (lon, lat)) in enumerate(REFERENCE_TOWNS.items()):
        x, y = tr.transform(lon, lat)
        win = (x - 6000, x + 6000, y - 6000, y + 6000)
        for c, (col, lab, cm, log) in enumerate(variables):
            ax = axes[r, c]
            arr = raster(df[col].to_numpy())
            vmax = float(np.nanpercentile(df[col][df[col] > 0], 99)) if (df[col] > 0).any() else 1
            kw = {"norm": LogNorm(vmin=1, vmax=max(vmax, 2))} if log else {"vmin": 0, "vmax": vmax}
            im = ax.imshow(
                arr if not log else np.where(arr > 0, arr, np.nan),
                origin="lower",
                extent=extent,
                cmap=cm,
                interpolation="nearest",
                **kw,
            )
            ax.set_xlim(win[0], win[1])
            ax.set_ylim(win[2], win[3])
            ax.plot([x], [y], "w+", ms=8, mew=1.5)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f"{name}\n{lab}" if c == 0 else lab, fontsize=6)
            plt.colorbar(im, ax=ax, shrink=0.7)
    fig.suptitle(
        "Urban-core calibration panels (12 km windows): four separate descriptive variables, same colour limit per column (99th percentile of non-zero cells, for display only). No scalar, no threshold; reference towns were chosen for orientation, not classification.",
        fontsize=8,
    )
    fig.text(0.01, 0.005, NOTE, fontsize=7)
    save(fig, "urban-core-calibration-panels")
    print("maps written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
