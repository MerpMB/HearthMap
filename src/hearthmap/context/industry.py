# ruff: noqa: E501
"""Industrial and mining context: DIW registers (tambon level), OSM land-use features (located), DPIM concessions (province/tambon level).

None of these sources is a nuisance measurement. A register entry says a factory/concession is recorded; an OSM polygon says land is tagged industrial or quarry.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

import pandas as pd
import shapely

AOI_PROVINCES_TH = {"เชียงใหม่": "TH50", "พะเยา": "TH56", "เชียงราย": "TH57"}
# DIW "รหัสประเภท" codes for extraction / stone / aggregate related operations (type-level facts, not status)
DIW_EXTRACTION_CODES = {
    301: "STONE_CRUSHING_OR_GRINDING",
    302: "EARTH_SAND_GRAVEL_EXCAVATION",
    303: "SAND_GRAVEL_SCREENING",
    304: "SAND_DREDGING",
}
DIW_STONE_PRODUCT_CODES = {
    5801: "CONCRETE_OR_GYPSUM_PRODUCTS",
    5803: "STONE_PRODUCTS",
    5703: "CEMENT_OR_LIME_MIXING",
}
OSM_INDUSTRY_SELECTORS = ("landuse=quarry", "landuse=industrial", "man_made=works", "industrial")


def _tambon_key(prov: Any, amphoe: Any, tambon: Any) -> str:
    def clean(x: Any, prefix: str) -> str:
        s = re.sub(r"\s+", "", str(x))
        return s[len(prefix) :] if s.startswith(prefix) else s

    return f"{clean(prov, 'จังหวัด')}|{clean(amphoe, 'อำเภอ')}|{clean(tambon, 'ตำบล')}"


def load_diw(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Normalise DIW registers (keyed by source file stem) to the three AOI provinces; one row per DIW fid.

    The registers carry NO coordinates and NO operating-status field: location is the address (tambon) and the
    date is the licence year (Buddhist era). Both are kept as stated and neither is turned into 'currently operating'.
    """
    parts = []
    for stem, df in frames.items():
        d = df[df["จังหวัด"].isin(AOI_PROVINCES_TH)].copy()
        d["source_file"] = stem
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    waste_fids = set(d.loc[d["source_file"] == "factype101-105-106", "fid"])
    d = d.sort_values(["fid", "source_file"]).drop_duplicates("fid", keep="first").copy()
    code = pd.to_numeric(d["รหัสประเภท"], errors="coerce")
    out = pd.DataFrame(
        {
            "diw_fid": d["fid"].astype("int64").astype(str),
            "province_pcode": d["จังหวัด"].map(AOI_PROVINCES_TH),
            "tambon_key": [
                _tambon_key(p, a, t)
                for p, a, t in zip(d["จังหวัด"], d["อำเภอ"], d["ตำบล"], strict=True)
            ],
            "factory_class": pd.to_numeric(d["จำพวก"], errors="coerce").astype("Int64"),
            "type_code": code.astype("Int64"),
            "type_name_th": d["ประเภทโรงงาน"],
            "licence_year_be": pd.to_numeric(d["ปีที่อนุญาต"], errors="coerce").astype("Int64"),
            "workers": pd.to_numeric(d["คนงานรวม"], errors="coerce"),
            "horsepower": pd.to_numeric(d["แรงม้า"], errors="coerce"),
            "industry_group_th": d.get("หมวดอุตสาหกรรม"),
        }
    )
    out["licence_year_ce"] = out["licence_year_be"] - 543
    out["is_waste_or_recycling"] = out["diw_fid"].isin({str(int(x)) for x in waste_fids})
    out["extraction_type"] = out["type_code"].map(DIW_EXTRACTION_CODES)
    out["stone_product_type"] = out["type_code"].map(DIW_STONE_PRODUCT_CODES)
    out["record_status"] = (
        "UNKNOWN"  # no row-level status field; inclusion semantics are source-level and documented separately
    )
    out["row_level_status_field"] = "ABSENT"
    out["source_context"] = "OUTSIDE_INDUSTRIAL_ESTATES_CLOSURE_EXCLUSION_NOT_DOCUMENTED"
    out["coordinates"] = "NOT_PROVIDED_BY_REGISTER"
    return out.reset_index(drop=True)


