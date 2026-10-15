# ruff: noqa: E501
"""M2A.2: acquire the public MoPH hospital point layers (no authentication) for the three provinces.

Service: https://pherportal.moph.go.th/arcgis/rest/services/MOPH_DATA (public ArcGIS REST, query enabled, no key).
  facility-moph-hospital-update68   Hospital_update68 layer 32   (11,087 national records; last edited 2026-09)
  facility-moph-hospital-update69   Hospital_update69_correct layer 35 (6,581 national records; last edited 2026-03)
Only features whose `changwat` is Chiang Mai / Chiang Rai / Phayao are requested. HCODE itself (Cloudflare-challenged)
is NOT touched. Writes RAW pages + manifest + outputs/m2a2-review/moph-service-profile.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, raw_dir
from hearthmap.ingestion.arcgis import fetch_pages, layer_metadata

BASE = "https://pherportal.moph.go.th/arcgis/rest/services/MOPH_DATA"
VERSION = "service-2026-10-16"
WHERE = "changwat IN ('เชียงใหม่','เชียงราย','พะเยา')"
LAYERS = {
    "facility-moph-hospital-update68": ("Hospital_update68", 32, "OBJECTID"),
    "facility-moph-hospital-update69": ("Hospital_update69_correct", 35, "OBJECTID"),
}
REVIEW = Path("outputs/m2a2-review")


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    profile = {}
    for sid, (svc, lid, order) in LAYERS.items():
        url = f"{BASE}/{svc}/FeatureServer/{lid}"
        meta = layer_metadata(url)
        d = raw_dir(Path("data"), sid, VERSION)
        if not (d / "manifest.json").exists():
            arts, n = fetch_pages(
                url,
                where=WHERE,
                out_fields="*",
                order_by=order,
                dest_dir=d,
                prefix="page",
                page_size=1000,
            )
            RawManifest(
                source_id=sid,
                version=VERSION,
                landing_page="https://pherportal.moph.go.th/arcgis/rest/services/MOPH_DATA",
                licence=None,
                publisher_metadata={
                    "service": f"{svc}/FeatureServer/{lid}",
                    "features_in_aoi_provinces": n,
                    "service_description": meta.get("description"),
                    "maxRecordCount": meta.get("maxRecordCount"),
                    "fields": [f["name"] for f in meta["fields"]],
                    "currentVersion": meta.get("currentVersion"),
                },
                notes=[
                    "Public ArcGIS REST service (no credential). No licence statement on the service: use conservatively (REGIONAL_SCREENING), record as unstated.",
                    "HCODE ids (maincode/oldcode), type, level_, status and coordinates are source fields.",
                ],
                artifacts=arts,
            ).write(d)
            profile[sid] = {"features": n, "url": url}
        else:
            profile[sid] = {"features": "already acquired", "url": url}
    (REVIEW / "moph-service-profile.json").write_text(
        json.dumps(profile, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    print(profile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
