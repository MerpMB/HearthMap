# ruff: noqa: E501
"""M2D: acquire the WorldPop R2025A Thailand 2025 constrained 100 m population raster (RAW, unchanged, hashed).

Verified before acquisition: provider data.worldpop.org (University of Southampton), release R2025A v1 (alpha), constrained (CN) top-down
random-forest dasymetric product, units = estimated people per ~100 m (3 arc-second) pixel, WGS84, release statement read,
metadata from the public WorldPop REST API (DOI, date, citation). The unconstrained 2025 file does not exist for this release.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir

VERSION = "R2025A-v1-2025"
URL = "https://data.worldpop.org/GIS/Population/Global_2015_2030/R2025A/2025/THA/v1/100m/constrained/tha_pop_2025_CN_100m_R2025A_v1.tif"
API = "https://hub.worldpop.org/rest/data/pop/G2_CN_POP_R25A_100m?iso3=THA"
STATEMENT = "https://data.worldpop.org/repo/prj/Global_2015_2030/R2025A/doc/Global2_Release_Statement_R2025A_v1.pdf"


def main() -> int:
    d = raw_dir(Path("data"), "population-worldpop-r2025a", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    meta = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0"}), timeout=60
        ).read()
    )["data"]
    entry = next(m for m in meta if m.get("popyear") == "2025")
    art = download(URL, d, filename="tha_pop_2025_CN_100m_R2025A_v1.tif")
    RawManifest(
        source_id="population-worldpop-r2025a",
        version=VERSION,
        landing_page="https://hub.worldpop.org/geodata/summary?id=" + str(entry["id"]),
        licence="CC BY 4.0",
        licence_url="https://creativecommons.org/licenses/by/4.0/",
        publisher_metadata={
            "publisher": "WorldPop, School of Geography and Environmental Science, University of Southampton",
            "title": entry["title"],
            "doi": entry["doi"],
            "release_date": entry["date"],
            "population_year": entry["popyear"],
            "release": "R2025A v1 (alpha)",
            "method": "constrained (CN), top-down random-forest dasymetric disaggregation, aligned to UN WPP 2024 national totals",
            "units": "estimated number of people per pixel (3 arc-second, ~100 m)",
            "crs": "EPSG:4326 (WGS84)",
            "citation": entry["citation"],
            "release_statement": STATEMENT,
            "rest_api": API,
        },
        notes=[
            "The release statement warns the product is an alpha version and that comparisons between time points should be made with care at small area scales.",
            "Population counts are modelled estimates, not census counts, and are not peacefulness.",
        ],
        artifacts=[art],
    ).write(d)
    print("acquired", art.size_bytes, art.sha256[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main())
