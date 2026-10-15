"""Audit of explicit geometry repair (``make_valid``).

The "before" area of an invalid polygon is computed with the shoelace formula on
the invalid geometry; for self-intersecting rings this can be meaningless (lobes
can cancel). It is reported as DIAGNOSTIC ONLY.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pydantic import BaseModel, ConfigDict

from hearthmap.spatial.crs import assert_metric_crs, require_crs


class RepairAuditRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_feature_id: str
    validity_reason_before: str
    geometry_type_before: str
    geometry_type_after: str
    area_before_diagnostic_m2: float
    area_after_m2: float
    absolute_area_delta_m2: float
    percent_area_delta: float | None
    component_count_before: int
    component_count_after: int
    polygonal_area_dropped_m2: float
    empty_after_repair: bool


def _polygonal(g: shapely.Geometry) -> shapely.Geometry:
    parts = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(parts) if parts else shapely.Polygon()


def audit_repairs(gdf: gpd.GeoDataFrame, *, id_column: str) -> pd.DataFrame:
    """Repair invalid geometries (as M1A did) and describe what changed.

    Areas are measured in the layer's CRS, which must be metric.
    """
    assert_metric_crs(require_crs(gdf), purpose="repair audit")
    geoms = gdf.geometry.values
    invalid = ~shapely.is_valid(geoms) & ~shapely.is_missing(geoms)
    records = []
    for fid, g in zip(gdf.loc[invalid, id_column], geoms[invalid], strict=True):
        fixed = shapely.make_valid(g)
        poly = _polygonal(fixed)
        before = float(shapely.area(g))
        after = float(poly.area)
        delta = after - before
        records.append(
            RepairAuditRecord(
                source_feature_id=str(fid),
                validity_reason_before=shapely.is_valid_reason(g),
                geometry_type_before=g.geom_type,
                geometry_type_after=fixed.geom_type,
                area_before_diagnostic_m2=before,
                area_after_m2=after,
                absolute_area_delta_m2=abs(delta),
                percent_area_delta=(100 * delta / before) if before > 0 else None,
                component_count_before=int(shapely.get_num_geometries(g)),
                component_count_after=int(shapely.get_num_geometries(poly))
                if not poly.is_empty
                else 0,
                polygonal_area_dropped_m2=float(
                    sum(
                        shapely.area(p)
                        for p in shapely.get_parts(fixed)
                        if p.geom_type not in ("Polygon", "MultiPolygon")
                    )
                ),
                empty_after_repair=poly.is_empty,
            ).model_dump()
        )
    cols = list(RepairAuditRecord.model_fields)
    return pd.DataFrame(records, columns=cols) if records else pd.DataFrame(columns=cols)


def summarise_repairs(audit: pd.DataFrame, total_features: int) -> dict:
    if audit.empty:
        return {"repair_count": 0, "repair_rate": 0.0}
    pct = audit["percent_area_delta"].dropna().abs()
    return {
        "repair_count": len(audit),
        "total_features": total_features,
        "repair_rate": len(audit) / total_features,
        "median_abs_area_delta_m2": float(audit["absolute_area_delta_m2"].median()),
        "p95_abs_area_delta_m2": float(np.percentile(audit["absolute_area_delta_m2"], 95)),
        "max_abs_area_delta_m2": float(audit["absolute_area_delta_m2"].max()),
        "median_abs_percent_delta": float(pct.median()) if len(pct) else None,
        "p95_abs_percent_delta": float(np.percentile(pct, 95)) if len(pct) else None,
        "max_abs_percent_delta": float(pct.max()) if len(pct) else None,
        "total_abs_area_delta_km2": float(audit["absolute_area_delta_m2"].sum() / 1e6),
        "geometry_type_changes": (
            audit["geometry_type_before"] + " -> " + audit["geometry_type_after"]
        )
        .value_counts()
        .to_dict(),
        "validity_reasons": audit["validity_reason_before"]
        .str.split("[")
        .str[0]
        .value_counts()
        .to_dict(),
        "component_count_changed": int(
            (audit["component_count_before"] != audit["component_count_after"]).sum()
        ),
        "empty_after_repair": int(audit["empty_after_repair"].sum()),
        "area_values_are_diagnostic": True,
    }
