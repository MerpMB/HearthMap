"""M1A stage: validate + normalise administrative boundaries, then build the grid.

RAW -> VALIDATED (statistics JSON) -> NORMALIZED (EPSG:32647 GeoPackage) ->
DERIVED (500 m grid). Mismatches against independent references are recorded,
never silently corrected. Nothing here scores anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    AOI_LONLAT,
    AOI_PCODES,
    CANONICAL,
    PROCESSED,
    PROVINCE_NAMES,
    VALIDATION,
    raw_source,
    source_ref,
    write_json,
    write_layer,
)

from hearthmap.config import load_project_config
from hearthmap.enums import Confidence
from hearthmap.ingestion.readers import read_esrijson_pages
from hearthmap.qa.coverage import coverage_accounting
from hearthmap.spatial import GridSpec, check_geometries, generate_grid
from hearthmap.spatial.grid import cell_coverage
from hearthmap.spatial.transform import reproject_recorded

BOUNDARY_SAMPLE_STEP_M = 250.0


def _boundary_offsets(a: shapely.Geometry, b: shapely.Geometry) -> dict[str, float]:
    """Distances from points sampled every 250 m along a's boundary to b's boundary."""
    pts = []
    for ring in shapely.get_parts(shapely.line_merge(a.boundary)):
        n_r = max(int(ring.length // BOUNDARY_SAMPLE_STEP_M), 1)
        pts.append(
            shapely.line_interpolate_point(ring, np.linspace(0, ring.length, n_r, endpoint=False))
        )
    pts = np.concatenate(pts)
    n = len(pts)
    # Split the reference boundary into 2-point segments and use a spatial index
    # (distance to one huge linestring is O(n*m)).
    coords_list = [shapely.get_coordinates(g) for g in shapely.get_parts(b.boundary)]
    segs = np.concatenate(
        [shapely.linestrings(np.stack([c[:-1], c[1:]], axis=1)) for c in coords_list if len(c) > 1]
    )
    tree = shapely.STRtree(segs)
    _, d = tree.query_nearest(pts, return_distance=True, all_matches=False)
    return {
        "samples": int(n),
        "median_m": round(float(np.median(d)), 1),
        "p95_m": round(float(np.percentile(d, 95)), 1),
        "max_m": round(float(d.max()), 1),
        "share_within_100m": round(float((d <= 100).mean()), 4),
    }


def _compare(primary: gpd.GeoDataFrame, ref: gpd.GeoDataFrame, key_ref: str) -> dict:
    out = {}
    for pcode, row in primary.set_index("adm1_pcode").iterrows():
        match = ref[ref[key_ref] == pcode]
        if len(match) != 1:
            out[pcode] = {"error": f"expected one reference feature, found {len(match)}"}
            continue
        a, b = row.geometry, match.geometry.iloc[0]
        sym = a.symmetric_difference(b).area
        out[pcode] = {
            "primary_area_km2": round(a.area / 1e6, 2),
            "reference_area_km2": round(b.area / 1e6, 2),
            "area_diff_pct": round(100 * (b.area - a.area) / a.area, 3),
            "symmetric_difference_km2": round(sym / 1e6, 2),
            "symmetric_difference_pct_of_primary": round(100 * sym / a.area, 3),
            "boundary_offset": _boundary_offsets(a, b),
        }
    return out


def main() -> int:
    cfg = load_project_config("config")
    report: dict = {"stage": "VALIDATED", "aoi_pcodes": AOI_PCODES}

    # ------------------------------------------------------------ PRIMARY: COD-AB
    cod_dir, _ = raw_source("boundaries-ocha-cod-ab")
    gdb = f"zip://{(cod_dir / 'tha_admin_boundaries.gdb.zip').as_posix()}"
    adm1_all = gpd.read_file(gdb, layer="tha_admin1")
    adm2_all = gpd.read_file(gdb, layer="tha_admin2")
    adm1 = adm1_all[adm1_all["adm1_pcode"].isin(AOI_PCODES)].copy()
    adm2 = adm2_all[adm2_all["adm1_pcode"].isin(AOI_PCODES)].copy()
    report["primary"] = {
        "source_id": "boundaries-ocha-cod-ab",
        "national_feature_counts": {"admin1": len(adm1_all), "admin2": len(adm2_all)},
        "aoi_feature_counts": {"admin1": len(adm1), "admin2": len(adm2)},
        "source_crs": adm1.crs.to_string(),
        "names_and_codes": adm1[["adm1_pcode", "adm1_name", "adm1_name1"]].to_dict("records"),
        "geometry_validity_source": {
            "admin1": check_geometries(adm1).summary(),
            "admin2": check_geometries(adm2).summary(),
        },
        "bbox_lonlat": [round(v, 5) for v in adm1.total_bounds],
    }
    if len(adm1) != 3:
        raise SystemExit(f"expected 3 AOI provinces, found {len(adm1)}")

    adm1_n, tr1 = reproject_recorded(
        adm1, CANONICAL, name="cod-ab admin1", area_of_interest=AOI_LONLAT
    )
    adm2_n, tr2 = reproject_recorded(
        adm2, CANONICAL, name="cod-ab admin2", area_of_interest=AOI_LONLAT
    )
    report["primary"]["normalized_crs"] = CANONICAL
    report["primary"]["transformation"] = {
        "operation": tr1.operation,
        "datum_change": tr1.datum_change,
        "accuracy_m": tr1.accuracy_m,
        "selection": tr1.selection,
    }
    report["primary"]["bbox_utm47n"] = [round(v, 1) for v in adm1_n.total_bounds]

    geom_n = check_geometries(adm1_n)
    report["primary"]["geometry_validity_normalized"] = geom_n.summary()

    per_prov = {}
    for _, r in adm1_n.iterrows():
        dist = adm2_n[adm2_n["adm1_pcode"] == r["adm1_pcode"]]
        dist_union = shapely.union_all(dist.geometry.values)
        per_prov[r["adm1_pcode"]] = {
            "name": r["adm1_name"],
            "area_km2_computed_utm47n": round(r.geometry.area / 1e6, 2),
            "area_km2_attribute": round(float(r["area_sqkm"]), 2),
            "area_attribute_diff_pct": round(
                100 * (r.geometry.area / 1e6 - r["area_sqkm"]) / r["area_sqkm"], 3
            ),
            "district_count": len(dist),
            "district_area_sum_km2": round(dist.geometry.area.sum() / 1e6, 2),
            "district_overlap_km2": round((dist.geometry.area.sum() - dist_union.area) / 1e6, 4),
            "province_vs_district_union_symdiff_km2": round(
                r.geometry.symmetric_difference(dist_union).area / 1e6, 4
            ),
            "parts": int(shapely.get_num_geometries(r.geometry)),
            "interior_rings": int(
                sum(len(p.interiors) for p in getattr(r.geometry, "geoms", [r.geometry]))
            ),
        }
    report["primary"]["per_province"] = per_prov

    # Inter-province topology: overlaps and gaps along shared borders.
    topo = {}
    rows = list(adm1_n.itertuples())
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            inter = a.geometry.intersection(b.geometry)
            shared = a.geometry.boundary.intersection(b.geometry.boundary)
            topo[f"{a.adm1_pcode}|{b.adm1_pcode}"] = {
                "overlap_area_m2": round(inter.area, 2),
                "shared_border_km": round(shared.length / 1e3, 2),
            }
    union = shapely.union_all(adm1_n.geometry.values)
    holes = [shapely.Polygon(r) for p in getattr(union, "geoms", [union]) for r in p.interiors]
    report["primary"]["inter_province_topology"] = {
        "pairs": topo,
        "union_interior_gaps": len(holes),
        "union_interior_gap_area_m2": round(sum(h.area for h in holes), 2),
    }

    # ------------------------------------------------------------ SECONDARY / VALIDATION
    g_dir, _ = raw_source("boundaries-gistda-50k")
    gp = read_esrijson_pages(g_dir, "L05_Province_GISTDA_50k")
    ga = read_esrijson_pages(g_dir, "L05_Amphoe_GISTDA_50k")
    gp["adm1_pcode"] = "TH" + gp["PV_CODE"].astype(str)
    gp_n, tr_g = reproject_recorded(
        gp, CANONICAL, name="gistda province", area_of_interest=AOI_LONLAT
    )
    gb_dir, _ = raw_source("boundaries-geoboundaries")
    gb = gpd.read_file(next(gb_dir.glob("*.geojson")))
    gb = gb[gb["shapeISO"].isin(["TH-50", "TH-56", "TH-57"])].copy()
    gb["adm1_pcode"] = gb["shapeISO"].str.replace("-", "")
    gb_n, tr_b = reproject_recorded(
        gb, CANONICAL, name="geoboundaries", area_of_interest=AOI_LONLAT
    )

    report["references"] = {
        "boundaries-gistda-50k": {
            "role": "SECONDARY",
            "province_codes": gp[["PV_CODE", "PV_TN", "PV_EN"]].to_dict("records"),
            "district_counts": ga.groupby("PV_CODE").size().to_dict(),
            "geometry_validity": check_geometries(gp_n).summary(),
            "comparison_vs_primary": _compare(adm1_n, gp_n, "adm1_pcode"),
        },
        "boundaries-geoboundaries": {
            "role": "VALIDATION_ONLY",
            "province_codes": gb[["shapeISO", "shapeName"]].to_dict("records"),
            "geometry_validity": check_geometries(gb_n).summary(),
            "comparison_vs_primary": _compare(adm1_n, gb_n, "adm1_pcode"),
        },
    }

    # Code systems (verified, see registry + report): P-code TH50 = 'TH' + Thai
    # province code 50 (GISTDA PV_CODE 50) = ISO 3166-2 TH-50.
    codes = {}
    for pcode, name in PROVINCE_NAMES.items():
        num = pcode[2:]
        codes[pcode] = {
            "name": name,
            "thai_province_code": num,
            "ocha_pcode": pcode,
            "iso_3166_2": f"TH-{num}",
            "gistda_pv_code_matches": bool((gp["PV_CODE"].astype(str) == num).any()),
            "geoboundaries_iso_matches": bool((gb["shapeISO"] == f"TH-{num}").any()),
            "config_province_code_matches": any(
                r.province_code == num for r in cfg.regions.regions if r.name_en == name
            ),
        }
    report["code_crosswalk"] = codes

    gate = {
        "three_provinces": len(adm1_n) == 3,
        "geometry_valid": geom_n.ok,
        "no_inter_province_overlap": all(v["overlap_area_m2"] < 1.0 for v in topo.values()),
        "district_counts_match_secondary": {
            k: int(v["district_count"]) == int(ga[ga["PV_CODE"].astype(str) == k[2:]].shape[0])
            for k, v in per_prov.items()
        },
        "codes_consistent": all(
            c["gistda_pv_code_matches"]
            and c["geoboundaries_iso_matches"]
            and c["config_province_code_matches"]
            for c in codes.values()
        ),
    }
    gate["passed"] = (
        gate["three_provinces"]
        and gate["geometry_valid"]
        and gate["no_inter_province_overlap"]
        and all(gate["district_counts_match_secondary"].values())
        and gate["codes_consistent"]
    )
    report["gate"] = gate
    write_json(report, VALIDATION / "boundaries.json")
    if not gate["passed"]:
        print("BOUNDARY VALIDATION FAILED - grid not generated", gate)
        return 1

    # ------------------------------------------------------------ NORMALIZED layers
    cod_ref = source_ref("boundaries-ocha-cod-ab", original_crs="EPSG:4326")
    norm = PROCESSED / "boundaries.gpkg"
    keep1 = ["adm1_pcode", "adm1_name", "adm1_name1", "area_sqkm", "valid_on", "version"]
    adm1_out = adm1_n[[*keep1, "geometry"]].rename(
        columns={"adm1_name1": "adm1_name_th", "area_sqkm": "area_sqkm_source"}
    )
    adm1_out["area_km2_utm47n"] = adm1_out.geometry.area / 1e6
    write_layer(
        adm1_out,
        norm,
        "province_boundaries",
        sources=[cod_ref],
        method="COD-AB admin1 filtered to TH50/TH56/TH57; WGS84 geographic -> UTM 47N conversion.",
        resolution="Vector; source scale not published (RTSD-derived, 2022 edition)",
        confidence=Confidence.MEDIUM,
        limitations=[
            "Administrative boundaries are not cadastral/legal parcel boundaries.",
            "Edge position differs from independent references by tens to hundreds "
            "of metres in places (see validation report).",
        ],
        transformations=[tr1],
        steps=[
            ("filter", "adm1_pcode in AOI", {"pcodes": list(AOI_PCODES)}),
            ("reproject", "recorded conversion", {"target": CANONICAL}),
        ],
    )
    keep2 = ["adm2_pcode", "adm2_name", "adm2_name1", "adm1_pcode", "adm1_name", "area_sqkm"]
    write_layer(
        adm2_n[[*keep2, "geometry"]].rename(columns={"adm2_name1": "adm2_name_th"}),
        norm,
        "district_boundaries",
        sources=[cod_ref],
        method="COD-AB admin2 for AOI provinces; WGS84 -> UTM 47N conversion.",
        resolution="Vector; source scale not published",
        confidence=Confidence.MEDIUM,
        limitations=["Not legal parcel boundaries."],
        transformations=[tr2],
        steps=[("filter", "adm1_pcode in AOI", {"pcodes": list(AOI_PCODES)})],
    )
    # Reference differences, for human review in QGIS.
    diffs = []
    for ref_name, ref in (("gistda-50k", gp_n), ("geoboundaries", gb_n)):
        for _, r in adm1_n.iterrows():
            other = ref[ref["adm1_pcode"] == r["adm1_pcode"]].geometry.iloc[0]
            diffs.append(
                {
                    "adm1_pcode": r["adm1_pcode"],
                    "reference": ref_name,
                    "kind": "primary_only",
                    "geometry": r.geometry.difference(other),
                }
            )
            diffs.append(
                {
                    "adm1_pcode": r["adm1_pcode"],
                    "reference": ref_name,
                    "kind": "reference_only",
                    "geometry": other.difference(r.geometry),
                }
            )
    diff_gdf = gpd.GeoDataFrame(diffs, crs=CANONICAL).explode(index_parts=False)
    diff_gdf["area_m2"] = diff_gdf.geometry.area
    write_layer(
        diff_gdf[diff_gdf["area_m2"] > 0],
        norm,
        "boundary_reference_differences",
        sources=[
            cod_ref,
            source_ref("boundaries-gistda-50k", original_crs="EPSG:3857"),
            source_ref("boundaries-geoboundaries", original_crs="EPSG:4326"),
        ],
        method="Polygon differences between COD-AB (primary) and each reference, per province.",
        resolution="Vector",
        confidence=Confidence.MEDIUM,
        limitations=["Differences are recorded, not corrected. Validation aid only."],
        transformations=[tr1, tr_g, tr_b],
    )

    # ------------------------------------------------------------ DERIVED: grid
    gcfg = cfg.spatial.grid
    spec = GridSpec(
        cell_size_m=gcfg.cell_size_m,
        crs=CANONICAL,
        selection=gcfg.selection,
        id_prefix=gcfg.id_prefix,
        max_cells=gcfg.max_cells,
    )
    grid = generate_grid(adm1_n, spec)
    # Per-province membership by area (cells on borders can touch two provinces).
    cell_area = spec.cell_size_m**2
    prov_frac = {
        r.adm1_pcode: cell_coverage(grid.geometry.values, r.geometry, spec.cell_size_m)
        for r in adm1_n.itertuples()
    }
    fr = pd.DataFrame(prov_frac)
    grid["majority_pcode"] = fr.idxmax(axis=1).where(fr.max(axis=1) > 0).values
    grid["n_provinces"] = (fr > 0).sum(axis=1).values
    memb = fr.reset_index(names="cell").melt(id_vars="cell", var_name="pcode", value_name="frac")
    memb = memb[memb["frac"] > 0]
    memb["area"] = memb["frac"] * cell_area
    grid_stats = {}
    for pcode in AOI_PCODES:
        m = memb[memb["pcode"] == pcode]
        frac = m["frac"].to_numpy()
        prov_area = float(adm1_n.loc[adm1_n["adm1_pcode"] == pcode].geometry.area.iloc[0])
        acc = coverage_accounting(frac, spec.cell_size_m, prov_area)
        grid_stats[pcode] = {
            "province": PROVINCE_NAMES[pcode],
            **acc.as_km2(),
            "cells_majority_in_province": int((grid["majority_pcode"] == pcode).sum()),
        }
    union_area = shapely.union_all(adm1_n.geometry.values).area
    acc = coverage_accounting(grid["coverage_fraction"].to_numpy(), spec.cell_size_m, union_area)
    grid_stats["AOI"] = {
        **acc.as_km2(),
        "cells_touching_two_provinces": int((grid["n_provinces"] > 1).sum()),
        "cell_size_m": spec.cell_size_m,
        "selection": spec.selection,
        "cell_ids_unique": bool(grid["cell_id"].is_unique),
    }
    if not all(v["invariant_ok"] for v in grid_stats.values()):
        raise SystemExit(f"coverage invariant violated: {grid_stats}")
    write_json(grid_stats, VALIDATION / "grid.json")
    write_layer(
        grid,
        PROCESSED / "grid.gpkg",
        "analysis_grid_500m",
        sources=[cod_ref],
        method=f"{spec.cell_size_m:g} m cells aligned to multiples of the cell size in "
        f"{CANONICAL}; "
        "'intersects' selection (interior overlap) against the union of AOI provinces.",
        resolution="500 m regional decision surface (not the resolution of any dataset)",
        confidence=Confidence.MEDIUM,
        limitations=[
            "Geometry truth only: no cell carries a score in M1A.",
            "Edge-cell coverage depends on boundary generalisation.",
        ],
        transformations=[tr1],
        steps=[("grid", "generate aligned grid", {"cells": len(grid)})],
    )
    print("boundaries + grid OK:", grid_stats["AOI"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
