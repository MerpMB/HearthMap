"""M2A: per-cell accessibility and infrastructure context on the 500 m grid.

BASELINE_DRIVE_TIME only (free-flow class speeds, no traffic/weather). Unreachable or unsnapped cells stay
UNRESOLVED (NaN + reason); straight-line distance is a labelled diagnostic and never replaces routing.
Writes outputs/m2a/family-infrastructure-evidence.parquet (+ provenance) and review CSVs.
"""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, source_ref

from hearthmap.enums import Confidence
from hearthmap.family import (
    electricity_context,
    load_config,
    multi_source_dijkstra,
    telecom_context,
    water_context,
)
from hearthmap.family.routing import ListGraph, Network, bounded_reach, reverse
from hearthmap.provenance import ProvenanceRecord, current_code_version

DATA = Path("data/processed/m2a")
OUT = Path("outputs/m2a")
REVIEW = Path("outputs/m2a-review")
# M2A.1: `--refreshed` reads data/processed/m2a1 facilities and writes outputs/m2a1/ (routing inputs unchanged)
REFRESHED = "--refreshed" in sys.argv
FAC = Path("data/processed/m2a1") if REFRESHED else DATA
ART_DIR = Path("outputs/m2a1") if REFRESHED else OUT
SNAP_CSV = Path("outputs/m2a1-review") if REFRESHED else REVIEW
EDU_CATS = {"early_childhood_centre": "EARLY_CHILDHOOD", "kindergarten": "KINDERGARTEN", "primary_school": "PRIMARY", "secondary_school": ("LOWER_SECONDARY", "UPPER_SECONDARY"), "vocational_institution": "VOCATIONAL", "university": "UNIVERSITY_TERTIARY"}  # fmt: skip
HOSPITAL_CLASSES = {
    "COMMUNITY_HOSPITAL",
    "GENERAL_HOSPITAL",
    "REGIONAL_OR_TERTIARY_HOSPITAL",
    "UNIVERSITY_HOSPITAL",
    "HOSPITAL_UNSPECIFIED_LEVEL",
}
SENSITIVITY_CATS = ("primary_school", "secondary_school", "hospital")
COUNT_60 = {
    "secondary_school",
    "vocational_institution",
    "university",
    "hospital",
    "higher_level_hospital",
}


def load_network() -> Network:
    z = np.load(DATA / "network.npz")
    return Network(
        z["xy"],
        z["indptr"],
        z["indices"],
        z["length_m"],
        z["hw_code"],
        list(z["classes"]),
        z["component"],
        z["component_size"],
    )


