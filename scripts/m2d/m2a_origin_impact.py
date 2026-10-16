# ruff: noqa: E501
"""M2D.1e: impact of the canonical AOI analysis point on the M2A.2 education and healthcare accessibility.

Compares the FROZEN M2A.2 artifact (nominal GRID_CENTROID origin, outputs/m2a2/) with the corrected, separately versioned artifact
(outputs/m2a2-origin/, canonical AOI_ANALYSIS_POINT origin). Same graph, speeds, one-way handling, snap threshold, sources, taxonomy and search policy:
only the origin of edge cells whose nominal centroid lies outside the AOI footprint differs. Interior cells must be identical.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/m2d")
EDU = [
    "early_childhood_centre",
    "kindergarten",
    "primary_school",
    "secondary_school",
    "vocational_institution",
    "university",
]
HEALTH = ["primary_health_unit", "hospital", "higher_level_hospital"]
TOL = 0.005


def main() -> int:
    old = pd.read_parquet("outputs/m2a2/family-infrastructure-evidence.parquet")
    new = pd.read_parquet("outputs/m2a2-origin/family-infrastructure-evidence.parquet")
    d6 = pd.read_parquet(OUT / "regional-context-evidence.parquet")
    assert (old["cell_id"].to_numpy() == new["cell_id"].to_numpy()).all() and (
        old["cell_id"].to_numpy() == d6["cell_id"].to_numpy()
    ).all()
    moved = (new["analysis_point_method"] != "GRID_CENTROID").to_numpy()
    interior = (new["aoi_coverage_fraction_of_cell"] >= 1 - 1e-9).to_numpy()
    pop = d6["population_worldpop2025_mass_aoi_clipped"].to_numpy()

    # ---- interior identity: every column both artifacts share must match on interior cells (new columns are additions, not changes)
    shared = [c for c in old.columns if c in new.columns and c not in ("origin_semantics",)]
    diffs: dict[str, int] = {}
    for c in shared:
        a, b = old[c].to_numpy()[interior], new[c].to_numpy()[interior]
        if a.dtype.kind in "fc":
            bad = ~((np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= TOL))
        else:
            bad = a != b
        if bad.any():
            diffs[c] = int(bad.sum())
    # ---- impact per category on the cells whose origin changed
    rows = []
    for group, cats in (("education", EDU), ("healthcare", HEALTH)):
        for c in cats:
            o_ok, n_ok = (
                old[f"route_available_{c}"].to_numpy(),
                new[f"route_available_{c}"].to_numpy(),
            )
            to, tn = (
                old[f"drive_time_to_nearest_{c}_min"].to_numpy(),
                new[f"drive_time_to_nearest_{c}_min"].to_numpy(),
            )
            both = moved & o_ok & n_ok
            same = moved & ((~o_ok & ~n_ok) | (both & (np.abs(to - tn) < TOL)))
            chg = both & (np.abs(to - tn) >= TOL)
            d = (tn - to)[chg]
            nearest_changed = (
                moved
                & o_ok
                & n_ok
                & (old[f"nearest_{c}_id"].to_numpy() != new[f"nearest_{c}_id"].to_numpy())
            )
            cnt_cols = [x for x in old.columns if x.startswith(f"{c}_count_within_")]
            cnt_changed = np.zeros(len(old), dtype=bool)
            for cc in cnt_cols:
                cnt_changed |= moved & (old[cc].to_numpy() != new[cc].to_numpy())
            value_changed = moved & ~same
            rows.append(
                {
                    "group": group, "category": c, "affected_cells_origin_changed": int(moved.sum()),
                    "unchanged_resolved": int((both & ~chg).sum()), "unchanged_unresolved": int((moved & ~o_ok & ~n_ok).sum()),
                    "changed_but_still_resolved": int(chg.sum()), "became_unresolved": int((moved & o_ok & ~n_ok).sum()), "became_resolved": int((moved & ~o_ok & n_ok).sum()),
                    "delta_min_median": round(float(np.median(d)), 2) if len(d) else np.nan, "delta_min_p10": round(float(np.quantile(d, 0.1)), 2) if len(d) else np.nan,
                    "delta_min_p90": round(float(np.quantile(d, 0.9)), 2) if len(d) else np.nan, "delta_min_max_abs": round(float(np.max(np.abs(d))), 2) if len(d) else np.nan,
                    "nearest_facility_id_changed_cells": int(nearest_changed.sum()), "band_count_changed_cells": int(cnt_changed.sum()),
                    "modelled_population_in_changed_origin_cells": round(float(pop[moved].sum()), 1),
                    "modelled_population_in_cells_whose_value_changed": round(float(pop[value_changed].sum()), 1),
                    "whole_aoi_modelled_population": round(float(pop.sum())),
                    "share_of_aoi_population_in_cells_whose_value_changed": round(float(pop[value_changed].sum() / pop.sum()), 5),
                    "note": "statistics over the changed-origin edge cells only; delta = corrected minus nominal-centroid origin (minutes)",
                }
            )  # fmt: skip
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "tables" / "m2a-origin-correction-impact.csv", index=False)
    snap_d = (new["road_snap_distance_m"].to_numpy() - old["road_snap_distance_m"].to_numpy())[
        moved
        & (old["road_snap_distance_m"] <= 1000).to_numpy()
        & (new["road_snap_distance_m"] <= 1000).to_numpy()
    ]
    summary = {
        "changed_origin_cells": int(moved.sum()),
        "interior_cells": int(interior.sum()),
        "interior_columns_with_any_difference": diffs,
        "snap_origin_resolved_old": int(
            (moved & (old["road_snap_distance_m"] <= 1000).to_numpy()).sum()
        ),
        "snap_origin_resolved_new": int(
            (moved & (new["road_snap_distance_m"] <= 1000).to_numpy()).sum()
        ),
        "snap_distance_delta_m_median_among_resolved_both": round(float(np.median(snap_d)), 1)
        if len(snap_d)
        else None,
        "modelled_population_in_changed_origin_cells": round(float(pop[moved].sum()), 1),
        "columns_added_in_corrected_artifact": [c for c in new.columns if c not in old.columns],
        "values_that_differ_only_because_of_the_origin": "every value of the changed-origin cells that differs from the frozen artifact; nothing else changed",
    }
    (OUT / "m2a-origin-correction-summary.json").write_text(
        json.dumps(summary, indent=1, default=str) + "\n", "utf-8"
    )
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(t.drop(columns=["note", "whole_aoi_modelled_population"]).to_string())
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
