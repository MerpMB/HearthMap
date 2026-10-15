"""M1C.2: reconcile GISTDA legacy (2005-2016) and current (2011-2023) flood products.

Exact vector overlays per common year (2011-2016) using source-native yearly
flags (legacy `year2011..year2016`, current `y2011..y2016` from `detail[].freq`).
Neither product is ground truth. Within each product polygons do not overlap
(M1A / M1C.1 QA), so per-cell sums of intersection areas are union areas.

Outputs: outputs/m1c2-review/ (annual-comparison.csv, common-period-cell-
comparison.parquet, legacy-only-breakdown.csv, largest-disagreement-regions.csv,
reconciliation-summary.json) and outputs/m1c2/ (diagnostics).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import PROCESSED, PROVINCE_NAMES

from hearthmap.hazard import connected_components
from hearthmap.hazard.reconcile import (
    COMMON_YEARS,
    CURRENT,
    CURRENT_ONLY_YEARS,
    CURRENT_YEARS,
    LEGACY,
    LEGACY_ONLY_YEARS,
    LEGACY_YEARS,
    CommonPeriodClass,
    annual_accounting,
    cell_year_fractions,
    classify_common_period,
    common_year_pairs,
    distance_band,
    fraction_column,
    legacy_only_breakdown,
    temporal_flags,
)

OUT = Path("outputs/m1c2")
REVIEW = Path("outputs/m1c2-review")
EVIDENCE = Path("outputs/m1c1/evidence/hazard-evidence.parquet")
CELL = 500.0
PRESENCE_MIN = 0.01  # a product "sees" flooding in a cell-year if >= 1% of the cell
SAMPLES_PER_YEAR = 20000
SEED = 20261015
SIZE_BINS = [0, 0.01, 0.1, 1.0, np.inf]  # km2 of the source polygon
SIZE_LABELS = ["< 0.01 km2", "0.01-0.1 km2", "0.1-1 km2", ">= 1 km2"]


def log(m: str) -> None:
    print(m, flush=True)


def load():
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    prov = gpd.read_file(PROCESSED / "boundaries.gpkg", layer="province_boundaries")
    aoi = shapely.union_all(prov.geometry.values)
    shapely.prepare(aoi)
    leg = gpd.read_file(
        PROCESSED / "layers.gpkg",
        layer="flood_recurrence",
        columns=[f"year{y}" for y in LEGACY_YEARS],
    )
    cur = gpd.read_file(
        Path("data/processed/m1c1/flood.gpkg"),
        layer="flood_recurrence_2011_2023",
        columns=[f"y{y}" for y in CURRENT_YEARS],
    )
    leg = leg[shapely.intersects(aoi, leg.geometry.values)].reset_index(drop=True)
    cur = cur[shapely.intersects(aoi, cur.geometry.values)].reset_index(drop=True)
    # source-native yearly flags, kept per product (never renamed into one another)
    lf = {y: leg[f"year{y}"].to_numpy().astype(int) for y in LEGACY_YEARS}
    cf = {y: cur[f"y{y}"].to_numpy().astype(int) for y in CURRENT_YEARS}
    for name, flags in (("legacy", lf), ("current", cf)):
        bad = {y: sorted(set(v.tolist()) - {0, 1}) for y, v in flags.items()}
        if any(bad.values()):
            raise ValueError(f"{name}: yearly values outside {{0,1}}: {bad}")
    return grid, prov, aoi, leg, cur, lf, cf


def piece_pairs(pieces: np.ndarray, polys: np.ndarray):
    tree = shapely.STRtree(polys)
    ci, fi = tree.query(pieces, predicate="intersects")
    a = shapely.area(shapely.intersection(pieces[ci], polys[fi]))
    keep = a > 0
    return ci[keep], fi[keep], a[keep]


def sample_points(geoms, n, rng):
    """Area-uniform random points inside a set of (non-overlapping) polygons."""
    areas = shapely.area(geoms)
    idx = rng.choice(len(geoms), size=n, p=areas / areas.sum())
    b = shapely.bounds(geoms[idx])
    x, y = np.empty(n), np.empty(n)
    todo = np.arange(n)
    for _ in range(500):
        if not len(todo):
            break
        xs = rng.uniform(b[todo, 0], b[todo, 2])
        ys = rng.uniform(b[todo, 1], b[todo, 3])
        ok = shapely.contains_xy(geoms[idx[todo]], xs, ys)
        x[todo[ok]], y[todo[ok]] = xs[ok], ys[ok]
        todo = todo[~ok]
    keep = np.ones(n, bool)
    keep[todo] = False
    return x[keep], y[keep], idx[keep], len(todo)


def components_table(grid, ev, mask, area, label, extra, n=10):
    idx = np.flatnonzero(mask)
    if not len(idx):
        return [], {"class": label, "cells": 0}
    lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
    ca = np.bincount(lab, weights=area[idx])
    sizes = np.bincount(lab)
    cent = grid.geometry.centroid.to_crs("EPSG:4326")
    rows = []
    for rank, k in enumerate(np.argsort(ca)[::-1][:n], 1):
        m = idx[lab == k]
        w = area[m]
        rows.append(
            {
                "class": label,
                "rank": rank,
                "area_km2": round(float(ca[k]), 2),
                "cells": int(sizes[k]),
                "lon": round(float(cent.x.iloc[m].mean()), 3),
                "lat": round(float(cent.y.iloc[m].mean()), 3),
                "majority_province": PROVINCE_NAMES.get(
                    grid["majority_pcode"].iloc[m].mode().iloc[0], "?"
                ),
                "legacy_flooded_km2_2011_2016_sum": round(
                    float((extra["legacy_cp_sum"][m] * w).sum()), 2
                ),
                "current_flooded_km2_2011_2016_sum": round(
                    float((extra["current_cp_sum"][m] * w).sum()), 2
                ),
                "median_elevation_m_dsm": round(float(np.median(ev["elev_median_m"].iloc[m])), 1),
                "median_slope_p90_deg_dsm": round(float(np.median(ev["slope_p90_deg"].iloc[m])), 1),
                "median_dist_major_waterway_m": round(
                    float(np.median(ev["dist_major_waterway_m"].iloc[m])), 0
                ),
                "share_landslide_not_assessed": round(
                    float((ev["landslide_assessed_fraction"].iloc[m] < 0.5).mean()), 3
                ),
                "component_cells": ";".join(grid["cell_id"].iloc[m]) if rank == 1 else "",
            }
        )
    summary = {
        "class": label,
        "cells": len(idx),
        "area_km2": round(float(area[idx].sum()), 2),
        "components": len(ca),
        "isolated_single_cells": int((sizes == 1).sum()),
        "components_lt_1km2": int((ca < 1).sum()),
        "largest_component_km2": round(float(ca.max()), 2),
        "share_area_in_largest_10": round(float(np.sort(ca)[::-1][:10].sum() / ca.sum()), 4),
    }
    return rows, summary


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    grid, _prov, aoi, leg, cur, lf, cf = load()
    log(f"legacy {len(leg)} / current {len(cur)} polygons in AOI")
    n = len(grid)
    cov = grid["coverage_fraction"].to_numpy()
    clipped_m2 = cov * CELL**2
    area_km2 = clipped_m2 / 1e6
    pieces = grid.geometry.values.copy()
    part = np.flatnonzero(cov < 1 - 1e-9)
    pieces[part] = shapely.intersection(pieces[part], aoi)
    pcode = grid["majority_pcode"].to_numpy()

    def frac(ci, w):
        a = np.bincount(ci, weights=w, minlength=n)
        return np.divide(a, clipped_m2, out=np.zeros(n), where=clipped_m2 > 0).clip(0, 1)

    lg, cg = leg.geometry.values, cur.geometry.values
    lci, lfi, la = piece_pairs(pieces, lg)
    cci, cfi, ca = piece_pairs(pieces, cg)
    log("cell overlays done")
    # legacy x current polygon intersections (computed once, reused for every year)
    ctree = shapely.STRtree(cg)
    p, q = ctree.query(lg, predicate="intersects")
    ig = shapely.intersection(lg[p], cg[q])
    ia = shapely.area(ig)
    keep = ia > 0
    p, q, ig, ia = p[keep], q[keep], ig[keep], ia[keep]
    ici, iki, iarea = piece_pairs(pieces, ig)
    log(f"{len(p)} legacy x current polygon pairs")

    table = pd.DataFrame(
        {"cell_id": grid["cell_id"], "majority_pcode": pcode, "clipped_area_km2": area_km2}
    )
    for y in LEGACY_YEARS:
        table[fraction_column(LEGACY, y)] = frac(lci, la * lf[y][lfi])
    for y in CURRENT_YEARS:
        table[fraction_column(CURRENT, y)] = frac(cci, ca * cf[y][cfi])
    pairs = common_year_pairs(table.columns)
    assert [y for y, _, _ in pairs] == list(COMMON_YEARS)
    for y, lc, cc in pairs:
        both = lf[y][p] * cf[y][q]  # same year in both products, never across years
        inter = frac(ici, iarea * both[iki])
        parts = cell_year_fractions(table[lc].to_numpy(), table[cc].to_numpy(), inter)
        table[f"intersection_fraction_{y}"] = parts["intersection"]
        table[f"legacy_only_fraction_{y}"] = parts["legacy_only"]
        table[f"current_only_fraction_{y}"] = parts["current_only"]

    # ---------------- annual accounting (AOI exact; provinces by majority attribution)
    scopes = {"AOI": np.ones(n, bool)} | {k: pcode == k for k in ("TH50", "TH56", "TH57")}
    ann = []
    for y, lc, cc in pairs:
        for s, m in scopes.items():
            acc = annual_accounting(
                float((table[lc].to_numpy() * area_km2)[m].sum()),
                float((table[cc].to_numpy() * area_km2)[m].sum()),
                float((table[f"intersection_fraction_{y}"].to_numpy() * area_km2)[m].sum()),
            )
            ann.append(
                {
                    "year": y,
                    "scope": s,
                    "province": PROVINCE_NAMES.get(s, "AOI"),
                    **{k: round(v, 4) for k, v in acc.items()},
                }
            )
    annual = pd.DataFrame(ann)
    # all six years pooled (area-years)
    for s in scopes:
        a = annual[annual["scope"] == s]
        acc = annual_accounting(
            a["legacy_km2"].sum(), a["current_km2"].sum(), a["intersection_km2"].sum()
        )
        ann.append(
            {
                "year": "2011-2016 (area-years)",
                "scope": s,
                "province": PROVINCE_NAMES.get(s, "AOI"),
                **{k: round(v, 4) for k, v in acc.items()},
            }
        )
    annual = pd.DataFrame(ann)
    annual.to_csv(REVIEW / "annual-comparison.csv", index=False)
    # whole-record context, each product with its own years
    native = {
        "legacy_km2_by_year": {
            y: round(float((table[fraction_column(LEGACY, y)] * area_km2).sum()), 2)
            for y in LEGACY_YEARS
        },
        "current_km2_by_year": {
            y: round(float((table[fraction_column(CURRENT, y)] * area_km2).sum()), 2)
            for y in CURRENT_YEARS
        },
    }

    # ---------------- per-cell classes
    lcp = table[[fraction_column(LEGACY, y) for y in COMMON_YEARS]].set_axis(COMMON_YEARS, axis=1)
    ccp = table[[fraction_column(CURRENT, y) for y in COMMON_YEARS]].set_axis(COMMON_YEARS, axis=1)
    lpre = table[[fraction_column(LEGACY, y) for y in LEGACY_ONLY_YEARS]]
    cpost = table[[fraction_column(CURRENT, y) for y in CURRENT_ONLY_YEARS]]
    table["common_period_class"] = classify_common_period(lcp, ccp, presence_min=PRESENCE_MIN)
    table["temporal_flags"] = temporal_flags(lpre, lcp, ccp, cpost, presence_min=PRESENCE_MIN)
    inter_sum = table[[f"intersection_fraction_{y}" for y in COMMON_YEARS]].sum(axis=1)
    union_sum = lcp.sum(axis=1) + ccp.sum(axis=1) - inter_sum
    table["common_period_cell_iou"] = np.where(
        union_sum > 0, inter_sum / union_sum.where(union_sum > 0, 1), np.nan
    )
    table["legacy_common_years_seen"] = (lcp >= PRESENCE_MIN).sum(axis=1)
    table["current_common_years_seen"] = (ccp >= PRESENCE_MIN).sum(axis=1)
    table["presence_min_fraction"] = PRESENCE_MIN
    table.to_parquet(REVIEW / "common-period-cell-comparison.parquet", index=False)
    cls = table["common_period_class"].to_numpy()
    class_rows = []
    for s, m in scopes.items():
        for c in CommonPeriodClass:
            sel = m & (cls == c.value)
            class_rows.append(
                {
                    "scope": s,
                    "province": PROVINCE_NAMES.get(s, "AOI"),
                    "common_period_class": c.value,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area_km2[sel].sum()), 2),
                }
            )
    classes = pd.DataFrame(class_rows)
    classes.to_csv(OUT / "common-period-classes.csv", index=False)
    # presence-threshold sensitivity of the classes (AOI)
    class_sens = {
        str(pm): pd.Series(classify_common_period(lcp, ccp, presence_min=pm))
        .value_counts()
        .to_dict()
        for pm in (1e-9, 0.01, 0.05, 0.10)
    }
    tflags = pd.Series(table["temporal_flags"]).str.split("|").explode()
    tflag_counts = tflags[tflags != ""].value_counts().to_dict()
    cross = pd.crosstab(table["common_period_class"], table["temporal_flags"].replace("", "(none)"))

    # ---------------- the 6,387 legacy-only cells (M1C.1 definition: any fraction > 0)
    l_any = (table[[fraction_column(LEGACY, y) for y in LEGACY_YEARS]] > 0).any(axis=1)
    c_any = (table[[fraction_column(CURRENT, y) for y in CURRENT_YEARS]] > 0).any(axis=1)
    lo = (l_any & ~c_any).to_numpy()
    pre_any = (lpre > 0).any(axis=1).to_numpy()
    com_any = (lcp > 0).any(axis=1).to_numpy()
    br = legacy_only_breakdown(pre_any[lo], com_any[lo])
    lob = pd.DataFrame(
        {
            "cell_id": table["cell_id"][lo],
            "majority_pcode": pcode[lo],
            "area_km2": area_km2[lo],
            "breakdown": br,
            "legacy_max_fraction_any_year": table.loc[
                lo, [fraction_column(LEGACY, y) for y in LEGACY_YEARS]
            ].max(axis=1),
        }
    )
    lob_rows = []
    for s, m in scopes.items():
        mm = m[lo]
        for b in ("ONLY_2005_2010", "ONLY_2011_2016", "BOTH_2005_2010_AND_2011_2016"):
            sel = mm & (br == b)
            lob_rows.append(
                {
                    "scope": s,
                    "province": PROVINCE_NAMES.get(s, "AOI"),
                    "breakdown": b,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(lob["area_km2"].to_numpy()[sel].sum()), 2),
                    "median_legacy_max_fraction": round(
                        float(np.median(lob["legacy_max_fraction_any_year"].to_numpy()[sel])), 4
                    )
                    if sel.any()
                    else None,
                }
            )
    lob_tab = pd.DataFrame(lob_rows)
    lob_tab.to_csv(REVIEW / "legacy-only-breakdown.csv", index=False)
    # per legacy-only cell, which years the legacy product flagged
    year_hits = {
        y: int((table.loc[lo, fraction_column(LEGACY, y)] > 0).sum()) for y in LEGACY_YEARS
    }

    # ---------------- polygon-level: features one product draws that the other misses
    poly_rows = []
    for y in COMMON_YEARS:
        both = lf[y][p] * cf[y][q]
        lov = np.bincount(p, weights=ia * both, minlength=len(leg))
        cov_ = np.bincount(q, weights=ia * both, minlength=len(cur))
        for name, flags, ov, geoms in ((LEGACY, lf[y], lov, lg), (CURRENT, cf[y], cov_, cg)):
            on = flags == 1
            if not on.any():
                poly_rows.append({"year": y, "product": name, "polygons": 0})
                continue
            pa = shapely.area(geoms[on])
            share = ov[on] / pa
            missed = share <= 1e-6
            for lbl, lo_, hi in zip(SIZE_LABELS, SIZE_BINS[:-1], SIZE_BINS[1:], strict=True):
                inb = (pa / 1e6 >= lo_) & (pa / 1e6 < hi)
                poly_rows.append(
                    {
                        "year": y,
                        "product": name,
                        "size_bin": lbl,
                        "polygons": int(inb.sum()),
                        "area_km2": round(float(pa[inb].sum() / 1e6), 2),
                        "polygons_with_no_overlap": int((inb & missed).sum()),
                        "area_km2_with_no_overlap": round(float(pa[inb & missed].sum() / 1e6), 2),
                        "area_weighted_overlap_share": round(
                            float((ov[on][inb]).sum() / pa[inb].sum()), 4
                        )
                        if inb.any()
                        else None,
                    }
                )
    pd.DataFrame(poly_rows).to_csv(OUT / "polygon-overlap-by-size.csv", index=False)

    # ---------------- edge / interior diagnostic (area-uniform point samples)
    srows = []
    sample_drop = 0
    for y in COMMON_YEARS:
        for name, geoms, flags, other_geoms, other_flags in (
            (LEGACY, lg, lf[y], cg, cf[y]),
            (CURRENT, cg, cf[y], lg, lf[y]),
        ):
            on = np.flatnonzero(flags == 1)
            if not len(on):
                continue
            x, yy, k, dropped = sample_points(geoms[on], SAMPLES_PER_YEAR, rng)
            sample_drop += dropped
            pts = shapely.points(x, yy)
            inside_aoi = shapely.contains_xy(aoi, x, yy)
            pts, k = pts[inside_aoi], k[inside_aoi]
            oth = np.flatnonzero(other_flags == 1)
            if len(oth):
                _, d = shapely.STRtree(other_geoms[oth]).query_nearest(
                    pts, return_distance=True, all_matches=False
                )
            else:
                d = np.full(len(pts), np.inf)
            src_area_km2 = shapely.area(geoms[on][k]) / 1e6
            srows.append(
                pd.DataFrame(
                    {
                        "year": y,
                        "product": name,
                        "distance_m": d,
                        "source_polygon_km2": src_area_km2,
                    }
                )
            )
    samp = pd.concat(srows, ignore_index=True)
    samp["agrees"] = samp["distance_m"] == 0
    dis = samp[~samp["agrees"]].copy()
    dis["band"] = distance_band(dis["distance_m"].to_numpy())
    dis["size_bin"] = pd.cut(
        dis["source_polygon_km2"], SIZE_BINS, labels=SIZE_LABELS, right=False
    ).astype(str)
    edge = (
        dis.groupby(["product", "band"])
        .size()
        .rename("points")
        .reset_index()
        .assign(
            share_of_disagreement=lambda d: (
                d["points"] / d.groupby("product")["points"].transform("sum")
            )
        )
    )
    edge.to_csv(OUT / "disagreement-distance-bands.csv", index=False)
    edge_year = dis.groupby(["product", "year", "band"]).size().rename("points").reset_index()
    edge_year.to_csv(OUT / "disagreement-distance-bands-by-year.csv", index=False)
    size_tab = (
        dis.groupby(["product", "size_bin"])
        .size()
        .rename("points")
        .reset_index()
        .assign(share=lambda d: d["points"] / d.groupby("product")["points"].transform("sum"))
    )
    size_tab.to_csv(OUT / "disagreement-by-source-polygon-size.csv", index=False)
    agree_share = samp.groupby(["product", "year"])["agrees"].mean().round(4)

    # ---------------- clusters + examples
    ev = pd.read_parquet(EVIDENCE).set_index("cell_id").loc[grid["cell_id"]]
    extra = {
        "legacy_cp_sum": lcp.to_numpy().sum(axis=1),
        "current_cp_sum": ccp.to_numpy().sum(axis=1),
    }
    reg_rows, reg_sum = [], []
    for c in CommonPeriodClass:
        if c == CommonPeriodClass.AGREEMENT_NO_FLOOD:
            continue
        r, s = components_table(grid, ev, cls == c.value, area_km2, c.value, extra)
        reg_rows += r
        reg_sum.append(s)
    regions = pd.DataFrame(reg_rows)
    regions.drop(columns=["component_cells"]).to_csv(
        REVIEW / "largest-disagreement-regions.csv", index=False
    )
    examples = regions[regions["rank"] == 1][["class", "component_cells"]]
    examples.to_csv(OUT / "example-components.csv", index=False)

    # ---------------- recurrence: common-period counts, each product on the same 6 years
    rec_rows = []
    for k_ in range(1, 7):
        lk = np.bincount(
            lci, weights=la * (sum(lf[y][lfi] for y in COMMON_YEARS) >= k_), minlength=n
        )
        ck = np.bincount(
            cci, weights=ca * (sum(cf[y][cfi] for y in COMMON_YEARS) >= k_), minlength=n
        )
        rec_rows.append(
            {
                "min_years_of_6_common": k_,
                "legacy_km2": round(float(lk.sum() / 1e6), 2),
                "current_km2": round(float(ck.sum() / 1e6), 2),
            }
        )
    rec_common = pd.DataFrame(rec_rows)
    rec_common.to_csv(OUT / "recurrence-common-period.csv", index=False)
    # current full-record sensitivity: years (k of 13) x cell fraction, separate dimensions
    yrs_total = sum(cf[y][cfi] for y in CURRENT_YEARS)
    sens = []
    for k_ in range(1, 6):
        fk = frac(cci, ca * (yrs_total >= k_))
        for f in (0.05, 0.10, 0.25, 0.50):
            for s, m in scopes.items():
                sel = m & (fk >= f)
                sens.append(
                    {
                        "min_years_of_13": k_,
                        "min_cell_fraction": f,
                        "scope": s,
                        "province": PROVINCE_NAMES.get(s, "AOI"),
                        "cells": int(sel.sum()),
                        "area_km2": round(float(area_km2[sel].sum()), 2),
                        "share_of_area": round(float(area_km2[sel].sum() / area_km2[m].sum()), 4),
                    }
                )
    pd.DataFrame(sens).to_csv(OUT / "recurrence-sensitivity-current.csv", index=False)

    a6 = annual[(annual["scope"] == "AOI") & (annual["year"].astype(str).str.len() == 4)]
    summary = {
        "presence_min_fraction": PRESENCE_MIN,
        "common_years": list(COMMON_YEARS),
        "native_fields": {
            "legacy": "year2005..year2016 int32 {0,1}; flood_freq = sum (verified 214,350/214,350)",
            "current": "y2011..y2023 from detail[].freq int {0,1}; total = sum (verified)",
        },
        "polygons_in_aoi": {"legacy": len(leg), "current": len(cur)},
        "legacy_current_polygon_pairs": len(p),
        "annual_aoi": a6.to_dict("records"),
        "pooled_aoi": annual[
            (annual["scope"] == "AOI") & (annual["year"] == "2011-2016 (area-years)")
        ].to_dict("records"),
        "native_annual_km2": native,
        "legacy_larger_every_common_year": bool((a6["legacy_km2"] > a6["current_km2"]).all()),
        "common_period_classes_aoi": classes[classes["scope"] == "AOI"].to_dict("records"),
        "class_presence_sensitivity_cells": class_sens,
        "temporal_flag_cells": {k: int(v) for k, v in tflag_counts.items()},
        "class_by_temporal_flag_cells": {
            a: {b: int(cross.loc[a, b]) for b in cross.columns} for a in cross.index
        },
        "legacy_only_cells_m1c1_definition": int(lo.sum()),
        "legacy_only_breakdown_aoi": lob_tab[lob_tab["scope"] == "AOI"].to_dict("records"),
        "legacy_only_cells_flagged_by_year": year_hits,
        "edge_bands": edge.to_dict("records"),
        "sample": {
            "points_per_product_year": SAMPLES_PER_YEAR,
            "seed": SEED,
            "points_dropped_unplaceable": sample_drop,
            "points_used": len(samp),
        },
        "point_agreement_by_product_year": {
            f"{a}:{b}": float(v) for (a, b), v in agree_share.items()
        },
        "disagreement_clusters": reg_sum,
        "recurrence_common_period_km2": rec_common.to_dict("records"),
    }
    (REVIEW / "reconciliation-summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", "utf-8"
    )
    log(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "annual_aoi",
                    "legacy_larger_every_common_year",
                    "legacy_only_breakdown_aoi",
                    "temporal_flag_cells",
                    "edge_bands",
                    "recurrence_common_period_km2",
                )
            },
            indent=1,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
