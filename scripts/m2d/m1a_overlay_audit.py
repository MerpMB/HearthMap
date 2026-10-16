# ruff: noqa: E501
"""M2D.1d: audit (NOT rewrite) the M1A screening-overlay fields for the edge-cell effect.

The M1A overlay fractions are measured against the FULL nominal cell. For edge cells this means (a) a feature lying wholly outside the AOI can make
a cell read as affected, and (b) the fraction is diluted by the outside part. This script quantifies both for partial cells and checks whether any
downstream decision consumes the fields. It writes outputs/m2d/tables/m1a-overlay-edge-audit.csv only; M1A outputs are not changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

PROCESSED = Path("data/processed/m1a")
OUT = Path("outputs/m2d/tables")
LAYERS = {
    "flood_obs": "flood_recurrence",
    "forest_reserve": "forest_reserve_screening",
    "national_park": "national_park_screening",
    "wildlife_sanctuary": "wildlife_sanctuary_screening",
}
CELL_KM2 = 0.25


def main() -> int:
    ov = (
        gpd.read_file(PROCESSED / "overlays.gpkg", layer="screening_overlays_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    grid = (
        gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    assert (ov["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all()
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.to_numpy())
    cov = grid["coverage_fraction"].to_numpy()
    partial = np.flatnonzero(cov < 1 - 1e-9)
    foot = shapely.intersection(grid.geometry.to_numpy()[partial], aoi)
    rows = []
    for prefix, layer in LAYERS.items():
        frac = ov[f"{prefix}_affected_area_fraction"].to_numpy()
        feats = gpd.read_file(PROCESSED / "layers.gpkg", layer=layer).to_crs(grid.crs)
        union = shapely.union_all(feats.geometry.to_numpy())
        cells_p = grid.geometry.to_numpy()[partial]
        in_foot = shapely.area(
            shapely.intersection(foot, union)
        )  # feature area inside the AOI footprint of each partial cell
        full_aff = frac[partial] * 250000.0  # feature area inside the full cell
        affected = frac[partial] > 0
        only_outside = affected & (in_foot <= 1e-6)
        footprint_area = cov[partial] * 250000.0
        frac_fp = np.where(footprint_area > 0, in_foot / np.maximum(footprint_area, 1e-9), 0.0)
        rows.append(
            {
                "field": f"{prefix}_affected_area_fraction",
                "partial_cells": len(partial),
                "partial_cells_with_feature_in_full_cell": int(affected.sum()),
                "partial_cells_affected_ONLY_by_features_outside_the_aoi": int(only_outside.sum()),
                "area_km2_of_those_cells_full_cell": round(float(only_outside.sum() * CELL_KM2), 2),
                "feature_area_km2_in_partial_cells_full_cell": round(
                    float(full_aff.sum() / 1e6), 3
                ),
                "feature_area_km2_in_partial_cells_aoi_footprint": round(
                    float(in_foot.sum() / 1e6), 3
                ),
                "partial_cells_whose_fraction_changes_by_more_than_0.05_if_measured_on_aoi_footprint": int(
                    (affected & (np.abs(frac_fp - frac[partial]) > 0.05)).sum()
                ),
                "presence_flag_flips_to_false_on_aoi_footprint": int(only_outside.sum()),
                "consumed_by_active_downstream_decision": "NO (M1A packaging and M1A.1 QA text/maps only; M1B-M1E use their own AOI-clipped metrics)",
            }
        )
        del cells_p
    pd.DataFrame(rows).to_csv(OUT / "m1a-overlay-edge-audit.csv", index=False)
    print(pd.DataFrame(rows).drop(columns="consumed_by_active_downstream_decision").to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
