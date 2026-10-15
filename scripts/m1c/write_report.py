"""Write outputs/m1c-review/README.md and docs/research/m1c-hazard-policy-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.hazard import load_policy_config

M1C = Path("outputs/m1c")
OUT = Path("outputs/m1c-review")
DOC = Path("docs/research/m1c-hazard-policy-report.md")
NAMES = {"AOI": "AOI", "TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
PROFILES = ["CONSERVATIVE", "BALANCED", "PERMISSIVE"]


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += [
        "| " + " | ".join(str(v).replace("|", r"\|") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join(out)


def pair(a: float, b: float) -> str:
    return f"{a:g} / {b:g}"


def build(prefix: str) -> str:
    cfg = load_policy_config()
    s = json.loads((M1C / "policy-statistics.json").read_text("utf-8"))
    sens = pd.read_csv(M1C / "candidate-threshold-sensitivity.csv")
    trans = pd.read_csv(M1C / "profile-transitions.csv")
    frag = pd.read_csv(M1C / "fragmentation-summary.csv")
    comps = pd.read_csv(M1C / "largest-components.csv")
    rc = pd.read_csv(M1C / "reason-code-distribution.csv")
    res = pd.read_parquet(M1C / "policy-results.parquet")
    examples = (M1C / "example-explanations.md").read_text("utf-8")

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    # profile thresholds
    th = []
    for p, pr in cfg.profiles.items():
        th.append(
            {
                "profile": p,
                "flood strong / deprioritize (>=3 yrs fraction)": pair(
                    pr.flood.strong_min_fraction, pr.flood.deprioritize_min_fraction
                ),
                "Very High strong / deprioritize": pair(
                    pr.landslide.very_high_strong, pr.landslide.very_high_deprioritize
                ),
                "High+VH strong / deprioritize": pair(
                    pr.landslide.high_plus_strong, pr.landslide.high_plus_deprioritize
                ),
                "terrain VERIFY / corroborate (DSM p90 deg)": pair(
                    pr.terrain.verify_slope_p90_deg, pr.terrain.corroborate_slope_p90_deg
                ),
                "terrain escalates landslide": pr.terrain.corroboration_escalates_landslide,
                "scar within m / escalates": f"{pr.landslide.scar_within_m:g} / "
                f"{pr.landslide.scar_escalates_strong}",
                "flood+landslide escalation": pr.multi_hazard.escalate_flood_and_landslide_strong,
            }
        )
    # status tables
    blocks = []
    for scope in ("AOI", "TH50", "TH56", "TH57"):
        rows = []
        for p in PROFILES:
            e = s["profiles"][p][scope]
            rows.append(
                {
                    "profile": p,
                    **{
                        st: f"{e[st]['cells']:,} / {e[st]['area_km2']:,.0f} km2 "
                        f"({100 * e[st]['share_of_area']:.1f}%)"
                        for st in STATUSES
                    },
                }
            )
        blocks.append(
            f"**{NAMES[scope]}** (cells / area / share of area)\n\n" + table(pd.DataFrame(rows))
        )
    # transitions
    tr = trans[trans["from_status"] != trans["to_status"]].sort_values("area_km2", ascending=False)
    tr = tr.head(10)[["to_profile", "from_status", "to_status", "cells", "area_km2"]]
    # sensitivity
    sp = sens.pivot_table(
        index=["candidate", "threshold"], columns="scope", values="share_of_area", sort=False
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
    aoi = sens[sens["scope"] == "AOI"].set_index(["candidate", "threshold"])
    sp["AOI km2"] = [
        round(aoi.loc[(c, t), "area_km2"], 0)
        for c, t in zip(sp["candidate"], sp["threshold"], strict=True)
    ]
    inter = sens[sens["scope"] == "AOI"][
        [
            "candidate",
            "threshold",
            "cells",
            "share_with_landslide_unresolved",
            "share_with_terrain_unresolved",
            "also_flood_recurrent_ge0.10",
            "also_landslide_very_high_ge0.25",
            "also_landslide_high_plus_ge0.50",
            "also_terrain_p90_ge30",
        ]
    ].copy()
    for c in inter.columns[3:]:
        inter[c] = (100 * inter[c]).round(1)
    bal = res[res["policy_profile"] == "BALANCED"]
    inc = bal[bal["evidence_completeness_class"] != "COMPLETE"]
    inc_tab = (
        inc.groupby(["evidence_completeness_class", "regional_search_status"])
        .agg(cells=("cell_id", "size"), area_km2=("clipped_area_km2", "sum"))
        .round(1)
        .reset_index()
    )
    rc_tab = (
        rc.pivot_table(index="reason_code", columns="profile", values="area_km2", aggfunc="sum")
        .fillna(0)
        .round(0)[PROFILES]
    )
    rc_tab = rc_tab.sort_values("BALANCED", ascending=False).reset_index()
    first_example = (
        examples.split("```text")[1].split("```")[0].strip() if "```text" in examples else ""
    )
    sizes = {p.name: p.stat().st_size for p in sorted(M1C.iterdir()) if p.is_file()}
    sizes |= {f"m1c-review/{p.name}": p.stat().st_size for p in sorted(OUT.glob("*.png"))}

    lines = [
        "# HearthMap M1C — Hydrogeomorphic Hazard Screening policy review",
        "",
        f"**Policy {cfg.policy_version} — status {cfg.status}; no default profile.** Human visual "
        f"sign-off: M1A.1 {cfg.gates.m1a1_human_visual_signoff}, M1B "
        f"{cfg.gates.m1b_human_visual_signoff}. Scope: **hydrogeomorphic only** (observed flood "
        "2005-2016, DMR landslide susceptibility, DSM terrain) - not a complete natural-hazard "
        "assessment; seismic/active-fault, earthquake, wildfire and other hazards are not "
        "covered (`docs/product/natural-hazard-scope.md`). Outcomes are regional screening only: "
        "never safe, buildable, rejected or legally excluded; `eligible` is untouched.",
        "",
        "Policy semantics: `docs/product/hazard-screening-policy.md`; config: "
        "`config/hazard-policy.yaml`.",
        "",
        "## Profiles (for sensitivity analysis - none is selected)",
        "",
        table(pd.DataFrame(th)),
        "",
        img("policy-profiles-comparison.png"),
        "",
        "## Outcomes by profile and province",
        "",
        "Province rows use majority-province attribution; "
        "1,442 cells carry the M1A.1 boundary-attribution caution (outcomes are unaffected).",
        "",
        *[b + "\n" for b in blocks],
        "## Profile transitions (largest changes vs BALANCED)",
        "",
        f"Area changing outcome vs BALANCED: CONSERVATIVE "
        f"{s['transitions_changed_area_km2_vs_balanced']['CONSERVATIVE']:,.0f} km2, PERMISSIVE "
        f"{s['transitions_changed_area_km2_vs_balanced']['PERMISSIVE']:,.0f} km2 (AOI 39,930 km2).",
        "",
        table(tr),
        "",
        img("profile-differences.png"),
        "",
        "## Candidate thresholds (each rule evaluated alone)",
        "",
        table(sp),
        "",
        "Interactions (AOI, % of the flagged cells): unresolved for other hazards, and also "
        "flagged by other candidate rules:",
        "",
        table(inter),
        "",
        "Terrain values derive from the Copernicus GLO-30 **DSM**, not a bare-earth model; "
        "terrain can only produce REQUIRES_VERIFICATION or corroborate landslide concern.",
        "",
        "## Spatial structure (diagnostic; nothing smoothed or removed)",
        "",
        table(frag),
        "",
        "Largest BALANCED components:",
        "",
        table(comps[comps["profile"] == "BALANCED"].drop(columns=["profile"]).head(15)),
        "",
        img("largest-deprioritized-regions.png"),
        "",
        "## Unresolved / incomplete evidence (BALANCED)",
        "",
        "Cells with incomplete evidence keep any positive evidence visible; only cells with no "
        "concern signal become UNRESOLVED (incompleteness overrides reassurance).",
        "",
        table(inc_tab),
        "",
        img("unresolved-evidence.png"),
        "",
        "## Reason codes (area km2 of cells carrying each code)",
        "",
        table(rc_tab),
        "",
        img("reason-code-distribution.png"),
        "",
        "## Example explanation (BALANCED, generated from reason codes)",
        "",
        "```text",
        first_example,
        "```",
        "",
        "More examples: `outputs/m1c/example-explanations.md`.",
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
        build("../../outputs/m1c-review/").replace(
            "# HearthMap M1C — Hydrogeomorphic Hazard Screening policy review",
            "# HearthMap M1C — Hydrogeomorphic Hazard Screening policy report\n\n"
            "> Committed copy of `outputs/m1c-review/README.md`; "
            "images live in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