def osm_industry_frame(payload: dict[str, Any], province: str) -> pd.DataFrame:
    """OSM industrial-type features with centre and rough bounding-box extent (m2, a diagnostic only)."""
    rows = []
    for e in payload["elements"]:
        t = e.get("tags", {})
        kind = (
            "OSM_QUARRY" if t.get("landuse") == "quarry"
            else "OSM_INDUSTRIAL_LANDUSE" if t.get("landuse") == "industrial"
            else "OSM_WORKS" if t.get("man_made") == "works"
            else "OSM_INDUSTRIAL_OTHER" if "industrial" in t
            else None
        )  # fmt: skip
        b = e.get("bounds")
        if e.get("center"):
            c = e["center"]
        elif b:  # `out bb` replaces `center`: use the bounding-box midpoint (a way/relation centre)
            c = {"lat": (b["minlat"] + b["maxlat"]) / 2, "lon": (b["minlon"] + b["maxlon"]) / 2}
        else:
            c = e
        if kind is None or "lat" not in c:
            continue
        diag = (
            round(
                math.hypot(
                    (b["maxlat"] - b["minlat"]) * 111_000,
                    (b["maxlon"] - b["minlon"]) * 111_000 * math.cos(math.radians(c["lat"])),
                )
            )
            if b
            else 0
        )
        rows.append(
            {
                "osm_id": f"{e['type'][0]}{e['id']}", "province": province, "lon": c["lon"], "lat": c["lat"], "kind": kind,
                "industrial_tag": t.get("industrial", ""), "resource": t.get("resource", ""), "lifecycle_tag": next((k for k in t if k.startswith(("disused", "abandoned", "construction"))), ""),
                "has_bounds": b is not None, "bbox_diagonal_m": diag, "name": t.get("name", ""),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def _kind(t: dict[str, str]) -> str | None:
    return (
        "OSM_QUARRY" if t.get("landuse") == "quarry"
        else "OSM_INDUSTRIAL_LANDUSE" if t.get("landuse") == "industrial"
        else "OSM_WORKS" if t.get("man_made") == "works"
        else "OSM_INDUSTRIAL_OTHER" if "industrial" in t
        else None
    )  # fmt: skip


def osm_industry_geometries(payload: dict[str, Any], province: str) -> pd.DataFrame:
    """OSM industrial-type features as real geometries (lon/lat) with an explicit geometry class.

    POINT, POLYGON (closed way or assembled multipolygon) or LINE (an unclosed way: kept, never counted as an area).
    Point and polygon features are different evidence and must never be summed into one comparable count.
    """
    rows = []
    for e in payload["elements"]:
        t = e.get("tags", {})
        kind = _kind(t)
        if kind is None:
            continue
        geom = None
        if e["type"] == "node":
            geom = shapely.Point(e["lon"], e["lat"])
        elif e["type"] == "way" and e.get("geometry"):
            pts = [(g["lon"], g["lat"]) for g in e["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                geom = shapely.Polygon(pts)
            elif len(pts) >= 2:
                geom = shapely.LineString(pts)
        elif e["type"] == "relation":
            lines = [
                shapely.LineString([(g["lon"], g["lat"]) for g in m["geometry"]])
                for m in e.get("members", [])
                if m.get("geometry") and len(m["geometry"]) >= 2 and m.get("role") in ("outer", "")
            ]
            polys = list(shapely.polygonize(lines)) if lines else []
            if polys:
                geom = shapely.unary_union(polys)
        if geom is None or geom.is_empty:
            continue
        if not geom.is_valid:
            geom = geom.buffer(0)
        cls = (
            "POINT"
            if geom.geom_type == "Point"
            else "POLYGON"
            if geom.geom_type in ("Polygon", "MultiPolygon")
            else "LINE"
        )
        rows.append(
            {
                "osm_id": f"{e['type'][0]}{e['id']}", "province": province, "kind": kind, "geometry_class": cls, "geometry": geom,
                "lifecycle_tag": next((k for k in t if k.startswith(("disused", "abandoned", "construction"))), ""),
                "name": t.get("name", ""),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def dpim_current(payload: dict[str, Any], today: date) -> pd.DataFrame:
    """Current DPIM open-API concession records (province level; PII was removed before storage).

    Status is stated as flags + dates. ACTIVE_BY_DATE only means expire_dt >= today; it is not an operating statement.
    """
    d = pd.DataFrame(payload["detail"]["data"])
    for c in ("approve_dt", "effective_dt", "expire_dt"):
        d[c] = pd.to_datetime(d[c] if c in d else pd.Series(pd.NaT, index=d.index), errors="coerce")
    d["area_rai"] = (
        pd.to_numeric(d["rai"], errors="coerce").fillna(0)
        + pd.to_numeric(d["ngan"], errors="coerce").fillna(0) / 4
        + pd.to_numeric(d["wa"], errors="coerce").fillna(0) / 400
    )
    revoked = d["wid_concession_flag"].ne("N") | d["sur_concession_flag"].ne("N")
    d["date_status"] = "DATE_MISSING"
    has = d["expire_dt"].notna()
    d.loc[has & (d["expire_dt"] >= pd.Timestamp(today)), "date_status"] = "UNEXPIRED_BY_DATE"
    d.loc[has & (d["expire_dt"] < pd.Timestamp(today)), "date_status"] = "EXPIRED_BY_DATE"
    d.loc[revoked, "date_status"] = "REVOKED_OR_SURRENDERED_FLAG"
    return d[d["province_code"].isin(["50", "56", "57"])].reset_index(drop=True)


def dpim_legacy(df: pd.DataFrame) -> pd.DataFrame:
    """The 2016-06-21 concession snapshot at tambon level. LEGACY_CONTEXT only: a 2016 status is not a 2026 status."""
    d = df[df["จังหวัด"].isin(AOI_PROVINCES_TH)].copy()
    out = pd.DataFrame(
        {
            "tambon_key": [
                _tambon_key(p, a, t)
                for p, a, t in zip(d["จังหวัด"], d["อำเภอ"], d["ตำบล"], strict=True)
            ],
            "province_pcode": d["จังหวัด"].map(AOI_PROVINCES_TH),
            "mineral_th": d["ชนิดแร่"],
            "legacy_status_th": d["สถานะประทานบัตร"],
            "area_rai": pd.to_numeric(d["พื้นที่ (ไร่)"], errors="coerce"),
        }
    )
    out["evidence_class"] = "LEGACY_CONTEXT"
    return out.reset_index(drop=True)


STONE_STATUS_EN = {
    "เปิดการ": "OPENED_REGISTER_STATUS",
    "หยุดการ": "HALTED_REGISTER_STATUS",
    "ต่ออายุ": "RENEWED_REGISTER_STATUS",
    "สิ้นอายุ": "EXPIRED_REGISTER_STATUS",
    "จำหน่ายทะเบียน": "DEREGISTERED_REGISTER_STATUS",
    "รอแจ้งประกอบกิจการ": "AWAITING_OPERATION_NOTICE_REGISTER_STATUS",
}
CONCESSION_STATUS_EN = {
    "มีอายุ": "UNEXPIRED_REGISTER_STATUS",
    "ต่ออายุ": "RENEWED_REGISTER_STATUS",
    "สิ้นอายุ": "EXPIRED_REGISTER_STATUS",
}


def _be_date(v: Any) -> pd.Timestamp:
    """dd/mm/yyyy in the Buddhist era to a Timestamp (NaT when missing or out of range)."""
    if not v:
        return pd.NaT
    try:
        d, m, y = (int(x) for x in str(v).split("/"))
        return pd.Timestamp(year=y - 543, month=m, day=d)
    except (ValueError, OverflowError):
        return pd.NaT


def dpim_export_frame(payload: dict[str, Any], kind: str) -> pd.DataFrame:
    """Flatten a DPIM licence export (kind: 'stone' or 'concession') to one row per licence at TAMBON resolution.

    LICENCE_STATUS is a register status and is never turned into a current operating status; the expiry date and the
    status are kept as separate fields because they can disagree.
    """
    rows = []
    for prov, block in payload["provinces"].items():
        for r in block["records"]:
            rows.append(
                {
                    **r,
                    "province_code": r.get("province_code")
                    or r.get("location_province_codd")
                    or prov,
                }
            )
    d = pd.DataFrame(rows)
    if kind == "stone":
        d = d.rename(
            columns={
                "factory_no": "licence_no",
                "factory_status": "status_th",
                "effective_date": "effective_be",
                "expire_date": "expire_be",
            }
        )
        status_map = STONE_STATUS_EN
    else:
        d = d.rename(
            columns={
                "concessionNo": "licence_no",
                "concession_status": "status_th",
                "approve_dt": "effective_be",
                "expireDt": "expire_be",
            }
        )
        status_map = CONCESSION_STATUS_EN
    d["status_vocab"] = (
        d["status_th"]
        .map(status_map)
        .where(d["status_th"].notna(), "STATUS_MISSING_IN_SOURCE")
        .fillna("UNMAPPED_REGISTER_STATUS")
    )
    d["effective_date"] = d["effective_be"].map(_be_date)
    d["expire_date"] = d["expire_be"].map(_be_date)
    d["tambon_pcode"] = "TH" + d["tumbon_codes"].astype(str)
    d["spatial_resolution"] = "TAMBON_ADMINISTRATIVE"
    d["is_current_operating_status"] = (
        False  # a licence status never proves the plant or mine operates today
    )
    return d.reset_index(drop=True)
