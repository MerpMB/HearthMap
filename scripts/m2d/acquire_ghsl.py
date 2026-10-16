# ruff: noqa: E501
"""M2D: acquire GHS-BUILT-S R2023A (built-up surface, epoch 2020, 3 arc-second grid) tiles covering the AOI (RAW zips, unchanged, hashed).

Why this source: the GISTDA building-footprint API is DEFERRED (see assess_gistda_buildings.py), and built form must be an INDEPENDENT signal from
population. GHS-BUILT-S is satellite-derived built-up surface (m2 of built-up surface per grid cell), not a building count and not population.
Epoch note: the latest OBSERVED epoch of R2023A is 2018 (Sentinel-2 composite); the 2020 epoch is spatio-temporally interpolated/extrapolated from
observed epochs, so it is a modelled, somewhat dated picture of built form.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir

VERSION = "R2023A-E2020-4326-3ss-V1-0"
BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A/GHS_BUILT_S_E2020_GLOBE_R2023A_4326_3ss/V1-0/tiles"
TILES = [
    "R7_C28",
    "R7_C29",
    "R8_C28",
    "R8_C29",
]  # 10-degree tiles: lat 10-30 N, lon 90-110 E (AOI is 17.7-20.6 N, 97.9-101.4 E)


def main() -> int:
    d = raw_dir(Path("data"), "builtup-ghsl-r2023a", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    arts = []
    for t in TILES:
        name = f"GHS_BUILT_S_E2020_GLOBE_R2023A_4326_3ss_V1_0_{t}.zip"
        arts.append(download(f"{BASE}/{name}", d, filename=name))
    RawManifest(
        source_id="builtup-ghsl-r2023a",
        version=VERSION,
        landing_page="https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php",
        licence="Reuse authorised with acknowledgement of the source (EC JRC GHSL open data; CC BY 4.0 per JRC policy, not read from the portal in this session)",
        publisher_metadata={
            "publisher": "European Commission, Joint Research Centre (JRC), Global Human Settlement Layer",
            "title": "GHS-BUILT-S R2023A - GHS built-up surface grid, derived from Sentinel-2 composite and Landsat, multitemporal (1975-2030)",
            "doi": "10.2905/9F06F36F-4B11-47EC-ABB0-4F8B7B1D72EA",
            "authors": "Pesaresi M., Politis P.",
            "year": 2023,
            "epoch": "2020 (interpolated/extrapolated; latest observed epoch is 2018 from a Sentinel-2 composite)",
            "units": "m2 of built-up surface per grid cell",
            "grid": "EPSG:4326, 3 arc-second (~92 m)",
            "tiles": TILES,
        },
        notes=[
            "Satellite-derived built-up SURFACE, not a building count and not population.",
            "The 2020 epoch is modelled, not observed.",
        ],
        artifacts=arts,
    ).write(d)
    print("acquired", [a.size_bytes for a in arts])
    return 0


if __name__ == "__main__":
    sys.exit(main())
