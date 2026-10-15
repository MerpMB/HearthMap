"""Write outputs/m1c1-review/README.md and docs/research/m1c1-flood-refresh-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.hazard import load_policy_config
from hearthmap.qa import load_human_qa

M1C1 = Path("outputs/m1c1")
OUT = Path("outputs/m1c1-review")
DOC = Path("docs/research/m1c1-flood-refresh-report.md")
NAMES = {"AOI": "AOI", "TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
PROFILES = ["CONSERVATIVE", "BALANCED", "PERMISSIVE"]
TITLE = "# HearthMap M1C.1 — Flood truth refresh (GISTDA 2011-2023)"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += [
        "| " + " | ".join(str(v).replace("|", r"\|") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join(out)


def build(prefix: str) -> str:
    cfg = load_policy_config()
    qa_gates = load_human_qa()
    st = json.loads((M1C1 / "refresh-statistics.json").read_text("utf-8"))
    fq = json.loads((M1C1 / "flood-2011-2023-qa.json").read_text("utf-8"))
    api = json.loads((M1C1 / "flood-2011-2023-api-completeness.json").read_text("utf-8"))
    fcs = pd.read_csv(M1C1 / "flood-change-summary.csv")
    fcr = pd.read_csv(M1C1 / "flood-change-largest-regions.csv")
    evt = pd.read_csv(M1C1 / "evidence-refresh-transitions.csv")
    dist = pd.read_csv(M1C1 / "policy-refresh-distribution.csv")
    tr = pd.read_csv(M1C1 / "policy-refresh-transitions.csv")
    lc = pd.read_csv(M1C1 / "policy-refresh-largest-changes.csv")
    sens = pd.read_csv(M1C1 / "policy" / "candidate-threshold-sensitivity.csv")

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    gates = pd.DataFrame(
        [
            {
                "gate": g.upper(),
                "status": r.status,
                "review_date": r.review_date or "",
                "reviewer_role": r.reviewer_role or "",
                "result": r.result or "",
            }
            for g, r in qa_gates.gates.items()
        ]
    )
    # flood change
    fc = fcs.pivot_table(
        index="flood_change_class", columns="scope", values="area_km2", sort=False
    )[["AOI", "TH50", "TH56", "TH57"]].round(1)
    fcc = fcs.pivot_table(index="flood_change_class", columns="scope", values="cells", sort=False)[
        "AOI"
    ]
    fc.insert(0, "AOI cells", fcc.astype(int))
    fc = fc.rename(columns={k: f"{v} km2" for k, v in NAMES.items()}).reset_index()
    ft = st["flood_tier_transition_cells"]
    ft_tab = pd.DataFrame(ft).T.fillna(0).astype(int)
    ft_tab.index.name = "2005-2016 tier \\ 2011-2023 tier"
    ft_tab = ft_tab.reset_index()
    ev_over = evt[evt["field"] == "overall_state"].sort_values("area_km2", ascending=False)
    ev_over = ev_over[ev_over["before"] != ev_over["after"]].drop(columns="field")

    # policy distribution tables
    blocks = []
    for scope in ("AOI", "TH50", "TH56", "TH57"):
        d = dist[dist["scope"] == scope]
        rows = []
        for p in PROFILES:
            dp = d[d["profile"] == p].set_index("status")
            rows.append(
                {
                    "profile": p,
                    **{
                        s: f"{dp.loc[s, 'cells_before']:,} → {dp.loc[s, 'cells_after']:,} / "
                        f"{dp.loc[s, 'area_km2_before']:,.0f} → {dp.loc[s, 'area_km2_after']:,.0f}"
                        f" km2 ({dp.loc[s, 'area_km2_delta']:+,.0f})"
                        for s in STATUSES
                    },
                }
            )
        blocks.append(
            f"**{NAMES[scope]}** (cells before → after / km2 before → after (Δ km2))\n\n"
            + table(pd.DataFrame(rows))
        )
    chg = pd.DataFrame(
        [
            {
                "profile": p,
                "cells changed": f"{v['cells_changed']:,}",
                "area changed km2": f"{v['area_changed_km2']:,.0f}",
                "share of AOI": f"{100 * v['share_of_aoi_area']:.2f}%",
                "more concern (cells / km2)": f"{v['more_concern_cells']:,} / "
                f"{v['more_concern_km2']:,.0f}",
                "less concern (cells / km2)": f"{v['less_concern_cells']:,} / "
                f"{v['less_concern_km2']:,.0f}",
                "to/from UNRESOLVED": v["to_or_from_unresolved_cells"],
                "Chiang Mai / Phayao / Chiang Rai km2": " / ".join(
                    f"{x:,.0f}" for x in v["by_province_km2"].values()
                ),
            }
            for p, v in st["policy_change"].items()
        ]
    )
    key_pairs = [
        ("NO_MAJOR_CONCERN_DETECTED", "REQUIRES_VERIFICATION"),
        ("REQUIRES_VERIFICATION", "STRONG_REGIONAL_CONCERN"),
        ("STRONG_REGIONAL_CONCERN", "REGIONAL_DEPRIORITIZE"),
        ("REQUIRES_VERIFICATION", "REGIONAL_DEPRIORITIZE"),
    ]
    kp = []
    for a, b in key_pairs:
        for x, y, direction in ((a, b, "forward"), (b, a, "reverse")):
            row = {"transition": f"{x} → {y}", "direction": direction}
            for p in PROFILES:
                m = tr[(tr["profile"] == p) & (tr["before"] == x) & (tr["after"] == y)]
                row[p] = (
                    f"{int(m['cells'].sum()):,} / {m['area_km2'].sum():,.1f} km2" if len(m) else "0"
                )
            kp.append(row)
    full_bal = tr[(tr["profile"] == "BALANCED") & (tr["before"] != tr["after"])]
    full_bal = full_bal.sort_values("area_km2", ascending=False).drop(columns="profile")
    fs = sens[(sens["scope"] == "AOI") & sens["candidate"].str.startswith("FLOOD")]
    fs = fs[
        [
            "candidate",
            "threshold",
            "cells",
            "area_km2",
            "share_of_area",
            "share_with_landslide_unresolved",
            "also_landslide_high_plus_ge0.50",
        ]
    ].copy()
    fs["share_of_area"] = (100 * fs["share_of_area"]).round(2)
    fp = st["flooded_area_km2"]
    sizes = {f"m1c1/{p.name}": p.stat().st_size for p in sorted(M1C1.iterdir()) if p.is_file()}
    sizes |= {f"m1c1-review/{p.name}": p.stat().st_size for p in sorted(OUT.glob("*.png"))}

    fl = cfg.flood_source
    lines = [
        TITLE,
        "",
        f"**Policy {cfg.policy_version} — status {cfg.status}; no default profile is selected.** "
        "Hydrogeomorphic screening only (observed flooding 2011-2023, DMR landslide "
        "susceptibility, DSM terrain); not a complete natural-hazard assessment. Outcomes are "
        "regional screening only — never safe, buildable, rejected or legally excluded.",
        "",
        "## Human visual QA",
        "",
        table(gates),
        "",
        "Recorded in `config/human-qa.yaml` exactly as reported; no further observations are "
        "implied. The M1C policy review pack was not clearly part of the reviewed material and "
        "stays PENDING.",
        "",
        "## GISTDA 2011-2023 (verified)",
        "",
        f"* {fq['features_raw']:,} polygons in {fq['tiles']} AOI tiles "
        f"({fq['tiles_with_features']} with features); {fq['features_intersecting_aoi']:,} "
        "intersect the AOI.",
        f"* Each feature has exactly 13 yearly values 2011-2023; yearly `freq` ∈ "
        f"{{{', '.join(fq['detail_freq_values'])}}}; `total` = Σ yearly freq for "
        f"{fq['total_equals_sum_of_yearly_freq']:,} of {fq['features_raw']:,} features → "
        "`total` = years observed flooded. Distribution of `total`: "
        + ", ".join(f"{k}: {v:,}" for k, v in fq["total_distribution"].items())
        + ".",
        f"* Geometry: {fq['geometry_before']}; repairs {fq['repair_audit']['repair_count']}; "
        f"exact duplicates {fq['exact_duplicates']}; pairwise overlap "
        f"{fq['overlap']['overlap_area_total_m2']:.1e} m2 (areas additive); reprojected "
        f"lon/lat → EPSG:32647 ({fq['transformation']}, datum change: {fq['datum_change']}).",
        "* Feature-cap check: the two densest tiles re-requested as quadrants returned "
        + "; ".join(f"area ratio {r['area_ratio_all']:.3f}" for r in api)
        + ".",
        "* Licence: Open Data Common. Resolution 20 m (publisher). Ends 2023. "
        "Detailed methodology unpublished; the publisher's '10-year period' wording does not "
        "match the 13 yearly values.",
        "",
        "Full semantic comparison: `docs/research/flood-record-comparison.md`.",
        "",
        img("new-flood-evidence.png"),
        "",
        "## Old vs new flood evidence",
        "",
        "Observed flooded area in the AOI (km2, cell-clipped):",
        "",
        table(pd.DataFrame([fp]).T.reset_index().rename(columns={"index": "measure", 0: "km2"})),
        "",
        "Cells with any observed flooding: "
        + ", ".join(
            f"{k.replace('_', ' ')} {v:,}" for k, v in st["cells_with_any_observed_flood"].items()
        )
        + ".",
        "",
        "Per-cell flood screening tier (each record with its own definition: HIGH = ≥ 10% of "
        "the cell flooded in ≥ 3 of the record's years; CAUTION = any observed flooding ≥ 1% "
        "or within 250 m):",
        "",
        table(fc),
        "",
        table(ft_tab),
        "",
        "Largest contiguous changes:",
        "",
        table(fcr),
        "",
        img("old-vs-new-flood.png"),
        "",
        "## M1B evidence refresh",
        "",
        f"Landslide tiers unchanged: {st['landslide_tiers_unchanged']}; terrain tiers "
        f"unchanged: {st['terrain_tiers_unchanged']}. Overall screening state changed in "
        f"{st['evidence_overall_changed']['cells']:,} cells "
        f"({st['evidence_overall_changed']['area_km2']:,.0f} km2). Mean evidence completeness "
        f"{st['evidence_completeness_mean']['before']:.4f} → "
        f"{st['evidence_completeness_mean']['after']:.4f}.",
        "",
        table(ev_over),
        "",
        "## M1C profile refresh (policy 0.1.0 on 2005-2016 → 0.2.0 on 2011-2023)",
        "",
        "Only the flood record (and the explicit flood threshold semantics) changed; every "
        "landslide/terrain/multi-hazard threshold is identical. Province rows use "
        "majority-province attribution.",
        "",
        *[b + "\n" for b in blocks],
        img("balanced-policy-refreshed.png"),
        "",
        img("profile-change-summary.png"),
        "",
        "## Policy stability",
        "",
        table(chg),
        "",
        "Named transitions (cells / km2, before → after):",
        "",
        table(pd.DataFrame(kp)),
        "",
        "All BALANCED transitions:",
        "",
        table(full_bal),
        "",
        "Largest contiguous changed regions:",
        "",
        table(lc),
        "",
        img("flood-policy-change.png"),
        "",
        "## Flood threshold review (2011-2023 semantics)",
        "",
        f"Configured: source `{fl.source_id}`, period {fl.period}, {fl.record_years} years; "
        f"source-native metric: {fl.source_native_metric}. Derived: "
        f"{fl.derived_threshold_semantics}.",
        "",
        table(fs),
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
        build("../../outputs/m1c1-review/").replace(
            TITLE,
            TITLE + "\n\n> Committed copy of `outputs/m1c1-review/README.md`; images live in "
            "the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
