"""Readers for the RAW formats acquired in M1A (read-only; RAW is never modified)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import LineString


def read_esrijson_pages(directory: Path, prefix: str) -> gpd.GeoDataFrame:
    """Concatenate ArcGIS REST JSON pages ``<prefix>_NNNNN.json`` (GDAL ESRIJSON driver)."""
    paths = sorted(Path(directory).glob(f"{prefix}_*.json"))
    if not paths:
        raise FileNotFoundError(f"no pages {prefix}_*.json in {directory}")
    frames = [pyogrio.read_dataframe(p) for p in paths]  # GDAL autodetects ESRIJSON
    crs = frames[0].crs
    if any(f.crs != crs for f in frames):
        raise ValueError(f"{prefix}: pages disagree on CRS")
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs)


def read_overpass_ways(
    paths: Iterable[Path], *, keep_tags: Iterable[str] = ("highway", "waterway", "name", "ref")
) -> gpd.GeoDataFrame:
    """Overpass ``out tags geom`` JSON -> LineStrings in EPSG:4326, one row per way id.

    Ways returned for more than one province query are de-duplicated by OSM id.
    """
    keep_tags = list(keep_tags)
    rows: dict[int, dict] = {}
    for path in paths:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        for el in payload.get("elements", []):
            if el.get("type") != "way" or len(el.get("geometry") or []) < 2:
                continue
            tags = el.get("tags", {})
            rows[el["id"]] = {
                "osm_id": el["id"],
                **{t: tags.get(t) for t in keep_tags},
                "geometry": LineString([(p["lon"], p["lat"]) for p in el["geometry"]]),
            }
    return gpd.GeoDataFrame(list(rows.values()), geometry="geometry", crs="EPSG:4326")
