"""Recorded CRS normalisation (datum-transformation contract, ADR-0006).

PROJ (via pyproj) chooses and applies coordinate operations; HearthMap never
implements datum shifts itself. What this module adds is *accountability*:

* every candidate operation PROJ offers for the AOI is listed,
* "ballpark" operations (which silently skip the datum shift - hundreds of
  metres of error for Indian 1975 -> WGS 84) are refused unless explicitly
  allowed,
* a specific operation can be pinned by authority code (e.g. ``EPSG:1812``),
* the chosen operation, its authority codes and stated accuracy are returned as
  a :class:`~hearthmap.provenance.TransformationRecord` for provenance.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pyproj
import shapely
from pyproj import CRS, Transformer
from pyproj.transformer import AreaOfInterest, TransformerGroup

from hearthmap.provenance.model import TransformationRecord, TransformationStep
from hearthmap.spatial.crs import as_crs, crs_label, require_crs


class TransformationSelectionError(ValueError):
    """No acceptable coordinate operation exists, or a pinned one is unavailable."""


def _datum_name(crs: CRS) -> str:
    geod = crs.geodetic_crs
    datum = geod.datum if geod is not None else None
    return datum.name if datum is not None else "unknown"


def _code(op) -> str | None:
    ident = op.to_json_dict().get("id")
    if not ident:
        return None
    return f"{ident['authority']}:{ident['code']}"


def _steps(transformer: Transformer) -> list[TransformationStep]:
    ops = list(transformer.operations) or []
    steps = []
    for op in ops:
        accuracy = op.accuracy if op.accuracy is not None and op.accuracy >= 0 else None
        steps.append(
            TransformationStep(
                name=op.name,
                kind=op.type_name,
                authority_code=_code(op),
                accuracy_m=accuracy,
                ballpark="ballpark" in op.name.lower(),
            )
        )
    return steps


def _is_ballpark(transformer: Transformer) -> bool:
    return "ballpark" in transformer.description.lower() or any(
        s.ballpark for s in _steps(transformer)
    )


def plan_transformation(
    source: CRS | str | int,
    target: CRS | str | int,
    *,
    area_of_interest: tuple[float, float, float, float] | None = None,
    pinned: str | None = None,
    allow_ballpark: bool = False,
) -> tuple[Transformer, TransformationRecord]:
    """Choose a coordinate operation and describe the choice.

    Args:
        source, target: CRSs.
        area_of_interest: (west, south, east, north) in degrees; lets PROJ rank
            operations by their area of use.
        pinned: authority code of a transformation step that must be used
            (e.g. ``"EPSG:1812"``). Raises if no candidate contains it.
        allow_ballpark: accept operations that omit the datum shift.
    """
    src, dst = as_crs(source), as_crs(target)
    aoi = AreaOfInterest(*area_of_interest) if area_of_interest else None
    group = TransformerGroup(src, dst, always_xy=True, area_of_interest=aoi)
    candidates = list(group.transformers)
    if not candidates:
        raise TransformationSelectionError(
            f"PROJ offers no instantiable operation {crs_label(src)} -> {crs_label(dst)}"
            + (
                f"; unavailable (missing grids?): {[o.name for o in group.unavailable_operations]}"
                if group.unavailable_operations
                else ""
            )
        )
    acceptable = [t for t in candidates if allow_ballpark or not _is_ballpark(t)]
    if not acceptable:
        raise TransformationSelectionError(
            f"only ballpark operations exist for {crs_label(src)} -> {crs_label(dst)}; "
            "they skip the datum shift. Pass allow_ballpark=True only if that is acceptable."
        )

    if pinned is not None:
        matches = [t for t in acceptable if any(s.authority_code == pinned for s in _steps(t))]
        if not matches:
            raise TransformationSelectionError(
                f"pinned operation {pinned} is not among the candidates: "
                f"{[t.description for t in acceptable]}"
            )
        chosen, selection = matches[0], "pinned"
    else:
        # PROJ returns candidates ranked by area-of-use relevance and accuracy.
        chosen = acceptable[0]
        selection = "only_candidate" if len(acceptable) == 1 else "best_ranked"

    steps = _steps(chosen)
    transform_steps = [s for s in steps if s.kind == "Transformation"]
    if not transform_steps:
        accuracy: float | None = 0.0  # pure conversions are exact by definition
    elif all(s.accuracy_m is not None for s in transform_steps):
        accuracy = float(sum(s.accuracy_m for s in transform_steps))  # type: ignore[misc]
    else:
        accuracy = None

    src_datum, dst_datum = _datum_name(src), _datum_name(dst)
    area = chosen.area_of_use
    record = TransformationRecord(
        source_crs=crs_label(src) or src.to_string(),
        source_datum=src_datum,
        target_crs=crs_label(dst) or dst.to_string(),
        target_datum=dst_datum,
        datum_change=src_datum != dst_datum,
        operation=chosen.description,
        steps=steps,
        transformation_codes=[s.authority_code for s in transform_steps if s.authority_code],
        accuracy_m=accuracy,
        area_of_use=f"{area.name} {area.bounds}" if area else None,
        candidates=[t.description for t in candidates],
        selection=selection,
        proj_pipeline=chosen.definition,
        pyproj_version=pyproj.__version__,
        proj_version=pyproj.proj_version_str,
    )
    return chosen, record


def reproject_recorded(
    gdf: gpd.GeoDataFrame,
    target: CRS | str | int,
    *,
    name: str = "layer",
    area_of_interest: tuple[float, float, float, float] | None = None,
    pinned: str | None = None,
    allow_ballpark: bool = False,
) -> tuple[gpd.GeoDataFrame, TransformationRecord]:
    """Reproject with an explicit, recorded coordinate operation. Returns a copy."""
    source = require_crs(gdf, name=name)
    transformer, record = plan_transformation(
        source,
        target,
        area_of_interest=area_of_interest,
        pinned=pinned,
        allow_ballpark=allow_ballpark,
    )
    out = gdf.copy()
    geoms = out.geometry.array

    def _apply(coords: np.ndarray) -> np.ndarray:
        x, y = transformer.transform(coords[:, 0], coords[:, 1])
        return np.column_stack([x, y])

    out[out.geometry.name] = gpd.GeoSeries(
        shapely.transform(np.asarray(geoms), _apply), index=out.index, crs=as_crs(target)
    )
    return out.set_crs(as_crs(target), allow_override=True), record
