"""M2A: normalise, classify, QA and de-duplicate education institutions and health facilities.

Outputs data/processed/m2a/facilities.gpkg (layers education_facilities, health_facilities) in EPSG:32647
plus outputs/m2a-review/facility-qa.csv and facility-summary.json. Coordinates are never corrected.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, PROVINCE_NAMES, source_ref

from hearthmap.enums import Confidence
from hearthmap.family import (
    classify_education,
    classify_health,
    coordinate_flags,
    deduplicate,
    freshness,
    load_config,
)
from hearthmap.family.config import load_reference_levels
from hearthmap.provenance import ProvenanceRecord, current_code_version

OUT = Path("data/processed/m2a")
REVIEW = Path("outputs/m2a-review")
PCODE_BY_NUM = {"50": "TH50", "56": "TH56", "57": "TH57"}
PROV_TEXT = {"เชียงใหม่": "TH50", "พะเยา": "TH56", "เชียงราย": "TH57"}


def provinces() -> gpd.GeoDataFrame:
    return gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")[
        ["adm1_pcode", "geometry"]
    ]


def to_points(df: pd.DataFrame, lon: str, lat: str) -> gpd.GeoDataFrame:
    ok = df[lon].notna() & df[lat].notna()
    g = gpd.GeoDataFrame(
        df, geometry=gpd.points_from_xy(df[lon].where(ok), df[lat].where(ok)), crs="EPSG:4326"
    )
    g.loc[~ok, "geometry"] = None
    return g.to_crs(CANONICAL)


def membership(
    g: gpd.GeoDataFrame, prov: gpd.GeoDataFrame, stated: pd.Series | None
) -> tuple[pd.Series, pd.Series | None]:
    aoi = prov.geometry.union_all()
    inside_aoi = g.geometry.within(aoi).fillna(False)
    if stated is None:
        return inside_aoi, None
    geoms = prov.set_index("adm1_pcode").geometry
    ins = pd.Series(
        [
            bool(pt is not None and sp in geoms.index and pt.within(geoms[sp])) if sp else True
            for pt, sp in zip(g.geometry, stated, strict=True)
        ],
        index=g.index,
    )
    return inside_aoi, ins


def education(cfg, prov) -> gpd.GeoDataFrame:
    rows = []
    for p in ("chiang-mai", "chiang-rai", "phayao"):
        path = Path("data/raw/places-dopa-gis02/download-2026-10-16") / f"dopa_gis02_{p}.json"
        for i, r in enumerate(json.loads(path.read_text("utf-8"))):
            if str(r.get("gov_office_id")) != "2":
                continue
            rows.append({
                "source_id": f"dopa:{p}:{i}", "name": str(r.get("oct_side01_name") or "").strip(),
                "native_subcode": str(r.get("gov_sub_office_id")), "stated_pcode": PCODE_BY_NUM.get(str(r.get("pcode"))),
                "tcode": r.get("tcode"), "lat": pd.to_numeric(r.get("oct_side01_lat"), errors="coerce"),
                "lon": pd.to_numeric(r.get("oct_side01_lon"), errors="coerce"), "source_budget_year_be": r.get("budget_id"),
            })  # fmt: skip
    df = pd.DataFrame(rows)
    cls = [
        classify_education(n, s, cfg) for n, s in zip(df["name"], df["native_subcode"], strict=True)
    ]
    df["levels"] = ["|".join(c["levels"]) for c in cls]
    for k in ("kind", "level_basis", "level_confidence"):
        df[k] = [c[k] for c in cls]
    df["levels_derived"] = True
    g = to_points(df, "lon", "lat")
    inside_aoi, inside_prov = membership(g, prov, g["stated_pcode"])
    flags = coordinate_flags(g["lon"], g["lat"], g["name"], cfg, inside_aoi, inside_prov)
    g = pd.concat([g, flags], axis=1)
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    return g


def health(cfg, prov, ref) -> gpd.GeoDataFrame:
    raw = pd.read_csv(
        Path("data/raw/health-citizeninfo-dga/download-2026-10-16/citizeninfo_health_20200314.csv"),
        encoding="utf-8-sig",
        dtype={"รหัสหน่วยงาน": str},
    )
    raw.columns = [
        "official_id",
        "ministry",
        "department",
        "name",
        "pin_ok_flag",
        "address",
        "lat",
        "lon",
    ]
    text = raw["name"].fillna("") + " " + raw["address"].fillna("")
    # the stated province must follow an explicit "จังหวัด"/"จ." marker: a hospital NAME may contain a province word
    # (e.g. "โรงพยาบาลศรีเชียงใหม่ จังหวัดหนองคาย" is in Nong Khai)
    stated = text.map(
        lambda t: next(
            (v for k, v in PROV_TEXT.items() if re.search(rf"(จังหวัด|จ\.)\s*{k}", t)), None
        )
    )
    df = raw[stated.notna()].copy()
    df["stated_pcode"] = stated[stated.notna()]
    df["source_id"] = ["citizeninfo:" + str(i) for i in df.index]
    cls = [
        classify_health(n, o, m, d, cfg, ref)
        for n, o, m, d in zip(
            df["name"], df["official_id"], df["ministry"], df["department"], strict=True
        )
    ]
    for k in ("facility_class", "class_basis", "class_confidence"):
        df[k] = [c[k] for c in cls]
    df["capabilities_source_supported"] = ""
    g = to_points(df, "lon", "lat")
    inside_aoi, inside_prov = membership(g, prov, g["stated_pcode"])
    flags = coordinate_flags(g["lon"], g["lat"], g["name"], cfg, inside_aoi, inside_prov)
    flags.loc[df["pin_ok_flag"].eq("N").to_numpy(), "coordinate_qa_status"] = "FAILED"
    g = pd.concat([g, flags], axis=1)
    g["x"], g["y"] = g.geometry.x, g.geometry.y
    return g


def dedupe(g: gpd.GeoDataFrame, radius: float, official_id_col: str | None) -> gpd.GeoDataFrame:
    keep = g.drop(columns="geometry")
    d = deduplicate(keep, radius, official_id_col)
    geom = gpd.points_from_xy(d["x"], d["y"])
    return gpd.GeoDataFrame(d, geometry=geom, crs=CANONICAL)


def prov_record(layer: str, sources, method: str, limits: list[str], conf: Confidence) -> None:
    rec = ProvenanceRecord(
        artifact_id=f"m2a-{layer}", artifact_path=f"{(OUT / 'facilities.gpkg').as_posix()}#{layer}", code_version=current_code_version(),
        sources=sources, normalized_crs=CANONICAL, method=method, spatial_resolution="point", confidence=conf, limitations=limits,
    )  # fmt: skip
    side = OUT / "provenance" / f"facilities.{layer}.provenance.json"
    side.parent.mkdir(parents=True, exist_ok=True)
    side.write_text(rec.to_json() + "\n", encoding="utf-8")


def main() -> int:
    cfg = load_config()
    prov = provinces()
    ref = load_reference_levels()
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    edu_raw, hl_raw = education(cfg, prov), health(cfg, prov, ref)
    r = cfg["dedup"]["same_institution_radius_m"]
    edu = dedupe(edu_raw, r, None)
    hl = dedupe(hl_raw, cfg["dedup"]["exact_duplicate_radius_m"], "official_id")
    edu_fresh = freshness(
        **{
            k: v
            for k, v in cfg["freshness"]["sources"]["education_dopa_gis02"].items()
            if k != "basis"
        },
        verification_date=cfg["freshness"]["verification_date"],
        stale_after_years=cfg["freshness"]["stale_after_years"],
    )
    hl_fresh = freshness(
        **{
            k: v
            for k, v in cfg["freshness"]["sources"]["health_citizeninfo"].items()
            if k != "basis"
        },
        verification_date=cfg["freshness"]["verification_date"],
        stale_after_years=cfg["freshness"]["stale_after_years"],
    )
    for t, f in ((edu, edu_fresh), (hl, hl_fresh)):
        for k, v in f.items():
            t[k] = v
    for lay, g in (("education_facilities", edu), ("health_facilities", hl)):
        g.to_file(OUT / "facilities.gpkg", layer=lay, driver="GPKG")
    prov_record(
        "education_facilities",
        [source_ref("places-dopa-gis02", original_crs="EPSG:4326")],
        "DOPA gis-02 filtered to gov_office_id 2 (education); levels derived from names/sub-codes (marked DERIVED); coordinate QA flags only; deterministic de-duplication.",
        [
            "Budget year 2564 (BE) - STALE.",
            "No authoritative level field; levels derived and confidence-qualified.",
            "Private/foreign schools only if DOPA lists them; MOE register unreachable.",
        ],
        Confidence.LOW,
    )
    prov_record(
        "health_facilities",
        [source_ref("health-citizeninfo-dga", original_crs="EPSG:4326")],
        "DGA CITIZENinfo government health facilities within the three provinces (stated in name/address); class from name/ministry only; capabilities never inferred.",
        [
            "File dated 2020-03-14 - STALE.",
            "Government facilities only (no private hospitals/clinics).",
            "No service-level (regional/general/community) field.",
        ],
        Confidence.LOW,
    )
    # QA table + summary
    qa = pd.concat([
        edu.assign(domain="education")[["domain", "facility_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]],
        hl.assign(domain="health")[["domain", "facility_id", "name", "coordinate_qa_status", "coordinate_qa_flags"]],
    ])  # fmt: skip
    qa[qa["coordinate_qa_status"] != "PASS"].to_csv(
        REVIEW / "facility-coordinate-qa.csv", index=False, encoding="utf-8-sig"
    )
    summ = {
        "education": {"source_records_gov_office_2": len(edu_raw), "institutions_after_dedup": len(edu), "merged_groups": int((edu["n_merged"] > 1).sum()), "by_kind": edu["kind"].value_counts().to_dict(), "levels": edu["levels"].value_counts().to_dict(), "qa_status": edu["coordinate_qa_status"].value_counts().to_dict(), "freshness": edu_fresh},
        "health": {"source_records_in_three_provinces": len(hl_raw), "facilities_after_dedup": len(hl), "merged_groups": int((hl["n_merged"] > 1).sum()), "by_class": hl["facility_class"].value_counts().to_dict(), "qa_status": hl["coordinate_qa_status"].value_counts().to_dict(), "freshness": hl_fresh},
        "province_names": PROVINCE_NAMES,
    }  # fmt: skip
    (REVIEW / "facility-summary.json").write_text(
        json.dumps(summ, indent=2, ensure_ascii=False, default=str) + "\n", "utf-8"
    )
    print(json.dumps(summ, indent=1, ensure_ascii=False, default=str)[:3500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
