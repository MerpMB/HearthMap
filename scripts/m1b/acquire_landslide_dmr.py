"""M1B: acquire DMR landslide datasets (RAW stage) - each concept kept separate.

- landslide-susceptibility-dmr : susceptibility polygons (5 published levels)
- landslide-inventory-dmr      : historical landslide scars/locations 1989-2019
Files are stored untouched with publisher metadata snapshots.
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

from hearthmap.ingestion.acquire import (
    _USER_AGENT,
    RawManifest,
    download,
    raw_dir,
    register_existing,
)

DATA = Path("data")
API = "https://data.dmr.go.th/api/3/action/package_show?id="


def pkg(pid: str) -> dict:
    req = urllib.request.Request(API + pid, headers={"User-Agent": _USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["result"]
        except urllib.error.HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt == 4:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def acquire(pid: str, source_id: str) -> None:
    p = pkg(pid)
    version = p["metadata_modified"][:10]
    d = raw_dir(DATA, source_id, version)
    arts = []
    for res in p["resources"]:
        if res.get("format") in ("SHP", "CSV", "DOCX") and res.get("url"):
            if (res.get("size") or 0) > 250 * 1024 * 1024:
                print("skip (size guard)", res["name"], res["size"])
                continue
            name = Path(urllib.parse.unquote(urllib.parse.urlparse(res["url"]).path)).name
            if (d / name).exists():  # resume: never re-download or rewrite RAW
                arts.append(
                    register_existing(
                        d / name,
                        source_url=res["url"],
                        acquired_at=datetime.fromtimestamp((d / name).stat().st_mtime, UTC),
                    )
                )
            else:
                for attempt in range(4):
                    try:
                        arts.append(download(res["url"], d))
                        break
                    except urllib.error.HTTPError as exc:
                        if exc.code not in (502, 503, 504) or attempt == 3:
                            raise
                        time.sleep(15 * (attempt + 1))
            print(source_id, arts[-1].original_filename, arts[-1].size_bytes, flush=True)
    (d / "package_show.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), "utf-8")
    RawManifest(
        source_id=source_id,
        version=version,
        landing_page=f"https://data.dmr.go.th/dataset/{pid}",
        licence=p.get("license_title"),
        publisher_metadata={
            k: p.get(k)
            for k in (
                "title",
                "notes",
                "maintainer",
                "data_source",
                "metadata_created",
                "metadata_modified",
                "update_frequency_unit",
                "update_frequency_interval",
                "geo_coverage",
            )
        }
        | {"resources": p["resources"]},
        notes=[
            "Downloaded with a descriptive User-Agent.",
            "SHP resource is a RAR archive; CSV is the tabular export of the same dataset.",
        ],
        artifacts=arts,
    ).write(d)


if __name__ == "__main__":
    for pid, sid in (
        ("landslide_susceptibility", "landslide-susceptibility-dmr"),
        ("landslide_inventory_map", "landslide-inventory-dmr"),
    ):
        if sys.argv[1:] and sid not in sys.argv[1:]:
            continue
        acquire(pid, sid)
    sys.exit(0)
