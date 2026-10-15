"""M1D: acquire historical-seismicity sources (public, no credentials), stored untouched in RAW.

  seismic-felt-events-tmd     TMD "statistics of earthquakes affecting Thailand" (SpreadsheetML)
  seismicity-usgs-comcat      USGS ComCat FDSN event catalogue, 6x6 degree box around the AOI

The TMD list is a felt/effects record (historical chronicles to 2026), not a complete
instrumental catalogue. USGS is an authoritative INTERNATIONAL catalogue (documented API,
no key) used as an instrumental reference; it is not a Thai source and is kept separate.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir

VERSION = "download-2026-10-15"
TMD_URL = "https://earthquake.tmd.go.th/eqstat_2excel.php"
USGS_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=1900-01-01"
    "&endtime=2026-10-15&minlatitude=16.0&maxlatitude=22.0&minlongitude=96.0"
    "&maxlongitude=102.0&minmagnitude=3.0&orderby=time-asc"
)


def main() -> int:
    for source_id, url, name, landing, licence, notes in (
        (
            "seismic-felt-events-tmd",
            TMD_URL,
            "thailand_earthquake_stat.xls",
            "https://earthquake.tmd.go.th/earthquakestat.html",
            "Not stated by TMD (Thai Meteorological Department public statistics page)",
            [
                "SpreadsheetML export of 'statistics of earthquakes affecting Thailand'.",
                "Dates are Thai Buddhist-era text; M/I mixes magnitudes and MM intensities.",
            ],
        ),
        (
            "seismicity-usgs-comcat",
            USGS_URL,
            "usgs_comcat_16-22N_96-102E_M3plus.geojson",
            "https://earthquake.usgs.gov/fdsnws/event/1/",
            "USGS public domain (U.S. Government work); attribution requested",
            [
                "FDSN event API, GeoJSON as served; magnitude types and contributing networks "
                "vary per event."
            ],
        ),
    ):
        dest = raw_dir(Path("data"), source_id, VERSION)
        if (dest / "manifest.json").exists():
            print(f"{source_id}: already acquired")
            continue
        art = download(url, dest, filename=name)
        RawManifest(
            source_id=source_id,
            version=VERSION,
            landing_page=landing,
            licence=licence,
            publisher_metadata={"request": url},
            notes=notes,
            artifacts=[art],
        ).write(dest)
        print(f"{source_id}: {art.size_bytes:,} bytes sha256={art.sha256[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
