"""Composite sanity checks for a vector layer before it enters analysis."""

from __future__ import annotations

from dataclasses import dataclass, field

import geopandas as gpd

from hearthmap.spatial.bbox import BBox
from hearthmap.spatial.crs import crs_label
from hearthmap.spatial.geometry import GeometryReport, check_geometries


@dataclass(frozen=True)
class LayerValidationReport:
    name: str
    crs: str | None
    feature_count: int
    geometry: GeometryReport | None
    within_envelope: bool | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        state = "OK" if self.ok else "FAILED"
        lines = [f"{self.name}: {state} ({self.feature_count} features, CRS {self.crs})"]
        lines += [f"  error: {e}" for e in self.errors]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


def validate_layer(
    gdf: gpd.GeoDataFrame, *, name: str = "layer", envelope: BBox | None = None
) -> LayerValidationReport:
    """Check CRS presence, geometry validity and (optionally) envelope containment.

    Never modifies the layer.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if gdf.crs is None:
        errors.append("no CRS metadata; refusing to assume one")
    if gdf.empty:
        errors.append("layer has no features")

    geom_report = None if gdf.empty else check_geometries(gdf)
    if geom_report is not None and not geom_report.ok:
        errors.append(f"geometry problems: {geom_report.summary()}")

    inside: bool | None = None
    if envelope is not None and gdf.crs is not None and not gdf.empty:
        inside = envelope.contains(BBox.from_gdf(gdf, name=name))
        if not inside:
            errors.append(
                "extent falls outside the study-area sanity envelope - check for swapped "
                "axes, a wrong CRS label or a datum/zone mix-up"
            )

    if gdf.crs is not None and gdf.crs.is_geographic:
        warnings.append("geographic CRS (degrees): reproject before any distance/area work")

    return LayerValidationReport(
        name=name,
        crs=crs_label(gdf.crs),
        feature_count=len(gdf),
        geometry=geom_report,
        within_envelope=inside,
        errors=errors,
        warnings=warnings,
    )
