# ruff: noqa: E501
"""M2A.1: refresh facility layers with authoritative classification and reconcile sources.

Roles (the MOE current register and the MoPH HCODE data were NOT reachable/lawfully accessible):
  education  DOPA gis-02 (2021)  FALLBACK primary layer (stale)   |  OBEC list (2020) AUTHORITATIVE_CLASSIFICATION
             OSM (2026)          CURRENT_VALIDATION only
  health     CITIZENinfo (2020)  FALLBACK primary layer (stale)   |  OSM (2026)       CURRENT_VALIDATION only
Nothing is unioned into the primary layers; every comparison keeps its evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, source_ref

from hearthmap.enums import Confidence
from hearthmap.family import classify_education, coordinate_flags, load_config
from hearthmap.family.reconcile import (
    FacilitySource,
    compose_primary,
    health_comparison_name,
    reconcile,
    summarise,
)
from hearthmap.family.taxonomy import levels_from_class_range, resolve_levels
from hearthmap.provenance import ProvenanceRecord, current_code_version

M2A = Path("data/processed/m2a")
OUT = Path("data/processed/m2a1")
REVIEW = Path("outputs/m2a1-review")
PROV_TH = {"เชียงใหม่": "TH50", "พะเยา": "TH56", "เชียงราย": "TH57"}
OBEC_RAW = Path("data/raw/education-obec-school-list/api-2026-10-16/OBEC_SCHOOL_007.json")
OSM_RAW = Path("data/raw/osm-facilities-aoi/api-2026-10-16")
SRC_EDU = FacilitySource("DOPA gis-02 (budget year 2564)", 2021, "FALLBACK", current=False)
SRC_HEALTH = FacilitySource("DGA CITIZENinfo (2020-03-14)", 2020, "FALLBACK", current=False)
SRC_OBEC = FacilitySource(
    "OBEC school list OBEC_SCHOOL_007 (academic year 2563)",
    2020,
    "AUTHORITATIVE_CLASSIFICATION",
    current=False,
)
SRC_OSM = FacilitySource(
    "OpenStreetMap facilities (2026-10-16)", 2026, "CURRENT_VALIDATION", current=True
)


def pts(df: pd.DataFrame, lon: str, lat: str) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs="EPSG:4326").to_crs(
        CANONICAL
    )
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    return g


def load_obec(prov: gpd.GeoDataFrame, cfg) -> gpd.GeoDataFrame:
    d = [r for r in json.loads(OBEC_RAW.read_text("utf-8")) if r["province"] in PROV_TH]
    df = pd.DataFrame(d)
    df["rec_id"] = "obec:" + df["moeCode"].astype(str)
    df["name"] = df["schoolName"]
    df["stated_pcode"] = df["province"].map(PROV_TH)
    df["lat"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["lon"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["native_levels"] = df["classMinLevel"].astype(str) + "-" + df["classMaxLevel"].astype(str)
    df["authoritative_levels"] = [
        levels_from_class_range(a, b)
        for a, b in zip(df["classMinLevel"], df["classMaxLevel"], strict=True)
    ]
    g = pts(df, "lon", "lat")
    geoms = prov.set_index("adm1_pcode").geometry
    inside = pd.Series(
        [bool(p.within(geoms[sp])) for p, sp in zip(g.geometry, g["stated_pcode"], strict=True)],
        index=g.index,
    )
    aoi = pd.Series(g.geometry.within(prov.geometry.union_all()), index=g.index)
    g = pd.concat([g, coordinate_flags(g["lon"], g["lat"], g["name"], cfg, aoi, inside)], axis=1)
    return g


def load_osm(prov: gpd.GeoDataFrame, cfg) -> gpd.GeoDataFrame:
    rows = []
    for f in sorted(OSM_RAW.glob("*_facilities.json")):
        for e in json.loads(f.read_text("utf-8"))["elements"]:
            c = e if e["type"] == "node" else e.get("center")
            if not c:
                continue
            t = e.get("tags", {})
            rows.append(
                {
                    "rec_id": f"osm:{e['type'][0]}{e['id']}",
                    "name": t.get("name") or t.get("name:th") or "",
                    "amenity": t.get("amenity"),
                    "healthcare": t.get("healthcare"),
                    "operator_type": t.get("operator:type"),
                    "emergency": t.get("emergency"),
                    "lat": c["lat"],
                    "lon": c["lon"],
                }
            )
    g = pts(pd.DataFrame(rows).drop_duplicates("rec_id"), "lon", "lat")
    aoi = pd.Series(g.geometry.within(prov.geometry.union_all()), index=g.index)
    g = pd.concat(
        [
            g,
            coordinate_flags(
                g["lon"], g["lat"], g["name"].replace("", np.nan).fillna("?"), cfg, aoi, None
            ),
        ],
        axis=1,
    )
    return g


def main() -> int:
    cfg = load_config()
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")[
        ["adm1_pcode", "geometry"]
    ]
    REVIEW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    edu = gpd.read_file(M2A / "facilities.gpkg", layer="education_facilities")
    hl = gpd.read_file(M2A / "facilities.gpkg", layer="health_facilities")
    obec, osm = load_obec(prov, cfg), load_osm(prov, cfg)
    osm_edu = osm[
        osm["amenity"].isin(["school", "kindergarten", "childcare", "college", "university"])
    ].copy()
    gov_names = ("โรงพยาบาลส่งเสริมสุขภาพตำบล", "รพ.สต", "ศูนย์สุขภาพชุมชน", "โรงพยาบาล")
    osm_hl = osm[
        (osm["amenity"] == "hospital")
        | (osm["healthcare"] == "hospital")
        | osm["name"].fillna("").str.contains("|".join(gov_names), regex=True)
    ].copy()
    osm_hl_other = int(
        len(
            osm[
                osm["amenity"].isin(["clinic", "doctors"])
                | osm["healthcare"].isin(["clinic", "centre"])
            ]
        )
        - len(osm_hl[osm_hl["amenity"].isin(["clinic", "doctors"])])
    )

    # ---- education: DOPA primary layer enriched with OBEC authoritative classification ----------------
    base = compose_primary(
        edu.rename(columns={"facility_id": "rec_id"}),
        SRC_EDU,
        {"OBEC": (obec, SRC_OBEC), "OSM": (osm_edu, SRC_OSM)},
    ).rename(columns={"rec_id": "facility_id"})
    schools = base[(base["kind"] == "SCHOOL") & (base["coordinate_qa_status"] != "FAILED")]
    ob_ok = obec[obec["coordinate_qa_status"] != "FAILED"]
    rec_obec = reconcile(
        schools.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], ob_ok[["rec_id", "name", "x", "y"]],
        match_radius_m=cfg["reconcile"]["match_radius_m"], possible_radius_m=cfg["reconcile"]["possible_radius_m"], same_name_far_m=cfg["reconcile"]["same_name_far_m"],
    )  # fmt: skip
    rec_obec.insert(0, "pair", "DOPA_2021_vs_OBEC_2020")
    cs = rec_obec[rec_obec["side"] == "current_side"].set_index("rec_id")
    ob_idx = ob_ok.set_index("rec_id")
    methods, conf, norm_levels, native_levels, moe, affil, dxy, mstat = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for _, r in base.iterrows():
        d = classify_education(r["name"], r["native_subcode"], cfg)
        c = cs.loc[r["facility_id"]] if r["facility_id"] in cs.index else None
        auth = None
        nat = None
        m = None
        if c is not None and c["status"] == "MATCHED":
            m = ob_idx.loc[c["counterpart_rec_id"]]
            auth, nat = m["authoritative_levels"], m["native_levels"]
        res = resolve_levels(d, auth, nat)
        methods.append(res["normalization_method"])
        conf.append(res["normalization_confidence"])
        norm_levels.append("|".join(res["normalized_levels"]))
        native_levels.append(res["source_native_levels"])
        moe.append(m["moeCode"] if m is not None else None)
        affil.append(m["schoolType"] if m is not None else None)
        dxy.append(
            float(c["distance_m"])
            if c is not None and c["status"] in ("MATCHED", "CONFLICT")
            else np.nan
        )
        mstat.append(c["status"] if c is not None else "NOT_COMPARED_NOT_A_SCHOOL_OR_QA_FAILED")
    before = base["levels"].copy()
    base["source_native_type"] = base["native_subcode"]
    base["source_native_levels"] = native_levels
    base["normalized_levels"] = norm_levels
    base["normalization_method"] = methods
    base["normalization_confidence"] = conf
    base["levels"] = norm_levels  # consumed by the accessibility build
    base["levels_derived"] = [m.startswith("DERIVED") or m == "UNKNOWN" for m in methods]
    base["moe_school_code"] = moe
    base["obec_school_type"] = affil
    base["obec_match_status"] = mstat
    base["obec_coordinate_difference_m"] = np.round(dxy, 1)
    base["obec_coordinate_conflict"] = [s == "CONFLICT" for s in mstat]
    base["level_set_changed_vs_m2a"] = base["levels"] != before

    # ---- education vs OSM (current validation) ----------------------------------------------------
    inst = base[
        (
            base["kind"].isin(
                ["SCHOOL", "EARLY_CHILDHOOD_CENTRE", "VOCATIONAL_COLLEGE", "UNIVERSITY_OR_COLLEGE"]
            )
        )
        & (base["coordinate_qa_status"] != "FAILED")
    ]
    osm_named = osm_edu[osm_edu["name"] != ""]
    rec_osm_edu = reconcile(osm_named[["rec_id", "name", "x", "y"]], inst.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], match_radius_m=cfg["reconcile"]["match_radius_m"], possible_radius_m=cfg["reconcile"]["possible_radius_m"], same_name_far_m=cfg["reconcile"]["same_name_far_m"])  # fmt: skip
    rec_osm_edu.insert(0, "pair", "OSM_2026_vs_DOPA_2021")

    # ---- health: CITIZENinfo primary layer vs OSM current validation ------------------------------
    hbase = compose_primary(
        hl.rename(columns={"facility_id": "rec_id"}), SRC_HEALTH, {"OSM": (osm_hl, SRC_OSM)}
    ).rename(columns={"rec_id": "facility_id"})
    hbase["hospital_level_status"] = "PARTIALLY_ASSESSED_NO_ACCESSIBLE_AUTHORITATIVE_LEVEL_FIELD"
    hl_ok = hbase[hbase["coordinate_qa_status"] != "FAILED"]
    osm_hl_named = osm_hl[osm_hl["name"] != ""]
    rec_hl = reconcile(osm_hl_named[["rec_id", "name", "x", "y"]], hl_ok.rename(columns={"facility_id": "rec_id"})[["rec_id", "name", "x", "y"]], match_radius_m=cfg["reconcile"]["match_radius_m"], possible_radius_m=cfg["reconcile"]["possible_radius_m"], same_name_far_m=cfg["reconcile"]["same_name_far_m"], name_fn=health_comparison_name)  # fmt: skip
    rec_hl.insert(0, "pair", "OSM_2026_vs_CITIZENinfo_2020")

    # ---- outputs ---------------------------------------------------------------------------------
    for lay, g in (("education_facilities", base), ("health_facilities", hbase)):
        g.to_file(OUT / "facilities.gpkg", layer=lay, driver="GPKG")
    osm_hl.drop(columns=["geometry"]).assign(geometry=osm_hl.geometry).pipe(
        gpd.GeoDataFrame, crs=CANONICAL
    ).to_file(OUT / "facilities.gpkg", layer="osm_health_current", driver="GPKG")
    gpd.GeoDataFrame(osm_edu, crs=CANONICAL).to_file(
        OUT / "facilities.gpkg", layer="osm_education_current", driver="GPKG"
    )
    ob_only_ids = set(
        rec_obec[(rec_obec["side"] == "legacy_side") & (rec_obec["status"] == "LEGACY_ONLY")][
            "rec_id"
        ]
    )
    ob_ok[ob_ok["rec_id"].isin(ob_only_ids)].drop(columns=["authoritative_levels"]).assign(
        authoritative_levels=lambda d: d["native_levels"]
    ).to_file(OUT / "facilities.gpkg", layer="education_obec_only", driver="GPKG")
    pd.concat([rec_obec, rec_osm_edu]).to_csv(
        REVIEW / "education-source-reconciliation.csv", index=False, encoding="utf-8-sig"
    )
    rec_hl.to_csv(
        REVIEW / "healthcare-source-reconciliation.csv", index=False, encoding="utf-8-sig"
    )
    qa = pd.concat([
        base.assign(source="DOPA_2021", domain="education")[["source", "domain", "facility_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]].rename(columns={"facility_id": "rec_id"}),
        hbase.assign(source="CITIZENinfo_2020", domain="health")[["source", "domain", "facility_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]].rename(columns={"facility_id": "rec_id"}),
        obec.assign(source="OBEC_2020", domain="education")[["source", "domain", "rec_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]],
        osm.assign(source="OSM_2026", domain="mixed")[["source", "domain", "rec_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]],
    ])  # fmt: skip
    qa[qa["coordinate_qa_status"] != "PASS"].to_csv(
        REVIEW / "facility-coordinate-qa.csv", index=False, encoding="utf-8-sig"
    )
    qa_counts = qa.groupby(["source", "coordinate_qa_status"]).size().unstack(fill_value=0)
    qa_counts.to_csv(REVIEW / "facility-coordinate-qa-counts.csv")
    # classification before / after
    sch = base[base["kind"] == "SCHOOL"]
    cls = {
        "all_institutions": len(base),
        "schools": len(sch),
        "schools_authoritative": int(
            (sch["normalization_method"] == "AUTHORITATIVE_CLASS_RANGE").sum()
        ),
        "schools_derived": int(sch["normalization_method"].str.startswith("DERIVED").sum()),
        "schools_unknown": int((sch["normalization_method"] == "UNKNOWN").sum()),
        "schools_derived_default_primary_low": int(
            (sch["normalization_method"] == "DERIVED_DEFAULT_BASIC_SCHOOL_LEVEL_NOT_STATED").sum()
        ),
        "all_authoritative": int(
            (base["normalization_method"] == "AUTHORITATIVE_CLASS_RANGE").sum()
        ),
        "all_derived_or_unknown": int(base["levels_derived"].sum()),
        "level_sets_changed_vs_m2a": int(base["level_set_changed_vs_m2a"].sum()),
        "m2a_baseline_schools_derived": len(
            sch
        ),  # in M2A every school level was name/sub-code derived
    }
    summ = {
        "classification": cls,
        "education_obec": summarise(rec_obec), "education_osm": summarise(rec_osm_edu), "health_osm": summarise(rec_hl),
        "obec_records_in_aoi": len(obec), "obec_qa": obec["coordinate_qa_status"].value_counts().to_dict(),
        "osm_education_objects": len(osm_edu), "osm_education_unnamed": int((osm_edu["name"] == "").sum()),
        "osm_health_objects": len(osm_hl), "osm_health_unnamed": int((osm_hl["name"] == "").sum()), "osm_other_clinics_out_of_scope": osm_hl_other,
        "obec_only_schools": len(ob_only_ids), "obec_coordinate_conflicts": int(base["obec_coordinate_conflict"].sum()),
        "roles": {"education_primary": SRC_EDU.__dict__, "education_classification": SRC_OBEC.__dict__, "education_current_validation": SRC_OSM.__dict__, "health_primary": SRC_HEALTH.__dict__},
        "hospital_level": "PARTIALLY_ASSESSED: no lawfully accessible authoritative service-level field (HCODE is behind a bot challenge; not bypassed)",
    }  # fmt: skip
    (REVIEW / "facility-refresh-summary.json").write_text(
        json.dumps(summ, indent=2, ensure_ascii=False, default=str) + "\n", "utf-8"
    )
    for lay, srcs, method in (
        (
            "education_facilities",
            [
                source_ref("places-dopa-gis02", original_crs="EPSG:4326"),
                source_ref("education-obec-school-list", original_crs="EPSG:4326"),
                source_ref("osm-facilities-aoi", original_crs="EPSG:4326"),
            ],
            "DOPA primary (FALLBACK) layer; levels from OBEC class ranges where MATCHED (authoritative), else derived; OSM used only for validation.",
        ),
        (
            "health_facilities",
            [
                source_ref("health-citizeninfo-dga", original_crs="EPSG:4326"),
                source_ref("osm-facilities-aoi", original_crs="EPSG:4326"),
            ],
            "CITIZENinfo primary (FALLBACK) layer; OSM validation only; hospital level PARTIALLY_ASSESSED.",
        ),
    ):
        rec = ProvenanceRecord(artifact_id=f"m2a1-{lay}", artifact_path=f"{(OUT / 'facilities.gpkg').as_posix()}#{lay}", code_version=current_code_version(), sources=srcs, normalized_crs=CANONICAL, method=method, spatial_resolution="point", confidence=Confidence.LOW, limitations=["No current official register was accessible; primary layers remain STALE (2021 / 2020).", "Validation sources are not merged into primary layers."])  # fmt: skip
        side = OUT / "provenance" / f"facilities.{lay}.provenance.json"
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(rec.to_json() + "\n", encoding="utf-8")
    print(json.dumps(summ, indent=1, ensure_ascii=False, default=str)[:4500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
