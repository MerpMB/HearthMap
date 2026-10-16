# ruff: noqa: E501
"""M2D: acquire OSM service and nightlife POIs for the three provinces (RAW Overpass JSON, hashed; ODbL; practical evidence only).

Tag families are queried separately so components are never collapsed. OSM completeness varies geographically, businesses open and close,
tagging is inconsistent, and the absence of a POI is not proof that a service does not exist.
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

VERSION = "overpass-2026-10-16"
ENDPOINT = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
PROVINCES = {"TH-50": "chiang-mai", "TH-56": "phayao", "TH-57": "chiang-rai"}
SELECTORS = [
    'nwr["shop"~"^(supermarket|grocery|convenience|department_store|mall|variety_store|general|hardware|doityourself|greengrocer)$"](area.a);',
    'nwr["amenity"~"^(marketplace|pharmacy|bank|atm|fuel|townhall|bar|pub|nightclub|stripclub|karaoke_box)$"](area.a);',
    'nwr["healthcare"="pharmacy"](area.a);',
    'nwr["office"="government"](area.a);',
]


def query(iso: str) -> str:
    return (
        f'[out:json][timeout:900];area["ISO3166-2"="{iso}"]["admin_level"="4"]->.a;('
        + "".join(SELECTORS)
        + ");out tags center;"
    )


def main() -> int:
    d = raw_dir(Path("data"), "osm-service-pois-aoi", VERSION)
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
        target = d / f"{slug}_service_pois.json"
        target.write_bytes(raw)
        meta[target.name] = {
            "query": q,
            "osm3s": payload.get("osm3s"),
            "elements": len(payload["elements"]),
        }
        arts.append(register_existing(target, source_url=ENDPOINT, acquired_at=datetime.now(UTC)))
        print(slug, len(payload["elements"]))
    RawManifest(
        source_id="osm-service-pois-aoi",
        version=VERSION,
        landing_page="https://www.openstreetmap.org/copyright",
        licence="ODbL 1.0",
        publisher_metadata=meta,
        notes=[
            "Practical POI evidence; completeness varies; absence of a POI is not absence of a service."
        ],
        artifacts=arts,
    ).write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
