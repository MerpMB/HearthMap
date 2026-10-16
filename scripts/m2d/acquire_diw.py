# ruff: noqa: E501
"""M2D: acquire DIW (Department of Industrial Works) factory registers as structured CSV (RAW, unchanged, hashed).

Source: the DIW open-data CKAN (diw-dataset.diw.go.th), mirrored on data.go.th. Resource URLs come from package_show, not page scraping.
Factory-present is NOT nuisance-confirmed: a register entry says a licensed/notified factory is recorded, nothing about emissions or noise.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, download, raw_dir

VERSION = "diw-ckan-2026-10-16"
HOST = "https://diw-dataset.diw.go.th"
PACKAGES = ["factype2", "factype3", "factype101-105-106"]
UA = {"User-Agent": "Mozilla/5.0 HearthMap/0.1 (local research)"}


def package(name: str) -> dict:
    with urllib.request.urlopen(
        urllib.request.Request(f"{HOST}/api/3/action/package_show?id={name}", headers=UA),
        timeout=90,
    ) as r:
        return json.loads(r.read())["result"]


def main() -> int:
    d = raw_dir(Path("data"), "industry-diw-factories", VERSION)
    if (d / "manifest.json").exists():
        print("already acquired")
        return 0
    arts, meta = [], {}
    for name in PACKAGES:
        p = package(name)
        res = next(r for r in p["resources"] if r["format"].upper() == "CSV")
        arts.append(download(res["url"], d, filename=f"{name}.csv"))
        meta[name] = {
            "title": p["title"],
            "licence": p.get("license_title"),
            "metadata_modified": p["metadata_modified"],
            "resource_last_modified": res.get("last_modified"),
            "resource_url": res["url"],
            "organization": (p.get("organization") or {}).get("title"),
        }
    RawManifest(
        source_id="industry-diw-factories",
        version=VERSION,
        landing_page=HOST,
        licence="Open Data Common (as stated by the DIW catalogue)",
        publisher_metadata=meta,
        notes=["Register entries; factory presence is not confirmed nuisance."],
        artifacts=arts,
    ).write(d)
    print("acquired", [a.size_bytes for a in arts])
    return 0


if __name__ == "__main__":
    sys.exit(main())
