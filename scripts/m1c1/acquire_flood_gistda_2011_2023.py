"""M1C.1: acquire GISTDA flood recurrence 2011-2023 (API Gateway, authenticated).

The API answers polygon queries with flood polygons clipped to the query area.
The AOI is requested as a grid of TILE_DEG lon/lat rectangles (only tiles that
touch the three provinces); every response is stored byte-for-byte in RAW.
Resumable: existing tiles are kept. The API key is read from the environment
or the Git-ignored .env.local, and every recorded URL is sanitised.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import PROCESSED

from hearthmap.ingestion.acquire import _USER_AGENT, RawArtifact, RawManifest, raw_dir
from hearthmap.ingestion.secrets import (
    credential_source,
    load_secret,
    sanitize_url,
    scrub,
)
from hearthmap.provenance.model import sha256_file

SOURCE_ID = "flood-gistda-history"
VERSION = "api-2026-10-15"
ENDPOINT = (
    "https://api-gateway.gistda.or.th/api/2.0/resources/gi-service/v1.1/disasters/flood-recurrence"
)
KEY_NAME = "GISTDA_API_KEY"
TILE_DEG = 0.2


def tiles() -> list[tuple[int, int, tuple[float, float, float, float]]]:
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = prov.to_crs("EPSG:4326").union_all()  # tile selection only (same WGS 84 datum)
    x0, y0, x1, y1 = aoi.bounds
    ix0, iy0 = int(np.floor(x0 / TILE_DEG)), int(np.floor(y0 / TILE_DEG))
    ix1, iy1 = int(np.ceil(x1 / TILE_DEG)), int(np.ceil(y1 / TILE_DEG))
    out = []
    for ix in range(ix0, ix1):
        for iy in range(iy0, iy1):
            b = (
                round(ix * TILE_DEG, 6),
                round(iy * TILE_DEG, 6),
                round((ix + 1) * TILE_DEG, 6),
                round((iy + 1) * TILE_DEG, 6),
            )
            if aoi.intersects(box(*b)):
                out.append((ix, iy, b))
    return out


def area_param(b: tuple[float, float, float, float]) -> str:
    x0, y0, x1, y1 = b
    ring = [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
    return json.dumps(
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
    )


def fetch(url: str, secret, attempts: int = 6) -> bytes:
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}"
            if e.code in (401, 403, 407):
                raise RuntimeError(f"authentication failed ({msg}); check {KEY_NAME}") from None
        except Exception as e:
            msg = scrub(f"{type(e).__name__}: {e}", secret)
        wait = 10 * (i + 1)
        print(f"  retry {i + 1}/{attempts} after {msg}; sleeping {wait}s", flush=True)
        time.sleep(wait)
    raise RuntimeError(f"giving up after {attempts} attempts")


def main() -> int:
    secret = load_secret(KEY_NAME)
    dest = raw_dir(Path("data"), SOURCE_ID, VERSION)
    dest.mkdir(parents=True, exist_ok=True)
    plan = tiles()
    print(f"{len(plan)} tiles of {TILE_DEG} deg", flush=True)
    artifacts = []
    for n, (ix, iy, b) in enumerate(plan, 1):
        path = dest / f"tile_{ix:+05d}_{iy:+05d}.json"
        url = (
            ENDPOINT
            + "?"
            + urllib.parse.urlencode({"api_key": secret.reveal(), "area": area_param(b)})
        )
        if not path.exists():
            t = time.time()
            body = fetch(url, secret)
            json.loads(body)  # must be JSON before it is kept
            tmp = path.with_suffix(".part")
            tmp.write_bytes(body)
            tmp.rename(path)
            print(f"{n}/{len(plan)} {path.name} {len(body):,} B {time.time() - t:.0f}s", flush=True)
        artifacts.append(
            RawArtifact(
                original_filename=path.name,
                stored_path=path.name,
                source_url=sanitize_url(url),
                acquired_at=datetime.fromtimestamp(path.stat().st_mtime, UTC),
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
                http_headers={"content-type": "application/json; charset=utf-8"},
            )
        )
    RawManifest(
        source_id=SOURCE_ID,
        version=VERSION,
        landing_page="https://opendata.gistda.or.th/dataset/disasters-01",
        licence="Open Data Common (GISTDA open-data catalogue, dataset disasters-01)",
        licence_url="https://opendata.gistda.or.th/dataset/disasters-01",
        publisher_metadata={
            "access_method": "authenticated GISTDA API",
            "credential_source": credential_source(KEY_NAME),
            "endpoint": ENDPOINT,
            "query": "area = lon/lat rectangle (GeoJSON Feature, EPSG:4326)",
            "tile_deg": TILE_DEG,
            "tiles": len(plan),
            "catalogue_title": "ข้อมูลพื้นที่น้ำท่วมซ้ำซาก (2011-2023, 13 years)",
            "catalogue_metadata_modified": "2026-09-04",
            "documented_metadata": {"coverage": "Thailand", "spatial": "20 m", "update": "Yearly"},
            "documented_fields": {
                "total": "sum of the number of recurring floods (years flooded)",
                "detail[].freq": "frequency found in each year",
                "geom": "area boundary (GeoJSON)",
            },
        },
        notes=[
            "Responses stored exactly as received; polygons are clipped by the API to each tile.",
            "Credential value never recorded; URLs sanitised (api_key=REDACTED).",
        ],
        artifacts=artifacts,
    ).write(dest)
    total = sum(a.size_bytes for a in artifacts)
    print(f"done: {len(artifacts)} tiles, {total / 1e6:.1f} MB -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
