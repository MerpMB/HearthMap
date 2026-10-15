"""M1B: per-cell hazard evidence (DERIVED_INDICATOR + PROVISIONAL_HAZARD_INTERPRETATION).

Outputs
  outputs/m1b/hearthmap-hazard-evidence.gpkg   cells (geometry + key fields), review-friendly
  outputs/m1b/hazard-evidence.parquet          wide analytical table (no geometry)
  outputs/m1b/hazard-data-dictionary.csv       every field: level, hazard, meaning, source
  outputs/m1b/experimental-exclusion-candidates.parquet
  outputs/m1b/threshold-sensitivity.csv, hazard-statistics.json, provenance sidecars
Nothing here excludes, scores or ranks a location.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
import terrain_cells
from common import AOI_LONLAT, CANONICAL, PROCESSED, PROVINCE_NAMES, raw_source, source_ref

from hearthmap.enums import Confidence
from hearthmap.hazard import (
    EvidenceLevel,
    experimental_candidates,
    interpret,
    load_hazard_config,
    threshold_sensitivity,
)
from hearthmap.provenance import ProvenanceRecord, current_code_version
from hearthmap.qa import audit_repairs
from hearthmap.qa.repair import summarise_repairs
from hearthmap.spatial import repair_geometries
from hearthmap.spatial.overlay import categorical_cell_fractions
from hearthmap.spatial.transform import reproject_recorded

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs/m1b")
CACHE = Path("data/processed/m1b")
CELL = 500.0
REVIEW_GPKG = Path("outputs/m1a-review/hearthmap-m1a-review.gpkg")
DMR_CLASSES = [1, 2, 3, 4, 5]
DMR_LABELS = {1: "Very Low", 2: "Low", 3: "Medium", 4: "High", 5: "Very High"}
FLOOD_YEAR_KS = (2, 3, 4, 5)
LEGACY_FLOOD = "legacy_flood_2005_2016"
FLOOD_2011_2023 = Path("data/processed/m1c1/flood.gpkg")


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------- loaders


def base():
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.values)
    return grid, prov, aoi


def flood_metrics(grid, aoi, fl, *, years_col: str, record_years: int, prefix: str):
    """Single pass of (cell piece x flood polygon) intersections for one flood record.

    Requires polygons that do not overlap each other (checked per source: M1A for
    2005-2016, outputs/m1c1/flood-2011-2023-qa.json for 2011-2023), so per-cell sums
    of intersection areas equal the area of their union. Cell pieces are clipped
    to the AOI for partial cells. ``{prefix}_years_ge{k}_area_fraction`` = share of
    the cell observed flooded in >= k of ``record_years`` years.
    """
    cells = grid.geometry.values
    cov = grid["coverage_fraction"].to_numpy()
    pieces = cells.copy()
    part = np.flatnonzero(cov < 1 - 1e-9)
    pieces[part] = shapely.intersection(cells[part], aoi)
    tree = shapely.STRtree(fl.geometry.values)
    ci, fi = tree.query(pieces, predicate="intersects")
    area = shapely.area(shapely.intersection(pieces[ci], fl.geometry.values[fi]))
    pos = area > 0
    ci, fi, area = ci[pos], fi[pos], area[pos]
    years = fl[years_col].to_numpy()[fi].astype(int)
    if years.max(initial=0) > record_years:
        raise ValueError(f"{years_col} exceeds the record length {record_years}")
    by_years = np.zeros((len(grid), record_years + 1))
    np.add.at(by_years, (ci, years), area)
    clipped = cov * CELL**2
    frac = np.divide(
        by_years, clipped[:, None], out=np.zeros_like(by_years), where=clipped[:, None] > 0
    )
    out = pd.DataFrame(index=grid.index)
    out[f"{prefix}_area_fraction"] = frac[:, 1:].sum(axis=1).clip(0, 1)
    for k in FLOOD_YEAR_KS:
        out[f"{prefix}_years_ge{k}_area_fraction"] = frac[:, k:].sum(axis=1).clip(0, 1)
    flooded = frac[:, 1:].sum(axis=1) > 0
    out[f"{prefix}_dominant_years"] = np.where(flooded, frac[:, 1:].argmax(axis=1) + 1, np.nan)
    present = frac[:, 1:] > 0
    out[f"{prefix}_max_years"] = np.where(
        flooded, record_years - np.argmax(present[:, ::-1], axis=1), np.nan
    )
    out[f"{prefix}_feature_count"] = np.bincount(ci, minlength=len(grid))
    _, dist = tree.query_nearest(pieces, return_distance=True, all_matches=False)
    out[f"{prefix}_distance_m"] = np.round(dist, 1)  # 0 when the cell touches a flood polygon
    return out


def flood_indicators(grid, aoi, cfg) -> pd.DataFrame:
    """Primary record (interpreted) + legacy record (corroboration/context only)."""
    ps, ls_ = cfg.flood.primary_source, cfg.flood.legacy_source
    raw_source(ps.source_id)  # re-verifies RAW checksums
    new = gpd.read_file(FLOOD_2011_2023, layer="flood_recurrence_2011_2023", columns=["total"])
    out = flood_metrics(
        grid, aoi, new, years_col="total", record_years=ps.record_years, prefix="flood"
    )
    out["flood_assessed"] = True  # national source answered for every AOI tile (not safety)
    out["flood_source_id"] = ps.source_id
    out["flood_evidence_period"] = ps.evidence_period
    out["flood_record_years"] = ps.record_years
    out["flood_source_role"] = ps.role
    old = gpd.read_file(PROCESSED / "layers.gpkg", layer="flood_recurrence", columns=["flood_freq"])
    leg = flood_metrics(
        grid,
        aoi,
        old,
        years_col="flood_freq",
        record_years=ls_.record_years,
        prefix=LEGACY_FLOOD,
    )
    leg[f"{LEGACY_FLOOD}_source_id"] = ls_.source_id
    leg[f"{LEGACY_FLOOD}_role"] = ls_.role
    return pd.concat([out, leg], axis=1)


def landslide_indicators(grid, aoi) -> tuple[pd.DataFrame, dict, dict]:
    raw_source("landslide-susceptibility-dmr")  # re-verifies RAW checksums
    shp = next(
        Path("data/interim/landslide-susceptibility-dmr").rglob("LANDSLIDE_SUSCEPTIBILITY.shp")
    )
    ls = gpd.read_file(shp)
    ls = ls[ls.intersects(aoi.buffer(2000))].copy()
    audit = audit_repairs(ls.assign(fid=ls["Id"]), id_column="fid")
    repair = summarise_repairs(audit, total_features=len(ls))
    ls = repair_geometries(ls)
    ls, tr = reproject_recorded(ls, CANONICAL, area_of_interest=AOI_LONLAT)  # already 32647
    cov = grid["coverage_fraction"].to_numpy()
    out = categorical_cell_fractions(
        grid,
        ls,
        class_field="gridcode",
        classes=DMR_CLASSES,
        prefix="landslide",
        within=aoi,
        coverage=cov,
    )
    out["landslide_max_class_label"] = out["landslide_max_class"].map(DMR_LABELS)
    out["landslide_dominant_class_label"] = out["landslide_dominant_class"].map(DMR_LABELS)
    out["landslide_source_support"] = out["landslide_assessed_fraction"]

    raw_source("landslide-inventory-dmr")  # re-verifies RAW checksums
    ishp = next(Path("data/interim/landslide-inventory-dmr").rglob("LANDSLIDE_INVENTORY_MAP.shp"))
    inv = gpd.read_file(ishp)
    inv = inv[inv.within(aoi)]
    j = gpd.sjoin(inv[["geometry"]], grid[["geometry"]], predicate="within", how="inner")
    out["landslide_inventory_points"] = np.bincount(
        j["index_right"].to_numpy(), minlength=len(grid)
    )
    tree = shapely.STRtree(inv.geometry.values)
    _, dist = tree.query_nearest(grid.geometry.values, return_distance=True, all_matches=False)
    out["landslide_inventory_distance_m"] = np.round(dist, 1)
    meta = {
        "features_near_aoi": len(ls),
        "repair": repair,
        "inventory_points_in_aoi": len(inv),
        "inventory_year_data_non_null": int(inv["YEAR_DATA"].notna().sum()),
        "transformation": tr.operation,
    }
    return out, meta, {"susceptibility_shp": shp.as_posix(), "inventory_shp": ishp.as_posix()}


def waterway_indicators(grid) -> pd.DataFrame:
    ww = gpd.read_file(PROCESSED / "layers.gpkg", layer="waterways", columns=["waterway", "osm_id"])
    cells = grid.geometry.values
    out = pd.DataFrame(index=grid.index)
    for name, sel in (
        ("major", ww["waterway"].isin(["river", "canal"])),
        ("any", pd.Series(True, index=ww.index)),
    ):
        tree = shapely.STRtree(ww[sel].geometry.values)
        _, dist = tree.query_nearest(cells, return_distance=True, all_matches=False)
        out[f"dist_{name}_waterway_m"] = np.round(dist, 1)
    for cls in ("river", "canal", "stream"):
        g = ww[ww["waterway"] == cls].geometry.values
        tree = shapely.STRtree(g)
        ci, gi = tree.query(cells, predicate="intersects")
        lens = shapely.length(shapely.intersection(cells[ci], g[gi]))
        out[f"waterway_{cls}_length_m"] = np.round(
            np.bincount(ci, weights=lens, minlength=len(grid)), 1
        )
    out["waterway_source_note"] = "OSM mapped waterways; absence of a mapped stream is not absence"
    return out


def context_columns(grid) -> pd.DataFrame:
    """Context only (never read by interpretation): M1A.1 review flags, legal screening."""
    out = pd.DataFrame(index=grid.index)
    unc = pyogrio.read_dataframe(
        REVIEW_GPKG, layer="boundary_uncertainty_review", read_geometry=False
    )
    gcol = "disagreement_fraction_gistda_50k"
    gids = set(unc.loc[unc[gcol] > 0, "cell_id"])
    out["boundary_attribution_uncertain"] = grid["cell_id"].isin(gids).to_numpy()
    zones = pyogrio.read_dataframe(REVIEW_GPKG, layer="boundary_disagreement_zones")
    zones = zones[(zones["reference_source"] == "gistda-50k") & zones["material"].astype(bool)]
    j = gpd.sjoin(
        grid[["cell_id", "geometry"]],
        zones[["zone_id", "geometry"]],
        predicate="intersects",
        how="inner",
    )
    ids = j.groupby("cell_id")["zone_id"].apply(lambda s: "|".join(sorted(set(s))))
    out["boundary_zone_ids"] = grid["cell_id"].map(ids).fillna("").to_numpy()
    fr = pyogrio.read_dataframe(
        REVIEW_GPKG,
        layer="forest_review",
        read_geometry=False,
        columns=[
            "cell_id",
            "reserve_area_fraction",
            "park_area_fraction",
            "sanctuary_area_fraction",
        ],
    )
    fr = fr.set_index("cell_id")
    for c in ("reserve_area_fraction", "park_area_fraction", "sanctuary_area_fraction"):
        out[c] = grid["cell_id"].map(fr[c]).fillna(0.0).to_numpy()
    out["requires_legal_verification"] = (
        out[["reserve_area_fraction", "park_area_fraction", "sanctuary_area_fraction"]] > 0
    ).any(axis=1)
    out["context_note"] = "context only - never changes hazard interpretation"
    return out


# ---------------------------------------------------------------- dictionary


def data_dictionary(cols: list[str]) -> pd.DataFrame:
    lv = EvidenceLevel
    rules = [
        (
            "flood_",
            "flood",
            lv.DERIVED_INDICATOR,
            "flood-gistda-history",
            "PRIMARY: observed (satellite) flooding 2011-2023; years_ge{k} = share of the cell "
            "observed flooded in >= k of 13 years; absence is not evidence of no risk",
        ),
        (
            "legacy_flood_",
            "flood (legacy, context)",
            lv.DERIVED_INDICATOR,
            "flood-gistda-repeated-2005-2016",
            "HISTORICAL_CORROBORATION: observed flooding 2005-2016; years_ge{k} = share observed "
            "flooded in >= k of 12 years; never read by interpretation or policy",
        ),
        (
            "landslide_class",
            "landslide",
            lv.DERIVED_INDICATOR,
            "landslide-susceptibility-dmr",
            "Area share of DMR susceptibility class (publisher gridcode 1..5)",
        ),
        (
            "landslide_inventory",
            "landslide",
            lv.DERIVED_INDICATOR,
            "landslide-inventory-dmr",
            "Mapped historical landslide scar points (aerial-photo interpretation; "
            "uneven coverage)",
        ),
        (
            "landslide_",
            "landslide",
            lv.DERIVED_INDICATOR,
            "landslide-susceptibility-dmr",
            "DMR susceptibility summary (assessed share, max/dominant class)",
        ),
        (
            "terrain_",
            "terrain",
            lv.DERIVED_INDICATOR,
            "dem-copernicus-glo30",
            "Support of zonal terrain statistics (pixel-equivalents / area share)",
        ),
        (
            "elev_",
            "terrain",
            lv.DERIVED_INDICATOR,
            "dem-copernicus-glo30",
            "DSM elevation (m, EGM2008), weighted statistics",
        ),
        (
            "slope_",
            "terrain",
            lv.DERIVED_INDICATOR,
            "dem-copernicus-glo30",
            "DSM slope (deg, Horn) - canopy/buildings bias; not ground slope",
        ),
        (
            "dist_",
            "waterway",
            lv.DERIVED_INDICATOR,
            "osm-overpass-aoi",
            "Distance from cell polygon to nearest mapped waterway (m)",
        ),
        (
            "waterway_",
            "waterway",
            lv.DERIVED_INDICATOR,
            "osm-overpass-aoi",
            "Length of mapped waterway inside the cell (m)",
        ),
        (
            "boundary_",
            "context",
            lv.DERIVED_INDICATOR,
            "review:boundary_uncertainty",
            "M1A.1 review context; administrative attribution caution; never decisional",
        ),
        (
            "reserve_",
            "context",
            lv.DERIVED_INDICATOR,
            "forest-reserve-rfd",
            "Legal screening context only; no hazard effect",
        ),
        (
            "park_",
            "context",
            lv.DERIVED_INDICATOR,
            "protected-gistda-mnre",
            "Legal screening context",
        ),
        (
            "sanctuary_",
            "context",
            lv.DERIVED_INDICATOR,
            "protected-gistda-mnre",
            "Legal screening context",
        ),
        (
            "requires_legal",
            "context",
            lv.DERIVED_INDICATOR,
            "forest-reserve-rfd",
            "Any reserve/park/sanctuary overlap: verify legal status",
        ),
        (
            "_state",
            "interpretation",
            lv.PROVISIONAL_HAZARD_INTERPRETATION,
            "config/hazard.yaml",
            "Provisional rule-labelled state",
        ),
        (
            "_reason",
            "interpretation",
            lv.PROVISIONAL_HAZARD_INTERPRETATION,
            "config/hazard.yaml",
            "Why the state was assigned",
        ),
        (
            "_confidence",
            "interpretation",
            lv.PROVISIONAL_HAZARD_INTERPRETATION,
            "config/hazard.yaml",
            "Confidence of the provisional state",
        ),
    ]
    rows = []
    for c in cols:
        for key, hazard, level, src, desc in rules:
            if c.startswith(key) or (key.startswith("_") and c.endswith(key)):
                rows.append(
                    {
                        "field": c,
                        "hazard": hazard,
                        "level": level.value,
                        "source": src,
                        "meaning": desc,
                    }
                )
                break
        else:
            rows.append(
                {
                    "field": c,
                    "hazard": "overall/meta",
                    "level": EvidenceLevel.PROVISIONAL_HAZARD_INTERPRETATION.value
                    if c not in ("cell_id", "coverage_fraction", "majority_pcode")
                    else "grid",
                    "source": "derived",
                    "meaning": "",
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- main


def main() -> int:
    cfg = load_hazard_config()
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    grid, _prov, aoi = base()
    log(f"grid {len(grid)} cells")

    tcache = CACHE / "terrain_cells.parquet"
    if tcache.exists():
        terrain = pd.read_parquet(tcache)
    else:
        d, m = raw_source("dem-copernicus-glo30")
        terrain = terrain_cells.terrain_indicators(
            grid,
            aoi,
            [d / a.stored_path for a in m.artifacts],
            min_support=cfg.terrain.min_support_px,
            slope_thresholds=cfg.terrain.slope_thresholds_deg,
            progress=lambda s: None,
        )
        terrain.to_parquet(tcache)
    log("terrain done")
    flood = flood_indicators(grid, aoi, cfg)
    log("flood done")
    landslide, ls_meta, _ls_paths = landslide_indicators(grid, aoi)
    log("landslide done")
    water = waterway_indicators(grid)
    log("waterway done")
    ctx = context_columns(grid)
    log("context done")

    ind = pd.concat(
        [
            grid[["cell_id", "coverage_fraction", "majority_pcode"]],
            terrain,
            flood,
            landslide,
            water,
            ctx,
        ],
        axis=1,
    )
    interp = interpret(ind, cfg)
    ind["evidence_completeness"] = interp["evidence_completeness"]
    exp = experimental_candidates(ind, cfg)
    wide = pd.concat([ind, interp.drop(columns=["evidence_completeness"])], axis=1)
    wide["clipped_area_km2"] = wide["coverage_fraction"] * CELL**2 / 1e6
    wide.to_parquet(OUT / "hazard-evidence.parquet", index=False)
    exp.insert(0, "cell_id", grid["cell_id"])
    exp.to_parquet(OUT / "experimental-exclusion-candidates.parquet", index=False)
    data_dictionary(list(wide.columns)).to_csv(OUT / "hazard-data-dictionary.csv", index=False)

    # GeoPackage: geometry + key fields (wide table stays in Parquet)
    key_cols = [
        "cell_id",
        "coverage_fraction",
        "majority_pcode",
        "overall_state",
        "overall_tier",
        "flood_tier",
        "landslide_tier",
        "terrain_tier",
        "high_hazards",
        "caution_hazards",
        "unresolved_hazards",
        "evidence_completeness",
        "interpretation_confidence",
        "flood_state",
        "flood_reason",
        "landslide_state",
        "landslide_reason",
        "terrain_state",
        "terrain_reason",
        "terrain_low_support",
        "flood_area_fraction",
        "flood_years_ge3_area_fraction",
        "flood_max_years",
        "flood_evidence_period",
        "legacy_flood_2005_2016_years_ge3_area_fraction",
        "landslide_assessed_fraction",
        "landslide_max_class",
        "landslide_dominant_class_label",
        "landslide_class5_fraction",
        "landslide_inventory_points",
        "terrain_support_px",
        "slope_p90_deg",
        "elev_median_m",
        "dist_major_waterway_m",
        "dist_any_waterway_m",
        "boundary_attribution_uncertain",
        "boundary_zone_ids",
        "reserve_area_fraction",
        "requires_legal_verification",
    ]
    gdf = gpd.GeoDataFrame(wide[key_cols], geometry=grid.geometry.values, crs=CANONICAL)
    gpkg = OUT / "hearthmap-hazard-evidence.gpkg"
    if gpkg.exists():
        gpkg.unlink()
    gdf.to_file(gpkg, layer="hazard_evidence_cells", driver="GPKG")
    exp_g = gpd.GeoDataFrame(exp, geometry=grid.geometry.values, crs=CANONICAL)
    flag_cols = [c for c in exp.columns if "@" in c]
    exp_g[exp_g[flag_cols].any(axis=1)].to_file(
        gpkg, layer="experimental_exclusion_candidates", driver="GPKG"
    )

    # ---------------- sensitivity
    groups = {p: wide["majority_pcode"] == p for p in ("TH50", "TH56", "TH57")}
    sens = []
    for tag, rule in cfg.experimental_exclusion_candidates.items():
        vals = wide[rule.field]
        if rule.thresholds:
            t = threshold_sensitivity(
                vals, rule.thresholds, area_km2=wide["clipped_area_km2"], groups=groups
            )
        else:
            t = threshold_sensitivity(
                vals,
                rule.thresholds_below,
                area_km2=wide["clipped_area_km2"],
                groups=groups,
                below=True,
            )
        t.insert(0, "candidate_rule", tag)
        t.insert(1, "field", rule.field)
        sens.append(t)
    sens = pd.concat(sens, ignore_index=True)
    sens["province"] = sens["scope"].map(PROVINCE_NAMES).fillna("AOI")
    sens["experimental"] = True
    sens.to_csv(OUT / "threshold-sensitivity.csv", index=False)

    # ---------------- statistics
    stats = {}
    for scope, m in [("AOI", pd.Series(True, index=wide.index)), *groups.items()]:
        s = wide[m]
        n = len(s)
        a = s["clipped_area_km2"]

        def share(mask, n=n, a=a):
            return {
                "cells": int(mask.sum()),
                "share_of_cells": float(mask.sum() / n),
                "area_km2": float(a[mask].sum()),
                "share_of_area": float(a[mask].sum() / a.sum()),
            }

        hi = {h: s[f"{h}_tier"] == "HIGH" for h in ("flood", "landslide", "terrain")}
        stats[scope] = {
            "cells": n,
            "complete_flood_evidence": share(s["flood_tier"] != "UNRESOLVED"),
            "complete_landslide_evidence": share(s["landslide_tier"] != "UNRESOLVED"),
            "adequate_terrain_support": share(
                s["terrain_support_px"] >= cfg.terrain.low_support_px
            ),
            "terrain_low_support": share(s["terrain_low_support"]),
            "terrain_unresolved": share(s["terrain_tier"] == "UNRESOLVED"),
            "incomplete_evidence": share(s["evidence_completeness"] < 1),
            "high_flood_evidence": share(hi["flood"]),
            "high_landslide_evidence": share(hi["landslide"]),
            "strong_terrain_concern": share(hi["terrain"]),
            "overall_state": s["overall_state"].value_counts().to_dict(),
            "multi_hazard_high_combinations": s.loc[s["high_hazards"] != "", "high_hazards"]
            .value_counts()
            .to_dict(),
            "flood_state": s["flood_state"].value_counts().to_dict(),
            "landslide_state": s["landslide_state"].value_counts().to_dict(),
            "terrain_state": s["terrain_state"].value_counts().to_dict(),
            "boundary_attribution_uncertain_cells": int(s["boundary_attribution_uncertain"].sum()),
        }
    unassessed = wide["landslide_tier"] == "UNRESOLVED"
    stats["landslide_unassessed_context"] = {
        "cells": int(unassessed.sum()),
        "median_slope_p90_deg": float(wide.loc[unassessed, "slope_p90_deg"].median()),
        "share_slope_p90_lt_10deg": float((wide.loc[unassessed, "slope_p90_deg"] < 10).mean()),
        "note": "Descriptive only: low DSM slope in unassessed cells is NOT used to resolve them.",
    }
    stats["wiang_pa_pao_zone_cells"] = {
        z: wide.loc[wide["boundary_zone_ids"].str.contains(z), "overall_state"]
        .value_counts()
        .to_dict()
        for z in ("gistda-50k-0008", "gistda-50k-0009")
    }
    stats["sources"] = {"landslide": ls_meta}
    stats["gates"] = {
        "M1A1_HUMAN_VISUAL_SIGNOFF": cfg.gates.m1a1_human_visual_signoff,
        "M1B_HUMAN_VISUAL_SIGNOFF": cfg.gates.m1b_human_visual_signoff,
        "decision_rules_active": False,
        "config_status": cfg.status,
    }
    (OUT / "hazard-statistics.json").write_text(
        json.dumps(stats, indent=2, default=str) + "\n", "utf-8"
    )

    # ---------------- provenance
    srcs = [
        source_ref(s, original_crs=c)
        for s, c in (
            ("dem-copernicus-glo30", "EPSG:4326+EPSG:3855"),
            ("flood-gistda-history", "EPSG:4326"),
            ("flood-gistda-repeated-2005-2016", "EPSG:3857"),
            ("landslide-susceptibility-dmr", "EPSG:32647"),
            ("landslide-inventory-dmr", "EPSG:32647"),
            ("osm-overpass-aoi", "EPSG:4326"),
            ("boundaries-ocha-cod-ab", "EPSG:4326"),
        )
    ]
    rec = ProvenanceRecord(
        artifact_id="m1b-hazard-evidence",
        artifact_path=gpkg.as_posix(),
        code_version=current_code_version(),
        sources=srcs,
        normalized_crs=CANONICAL,
        method="Per-cell area-based overlays (flood, DMR susceptibility classes), point counts "
        "(inventory), support-aware weighted DSM statistics (ADR-0009, Horn slope), "
        "distances/lengths to OSM waterways; provisional interpretation per "
        "config/hazard.yaml (PROVISIONAL) - categorical, no averaging.",
        spatial_resolution="500 m cells; DMR susceptibility ~1 km lattice; DSM ~30 m; "
        "flood 2011-2023 20 m (legacy 2005-2016 1:50k)",
        confidence=Confidence.LOW,
        limitations=[
            "Not a decision: no exclusions, scores or rankings. Human visual sign-off M1A.1 "
            f"{cfg.gates.m1a1_human_visual_signoff}, M1B {cfg.gates.m1b_human_visual_signoff}.",
            "Flood = observed 2011-2023 (PRIMARY_HISTORICAL_FLOOD_EVIDENCE); 2005-2016 kept as "
            "legacy_flood_* context (HISTORICAL_CORROBORATION), never interpreted.",
            "DMR susceptibility is a ~1 km product, methodology not published; coverage partial.",
            "Terrain from a DSM: slope biased by canopy/buildings.",
            "Context columns (boundary uncertainty, legal screening) never affect states.",
        ],
    ).with_step("landslide_repair", "make_valid on DMR polygons", **ls_meta["repair"])
    rec.write_sidecar(gpkg)
    log(
        json.dumps(
            {
                k: v
                for k, v in stats["AOI"].items()
                if k in ("overall_state", "multi_hazard_high_combinations")
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
