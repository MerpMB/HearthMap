# ruff: noqa: E501
"""M2A.1: retry the official MOE / MoPH sources, record every attempt, and acquire what is reachable.

Acquired (RAW, immutable, hashed):
  education-obec-school-list   OBEC open API OBEC_SCHOOL_007 (school list, academic year 2563)
  osm-facilities-aoi           Overpass: schools/colleges/hospitals/clinics (current validation only; ODbL)
Probed only (no bypass of authentication, bot challenges or access restrictions): catalog.moe.go.th,
hcode.moph.go.th, opendata.moph.go.th. Output: outputs/m2a1-review/source-access-log.json
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir, register_existing

VERSION = "api-2026-10-16"
REVIEW = Path("outputs/m2a1-review")
UA_BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
OBEC = "https://opendata.edudev.in.th/v1/OBEC_SCHOOL_007"
OVERPASS = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
PROVINCES = {"TH-50": "chiang-mai", "TH-56": "phayao", "TH-57": "chiang-rai"}
PROBES = [
    ("MOE catalogue (https)", "https://catalog.moe.go.th/dataset"),
    (
        "MOE catalogue CKAN API (https)",
        "https://catalog.moe.go.th/api/3/action/package_search?q=school&rows=1",
    ),
    (
        "MOE catalogue (plain http)",
        "http://catalog.moe.go.th/api/3/action/package_search?q=school&rows=1",
    ),
    ("MOE data portal (https)", "https://data.moe.go.th/"),
    ("MOE file server by IP (http)", "http://203.159.172.49/"),
    ("MoPH HCODE (https)", "https://hcode.moph.go.th/"),
    ("MoPH HCODE API (https)", "https://hcode.moph.go.th/api"),
    ("MoPH Open Data (https)", "https://opendata.moph.go.th/"),
    ("OBEC open API (https)", "https://opendata.edudev.in.th/v1/OBEC_SCHOOL_005"),
]


def probe() -> list[dict]:
    out = []
    for name, url in PROBES:
        rec = {"name": name, "url": url, "checked": datetime.now(UTC).isoformat()}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA_BROWSER})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read(4000).decode("utf-8", "replace")
                rec |= {"http_status": r.status, "bytes_head": len(body)}
                if "Just a moment" in body or "cf-chl" in body:
                    rec["note"] = "Cloudflare bot challenge page; NOT bypassed"
                if "ไม่พบชุดข้อมูล" in body or '"count": 0' in body:
                    rec["note"] = (
                        "reachable but the instance lists zero datasets (not the live catalogue)"
                    )
        except urllib.error.HTTPError as e:
            rec |= {"http_status": e.code, "note": "HTTP error; no workaround attempted"}
        except Exception as e:
            rec |= {"error": type(e).__name__ + ": " + str(e)[:120]}
        out.append(rec)
    return out


def osm_query(iso: str) -> str:
    sel = (
        '["amenity"~"^(school|kindergarten|college|university|hospital|clinic|doctors|childcare)$"]'
    )
    return f'[out:json][timeout:600];area["ISO3166-2"="{iso}"]["admin_level"="4"]->.a;(nwr{sel}(area.a);nwr["healthcare"~"^(hospital|clinic|centre)$"](area.a););out tags center;'


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    log = probe()
    (REVIEW / "source-access-log.json").write_text(
        json.dumps(log, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    d = raw_dir(Path("data"), "education-obec-school-list", VERSION)
    if not (d / "manifest.json").exists():
        art = download(OBEC, d, filename="OBEC_SCHOOL_007.json")
        RawManifest(
            source_id="education-obec-school-list",
            version=VERSION,
            landing_page="https://opendata.edudev.in.th/",
            licence="Open Data Common (data.go.th records obec-school-007)",
            publisher_metadata={
                "publisher": "OBEC",
                "dataset": "OBEC_SCHOOL_007 รายชื่อ ร.ร. สังกัด สพฐ. ปี 2563",
                "academic_year_be": 2563,
                "catalogue_modified": "2024-04-12",
            },
            notes=[
                "Authoritative class min/max levels and MOE code; academic year 2563 (2020) - STALE; OBEC schools only."
            ],
            artifacts=[art],
        ).write(d)
    d = raw_dir(Path("data"), "osm-facilities-aoi", VERSION)
    if not (d / "manifest.json").exists():
        d.mkdir(parents=True, exist_ok=True)
        arts, meta = [], {}
        for iso, slug in PROVINCES.items():
            q = osm_query(iso)
            req = urllib.request.Request(
                OVERPASS,
                data=urllib.parse.urlencode({"data": q}).encode(),
                headers={"User-Agent": "HearthMap/0.1 (local research)"},
            )
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=900) as r:
                        raw = r.read()
                    break
                except urllib.error.HTTPError as e:
                    if e.code not in (429, 502, 503, 504) or attempt == 3:
                        raise
                    time.sleep(60 * (attempt + 1))
            payload = json.loads(raw)
            if payload.get("remark"):
                raise RuntimeError(f"{iso}: overpass remark {payload['remark']}")
            target = d / f"{slug}_facilities.json"
            target.write_bytes(raw)
            meta[target.name] = {
                "query": q,
                "osm3s": payload.get("osm3s"),
                "elements": len(payload["elements"]),
            }
            arts.append(
                register_existing(target, source_url=OVERPASS, acquired_at=datetime.now(UTC))
            )
        RawManifest(
            source_id="osm-facilities-aoi",
            version=VERSION,
            landing_page="https://www.openstreetmap.org/copyright",
            licence="ODbL 1.0",
            publisher_metadata=meta,
            notes=[
                "Current crowd-sourced facility presence; validation only, never authoritative."
            ],
            artifacts=arts,
        ).write(d)
    print(json.dumps(log, indent=1, ensure_ascii=False)[:2500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
