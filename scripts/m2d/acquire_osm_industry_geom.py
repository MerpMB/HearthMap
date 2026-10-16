# ruff: noqa: E501
"""M2D.1: acquire OSM industrial and quarry features WITH GEOMETRY (`out tags geom`) so polygons can be measured as polygons.

M2D acquired bounding boxes only (osm-industry-aoi); area fractions and polygon-vs-point distinctions need real geometry. An OSM polygon is not an
operating-status or nuisance claim, and OSM completeness varies.
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

from hearthmap.ingestion.acquire import RawManifest, raw_dir, register_existing

VERSION = "overpass-geom-2026-10-16"
ENDPOINT = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
PROVINCES = {"TH-50": "chiang-mai", "TH-56": "phayao", "TH-57": "chiang-rai"}
SELECTORS = [
    'nwr["landuse"~"^(quarry|industrial)$"](area.a);',
    'nwr["man_made"="works"](area.a);',
    'nwr["industrial"](area.a);',
]


def query(iso: str) -> str:
    return (
        f'[out:json][timeout:900];area["ISO3166-2"="{iso}"]["admin_level"="4"]->.a;('
        + "".join(SELECTORS)
        + ");out tags geom;"
    )


def main() -> int:
    d = raw_dir(Path("data"), "osm-industry-geom-aoi", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    d.mkdir(parents=True, exist_ok=True)
    arts, meta = [], {}
    for iso, slug in PROVINCES.items():
        q = query(iso)
        req = urllib.request.Request(
            ENDPOINT,
            data=urllib.parse.urlencode({"data": q}).encode(),
            headers={"User-Agent": "HearthMap/0.1 (local research)"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=1200) as r:
                    raw = r.read()
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 502, 503, 504) or attempt == 3:
                    raise
                time.sleep(60 * (attempt + 1))
        payload = json.loads(raw)
        if payload.get("remark"):
            raise RuntimeError(f"{iso}: overpass remark {payload['remark']}")
        target = d / f"{slug}_industry_geom.json"
        target.write_bytes(raw)
        meta[target.name] = {
            "query": q,
            "osm3s": payload.get("osm3s"),
            "elements": len(payload["elements"]),
        }
        arts.append(register_existing(target, source_url=ENDPOINT, acquired_at=datetime.now(UTC)))
        print(slug, len(payload["elements"]))
    RawManifest(
        source_id="osm-industry-geom-aoi",
        version=VERSION,
        landing_page="https://www.openstreetmap.org/copyright",
        licence="ODbL 1.0",
        publisher_metadata=meta,
        notes=[
            "Land-use/feature evidence; completeness varies; an OSM quarry or industrial polygon is not an operating-status or nuisance claim."
        ],
        artifacts=arts,
    ).write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
