# ruff: noqa: E501
"""M2D: human-review maps for the Wave-1 regional-context evidence (descriptive, no scoring)."""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED

from hearthmap.context.settlement import GridIndex

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
PROC = Path("data/processed/m2d")
NOTE = "Evidence only - not a score. Cells are 500 m. See docs/research/m2d-wave1-findings.md."


def main() -> int:
    df = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    gi = GridIndex(df["cell_id"].tolist())
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries").to_crs(
        CANONICAL
    )
    extent = (gi.e0 * 500, (gi.e0 + gi.w) * 500, gi.n0 * 500, (gi.n0 + gi.h) * 500)

    def raster(values: np.ndarray) -> np.ndarray:
        a = np.full((gi.h, gi.w), np.nan)
        a[gi.row, gi.col] = values
        return a

    def base(title: str, size=(9, 10)):
        fig, ax = plt.subplots(figsize=size)
        ax.set_title(title, fontsize=11)
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

    pd_ = df["population_worldpop2025_density_per_km2"].replace(0, np.nan).to_numpy()
    fig, ax = base(
        "Population intensity: WorldPop R2025A people/km2 per 500 m cell (modelled; NOT peacefulness)"
    )
    show(ax, pd_, "viridis", "people / km2 (log)", norm=LogNorm(vmin=1, vmax=np.nanmax(pd_)))
    save(fig, "population-intensity")

    b = df["built_ghsl2020_fraction_500m"].replace(0, np.nan).to_numpy()
    fig, ax = base(
        "Built-form intensity: GHS-BUILT-S 2020 built-up surface fraction of cell (satellite-derived; NOT population)"
    )
    show(ax, b, "magma_r", "built-up fraction of cell", vmin=0, vmax=1)
    save(fig, "built-form-intensity")

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

    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    for ax, col, name in zip(
        axes,
        [
            "drive_time_to_nearest_service_cluster_core_min",
            "drive_time_to_nearest_service_cluster_broader_min",
        ],
        ["CORE (>=4 components within 400 m links)", "BROADER (>=3 components within 800 m links)"],
        strict=True,
    ):
        prov.boundary.plot(ax=ax, color="black", linewidth=0.6)
        im = ax.imshow(
            raster(df[col].to_numpy()),
            origin="lower",
            extent=extent,
            cmap="cividis_r",
            vmin=0,
            vmax=90,
            interpolation="nearest",
        )
        ax.set_title(f"Baseline drive time to nearest service cluster - {name}", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        plt.colorbar(im, ax=ax, shrink=0.6, label="minutes (BASELINE_DRIVE_TIME)")
    fig.text(
        0.01,
        0.01,
        "Two exposed cluster definitions shown side by side; neither is selected. Blank = unresolved (no route). "
        + NOTE,
        fontsize=7,
    )
    save(fig, "town-services-routing-qa")

    oi = pd.read_csv(PROC / "osm_industry_features.csv")
    diw_t = pd.read_csv(OUT / "tables" / "tambon-industry-mining-context.csv")
    fig, ax = base(
        "Industrial context: OSM industrial features (located). DIW has no coordinates - see tambon map."
    )
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    for kind, g in oi.groupby("kind"):
        ax.scatter(g["x"], g["y"], s=6, label=f"{kind} ({len(g)})", alpha=0.8)
    ax.legend(fontsize=7, loc="lower left", markerscale=2)
    save(fig, "industrial-facilities")

    fig, ax = base(
        "Industrial density context: DIW registered factories per tambon (admin level; NOT point locations; FACTORY_PRESENT != NUISANCE)"
    )
    a3 = gpd.read_file(
        next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip")),
        layer="tha_admin3",
    )
    a3 = (
        a3[a3["adm3_pcode"].isin(diw_t["adm3_pcode"])]
        .to_crs(CANONICAL)
        .merge(diw_t[["adm3_pcode", "diw_registered_factories"]], on="adm3_pcode")
    )
    a3.plot(
        ax=ax,
        column="diw_registered_factories",
        cmap="OrRd",
        legend=True,
        legend_kwds={"shrink": 0.6, "label": "DIW registered factories in tambon"},
        linewidth=0.1,
        edgecolor="grey",
    )
    save(fig, "industrial-density-context")

    fig, ax = base(
        "Mining / quarry context: OSM quarry polygons (centres) + DIW extraction-related tambons + 2016 legacy concession tambons (LEGACY_CONTEXT)"
    )
    a3m = a3.merge(
        diw_t[["adm3_pcode", "diw_extraction_related", "legacy_dpim_2016_concessions"]],
        on="adm3_pcode",
        suffixes=("", "_x"),
    )
    a3m.plot(ax=ax, color="whitesmoke", linewidth=0.1, edgecolor="lightgrey")
    a3m[a3m["diw_extraction_related"] > 0].plot(
        ax=ax, color="#fdd49e", linewidth=0.1, edgecolor="grey"
    )
    a3m[a3m["legacy_dpim_2016_concessions"] > 0].boundary.plot(ax=ax, color="purple", linewidth=0.8)
    q = oi[oi["kind"] == "OSM_QUARRY"]
    ax.scatter(q["x"], q["y"], s=14, c="red", label=f"OSM quarry ({len(q)})")
    ax.legend(
        handles=[
            plt.Line2D([], [], marker="o", color="red", ls="", label=f"OSM quarry ({len(q)})"),
            plt.Rectangle(
                (0, 0), 1, 1, fc="#fdd49e", label="tambon with DIW extraction-related (301-304)"
            ),
            plt.Line2D([], [], color="purple", label="tambon with 2016 DPIM concession (legacy)"),
        ],
        fontsize=7,
        loc="lower left",
    )
    save(fig, "mining-quarry-context")

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
            "Service components with a route (of 8)",
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
    print("maps written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
