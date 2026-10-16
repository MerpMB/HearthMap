# ruff: noqa: E501
"""M2D.1: acquire the official DPIM public licence exports (stone crushing/grinding plants and mining concessions) for the three AOI provinces.

Source: the public DPIM report services linked from the DPIM data centre pages (www-old.dpim.go.th/webservices/facstone_report.php and
con_report.php). Those pages build a plain GET to https://dses.dpim.go.th/xmlreportservices/generate.do (reportname, paging=N, reqProvinceLocation);
leaving out the `expireDt` parameter is what the page's "include expired licences" box does. One request per report and province (six in total),
no authentication, no bypass, no crawling. The access-controlled quarry query page (www1.dpim.go.th/qry/quarry.php, HTTP 403) is NOT used.

Personal data is minimised before storage: operator/holder names (customerName, tovCustomerName, factory_name) are dropped and replaced by a
juristic-person flag derived from the name prefix. The transformation is recorded in the manifest.
LICENCE_STATUS is a register status and is never a current operating status.
"""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, raw_dir, register_existing

VERSION = "dpim-dses-2026-10-16"
ENDPOINT = "https://dses.dpim.go.th/xmlreportservices/generate.do"
PROVINCES = {"50": "chiang-mai", "56": "phayao", "57": "chiang-rai"}
REPORTS = {"facstone_report": "stone_crushing_licences", "concession_report": "mining_concessions"}
PII = {"customerName", "tovCustomerName", "factory_name"}
JURISTIC_PREFIXES = (
    "บริษัท",
    "บจก",
    "ห้างหุ้นส่วน",
    "หจก",
    "บมจ",
    "สหกรณ์",
    "องค์การ",
    "เทศบาล",
    "องค์การบริหาร",
    "กรม",
    "มูลนิธิ",
    "วิสาหกิจ",
    "ร้าน",
)
UA = {"User-Agent": "Mozilla/5.0 HearthMap/0.1 (local research)"}


def fetch(report: str, prov: str) -> tuple[str, list[dict[str, str | None]], list[str]]:
    url = f"{ENDPOINT}?reportname={report}&paging=N&dt=0&reqProvinceLocation={prov}&ran=m2d1"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    headers = [(h.text or "") for h in root.find("Header")]
    rows = []
    for d in root.findall("Detail"):
        rec = {c.tag: (None if c.text in (None, "null") else c.text.strip()) for c in d}
        holder = (rec.get("customerName") or rec.get("factory_name") or "").replace(" ", "")
        rec["operator_is_juristic_person"] = (
            holder.startswith(JURISTIC_PREFIXES) or "จำกัด" in holder
        )
        for k in PII:
            rec.pop(k, None)
        rows.append(rec)
    return url, rows, headers


def main() -> int:
    d = raw_dir(Path("data"), "mining-dpim-licence-exports", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    d.mkdir(parents=True, exist_ok=True)
    arts, meta = [], {}
    for report, label in REPORTS.items():
        payload: dict = {
            "report": report,
            "endpoint": ENDPOINT,
            "provinces": {},
            "headers_th": None,
            "removed_fields": sorted(PII),
        }
        for prov in PROVINCES:
            url, rows, headers = fetch(report, prov)
            payload["provinces"][prov] = {"request": url, "records": rows}
            payload["headers_th"] = headers
        target = d / f"{label}_aoi_provinces.json"
        target.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        arts.append(register_existing(target, source_url=ENDPOINT, acquired_at=datetime.now(UTC)))
        meta[label] = {
            "report": report,
            "records_by_province": {p: len(v["records"]) for p, v in payload["provinces"].items()},
        }
        print(label, meta[label])
    RawManifest(
        source_id="mining-dpim-licence-exports",
        version=VERSION,
        landing_page="https://www-old.dpim.go.th/datacenter",
        licence="Not stated on the export pages (public government system); treated as public-information use for non-commercial local research. Re-check terms before redistribution.",
        publisher_metadata={
            "reports": meta,
            "removed_fields_before_storage": sorted(PII),
            "removal_reason": "personal data not needed for area-level context",
            "xml_encoding": "TIS-620",
            "date_calendar": "Buddhist era (dd/mm/yyyy)",
            "statuses_stone_filter_values": {
                "03": "เปิดการ",
                "02": "หยุดการ",
                "04": "ต่ออายุ",
                "06": "สิ้นอายุ",
                "01": "จำหน่ายทะเบียน",
                "08": "รอแจ้งประกอบกิจการ",
            },
        },
        notes=[
            "No coordinates in either export: tambon is the finest location.",
            "Licence status is a register status, not a current operating status.",
            "Expired licences are included (the include-expired option).",
        ],
        artifacts=arts,
    ).write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
