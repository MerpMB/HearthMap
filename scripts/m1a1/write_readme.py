"""Write outputs/m1a-review/README.md and the committed copy
docs/research/m1a1-spatial-qa-report.md from the computed QA results."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("outputs/m1a-review")
DOC = Path("docs/research/m1a1-spatial-qa-report.md")


def pct(x: float, d: int = 1) -> str:
    return f"{100 * x:.{d}f}%"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def build(image_prefix: str) -> str:
    s = json.loads((OUT / "qa-summary.json").read_text("utf-8"))
    sizes = json.loads((OUT / "file-sizes.json").read_text("utf-8"))
    z = pd.read_csv(OUT / "boundary-disagreements.csv")
    ctx = pd.read_csv(OUT / "boundary-uncertainty-context.csv")
    fdist = pd.read_csv(OUT / "forest-coverage-summary.csv")
    combos = pd.read_csv(OUT / "forest-category-overlaps.csv")
    mask = s["boundaries"]["uncertainty_mask"]
    fr = s["flood_repair"]
    dem = s["dem_edge_cells"]
    img = lambda n: f"![{n}]({image_prefix}{n})"  # noqa: E731

    mat = z[z["material"]]
    g = mat[mat["reference_source"] == "gistda-50k"]
    gb = mat[mat["reference_source"] == "geoboundaries"]
    g_corr = g[g["corroboration_fraction"] >= 0.5]
    top = g.head(12)[
        [
            "zone_id",
            "province",
            "nearest_district",
            "other_side",
            "border_type",
            "max_offset_m",
            "median_offset_m",
            "symmetric_difference_area_km2",
            "affected_grid_cells",
            "corroboration_fraction",
            "provisional_class",
        ]
    ].copy()
    top["max_offset_m"] = top["max_offset_m"].round(0).astype(int)
    top["median_offset_m"] = top["median_offset_m"].round(0).astype(int)
    top["symmetric_difference_area_km2"] = top["symmetric_difference_area_km2"].round(2)
    top["corroboration_fraction"] = top["corroboration_fraction"].round(2)
    by_side = (
        g.groupby("other_side")["symmetric_difference_area_km2"]
        .sum()
        .sort_values(ascending=False)
        .round(1)
    )

    fd = fdist.pivot(index="threshold", columns="scope", values="share_of_cells")
    fd = fd.loc[fdist["threshold"].unique(), ["AOI", "TH50", "TH56", "TH57"]]
    fd = (
        fd.map(pct)
        .reset_index()
        .rename(
            columns={
                "threshold": "reserve_area_fraction",
                "TH50": "Chiang Mai",
                "TH56": "Phayao",
                "TH57": "Chiang Rai",
            }
        )
    )
    aoi_rows = fdist[fdist["scope"] == "AOI"].iloc[0]
    aoi_f = fdist[fdist["scope"] == "AOI"].set_index("threshold")["cells"]
    partial_share = (aoi_f["> 0"] - aoi_f[">= 0.9"]) / aoi_f["> 0"]
    rp = combos[
        (combos["scope"] == "AOI")
        & (combos["combination"] == "reserve+park")
        & combos["basis"].str.startswith("area")
    ]["share_of_scope"].iloc[0]
    ca = combos[(combos["scope"] == "AOI") & combos["basis"].str.startswith("area")][
        ["combination", "area_km2", "share_of_scope"]
    ].copy()
    ca["area_km2"] = ca["area_km2"].round(1)
    ca["share_of_scope"] = ca["share_of_scope"].map(pct)
    cc = combos[combos["basis"].str.startswith("cells")][["combination", "cells", "share_of_cells"]]
    cc = cc.assign(
        share_of_cells=cc["share_of_cells"].map(pct),
        cells=cc["cells"].astype(int).map("{:,}".format),
    )

    grid = pd.DataFrame(s["grid"]).T.reset_index().rename(columns={"index": "scope"})
    grid["coverage_difference_m2"] = (grid["coverage_difference_km2"].astype(float) * 1e6).round(4)
    grid["tolerance_m2"] = (grid["tolerance_km2"].astype(float) * 1e6).round(1)
    grid = grid[
        [
            "scope",
            "n_cells",
            "raw_cell_footprint_area_km2",
            "clipped_coverage_area_km2",
            "boundary_area_km2",
            "edge_overhang_area_km2",
            "coverage_difference_m2",
            "tolerance_m2",
            "invariant_ok",
        ]
    ]
    ctx_t = ctx.copy()
    for c in (
        "share_reserve_ge_0_9",
        "share_park_gt_0",
        "share_observed_flood_gt_0",
        "median_slope_gt15_fraction",
    ):
        ctx_t[c] = ctx_t[c].map(pct)
    ctx_t["median_elev_mean_m"] = ctx_t["median_elev_mean_m"].round(0).astype(int)
    ctx_t["median_dist_major_road_m"] = ctx_t["median_dist_major_road_m"].round(0).astype(int)

    cm = g[g["province"] == "TH50"].copy()
    cm["edge"] = np.where(
        cm["border_type"] == "international",
        "International border (Myanmar)",
        "Border with " + cm["other_side"].astype(str),
    )
    cm_rows = []
    for edge, grp in cm.groupby("edge"):
        grp = grp.sort_values("symmetric_difference_area_km2", ascending=False)
        corr_ids = grp[grp["corroboration_fraction"] >= 0.5]["zone_id"].str[-4:].tolist()
        uncorr_ids = grp[grp["corroboration_fraction"] < 0.5]["zone_id"].str[-4:].tolist()
        cm_rows.append(
            {
                "edge": edge,
                "zones": len(grp),
                "area_km2": round(grp["symmetric_difference_area_km2"].sum(), 1),
                "max_offset_km": round(grp["max_offset_m"].max() / 1000, 1),
                "corroborated (>=50%)": ", ".join(corr_ids[:6])
                + (" ..." if len(corr_ids) > 6 else ""),
                "not corroborated": ", ".join(uncorr_ids[:6])
                + (" ..." if len(uncorr_ids) > 6 else ""),
            }
        )
    cm_edges = md_table(pd.DataFrame(cm_rows).sort_values("area_km2", ascending=False))
    w = (
        g[(g["border_type"] == "aoi_internal") & (g["province"] == "TH50")]
        .sort_values("symmetric_difference_area_km2", ascending=False)
        .iloc[0]
    )
    wpp = (
        f"`{w['zone_id']}`, {w['symmetric_difference_area_km2']:.1f} km², "
        f"{w['kind'].replace('_', ' ')} for Chiang Mai, max offset "
        f"{w['max_offset_m'] / 1000:.1f} km, corroboration {w['corroboration_fraction']:.0%}"
    )

    lines = []
    lines += [
        "# HearthMap M1A.1 — Human spatial QA review",
        "",
        f"Code version `{s['code_version']}`. **Descriptive QA only** — no boundary was "
        "modified, nothing is scored, ranked or excluded. Every review layer carries "
        "`review_only = true`, `decision_use = NONE`; overlays refuse such layers and scores "
        "cannot cite `review:` sources.",
        "",
        "Figures are PNG excerpts readable without QGIS; the optional "
        "`hearthmap-m1a-review.gpkg` holds review-only subsets for anyone who wants to pan around.",
        "",
        img("overview.png"),
        "",
    ]

    # ---------------- boundaries
    lines += [
        "## 1. Boundary disagreements",
        "",
        "Zones = polygon parts of the symmetric difference between COD-AB (PRIMARY, unchanged) "
        "and each reference, per province. `max_offset_m` = largest distance from the zone "
        "outline to the COD-AB boundary (50 m sampling). A zone is **material** when that "
        f"offset is ≥ {s['boundaries']['material_offset_threshold_m']:.0f} m (half a grid cell: "
        "enough to change an edge cell's majority province). `corroboration_fraction` = share "
        "of the zone's alternative edge (the reference's own line) lying within 250 m of the *other* "
        "reference's line - i.e. whether both references follow the same alternative boundary. "
        "Classes are provisional, rule-labelled descriptions, not causes.",
        "",
        f"- GISTDA 1:50k: **{len(g)} material zones, {g['symmetric_difference_area_km2'].sum():.1f} km²**; "
        f"{len(g_corr)} of them ({g_corr['symmetric_difference_area_km2'].sum():.1f} km²) are "
        "corroborated ≥ 50% by geoBoundaries — i.e. both independent references place the line "
        "elsewhere than COD-AB.",
        f"- geoBoundaries (OSM 2017): **{len(gb)} material zones, "
        f"{gb['symmetric_difference_area_km2'].sum():.1f} km²**; only "
        f"{(gb['corroboration_fraction'] >= 0.5).sum()} zones "
        f"({gb[gb['corroboration_fraction'] >= 0.5]['symmetric_difference_area_km2'].sum():.1f} km²) "
        "are corroborated by GISTDA. Most of its divergence is unique to geoBoundaries.",
        "",
        "GISTDA material-zone area by what lies on the other side of the edge (km²):",
        "",
        md_table(by_side.reset_index().rename(columns={"symmetric_difference_area_km2": "km2"})),
        "",
        "Largest GISTDA zones (full table: `boundary-disagreements.csv`):",
        "",
        md_table(top),
        "",
    ]
    lines += [
        "### Chiang Mai",
        "",
        img("chiang-mai-boundary-disagreement.png"),
        "",
        "The Chiang Mai statistics (p95 offset 1.1 km, max 4.9 km vs GISTDA) come from a "
        "small number of **edge blocks**, not from a systematic shift: the median offset stays "
        "~37 m. GISTDA material zones in Chiang Mai, grouped by edge "
        "(corroboration = share of the GISTDA line within 250 m of the geoBoundaries line):",
        "",
        cm_edges,
        "",
        f"The largest disagreement that changes *which AOI province* an area belongs to is on "
        f"the Chiang Mai / Chiang Rai edge near Wiang Pa Pao ({wpp}).",
        "",
        "No evidence was found to test a *vintage* explanation (no dated boundary editions are "
        "available), so no zone is classed LIKELY_SOURCE_VINTAGE_DIFFERENCE.",
        "",
        "### Chiang Rai and Phayao",
        "",
        img("chiang-rai-boundary-review.png"),
        "",
        img("phayao-boundary-review.png"),
        "",
    ]
    lines += [
        "### Boundary uncertainty mask (`boundary_uncertainty_review`)",
        "",
        "| Reference | Cells | Share of AOI cells | Clipped area of affected cells km² | Share of AOI area | Cells by majority province |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for k in ("gistda_50k", "geoboundaries", "any_reference"):
        m = mask[k]
        lines.append(
            f"| {k} | {m['cells']:,} | {pct(m['share_of_aoi_cells'], 2)} | "
            f"{m['clipped_area_of_affected_cells_km2']:.1f} | {pct(m['share_of_aoi_area'], 2)} | "
            f"{m['by_province_cells']} |"
        )
    lines += [
        "",
        "What kind of land the uncertainty cells are (context only, `boundary-uncertainty-context.csv`):",
        "",
        md_table(ctx_t),
        "",
        "**Materiality for HearthMap.** The GISTDA-flagged cells (0.9% of the AOI) are "
        "mostly steep, high, reserve-covered border terrain that later hazard/legal screening "
        "will treat cautiously anyway. They matter where province attribution matters - "
        "planning regulation and administrative statistics - e.g. on internal edges such as "
        "Wiang Pa Pao (Chiang Mai/Chiang Rai) or Saraphi (Chiang Mai/Lamphun). The mask therefore remains a *caution flag on "
        "administrative attribution*, never a hazard input. geoBoundaries is too divergent "
        "(and only 2017 OSM) to drive any caution by itself.",
        "",
    ]

    # ---------------- forest
    lines += [
        "## 2. Reserve-forest coverage (actual area, not touched cells)",
        "",
        img("forest-coverage-overview.png"),
        "",
        "`reserve_area_fraction` = area(RFD reserve ∩ cell ∩ AOI) / area(cell ∩ AOI). "
        f"RFD reserve polygons cover **{aoi_rows['reserve_area_km2_in_scope']:,.0f} km² = "
        f"{pct(aoi_rows['reserve_area_km2_in_scope'] / aoi_rows['scope_area_km2'])} of the AOI area**. "
        "The distribution is strongly bimodal: most cells are either (almost) fully inside a "
        f"reserve or not at all; {pct(partial_share)} of touched cells have a fraction "
        "between 0 and 0.9.",
        "",
        md_table(fd),
        "",
        img("forest-overlap-examples.png"),
        "",
        "### Overlapping legal-screening categories (exact combinations, no double counting)",
        "",
        md_table(ca),
        "",
        "Cells (category present with fraction > 0):",
        "",
        md_table(cc),
        "",
        f"Reserve and national-park polygons overlap on {pct(rp)} of the AOI. This is "
        "consistent with parks having been declared over reserve land while the RFD 2019 "
        "layer still draws both - not verified here. These are "
        "descriptive combinations; they must not be summed into a severity score. Rule "
        "unchanged: RFD/park/sanctuary geometry is SCREENING / REQUIRES_LEGAL_VERIFICATION "
        "and cannot create a definitive exclusion.",
        "",
    ]

    # ---------------- flood
    lines += [
        "## 3. Flood geometry repair audit",
        "",
        img("flood-overview.png"),
        "",
        f"- Repaired: **{fr['repair_count']} of {fr['total_features']:,} features "
        f"({pct(fr['repair_rate'], 3)})**; reason: {fr['validity_reasons']}.",
        f"- Geometry types: {fr['geometry_type_changes']} (no type changes); component count "
        f"changed for {fr['component_count_changed']}; empty after repair: "
        f"{fr['empty_after_repair']}.",
        f"- |area delta|: median {fr['median_abs_area_delta_m2']:.1e} m², p95 "
        f"{fr['p95_abs_area_delta_m2']:.1e} m², max {fr['max_abs_area_delta_m2']:.1e} m² "
        f"(max {fr['max_abs_percent_delta']:.1e} %). Total {fr['total_abs_area_delta_km2']:.1e} km².",
        f"- Replay vs M1A layer: max area difference {fr['max_abs_m1a_vs_audit_area_delta_m2']:.1e} m².",
        "- Interpretation: every invalidity is a ring touching itself at a single vertex "
        "(zero-area self-intersection). `make_valid` only re-expressed topology; **shapes did "
        "not materially change**. 'Before' areas are diagnostic (shoelace on invalid rings).",
        "",
        img("flood-repair-examples.png"),
        "",
        "Flood source roles: `flood-gistda-repeated-2005-2016` = TEMPORARY_HISTORICAL_EVIDENCE; "
        "`flood-gistda-history` (2011–2023) = metadata_verified, data NOT verified, "
        "BLOCKED_CREDENTIAL_REQUIRED, intended PRIMARY_HISTORICAL_FLOOD_EVIDENCE. Catalogue "
        "example API keys were not used.",
        "",
    ]

    # ---------------- grid
    lines += [
        "## 4. Grid area accounting",
        "",
        "Invariant: Σ(cell area × coverage_fraction) = boundary area within "
        "1 m² + 1e-9 × boundary area.",
        "",
        md_table(grid),
        "",
    ]

    # ---------------- DEM
    lines += [
        "## 5. Terrain preview QA and the 120 DEM edge cells",
        "",
        img("terrain-review.png"),
        "",
        "Rivers and major roads (OSM, independent) run along DSM valleys in all four windows; "
        "no raster offset, striping or tile-seam artifacts are visible at 500 m.",
        "",
        f"- {dem['cells_without_pixel_centre']} cells have no DEM pixel centre; all are partial "
        f"edge cells: coverage ≤ {pct(dem['coverage_fraction_max'], 2)} (median "
        f"{pct(dem['coverage_fraction_median'], 2)}), clipped area ≤ "
        f"{dem['clipped_area_m2_max']:,.0f} m² (median {dem['clipped_area_m2_median']:,.0f} m²), "
        f"mean width ≤ {dem['clipped_mean_width_m_max']:.0f} m; total "
        f"{dem['clipped_area_total_m2'] / 1e6:.3f} km².",
        "- Cause: pixel centres lie on a ~29 × 31 m lattice; a sliver narrower than that lattice "
        "can fall between centres. They were not filled.",
        f"- {dem['partial_cells_smaller_than_2_pixels']} partial cells are smaller than two "
        f"pixels; {dem['of_which_without_pixel']} of them have none.",
        "- Recommended policy (ADR-0009, proposed): weighted raster overlap with recorded "
        "support; UNKNOWN when support < 1 pixel; LOW_SUPPORT flag below ~10 pixels; never "
        "nearest-pixel filling for constraints or scores.",
        "",
    ]

    lines += ["## 6. Files", "", "| File | Bytes |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in sizes.items()]
    lines += [
        "",
        "Review GeoPackage layers: province_boundaries, reference_boundaries, "
        "boundary_disagreement_zones, boundary_uncertainty_review, forest_review, "
        "flood_repair_review, selected_grid_cells (all except province_boundaries are "
        "review_only).",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    (OUT / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1a-review/").replace(
            "# HearthMap M1A.1 — Human spatial QA review",
            "# HearthMap M1A.1 — Human spatial QA report\n\n> Committed copy of "
            "`outputs/m1a-review/README.md` (images live in the untracked review folder; "
            "regenerate with `python scripts/m1a1/build_review.py && "
            "python scripts/m1a1/write_readme.py`).",
        ),
        "utf-8",
    )
    print("written")


if __name__ == "__main__":
    main()
