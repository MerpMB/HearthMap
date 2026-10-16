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
from hearthmap.context.semantics import COLUMN_LINEAGE_RULES  # noqa: E402
from hearthmap.context.settlement import CELL_KM2, GridIndex, aggregate_to_grid  # noqa: E402
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
    cen: shapely.Geometry, pts_xy: np.ndarray, n_cells: int
) -> tuple[dict[int, np.ndarray], np.ndarray]:
    """Per-cell counts of points within each context radius and nearest-point distance (km). Euclidean context, not routing."""
    if len(pts_xy) == 0:
        return {r: np.zeros(n_cells, dtype=np.int32) for r in CONTEXT_RADII_KM}, np.full(
            n_cells, np.nan
        )
    pts = shapely.points(pts_xy)
    tree = shapely.STRtree(pts)
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

    # descriptive agreement between the two INDEPENDENT signals (terciles of cells that have either signal; not a score)
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

    for comp in svc.COMPONENTS:
        route(comp.lower(), comp_nodes.get(comp), True)
    for name in svc.CLUSTER_DEFINITIONS:
        col = f"cluster_{name.lower()}"
        members = {i: n for c in comp_nodes.values() for i, n in c.items() if sv.loc[i, col] >= 0}
        route(f"cluster_{name.lower()}", members, False)
        out[f"service_cluster_{name.lower()}_poi_members"] = int((sv[col] >= 0).sum())
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
    nlc, nln = euclid_counts(cen_pts, nl[["x", "y"]].to_numpy(), n_cells)
    for r, v in nlc.items():
        out[f"nightlife_candidate_count_within_{r}km_euclidean_context"] = v
    out["nightlife_nearest_candidate_km_euclidean_diagnostic"] = nln
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
    j = gpd.sjoin(
        gpd.GeoDataFrame(geometry=cen_geo, crs=CANONICAL),
        admin3[["adm3_pcode", "geometry"]],
        how="left",
        predicate="within",
    )
    j = j[~j.index.duplicated()]
    out["diw_tambon_pcode"] = j["adm3_pcode"].reindex(range(n_cells)).fillna("").to_numpy()

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
    for c, col in (
        ("diw_tambon_registered_factory_count", "diw_registered_factories"),
        ("diw_tambon_extraction_related_count", "diw_extraction_related"),
        ("diw_tambon_stone_crushing_type301_count", "diw_stone_crushing_type301"),
        ("diw_tambon_waste_or_recycling_count", "diw_waste_or_recycling"),
    ):
        out[c] = out["diw_tambon_pcode"].map(tam[col]).fillna(0).astype(int)
    out["diw_evidence_basis"] = "TAMBON_LEVEL_NO_COORDINATES_NO_OPERATING_STATUS"

    # legacy DPIM 2016 concessions: tambon level, LEGACY_CONTEXT
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
    out["legacy_dpim_2016_concession_record_count_in_tambon"] = (
        out["diw_tambon_pcode"].map(lc).fillna(0).astype(int)
    )
    out["legacy_dpim_evidence_class"] = "LEGACY_CONTEXT_2016_NOT_CURRENT"
    cur = ind.dpim_current(
        json.loads((dpim / "concession_search_current.json").read_text("utf-8")), TODAY
    )
    cur_summary = (
        cur.groupby(["province_name", "date_status"])
        .agg(records=("license_id", "size"), area_rai=("area_rai", "sum"))
        .reset_index()
    )
    cur_summary.to_csv(TABLES / "dpim-current-concessions-province-summary.csv", index=False)

    oi = pd.concat(
        [
            ind.osm_industry_frame(p, pc)
            for pc, p in read_overpass("osm-industry-aoi", "industry").items()
        ],
        ignore_index=True,
    )
    ox = gpd.GeoSeries(gpd.points_from_xy(oi["lon"], oi["lat"]), crs=4326).to_crs(CANONICAL)
    oi["x"], oi["y"] = ox.x.to_numpy(), ox.y.to_numpy()
    oi.to_csv(PROC / "osm_industry_features.csv", index=False)
    for label, kinds in (
        ("osm_industrial_landuse", ["OSM_INDUSTRIAL_LANDUSE"]),
        ("osm_works_or_other_industrial", ["OSM_WORKS", "OSM_INDUSTRIAL_OTHER"]),
        ("osm_quarry", ["OSM_QUARRY"]),
    ):
        sub = oi[oi["kind"].isin(kinds)]
        counts, near = euclid_counts(cen_pts, sub[["x", "y"]].to_numpy(), n_cells)
        for r, v in counts.items():
            out[f"{label}_feature_count_within_{r}km_euclidean_context"] = v
        out[f"{label}_nearest_feature_km_euclidean_diagnostic"] = near
    # tambon of each OSM feature, for the cross-checks
    of = gpd.GeoDataFrame(oi, geometry=gpd.points_from_xy(oi["x"], oi["y"]), crs=CANONICAL)
    oi["adm3_pcode"] = (
        gpd.sjoin(
            of[["geometry"]], admin3[["adm3_pcode", "geometry"]], how="left", predicate="within"
        )["adm3_pcode"]
        .groupby(level=0)
        .first()
        .reindex(oi.index)
        .to_numpy()
    )

    # ---------------------------------------------------------------- completeness (states, not scores)
    out["evidence_settlement_state"] = (
        "POPULATION_AND_BUILT_FORM_SIGNALS_PRESENT_INDEPENDENT_SOURCES"
    )
    out["evidence_service_routing_state"] = np.select(
        [~cell_ok, out["service_components_with_a_route"] == len(svc.COMPONENTS)],
        ["UNRESOLVED_NO_ROAD_ACCESS", "ALL_COMPONENTS_ROUTED"],
        "PARTIAL_SOME_COMPONENTS_UNREACHABLE_OR_ABSENT",
    )
    out["evidence_industry_basis"] = (
        "OSM_LOCATED_FEATURES_PLUS_DIW_TAMBON_COUNTS_NO_OPERATING_STATUS"
    )
    out["evidence_mining_basis"] = (
        "OSM_QUARRY_POLYGONS_PLUS_LEGACY_2016_TAMBON_CONCESSIONS_NO_CURRENT_LOCATIONS"
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
    (OUT / "regional-context-evidence.columns.json").write_text(
        json.dumps(lineage, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )

    # ---------------------------------------------------------------- tables
    tam_t = (
        admin3[["adm3_pcode", "adm1_name", "adm2_name", "adm3_name", "adm3_name1", "area_sqkm"]]
        .merge(tam, left_on="adm3_pcode", right_index=True, how="left")
        .fillna({c: 0 for c in tam.columns})
    )
    for kind, lab in (
        ("OSM_QUARRY", "osm_quarry_features"),
        ("OSM_INDUSTRIAL_LANDUSE", "osm_industrial_landuse_features"),
        ("OSM_WORKS", "osm_works_features"),
    ):
        tam_t[lab] = (
            tam_t["adm3_pcode"]
            .map(oi[oi["kind"] == kind].groupby("adm3_pcode").size())
            .fillna(0)
            .astype(int)
        )
    tam_t["legacy_dpim_2016_concessions"] = tam_t["adm3_pcode"].map(lc).fillna(0).astype(int)
    tam_t.drop(columns="area_sqkm").to_csv(
        TABLES / "tambon-industry-mining-context.csv", index=False
    )
    chk = pd.DataFrame(
        [
            {"comparison": "tambons with DIW stone-crushing (type 301) vs tambons with an OSM quarry", "a_only": int(((tam_t["diw_stone_crushing_type301"] > 0) & (tam_t["osm_quarry_features"] == 0)).sum()), "both": int(((tam_t["diw_stone_crushing_type301"] > 0) & (tam_t["osm_quarry_features"] > 0)).sum()), "b_only": int(((tam_t["diw_stone_crushing_type301"] == 0) & (tam_t["osm_quarry_features"] > 0)).sum())},
            {"comparison": "tambons with DIW extraction-related (301-304) vs tambons with an OSM quarry", "a_only": int(((tam_t["diw_extraction_related"] > 0) & (tam_t["osm_quarry_features"] == 0)).sum()), "both": int(((tam_t["diw_extraction_related"] > 0) & (tam_t["osm_quarry_features"] > 0)).sum()), "b_only": int(((tam_t["diw_extraction_related"] == 0) & (tam_t["osm_quarry_features"] > 0)).sum())},
            {"comparison": "tambons with DIW registered factories vs tambons with OSM industrial landuse/works", "a_only": int(((tam_t["diw_registered_factories"] > 0) & (tam_t["osm_industrial_landuse_features"] + tam_t["osm_works_features"] == 0)).sum()), "both": int(((tam_t["diw_registered_factories"] > 0) & (tam_t["osm_industrial_landuse_features"] + tam_t["osm_works_features"] > 0)).sum()), "b_only": int(((tam_t["diw_registered_factories"] == 0) & (tam_t["osm_industrial_landuse_features"] + tam_t["osm_works_features"] > 0)).sum())},
            {"comparison": "tambons with a 2016 DPIM concession (legacy) vs tambons with an OSM quarry", "a_only": int(((tam_t["legacy_dpim_2016_concessions"] > 0) & (tam_t["osm_quarry_features"] == 0)).sum()), "both": int(((tam_t["legacy_dpim_2016_concessions"] > 0) & (tam_t["osm_quarry_features"] > 0)).sum()), "b_only": int(((tam_t["legacy_dpim_2016_concessions"] == 0) & (tam_t["osm_quarry_features"] > 0)).sum())},
        ]
    )  # fmt: skip
    chk["tambons_total"] = len(tam_t)
    chk.to_csv(TABLES / "source-crosschecks.csv", index=False)

    stats = []
    num = [
        c
        for c in out.columns
        if out[c].dtype.kind in "fi" and not c.endswith("_poi_members") and c != "coverage_fraction"
    ]
    for pc, name in {**PROV, "AOI": "Whole AOI"}.items():
        s = out if pc == "AOI" else out[out["majority_pcode"] == pc]
        for c in num:
            v = s[c].replace(-1, np.nan).dropna()
            if v.empty:
                continue
            stats.append(
                {
                    "scope": name,
                    "column": c,
                    "n_cells": len(v),
                    "mean": round(float(v.mean()), 3),
                    "p10": round(float(v.quantile(0.1)), 3),
                    "median": round(float(v.median()), 3),
                    "p90": round(float(v.quantile(0.9)), 3),
                    "max": round(float(v.max()), 3),
                }
            )
    pd.DataFrame(stats).to_csv(TABLES / "descriptive-statistics.csv", index=False)
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
        "legacy_dpim_aoi_records": len(leg), "legacy_dpim_tambon_match_share": round(leg_match, 3),
        "dpim_current_aoi_records": len(cur), "osm_industry_features_by_kind": oi["kind"].value_counts().to_dict(),
        "cells_without_road_access": int((~cell_ok).sum()),
        "spearman_correlation_population_vs_built_cells_with_signal": round(float(pd.Series(pop[has]).rank().corr(pd.Series(built[has]).rank())), 3),
        "seconds": round(time.time() - t0),
    }  # fmt: skip
    (OUT / "build-summary.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n", "utf-8"
    )

    rec = ProvenanceRecord(
        artifact_id="m2d-regional-context-evidence", artifact_path=pq.as_posix(), artifact_kind="table", code_version=current_code_version(),
        sources=[source_ref("population-worldpop-r2025a", original_crs="EPSG:4326"), source_ref("builtup-ghsl-r2023a", original_crs="EPSG:4326"), source_ref("osm-service-pois-aoi", original_crs="EPSG:4326"), source_ref("osm-industry-aoi", original_crs="EPSG:4326"), source_ref("industry-diw-factories", original_crs=None), source_ref("mining-dpim-concessions", original_crs=None), source_ref("boundaries-ocha-cod-ab", original_crs="EPSG:4326")],
        normalized_crs=CANONICAL,
        method="Wave-1 evidence: rasters summed to 500 m cells by pixel centre; OSM POIs classified into separate components and routed on the frozen M2A BASELINE_DRIVE_TIME network; DIW/DPIM records are tambon-level only; no score of any kind.",
        spatial_resolution="500 m cells (population/built-form/POI), tambon (DIW, DPIM legacy), province (DPIM current)", confidence=Confidence.LOW,
        limitations=[*list(SCOPE_STATEMENTS.values()), "DIW registers have no coordinates or operating status; DPIM sources have no coordinates; no source here locates a stone-crushing plant.", "OSM completeness varies and the absence of a POI is not the absence of a service.", "Euclidean context counts are descriptive radii, not exclusion buffers."],
    )  # fmt: skip
    Path(str(pq) + ".provenance.json").write_text(rec.to_json() + "\n", "utf-8")
    print(json.dumps(summary, ensure_ascii=False)[:1500])
    print(f"done {len(out):,} cells, {out.shape[1]} columns in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
