"""M1C.1: does one large API tile return everything? (feature-cap check)

The densest RAW tiles are re-requested as four quadrants (stored under
data/interim, not RAW). Flooded area per `total` class must agree between the
whole tile and the sum of its quadrants; a large deficit in the whole tile
would reveal a silent server-side feature limit.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from acquire_flood_gistda_2011_2023 import ENDPOINT, KEY_NAME, TILE_DEG, area_param, fetch
from common import raw_source

from hearthmap.ingestion.secrets import load_secret

SOURCE_ID = "flood-gistda-history"
QA_DIR = Path("data/interim/m1c1/api-completeness")
OUT = Path("outputs/m1c1/flood-2011-2023-api-completeness.json")


def area_by_total(features: list) -> dict[int, float]:
    out: dict[int, float] = {}
    for f in features:
        g = shapely.geometry.shape(f["geom"])
        # degree^2 areas: only ratios within the same tile are compared
        out[f["total"]] = out.get(f["total"], 0.0) + g.area
    return out


def main() -> int:
    secret = load_secret(KEY_NAME)
    d, manifest = raw_source(SOURCE_ID)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    arts = sorted(manifest.artifacts, key=lambda a: a.size_bytes, reverse=True)[:2]
    report = []
    for art in arts:
        _, ix, iy = Path(art.stored_path).stem.split("_")
        x0, y0 = int(ix) * TILE_DEG, int(iy) * TILE_DEG
        whole = json.loads((d / art.stored_path).read_bytes())
        h = TILE_DEG / 2
        quads = []
        for qx in (0, 1):
            for qy in (0, 1):
                b = (x0 + qx * h, y0 + qy * h, x0 + (qx + 1) * h, y0 + (qy + 1) * h)
                b = tuple(round(v, 6) for v in b)
                p = QA_DIR / f"{Path(art.stored_path).stem}_q{qx}{qy}.json"
                if not p.exists():
                    url = (
                        ENDPOINT
                        + "?"
                        + urllib.parse.urlencode(
                            {"api_key": secret.reveal(), "area": area_param(b)}
                        )
                    )
                    p.write_bytes(fetch(url, secret))
                q = json.loads(p.read_bytes())
                quads += q if isinstance(q, list) else []
        aw, aq = area_by_total(whole), area_by_total(quads)
        report.append(
            {
                "tile": art.stored_path,
                "features_whole": len(whole),
                "features_quadrants": len(quads),
                "area_ratio_whole_over_quadrants_by_total": {
                    str(k): round(aw.get(k, 0) / aq[k], 6) for k in sorted(aq)
                },
                "area_ratio_all": round(sum(aw.values()) / sum(aq.values()), 6),
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
