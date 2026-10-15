"""M2A: acquire the verified family/infrastructure sources into RAW (immutable, hashed).

  health-citizeninfo-dga     data.go.th CSV, government health-facility coordinates (2020-03-14)
  places-dopa-gis02          DOPA gis-02 JSON per province (budget year 2564), education institutions
  roads-drr-gis              DRR ArcGIS FeatureServer layer 2 (rural highways), AOI envelope only
No credential is needed or used for any of them.
"""

# ruff: noqa: E501

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir
from hearthmap.ingestion.arcgis import fetch_pages, layer_metadata

VERSION = "download-2026-10-16"
HEALTH = (
    "https://data.go.th/dataset/00170665-bda1-4f4a-ad7c-52dac7abc7a5/resource/"
    "2d45b0c6-75e9-4463-888d-ef364ad164fb/download/citizeninfo_health_20200314.csv"
)
DOPA = "https://catalog.dopa.go.th/dataset/c0cddb04-4b6e-40bc-afb9-ea72d28324bb/resource/{rid}/download/.json"
DOPA_RES = {
    "chiang-mai": "17d375c4-76be-4c65-b24d-1b7c2c5ae719",
    "chiang-rai": "b8af1e10-8b22-4d22-a9ce-523d06d2876f",
    "phayao": "2399888c-b888-4a5f-a4f9-f70a15d63f99",
}
DRR_LAYER = "https://gis.drr.go.th/arcgis/rest/services/DRR_Feature/FeatureServer/2"
ENVELOPE = '{"xmin":97.9,"ymin":17.7,"xmax":101.4,"ymax":20.6,"spatialReference":{"wkid":4326}}'


def main() -> int:
    d = raw_dir(Path("data"), "health-citizeninfo-dga", VERSION)
    if not (d / "manifest.json").exists():
        art = download(HEALTH, d, filename="citizeninfo_health_20200314.csv")
        RawManifest(
            source_id="health-citizeninfo-dga",
            version=VERSION,
            landing_page="https://data.go.th/dataset/health-citizeninfo",
            licence="CC BY 4.0",
            licence_url="https://creativecommons.org/licenses/by/4.0/",
            publisher_metadata={
                "publisher": "Digital Government Development Agency (DGA)",
                "metadata_modified": "2021-10-31",
                "resource_dated": "2020-03-14",
            },
            notes=["Government health facilities with coordinates; no facility-class field."],
            artifacts=[art],
        ).write(d)
    d = raw_dir(Path("data"), "places-dopa-gis02", VERSION)
    if not (d / "manifest.json").exists():
        arts = [
            download(DOPA.format(rid=rid), d, filename=f"dopa_gis02_{p}.json")
            for p, rid in DOPA_RES.items()
        ]
        RawManifest(
            source_id="places-dopa-gis02",
            version=VERSION,
            landing_page="https://catalog.dopa.go.th/dataset/gis-02",
            publisher_metadata={
                "publisher": "Department of Provincial Administration",
                "budget_id": "2564",
            },
            notes=["Place names with coordinates; institution type is not a field."],
            artifacts=arts,
        ).write(d)
    d = raw_dir(Path("data"), "roads-drr-gis", VERSION)
    if not (d / "manifest.json").exists():
        meta = layer_metadata(DRR_LAYER)
        arts, n = fetch_pages(
            DRR_LAYER,
            where="1=1",
            out_fields="*",
            order_by="OBJECTID",
            dest_dir=d,
            prefix="page",
            page_size=500,
            extra_params={
                "geometry": ENVELOPE,
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outSR": "32647",
            },
        )
        RawManifest(
            source_id="roads-drr-gis",
            version=VERSION,
            landing_page="https://gis.drr.go.th/arcgis/rest/services/DRR_Feature/FeatureServer/2",
            publisher_metadata={
                "description": meta.get("description"),
                "features_in_envelope": n,
                "retrieved": datetime.now(UTC).isoformat(),
            },
            notes=[
                "DRR rural highway centrelines; scale 1:4000 urban, 1:20000 elsewhere (service description)."
            ],
            artifacts=arts,
        ).write(d)
        print("drr features", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
