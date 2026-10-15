"""M1A: Copernicus DEM GLO-30 tiles intersecting the validated AOI (RAW stage).

Anonymous HTTPS access to the AWS Open Data bucket (verified 2026-10-15).
Only 1x1 degree tiles that intersect the real province union are fetched.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import geopandas as gpd
import shapely

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir

BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"
VERSION = "aws-2021-release"  # COGs in the bucket are dated 2022-05-09


def tile_name(lat: int, lon: int) -> str:
    ns, ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
    return f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def main() -> int:
    aoi = gpd.read_file("data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    aoi_ll = aoi.to_crs("EPSG:4326").union_all()  # same datum: pure conversion
    minx, miny, maxx, maxy = aoi_ll.bounds
    tiles = [
        (lat, lon)
        for lat in range(math.floor(miny), math.ceil(maxy))
        for lon in range(math.floor(minx), math.ceil(maxx))
        if aoi_ll.intersects(shapely.box(lon, lat, lon + 1, lat + 1))
    ]
    d = raw_dir(Path("data"), "dem-copernicus-glo30", VERSION)
    arts = []
    for lat, lon in tiles:
        t = tile_name(lat, lon)
        target = d / f"{t}.tif"
        if target.exists():
            raise FileExistsError(target)
        arts.append(download(f"{BUCKET}/{t}/{t}.tif", d))
        print(t, arts[-1].size_bytes, flush=True)
    RawManifest(
        source_id="dem-copernicus-glo30",
        version=VERSION,
        landing_page="https://registry.opendata.aws/copernicus-dem/",
        licence="Copernicus DEM licence (GLO-30 Public: free for the general public); "
        "attribution notice required when distributing",
        licence_url="https://spacedata.copernicus.eu/documents/20123/121286/CSCDA_ESA_Mission-specific+Annex_31_Oct_22.pdf",
        publisher_metadata={
            "tiles": [tile_name(a, b) for a, b in tiles],
            "aoi_bounds_lonlat": [minx, miny, maxx, maxy],
        },
        notes=[
            "Digital SURFACE model (includes vegetation and buildings), TanDEM-X 2011-2015.",
            "Horizontal WGS84-G1150 (EPSG:4326), vertical EGM2008 (EPSG:3855), per the "
            "Copernicus Data Space collection description.",
        ],
        artifacts=arts,
    ).write(d)
    print(f"{len(arts)} tiles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