def snap(
    points_xy: np.ndarray, node_xy: np.ndarray, node_ids: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    tree = shapely.STRtree(shapely.points(node_xy[node_ids]))
    idx = tree.query_nearest(shapely.points(points_xy), return_distance=True, all_matches=False)
    order = np.argsort(idx[0][0])
    return node_ids[idx[0][1][order]], idx[1][order]


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    tt = cfg["travel_time"]
    net = load_network()
    rev = reverse(net)
    routable = np.where(net.component_size[net.component] >= 500)[0]
    grid = (
        gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    cen = shapely.get_coordinates(grid.geometry.centroid)
    cell_node, cell_snap = snap(cen, net.xy, routable)
    # nodes of ANY component, to tell 'no road' from 'road only in an isolated fragment'
    _, cell_any_snap = snap(cen, net.xy, np.arange(len(net.xy)))
    edu = gpd.read_file(FAC / "facilities.gpkg", layer="education_facilities")
    hl = gpd.read_file(FAC / "facilities.gpkg", layer="health_facilities")
    edu_ok = edu[edu["coordinate_qa_status"] != "FAILED"].copy()
    hl_ok = hl[hl["coordinate_qa_status"] != "FAILED"].copy()
    cats: dict[str, gpd.GeoDataFrame] = {}
    for c, lv in EDU_CATS.items():
        lv = (lv,) if isinstance(lv, str) else lv
        cats[c] = edu_ok[edu_ok["levels"].map(lambda s, lv=lv: any(x in s.split("|") for x in lv))]
    cats["primary_health_unit"] = hl_ok[hl_ok["facility_class"] == "PRIMARY_HEALTH_UNIT"]
    cats["hospital"] = hl_ok[hl_ok["facility_class"].isin(HOSPITAL_CLASSES)]
    cats["higher_level_hospital"] = hl_ok[
        hl_ok["facility_class"] == "REGIONAL_OR_TERTIARY_HOSPITAL"
    ]  # empty unless an authoritative reference list is supplied
    # snap facilities
    fac_rows, fac_node = [], {}
    for c, g in cats.items():
        if len(g) == 0:
            continue
        nodes, d = snap(shapely.get_coordinates(g.geometry), net.xy, routable)
        ok = d <= tt["max_snap_distance_m"]
        for fid, n, dd, o in zip(g["facility_id"], nodes, d, ok, strict=True):
            fac_rows.append(
                {"category": c, "facility_id": fid, "snap_distance_m": float(dd), "routed": bool(o)}
            )
            if o:
                fac_node.setdefault(c, {})[fid] = int(n)
    pd.DataFrame(fac_rows).to_csv(SNAP_CSV / "facility-routing-snap.csv", index=False)
    print(f"snapped in {time.time() - t0:.0f}s", {c: len(v) for c, v in fac_node.items()})

    out = pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "majority_pcode": grid["majority_pcode"],
            "coverage_fraction": grid["coverage_fraction"],
        }
    )
    out["road_snap_distance_m"] = cell_snap.round(1)
    out["road_any_fragment_distance_m"] = cell_any_snap.round(1)
    cell_ok = cell_snap <= tt["max_snap_distance_m"]
    out["road_access_context"] = np.select(
        [cell_snap <= 500, cell_snap <= tt["max_snap_distance_m"], cell_any_snap <= tt["max_snap_distance_m"]],
        ["CONNECTED_ROAD_WITHIN_500M", "CONNECTED_ROAD_500M_TO_1KM", "ONLY_ISOLATED_ROAD_FRAGMENT_WITHIN_1KM"], "NO_ROAD_WITHIN_1KM",
    )  # fmt: skip
    # nearest major road (OSM primary/trunk/secondary from the M1A layer)
    major = gpd.read_file(PROCESSED / "layers.gpkg", layer="major_roads")
    mtree = shapely.STRtree(major.geometry.to_numpy())
    ci, cd = mtree.query_nearest(shapely.points(cen), return_distance=True, all_matches=False)
    order = np.argsort(ci[0])
    out["nearest_major_road_distance_m"] = cd[order].round(0)
    out["nearest_major_road_class"] = major["highway"].to_numpy()[ci[1][order]]
    # DRR rural-highway centrelines: separate provenance, context only
    drr = gpd.read_file(Path("data/raw/roads-drr-gis/download-2026-10-16/page_00000.json"))
    drr_dist = shapely.STRtree(drr.to_crs(CANONICAL).geometry.to_numpy()).query_nearest(
        shapely.points(cen), return_distance=True, all_matches=False
    )
    o2 = np.argsort(drr_dist[0][0])
    out["drr_rural_highway_within_1km"] = drr_dist[1][o2] <= 1000

    speeds = cfg.speeds
    cell_xy = cen
    for c in list(cats):
        fn = fac_node.get(c, {})
        n_all = len(cats[c])
        reason = np.full(len(out), "", dtype=object)
        t_min = np.full(len(out), np.nan)
        dist_km = np.full(len(out), np.nan)
        nearest = np.full(len(out), "", dtype=object)
        if n_all == 0:
            reason[:] = (
                "CATEGORY_DEFERRED_NO_VERIFIED_CLASSIFICATION"
                if c == "higher_level_hospital"
                else "NO_FACILITIES_IN_CATEGORY"
            )
        elif not fn:
            reason[:] = "NO_ROUTABLE_FACILITY"
        else:
            fids = sorted(fn)
            src = np.array([fn[f] for f in fids])
            t, d, lab = multi_source_dijkstra(
                rev,
                rev.edge_time_s(speeds, 1.0),
                src,
                np.arange(len(fids)),
                tt["max_search_min"] * 60.0,
            )
            tc, dc, lc = t[cell_node], d[cell_node], lab[cell_node]
            reached = cell_ok & np.isfinite(tc) & (lc >= 0)
            t_min[reached] = tc[reached] / 60.0
            dist_km[reached] = dc[reached] / 1000.0
            nearest[reached] = np.array(fids, dtype=object)[lc[reached]]
            reason[~cell_ok] = "NO_ROAD_WITHIN_SNAP_DISTANCE"
            reason[cell_ok & ~reached] = "UNREACHABLE_WITHIN_SEARCH_LIMIT_OR_NETWORK"
            if c in SENSITIVITY_CATS:
                for name, mult in tt["sensitivity"].items():
                    if name == "BASE":
                        continue
                    ts, _, _ = multi_source_dijkstra(
                        rev,
                        rev.edge_time_s(speeds, mult),
                        src,
                        np.arange(len(fids)),
                        tt["max_search_min"] * 60.0,
                    )
                    v = np.where(cell_ok, ts[cell_node] / 60.0, np.nan)
                    out[f"drive_time_to_nearest_{c}_{name.lower()}_min"] = np.where(
                        np.isfinite(v), v, np.nan
                    ).round(2)
            # counts within bands (bounded search per facility)
            if c != "higher_level_hospital":
                lg = ListGraph(rev, rev.edge_time_s(speeds, 1.0))
                bands = [b for b in cfg.bands if b <= (60 if c in COUNT_60 else 30)]
                cnt = {b: np.zeros(len(net.xy), dtype=np.int32) for b in bands}
                t1 = time.time()
                for f in fids:
                    nodes, tm = bounded_reach(lg, fn[f], max(bands) * 60.0)
                    for b in bands:
                        cnt[b][nodes[tm <= b * 60.0]] += 1
                for b in bands:
                    out[f"{c}_count_within_{b}min"] = np.where(
                        cell_ok, cnt[b][cell_node], -1
                    )  # -1 = unresolved (no road access)
                print(f"{c}: {len(fids)} facilities counted in {time.time() - t1:.0f}s")
        out[f"drive_time_to_nearest_{c}_min"] = np.round(t_min, 2)
        out[f"network_distance_to_nearest_{c}_km"] = np.round(dist_km, 2)
        out[f"nearest_{c}_id"] = nearest
        out[f"route_available_{c}"] = np.isfinite(t_min)
        out[f"{c}_unresolved_reason"] = np.where(np.isfinite(t_min), "", reason)
        # Euclidean DIAGNOSTIC (never a substitute for routing)
        if n_all:
            ft = shapely.STRtree(shapely.points(shapely.get_coordinates(cats[c].geometry)))
            ed = ft.query_nearest(shapely.points(cell_xy), return_distance=True, all_matches=False)
            oo = np.argsort(ed[0][0])
            out[f"euclidean_distance_to_nearest_{c}_km_diagnostic"] = (ed[1][oo] / 1000.0).round(2)
        else:
            out[f"euclidean_distance_to_nearest_{c}_km_diagnostic"] = np.nan
        print(f"{c}: n={n_all} routed={len(fn)} elapsed {time.time() - t0:.0f}s")

    # pathways: number of distinct education pathways reachable within each band (from nearest times)
    path_cols = [
        "early_childhood_centre",
        "kindergarten",
        "primary_school",
        "secondary_school",
        "vocational_institution",
        "university",
    ]
    for b in cfg.bands:
        out[f"education_pathways_within_{b}min"] = sum(
            (out[f"drive_time_to_nearest_{c}_min"] <= b).astype(int) for c in path_cols
        )
    out["education_pathways_resolved"] = out[[f"route_available_{c}" for c in path_cols]].sum(
        axis=1
    )
    out["education_evidence_completeness"] = np.select(
        [~cell_ok, out["education_pathways_resolved"] == len(path_cols)], ["UNRESOLVED_NO_ROAD_ACCESS", "ALL_PATHWAYS_ROUTED"], "PARTIAL_SOME_PATHWAYS_UNREACHABLE"
    )  # fmt: skip
    out["healthcare_evidence_completeness"] = np.select(
        [~cell_ok, out["route_available_hospital"] & out["route_available_primary_health_unit"]], ["UNRESOLVED_NO_ROAD_ACCESS", "HOSPITAL_AND_PRIMARY_UNIT_ROUTED_HIGHER_LEVEL_DEFERRED"], "PARTIAL"
    )  # fmt: skip
    # infrastructure context (no combined score)
    el, wt, tc = electricity_context(False), water_context(None), telecom_context(False)
    for k, v in {**el, **wt, **tc}.items():
        out[k] = v
    out["routing_basis"] = "BASELINE_DRIVE_TIME"
    out["routing_config_fingerprint"] = hashlib.sha256(
        json.dumps(cfg["travel_time"], sort_keys=True).encode()
    ).hexdigest()[:16]
    out["education_primary_source_vintage"] = (
        "DOPA_2021_STALE_FALLBACK" if REFRESHED else "DOPA_2021_STALE"
    )
    out["healthcare_primary_source_vintage"] = (
        "CITIZENINFO_2020_STALE_FALLBACK" if REFRESHED else "CITIZENINFO_2020_STALE"
    )
    out["hospital_level_status"] = (
        "PARTIALLY_ASSESSED_NO_ACCESSIBLE_AUTHORITATIVE_LEVEL_FIELD"
        if REFRESHED
        else "NOT_ASSESSED"
    )
    out["education_levels_basis"] = "DERIVED_FROM_NAME_AND_SOURCE_SUBCODE_CONFIDENCE_QUALIFIED"
    out["facility_data_freshness"] = "STALE_EDUCATION_2021_HEALTH_2020"
    ART_DIR.mkdir(parents=True, exist_ok=True)
    pq = ART_DIR / "family-infrastructure-evidence.parquet"
    out.to_parquet(pq, index=False)
    rec = ProvenanceRecord(
        artifact_id="m2a1-family-infrastructure-evidence" if REFRESHED else "m2a-family-infrastructure-evidence", artifact_path=pq.as_posix(), code_version=current_code_version(),
        sources=[source_ref("places-dopa-gis02", original_crs="EPSG:4326"), source_ref("health-citizeninfo-dga", original_crs="EPSG:4326"), source_ref("osm-overpass-aoi", original_crs="EPSG:4326"), source_ref("roads-drr-gis", original_crs="EPSG:32647")] + ([source_ref("education-obec-school-list", original_crs="EPSG:4326"), source_ref("osm-facilities-aoi", original_crs="EPSG:4326")] if REFRESHED else []),
        normalized_crs=CANONICAL,
        method="config/family-infrastructure.yaml: BASELINE_DRIVE_TIME multi-source Dijkstra on a directed OSM network; facility classes derived only from source fields; PEA/PWA/NBTC contribute evidence STATES, not data.",
        spatial_resolution="500 m cells (cell-centre routing)", confidence=Confidence.LOW,
        limitations=[
            "Accessibility, not suitability: no family score, no school quality, no capacity or reliability.",
            "Facility sources are STALE (education 2021, health 2020) and government-only; levels/classes are derived.",
            "BASELINE_DRIVE_TIME excludes traffic, weather, rainy-season closures and road surface; OSM completeness varies.",
            "Electricity, water and telecom are context states only; parcel verification always required.",
        ],
    )  # fmt: skip
    Path(str(pq) + ".provenance.json").write_text(rec.to_json() + "\n", encoding="utf-8")
    print(f"done {len(out):,} cells, {out.shape[1]} columns in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
