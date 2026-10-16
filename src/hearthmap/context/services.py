# ruff: noqa: E501
"""Town-service components from OSM tags. Components are never merged into one opaque 'town POI' category.

Clusters are descriptive groupings of distinct service components that sit close together. Two exposed definitions (CORE, BROADER) are
reported side by side; neither is chosen here, and neither is a score.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import shapely

COMPONENTS = (
    "GROCERY_OR_SUPERMARKET",
    "CONVENIENCE_STORE",
    "MARKET",
    "PHARMACY",
    "BANK_OR_FINANCIAL",
    "FUEL",
    "PUBLIC_ADMINISTRATION",
    "GENERAL_RETAIL_OR_SERVICE",
)
SHOP = {
    "supermarket": "GROCERY_OR_SUPERMARKET",
    "grocery": "GROCERY_OR_SUPERMARKET",
    "convenience": "CONVENIENCE_STORE",
    "department_store": "GENERAL_RETAIL_OR_SERVICE",
    "mall": "GENERAL_RETAIL_OR_SERVICE",
    "variety_store": "GENERAL_RETAIL_OR_SERVICE",
    "general": "GENERAL_RETAIL_OR_SERVICE",
    "hardware": "GENERAL_RETAIL_OR_SERVICE",
    "doityourself": "GENERAL_RETAIL_OR_SERVICE",
    "greengrocer": "GENERAL_RETAIL_OR_SERVICE",
}
AMENITY = {
    "marketplace": "MARKET",
    "pharmacy": "PHARMACY",
    "bank": "BANK_OR_FINANCIAL",
    "atm": "BANK_OR_FINANCIAL",
    "fuel": "FUEL",
    "townhall": "PUBLIC_ADMINISTRATION",
}
NIGHTLIFE = {
    "bar": "BAR",
    "pub": "PUB",
    "nightclub": "NIGHTCLUB",
    "stripclub": "STRIPCLUB",
    "karaoke_box": "KARAOKE_BOX",
}
# exposed assumptions; none is selected as the production definition
CLUSTER_DEFINITIONS = {
    "CORE": {"link_m": 400.0, "min_distinct_components": 4},
    "BROADER": {"link_m": 800.0, "min_distinct_components": 3},
}
DEDUP_SAME_COMPONENT_M = 40.0


def classify_tags(tags: dict[str, str]) -> tuple[str | None, str | None]:
    """(service component, nightlife subtype). Nightlife wins over service and is never a service component."""
    am = tags.get("amenity")
    if am in NIGHTLIFE:
        return None, NIGHTLIFE[am]
    if am in AMENITY:
        return AMENITY[am], None
    if tags.get("healthcare") == "pharmacy":
        return "PHARMACY", None
    if tags.get("shop") in SHOP:
        return SHOP[tags["shop"]], None
    if tags.get("office") == "government":
        return "PUBLIC_ADMINISTRATION", None
    return None, None


def parse_overpass(payload: dict[str, Any], province: str) -> pd.DataFrame:
    rows = []
    for e in payload["elements"]:
        tags = e.get("tags", {})
        comp, night = classify_tags(tags)
        if comp is None and night is None:
            continue
        c = e.get("center") or e
        if "lat" not in c:
            continue
        rows.append(
            {
                "osm_id": f"{e['type'][0]}{e['id']}", "province": province, "lon": c["lon"], "lat": c["lat"], "component": comp, "nightlife_subtype": night,
                "osm_tag": next((f"{k}={tags[k]}" for k in ("amenity", "shop", "healthcare", "office") if k in tags), ""), "name": tags.get("name", ""),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def _union_find(n: int, pairs: np.ndarray) -> np.ndarray:
    parent = np.arange(n)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs.tolist():
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return np.array([find(i) for i in range(n)])


def link_groups(xy: np.ndarray, link_m: float) -> np.ndarray:
    """Group id (smallest member index) of points chained together by <= link_m."""
    if len(xy) == 0:
        return np.zeros(0, dtype=int)
    pts = shapely.points(xy)
    tree = shapely.STRtree(pts)
    pairs = tree.query(pts, predicate="dwithin", distance=link_m)
    return _union_find(len(xy), pairs.T)


def dedup_same_component(df: pd.DataFrame, xy: np.ndarray) -> pd.Series:
    """True for the rows kept: within a component, features closer than DEDUP_SAME_COMPONENT_M collapse to one."""
    keep = np.zeros(len(df), dtype=bool)
    for _, idx in df.groupby("component").indices.items():
        g = link_groups(xy[idx], DEDUP_SAME_COMPONENT_M)
        first = {}
        for j, gid in zip(idx, g, strict=True):
            first.setdefault(gid, j)
        keep[list(first.values())] = True
    return pd.Series(keep, index=df.index)


def cluster_labels(df: pd.DataFrame, xy: np.ndarray, definition: dict[str, float]) -> np.ndarray:
    """Cluster id per POI (-1 when its linked group has fewer distinct components than the definition requires)."""
    g = link_groups(xy, definition["link_m"])
    out = np.full(len(df), -1, dtype=int)
    comp = df["component"].to_numpy()
    for gid in np.unique(g):
        m = g == gid
        if len(set(comp[m])) >= definition["min_distinct_components"]:
            out[m] = gid
    return out
