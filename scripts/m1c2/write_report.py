"""Write outputs/m1c2-review/README.md and docs/research/m1c2-flood-reconciliation-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.qa import load_human_qa

OUT = Path("outputs/m1c2")
REVIEW = Path("outputs/m1c2-review")
DOC = Path("docs/research/m1c2-flood-reconciliation-report.md")
FINDINGS = Path("docs/research/m1c2-findings.md")
TITLE = "# HearthMap M1C.2 - Flood record reconciliation (GISTDA 2005-2016 vs 2011-2023)"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += [
        "| " + " | ".join(str(v).replace("|", r"\|") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join(out)


def build(prefix: str) -> str:
    s = json.loads((REVIEW / "reconciliation-summary.json").read_text("utf-8"))
    ann = pd.read_csv(REVIEW / "annual-comparison.csv")
    lob = pd.read_csv(REVIEW / "legacy-only-breakdown.csv")
    reg = pd.read_csv(REVIEW / "largest-disagreement-regions.csv")
    edge = pd.read_csv(OUT / "disagreement-distance-bands.csv")
    size = pd.read_csv(OUT / "disagreement-by-source-polygon-size.csv")
    poly = pd.read_csv(OUT / "polygon-overlap-by-size.csv")
    rc = pd.read_csv(OUT / "recurrence-common-period.csv")
    rs = pd.read_csv(OUT / "recurrence-sensitivity-current.csv")
    qa = load_human_qa()

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    cols = [
        "year",
        "province",
        "legacy_km2",
        "current_km2",
        "intersection_km2",
        "legacy_only_km2",
        "current_only_km2",
        "union_km2",
        "intersection_over_union",
        "legacy_captured_by_current",
        "current_captured_by_legacy",
    ]
    a = ann[cols].copy()
    for c in cols[2:]:
        a[c] = a[c].round(3)
    classes = pd.DataFrame(s["common_period_classes_aoi"]).drop(columns=["scope", "province"])
    sens = pd.DataFrame(s["class_presence_sensitivity_cells"]).fillna(0).astype(int)
    sens.index.name = "class \\ presence threshold"
    cross = pd.DataFrame(s["class_by_temporal_flag_cells"]).T
    cross.index.name = "common-period class \\ temporal flags"
    nat = pd.DataFrame(s["native_annual_km2"]).rename_axis("year").reset_index()
    edge["share_of_disagreement"] = (100 * edge["share_of_disagreement"]).round(2)
    size["share"] = (100 * size["share"]).round(1)
    rs_tab = rs[rs["scope"] == "AOI"].pivot_table(
        index="min_years_of_13", columns="min_cell_fraction", values="share_of_area"
    )
    rs_tab = (100 * rs_tab).round(2).reset_index()
    rs_tab.columns = ["min years flooded (of 13)"] + [
        f">= {c:g} of cell (% AOI)" for c in rs_tab.columns[1:]
    ]
    gates = pd.DataFrame(
        [{"gate": g.upper(), "status": r.status} for g, r in qa.gates.items()]
        + [
            {
                "gate": "M1C1_HUMAN_VISUAL_SIGNOFF (outputs/m1c1-review)",
                "status": "NOT RECORDED (no review reported)",
            },
            {
                "gate": "M1C2_HUMAN_VISUAL_SIGNOFF (outputs/m1c2-review)",
                "status": "NOT RECORDED (no review reported)",
            },
        ]
    )
    files = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name not in ("README.md", "file-sizes.json")
    }
    files |= {f"m1c2/{p.name}": p.stat().st_size for p in sorted(OUT.iterdir()) if p.is_file()}

    lines = [
        TITLE,
        "",
        "Descriptive reconciliation of two GISTDA observed-flood products. Roles: 2011-2023 = "
        "`PRIMARY_CURRENT_PRODUCT`, 2005-2016 = `LEGACY_COMPARISON_PRODUCT`; neither is ground "
        "truth. No hazard-policy profile is selected and no policy change is implemented.",
        "",
        f"Native yearly fields: legacy - {s['native_fields']['legacy']}; current - "
        f"{s['native_fields']['current']}. Polygons in the AOI: legacy "
        f"{s['polygons_in_aoi']['legacy']:,}, current {s['polygons_in_aoi']['current']:,}. "
        f"Cell-year presence = flooded share >= {s['presence_min_fraction']:.0%} of the cell "
        "(sensitivity below). Province rows use majority-province cell attribution.",
        "",
        FINDINGS.read_text("utf-8"),
        "",
        "## Annual comparison (same year in both products)",
        "",
        table(a),
        "",
        img("year-by-year-agreement.png"),
        "",
        "Each product on its own years (km2, AOI):",
        "",
        table(nat.fillna("")),
        "",
        "## Per-cell common-period classes (AOI)",
        "",
        table(classes),
        "",
        "Presence-threshold sensitivity (cells):",
        "",
        table(sens.reset_index()),
        "",
        "Temporal flags are separate from the common-period class (cells):",
        "",
        table(cross.reset_index()),
        "",
        img("common-period-agreement.png"),
        "",
        img("legacy-only-common-period.png"),
        "",
        img("current-only-common-period.png"),
        "",
        "## The 6,387 legacy-only cells (M1C.1 definition)",
        "",
        table(lob),
        "",
        "Legacy-only cells flagged per legacy year: "
        + ", ".join(f"{y}: {n:,}" for y, n in s["legacy_only_cells_flagged_by_year"].items())
        + ".",
        "",
        "## Spatial disagreement",
        "",
        table(pd.DataFrame(s["disagreement_clusters"])),
        "",
        table(reg),
        "",
        img("largest-disagreement-regions.png"),
        "",
        "### Edge vs interior (area-uniform sample points; "
        f"{s['sample']['points_used']:,} points, seed {s['sample']['seed']})",
        "",
        "Distance from disagreement area to the other product's same-year polygon:",
        "",
        table(edge),
        "",
        "Disagreement by size of the source polygon:",
        "",
        table(size),
        "",
        "Polygon-level overlap with the other product, same year:",
        "",
        table(poly.fillna("")),
        "",
        "## Recurrence review",
        "",
        "Same six years for both products (km2 flooded in >= k of 2011-2016):",
        "",
        table(rc),
        "",
        "Current product, full record - years flooded (of 13) x share of cell, kept as "
        "separate dimensions (% of AOI area):",
        "",
        table(rs_tab),
        "",
        "## Lowland unresolved semantics (policy 0.2.1)",
        "",
        "Policy outputs now carry `hazard_interpretation` (what the assessed hazards say), "
        "`data_completeness` and `landslide_assessment_status` (`ASSESSED` / "
        "`PARTIALLY_ASSESSED` / `NOT_ASSESSED`) as separate fields, plus `assessed_hazards`. "
        "Outside DMR coverage the landslide level reads `NOT_ASSESSED`, never `NONE` or "
        "'low'; flood/terrain interpretation remains available and explanations say so. The "
        "`regional_search_status` rule is unchanged.",
        "",
        "## Human QA",
        "",
        table(gates),
        "",
        "## Files",
        "",
        "| File | Bytes |",
        "|---|---:|",
    ]
    lines += [f"| {k} | {v:,} |" for k, v in files.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (REVIEW / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1c2-review/").replace(
            TITLE,
            TITLE + "\n\n> Committed copy of `outputs/m1c2-review/README.md`; images and "
            "tables live in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
