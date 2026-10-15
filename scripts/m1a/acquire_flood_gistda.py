"""M1A: acquire GISTDA repeated-flooding 2005-2016 (1:50k) for the AOI provinces.

Server-side filter by province code; each page stored untouched in RAW.
"""

from __future__ import annotations

import sys
from pathlib import Path

from hearthmap.ingestion.acquire import RawManifest, raw_dir
from hearthmap.ingestion.arcgis import fetch_pages, layer_metadata

SOURCE_ID = "flood-gistda-repeated-2005-2016"
VERSION = "service-2026-10-15"
LAYER = (
    "https://gistdaportal.gistda.or.th/data/rest/services/FL_Flood/"
    "FL_RepeatedFlooding_GISTDA_50k_Y2005_Y2016/FeatureServer/0"
)
WHERE = "pv_code in ('50','56','57')"
FIELDS = [
    "objectid",
    *(f"year{y}" for y in range(2005, 2017)),
    "flood_freq",
    "tb_code",
    "ap_code",
    "pv_code",
]


def main() -> int:
    dest = raw_dir(Path("data"), SOURCE_ID, VERSION)
    meta = layer_metadata(LAYER)
    artifacts, n = fetch_pages(
        LAYER,
        where=WHERE,
        out_fields=FIELDS,
        order_by="objectid",
        dest_dir=dest,
        prefix="page",
        progress=lambda r, e: print(f"{r}/{e}", flush=True) if r % 20000 < 1000 else None,
    )
    RawManifest(
        source_id=SOURCE_ID,
        version=VERSION,
        landing_page="https://gistdaportal.gistda.or.th/data/rest/services/FL_Flood",
        licence=(
            "Not stated on the service (copyright: GISTDA). "
            "Internal analysis only; do not redistribute."
        ),
        publisher_metadata={"layer": meta, "where": WHERE, "feature_count": n},
        notes=[
            "Pages are ArcGIS JSON in EPSG:3857 exactly as served.",
            "Service advertises editing capabilities; HearthMap only reads.",
        ],
        artifacts=artifacts,
    ).write(dest)
    print(f"done: {n} features in {len(artifacts)} pages -> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
