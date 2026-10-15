"""Write outputs/m1c3-review/README.md and docs/research/m1c3-flood-fusion-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.hazard import load_fusion_config
from hearthmap.qa import load_human_qa

OUT = Path("outputs/m1c3")
REVIEW = Path("outputs/m1c3-review")
DOC = Path("docs/research/m1c3-flood-fusion-report.md")
FINDINGS = Path("docs/research/m1c3-findings.md")
TITLE = "# HearthMap M1C.3 - Flood evidence fusion policy"
NAMES = {"AOI": "AOI", "TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
LADDER = [
    "NO_MAJOR_OBSERVED_SIGNAL",
    "HISTORICAL_SIGNAL",
    "REQUIRES_FLOOD_VERIFICATION",
    "STRONG_FLOOD_SCREENING_CONCERN",
    "UNRESOLVED",
]
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
POLICIES = [
    "V021_CURRENT_ONLY_REFERENCE",
    "FLOOD_CURRENT_PRIMARY",
    "FLOOD_ANY_SOURCE",
    "FLOOD_UNION_CONSERVATIVE",
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


def build(prefix: str) -> str:
    fcfg = load_fusion_config()
    st = json.loads((OUT / "fusion-statistics.json").read_text("utf-8"))
    comp = pd.read_csv(REVIEW / "flood-policy-comparison.csv")
    matrix = pd.read_csv(REVIEW / "policy-matrix.csv")
    low = pd.read_csv(REVIEW / "lowland-policy-sensitivity.csv")
    reg = pd.read_csv(REVIEW / "policy-sensitive-regions.csv")
    ftr = pd.read_csv(OUT / "flood-policy-transitions.csv")
    fam = pd.read_csv(OUT / "rule-family-sensitivity.csv")
    pair = pd.read_csv(OUT / "stability-pairwise-area.csv")
    rc = pd.read_csv(OUT / "flood-reason-code-counts.csv")
    qa = load_human_qa()

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    # candidate definitions
    defs = []
    for cid, c in fcfg.candidates.items():
        for r in c.rules:
            defs.append(
                {
                    "candidate": cid,
                    "level": r.level,
                    "rule": r.id,
                    "metric": r.metric,
                    "years": f"{r.years[0]}-{r.years[1]}",
                    "min_years": r.min_years,
                    "min_cell_fraction": r.min_fraction,
                }
            )
    cand_tab = []
    for scope in NAMES:
        t = comp[comp["scope"] == scope]
        rows = []
        for state in LADDER:
            row = {"flood ladder state": state}
            for p in POLICIES[1:]:
                x = t[(t["flood_policy"] == p) & (t["state"] == state)].iloc[0]
                row[p] = (
                    f"{x['cells']:,} / {x['area_km2']:,.0f} km2 ({100 * x['share_of_area']:.1f}%)"
                )
            rows.append(row)
        cand_tab.append(
            f"**{NAMES[scope]}** (cells / area / share)\n\n" + table(pd.DataFrame(rows))
        )
    trans_tabs = []
    for a, b in (
        ("FLOOD_CURRENT_PRIMARY", "FLOOD_ANY_SOURCE"),
        ("FLOOD_ANY_SOURCE", "FLOOD_UNION_CONSERVATIVE"),
        ("FLOOD_CURRENT_PRIMARY", "FLOOD_UNION_CONSERVATIVE"),
    ):
        t = ftr[(ftr["from_policy"] == a) & (ftr["to_policy"] == b)]
        m = t.pivot_table(
            index="from", columns="to", values="cells", aggfunc="sum", fill_value=0
        ).reindex(index=LADDER, columns=LADDER, fill_value=0)
        m = m.loc[(m.sum(axis=1) > 0), (m.sum(axis=0) > 0)].astype(int)
        m.index.name = f"{a} \\ {b} (cells)"
        trans_tabs.append(table(m.reset_index()))
    # matrix tables
    mats = []
    for scope in NAMES:
        t = matrix[matrix["scope"] == scope]
        rows = []
        for p in POLICIES:
            for q in PROFILES:
                x = t[(t["flood_policy"] == p) & (t["profile"] == q)].set_index("state")
                rows.append(
                    {
                        "flood policy": p,
                        "profile": q,
                        **{
                            s: f"{x.loc[s, 'cells']:,} / {x.loc[s, 'area_km2']:,.0f}"
                            for s in STATUSES
                        },
                    }
                )
        mats.append(f"**{NAMES[scope]}** (cells / km2)\n\n" + table(pd.DataFrame(rows)))
    # lowland table
    keep = [
        "flood_ladder_differs_across_candidates",
        "overall_status_differs_across_flood_candidates:any_profile",
        "overall_status_differs_across_profiles:FLOOD_ANY_SOURCE",
    ]
    lw = low[low["measure"].isin(keep)][
        [
            "stratum",
            "measure",
            "stratum_area_km2",
            "stratum_share_of_aoi",
            "changed_area_km2",
            "share_of_stratum_changed",
            "share_of_all_changed_in_stratum",
            "disproportion_ratio",
        ]
    ]
    pair_sum = pair.groupby("axis")["area_km2"].agg(["mean", "max"]).round(1).reset_index()
    fam_a = fam[(fam["scope"] == "AOI")][
        ["family", "rule", "years", "cells", "area_km2", "share_of_area"]
    ].copy()
    fam_a["share_of_area"] = (100 * fam_a["share_of_area"]).round(2)
    gates = pd.DataFrame([{"gate": g.upper(), "status": r.status} for g, r in qa.gates.items()])
    sizes = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name not in ("README.md", "file-sizes.json")
    }
    sizes |= {f"m1c3/{p.name}": p.stat().st_size for p in sorted(OUT.iterdir()) if p.is_file()}
    lines = [
        TITLE,
        "",
        f"**Flood fusion {fcfg.fusion_version} - status {fcfg.status}; no flood candidate and no "
        "hydrogeomorphic profile is selected.** Hydrogeomorphic screening only; observed "
        "flooding only - the absence of a polygon in either product is never evidence of no flood "
        "risk, and outcomes never mean safe, buildable or rejected. Semantics: "
        "`docs/product/flood-fusion-policy.md`.",
        "",
        f"`observed_year_count_total`: {st['observed_year_count_definition']}.",
        "",
        FINDINGS.read_text("utf-8"),
        "",
        "## Annual source-aware ledger",
        "",
        "Cells by number of years with observed flooding (raw observational count):",
        "",
        table(
            pd.DataFrame(
                st["observed_year_count_distribution_cells"].items(),
                columns=["observed years", "cells"],
            )
        ),
        "",
        img("annual-source-ledger-summary.png"),
        "",
        img("recent-vs-historical-flood.png"),
        "",
        img("product-disagreement.png"),
        "",
        "## Flood policy candidates (exact rules)",
        "",
        "Each candidate also inherits every rule of the candidate it extends. A rule fires "
        "when the metric is >= `min_cell_fraction` in >= `min_years` years of the window; "
        "unavailable years never count.",
        "",
        table(pd.DataFrame(defs)),
        "",
        "Reason-code frequency (cells):",
        "",
        table(
            rc.pivot_table(
                index="reason_code", columns="flood_policy", values="cells", fill_value=0
            )
            .astype(int)
            .reset_index()
        ),
        "",
        "## Candidate comparison",
        "",
        *[b + "\n" for b in cand_tab],
        "Transitions between candidates (flood ladder):",
        "",
        *[b + "\n" for b in trans_tabs],
        img("flood-policy-candidates.png"),
        "",
        "## Rule-family sensitivity (AOI, each rule on its own)",
        "",
        table(fam_a),
        "",
        "## Residential-lowland sensitivity (slope strata for reporting only)",
        "",
        table(lw),
        "",
        img("policy-sensitive-lowlands.png"),
        "",
        "## Hydrogeomorphic policy matrix (flood policy x profile)",
        "",
        "`V021_CURRENT_ONLY_REFERENCE` is the earlier policy 0.2.1 flood rule (current "
        "product only, profile-specific thresholds), kept as a reference.",
        "",
        *[b + "\n" for b in mats],
        "Pairwise changed area (km2):",
        "",
        table(pair_sum),
        "",
        img("overall-policy-matrix.png"),
        "",
        "## Sensitive regions (flood-source choice changes the outcome under >= 1 profile)",
        "",
        table(reg.head(15)),
        "",
        "## Human QA",
        "",
        table(gates),
        "",
        "No review of the M1C, M1C.1, M1C.2 or M1C.3 map packs has been reported; none is "
        "inferred.",
        "",
        "## Files",
        "",
        "| File | Bytes |",
        "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in sizes.items()],
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (REVIEW / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1c3-review/").replace(
            TITLE,
            TITLE + "\n\n> Committed copy of `outputs/m1c3-review/README.md`; images and tables "
            "live in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
