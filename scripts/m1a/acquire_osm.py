"""M1A: OpenStreetMap bootstrap subset for the AOI provinces (RAW stage).

The national Geofabrik extract (~700 MB) exceeds the acquisition size guard,
so roads and waterways are requested per province from an Overpass API
instance. OSM data stays logically separate from government sources (ODbL).
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

from hearthmap.ingestion.acquire import _USER_AGENT, RawArtifact, RawManifest, raw_dir
from hearthmap.provenance.model import sha256_file

ENDPOINT = "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
PROVINCES = {"TH-50": "chiang-mai", "TH-56": "phayao", "TH-57": "chiang-rai"}
CATEGORIES = {
    "major_roads": 'way["highway"~"^(motorway|trunk|primary|secondary)(_link)?$"](area.a);',
    "minor_roads": 'way["highway"~"^(tertiary|tertiary_link|unclassified|residential)$"](area.a);',
    "waterways": 'way["waterway"~"^(river|stream|canal)$"](area.a);',
}
MAX_BYTES = 250 * 1024 * 1024


def query(iso: str, body: str) -> str:
    return (
        f"[out:json][timeout:900][maxsize:{MAX_BYTES}];"
        f'area["ISO3166-2"="{iso}"]["admin_level"="4"]->.a;'
        f"({body});out tags geom;"
    )


def main() -> int:
    version = datetime.now(UTC).strftime("%Y-%m-%d")
    d = raw_dir(Path("data"), "osm-overpass-aoi", version)
    d.mkdir(parents=True, exist_ok=True)
    arts, meta = [], {}
    for iso, slug in PROVINCES.items():
        for cat, body in CATEGORIES.items():
            q = query(iso, body)
            target = d / f"{slug}_{cat}.json"
            if target.exists():
                # Resume: never re-download or rewrite an existing RAW file.
                raw = target.read_bytes()
                payload = json.loads(raw)
                started = datetime.fromtimestamp(target.stat().st_mtime, UTC)
            else:
                req = urllib.request.Request(
                    ENDPOINT,
                    data=urllib.parse.urlencode({"data": q}).encode(),
                    headers={"User-Agent": _USER_AGENT},
                )
                started = datetime.now(UTC)
                for attempt in range(4):
                    try:
                        with urllib.request.urlopen(req, timeout=1200) as resp:
                            raw = resp.read()
                        break
                    except urllib.error.HTTPError as exc:
                        if exc.code not in (429, 502, 503, 504) or attempt == 3:
                            raise
                        time.sleep(60 * (attempt + 1))
                payload = json.loads(raw)
                if payload.get("remark"):
                    raise RuntimeError(f"{iso} {cat}: overpass remark: {payload['remark']}")
                target.write_bytes(raw)
            meta[target.name] = {
                "query": q,
                "osm3s": payload.get("osm3s"),
                "elements": len(payload.get("elements", [])),
            }
            arts.append(
                RawArtifact(
                    original_filename=target.name,
                    stored_path=target.name,
                    source_url=f"{ENDPOINT} (POST data=query, see publisher_metadata)",
                    acquired_at=started,
                    size_bytes=target.stat().st_size,
                    sha256=sha256_file(target),
                )
            )
            print(iso, cat, len(payload["elements"]), target.stat().st_size, flush=True)
            time.sleep(5)
    RawManifest(
        source_id="osm-overpass-aoi",
        version=version,
        landing_page="https://www.openstreetmap.org/copyright",
        licence="Open Data Commons Open Database License (ODbL) 1.0",
        licence_url="https://opendatacommons.org/licenses/odbl/1-0/",
        publisher_metadata=meta,
        notes=[
            "Overpass JSON with full way geometry (EPSG:4326) as served.",
            "Main overpass-api.de instance was failing (502/timeouts) on acquisition day; "
            "the maps.mail.ru public instance was used.",
            "Attribution required: (c) OpenStreetMap contributors. Derived databases that "
            "are publicly distributed must be offered under ODbL.",
        ],
        artifacts=arts,
    ).write(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
