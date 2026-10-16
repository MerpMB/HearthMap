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
    out["operating_status"] = "NOT_PROVIDED_BY_REGISTER"
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
