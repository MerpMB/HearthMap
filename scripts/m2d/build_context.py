# ruff: noqa: E501
"""M2D: build the Wave-1 regional-context evidence artifact (settlement, town services, industry, mining). EVIDENCE ONLY, no scoring.

Writes outputs/m2d/regional-context-evidence.parquet (+ provenance + column lineage), supporting tables, and processed intermediates.
Reuses the frozen M2A routing foundation (BASELINE_DRIVE_TIME, config/family-infrastructure.yaml) without any tuning.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "m1a"))
sys.path.insert(0, str(ROOT / "scripts" / "m2a"))
from build_accessibility import load_network, snap  # noqa: E402
from common import CANONICAL, PROCESSED, source_ref  # noqa: E402

from hearthmap.context import SCOPE_STATEMENTS, forbidden_columns  # noqa: E402
from hearthmap.context import industry as ind  # noqa: E402
from hearthmap.context import services as svc  # noqa: E402
from hearthmap.context.semantics import (  # noqa: E402
    CANDIDATE_DEFINITION,
    COLUMN_LINEAGE_RULES,
    SOURCE_SEMANTICS,
)
from hearthmap.context.settlement import (  # noqa: E402
    CELL_KM2,
    GridIndex,
    aggregate_to_grid,
    area_fraction,
    assign_max_overlap,
)
from hearthmap.context.stats import distribution_table, stat_with_denominator  # noqa: E402
from hearthmap.enums import Confidence  # noqa: E402
from hearthmap.family import load_config, multi_source_dijkstra  # noqa: E402
from hearthmap.family.routing import ListGraph, bounded_reach, reverse  # noqa: E402
from hearthmap.provenance import ProvenanceRecord, current_code_version  # noqa: E402

RAW = Path("data/raw")
PROC = Path("data/processed/m2d")
OUT = Path("outputs/m2d")
REVIEW = Path("outputs/m2d-review")
TABLES = OUT / "tables"
PROV = {"TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
BAND_MIN = (15, 30)
CONTEXT_RADII_KM = (1, 2, 5)
TODAY = date(2026, 10, 16)
FRESH = "--fresh" in sys.argv  # ignore the routing cache (clean rebuild)


def one_version(source_id: str) -> Path:
    vs = [p for p in (RAW / source_id).iterdir() if p.is_dir()]
    assert len(vs) == 1, (source_id, vs)
    return vs[0]


def read_overpass(source_id: str, suffix: str) -> dict[str, dict]:
    d = one_version(source_id)
    return {
        pc: json.loads((d / f"{slug}_{suffix}.json").read_text("utf-8"))
        for pc, slug in {"TH50": "chiang-mai", "TH56": "phayao", "TH57": "chiang-rai"}.items()
    }


def euclid_counts(
    cen: np.ndarray, geoms: np.ndarray, n_cells: int
) -> tuple[dict[int, np.ndarray], np.ndarray]:
    """Per-cell counts of geometries within each context radius and nearest-geometry distance (km). Euclidean context, not routing."""
    if len(geoms) == 0:
        return {r: np.zeros(n_cells, dtype=np.int32) for r in CONTEXT_RADII_KM}, np.full(
            n_cells, np.nan
        )
    tree = shapely.STRtree(geoms)
    counts = {}
    for r in CONTEXT_RADII_KM:
        pairs = tree.query(cen, predicate="dwithin", distance=r * 1000.0)
        counts[r] = np.bincount(pairs[0], minlength=n_cells).astype(np.int32)
    idx = tree.query_nearest(cen, return_distance=True, all_matches=False)
    nearest = np.full(n_cells, np.nan)
    nearest[idx[0][0]] = idx[1] / 1000.0
    return counts, nearest.round(2)


def main() -> int:
    t0 = time.time()
    for p in (PROC, OUT, TABLES, REVIEW):
        p.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    tt = cfg["travel_time"]
    grid = (
        gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
        .sort_values("cell_id")
        .reset_index(drop=True)
    )
    n_cells = len(grid)
    cen_geo = grid.geometry.centroid
    cen = shapely.get_coordinates(cen_geo)
    cen_pts = shapely.points(cen)
    cell_polys = grid.geometry.to_numpy()
    area_w = grid["coverage_fraction"].to_numpy() * CELL_KM2
    gi = GridIndex(grid["cell_id"].tolist())
    out = pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "majority_pcode": grid["majority_pcode"],
            "coverage_fraction": grid["coverage_fraction"],
        }
    )
    lonlat = gpd.GeoSeries(cen_geo, crs=CANONICAL).to_crs(4326).total_bounds
    aoi_ll = (
        float(lonlat[0]) - 0.02,
        float(lonlat[1]) - 0.02,
        float(lonlat[2]) + 0.02,
        float(lonlat[3]) + 0.02,
    )

    # ---------------------------------------------------------------- settlement
    wp = next(one_version("population-worldpop-r2025a").glob("*.tif"))
    pop, used = aggregate_to_grid([str(wp)], gi, aoi_ll, n_cells, nodata=-99999)
    print(f"population: {used:,} pixels, sum {pop.sum():,.0f} ({time.time() - t0:.0f}s)")
    out["population_worldpop2025_count_500m"] = pop.round(2)
    out["population_worldpop2025_density_per_km2"] = (pop / CELL_KM2).round(1)
    for r, tag in ((1, "1p5km"), (2, "2p5km")):
        out[f"population_worldpop2025_density_per_km2_mean_{tag}"] = (
            gi.smooth_mean(pop, r) / CELL_KM2
        ).round(1)
    out["population_product_class"] = SOURCE_SEMANTICS["population"]["product_class"]
    out["population_worldpop_depends_partly_on_ghsl"] = True
    out["population_evidence_state"] = np.where(
        pop > 0, "POPULATED_PIXELS_PRESENT", "NO_POPULATED_PIXELS_IN_MODEL"
    )
    ghsl_zips = sorted(one_version("builtup-ghsl-r2023a").glob("*.zip"))
    srcs = [f"/vsizip/{z.as_posix()}/{z.stem}.tif" for z in ghsl_zips]
    built, used = aggregate_to_grid(srcs, gi, aoi_ll, n_cells, nodata=None)
    print(f"built-up: {used:,} pixels, sum {built.sum() / 1e6:,.1f} km2 ({time.time() - t0:.0f}s)")
    out["built_ghsl2020_surface_m2_500m"] = built.round(0)
    frac = np.clip(built / (CELL_KM2 * 1e6), 0, 1)
    out["built_ghsl2020_fraction_500m"] = frac.round(4)
    for r, tag in ((1, "1p5km"), (2, "2p5km")):
        out[f"built_ghsl2020_fraction_mean_{tag}"] = gi.smooth_mean(frac, r).round(4)

    net = load_network()
    rev = reverse(net)
    routable = np.where(net.component_size[net.component] >= 500)[0]
    # drivable-road length density (unordered edge pairs counted once)
    u = np.repeat(np.arange(len(net.indptr) - 1), np.diff(net.indptr))
    key = np.minimum(u, net.indices) * len(net.xy) + np.maximum(u, net.indices)
    _, first = np.unique(key, return_index=True)
    mid = (net.xy[u[first]] + net.xy[net.indices[first]]) / 2
    ei = gi.locate(mid[:, 0], mid[:, 1])
    rl = np.zeros(n_cells)
    np.add.at(rl, ei[ei >= 0], net.length_m[first][ei >= 0] / 1000.0)
    out["road_density_osm_drivable_km_per_km2"] = (rl / CELL_KM2).round(2)
    out["road_density_osm_drivable_km_per_km2_mean_1p5km"] = (
        gi.smooth_mean(rl, 1) / CELL_KM2
    ).round(2)

    # descriptive agreement between two PARTLY DEPENDENT signals (WorldPop uses GHSL as a covariate) (terciles of cells that have either signal; not a score)
    has = (pop > 0) | (built > 0)

    def tercile(v: np.ndarray) -> np.ndarray:
        q = np.quantile(v[has], [1 / 3, 2 / 3])
        return np.where(v <= q[0], "LOW", np.where(v <= q[1], "MID", "HIGH"))

    pc, bc = tercile(pop), tercile(built)
    out["settlement_signal_agreement_class"] = np.where(
        ~has,
        "NO_SIGNAL",
        np.where(pc == bc, "SIGNALS_AGREE_" + pc, "SIGNALS_DIFFER_POP_" + pc + "_BUILT_" + bc),
    )

    # ---------------------------------------------------------------- routing set-up
    cell_node, cell_snap = snap(cen, net.xy, routable)
    cell_ok = cell_snap <= tt["max_snap_distance_m"]
    out["road_snap_distance_m"] = cell_snap.round(1)
    speeds = cfg.speeds
    et = rev.edge_time_s(speeds, 1.0)
    lg = ListGraph(rev, et)

    # ---------------------------------------------------------------- town services (OSM POIs, components kept separate)
    pois = pd.concat(
        [
            svc.parse_overpass(p, pc)
            for pc, p in read_overpass("osm-service-pois-aoi", "service_pois").items()
        ],
        ignore_index=True,
    )
    tr_xy = gpd.GeoSeries(gpd.points_from_xy(pois["lon"], pois["lat"]), crs=4326).to_crs(CANONICAL)
    pois["x"], pois["y"] = tr_xy.x.to_numpy(), tr_xy.y.to_numpy()
    nl = pois[pois["nightlife_subtype"].notna()].reset_index(drop=True)
    sv = pois[pois["component"].notna()].reset_index(drop=True)
    n_raw = len(sv)
    keep = svc.dedup_same_component(sv, sv[["x", "y"]].to_numpy())
    sv = sv[keep.to_numpy()].reset_index(drop=True)
    print(
        f"service POIs {n_raw} -> {len(sv)} after same-component duplicate collapse; nightlife candidates {len(nl)}"
    )
    sxy = sv[["x", "y"]].to_numpy()
    for name, dfn in svc.CLUSTER_DEFINITIONS.items():
        sv[f"cluster_{name.lower()}"] = svc.cluster_labels(sv, sxy, dfn)
    comp_nodes: dict[str, dict[int, int]] = {}
    nodes_all, dist_all = snap(sxy, net.xy, routable)
    sv["snap_distance_m"], sv["routed"] = dist_all, dist_all <= tt["max_snap_distance_m"]
    sv["node"] = nodes_all
    for i, r in sv.iterrows():
        if r["routed"]:
            comp_nodes.setdefault(r["component"], {})[i] = int(r["node"])
    sv.drop(columns=["node"]).to_csv(REVIEW / "service-poi-routing-snap.csv", index=False)

    def route(label: str, nodes: dict[int, int] | None, count_bands: bool) -> None:
        reason = np.full(n_cells, "", dtype=object)
        t_min = np.full(n_cells, np.nan)
        if not nodes:
            reason[:] = "NO_ROUTABLE_FACILITY_IN_CATEGORY"
        else:
            ids = sorted(nodes)
            src = np.array([nodes[i] for i in ids])
            t, _, _lab = multi_source_dijkstra(
                rev, et, src, np.arange(len(ids)), tt["max_search_min"] * 60.0
            )
            tc = t[cell_node]
            reached = cell_ok & np.isfinite(tc)
            t_min[reached] = tc[reached] / 60.0
            reason[~cell_ok] = "NO_ROAD_WITHIN_SNAP_DISTANCE"
            reason[cell_ok & ~reached] = "UNREACHABLE_WITHIN_SEARCH_LIMIT_OR_NETWORK"
            if count_bands:
                cnt = {b: np.zeros(len(net.xy), dtype=np.int32) for b in BAND_MIN}
                for i in ids:
                    nd, tm = bounded_reach(lg, nodes[i], max(BAND_MIN) * 60.0)
                    for b in BAND_MIN:
                        cnt[b][nd[tm <= b * 60.0]] += 1
                for b in BAND_MIN:
                    out[f"service_{label}_count_within_{b}min"] = np.where(
                        cell_ok, cnt[b][cell_node], -1
                    )
        out[f"drive_time_to_nearest_service_{label}_min"] = np.round(t_min, 2)
        out[f"route_available_service_{label}"] = np.isfinite(t_min)
        out[f"service_{label}_unresolved_reason"] = np.where(np.isfinite(t_min), "", reason)
        print(f"  {label}: facilities={len(nodes or {})} elapsed {time.time() - t0:.0f}s")

    cache_key = hashlib.sha256(
        json.dumps(
            {
                "pois": sorted(sv["osm_id"].tolist()),
                "cfg": cfg["travel_time"],
                "net": Path("data/processed/m2a/network.npz").stat().st_size,
                "clusters": svc.CLUSTER_DEFINITIONS,
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()
    cache_pq, cache_meta = PROC / "routing_cache.parquet", PROC / "routing_cache.key"
    cached = (
        not FRESH
        and cache_pq.exists()
        and cache_meta.exists()
        and cache_meta.read_text() == cache_key
    )
    before_cols = list(out.columns)
    if cached:
        rc = pd.read_parquet(cache_pq)
        for c in rc.columns:
            out[c] = rc[c].to_numpy()
        print("routing columns loaded from cache")
    else:
        for comp in svc.COMPONENTS:
            route(comp.lower(), comp_nodes.get(comp), True)
        for name in svc.CLUSTER_DEFINITIONS:
            col = f"cluster_{name.lower()}"
            members = {
                i: n for c in comp_nodes.values() for i, n in c.items() if sv.loc[i, col] >= 0
            }
            route(f"cluster_{name.lower()}", members, False)
        out[[c for c in out.columns if c not in before_cols]].to_parquet(cache_pq, index=False)
        cache_meta.write_text(cache_key)
    for name in svc.CLUSTER_DEFINITIONS:
        col = f"cluster_{name.lower()}"
        out[f"service_cluster_{name.lower()}_poi_members"] = int((sv[col] >= 0).sum())
        out[f"service_cluster_{name.lower()}_definition_status"] = CANDIDATE_DEFINITION
        out[f"service_cluster_{name.lower()}_definition"] = json.dumps(
            svc.CLUSTER_DEFINITIONS[name], sort_keys=True
        )
    for b in BAND_MIN:
        out[f"service_components_reached_within_{b}min"] = sum(
            (out[f"drive_time_to_nearest_service_{c.lower()}_min"] <= b).astype(int)
            for c in svc.COMPONENTS
        )
    out["service_components_with_a_route"] = out[
        [f"route_available_service_{c.lower()}" for c in svc.COMPONENTS]
    ].sum(axis=1)
    nlc, nln = euclid_counts(cen_pts, shapely.points(nl[["x", "y"]].to_numpy()), n_cells)
    for r, v in nlc.items():
        out[f"nightlife_candidate_count_within_{r}km_euclidean_context"] = v
    out["nightlife_nearest_candidate_km_euclidean_diagnostic"] = nln
    # OSM service-POI intensity (all components after duplicate collapse): DESCRIPTIVE_CONTEXT only
    pidx = gi.locate(sxy[:, 0], sxy[:, 1])
    poi_n = np.bincount(pidx[pidx >= 0], minlength=n_cells).astype(float)
    out["osm_service_poi_count_500m"] = poi_n.astype(int)
    out["osm_service_poi_density_per_km2_mean_2p5km"] = (gi.smooth_mean(poi_n, 2) / CELL_KM2).round(
        2
    )
    sv.drop(columns=["node"], errors="ignore").to_csv(PROC / "service_pois.csv", index=False)
    nl.to_csv(PROC / "nightlife_candidates.csv", index=False)

    # ---------------------------------------------------------------- industry and mining
    admin3 = gpd.read_file(
        one_version("boundaries-ocha-cod-ab") / "tha_admin_boundaries.gdb.zip", layer="tha_admin3"
    )
    admin3 = admin3[admin3["adm1_pcode"].isin(PROV)].to_crs(CANONICAL).reset_index(drop=True)
    admin3["tambon_key"] = [
        ind._tambon_key(a, b, c)
        for a, b, c in zip(
            admin3["adm1_name1"], admin3["adm2_name1"], admin3["adm3_name1"], strict=True
        )
    ]
    # tambon of a cell: the tambon of the cell's OWN (majority) province that overlaps it most. A centroid join mislabels edge cells
    # (the grid keeps cells that only partly cover the AOI, and their centroid can lie in a neighbouring province or outside Thailand).
    tb_ids, tb_share, tb_method = assign_max_overlap(
        cell_polys,
        grid["majority_pcode"].to_numpy(),
        admin3.geometry.to_numpy(),
        admin3["adm1_pcode"].to_numpy(),
        admin3["adm3_pcode"].to_numpy(),
        centroid_first=True,
    )
    out["diw_tambon_pcode"] = tb_ids
    out["diw_tambon_assignment_method"] = tb_method
    out["diw_tambon_overlap_share_of_cell"] = tb_share.round(4)
    out["dpim_tambon_pcode"] = out["diw_tambon_pcode"]

    d = one_version("industry-diw-factories")
    diw = ind.load_diw(
        {p.stem: pd.read_csv(p, encoding="utf-8-sig", low_memory=False) for p in d.glob("*.csv")}
    )
    key_to_pc = dict(zip(admin3["tambon_key"], admin3["adm3_pcode"], strict=True))
    diw["adm3_pcode"] = diw["tambon_key"].map(key_to_pc)
    # fallback: (province, tambon) when the district spelling differs and the pair is unique in the boundary set
    short = admin3.assign(
        pt=admin3["tambon_key"].str.split("|").str[0]
        + "|"
        + admin3["tambon_key"].str.split("|").str[2]
    )
    uniq = short.groupby("pt")["adm3_pcode"].agg(["nunique", "first"])
    uniq = uniq[uniq["nunique"] == 1]["first"]
    miss = diw["adm3_pcode"].isna()
    diw.loc[miss, "match_method"] = "UNMATCHED"
    diw.loc[~miss, "match_method"] = "PROVINCE_DISTRICT_TAMBON_NAME"
    pt = diw["tambon_key"].str.split("|").str[0] + "|" + diw["tambon_key"].str.split("|").str[2]
    fb = miss & pt.isin(uniq.index)
    diw.loc[fb, "adm3_pcode"] = pt[fb].map(uniq)
    diw.loc[fb, "match_method"] = "PROVINCE_TAMBON_NAME_UNIQUE"
    diw.to_csv(PROC / "diw_factories_aoi.csv", index=False)
    diw_match = diw["match_method"].value_counts().to_dict()
    print("DIW tambon match", diw_match)
    g = diw.dropna(subset=["adm3_pcode"]).groupby("adm3_pcode")
    tam = pd.DataFrame(
        {
            "diw_registered_factories": g.size(),
            "diw_extraction_related": g["extraction_type"].count(),
            "diw_stone_crushing_type301": g["type_code"].apply(lambda s: int((s == 301).sum())),
            "diw_waste_or_recycling": g["is_waste_or_recycling"].sum().astype(int),
        }
    )
    # names state the ADMINISTRATIVE resolution: a cell inherits its tambon value and no distance or buffer is derived from it
    for c, col in (
        ("diw_factory_count_tambon_context", "diw_registered_factories"),
        ("diw_extraction_related_count_tambon_context", "diw_extraction_related"),
        ("diw_stone_crushing_type301_count_tambon_context", "diw_stone_crushing_type301"),
        ("diw_waste_or_recycling_count_tambon_context", "diw_waste_or_recycling"),
    ):
        out[c] = out["diw_tambon_pcode"].map(tam[col]).fillna(0).astype(int)
    out["diw_spatial_resolution"] = SOURCE_SEMANTICS["diw"]["spatial_resolution"]
    out["diw_record_status"] = SOURCE_SEMANTICS["diw"]["record_status"]
    out["diw_evidence_basis"] = "TAMBON_ADMIN_CONTEXT_NO_COORDINATES_NO_ROW_LEVEL_STATUS"

    # DPIM official licence exports: tambon resolution, register status (never operating status)
    dl = one_version("mining-dpim-licence-exports")
    stone = ind.dpim_export_frame(
        json.loads((dl / "stone_crushing_licences_aoi_provinces.json").read_text("utf-8")), "stone"
    )
    conc = ind.dpim_export_frame(
        json.loads((dl / "mining_concessions_aoi_provinces.json").read_text("utf-8")), "concession"
    )
    known = set(admin3["adm3_pcode"])
    for df_ in (stone, conc):
        df_["tambon_in_boundaries"] = df_["tambon_pcode"].isin(known)
    st_by = stone[stone["tambon_in_boundaries"]]
    cn_by = conc[conc["tambon_in_boundaries"]]
    m_ = out["dpim_tambon_pcode"]
    out["dpim_stone_crushing_licence_count_tambon_context"] = (
        m_.map(st_by.groupby("tambon_pcode").size()).fillna(0).astype(int)
    )
    out["dpim_stone_crushing_opened_register_status_count_tambon_context"] = (
        m_.map(
            st_by[st_by["status_vocab"] == "OPENED_REGISTER_STATUS"].groupby("tambon_pcode").size()
        )
        .fillna(0)
        .astype(int)
    )
    out["dpim_concession_count_tambon_context"] = (
        m_.map(cn_by.groupby("tambon_pcode").size()).fillna(0).astype(int)
    )
    out["dpim_concession_unexpired_register_status_count_tambon_context"] = (
        m_.map(
            cn_by[
                cn_by["status_vocab"].isin(["UNEXPIRED_REGISTER_STATUS", "RENEWED_REGISTER_STATUS"])
            ]
            .groupby("tambon_pcode")
            .size()
        )
        .fillna(0)
        .astype(int)
    )
    out["dpim_spatial_resolution"] = SOURCE_SEMANTICS["dpim_licences"]["spatial_resolution"]
    out["dpim_status_semantics"] = "REGISTER_STATUS_NOT_CURRENT_OPERATING_STATUS"
    stone.drop(columns=["spatial_resolution"]).assign(
        spatial_resolution="TAMBON_ADMINISTRATIVE"
    ).to_csv(TABLES / "dpim-stone-crushing-licences-aoi.csv", index=False)
    conc.to_csv(TABLES / "dpim-mining-concessions-aoi.csv", index=False)

    # legacy 2016 snapshot (LEGACY_CONTEXT) and the open-API record (province only, never mapped to cells)
    dpim = one_version("mining-dpim-concessions")
    leg = ind.dpim_legacy(
        pd.read_csv(
            dpim / "concession_2016-06-21_legacy.csv",
            encoding="cp874",
            skiprows=1,
            low_memory=False,
        )
    )
    leg["adm3_pcode"] = leg["tambon_key"].map(key_to_pc)
    leg_match = float(leg["adm3_pcode"].notna().mean())
    lc = leg.dropna(subset=["adm3_pcode"]).groupby("adm3_pcode").size()
    out["legacy_dpim_2016_concession_count_tambon_context"] = (
        out["diw_tambon_pcode"].map(lc).fillna(0).astype(int)
    )
    out["legacy_dpim_evidence_class"] = "LEGACY_CONTEXT_2016_NOT_CURRENT"
    cur = ind.dpim_current(
        json.loads((dpim / "concession_search_current.json").read_text("utf-8")), TODAY
    )
    prov_ctx = pd.concat(
        [
            cur.groupby(["province_name", "date_status"])
            .size()
            .rename("records")
            .reset_index()
            .assign(source="DPIM_OPEN_API_CONCESSIONS", resolution="PROVINCE_ADMIN_CONTEXT"),
            stone.groupby(["province_name", "status_vocab"])
            .size()
            .rename("records")
            .reset_index()
            .rename(columns={"status_vocab": "date_status"})
            .assign(
                source="DPIM_STONE_CRUSHING_LICENCE_EXPORT",
                resolution="TAMBON_ADMINISTRATIVE_AGGREGATED_TO_PROVINCE",
            ),
            conc.groupby(["province_name", "status_vocab"])
            .size()
            .rename("records")
            .reset_index()
            .rename(columns={"status_vocab": "date_status"})
            .assign(
                source="DPIM_CONCESSION_EXPORT",
                resolution="TAMBON_ADMINISTRATIVE_AGGREGATED_TO_PROVINCE",
            ),
        ],
        ignore_index=True,
    )
    prov_ctx.to_csv(TABLES / "dpim-province-admin-context.csv", index=False)

    # OSM industrial features WITH geometry: polygons and points stay distinct
    og = pd.concat(
        [
            ind.osm_industry_geometries(p, pc)
            for pc, p in read_overpass("osm-industry-geom-aoi", "industry_geom").items()
        ],
        ignore_index=True,
    )
    og["geometry"] = gpd.GeoSeries(og["geometry"].tolist(), crs=4326).to_crs(CANONICAL).to_numpy()
    og_gdf = gpd.GeoDataFrame(og, geometry="geometry", crs=CANONICAL)
    og_gdf.assign(wkt=og_gdf.geometry.to_wkt()).drop(columns="geometry").to_csv(
        PROC / "osm_industry_geometries.csv", index=False
    )

    def sel(kind: str, cls: str | None = None) -> np.ndarray:
        m = og["kind"] == kind
        if cls:
            m &= og["geometry_class"] == cls
        return og.loc[m, "geometry"].to_numpy()

    out["osm_industrial_landuse_polygon_area_fraction_500m"] = area_fraction(
        cell_polys, sel("OSM_INDUSTRIAL_LANDUSE", "POLYGON"), n_cells
    ).round(4)
    _, near = euclid_counts(cen_pts, sel("OSM_INDUSTRIAL_LANDUSE"), n_cells)
    out["osm_industrial_landuse_geometry_nearest_km_euclidean_diagnostic"] = near
    for cls in ("POINT", "POLYGON"):
        counts, _ = euclid_counts(cen_pts, sel("OSM_WORKS", cls), n_cells)
        for r, v in counts.items():
            out[f"osm_works_{cls.lower()}_count_within_{r}km_euclidean_context"] = v
    out["osm_quarry_polygon_area_fraction_500m"] = area_fraction(
        cell_polys, sel("OSM_QUARRY", "POLYGON"), n_cells
    ).round(4)
    qcounts, qnear = euclid_counts(cen_pts, sel("OSM_QUARRY"), n_cells)
    for r, v in qcounts.items():
        out[f"osm_quarry_geometry_presence_within_{r}km_euclidean_context"] = v > 0
    out["osm_quarry_geometry_nearest_km_euclidean_diagnostic"] = qnear
    out["osm_industrial_geometry_basis"] = "OSM_GEOMETRY_CONTEXT_POINTS_AND_POLYGONS_NOT_COMBINED"
    rp = og_gdf.geometry.representative_point()
    og["adm3_pcode"] = (
        gpd.sjoin(
            gpd.GeoDataFrame(geometry=rp, crs=CANONICAL),
            admin3[["adm3_pcode", "geometry"]],
            how="left",
            predicate="within",
        )["adm3_pcode"]
        .groupby(level=0)
        .first()
        .reindex(og.index)
        .to_numpy()
    )

    # ---------------------------------------------------------------- completeness (states, not scores)
    out["evidence_settlement_state"] = (
        "POPULATION_AND_BUILT_FORM_SIGNALS_PRESENT_PARTLY_DEPENDENT_SOURCES"
    )
    out["evidence_service_routing_state"] = np.select(
        [~cell_ok, out["service_components_with_a_route"] == len(svc.COMPONENTS)],
        ["UNRESOLVED_NO_ROAD_ACCESS", "ALL_COMPONENTS_ROUTED"],
        "PARTIAL_SOME_COMPONENTS_UNREACHABLE_OR_ABSENT",
    )
    out["evidence_industry_basis"] = (
        "OSM_GEOMETRY_CONTEXT_PLUS_DIW_TAMBON_ADMIN_CONTEXT_NO_ROW_LEVEL_STATUS"
    )
    out["evidence_mining_basis"] = (
        "OSM_QUARRY_GEOMETRY_PLUS_DPIM_TAMBON_LICENCE_REGISTER_CONTEXT_NO_COORDINATES"
    )
    out["scope_statement_ref"] = (
        "SCOPE_STATEMENTS in hearthmap.context.semantics; hazard outputs keep their own M1E scope"
    )
    out["routing_basis"] = "BASELINE_DRIVE_TIME"
    out["routing_config_fingerprint"] = hashlib.sha256(
        json.dumps(cfg["travel_time"], sort_keys=True).encode()
    ).hexdigest()[:16]

    bad = forbidden_columns(out.columns)
    assert not bad, bad
    unmapped = [c for c in out.columns if not any(re.search(p, c) for p, _ in COLUMN_LINEAGE_RULES)]
    assert not unmapped, unmapped
    pq = OUT / "regional-context-evidence.parquet"
    out.to_parquet(pq, index=False)
    lineage = {c: next(v for p, v in COLUMN_LINEAGE_RULES if re.search(p, c)) for c in out.columns}
    (OUT / "regional-context-evidence.sources.json").write_text(
        json.dumps(SOURCE_SEMANTICS, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )
    (OUT / "regional-context-evidence.columns.json").write_text(
        json.dumps(lineage, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )

    # ---------------------------------------------------------------- tables
    tam_t = (
        admin3[["adm3_pcode", "adm1_name", "adm2_name", "adm3_name", "adm3_name1", "area_sqkm"]]
        .merge(tam, left_on="adm3_pcode", right_index=True, how="left")
        .fillna({c: 0 for c in tam.columns})
    )
    for kind, cls, lab in (
        ("OSM_QUARRY", None, "osm_quarry_geometries"),
        ("OSM_INDUSTRIAL_LANDUSE", "POLYGON", "osm_industrial_landuse_polygons"),
        ("OSM_WORKS", "POINT", "osm_works_points"),
        ("OSM_WORKS", "POLYGON", "osm_works_polygons"),
    ):
        m = (og["kind"] == kind) & ((og["geometry_class"] == cls) if cls else True)
        tam_t[lab] = (
            tam_t["adm3_pcode"].map(og[m].groupby("adm3_pcode").size()).fillna(0).astype(int)
        )
    tam_t["legacy_dpim_2016_concessions"] = tam_t["adm3_pcode"].map(lc).fillna(0).astype(int)
    tam_t["dpim_stone_crushing_licences"] = (
        tam_t["adm3_pcode"].map(st_by.groupby("tambon_pcode").size()).fillna(0).astype(int)
    )
    tam_t["dpim_stone_crushing_opened_register_status"] = (
        tam_t["adm3_pcode"]
        .map(
            st_by[st_by["status_vocab"] == "OPENED_REGISTER_STATUS"].groupby("tambon_pcode").size()
        )
        .fillna(0)
        .astype(int)
    )
    tam_t["dpim_concessions"] = (
        tam_t["adm3_pcode"].map(cn_by.groupby("tambon_pcode").size()).fillna(0).astype(int)
    )
    tam_t["dpim_concessions_unexpired_register_status"] = (
        tam_t["adm3_pcode"]
        .map(
            cn_by[
                cn_by["status_vocab"].isin(["UNEXPIRED_REGISTER_STATUS", "RENEWED_REGISTER_STATUS"])
            ]
            .groupby("tambon_pcode")
            .size()
        )
        .fillna(0)
        .astype(int)
    )
    tam_t["spatial_resolution"] = "TAMBON_ADMINISTRATIVE"
    tam_t.drop(columns="area_sqkm").to_csv(
        TABLES / "tambon-industry-mining-context.csv", index=False
    )

    def overlap(a: pd.Series, b: pd.Series, label: str) -> dict:
        return {
            "comparison": label,
            "a_only": int(((a > 0) & (b == 0)).sum()),
            "both": int(((a > 0) & (b > 0)).sum()),
            "b_only": int(((a == 0) & (b > 0)).sum()),
            "tambons_total": len(tam_t),
            "note": "TAMBON-LEVEL presence overlap only; polygons and points are not combined",
        }

    chk = pd.DataFrame(
        [
            overlap(tam_t["diw_stone_crushing_type301"], tam_t["osm_quarry_geometries"], "tambons with DIW stone-crushing (type 301) vs tambons with an OSM quarry geometry"),
            overlap(tam_t["dpim_stone_crushing_licences"], tam_t["osm_quarry_geometries"], "tambons with a DPIM stone-crushing licence record (any status) vs tambons with an OSM quarry geometry"),
            overlap(tam_t["dpim_stone_crushing_licences"], tam_t["diw_stone_crushing_type301"], "tambons with a DPIM stone-crushing licence record vs tambons with a DIW stone-crushing record"),
            overlap(tam_t["dpim_concessions"], tam_t["osm_quarry_geometries"], "tambons with a DPIM concession record (any status) vs tambons with an OSM quarry geometry"),
            overlap(tam_t["diw_registered_factories"], tam_t["osm_industrial_landuse_polygons"], "tambons with DIW registered factories vs tambons with an OSM industrial landuse polygon"),
            overlap(tam_t["diw_registered_factories"], tam_t["osm_works_points"] + tam_t["osm_works_polygons"], "tambons with DIW registered factories vs tambons with an OSM works feature (presence only)"),
        ]
    )  # fmt: skip
    chk.to_csv(TABLES / "source-crosschecks.csv", index=False)

    # statistics with explicit denominators (routable-only medians are never AOI-wide medians)
    stats = []
    num = [
        c
        for c in out.columns
        if out[c].dtype.kind in "fi" and not c.endswith("_poi_members") and c != "coverage_fraction"
    ]
    scopes = {
        **{name: (out["majority_pcode"] == pc).to_numpy() for pc, name in PROV.items()},
        "Whole AOI": np.ones(n_cells, dtype=bool),
    }
    routed_cells = cell_ok
    for scope, m in scopes.items():
        for c in num:
            v = out[c].replace(-1, np.nan).to_numpy(dtype=float)
            is_time = c.startswith("drive_time_to_nearest_service_") or (
                "_count_within_" in c and c.startswith("service_")
            )
            resolved = (m & routed_cells) if is_time else m
            lab = "MEDIAN_AMONG_ROUTABLE_CELLS_ONLY" if is_time else "ALL_CELLS"
            stats.append(
                stat_with_denominator(
                    np.where(m, v, np.nan), resolved, np.where(m, area_w, 0.0), lab, scope, c
                )
            )
    pd.DataFrame(stats).to_csv(TABLES / "descriptive-statistics.csv", index=False)
    rows = []
    for scope, m in scopes.items():
        rows.append(
            {
                "scope": scope,
                "cells_total": int(m.sum()),
                "cells_routable": int((m & routed_cells).sum()),
                "cells_unresolved_no_road_within_1km": int((m & ~routed_cells).sum()),
                "routable_cell_share": round(float((m & routed_cells).sum() / m.sum()), 4),
                "area_total_km2": round(float(area_w[m].sum()), 1),
                "area_routable_km2": round(float(area_w[m & routed_cells].sum()), 1),
                "routable_area_share": round(
                    float(area_w[m & routed_cells].sum() / area_w[m].sum()), 4
                ),
                "unresolved_area_share": round(
                    float(area_w[m & ~routed_cells].sum() / area_w[m].sum()), 4
                ),
            }
        )
    pd.DataFrame(rows).to_csv(TABLES / "routing-denominators.csv", index=False)

    # CORE vs BROADER: both are CANDIDATE_DEFINITIONs; the difference stays visible
    tc, tb = (
        out["drive_time_to_nearest_service_cluster_core_min"],
        out["drive_time_to_nearest_service_cluster_broader_min"],
    )
    both = tc.notna() & tb.notna()
    sens = []
    for scope, m in scopes.items():
        mm = both.to_numpy() & m
        sens.append({"scope": scope, "definition_status": CANDIDATE_DEFINITION, "cells_routable_for_both": int(mm.sum()), "cells_total": int(m.sum()), "routable_cell_share": round(float(mm.sum() / m.sum()), 4),
                     "median_core_min": round(float(tc[mm].median()), 2), "median_broader_min": round(float(tb[mm].median()), 2), "median_of_paired_difference_core_minus_broader_min": round(float((tc[mm] - tb[mm]).median()), 2), "p90_paired_difference_min": round(float((tc[mm] - tb[mm]).quantile(0.9)), 2),
                     "statistic_population": "AMONG_CELLS_ROUTABLE_FOR_BOTH_DEFINITIONS_ONLY"})  # fmt: skip
    pd.DataFrame(sens).to_csv(TABLES / "service-cluster-sensitivity.csv", index=False)

    # urban-core calibration distributions: descriptive, no threshold, no combination
    uc_cols = [
        "population_worldpop2025_density_per_km2",
        "built_ghsl2020_fraction_500m",
        "road_density_osm_drivable_km_per_km2",
        "osm_service_poi_density_per_km2_mean_2p5km",
        "service_components_reached_within_15min",
    ]
    dist = distribution_table(
        out, uc_cols, {k: pd.Series(v, index=out.index) for k, v in scopes.items()}
    )
    dist["note"] = (
        "descriptive distribution for human calibration; no quantile is a policy threshold; variables are never combined"
    )
    dist.to_csv(TABLES / "urban-core-calibration-distributions.csv", index=False)
    comp = pd.crosstab(out["majority_pcode"], out["settlement_signal_agreement_class"])
    comp.to_csv(TABLES / "settlement-signal-agreement.csv")
    summary = {
        "cells": n_cells, "population_total_in_grid": round(float(pop.sum())), "built_up_km2_in_grid": round(float(built.sum() / 1e6), 1),
        "service_pois_raw": n_raw, "service_pois_after_dedup": len(sv), "nightlife_candidates": len(nl),
        "service_pois_by_component": sv["component"].value_counts().to_dict(),
        "service_cluster_poi_members": {k: int((sv[f"cluster_{k.lower()}"] >= 0).sum()) for k in svc.CLUSTER_DEFINITIONS},
        "service_routed_pois": int(sv["routed"].sum()),
        "diw_aoi_records": len(diw), "diw_tambon_match": diw_match, "diw_by_province": diw["province_pcode"].value_counts().to_dict(),
        "diw_extraction_by_type": diw["extraction_type"].value_counts().to_dict(),
        "dpim_stone_crushing_aoi_records": len(stone), "dpim_stone_crushing_by_status": stone["status_vocab"].value_counts().to_dict(), "dpim_concession_export_aoi_records": len(conc), "dpim_concession_by_status": conc["status_vocab"].value_counts().to_dict(), "dpim_tambon_code_match_share": [round(float(stone["tambon_in_boundaries"].mean()), 3), round(float(conc["tambon_in_boundaries"].mean()), 3)],
        "legacy_dpim_aoi_records": len(leg), "legacy_dpim_tambon_match_share": round(leg_match, 3),
        "dpim_open_api_aoi_records": len(cur), "osm_industry_geometries_by_kind_and_class": {f"{k}|{c}": int(n) for (k, c), n in og.groupby(["kind", "geometry_class"]).size().items()},
        "cells_without_road_access": int((~cell_ok).sum()), "unresolved_cell_share": round(float((~cell_ok).mean()), 4), "unresolved_area_share": round(float(area_w[~cell_ok].sum() / area_w.sum()), 4),
        "descriptive_rank_correlation_population_vs_built_PARTLY_DEPENDENT_sources_not_validation": round(float(pd.Series(pop[has]).rank().corr(pd.Series(built[has]).rank())), 3),
        "seconds": round(time.time() - t0),
    }  # fmt: skip
    (OUT / "build-summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )

    rec = ProvenanceRecord(
        artifact_id="m2d-regional-context-evidence", artifact_path=pq.as_posix(), artifact_kind="table", code_version=current_code_version(),
        sources=[source_ref("population-worldpop-r2025a", original_crs="EPSG:4326"), source_ref("builtup-ghsl-r2023a", original_crs="EPSG:4326"), source_ref("osm-service-pois-aoi", original_crs="EPSG:4326"), source_ref("osm-industry-geom-aoi", original_crs="EPSG:4326"), source_ref("industry-diw-factories", original_crs=None), source_ref("mining-dpim-concessions", original_crs=None), source_ref("mining-dpim-licence-exports", original_crs=None), source_ref("boundaries-ocha-cod-ab", original_crs="EPSG:4326")],
        normalized_crs=CANONICAL,
        method="Wave-1 evidence: rasters summed to 500 m cells by pixel centre; OSM POIs classified into separate components and routed on the frozen M2A BASELINE_DRIVE_TIME network; DIW and DPIM licence records are TAMBON_ADMINISTRATIVE only (no distance, buffer or local-presence claim); the DPIM open API is PROVINCE_ADMIN_CONTEXT and is never mapped to cells; WorldPop and GHSL are partly dependent; no score of any kind.",
        spatial_resolution="500 m cells (population/built-form/POI), tambon (DIW, DPIM legacy), province (DPIM current)", confidence=Confidence.LOW,
        limitations=[*list(SCOPE_STATEMENTS.values()), "DIW registers have no coordinates or row-level status (record_status UNKNOWN); DPIM licence exports have tambon resolution and register status only; LICENCE_STATUS is not current operating status; no source here locates a stone-crushing plant to a point.", SOURCE_SEMANTICS["population"]["dependency_note"], "WorldPop R2025A is a MODELLED_POPULATION_ESTIMATE (alpha), not observed population.", "OSM completeness varies and the absence of a POI is not the absence of a service.", "Euclidean context counts are descriptive radii, not exclusion buffers."],
    )  # fmt: skip
    Path(str(pq) + ".provenance.json").write_text(rec.to_json() + "\n", "utf-8")
    print(json.dumps(summary, ensure_ascii=False)[:1500])
    print(f"done {len(out):,} cells, {out.shape[1]} columns in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
