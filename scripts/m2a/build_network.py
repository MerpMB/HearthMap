"""M2A: build the routable directed road network from the raw OSM Overpass extract and cache it.

Reads data/raw/osm-overpass-aoi (immutable). Shared vertices are identified by exact lon/lat rounded to 1e-7 deg.
Writes data/processed/m2a/network.npz and outputs/m2a-review/network-stats.json.
"""

# ruff: noqa: E501

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from pyproj import Transformer

from hearthmap.family.routing import build_network

RAW = Path("data/raw/osm-overpass-aoi/2026-10-15")
OUT = Path("data/processed/m2a")
REVIEW = Path("outputs/m2a-review")
EXCLUDED_ACCESS = {"no", "private"}


def load_ways() -> tuple[list[dict], dict]:
    tr = Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
    seen: set[int] = set()
    ways: list[dict] = []
    raw_counts = {
        "ways_read": 0,
        "duplicates_dropped": 0,
        "non_road_dropped": 0,
        "access_excluded": 0,
    }
    for f in sorted(RAW.glob("*_roads.json")):
        for e in json.loads(f.read_text("utf-8"))["elements"]:
            raw_counts["ways_read"] += 1
            if e["id"] in seen:
                raw_counts["duplicates_dropped"] += 1
                continue
            seen.add(e["id"])
            t = e.get("tags", {})
            hw = t.get("highway")
            if not hw or "geometry" not in e:
                raw_counts["non_road_dropped"] += 1
                continue
            if t.get("access") in EXCLUDED_ACCESS or t.get("motor_vehicle") in {"no", "private"}:
                raw_counts["access_excluded"] += 1
                continue
            g = e["geometry"]
            lon = np.array([p["lon"] for p in g])
            lat = np.array([p["lat"] for p in g])
            ways.append(
                {
                    "id": e["id"],
                    "highway": hw,
                    "oneway": t.get("oneway") if t.get("junction") != "roundabout" else "yes",
                    "lon": lon,
                    "lat": lat,
                }
            )
    # project in one vectorised call
    sizes = [len(w["lon"]) for w in ways]
    x, y = tr.transform(
        np.concatenate([w["lon"] for w in ways]), np.concatenate([w["lat"] for w in ways])
    )
    off = 0
    for w, k in zip(ways, sizes, strict=True):
        w["xy"] = np.column_stack([x[off : off + k], y[off : off + k]])
        w["keys"] = np.round(w["lon"] * 1e7).astype(np.int64) * (1 << 28) + np.round(
            w["lat"] * 1e7
        ).astype(np.int64)
        off += k
        del w["lon"], w["lat"]
    return ways, raw_counts


def main() -> int:
    t0 = time.time()
    ways, counts = load_ways()
    print(f"ways {len(ways):,} loaded in {time.time() - t0:.0f}s", counts)
    net = build_network(ways)
    print(
        f"nodes {len(net.xy):,} directed edges {len(net.indices):,} components {len(net.component_size):,} in {time.time() - t0:.0f}s"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        OUT / "network.npz",
        xy=net.xy,
        indptr=net.indptr,
        indices=net.indices,
        length_m=net.length_m,
        hw_code=net.hw_code,
        classes=np.array(net.classes),
        component=net.component,
        component_size=net.component_size,
    )
    sizes = np.sort(net.component_size)[::-1]
    by_class = {
        c: float(net.length_m[net.hw_code == i].sum() / 1000) for i, c in enumerate(net.classes)
    }
    stats = {
        **counts, "ways_used": len(ways), "nodes": len(net.xy), "directed_edges": len(net.indices), "components": len(sizes),
        "largest_component_nodes": int(sizes[0]), "largest_component_share_of_nodes": float(sizes[0] / len(net.xy)),
        "components_ge_500_nodes": int((sizes >= 500).sum()), "nodes_in_components_ge_500": int(sizes[sizes >= 500].sum()),
        "directed_km_by_class": by_class, "oneway_ways": int(sum(1 for w in ways if str(w.get("oneway")) in {"yes", "-1", "true", "1"})),
    }  # fmt: skip
    (REVIEW / "network-stats.json").write_text(json.dumps(stats, indent=2) + "\n", "utf-8")
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
