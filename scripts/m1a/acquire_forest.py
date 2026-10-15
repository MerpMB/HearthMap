"""M1A: forest / protected-land screening sources (RAW stage).

- forest-reserve-rfd: Royal Forest Department national reserved forest boundary
  shapefile (RAR) + reserve list, from data.forest.go.th. Publisher states the
  data CANNOT certify forest boundaries (requires forest officials).
- protected-gistda-mnre: national parks (2014, 1:50k) and wildlife sanctuaries
  served by GISTDA (MNRE copyright), filtered to the AOI envelope.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from hearthmap.ingestion.acquire import _USER_AGENT, RawManifest, download, raw_dir
from hearthmap.ingestion.arcgis import fetch_pages, layer_metadata

DATA = Path("data")
AOI_ENVELOPE = json.dumps(
    {"xmin": 97.2, "ymin": 17.0, "xmax": 101.0, "ymax": 20.6, "spatialReference": {"wkid": 4326}}
)


def rfd() -> None:
    pkg_url = "https://data.forest.go.th/api/3/action/package_show?id=reserve_forest"
    req = urllib.request.Request(pkg_url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        pkg = json.loads(r.read())["result"]
    shp = next(x for x in pkg["resources"] if x["format"] == "SHP")
    d = raw_dir(DATA, "forest-reserve-rfd", shp["last_modified"][:10])
    arts = [download(shp["url"], d)]
    for res in pkg["resources"]:
        if res["format"] in ("JSON", "CSV", "XLSX"):
            arts.append(download(res["url"], d))
    (d / "package_show.json").write_text(json.dumps(pkg, ensure_ascii=False, indent=2), "utf-8")
    RawManifest(
        source_id="forest-reserve-rfd",
        version=shp["last_modified"][:10],
        landing_page="https://data.forest.go.th/dataset/reserve_forest",
        licence=pkg.get("license_title"),
        publisher_metadata={
            "title": pkg["title"],
            "notes": pkg["notes"],
            "organization": pkg["organization"]["title"],
            "metadata_modified": pkg["metadata_modified"],
            "shp_resource": shp,
        },
        notes=[
            "Publisher note (verbatim, Thai): data cannot be used to certify forest "
            "boundaries; certification only by forest officials.",
            "WMS/WFS services of the same layer are labelled approximate and not legally citable.",
        ],
        artifacts=arts,
    ).write(d)


def gistda_protected() -> None:
    version = "service-" + datetime.now(UTC).strftime("%Y-%m-%d")
    d = raw_dir(DATA, "protected-gistda-mnre", version)
    base = "https://gistdaportal.gistda.or.th/data/rest/services/L10_Forest"
    geo = {
        "geometry": AOI_ENVELOPE,
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
    }
    arts, meta = [], {}
    for name in ("L10_NPRK_MNRE_50k", "L10_WLDS_MNRE_xxk"):
        url = f"{base}/{name}/MapServer/0"
        meta[name] = {
            "service": layer_metadata(f"{base}/{name}/MapServer"),
            "layer": layer_metadata(url),
        }
        a, n = fetch_pages(
            url,
            where="1=1",
            out_fields="*",
            order_by="objectid",
            dest_dir=d,
            prefix=name,
            paginate=False,
            extra_params=geo,
        )
        meta[name + "_feature_count"] = n
        arts += a
    RawManifest(
        source_id="protected-gistda-mnre",
        version=version,
        landing_page=base,
        licence="Not stated on the service (copyright: Ministry of Natural Resources and "
        "Environment). Screening use only.",
        publisher_metadata=meta,
        notes=[
            "Filtered by AOI envelope (EPSG:4326 97.2,17.0,101.0,20.6).",
            "National parks layer is described as BE 2557 (2014) at 1:50,000.",
        ],
        artifacts=arts,
    ).write(d)


if __name__ == "__main__":
    for step in sys.argv[1:] or ["rfd", "gistda_protected"]:
        print("==", step, flush=True)
        globals()[step]()
