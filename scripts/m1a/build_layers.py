"""M1A stage: normalise flood, forest/protected and OSM layers + grid overlay metrics.

Nothing here is a score. Overlay metrics are area-based geometry facts per cell
(affected_area_fraction, max value, feature count, distance to feature).
Forest/protected overlaps are SCREENING evidence that REQUIRES LEGAL
VERIFICATION; flood recurrence is OBSERVED HISTORICAL flooding only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    AOI_LONLAT,
    CANONICAL,
    PROCESSED,
    VALIDATION,
    raw_source,
    source_ref,
    write_json,
    write_layer,
)

from hearthmap.enums import Confidence
from hearthmap.ingestion.readers import read_esrijson_pages, read_overpass_ways
from hearthmap.spatial import check_geometries, repair_geometries
from hearthmap.spatial.overlay import polygon_cell_metrics
from hearthmap.spatial.transform import reproject_recorded

REPORT: dict = {"stage": "VALIDATED/NORMALIZED"}


def _normalise(gdf: gpd.GeoDataFrame, name: str) -> tuple[gpd.GeoDataFrame, object, list]:
    """Validate (report), repair explicitly if needed, reproject with a recorded op."""
    before = check_geometries(gdf)
    steps = [("validate", "geometry check on source", {"report": before.summary()})]
    if not before.ok:
        gdf = repair_geometries(gdf)
        gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
        steps.append(
            (
                "repair",
                "shapely.make_valid on invalid geometries; empties dropped",
                {
                    "invalid_before": before.invalid,
                    "null_before": before.null,
                    "empty_before": before.empty,
                },
            )
        )
    out, tr = reproject_recorded(gdf, CANONICAL, name=name, area_of_interest=AOI_LONLAT)
    after = check_geometries(out)
    REPORT[name] = {
        "source_crs": gdf.crs.to_string(),
        "features": len(out),
        "geometry_before": before.summary(),
        "geometry_after": after.summary(),
        "transformation": tr.operation,
        "datum_change": tr.datum_change,
    }
    return out, tr, steps


def main() -> int:
    aoi = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi_union = aoi.union_all()
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    out = PROCESSED / "layers.gpkg"
    overlays = [grid[["cell_id", "coverage_fraction"]]]

    # ------------------------------------------------------------ flood
    f_dir, _ = raw_source("flood-gistda-repeated-2005-2016")
    flood = read_esrijson_pages(f_dir, "page")
    flood, tr_f, st_f = _normalise(flood, "flood_recurrence")
    REPORT["flood_recurrence"]["flood_freq_counts"] = (
        flood["flood_freq"].value_counts().sort_index().to_dict()
    )
    REPORT["flood_recurrence"]["area_km2_by_freq"] = (
        flood.assign(a=flood.geometry.area / 1e6)
        .groupby("flood_freq")["a"]
        .sum()
        .round(2)
        .to_dict()
    )
    write_layer(
        flood,
        out,
        "flood_recurrence",
        sources=[source_ref("flood-gistda-repeated-2005-2016", original_crs="EPSG:3857")],
        method="GISTDA repeated-flooding polygons 2005-2016 for PV_CODE 50/56/57; "
        "flood_freq = number of years (of 12) with satellite-observed flooding.",
        resolution="1:50,000 mapping scale (per service name)",
        confidence=Confidence.MEDIUM,
        limitations=[
            "HISTORICAL OBSERVED flooding only (satellite). Not modelled hazard, "
            "not current events.",
            "Satellite observation misses short flash floods and cloud-covered peaks: absence of "
            "a polygon is NOT evidence of no flood risk.",
            "Ends in 2016; land use and drainage have changed since.",
            "Licence not stated on the service; internal analysis only.",
        ],
        transformations=[tr_f],
        steps=st_f,
    )
    m = polygon_cell_metrics(grid, flood, prefix="flood_obs", value_column="flood_freq")
    overlays.append(m)

    # ------------------------------------------------------------ forest reserve (RFD)
    raw_source("forest-reserve-rfd")  # re-verifies RAW checksums
    shp = next(Path("data/interim/forest-reserve-rfd").rglob("final_NRF_all_1221_620108.shp"))
    nrf = gpd.read_file(shp)
    REPORT["forest_reserve_national_features"] = len(nrf)
    nrf = nrf[nrf.intersects(aoi_union)].copy()
    nrf["area_rai_gis_computed"] = nrf.geometry.area / 1600.0
    nrf["declared_vs_gis_area_pct"] = 100 * (nrf["rai_GIS"] - nrf["AREA_RAI"]) / nrf["AREA_RAI"]
    nrf["evidence_class"] = "REQUIRES_LEGAL_VERIFICATION"
    nrf, tr_r, st_r = _normalise(nrf, "forest_reserve_screening")
    REPORT["forest_reserve_screening"]["declared_vs_gis_area_pct_quantiles"] = (
        nrf["declared_vs_gis_area_pct"].quantile([0.05, 0.5, 0.95]).round(1).to_dict()
    )
    write_layer(
        nrf,
        out,
        "forest_reserve_screening",
        sources=[source_ref("forest-reserve-rfd", original_crs="EPSG:32647", path=shp.as_posix())],
        method="RFD national reserved forest polygons (1,221 nationally) intersecting the AOI; "
        "extracted from the untouched RAR into data/interim.",
        resolution="Vector; mapping scale not published",
        confidence=Confidence.LOW,
        limitations=[
            "Publisher: data CANNOT certify forest boundaries; certification only by forest "
            "officials. Screening / legal warning only - never a definitive exclusion.",
            "Declared legal area (AREA_RAI) and GIS area (rai_GIS) differ materially for many "
            "reserves - geometry is approximate.",
            "Dataset edition 2019 (filename 620108 = BE 2562-01-08); later revocations or "
            "additions are not reflected.",
        ],
        transformations=[tr_r],
        steps=[("filter", "intersects AOI", {}), *st_r],
    )
    overlays.append(polygon_cell_metrics(grid, nrf, prefix="forest_reserve"))

    # ---------------------------------------- parks / sanctuaries (MNRE via GISTDA)
    p_dir, _ = raw_source("protected-gistda-mnre")
    for prefix, layer, label in (
        ("L10_NPRK_MNRE_50k", "national_park_screening", "national_park"),
        ("L10_WLDS_MNRE_xxk", "wildlife_sanctuary_screening", "wildlife_sanctuary"),
    ):
        g = read_esrijson_pages(p_dir, prefix)
        g = g.explode(index_parts=False).reset_index(drop=True)
        g = g[g.intersects(aoi.to_crs(g.crs).union_all())].copy()
        g["evidence_class"] = "REQUIRES_LEGAL_VERIFICATION"
        g, tr_p, st_p = _normalise(g, layer)
        write_layer(
            g,
            out,
            layer,
            sources=[source_ref("protected-gistda-mnre", original_crs="EPSG:3857")],
            method=f"{prefix} served by GISTDA (MNRE copyright), parts intersecting the AOI.",
            resolution="1:50,000 (national parks, per service description); sanctuaries: scale "
            "not stated ('xxk')",
            confidence=Confidence.LOW,
            limitations=[
                "Screening only; legal status must be verified with DNP / land documents.",
                "National parks layer dated BE 2557 (2014).",
            ],
            transformations=[tr_p],
            steps=st_p,
        )
        overlays.append(polygon_cell_metrics(grid, g, prefix=label))

    # ------------------------------------------------------------ OSM
    o_dir, _ = raw_source("osm-overpass-aoi")
    osm_ref = source_ref("osm-overpass-aoi", original_crs="EPSG:4326")
    osm_lims = [
        "(c) OpenStreetMap contributors, ODbL 1.0. Kept separate from government data.",
        "Completeness varies; absence of a mapped road/stream is not absence in reality.",
        "No surface, width, legal-access or rainy-season information is implied.",
    ]
    lines = {}
    for cat, layer in (
        ("major_roads", "major_roads"),
        ("minor_roads", "minor_roads"),
        ("waterways", "waterways"),
    ):
        g = read_overpass_ways(sorted(o_dir.glob(f"*_{cat}.json")))
        g, tr_o, st_o = _normalise(g, layer)
        REPORT[layer]["classes"] = (
            g[("waterway" if cat == "waterways" else "highway")].value_counts().to_dict()
        )
        REPORT[layer]["length_km"] = round(g.geometry.length.sum() / 1e3, 1)
        write_layer(
            g,
            out,
            layer,
            sources=[osm_ref],
            method=f"Overpass ways ({cat}) per AOI province, de-duplicated by OSM id.",
            resolution="Vector, variable",
            confidence=Confidence.MEDIUM,
            limitations=osm_lims,
            transformations=[tr_o],
            steps=st_o,
        )
        lines[layer] = g

    centroids = grid.geometry.centroid.values
    dist = pd.DataFrame(index=grid.index)
    for name, g in (
        ("major_road", lines["major_roads"]),
        ("river_or_canal", lines["waterways"][lines["waterways"]["waterway"] != "stream"]),
    ):
        tree = shapely.STRtree(g.geometry.values)
        _, d = tree.query_nearest(centroids, return_distance=True, all_matches=False)
        dist[f"dist_{name}_m"] = np.round(d, 1)
    overlays.append(dist)

    ov = gpd.GeoDataFrame(pd.concat(overlays, axis=1), geometry=grid.geometry, crs=CANONICAL)
    ov["overlay_label"] = "GEOMETRY FACTS ONLY - not suitability scores"
    write_layer(
        ov,
        PROCESSED / "overlays.gpkg",
        "screening_overlays_500m",
        sources=[
            source_ref("flood-gistda-repeated-2005-2016", original_crs="EPSG:3857"),
            source_ref("forest-reserve-rfd", original_crs="EPSG:32647"),
            source_ref("protected-gistda-mnre", original_crs="EPSG:3857"),
            osm_ref,
        ],
        method="Area-based overlay (union of intersecting polygons per cell, not centroid "
        "sampling); distances from cell centroid to nearest OSM line.",
        resolution="500 m cells summarising finer vector data",
        confidence=Confidence.LOW,
        limitations=[
            "A fraction of 0 means no mapped feature, not absence of hazard/restriction.",
            "Forest/protected fractions are screening flags requiring legal verification.",
            "Distances are straight-line, not travel distance or legal access.",
        ],
    )
    REPORT["overlay_summary"] = {
        c: {"cells_gt0": int((ov[c] > 0).sum()), "mean": round(float(ov[c].mean()), 4)}
        for c in ov.columns
        if c.endswith("_affected_area_fraction")
    }
    REPORT["overlay_summary"]["narrow_hits_flood"] = int(
        (
            (ov["flood_obs_affected_area_fraction"] > 0)
            & (ov["flood_obs_affected_area_fraction"] < 0.05)
        ).sum()
    )
    write_json(REPORT, VALIDATION / "layers.json")
    print("layers OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
