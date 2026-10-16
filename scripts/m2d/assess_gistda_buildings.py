# ruff: noqa: E501
"""M2D: assess (not acquire) the GISTDA nationwide building-footprint feature API with the project's own key.

Counts only: three requests (collection metadata, a small and a medium test window, the AOI envelope). Response bodies are never printed or
stored because GISTDA echoes the caller's api_key inside the `links` array. The key is read from the environment/.env.local, never printed,
never written. Result: outputs/m2d-review/gistda-buildings-assessment.json (decision: DEFERRED, see `decision`).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from hearthmap.ingestion.secrets import load_secret

BASE = "https://api-gateway.gistda.or.th/api/2.0/resources/features/thailand-buildings-footprint"
UA = {"User-Agent": "HearthMap/0.1 (local research)"}
WINDOWS = {
    "small_1x1km_urban_chiang_mai": (98.98, 18.79, 98.99, 18.80),
    "medium_5x5km_urban_chiang_mai": (98.97, 18.78, 99.02, 18.83),
    "aoi_envelope_three_provinces": (97.9, 17.7, 101.4, 20.6),
}
OUT = Path("outputs/m2d-review")


def main() -> int:
    key = load_secret("GISTDA_API_KEY")
    result: dict = {
        "endpoint": BASE,
        "method": "GET collection metadata and items?limit=1&bbox=... (counts only; bodies never stored)",
        "windows": {},
    }

    def call(path: str, **params):
        url = f"{BASE}{path}?" + urllib.parse.urlencode({"api_key": key.reveal(), **params})
        t = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return r.status, json.loads(r.read()), round(time.time() - t, 1)
        except urllib.error.HTTPError as e:
            return e.code, None, round(time.time() - t, 1)
        except Exception as e:
            return type(e).__name__, None, round(time.time() - t, 1)

    st, meta, _ = call("")
    if meta:
        result["collection"] = {
            k: meta.get(k)
            for k in ("alias", "title", "description", "itemType", "public", "storageCrs")
        } | {
            "spatial_bbox": meta["extent"]["spatial"]["bbox"],
            "temporal_start": meta["extent"]["temporal"]["interval"][0][0],
        }
    st, items, _ = call("/items", limit=1)
    if items:
        f = items["features"][0]
        result["national_feature_count"] = items.get("numberMatched")
        result["geometry_form"] = f["geometry"]["type"]
        result["property_names"] = sorted(f["properties"])
        result["sample_source_values"] = f["properties"].get("sources")
    for name, bb in WINDOWS.items():
        st, d, secs = call("/items", limit=1, bbox=",".join(map(str, bb)))
        result["windows"][name] = {
            "bbox": bb,
            "http_status": st,
            "seconds": secs,
            "numberMatched": d.get("numberMatched") if d else None,
        }
    result["licence_or_terms"] = (
        "NOT SPECIFIED: the open-data catalogue lists 'License not specified'; access requires a registered API key (api-gateway.gistda.or.th)"
    )
    result["decision"] = "DEFERRED"
    result["reasons"] = [
        "no stated licence or terms for bulk extraction",
        f"{result.get('national_feature_count')} features nationally; the AOI-envelope count request does not complete (see windows), so a bulk extract is not a reasonable use of this API",
        "a 5 km x 5 km urban window already holds tens of thousands of footprints; paging millions through a gateway that times out on counts is impractical",
        "the layer merges several modelled sources (Google, Microsoft, OSM, others): completeness is not uniform and must be assessed before any density signal",
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, indent=1, ensure_ascii=False)
    assert "api_key" not in text.lower()
    (OUT / "gistda-buildings-assessment.json").write_text(text + "\n", "utf-8")
    print(
        json.dumps(
            {k: result.get(k) for k in ("national_feature_count", "windows", "decision")},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
