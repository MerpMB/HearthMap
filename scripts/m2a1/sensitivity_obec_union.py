# ruff: noqa: E501
"""M2A.1 sensitivity: what if the 211 OBEC-only schools (2020, authoritative levels, no DOPA counterpart) were added?

NOT a replacement of the primary layer (stale and stale records are not unioned into truth): it only measures how much the
choice matters. Routing assumptions are the frozen M2A ones.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m2a"))
from build_accessibility import load_network, snap

from hearthmap.family import load_config, multi_source_dijkstra
from hearthmap.family.routing import reverse
from hearthmap.family.taxonomy import levels_from_class_range

REVIEW = Path("outputs/m2a1-review")


def main() -> int:
    cfg = load_config()
    tt = cfg["travel_time"]
    net = load_network()
    rev = reverse(net)
    et = rev.edge_time_s(cfg.speeds, 1.0)
    routable = np.where(net.component_size[net.component] >= 500)[0]
    grid = (
        gpd.read_file("data/processed/m1a/grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    cell_node, cell_snap = snap(shapely.get_coordinates(grid.geometry.centroid), net.xy, routable)
    ok = cell_snap <= tt["max_snap_distance_m"]
    edu = gpd.read_file("data/processed/m2a1/facilities.gpkg", layer="education_facilities")
    edu = edu[edu["coordinate_qa_status"] != "FAILED"]
    ob = gpd.read_file("data/processed/m2a1/facilities.gpkg", layer="education_obec_only")
    ob["levels_list"] = [levels_from_class_range(*str(n).split("-")) for n in ob["native_levels"]]
    new = pd.read_parquet("outputs/m2a1/family-infrastructure-evidence.parquet")
    area = 0.25 * new["coverage_fraction"].to_numpy()
    rows = []
    for cat, wanted in (
        ("primary_school", {"PRIMARY"}),
        ("secondary_school", {"LOWER_SECONDARY", "UPPER_SECONDARY"}),
        ("kindergarten", {"KINDERGARTEN"}),
    ):
        base = edu[edu["levels"].map(lambda s, w=wanted: bool(set(s.split("|")) & w))]
        extra = ob[ob["levels_list"].map(lambda s, w=wanted: bool(set(s) & w))]
        pts = np.concatenate(
            [shapely.get_coordinates(base.geometry), shapely.get_coordinates(extra.geometry)]
        )
        nodes, d = snap(pts, net.xy, routable)
        keep = d <= tt["max_snap_distance_m"]
        t, _, _lab = multi_source_dijkstra(
            rev, et, nodes[keep], np.arange(keep.sum()), tt["max_search_min"] * 60.0
        )
        tu = np.where(ok & np.isfinite(t[cell_node]), np.round(t[cell_node] / 60.0, 2), np.nan)
        t0 = new[f"drive_time_to_nearest_{cat}_min"].to_numpy(float)
        both = np.isfinite(t0) & np.isfinite(tu)
        dl = tu - t0
        a = area[both]
        v = dl[both]
        o = np.argsort(v)
        cw = np.cumsum(a[o]) / a.sum()
        rows.append({
            "category": cat, "primary_layer_facilities": len(base), "obec_only_added": len(extra), "resolved_both_km2": round(float(a.sum()), 1),
            "cells_with_shorter_time_pct": round(float(a[v < -0.005].sum() / a.sum() * 100), 2), "median_change_min": float(v[o][np.searchsorted(cw, 0.5)]), "p05_change_min": float(v[o][np.searchsorted(cw, 0.05)]),
            "largest_reduction_min": round(float(v.min()), 2), "newly_resolved_km2": round(float(area[~np.isfinite(t0) & np.isfinite(tu)].sum()), 1),
        })  # fmt: skip
    out = pd.DataFrame(rows)
    out.to_csv(REVIEW / "obec-only-union-sensitivity.csv", index=False)
    print(out.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
