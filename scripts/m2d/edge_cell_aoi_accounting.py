# ruff: noqa: E501
"""M2D.1c: edge-cell AOI evidence accounting.

Compares the AOI-clipped analytical WorldPop/GHSL values with the full-cell context sums for the cells that extend outside the AOI, checks that interior cells
did not change, re-checks the previously identified cell, and writes outputs/m2d-review/edge-cell-aoi-accounting.csv. No score or rank field.
GRID_FOOTPRINT = the 500 m cell; AOI_ANALYTICAL_FOOTPRINT = GRID_FOOTPRINT intersect AOI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
PROV = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
CHECK_CELL = "G500-E001332-N004224"
INTERIOR = 1 - 1e-9


def main() -> int:
    df = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    pop, pop_full = (
        df["population_worldpop2025_mass_aoi_clipped"].to_numpy(),
        df["population_worldpop2025_mass_full_cell_context"].to_numpy(),
    )
    built, built_full = (
        df["built_ghsl2020_m2_aoi_clipped"].to_numpy(),
        df["built_ghsl2020_m2_full_cell_context"].to_numpy(),
    )
    cov = df["coverage_fraction"].to_numpy()
    partial = cov < INTERIOR
    adm2 = gpd.read_file(
        next(Path("data/raw/boundaries-ocha-cod-ab").glob("*/tha_admin_boundaries.gdb.zip")),
        layer="tha_admin2",
    )
    names = adm2.drop_duplicates("adm2_pcode").set_index("adm2_pcode")["adm2_name"]
    district_pcode = df["diw_tambon_pcode"].str[
        :6
    ]  # the district of the (own-province) tambon: same hierarchy as M2D.1b
    table = pd.DataFrame(
        {
            "grid_id": df["cell_id"],
            "aoi_coverage_fraction_of_cell": cov.round(4),
            "province": df["majority_pcode"].map(PROV),
            "district_pcode": district_pcode,
            "district": district_pcode.map(names).fillna(""),
            "full_cell_modelled_population": pop_full.round(2),
            "aoi_clipped_modelled_population": pop.round(2),
            "population_removed_outside_aoi": (pop_full - pop).round(2),
            "full_cell_built_up_m2": built_full.round(0),
            "aoi_clipped_built_up_m2": built.round(0),
            "built_up_removed_outside_aoi": (built_full - built).round(0),
            "note": "population is a MODELLED_POPULATION_ESTIMATE (WorldPop R2025A alpha); removed = outside the AOI footprint of the cell",
        }
    )[partial]
    changed = ((pop_full - pop) > 1e-6) | ((built_full - built) > 1e-6)
    table = table[changed[partial]].sort_values("grid_id")
    table.to_csv(REVIEW / "edge-cell-aoi-accounting.csv", index=False)

    interior = ~partial
    max_rel_pop = (
        float(
            np.max(
                np.abs(pop[interior] - pop_full[interior]) / np.maximum(pop_full[interior], 1e-9)
            )
        )
        if interior.any()
        else 0.0
    )
    interior_summary = {
        "interior_cells": int(interior.sum()),
        "interior_population_max_abs_difference": float(
            np.max(np.abs(pop[interior] - pop_full[interior]))
        ),
        "interior_built_up_max_abs_difference_m2": float(
            np.max(np.abs(built[interior] - built_full[interior]))
        ),
        "interior_population_max_relative_difference": max_rel_pop,
    }
    near_full = cov >= 0.9999
    c = df[df["cell_id"] == CHECK_CELL].iloc[0]
    cell = {
        "grid_id": CHECK_CELL,
        "aoi_coverage_fraction": round(float(c["coverage_fraction"]), 4),
        "full_cell_worldpop_modelled_population": round(
            float(c["population_worldpop2025_mass_full_cell_context"]), 2
        ),
        "aoi_clipped_worldpop_modelled_population": round(
            float(c["population_worldpop2025_mass_aoi_clipped"]), 2
        ),
        "full_cell_ghsl_built_up_m2": round(float(c["built_ghsl2020_m2_full_cell_context"]), 0),
        "aoi_clipped_ghsl_built_up_m2": round(float(c["built_ghsl2020_m2_aoi_clipped"]), 0),
    }
    summary = {
        "edge_cells_with_partial_aoi_coverage": int(partial.sum()),
        "edge_cells_whose_evidence_changed": int(changed.sum()),
        "cells_with_coverage_at_least_0.9999": int(near_full.sum()),
        "population_removed_total": round(float((pop_full - pop).sum()), 1),
        "built_up_removed_total_m2": round(float((built_full - built).sum()), 0),
        "interior": interior_summary,
        "checked_cell": cell,
    }
    (OUT / "edge-cell-aoi-accounting-summary.json").write_text(
        json.dumps(summary, indent=1) + "\n", "utf-8"
    )
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
