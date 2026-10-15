"""Marking and guarding review-only layers.

Review layers (boundary uncertainty, repair audits, coverage diagnostics) exist
for humans. They must never silently become decision inputs, so they carry
``review_only = True`` / ``decision_use = "NONE"`` and are refused by
:func:`hearthmap.spatial.overlay.polygon_cell_metrics` and by scoring
evidence (source ids starting with ``review:``).
"""

from __future__ import annotations

import geopandas as gpd

from hearthmap.enums import REVIEW_SOURCE_PREFIX  # noqa: F401  (re-exported)

REVIEW_COLUMN = "review_only"
DECISION_USE_COLUMN = "decision_use"


class ReviewLayerError(ValueError):
    """A review-only layer or artifact was offered as a decision input."""


def mark_review_only(gdf: gpd.GeoDataFrame, *, purpose: str) -> gpd.GeoDataFrame:
    out = gdf.copy()
    out[REVIEW_COLUMN] = True
    out[DECISION_USE_COLUMN] = "NONE"
    out["review_purpose"] = purpose
    return out


def is_review_layer(gdf: gpd.GeoDataFrame) -> bool:
    return REVIEW_COLUMN in gdf.columns and bool(gdf[REVIEW_COLUMN].fillna(False).any())


def assert_not_review_layer(gdf: gpd.GeoDataFrame, *, name: str = "layer") -> None:
    if is_review_layer(gdf):
        raise ReviewLayerError(
            f"{name} is a review-only layer (decision_use=NONE) and cannot feed overlays or scores"
        )
