"""Parsers that normalise the three historical-seismicity sources to one event schema.

The sources are NOT equivalent and are never merged or deduplicated here:

* ``geohazard-events-dmr``   DMR geohazard inventory, earthquake subset (M >= 3, curated)
* ``seismic-felt-events-tmd``  TMD "earthquakes affecting Thailand": chronicles and felt events
* ``seismicity-usgs-comcat``   USGS ComCat instrumental catalogue (international)

Common columns: source_id, event_id, event_year, event_time_utc, lat, lon, magnitude,
magnitude_kind (MAGNITUDE | MM_INTENSITY | None), depth_km, coords_available,
location_text, record_note.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

COLUMNS = [
    "source_id",
    "event_id",
    "event_year",
    "event_time_utc",
    "lat",
    "lon",
    "magnitude",
    "magnitude_kind",
    "depth_km",
    "coords_available",
    "location_text",
    "record_note",
]
_TH_MONTHS = {
    "มกราคม": 1,
    "กุมภาพันธ์": 2,
    "มีนาคม": 3,
    "เมษายน": 4,
    "พฤษภาคม": 5,
    "มิถุนายน": 6,
    "กรกฎาคม": 7,
    "สิงหาคม": 8,
    "กันยายน": 9,
    "ตุลาคม": 10,
    "พฤศจิกายน": 11,
    "ธันวาคม": 12,
    "ม.ค.": 1,
    "ก.พ.": 2,
    "มี.ค.": 3,
    "เม.ย.": 4,
    "พ.ค.": 5,
    "มิ.ย.": 6,
    "ก.ค.": 7,
    "ส.ค.": 8,
    "ก.ย.": 9,
    "ต.ค.": 10,
    "พ.ย.": 11,
    "ธ.ค.": 12,
}
_BE_OFFSET = 543
_DATE = re.compile(r"^\s*(\d{1,2})\s*([ก-๙.]+)\s*(\d{2,4})\s*$")
_BC = re.compile(r"^\s*(\d+)\s*ปี\s*ก่อน\s*ค\.ศ")
_BE_YEAR = re.compile(r"พ\.ศ\.\s*(\d{3,4})")
_LATLON = re.compile(r"([\d.]+)\s*°?\s*N\s*,?\s*([\d.]+)\s*°?\s*E", re.I)
_BARE_LATLON = re.compile(r"^\s*(\d{1,2}(?:\.\d+)?)\s+(\d{2,3}(?:\.\d+)?)\s*$")
_LEAD_FLOAT = re.compile(r"^\s*(\d+(?:\.\d+)?)")
_ROMAN = re.compile(r"^\s*([IVX]+)\s*(?:-\s*[IVX]+)?\s*MM", re.I)
_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10}


def _roman(s: str) -> int:
    total = 0
    for a, b in zip(s, [*s[1:], ""], strict=True):
        v = _ROMAN_VALUES[a]
        total += -v if b and _ROMAN_VALUES[b] > v else v
    return total


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def parse_tmd_date(text: str | None) -> tuple[int | None, tuple[int, int, int] | None, str]:
    """Return (year, (y, m, d) or None, precision) for a TMD Thai-text date."""
    if not text:
        return None, None, "UNPARSED"
    m = _DATE.match(text)
    if m and m.group(2) in _TH_MONTHS:
        y = int(m.group(3))
        if y < 100:  # two-digit Buddhist-era year (e.g. 51 -> 2551)
            y += 2500
        y = y - _BE_OFFSET if y > 2400 else y
        return y, (y, _TH_MONTHS[m.group(2)], int(m.group(1))), "DAY"
    b = _BC.match(text)
    if b:
        return -int(b.group(1)), None, "YEAR_BC_CHRONICLE"
    be = _BE_YEAR.search(text)
    if be:
        return int(be.group(1)) - _BE_OFFSET, None, "YEAR_CHRONICLE"
    return None, None, "UNPARSED"


def parse_tmd_magnitude(text: str | None) -> tuple[float, str | None]:
    """'5.1' -> (5.1, MAGNITUDE); 'VI MM' -> (6.0, MM_INTENSITY); else (nan, None)."""
    if not text:
        return np.nan, None
    t = text.strip()
    f = _LEAD_FLOAT.match(t)  # '5.3', '5.3 Mb', '7.3 IX MM' -> magnitude 5.3 / 5.3 / 7.3
    if f:
        return float(f.group(1)), "MAGNITUDE"
    m = _ROMAN.match(t)
    if m:
        return float(_roman(m.group(1).upper())), "MM_INTENSITY"
    return np.nan, None


def parse_tmd_statistics(path: Path | str) -> pd.DataFrame:
    """SpreadsheetML export of the TMD statistics page -> normalised events."""
    root = ET.parse(path).getroot()
    rows = []
    for ws in root.findall("ss:Worksheet", _NS):
        for tr in ws.iter(f"{{{_NS['ss']}}}Row"):
            rows.append(
                [
                    (c.find("ss:Data", _NS).text if c.find("ss:Data", _NS) is not None else None)
                    for c in tr.findall("ss:Cell", _NS)
                ]
            )
    if not rows or rows[0][:2] != ["DATE", "TIME"]:
        raise ValueError("unexpected TMD statistics layout (header row not DATE/TIME/...)")
    out = []
    for i, r in enumerate(rows[1:]):
        r = (r + [None] * 6)[:6]
        date_txt, time_txt, loc, ll, mi, _detail = r
        year, ymd, precision = parse_tmd_date(date_txt)
        mag, kind = parse_tmd_magnitude(mi)
        t = pd.NaT
        if ymd is not None and time_txt and re.match(r"^\d{2}:\d{2}:\d{2}$", time_txt.strip()):
            # only ISO-style times are converted; other time spellings leave the time unknown
            local = pd.Timestamp(*ymd, *map(int, time_txt.strip().split(":")))
            t = (local - pd.Timedelta(hours=7)).tz_localize("UTC")  # Thai local time -> UTC
        lat = lon = np.nan
        m = _LATLON.search(ll or "")
        fmt = "LATLON_NE"
        if not m:
            m, fmt = _BARE_LATLON.match(ll or ""), "BARE_ASSUMED_NE"
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if not (-5 <= lat <= 45 and 60 <= lon <= 140):  # implausible -> not a coordinate
                lat = lon = np.nan
                m = None
        out.append(
            {
                "source_id": "seismic-felt-events-tmd",
                "event_id": f"tmd-{i:04d}",
                "event_year": year,
                "event_time_utc": t,
                "lat": lat,
                "lon": lon,
                "magnitude": mag,
                "magnitude_kind": kind,
                "depth_km": np.nan,
                "coords_available": bool(m),
                "location_text": loc,
                "record_note": f"date_precision={precision};coord_format={fmt if m else 'NONE'}",
            }
        )
    return pd.DataFrame(out, columns=COLUMNS)


def parse_usgs_geojson(path: Path | str) -> pd.DataFrame:
    gj = json.loads(Path(path).read_text("utf-8"))
    out = []
    for f in gj["features"]:
        p, g = f["properties"], f["geometry"]["coordinates"]
        if p.get("type") != "earthquake" or p.get("mag") is None:
            continue
        t = pd.Timestamp(p["time"], unit="ms", tz="UTC")
        out.append(
            {
                "source_id": "seismicity-usgs-comcat",
                "event_id": f.get("id"),
                "event_year": t.year,
                "event_time_utc": t,
                "lat": g[1],
                "lon": g[0],
                "magnitude": float(p["mag"]),
                "magnitude_kind": "MAGNITUDE",
                "depth_km": g[2] if len(g) > 2 else np.nan,
                "coords_available": True,
                "location_text": p.get("place"),
                "record_note": f"magType={p.get('magType')};status={p.get('status')}",
            }
        )
    return pd.DataFrame(out, columns=COLUMNS) if out else _empty()


def parse_dmr_earthquakes(gdf: pd.DataFrame) -> pd.DataFrame:
    """Earthquake subset of the DMR geohazard-events layer (other event types ignored)."""
    q = gdf[gdf["Geohaz_E"] == "Earthquake"]
    out = []
    for _, r in q.iterrows():
        d = pd.to_datetime(r["DATE"], utc=True) if pd.notna(r["DATE"]) else pd.NaT
        depth = pd.to_numeric(r["DEPTH_KM"], errors="coerce")
        out.append(
            {
                "source_id": "geohazard-events-dmr",
                "event_id": f"dmr-{int(r['Event_ID'])}",
                "event_year": d.year if pd.notna(d) else None,
                "event_time_utc": d,
                "lat": r["LATITUDE"],
                "lon": r["LONGITUDE"],
                "magnitude": float(r["MAGNITUDE"]) if pd.notna(r["MAGNITUDE"]) else np.nan,
                "magnitude_kind": "MAGNITUDE" if pd.notna(r["MAGNITUDE"]) else None,
                "depth_km": depth,
                "coords_available": bool(pd.notna(r["LATITUDE"]) and pd.notna(r["LONGITUDE"])),
                "location_text": r.get("LOCATION"),
                "record_note": "DMR geohazard inventory",
            }
        )
    return pd.DataFrame(out, columns=COLUMNS) if out else _empty()
