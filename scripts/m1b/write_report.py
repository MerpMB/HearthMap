"""Write outputs/m1b-review/README.md and docs/research/m1b-hazard-evidence-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

M1B = Path("outputs/m1b")
OUT = Path("outputs/m1b-review")
DOC = Path("docs/research/m1b-hazard-evidence-report.md")
NAMES = {"AOI": "AOI", "TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
DMR = ["Very Low", "Low", "Medium", "High", "Very High"]


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    # Escape pipes inside values (e.g. "landslide|terrain") so Markdown cells stay intact.
    out += [
        "| " + " | ".join(str(v).replace("|", r"\|") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join(out)


def build(prefix: str) -> str:
    s = json.loads((M1B / "hazard-statistics.json").read_text("utf-8"))
    w = pd.read_parquet(M1B / "hazard-evidence.parquet")
    sens = pd.read_csv(M1B / "threshold-sensitivity.csv")
    sizes = {p.name: p.stat().st_size for p in sorted(M1B.iterdir()) if p.is_file()}
    sizes |= {f"m1b-review/{p.name}": p.stat().st_size for p in sorted(OUT.glob("*.png"))}

    def img(name: str) -> str:
        return f"![{name}]({prefix}{name})"

    rows = []
    for k in ("AOI", "TH50", "TH56", "TH57"):
        d = s[k]
        rows.append(
            {
                "scope": NAMES[k],
                "cells": f"{d['cells']:,}",
                "complete flood evidence": pct(d["complete_flood_evidence"]["share_of_cells"]),
                "complete landslide evidence": pct(
                    d["complete_landslide_evidence"]["share_of_cells"]
                ),
                "adequate terrain support (>=10 px)": pct(
                    d["adequate_terrain_support"]["share_of_cells"]
                ),
                "incomplete evidence": pct(d["incomplete_evidence"]["share_of_cells"]),
                "HIGH flood evidence (area)": pct(d["high_flood_evidence"]["share_of_area"]),
                "HIGH landslide evidence (area)": pct(
                    d["high_landslide_evidence"]["share_of_area"]
                ),
                "strong terrain concern (area)": pct(d["strong_terrain_concern"]["share_of_area"]),
            }
        )
    cov = pd.DataFrame(rows)
    states = ("HIGH_HAZARD_EVIDENCE", "CAUTION", "UNRESOLVED", "NO_HIGH_HAZARD_EVIDENCE_DETECTED")
    ov = pd.DataFrame(
        [
            {"scope": NAMES[k], **{st: f"{s[k]['overall_state'].get(st, 0):,}" for st in states}}
            for k in ("AOI", "TH50", "TH56", "TH57")
        ]
    )
    mh = pd.DataFrame(
        [
            {"HIGH evidence combination": c, "cells": f"{n:,}"}
            for c, n in s["AOI"]["multi_hazard_high_combinations"].items()
        ]
    )
    area = w["clipped_area_km2"]
    ls_rows = [
        {
            "DMR class": f"{c} {lab}",
            "area km2 (AOI)": round(float((w[f"landslide_class{c}_fraction"] * area).sum()), 1),
        }
        for c, lab in zip(range(1, 6), DMR, strict=True)
    ]
    ls_rows.append(
        {
            "DMR class": "not assessed",
            "area km2 (AOI)": round(
                float(((1 - w["landslide_assessed_fraction"]) * area).sum()), 1
            ),
        }
    )
    ls_area = pd.DataFrame(ls_rows)
    sp = sens.pivot_table(
        index=["candidate_rule", "threshold"], columns="scope", values="share_of_area", sort=False
    )[["AOI", "TH50", "TH56", "TH57"]]
    sp = (
        (100 * sp)
        .round(1)
        .reset_index()
        .rename(
            columns={
                "AOI": "AOI %",
                "TH50": "Chiang Mai %",
                "TH56": "Phayao %",
                "TH57": "Chiang Rai %",
            }
        )
    )
    rep = s["sources"]["landslide"]["repair"]
    unass = s["landslide_unassessed_context"]
    wpp = s["wiang_pa_pao_zone_cells"]

    lines = [
        "# HearthMap M1B — Hazard evidence review",
        "",
        "**Status:** PROVISIONAL hazard *evidence* — not a decision. No exclusions, scores or "
        "rankings. `M1A1_HUMAN_VISUAL_SIGNOFF = PENDING` (only the builder has looked at the "
        "M1A.1 maps), so no rule here may be promoted to a DECISION_RULE. "
        "`NO_HIGH_HAZARD_EVIDENCE_DETECTED` never means safe.",
        "",
        "Model and field semantics: `docs/product/hazard-evidence-model.md`; terrain method: "
        "`docs/architecture/terrain-methods.md`; thresholds: `config/hazard.yaml`.",
        "",
        "## Evidence coverage and provisional states (majority-province attribution)",
        "",
        table(cov),
        "",
        f"Province rows use each cell's majority province; "
        f"{s['AOI']['boundary_attribution_uncertain_cells']:,} cells carry the M1A.1 "
        "boundary-attribution caution (context only; hazard values are unaffected).",
        "",
        "Overall categorical state (worst hazard wins, never averaged):",
        "",
        table(ov),
        "",
        "Cells by which hazards have HIGH evidence (AOI):",
        "",
        table(mh),
        "",
        img("multi-hazard-evidence.png"),
        "",
        "## Flood (historical observed, TEMPORARY evidence)",
        "",
        "GISTDA repeated flooding 2005-2016 (satellite-observed). HIGH = at least 10% of the "
        "cell observed flooded in at least 3 of 12 years; CAUTION = any observed flooding on "
        "at least 1% of the cell or within 250 m. The 2011-2023 recurrence API stays "
        "`BLOCKED_CREDENTIAL_REQUIRED` (no project key in the environment; catalogue keys not "
        "used). Observed flooding is concentrated in Chiang Rai and Phayao valley floors. The "
        "record ends in 2016 and misses flash floods and cloud-covered events.",
        "",
        img("flood-evidence.png"),
        "",
        "## Landslide (DMR susceptibility and inventory, kept separate)",
        "",
        "DMR susceptibility (gridcode 1-5 = Very Low ... Very High per the data dictionary); "
        "~1 km lattice offset from the HearthMap grid; methodology not published. Repairs in "
        f"the AOI: {rep['repair_count']} ring self-intersections, max area change "
        f"{rep['max_abs_area_delta_m2']:.1e} m2. Inventory: "
        f"{s['sources']['landslide']['inventory_points_in_aoi']:,} scar points in the AOI, "
        "no event years in the data, very uneven by province.",
        "",
        table(ls_area),
        "",
        f"Unassessed landslide cells: {unass['cells']:,}; {pct(unass['share_slope_p90_lt_10deg'])} "
        f"of them have DSM slope p90 below 10 deg (median {unass['median_slope_p90_deg']:.1f} deg) "
        "- mostly lowlands outside the DMR product. Reported only; they stay UNRESOLVED.",
        "",
        img("landslide-evidence.png"),
        "",
        "## Terrain (DSM slope, support-aware)",
        "",
        "Horn 3x3 slope in degrees on the native 1-arc-second grid with geodesic per-row "
        "spacing, halo reads across tile seams, NaN on nodata/edges, no smoothing; weighted "
        "per-cell statistics with support (ADR-0009). Interpretation uses slope p90 (robust); "
        "raw max is reported but not used. The steepest cells cluster around 98.9E 19.4N with "
        "DSM maxima near 2,176 m - consistent with the Doi Chiang Dao limestone massif (not "
        f"field-confirmed). Support: {s['AOI']['terrain_unresolved']['cells']} cells below 1 "
        f"pixel (UNRESOLVED) and {s['AOI']['terrain_low_support']['cells']} cells with 1-10 "
        "pixels (LOW_SUPPORT), all thin edge slivers.",
        "",
        img("terrain-slope-support.png"),
        "",
        "## Waterway context",
        "",
        "OSM distances and in-cell lengths are context only - not flood safety; OSM "
        "completeness differs strongly by province.",
        "",
        img("waterway-context.png"),
        "",
        "## Unknown / incomplete evidence",
        "",
        img("unknown-incomplete-evidence.png"),
        "",
        "## Experimental exclusion-candidate sensitivity (no threshold selected)",
        "",
        table(sp),
        "",
        "Terrain is the most brittle candidate (25 -> 30 -> 35 deg moves the flagged share "
        "from about 49% to 26% to 7% of the AOI, on a DSM); flood and landslide candidates "
        "change more gradually; INSUFFICIENT_HAZARD_DATA is a step function because "
        "completeness takes only three values.",
        "",
        img("experimental-exclusion-sensitivity.png"),
        "",
        "## Boundary context (Wiang Pa Pao)",
        "",
        "Cells in GISTDA zones gistda-50k-0008/0009 keep their physical hazard evidence "
        f"({wpp['gistda-50k-0008']}); only their province attribution is uncertain.",
        "",
        "## Files",
        "",
        "| File | Bytes |",
        "|---|---:|",
    ]
    lines += [f"| {k} | {v:,} |" for k, v in sizes.items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (OUT / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1b-review/").replace(
            "# HearthMap M1B — Hazard evidence review",
            "# HearthMap M1B — Hazard evidence report\n\n> Committed copy of "
            "`outputs/m1b-review/README.md`; images live in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
