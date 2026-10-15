"""M1D: acquire DMR seismic-related layers (read-only ArcGIS REST), stored untouched in RAW.

Layers (service CRS EPSG:32647, no reprojection requested):
  seismic-active-faults-dmr        THA_DMR_ZONE_ACTIVEFAULT_WMS/0  polylines (640)
  seismic-intensity-zones-dmr      EQ_ZONE/0                       polygons  (427)
  seismic-tambon-near-faults-dmr   T_ACTIVEFAULT/0                 points    (1,329)
  geohazard-events-dmr             GEOHAZARD_EVENTS/0              points    (1,015)
The DMR portal republishes the fault layer under three more service names
(ZONE_ACTIVEFAULT, ZONE_ACTIVEFAULT_WMS_GSi and a Thai-named service); their
attribute tables are hashed and compared so duplicates are shown to be duplicates.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, raw_dir
from hearthmap.ingestion.arcgis import _get, fetch_pages, layer_metadata

BASE = "https://gisportal.dmr.go.th/arcgis/rest/services/HAZARD"
VERSION = "service-2026-10-15"
LAYERS = {
    "seismic-active-faults-dmr": ("THA_DMR_ZONE_ACTIVEFAULT_WMS", 500),
    "seismic-intensity-zones-dmr": ("EQ_ZONE", 25),
    "seismic-tambon-near-faults-dmr": ("T_ACTIVEFAULT", 500),
    "geohazard-events-dmr": ("GEOHAZARD_EVENTS", 500),
}
DUPLICATES = ["ZONE_ACTIVEFAULT", "ZONE_ACTIVEFAULT_WMS_GSi", "กลุ่มรอยเลื่อนมีพลัง"]


def layer_url(service: str) -> str:
    return f"{BASE}/{urllib.parse.quote(service)}/MapServer/0"


def attr_hash(url: str) -> tuple[int, str]:
    raw = _get(
        f"{url}/query",
        {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "false",
            "orderByFields": "OBJECTID",
            "f": "json",
        },
        180,
    )
    feats = json.loads(raw)["features"]
    blob = json.dumps([f["attributes"] for f in feats], sort_keys=True, ensure_ascii=False)
    return len(feats), hashlib.sha256(blob.encode("utf-8")).hexdigest()


def main() -> int:
    dups = {}
    primary = attr_hash(layer_url(LAYERS["seismic-active-faults-dmr"][0]))
    for d in DUPLICATES:
        n, h = attr_hash(layer_url(d))
        dups[d] = {"features": n, "attribute_sha256_equals_primary": h == primary[1]}
    for source_id, (service, page_size) in LAYERS.items():
        url = layer_url(service)
        dest = raw_dir(Path("data"), source_id, VERSION)
        if (dest / "manifest.json").exists():
            print(f"{source_id}: already acquired")
            continue
        meta = layer_metadata(url)
        arts, n = fetch_pages(
            url,
            where="1=1",
            out_fields="*",
            order_by="OBJECTID",
            dest_dir=dest,
            prefix="page",
            page_size=page_size,
        )
        RawManifest(
            source_id=source_id,
            version=VERSION,
            landing_page=f"{BASE}/{urllib.parse.quote(service)}/MapServer",
            licence="Not stated on the DMR service (publisher: Department of Mineral Resources)",
            publisher_metadata={
                "layer": {
                    k: meta.get(k)
                    for k in (
                        "name",
                        "geometryType",
                        "fields",
                        "extent",
                        "description",
                        "copyrightText",
                        "type",
                    )
                },
                "feature_count": n,
                "republished_as": dups if source_id == "seismic-active-faults-dmr" else None,
            },
            notes=["ArcGIS JSON exactly as served in the service CRS (EPSG:32647)."],
            artifacts=arts,
        ).write(dest)
        print(f"{source_id}: {n} features in {len(arts)} pages -> {dest}")
    print(json.dumps(dups, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
