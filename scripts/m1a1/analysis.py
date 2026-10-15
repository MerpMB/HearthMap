"""M1A.1 analyses (descriptive QA only). Results cached in data/interim/m1a1/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import AOI_LONLAT, CANONICAL, PROCESSED, PROVINCE_NAMES, raw_source

from hearthmap.ingestion.readers import read_esrijson_pages
from hearthmap.qa import (
    audit_repairs,
    category_area_combinations,
    category_cell_combinations,
    corroborate_zones,
    disagreement_zones,
    threshold_distribution,
    uncertainty_cells,
)
from hearthmap.qa.repair import summarise_repairs
from hearthmap.spatial import reproject
from hearthmap.spatial.grid import cell_coverage
from hearthmap.spatial.transform import reproject_recorded

CACHE = Path("data/interim/m1a1")
MATERIAL_OFFSET_M = 250.0  # half a grid cell: enough to flip an edge cell's majority province
CELL = 500.0
PIXEL_AREA_M2 = 29.3 * 30.9  # 1 arc-second at ~19 N (approximate, for explanation only)


def load_base() -> dict:
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    dist = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="district_boundaries")
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")

    g_dir, _ = raw_source("boundaries-gistda-50k")
    gp = read_esrijson_pages(g_dir, "L05_Province_GISTDA_50k")
    gp["adm1_pcode"] = "TH" + gp["PV_CODE"].astype(str)
    gp = reproject(gp[["adm1_pcode", "geometry"]], CANONICAL)
    gb_dir, _ = raw_source("boundaries-geoboundaries")
    gb = gpd.read_file(next(gb_dir.glob("*.geojson")))
    gb = gb[gb["shapeISO"].isin(["TH-50", "TH-56", "TH-57"])].copy()
    gb["adm1_pcode"] = gb["shapeISO"].str.replace("-", "")
    gb = reproject(gb[["adm1_pcode", "geometry"]], CANONICAL)

    cod_dir, _ = raw_source("boundaries-ocha-cod-ab")
    adm0 = gpd.read_file(
        f"zip://{(cod_dir / 'tha_admin_boundaries.gdb.zip').as_posix()}", layer="tha_admin0"
    )
    adm0, _ = reproject_recorded(adm0, CANONICAL, area_of_interest=AOI_LONLAT)
    adm1_all = gpd.read_file(
        f"zip://{(cod_dir / 'tha_admin_boundaries.gdb.zip').as_posix()}", layer="tha_admin1"
    )
    adm1_all, _ = reproject_recorded(
        adm1_all[["adm1_pcode", "adm1_name", "geometry"]], CANONICAL, area_of_interest=AOI_LONLAT
    )
    aoi = shapely.union_all(prov.geometry.values)
    national_border = adm0.geometry.iloc[0].boundary.intersection(aoi.buffer(20_000))
    return {
        "prov": prov,
        "dist": dist,
        "grid": grid,
        "gistda": gp,
        "geob": gb,
        "national_border": national_border,
        "aoi": aoi,
        "adm1_all": adm1_all[adm1_all.intersects(aoi.buffer(30_000))],
    }


# ---------------------------------------------------------------- boundaries


def boundary_audit(b: dict) -> dict:
    zones = []
    for name, ref in (("gistda-50k", b["gistda"]), ("geoboundaries", b["geob"])):
        zones.append(
            disagreement_zones(
                b["prov"],
                ref,
                key="adm1_pcode",
                reference_name=name,
                grid=b["grid"],
                districts=b["dist"],
                national_border=b["national_border"],
                material_offset_m=MATERIAL_OFFSET_M,
            )
        )
    z = pd.concat(zones, ignore_index=True)
    z = gpd.GeoDataFrame(z, geometry="geometry", crs=CANONICAL)
    z["province_name"] = z["province"].map(PROVINCE_NAMES)
    # Corroboration: does the OTHER reference follow the same alternative line?
    z["corroboration_fraction"] = corroborate_zones(
        z,
        b["prov"],
        {"gistda-50k": b["gistda"], "geoboundaries": b["geob"]},
        key="adm1_pcode",
        distance_m=MATERIAL_OFFSET_M,
        only=(z["material"] | (z["area_km2"] >= 0.01)).to_numpy(),
    )
    # Which COD-AB province lies on the other side of the edge (context only).
    nb = []
    for _, r in z.iterrows():
        if not (r["material"] or r["area_km2"] >= 0.01):
            nb.append(None)  # only attributed for zones that appear in the review table
            continue
        cand = b["adm1_all"][b["adm1_all"]["adm1_pcode"] != r["province"]]
        d = cand.distance(r.geometry)
        nb.append(
            "Myanmar/Laos (international)"
            if r["border_type"] == "international"
            else cand.loc[d.idxmin(), "adm1_name"]
        )
    z["other_side"] = nb
    z["notes"] = (
        np.where(
            z["kind"] == "primary_only",
            "COD-AB includes this area; reference excludes it. ",
            "Reference includes this area; COD-AB does not. ",
        )
        + z["classification_rule"]
    )

    cells = uncertainty_cells(b["grid"], z)
    grid = b["grid"].set_index("cell_id")
    cells = cells.merge(
        grid[["coverage_fraction", "majority_pcode"]], left_on="cell_id", right_index=True
    )
    frac_cols = [c for c in cells.columns if c.startswith("disagreement_fraction_")]
    aoi_cells = len(grid)
    aoi_area = float((grid["coverage_fraction"] * CELL**2).sum())

    def stats(sel: pd.DataFrame) -> dict:
        return {
            "cells": len(sel),
            "share_of_aoi_cells": len(sel) / aoi_cells,
            "clipped_area_of_affected_cells_km2": float(
                (sel["coverage_fraction"] * CELL**2).sum() / 1e6
            ),
            "share_of_aoi_area": float((sel["coverage_fraction"] * CELL**2).sum() / aoi_area),
            "by_province_cells": sel["majority_pcode"].value_counts().to_dict(),
        }

    mask_stats = {"material_offset_threshold_m": MATERIAL_OFFSET_M, "any_reference": stats(cells)}
    for c in frac_cols:
        mask_stats[c.replace("disagreement_fraction_", "")] = stats(cells[cells[c] > 0])
    material_area = z[z["material"]].groupby(["reference_source", "province"])["area_km2"].sum()
    mask_stats["material_zone_area_km2"] = {
        f"{r}|{p}": round(v, 3) for (r, p), v in material_area.items()
    }
    return {"zones": z, "cells": cells, "stats": mask_stats}


# ---------------------------------------------------------------- forest / protected


def _load_screening(b: dict) -> dict:
    lay = PROCESSED / "layers.gpkg"
    return {
        "reserve": gpd.read_file(lay, layer="forest_reserve_screening"),
        "park": gpd.read_file(lay, layer="national_park_screening"),
        "sanctuary": gpd.read_file(lay, layer="wildlife_sanctuary_screening"),
    }


def forest_audit(b: dict) -> dict:
    layers = _load_screening(b)
    grid = b["grid"]
    cells = grid.geometry.values
    unions = {k: shapely.union_all(v.geometry.values) for k, v in layers.items()}

    # Fractions of the IN-AOI part of each cell (intersection area / clipped cell area).
    cov = grid["coverage_fraction"].to_numpy()
    aoi_frac = {
        k: np.divide(
            cell_coverage(cells, u.intersection(b["aoi"]), CELL),
            cov,
            out=np.zeros(len(grid)),
            where=cov > 0,
        ).clip(0, 1)
        for k, u in unions.items()
    }
    per_cell = pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "coverage_fraction": cov,
            "majority_pcode": grid["majority_pcode"],
            **{f"{k}_area_fraction": v for k, v in aoi_frac.items()},
        }
    )

    dist_rows, hist_rows = [], []
    bins = np.linspace(0, 1, 11)
    res_union = unions["reserve"]
    for scope, geom in [("AOI", b["aoi"])] + [
        (p, g) for p, g in zip(b["prov"]["adm1_pcode"], b["prov"].geometry, strict=True)
    ]:
        c_cov = cell_coverage(cells, geom, CELL) if scope != "AOI" else cov
        r_cov = cell_coverage(cells, res_union.intersection(geom), CELL)
        sel = c_cov > 0
        frac = np.clip(r_cov[sel] / c_cov[sel], 0, 1)
        t = threshold_distribution(frac, covered_area_m2=r_cov[sel] * CELL**2)
        t.insert(0, "scope", scope)
        t.insert(1, "province", PROVINCE_NAMES.get(scope, "AOI"))
        t["cells_in_scope"] = int(sel.sum())
        t["scope_area_km2"] = float(c_cov[sel].sum() * CELL**2 / 1e6)
        t["reserve_area_km2_in_scope"] = float(r_cov[sel].sum() * CELL**2 / 1e6)
        dist_rows.append(t)
        zero = int((frac == 0).sum())
        counts, _ = np.histogram(frac[frac > 0], bins=bins)
        hist_rows.append(
            {
                "scope": scope,
                "fraction_eq_0": zero,
                **{f"({bins[i]:.1f},{bins[i + 1]:.1f}]": int(n) for i, n in enumerate(counts)},
            }
        )
    dist = pd.concat(dist_rows, ignore_index=True)
    hist = pd.DataFrame(hist_rows)

    combos_area = []
    for scope, geom in [("AOI", b["aoi"])] + [
        (p, g) for p, g in zip(b["prov"]["adm1_pcode"], b["prov"].geometry, strict=True)
    ]:
        t = category_area_combinations(layers, within=geom)
        t.insert(0, "scope", scope)
        t["scope_area_km2"] = geom.area / 1e6
        t["share_of_scope"] = t["area_km2"] / t["scope_area_km2"]
        combos_area.append(t)
    combos_area = pd.concat(combos_area, ignore_index=True)
    combos_cells = category_cell_combinations({k: v for k, v in aoi_frac.items()})
    combo_label = per_cell.apply(
        lambda r: (
            "+".join(k for k in ("reserve", "park", "sanctuary") if r[f"{k}_area_fraction"] > 0)
            or "none"
        ),
        axis=1,
    )
    per_cell["category_combination"] = combo_label
    return {
        "layers": layers,
        "per_cell": per_cell,
        "distribution": dist,
        "histogram": hist,
        "combos_area": combos_area,
        "combos_cells": combos_cells,
    }


# ---------------------------------------------------------------- flood repair


def flood_repair_audit(b: dict) -> dict:
    f_dir, _ = raw_source("flood-gistda-repeated-2005-2016")
    raw = read_esrijson_pages(f_dir, "page")
    invalid_src = ~raw.geometry.is_valid
    # Same-datum conversion to metres; invalidity is preserved for area diagnostics.
    utm = reproject(raw[["objectid", "flood_freq", "geometry"]], CANONICAL)
    invalid_utm = ~utm.geometry.is_valid
    audit = audit_repairs(utm[invalid_src.to_numpy()], id_column="objectid")
    summary = summarise_repairs(audit, total_features=len(raw))
    summary["invalid_in_source_crs_epsg3857"] = int(invalid_src.sum())
    summary["invalid_after_conversion_to_utm"] = int(invalid_utm.sum())
    summary["audit_note"] = (
        "Repair replayed with shapely.make_valid on the source features after conversion to "
        "EPSG:32647 (same datum) to measure areas in metres. M1A repaired in EPSG:3857 before "
        "conversion; consistency with the M1A layer is checked below."
    )
    # Consistency with M1A processed layer (repaired in 3857 then projected).
    m1a = gpd.read_file(
        PROCESSED / "layers.gpkg",
        layer="flood_recurrence",
        where=f"objectid IN ({','.join(audit['source_feature_id'])})",
    )
    m1a_area = m1a.set_index(m1a["objectid"].astype(str)).geometry.area
    audit["m1a_layer_area_m2"] = audit["source_feature_id"].map(m1a_area)
    audit["m1a_vs_audit_area_delta_m2"] = audit["m1a_layer_area_m2"] - audit["area_after_m2"]
    summary["max_abs_m1a_vs_audit_area_delta_m2"] = float(
        audit["m1a_vs_audit_area_delta_m2"].abs().max()
    )
    flood_freq = utm.set_index(utm["objectid"].astype(str))["flood_freq"]
    audit["flood_freq"] = audit["source_feature_id"].map(flood_freq)
    before = utm[invalid_src.to_numpy()].copy()
    before["objectid"] = before["objectid"].astype(str)
    return {"audit": audit, "summary": summary, "before": before}


# ---------------------------------------------------------------- DEM edge cells


def dem_edge_cells(b: dict) -> dict:
    terr = gpd.read_file(PROCESSED / "dem.gpkg", layer="terrain_preview_500m")
    none = terr[terr["dem_pixel_count"] == 0].copy()
    clipped = shapely.intersection(none.geometry.values, b["aoi"])
    none["clipped_area_m2"] = shapely.area(clipped)
    none["clipped_mean_width_m"] = (
        2 * none["clipped_area_m2"] / np.maximum(shapely.length(clipped), 1e-9)
    )
    none["expected_pixel_centres"] = none["clipped_area_m2"] / PIXEL_AREA_M2
    partial = terr[terr["coverage_fraction"] < 1 - 1e-9]
    small = partial[partial["coverage_fraction"] * CELL**2 < 2 * PIXEL_AREA_M2]
    summary = {
        "cells_without_pixel_centre": len(none),
        "all_are_partial_edge_cells": bool((none["coverage_fraction"] < 1).all()),
        "coverage_fraction_max": float(none["coverage_fraction"].max()),
        "coverage_fraction_median": float(none["coverage_fraction"].median()),
        "clipped_area_m2_max": float(none["clipped_area_m2"].max()),
        "clipped_area_m2_median": float(none["clipped_area_m2"].median()),
        "clipped_area_total_m2": float(none["clipped_area_m2"].sum()),
        "clipped_mean_width_m_max": float(none["clipped_mean_width_m"].max()),
        "expected_pixel_centres_max": float(none["expected_pixel_centres"].max()),
        "approx_pixel_area_m2": PIXEL_AREA_M2,
        "partial_cells_smaller_than_2_pixels": len(small),
        "of_which_without_pixel": int((small["dem_pixel_count"] == 0).sum()),
        "by_majority_province": none.merge(b["grid"][["cell_id", "majority_pcode"]], on="cell_id")[
            "majority_pcode"
        ]
        .value_counts()
        .to_dict(),
    }
    return {"cells": none, "summary": summary, "terrain": terr}


def write_cache(obj, name: str) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(obj, indent=2, default=str), "utf-8")


# ---------------------------------------------------------------- materiality


def boundary_materiality(b: dict, ba: dict, fa: dict, terrain: gpd.GeoDataFrame) -> pd.DataFrame:
    """Describe what kind of land the uncertainty cells are (context, not scoring)."""
    ov = gpd.read_file(
        PROCESSED / "overlays.gpkg",
        layer="screening_overlays_500m",
        columns=["cell_id", "dist_major_road_m", "flood_obs_affected_area_fraction"],
        ignore_geometry=True,
    )
    base = (
        fa["per_cell"][["cell_id", "reserve_area_fraction", "park_area_fraction"]]
        .merge(terrain[["cell_id", "elev_mean_m", "slope_gt15_fraction"]], on="cell_id")
        .merge(ov, on="cell_id")
    )
    groups = {"AOI (all cells)": base["cell_id"]}
    cells = ba["cells"]
    for col in [c for c in cells.columns if c.startswith("disagreement_fraction_")]:
        groups[f"uncertainty cells: {col.replace('disagreement_fraction_', '')}"] = cells.loc[
            cells[col] > 0, "cell_id"
        ]
    rows = []
    for name, ids in groups.items():
        s = base[base["cell_id"].isin(set(ids))]
        rows.append(
            {
                "group": name,
                "cells": len(s),
                "median_elev_mean_m": float(s["elev_mean_m"].median()),
                "median_slope_gt15_fraction": float(s["slope_gt15_fraction"].median()),
                "share_reserve_ge_0_9": float((s["reserve_area_fraction"] >= 0.9).mean()),
                "share_park_gt_0": float((s["park_area_fraction"] > 0).mean()),
                "median_dist_major_road_m": float(s["dist_major_road_m"].median()),
                "share_observed_flood_gt_0": float(
                    (s["flood_obs_affected_area_fraction"] > 0).mean()
                ),
            }
        )
    return pd.DataFrame(rows)
