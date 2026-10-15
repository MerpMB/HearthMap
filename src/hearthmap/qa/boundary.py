"""Boundary disagreement audit between a primary boundary and references.

Zones are the individual polygon parts of the symmetric difference between the
primary province polygon and a reference polygon for the same province. For
each zone we measure how far the reference departs from the primary boundary
and attach PROVISIONAL classifications from simple, documented rules. The
rules describe geometry; they do not establish causes.

Nothing here modifies any boundary or influences suitability.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from hearthmap.spatial.crs import assert_metric_crs, require_crs, same_crs

GENERALIZATION_WIDTH_M = 200.0  # mean width below which a sliver looks like line generalisation
POTENTIALLY_MATERIAL_OFFSET_M = 1000.0
BORDER_PROXIMITY_M = 100.0


def _segments_tree(geom: shapely.Geometry) -> shapely.STRtree:
    coords = [shapely.get_coordinates(g) for g in shapely.get_parts(geom)]
    segs = np.concatenate(
        [shapely.linestrings(np.stack([c[:-1], c[1:]], axis=1)) for c in coords if len(c) > 1]
    )
    return shapely.STRtree(segs)


def _sample_boundary(poly: shapely.Geometry, step: float) -> np.ndarray:
    pts = []
    for ring in shapely.get_parts(shapely.line_merge(poly.boundary)):
        n = max(int(ring.length // step), 4)
        pts.append(
            shapely.line_interpolate_point(ring, np.linspace(0, ring.length, n, endpoint=False))
        )
    return np.concatenate(pts) if pts else np.array([])


def classify_zone(
    *, max_offset_m: float, mean_width_m: float, border_type: str, material_offset_m: float
) -> tuple[str, str]:
    """Provisional class + the rule that produced it (stored for transparency)."""
    if max_offset_m < material_offset_m and mean_width_m < GENERALIZATION_WIDTH_M:
        return (
            "LIKELY_SOURCE_GENERALIZATION",
            f"thin sliver: max offset < {material_offset_m:g} m and mean width < "
            f"{GENERALIZATION_WIDTH_M:g} m",
        )
    if border_type == "international" and max_offset_m >= material_offset_m:
        return (
            "LIKELY_BORDER_INTERPRETATION",
            "on the international border, where delineations are known to differ "
            "between sources; offset exceeds the materiality threshold",
        )
    if max_offset_m >= POTENTIALLY_MATERIAL_OFFSET_M:
        return (
            "POTENTIALLY_MATERIAL",
            f"inter-provincial edge displaced >= {POTENTIALLY_MATERIAL_OFFSET_M:g} m",
        )
    return ("UNKNOWN", "no rule matched with confidence")


def disagreement_zones(
    primary: gpd.GeoDataFrame,
    reference: gpd.GeoDataFrame,
    *,
    key: str,
    reference_name: str,
    grid: gpd.GeoDataFrame | None = None,
    districts: gpd.GeoDataFrame | None = None,
    district_name: str = "adm2_name",
    national_border: shapely.Geometry | None = None,
    material_offset_m: float = 250.0,
    sample_step_m: float = 50.0,
    min_area_m2: float = 1.0,
) -> gpd.GeoDataFrame:
    crs = require_crs(primary, name="primary")
    assert_metric_crs(crs, purpose="boundary disagreement audit")
    if not same_crs(crs, require_crs(reference, name=reference_name)):
        raise ValueError("reference CRS differs from primary; reproject first")

    rows = []
    for _, p in primary.iterrows():
        match = reference[reference[key] == p[key]]
        if len(match) != 1:
            raise ValueError(
                f"{reference_name}: expected one feature for {p[key]}, got {len(match)}"
            )
        a, b = p.geometry, match.geometry.iloc[0]
        tree = _segments_tree(a.boundary)
        others = primary[primary[key] != p[key]]
        others_union = shapely.union_all(others.geometry.values) if len(others) else None
        for kind, diff in (("primary_only", a.difference(b)), ("reference_only", b.difference(a))):
            for part in shapely.get_parts(diff):
                if part.area < min_area_m2:
                    continue
                pts = _sample_boundary(part, sample_step_m)
                _, d = tree.query_nearest(pts, return_distance=True, all_matches=False)
                far = d[d > 1.0]
                border_type = "neighbour_province"
                if (
                    national_border is not None
                    and part.distance(national_border) <= BORDER_PROXIMITY_M
                ):
                    border_type = "international"
                elif others_union is not None and part.distance(others_union) <= BORDER_PROXIMITY_M:
                    border_type = "aoi_internal"
                mean_width = 2 * part.area / part.length if part.length else 0.0
                rows.append(
                    {
                        "province": p[key],
                        "reference_source": reference_name,
                        "kind": kind,
                        "area_km2": part.area / 1e6,
                        "max_offset_m": float(d.max()) if len(d) else 0.0,
                        "median_offset_m": float(np.median(far)) if len(far) else 0.0,
                        "mean_width_m": mean_width,
                        "border_type": border_type,
                        "geometry": part,
                    }
                )
    zones = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
    if zones.empty:
        return zones

    cls = [
        classify_zone(
            max_offset_m=r.max_offset_m,
            mean_width_m=r.mean_width_m,
            border_type=r.border_type,
            material_offset_m=material_offset_m,
        )
        for r in zones.itertuples()
    ]
    zones["provisional_class"] = [c[0] for c in cls]
    zones["classification_rule"] = [c[1] for c in cls]
    zones["material"] = zones["max_offset_m"] >= material_offset_m

    if districts is not None:
        dtree = shapely.STRtree(districts.geometry.values)
        idx = dtree.query_nearest(zones.geometry.values, all_matches=False)[1]
        zones["nearest_district"] = districts[district_name].to_numpy()[idx]
    if grid is not None:
        gtree = shapely.STRtree(grid.geometry.values)
        zi, gi = gtree.query(zones.geometry.values, predicate="intersects")
        inter = shapely.area(
            shapely.intersection(zones.geometry.values[zi], grid.geometry.values[gi])
        )
        hits = pd.Series(gi[inter > 0]).groupby(zi[inter > 0]).nunique()
        zones["affected_grid_cells"] = hits.reindex(range(len(zones)), fill_value=0).to_numpy()
    lonlat = zones.geometry.representative_point().to_crs("EPSG:4326")
    zones["lon"] = lonlat.x.round(4)
    zones["lat"] = lonlat.y.round(4)
    zones = zones.sort_values("area_km2", ascending=False).reset_index(drop=True)
    zones.insert(
        0, "zone_id", [f"{r}-{i + 1:04d}" for i, r in enumerate(zones["reference_source"])]
    )
    return zones


def uncertainty_cells(
    grid: gpd.GeoDataFrame, zones: gpd.GeoDataFrame, *, id_column: str = "cell_id"
) -> gpd.GeoDataFrame:
    """Grid cells intersecting MATERIAL disagreement zones, with per-reference fractions.

    Output is a review layer: it never feeds suitability (see qa.review).
    """
    mat = zones[zones["material"]]
    out = grid[[id_column, "geometry"]].copy()
    flags = []
    for ref, z in mat.groupby("reference_source"):
        u = shapely.union_all(z.geometry.values)
        shapely.prepare(u)
        hit = shapely.intersects(u, out.geometry.values)
        frac = np.zeros(len(out))
        if hit.any():
            frac[hit] = shapely.area(
                shapely.intersection(out.geometry.values[hit], u)
            ) / shapely.area(out.geometry.values[hit])
        col = f"disagreement_fraction_{ref.replace('-', '_')}"
        out[col] = frac
        flags.append(col)
    if not flags:
        return out.iloc[0:0]
    out = out[(out[flags] > 0).any(axis=1)].copy()
    out["references_disagreeing"] = (out[flags] > 0).sum(axis=1)
    return out
