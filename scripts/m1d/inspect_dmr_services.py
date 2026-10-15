"""M1D: inspect DMR HAZARD ArcGIS services relevant to seismic evidence (read-only).

Prints layer metadata (geometry type, fields with aliases, description, extent, count) so
semantics are taken from what the publisher actually serves, not from service names.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

BASE = "https://gisportal.dmr.go.th/arcgis/rest/services/HAZARD"
UA = "Mozilla/5.0 HearthMap research (local)"
SERVICES = sys.argv[1:] or [
    "THA_DMR_ZONE_ACTIVEFAULT_WMS",
    "ZONE_ACTIVEFAULT",
    "ZONE_ACTIVEFAULT_WMS_GSi",
    "กลุ่มรอยเลื่อนมีพลัง",
    "T_ACTIVEFAULT",
    "EQ_ZONE",
    "พื้นที่ภัยพิบัติแผ่นดินไหว",
    "GEOHAZARD_EVENTS",
    "เหตุการณ์ธรณีพิบัติภัย",
]


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def main() -> int:
    for s in SERVICES:
        root = f"{BASE}/{urllib.parse.quote(s)}/MapServer"
        try:
            svc = get(root + "?f=json")
        except Exception as e:
            print(f"== {s}: ERROR {type(e).__name__} {e}")
            continue
        print(f"== {s}: layers {[(x['id'], x['name']) for x in svc.get('layers', [])]}")
        print(
            "   desc:",
            svc.get("serviceDescription") or svc.get("description"),
            "| doc:",
            svc.get("documentInfo", {}).get("Keywords"),
        )
        for lyr in svc.get("layers", []):
            try:
                meta = get(f"{root}/{lyr['id']}?f=json")
                cnt = get(f"{root}/{lyr['id']}/query?where=1%3D1&returnCountOnly=true&f=json")
            except Exception as e:
                print(f"   layer {lyr['id']} ERROR {e}")
                continue
            print(
                f"   layer {lyr['id']} {meta.get('name')}: {meta.get('geometryType')} "
                f"count={cnt.get('count')} maxRecordCount={meta.get('maxRecordCount')}"
            )
            print(
                "   description:",
                str(meta.get("description"))[:300],
                "| copyright:",
                meta.get("copyrightText"),
            )
            print(
                "   fields:",
                [
                    (f["name"], f.get("alias"), f["type"].replace("esriFieldType", ""))
                    for f in meta.get("fields", [])
                ],
            )
            print(
                "   extent:",
                {
                    k: round(v)
                    for k, v in (meta.get("extent") or {}).items()
                    if isinstance(v, (int, float))
                },
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
