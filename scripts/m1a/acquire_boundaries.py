"""M1A: record/acquire administrative-boundary sources (RAW stage).

- boundaries-ocha-cod-ab   (PRIMARY): geodatabase downloaded earlier with curl
  (headers saved in headers.txt); this script registers it and adds the
  tabular XLSX and the HDX package metadata.
- boundaries-gistda-50k    (SECONDARY): GISTDA L05 province + amphoe layers,
  server-side filtered to the AOI provinces.
- boundaries-geoboundaries (VALIDATION_ONLY): ADM1 built from OpenStreetMap.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import (
    _USER_AGENT,
    RawManifest,
    download,
    raw_dir,
    register_existing,
)
from hearthmap.ingestion.arcgis import fetch_pages, layer_metadata

DATA = Path("data")
AOI_CODES = "('50','56','57')"


def _json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def cod_ab() -> None:
    d = raw_dir(DATA, "boundaries-ocha-cod-ab", "2026-01-26")
    started = (d / ".acq_start").read_text().strip()
    gdb = register_existing(
        d / "tha_admin_boundaries.gdb.zip",
        source_url=(
            "https://data.humdata.org/dataset/d24bdc45-eb4c-4e3d-8b16-44db02667c27/resource/"
            "ccbf3740-0638-48ea-b612-cdb61ef5462c/download/tha_admin_boundaries.gdb.zip"
        ),
        acquired_at=datetime.fromisoformat(started.replace("Z", "+00:00")),
    )
    gdb = gdb.model_copy(
        update={
            "final_url": "https://s3.us-east-1.amazonaws.com/hdx-production-filestore/resources/"
            "ccbf3740-0638-48ea-b612-cdb61ef5462c/tha_admin_boundaries.gdb.zip (signed redirect)",
            "http_headers": {
                "Last-Modified": "Mon, 26 Jan 2026 16:23:52 GMT",
                "ETag": '"7b6f2da7c7ab628ef0cf31aec4dcae62"',
                "Content-Length": "174679979",
            },
        }
    )
    xlsx = download(
        "https://data.humdata.org/dataset/d24bdc45-eb4c-4e3d-8b16-44db02667c27/resource/"
        "a925b917-01ae-48c4-9279-7efe680a6b11/download/tha_admin_boundaries.xlsx",
        d,
        filename="tha_admin_boundaries.xlsx",
    )
    pkg = _json("https://data.humdata.org/api/3/action/package_show?id=cod-ab-tha")["result"]
    (d / "hdx_package_show.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2), "utf-8")
    RawManifest(
        source_id="boundaries-ocha-cod-ab",
        version="2026-01-26",
        landing_page="https://data.humdata.org/dataset/cod-ab-tha",
        licence=pkg.get("license_title"),
        licence_url="https://creativecommons.org/licenses/by/3.0/igo/",
        publisher_metadata={
            k: pkg.get(k)
            for k in (
                "title",
                "dataset_source",
                "license_id",
                "last_modified",
                "metadata_modified",
                "dataset_date",
                "caveats",
                "methodology_other",
                "notes",
                "data_update_frequency",
            )
        },
        notes=[
            "Full HDX package metadata saved as hdx_package_show.json at acquisition time.",
            "headers.txt holds the raw HTTP headers of the geodatabase download (curl -D).",
        ],
        artifacts=[gdb, xlsx],
    ).write(d)


def gistda_50k() -> None:
    version = "service-" + datetime.now(UTC).strftime("%Y-%m-%d")
    d = raw_dir(DATA, "boundaries-gistda-50k", version)
    base = "https://gistdaportal.gistda.or.th/data/rest/services/L05_AdminBoundary"
    arts, meta = [], {}
    for name in ("L05_Province_GISTDA_50k", "L05_Amphoe_GISTDA_50k"):
        url = f"{base}/{name}/MapServer/0"
        meta[name] = layer_metadata(url)
        a, n = fetch_pages(
            url,
            where=f"PV_CODE in {AOI_CODES}",
            out_fields="*",
            order_by="FID",
            dest_dir=d,
            prefix=name,
            paginate=False,
        )
        meta[name + "_feature_count"] = n
        arts += a
    RawManifest(
        source_id="boundaries-gistda-50k",
        version=version,
        landing_page=base,
        licence="Not stated on the service (copyright: GISTDA). Validation use only.",
        publisher_metadata=meta,
        notes=[
            "ArcGIS JSON pages in EPSG:3857 as served; filtered to PV_CODE 50/56/57.",
            "No publication/vintage date exposed by the service (MOD_DATE is null).",
        ],
        artifacts=arts,
    ).write(d)


def geoboundaries() -> None:
    api = _json("https://www.geoboundaries.org/api/current/gbOpen/THA/ADM1/")
    d = raw_dir(DATA, "boundaries-geoboundaries", api["boundaryID"])
    art = download(api["gjDownloadURL"], d)
    (d / "api_metadata.json").write_text(json.dumps(api, indent=2), "utf-8")
    RawManifest(
        source_id="boundaries-geoboundaries",
        version=api["boundaryID"],
        landing_page="https://www.geoboundaries.org/countryDownloads.html",
        licence=api["boundaryLicense"],
        licence_url="https://opendatacommons.org/licenses/odbl/",
        publisher_metadata=api,
        notes=[
            "THA ADM1 in gbOpen is derived from OpenStreetMap (Wambacher), year 2017: "
            "independent of the RTSD lineage, therefore useful for validation only."
        ],
        artifacts=[art],
    ).write(d)


if __name__ == "__main__":
    for step in sys.argv[1:] or ["gistda_50k", "geoboundaries"]:
        print("==", step, flush=True)
        globals()[step]()
