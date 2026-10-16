# ruff: noqa: E501
"""M2D.1e: measure the actual extents of the routing network and of every destination/feature catalogue (current truth, not assumption).

ORIGIN_EXTENT, NETWORK_EXTENT, DESTINATION_CATALOG_EXTENT and FEATURE_CONTEXT_EXTENT are different concepts. This audit answers, from the data, whether facilities
outside the three AOI provinces are present, whether a Phayao cell could route to a Nan facility, and whether international destinations are included.
Writes outputs/m2d/tables/evidence-extent-audit.csv and outputs/m2d/evidence-extent-audit.json. No new data are acquired.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "m1a"))
from common import CANONICAL, PROCESSED  # noqa: E402

OUT = Path("outputs/m2d")
AOI_PCODES = {"TH50", "TH56", "TH57"}


def main() -> int:
    z = next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip"))
    adm1 = gpd.read_file(z, layer="tha_admin1").to_crs(CANONICAL)
    th = shapely.union_all(
        gpd.read_file(z, layer="tha_admin0").to_crs(CANONICAL).geometry.to_numpy()
    )
    aoi = shapely.union_all(
        gpd.read_file(
            PROCESSED / "boundaries.gpkg", layer="province_boundaries"
        ).geometry.to_numpy()
    )
    a1 = adm1.set_index("adm1_pcode")["adm1_name"]
    tree = shapely.STRtree(adm1.geometry.to_numpy())

    def province_of(xy: np.ndarray) -> np.ndarray:
        out = np.full(len(xy), "OUTSIDE_THAILAND", dtype=object)
        pts = shapely.points(xy)
        ci, pi = tree.query(pts, predicate="within")
        out[ci] = adm1["adm1_pcode"].to_numpy()[pi]
        return out

    rows: list[dict] = []
    summary: dict = {}

    def add(
        family: str, catalogue: str, xy: np.ndarray, extent_concept: str, note: str = ""
    ) -> None:
        xy = np.asarray(xy, dtype=float)
        xy = xy[np.isfinite(xy).all(axis=1)]
        in_aoi = shapely.contains_xy(aoi, xy[:, 0], xy[:, 1])
        prov = province_of(xy)
        in_three = np.isin(prov, list(AOI_PCODES))
        neigh = (~in_three) & (prov != "OUTSIDE_THAILAND")
        intl = prov == "OUTSIDE_THAILAND"
        rows.append(
            {
                "family": family, "catalogue": catalogue, "extent_concept": extent_concept, "records": len(xy),
                "inside_aoi_polygon": int(in_aoi.sum()), "outside_aoi_polygon": int((~in_aoi).sum()),
                "in_the_three_provinces_by_coordinate": int(in_three.sum()),
                "in_other_thai_provinces": int(neigh.sum()), "outside_thailand": int(intl.sum()),
                "neighbouring_provinces_present": ", ".join(sorted({str(a1.get(p, p)) for p in prov[neigh]})) or "none",
                "note": note,
            }
        )  # fmt: skip
        rows[-1]["_by_other_province"] = {
            str(k): int(v) for k, v in pd.Series(prov[neigh]).value_counts().items()
        }
        summary[f"{family}:{catalogue}"] = rows[-1]

    # network
    nz = np.load("data/processed/m2a/network.npz")
    nxy = nz["xy"]
    n_in = shapely.contains_xy(aoi, nxy[:, 0], nxy[:, 1])
    n_th = shapely.contains_xy(th, nxy[:, 0], nxy[:, 1])
    rows.append(
        {
            "family": "routing_network", "catalogue": "osm drivable network (M2A cache)", "extent_concept": "NETWORK_EXTENT", "records": len(nxy),
            "inside_aoi_polygon": int(n_in.sum()), "outside_aoi_polygon": int((~n_in).sum()), "in_the_three_provinces_by_coordinate": "",
            "in_other_thai_provinces": int((~n_in & n_th).sum()), "outside_thailand": int((~n_th).sum()), "neighbouring_provinces_present": "network nodes (not facilities)",
            "note": "the network extends beyond the AOI, so routes can cross provincial and international boundaries",
        }
    )  # fmt: skip
    # education and healthcare catalogues (the frozen M2A.2 processed layers)
    edu = gpd.read_file("data/processed/m2a2/facilities.gpkg", layer="education_facilities")
    edu_routed = edu[edu["coordinate_qa_status"] != "FAILED"]
    exy = (
        gpd.GeoSeries(gpd.points_from_xy(edu_routed["x"], edu_routed["y"]))
        .get_coordinates()
        .to_numpy()
        if "x" in edu_routed
        else None
    )
    exy = edu_routed.to_crs(CANONICAL).geometry.get_coordinates().to_numpy()
    add(
        "education",
        "DOPA gis-02 + OBEC (routed: coordinate QA not FAILED)",
        exy,
        "DESTINATION_CATALOG_EXTENT",
        "per-province DOPA registers for TH50/56/57",
    )
    hl = gpd.read_file("data/processed/m2a2/facilities.gpkg", layer="health_facilities").to_crs(
        CANONICAL
    )
    add(
        "healthcare",
        "MoPH public point layers (all records)",
        hl.geometry.get_coordinates().to_numpy(),
        "DESTINATION_CATALOG_EXTENT",
        "changwat filter at acquisition: Chiang Mai, Chiang Rai, Phayao",
    )
    # town services, industry, quarry, nightlife
    sv = pd.read_csv("data/processed/m2d/service_pois.csv")
    add(
        "town_services",
        "OSM service POIs (after duplicate collapse)",
        sv[["x", "y"]].to_numpy(),
        "DESTINATION_CATALOG_EXTENT",
        "Overpass area queries ISO3166-2 TH-50/56/57",
    )
    nl = pd.read_csv("data/processed/m2d/nightlife_candidates.csv")
    add(
        "nightlife",
        "OSM nightlife candidate tags",
        nl[["x", "y"]].to_numpy(),
        "FEATURE_CONTEXT_EXTENT",
        "same province-area extract",
    )
    og = pd.read_csv("data/processed/m2d/osm_industry_geometries.csv")
    g = shapely.from_wkt(og["wkt"])
    cxy = shapely.get_coordinates(shapely.point_on_surface(g))
    for kind in ("OSM_INDUSTRIAL_LANDUSE", "OSM_WORKS", "OSM_QUARRY"):
        m = (og["kind"] == kind).to_numpy()
        add(
            "industrial_quarry",
            kind,
            cxy[m],
            "FEATURE_CONTEXT_EXTENT",
            "feature representative point; same province-area extract",
        )
    pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]).to_csv(
        OUT / "tables" / "evidence-extent-audit.csv", index=False
    )

    ed, he, sv_ = (
        summary["education:DOPA gis-02 + OBEC (routed: coordinate QA not FAILED)"],
        summary["healthcare:MoPH public point layers (all records)"],
        summary["town_services:OSM service POIs (after duplicate collapse)"],
    )
    answers = {
        "facilities_outside_the_three_provinces_present": {
            "education": ed["in_other_thai_provinces"] + ed["outside_thailand"],
            "healthcare": he["in_other_thai_provinces"] + he["outside_thailand"],
            "town_services": sv_["in_other_thai_provinces"] + sv_["outside_thailand"],
        },
        "phayao_cell_can_route_to_a_nan_facility": {
            k: v["_by_other_province"].get("TH55", 0)
            for k, v in summary.items()
            if k.split(":")[0] in ("education", "healthcare", "town_services")
        },
        "chiang_mai_border_cell_catalogue_records_in_lamphun_lampang_mae_hong_son": {
            k: {p: v["_by_other_province"].get(p, 0) for p in ("TH51", "TH52", "TH58")}
            for k, v in summary.items()
            if k.split(":")[0] in ("education", "healthcare", "town_services")
        },
        "international_destinations_included": {
            "education": ed["outside_thailand"],
            "healthcare": he["outside_thailand"],
            "town_services": sv_["outside_thailand"],
        },
        "network_nodes_outside_aoi": int((~n_in).sum()),
        "network_nodes_outside_thailand": int((~n_th).sum()),
    }
    (OUT / "evidence-extent-audit.json").write_text(
        json.dumps(answers, indent=1, default=int) + "\n", "utf-8"
    )
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(
        pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
        .drop(columns=["note"])
        .to_string()
    )
    print(json.dumps(answers, indent=1, default=int))
    return 0


if __name__ == "__main__":
    sys.exit(main())
