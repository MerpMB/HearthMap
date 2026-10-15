# ruff: noqa: E501
"""M2A.1: how much did the refreshed facility layers change accessibility? (routing frozen; descriptive only)

Shorter or longer travel time is NOT a statement about school or hospital quality.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

REVIEW = Path("outputs/m2a1-review")
CATS = [
    "early_childhood_centre",
    "kindergarten",
    "primary_school",
    "secondary_school",
    "vocational_institution",
    "university",
    "primary_health_unit",
    "hospital",
]
CENTRES = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}


def wq(v: np.ndarray, w: np.ndarray, q: float) -> float | None:
    m = np.isfinite(v)
    if not m.any():
        return None
    v, w = v[m], w[m]
    o = np.argsort(v)
    cw = np.cumsum(w[o]) / w.sum()
    return float(v[o][min(np.searchsorted(cw, q), len(v) - 1)])


def main() -> int:
    old = pd.read_parquet("outputs/m2a/family-infrastructure-evidence.parquet")
    new = pd.read_parquet("outputs/m2a1/family-infrastructure-evidence.parquet")
    assert (old["cell_id"].to_numpy() == new["cell_id"].to_numpy()).all()
    assert old["routing_basis"].eq(new["routing_basis"]).all()
    area = (0.25 * old["coverage_fraction"]).to_numpy()
    haz = pd.read_parquet(
        "outputs/m1b/hazard-evidence.parquet", columns=["cell_id", "slope_median_deg"]
    )
    slope = old[["cell_id"]].merge(haz, on="cell_id", how="left")["slope_median_deg"].to_numpy()
    lowland = (old["road_access_context"] == "CONNECTED_ROAD_WITHIN_500M").to_numpy() & (
        slope <= 5
    )  # reporting stratum only
    strata = {
        "AOI": np.ones(len(old), bool),
        "TH50": old["majority_pcode"].eq("TH50").to_numpy(),
        "TH56": old["majority_pcode"].eq("TH56").to_numpy(),
        "TH57": old["majority_pcode"].eq("TH57").to_numpy(),
        "ROAD_WITHIN_500M_AND_LOW_SLOPE_LE_5": lowland,
    }
    rows, largest = [], []
    cen = shapely.get_coordinates(
        gpd.read_file("data/processed/m1a/grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
        .geometry.centroid
    )
    for c in CATS:
        to, tn = (
            old[f"drive_time_to_nearest_{c}_min"].to_numpy(float),
            new[f"drive_time_to_nearest_{c}_min"].to_numpy(float),
        )
        io, inn = old[f"nearest_{c}_id"].to_numpy(), new[f"nearest_{c}_id"].to_numpy()
        both = np.isfinite(to) & np.isfinite(tn)
        delta = tn - to
        for name, mask in strata.items():
            m = both & mask
            a = area[m]
            same = io[m] == inn[m]
            rows.append({
                "category": c, "stratum": name, "area_km2": round(float(area[mask].sum()), 1),
                "resolved_both_km2": round(float(a.sum()), 1), "newly_resolved_km2": round(float(area[mask & ~np.isfinite(to) & np.isfinite(tn)].sum()), 1), "newly_unresolved_km2": round(float(area[mask & np.isfinite(to) & ~np.isfinite(tn)].sum()), 1),
                "nearest_unchanged_pct": round(float(a[same].sum() / a.sum() * 100), 2) if a.sum() else None, "nearest_changed_pct": round(float(a[~same].sum() / a.sum() * 100), 2) if a.sum() else None,
                "median_old_min": wq(to[m], a, 0.5), "median_new_min": wq(tn[m], a, 0.5), "median_change_min": wq(delta[m], a, 0.5), "p95_change_min": wq(delta[m], a, 0.95), "p05_change_min": wq(delta[m], a, 0.05),
                "mean_change_min": round(float(np.average(delta[m], weights=a)), 3) if a.sum() else None,
                "count30_old_median": float(np.median(old.loc[m, f"{c}_count_within_30min"])) if f"{c}_count_within_30min" in old and m.any() else None,
                "count30_new_median": float(np.median(new.loc[m, f"{c}_count_within_30min"])) if f"{c}_count_within_30min" in new and m.any() else None,
            })  # fmt: skip
        order = np.argsort(-np.abs(np.where(both, delta, 0)))[:10]
        for i in order:
            if both[i] and abs(delta[i]) > 0:
                largest.append(
                    {
                        "category": c,
                        "cell_id": old["cell_id"].iloc[i],
                        "province": old["majority_pcode"].iloc[i],
                        "x_utm47n": round(float(cen[i, 0]), 0),
                        "y_utm47n": round(float(cen[i, 1]), 0),
                        "old_min": round(float(to[i]), 2),
                        "new_min": round(float(tn[i]), 2),
                        "change_min": round(float(delta[i]), 2),
                        "old_nearest": io[i],
                        "new_nearest": inn[i],
                    }
                )
    out = pd.DataFrame(rows)
    out.to_csv(REVIEW / "accessibility-change-summary.csv", index=False)
    pd.DataFrame(largest).to_csv(REVIEW / "accessibility-largest-changes.csv", index=False)
    # frozen-routing evidence
    cfg_fp = hashlib.sha256(
        json.dumps(
            __import__("yaml").safe_load(
                Path("config/family-infrastructure.yaml").read_text("utf-8")
            )["travel_time"],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    net_hash = hashlib.sha256(Path("data/processed/m2a/network.npz").read_bytes()).hexdigest()[:16]
    (REVIEW / "routing-freeze-evidence.json").write_text(
        json.dumps(
            {
                "routing_config_fingerprint": cfg_fp,
                "artifact_fingerprint_unique": sorted(
                    new["routing_config_fingerprint"].unique().tolist()
                ),
                "network_npz_sha256_16": net_hash,
                "routing_basis": "BASELINE_DRIVE_TIME",
            },
            indent=1,
        )
        + "\n",
        "utf-8",
    )
    print(
        out[out.stratum.isin(["AOI", "ROAD_WITHIN_500M_AND_LOW_SLOPE_LE_5"])][
            [
                "category",
                "stratum",
                "resolved_both_km2",
                "nearest_changed_pct",
                "median_old_min",
                "median_new_min",
                "median_change_min",
                "p95_change_min",
                "newly_resolved_km2",
                "newly_unresolved_km2",
            ]
        ].to_string()
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
