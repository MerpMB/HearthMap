# ruff: noqa: E501
"""M2A: does the OSM extract contain the official DRR rural highways? (validation only; networks are not merged)"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely


def main() -> int:
    drr = gpd.read_file("data/raw/roads-drr-gis/download-2026-10-16/page_00000.json").to_crs(32647)
    prov = gpd.read_file("data/processed/m1a/boundaries.gpkg", layer="province_boundaries")
    clip = drr.geometry.intersection(prov.geometry.union_all())
    clip = clip[~clip.is_empty]
    lay = "data/processed/m1a/layers.gpkg"
    osm = np.concatenate(
        [gpd.read_file(lay, layer=n).geometry.to_numpy() for n in ("minor_roads", "major_roads")]
    )
    tree = shapely.STRtree(osm)
    pts = []
    for g in clip:
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "LineString" and part.length > 0:
                n = max(2, int(part.length // 100))
                pts += [part.interpolate(i / (n - 1), normalized=True) for i in range(n)]
    _, d = tree.query_nearest(np.array(pts, dtype=object), return_distance=True, all_matches=False)
    out = {
        "drr_links_in_envelope": len(drr),
        "drr_links_intersecting_aoi": len(clip),
        "drr_length_in_aoi_km": round(float(clip.length.sum() / 1000), 1),
        "sample_points": len(pts),
        "within_25m_pct": round(float((d <= 25).mean() * 100), 1),
        "within_50m_pct": round(float((d <= 50).mean() * 100), 1),
        "within_200m_pct": round(float((d <= 200).mean() * 100), 1),
        "note": "links outside the three provinces are clipped away; matches measure OSM presence of official DRR rural highways",
    }
    Path("outputs/m2a-review/osm-vs-drr-validation.json").write_text(
        json.dumps(out, indent=1) + "\n", "utf-8"
    )
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
