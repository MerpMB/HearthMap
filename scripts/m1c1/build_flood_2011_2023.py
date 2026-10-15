"""M1C.1: validate and normalise GISTDA flood recurrence 2011-2023 (RAW API tiles).

Source-native fields are kept unchanged (`total`, one column per year from
`detail[].freq`, the administrative names and the API `area`). Every check is
reported in outputs/m1c1/flood-2011-2023-qa.json; repairs are audited, never
silent. Output: data/processed/m1c1/flood.gpkg#flood_recurrence_2011_2023
(EPSG:32647) with a provenance sidecar.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import AOI_LONLAT, CANONICAL, PROCESSED, raw_source, source_ref, write_layer

from hearthmap.enums import Confidence
from hearthmap.qa import audit_repairs
from hearthmap.qa.repair import summarise_repairs
from hearthmap.spatial import check_geometries, repair_geometries
from hearthmap.spatial.transform import reproject_recorded

SOURCE_ID = "flood-gistda-history"
YEARS = list(range(2011, 2024))
OUT_DIR = Path("outputs/m1c1")
LAYER_PATH = Path("data/processed/m1c1/flood.gpkg")
LAYER = "flood_recurrence_2011_2023"


def read_tiles(d: Path) -> tuple[gpd.GeoDataFrame, dict]:
    rows, geoms, meta = [], [], Counter()
    detail_shapes = Counter()
    for f in sorted(d.glob("tile_*.json")):
        data = json.loads(f.read_bytes())
        if isinstance(data, dict):
            meta[f"tile_response_{json.dumps(data, sort_keys=True)}"] += 1
            continue
        meta["tiles_with_features"] += 1
        for i, feat in enumerate(data):
            det = {int(x["year"]): x["freq"] for x in feat["detail"]}
            detail_shapes[tuple(sorted(det))] += 1
            row = {
                "tile": f.stem,
                "tile_feature_index": i,
                "province_name": feat.get("province_name"),
                "district_name": feat.get("district_name"),
                "subdistrict_name": feat.get("subdistrict_name"),
                "total": feat["total"],
                "api_area": feat.get("area"),
            }
            row |= {f"y{y}": det.get(y) for y in YEARS}
            rows.append(row)
            geoms.append(shapely.geometry.shape(feat["geom"]) if feat.get("geom") else None)
    gdf = gpd.GeoDataFrame(rows, geometry=geoms, crs="EPSG:4326")
    meta["detail_year_sets"] = {str(k): v for k, v in detail_shapes.items()}
    return gdf, dict(meta)


def overlap_audit(gdf: gpd.GeoDataFrame) -> dict:
    """Pairwise polygon overlap (area > 0) in a metric CRS: are areas additive?"""
    g = gdf.geometry.values
    tree = shapely.STRtree(g)
    a, b = tree.query(g, predicate="intersects")
    keep = a < b
    a, b = a[keep], b[keep]
    n_pairs = len(a)
    # neighbours that only share an edge (tile seams, subdistrict splits) cannot overlap
    interior = ~shapely.touches(g[a], g[b])
    a, b = a[interior], b[interior]
    inter = shapely.area(shapely.intersection(g[a], g[b]))
    pos = inter > 1e-6
    same_total = gdf["total"].to_numpy()[a[pos]] == gdf["total"].to_numpy()[b[pos]]
    return {
        "intersecting_pairs": n_pairs,
        "pairs_with_interior_contact": len(a),
        "overlapping_pairs_area_gt_1e-6_m2": int(pos.sum()),
        "overlap_area_total_m2": float(inter[pos].sum()),
        "overlap_area_max_m2": float(inter[pos].max()) if pos.any() else 0.0,
        "overlapping_pairs_same_total": int(same_total.sum()),
        "layer_area_km2": float(shapely.area(g).sum() / 1e6),
    }


def main() -> int:
    d, manifest = raw_source(SOURCE_ID)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gdf, meta = read_tiles(d)
    qa: dict = {"raw_version": manifest.version, "tiles": len(manifest.artifacts), **meta}
    qa["features_raw"] = len(gdf)

    # ---- source-native semantics
    yc = [f"y{y}" for y in YEARS]
    freq = gdf[yc]
    qa["detail_freq_values"] = {
        str(k): int(v) for k, v in Counter(freq.to_numpy().ravel().tolist()).items()
    }
    qa["total_equals_sum_of_yearly_freq"] = int((freq.sum(axis=1) == gdf["total"]).sum())
    qa["total_distribution"] = {
        str(k): int(v) for k, v in gdf["total"].value_counts().sort_index().items()
    }
    qa["province_name_values"] = gdf["province_name"].value_counts().to_dict()
    qa["geometry_types_raw"] = gdf.geom_type.value_counts().to_dict()

    # ---- geometry checks (lon/lat), explicit repair audit in a metric CRS
    before = check_geometries(gdf)
    qa["geometry_before"] = before.summary()
    gdf["fid"] = np.arange(len(gdf))
    utm_raw, _ = reproject_recorded(gdf, CANONICAL, name=LAYER, area_of_interest=AOI_LONLAT)
    audit = audit_repairs(utm_raw, id_column="fid")
    qa["repair_audit"] = summarise_repairs(audit, total_features=len(gdf))
    audit.to_csv(OUT_DIR / "flood-2011-2023-repair-audit.csv", index=False)
    if not before.ok:
        gdf = repair_geometries(gdf)
    # keep polygonal parts only (tile clipping can leave slivers/lines)
    gdf["geometry"] = [
        shapely.union_all(
            [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
        )
        if g is not None
        else None
        for g in gdf.geometry.values
    ]
    empty = gdf.geometry.isna() | gdf.geometry.is_empty
    qa["empty_or_non_polygonal_dropped"] = int(empty.sum())
    gdf = gdf[~empty].copy()

    # ---- reprojection (WGS 84 lon/lat -> UTM 47N, same datum) with recorded op
    utm, tr = reproject_recorded(gdf, CANONICAL, name=LAYER, area_of_interest=AOI_LONLAT)
    qa["transformation"] = tr.operation
    qa["datum_change"] = tr.datum_change
    after = check_geometries(utm)
    qa["geometry_after"] = after.summary()

    # ---- duplicates (identical geometry + attributes) and API area units
    wkb = shapely.to_wkb(utm.geometry.values)
    key = pd.Series(list(zip(wkb, utm["total"], strict=True)))
    qa["exact_duplicates"] = int(key.duplicated().sum())
    utm = utm[~key.duplicated().to_numpy()].copy()
    ratio = utm["api_area"] / utm.geometry.area
    big = utm.geometry.area > 1000
    qa["api_area_over_utm_area_m2"] = {
        "median": float(ratio[big].median()),
        "p05": float(ratio[big].quantile(0.05)),
        "p95": float(ratio[big].quantile(0.95)),
        "note": "ratio ~1 => API `area` is m2 of the clipped polygon",
    }

    # ---- overlap semantics
    qa["overlap"] = overlap_audit(utm)

    # ---- AOI coverage
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.values)
    inside = utm.intersects(aoi)
    qa["features_intersecting_aoi"] = int(inside.sum())
    utm = utm[inside].copy()
    qa["aoi_area_km2"] = float(aoi.area / 1e6)
    shapely.prepare(aoi)
    geoms = utm.geometry.values
    a_in = shapely.area(geoms)
    edge = ~shapely.contains_properly(aoi, geoms)  # only boundary polygons need clipping
    a_in[edge] = shapely.area(shapely.intersection(geoms[edge], aoi))
    qa["flooded_area_in_aoi_km2_by_total"] = {
        str(k): round(float(v), 3)
        for k, v in utm.assign(a=a_in / 1e6).groupby("total")["a"].sum().items()
    }
    qa["tile_coverage_note"] = (
        "All tiles touching the three provinces were requested and answered HTTP 200 "
        "(empty tiles answered {'result': 'not found'}); the source is national."
    )

    utm = utm.drop(columns=["fid"])
    utm["years_flooded"] = utm["total"].astype(int)  # alias, source-native meaning kept
    write_layer(
        utm,
        LAYER_PATH,
        LAYER,
        sources=[source_ref(SOURCE_ID, original_crs="EPSG:4326")],
        method="GISTDA flood-recurrence API (2011-2023) tiles; polygons clipped by the API "
        "to each tile; source-native `total` = years observed flooded (sum of yearly "
        "detail.freq 0/1), y2011..y2023 kept; polygonal parts only; reprojected with a "
        "recorded operation.",
        resolution="20 m (publisher metadata)",
        confidence=Confidence.MEDIUM,
        limitations=[
            "HISTORICAL OBSERVED flooding (satellite), not modelled hazard, not current events.",
            "Absence of a polygon is NOT evidence of no flood risk (flash floods, cloud cover).",
            "Methodology summary only ('frequency of floods in 10-year period' text vs a 13-"
            "year record); detailed method not published.",
            "Ends 2023; 2024-2026 not covered.",
        ],
        transformations=[tr],
        steps=[
            ("validate", "geometry check on API polygons", {"report": before.summary()}),
            ("repair_audit", "make_valid audit (see repair-audit csv)", qa["repair_audit"]),
        ],
    )
    (OUT_DIR / "flood-2011-2023-qa.json").write_text(
        json.dumps(qa, indent=2, ensure_ascii=False, default=str) + "\n", "utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in qa.items() if k != "province_name_values"},
            indent=1,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
