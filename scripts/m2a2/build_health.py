# ruff: noqa: E501
"""M2A.2: health facility layer from the public MoPH point layers (current location AND source classification).

Roles: MoPH update68 = PRIMARY (current, 2026 edit); MoPH update69 = CROSSCHECK; CITIZENinfo 2020 = HISTORICAL_VALIDATION;
OSM 2026 = EXTERNAL cross-check. Field-level provenance is recorded: location_source / classification_source /
classification_freshness. A record never looks current just because its coordinates are. Education layer is carried over
unchanged from M2A.1 (no current MOE register was supplied). Outputs: data/processed/m2a2/facilities.gpkg and
outputs/m2a2-review/*.csv|json
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, source_ref

from hearthmap.enums import Confidence
from hearthmap.family import coordinate_flags, deduplicate, load_config
from hearthmap.family.moph import classify_health_moph
from hearthmap.family.reconcile import (
    FacilitySource,
    compose_primary,
    health_comparison_name,
    reconcile,
    summarise,
)
from hearthmap.provenance import ProvenanceRecord, current_code_version

M2A1 = Path("data/processed/m2a1")
OUT = Path("data/processed/m2a2")
REVIEW = Path("outputs/m2a2-review")
PROV = {"เชียงใหม่": "TH50", "พะเยา": "TH56", "เชียงราย": "TH57"}
RAW68 = Path("data/raw/facility-moph-hospital-update68/service-2026-10-16")
RAW69 = Path("data/raw/facility-moph-hospital-update69/service-2026-10-16")
SRC_MOPH = FacilitySource(
    "MoPH PHER public hospital point layer Hospital_update68", 2026, "PRIMARY", current=True
)
SRC_MOPH69 = FacilitySource(
    "MoPH PHER Hospital_update69_correct", 2026, "HISTORICAL_VALIDATION", current=True
)
SRC_CIT = FacilitySource(
    "DGA CITIZENinfo (2020-03-14)", 2020, "HISTORICAL_VALIDATION", current=False
)
SRC_OSM = FacilitySource(
    "OpenStreetMap facilities (2026-10-16)", 2026, "CURRENT_VALIDATION", current=True
)


def ms_date(v) -> str | None:
    return (
        None
        if v is None or (isinstance(v, float) and np.isnan(v))
        else dt.datetime.fromtimestamp(v / 1000, dt.UTC).date().isoformat()
    )


def load_layer(raw: Path, cfg, prov: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    feats = []
    for p in sorted(raw.glob("page_*.json")):
        feats += json.loads(p.read_text("utf-8"))["features"]
    df = pd.DataFrame([f["attributes"] for f in feats])
    df["geom_lon"] = [f["geometry"]["x"] for f in feats]
    df["geom_lat"] = [f["geometry"]["y"] for f in feats]
    df["name"] = df["name1"].fillna(df.get("name")).astype(str).str.strip()
    df["official_id"] = df["maincode"].astype(str)
    df["stated_pcode"] = df["changwat"].map(PROV)
    cl = [
        classify_health_moph(
            r.typecode,
            r.level_,
            r.minname,
            r.name,
            r.status,
            tuple(cfg["moph_hospital_layers"]["higher_level_classes"]),
        )
        for r in df.itertuples()
    ]
    for k in (
        "source_native_type",
        "source_native_level",
        "facility_class",
        "class_basis",
        "class_confidence",
        "is_service_point",
        "is_active",
        "higher_level",
    ):
        df[k] = [c[k] for c in cl]
    df["capabilities_source_supported"] = ""
    g = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df["geom_lon"], df["geom_lat"]), crs="EPSG:4326"
    ).to_crs(CANONICAL)
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    a = gpd.GeoSeries(gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326").to_crs(CANONICAL)
    g["attr_lat_lon_vs_geometry_m"] = np.round(
        np.hypot(g["x"] - a.x.to_numpy(), g["y"] - a.y.to_numpy()), 1
    )
    g["geometry_attribute_conflict"] = (
        g["attr_lat_lon_vs_geometry_m"]
        > cfg["moph_hospital_layers"]["attribute_geometry_conflict_m"]
    )
    geoms = prov.set_index("adm1_pcode").geometry
    inside = pd.Series(
        [
            bool(p.within(geoms[sp])) if sp in geoms.index else False
            for p, sp in zip(g.geometry, g["stated_pcode"], strict=True)
        ],
        index=g.index,
    )
    aoi = pd.Series(g.geometry.within(prov.geometry.union_all()), index=g.index)
    g = pd.concat(
        [g, coordinate_flags(g["geom_lon"], g["geom_lat"], g["name"], cfg, aoi, inside)], axis=1
    )
    g["source_last_edited"] = [ms_date(v) for v in g["last_edited_date"]]
    g["source_record_date"] = pd.to_datetime(
        g["Last_update_infile"], format="%d/%m/%Y", errors="coerce"
    ).dt.date.astype(str)
    return g


def main() -> int:
    cfg = load_config()
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")[
        ["adm1_pcode", "geometry"]
    ]
    REVIEW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    m68, m69 = load_layer(RAW68, cfg, prov), load_layer(RAW69, cfg, prov)
    cit = gpd.read_file(PROCESSED.parent / "m2a" / "facilities.gpkg", layer="health_facilities")
    osm = gpd.read_file(M2A1 / "facilities.gpkg", layer="osm_health_current")

    # ---- primary layer: MoPH update68, de-duplicated by official id then identical name/location -------------
    keep = (
        m68.drop(columns="geometry")
        .rename(columns={"official_id": "oid"})
        .assign(source_id=lambda d: "moph68:" + d["oid"])
    )
    dd = deduplicate(keep, cfg["dedup"]["exact_duplicate_radius_m"], "oid")
    prim = gpd.GeoDataFrame(dd, geometry=gpd.points_from_xy(dd["x"], dd["y"]), crs=CANONICAL)
    prim = compose_primary(
        prim.rename(columns={"facility_id": "rec_id"}),
        SRC_MOPH,
        {"moph69": (m69, SRC_MOPH69), "citizeninfo": (cit, SRC_CIT), "osm": (osm, SRC_OSM)},
    ).rename(columns={"rec_id": "facility_id"})
    # field-level provenance (hybrid model): location from MoPH geometry; class from MoPH type/level fields
    prim["location_source"] = "MoPH PHER Hospital_update68 point geometry"
    prim["location_vintage"] = prim["source_last_edited"]
    prim["classification_source"] = np.where(
        prim["facility_class"].eq("UNKNOWN"), "NONE", "MoPH PHER Hospital_update68 typecode/level_"
    )
    prim["classification_freshness"] = np.where(
        prim["facility_class"].eq("UNKNOWN"), "UNRESOLVED", "CURRENT_SOURCE_FIELD"
    )

    # ---- reconcile with CITIZENinfo 2020 (name + location; HCODE and DGA ids do not map) --------------------
    cit_ok = cit[cit["coordinate_qa_status"] != "FAILED"]
    sv = prim[prim["is_service_point"] & (prim["coordinate_qa_status"] != "FAILED")]
    rec_cit = reconcile(sv.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], cit_ok.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], match_radius_m=cfg["reconcile"]["match_radius_m"], possible_radius_m=cfg["reconcile"]["possible_radius_m"], same_name_far_m=cfg["reconcile"]["same_name_far_m"], name_fn=health_comparison_name)  # fmt: skip
    rec_cit.insert(0, "pair", "MoPH_update68_2026_vs_CITIZENinfo_2020")
    cs = rec_cit[rec_cit["side"] == "current_side"].set_index("rec_id")
    # hybrid fallback: a MoPH record with no class but a matched CITIZENinfo class keeps location=current, class=STALE/partial
    cit_cls = cit.set_index("facility_id")["facility_class"]
    fb = 0
    for i, r in prim.iterrows():
        if (
            r["facility_class"] == "UNKNOWN"
            and r["facility_id"] in cs.index
            and cs.at[r["facility_id"], "status"] == "MATCHED"
        ):
            prim.at[i, "facility_class"] = cit_cls.get(
                cs.at[r["facility_id"], "counterpart_rec_id"], "UNKNOWN"
            )
            prim.at[i, "classification_source"] = "DGA CITIZENinfo 2020 (name-derived)"
            prim.at[i, "classification_freshness"] = "STALE_PARTIALLY_ASSESSED"
            fb += 1
    prim["citizeninfo_match_status"] = prim["facility_id"].map(cs["status"]).fillna("NOT_COMPARED")
    prim["citizeninfo_counterpart_class"] = [
        cit_cls.get(cs["counterpart_rec_id"].get(f), None) if f in cs.index else None
        for f in prim["facility_id"]
    ]
    prim["class_changed_vs_citizeninfo"] = [
        (c is not None and c != n and s == "MATCHED")
        for c, n, s in zip(
            prim["citizeninfo_counterpart_class"],
            prim["facility_class"],
            prim["citizeninfo_match_status"],
            strict=True,
        )
    ]

    # ---- cross-check update68 vs update69 by official id ------------------------------------------------------
    a, b = m68.set_index("official_id"), m69.set_index("official_id")
    both = a.index.intersection(b.index)
    dist = np.hypot(a.loc[both, "x"] - b.loc[both, "x"], a.loc[both, "y"] - b.loc[both, "y"])
    x69 = pd.DataFrame({
        "official_id": list(a.index.union(b.index)),
    })  # fmt: skip
    x69["status"] = np.where(
        x69["official_id"].isin(both),
        "MATCHED",
        np.where(x69["official_id"].isin(a.index), "ONLY_IN_UPDATE68", "ONLY_IN_UPDATE69"),
    )
    x69["name"] = [a["name"].get(i, b["name"].get(i)) for i in x69["official_id"]]
    x69["distance_m"] = x69["official_id"].map(dist)
    x69["coordinate_conflict"] = (
        x69["distance_m"] > cfg["moph_hospital_layers"]["attribute_geometry_conflict_m"]
    )
    x69["class_68"] = x69["official_id"].map(a["facility_class"])
    x69["class_69"] = x69["official_id"].map(b["facility_class"])
    x69["class_changed"] = x69["status"].eq("MATCHED") & (x69["class_68"] != x69["class_69"])
    x69.to_csv(REVIEW / "moph-update68-vs-update69.csv", index=False, encoding="utf-8-sig")

    # ---- OSM external cross-check -----------------------------------------------------------------------------
    osm_named = osm[osm["name"] != ""]
    rec_osm = reconcile(osm_named.rename(columns={"rec_id": "rec_id"})[["rec_id", "name", "x", "y"]], sv.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], match_radius_m=cfg["reconcile"]["match_radius_m"], possible_radius_m=cfg["reconcile"]["possible_radius_m"], same_name_far_m=cfg["reconcile"]["same_name_far_m"], name_fn=health_comparison_name)  # fmt: skip
    rec_osm.insert(0, "pair", "OSM_2026_vs_MoPH_update68_2026")
    pd.concat([rec_cit, rec_osm]).to_csv(
        REVIEW / "healthcare-source-reconciliation.csv", index=False, encoding="utf-8-sig"
    )

    # ---- write layers ------------------------------------------------------------------------------------------
    prim.to_file(OUT / "facilities.gpkg", layer="health_facilities", driver="GPKG")
    edu = gpd.read_file(M2A1 / "facilities.gpkg", layer="education_facilities")
    edu.to_file(
        OUT / "facilities.gpkg", layer="education_facilities", driver="GPKG"
    )  # unchanged: no current MOE register supplied
    qa = pd.concat(
        [
            prim.assign(source="MoPH_update68_2026")[
                [
                    "source",
                    "facility_id",
                    "name",
                    "coordinate_qa_status",
                    "coordinate_qa_flags",
                    "geometry_attribute_conflict",
                    "attr_lat_lon_vs_geometry_m",
                ]
            ]
        ]
    )
    qa[(qa["coordinate_qa_status"] != "PASS") | qa["geometry_attribute_conflict"]].to_csv(
        REVIEW / "facility-coordinate-qa.csv", index=False, encoding="utf-8-sig"
    )
    svc = prim[prim["is_service_point"]]
    summ = {
        "source_records_in_aoi_provinces": {"update68": len(m68), "update69": len(m69)},
        "primary_layer": {"records": len(prim), "service_points": len(svc), "non_service_points": int((~prim["is_service_point"]).sum()), "inactive": int((~prim["is_active"]).sum()), "merged_groups": int((prim["n_merged"] > 1).sum())},
        "classes": prim["facility_class"].value_counts().to_dict(),
        "class_basis": prim["class_basis"].value_counts().to_dict(),
        "classification_freshness": prim["classification_freshness"].value_counts().to_dict(),
        "hybrid_fallback_records": fb,
        "higher_level_hospitals": prim.loc[prim["higher_level"], "name"].tolist(),
        "location_vintage": {"max_source_last_edited": prim["source_last_edited"].max(), "record_dates_by_year": prim["source_record_date"].str[:4].value_counts().sort_index().to_dict()},
        "coordinate_qa": prim["coordinate_qa_status"].value_counts().to_dict(),
        "geometry_vs_attribute_conflicts_over_threshold": int(prim["geometry_attribute_conflict"].sum()),
        "vs_citizeninfo": summarise(rec_cit),
        "vs_osm": summarise(rec_osm),
        "class_changes_vs_citizeninfo_matched": int(prim["class_changed_vs_citizeninfo"].sum()),
        "update68_vs_update69": {"matched": int((x69.status == "MATCHED").sum()), "only_68": int((x69.status == "ONLY_IN_UPDATE68").sum()), "only_69": int((x69.status == "ONLY_IN_UPDATE69").sum()), "coordinate_conflicts": int(x69["coordinate_conflict"].sum()), "class_changed": int(x69["class_changed"].sum())},
        "hospital_level": "AVAILABLE_FROM_PUBLIC_MOPH_POINT_LAYER_NOT_HCODE: typecode/level_ are source fields; capabilities (emergency, trauma, ICU, specialists) are NOT stated and NOT assigned",
        "education": "UNCHANGED from M2A.1: no current MOE register supplied (SOURCE_EXISTS_AGENT_BLOCKED; manual import path ready)",
    }  # fmt: skip
    (REVIEW / "health-refresh-summary.json").write_text(
        json.dumps(summ, indent=2, ensure_ascii=False, default=str) + "\n", "utf-8"
    )
    rec = ProvenanceRecord(
        artifact_id="m2a2-health_facilities", artifact_path=f"{(OUT / 'facilities.gpkg').as_posix()}#health_facilities", code_version=current_code_version(),
        sources=[source_ref("facility-moph-hospital-update68", original_crs="EPSG:4326"), source_ref("facility-moph-hospital-update69", original_crs="EPSG:4326"), source_ref("health-citizeninfo-dga", original_crs="EPSG:4326"), source_ref("osm-facilities-aoi", original_crs="EPSG:4326")],
        normalized_crs=CANONICAL, method="MoPH public hospital point layer (update68) as PRIMARY; class from source typecode/level_; update69/CITIZENinfo/OSM as cross-checks; field-level provenance for location and classification.",
        spatial_resolution="point", confidence=Confidence.MEDIUM,
        limitations=["Public MoPH GIS layer, not an HCODE export; no licence statement on the service.", "Layer geometry and attribute lat/lon disagree by >100 m for a third of records (flagged; geometry used because it agrees better with an independent source).", "No capability (emergency/trauma/ICU/specialist) is stated or assigned.", "Education layer unchanged (no current MOE register)."],
    )  # fmt: skip
    side = OUT / "provenance" / "facilities.health_facilities.provenance.json"
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(rec.to_json() + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=1, ensure_ascii=False, default=str)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
