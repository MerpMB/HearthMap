# ruff: noqa: E501
"""Write outputs/m1d-review/README.md and docs/research/m1d-seismic-evidence-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.hazard.defaults import load_regional_defaults
from hearthmap.qa import load_human_qa
from hearthmap.seismic import INTERPRETATION_STATES, load_seismic_config

OUT = Path("outputs/m1d")
REVIEW = Path("outputs/m1d-review")
DOC = Path("docs/research/m1d-seismic-evidence-report.md")
FINDINGS = Path("docs/research/m1d-findings.md")
TITLE = "# HearthMap M1D - Seismic and active-fault evidence (regional screening)"
NAMES = {"AOI": "AOI", "TH50": "Chiang Mai", "TH56": "Phayao", "TH57": "Chiang Rai"}


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    out += [
        "| " + " | ".join(str(v).replace("|", r"\|") for v in r) + " |"
        for r in df.itertuples(index=False)
    ]
    return "\n".join(out)


def build(prefix: str) -> str:
    cfg = load_seismic_config()
    d = load_regional_defaults()
    qa = load_human_qa()
    st = json.loads((REVIEW / "seismic-statistics.json").read_text("utf-8"))
    dist = pd.read_csv(REVIEW / "seismic-interpretation-distribution.csv")
    sens = pd.read_csv(REVIEW / "seismic-sensitivity.csv")
    low = pd.read_csv(REVIEW / "seismic-lowland-context.csv")
    ct = pd.read_csv(REVIEW / "hydro-vs-seismic-crosstab.csv")
    dis = pd.read_csv(REVIEW / "hydro-seismic-disagreement.csv")
    ba = pd.read_csv(REVIEW / "before-after-strong-logic.csv")
    cat = pd.read_csv(REVIEW / "historical-seismicity-summary.csv")
    reg = pd.read_csv(REVIEW / "fault-regional-context.csv")
    bands = pd.read_csv(REVIEW / "fault-distance-bands.csv")
    cls = pd.read_csv(REVIEW / "intensity-class-area.csv")
    conf = pd.read_csv(REVIEW / "source-confidence.csv")
    fam = pd.read_csv(REVIEW / "seismic-family-tiers.csv")

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    dtab = dist.pivot_table(
        index="state", columns="province", values="area_km2", sort=False
    ).reindex(INTERPRETATION_STATES)
    ctab = dist.pivot_table(index="state", columns="province", values="cells", sort=False)
    dist_tab = (
        pd.DataFrame(
            {
                p: [
                    f"{int(ctab.loc[s, p]):,} / {dtab.loc[s, p]:,.0f} km2 "
                    f"({100 * dist[(dist.province == p) & (dist.state == s)]['share_of_area'].iloc[0]:.1f}%)"
                    for s in INTERPRETATION_STATES
                ]
                for p in ("AOI", "Chiang Mai", "Phayao", "Chiang Rai")
            },
            index=INTERPRETATION_STATES,
        )
        .rename_axis("state")
        .reset_index()
    )
    s_aoi = (
        sens[(sens["scope"] == "AOI") & (sens["stratum"] == "ALL")]
        .pivot_table(index="variant", columns="state", values="area_km2", sort=False)
        .round(0)
        .reset_index()
    )
    s_prov = (
        sens[(sens["stratum"] == "ALL") & (sens["state"] == "STRONG_SEISMIC_SCREENING_CONCERN")]
        .pivot_table(index="variant", columns="scope", values="share_of_area", sort=False)
        .mul(100)
        .round(1)
        .rename(columns=NAMES)
        .reset_index()
    )
    s_low = (
        sens[
            (sens["scope"] == "AOI")
            & (sens["state"] == "STRONG_SEISMIC_SCREENING_CONCERN")
            & (sens["stratum"] != "ALL")
        ]
        .pivot_table(index="variant", columns="stratum", values="share_of_area", sort=False)
        .mul(100)
        .round(1)
        .reset_index()
    )
    h_sens = pd.read_csv(REVIEW / "seismic-sensitivity-hydro-crosstab.csv")
    h_sens = h_sens[
        h_sens["variant"].str.startswith(("BASE", "VII_strong_ge_0.10", "VII_strong_ge_0.75"))
    ]
    h_tab = (
        h_sens[h_sens["seismic_state"] == "STRONG_SEISMIC_SCREENING_CONCERN"]
        .pivot_table(index="hydro_status", columns="variant", values="area_km2", sort=False)
        .round(0)
        .reset_index()
    )
    cross = (
        ct[(ct["scope"] == "AOI") & (ct["stratum"] == "ALL")]
        .pivot_table(index="hydro_status", columns="seismic_state", values="area_km2", sort=False)
        .round(0)
        .reset_index()
    )
    low_tab = low.pivot_table(index="state", columns="stratum", values="share_of_area", sort=False)
    low_tab = (100 * low_tab).round(1).reset_index()
    dis_tab = dis[dis["stratum"].isin(["ALL", "LOW_SLOPE_LE_5"]) & (dis["scope"] == "AOI")][
        ["pattern", "stratum", "cells", "area_km2", "share_of_scope_area"]
    ]
    band_tab = (
        bands[bands["stratum"] == "ALL"]
        .assign(share=lambda x: (100 * x["share_of_scope_area"]).round(1))
        .pivot_table(index="band", columns="province", values="share", sort=False)
        .reset_index()
    )
    cls_tab = (
        cls[cls["stratum"] == "ALL"]
        .assign(share=lambda x: (100 * x["share_of_scope_area"]).round(1))
        .pivot_table(index="class", columns="province", values="share", sort=False)
        .reset_index()
    )
    gates = pd.DataFrame([{"gate": g.upper(), "status": r.status} for g, r in qa.gates.items()])
    files = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name not in ("README.md", "file-sizes.json")
    }
    files |= {f"m1d/{p.name}": p.stat().st_size for p in sorted(OUT.iterdir()) if p.is_file()}
    lines = [
        TITLE,
        "",
        f"**Seismic evidence {cfg.seismic_version} - {cfg.status}, experimental; regional screening "
        "only.** Not a seismic hazard model, not a score, not a ranking, not a site assessment. "
        "Ground response is NOT assessed; absence of nearby faults or events is never evidence of "
        "low hazard. Semantics: `docs/product/seismic-evidence-model.md`; sources: "
        "`docs/research/seismic-source-findings.md`.",
        "",
        "## Selected provisional defaults (recorded)",
        "",
        f"`hydrogeomorphic_profile = {d.hydrogeomorphic_profile}`, "
        f"`flood_fusion_policy = {d.flood_fusion_policy}`, "
        f"`selected_for_provisional_screening = {str(d.selected_for_provisional_screening).lower()}`, "
        f"`production_truth = {str(d.production_truth).lower()}`; thresholds unchanged "
        "(fingerprint-checked). See `docs/product/policy-selection.md`.",
        "",
        FINDINGS.read_text("utf-8"),
        "",
        "## Seismic screening distribution (cells / area / share of province area)",
        "",
        table(dist_tab),
        "",
        img("seismic-screening.png"),
        "",
        "Evidence-family tiers (AOI):",
        "",
        table(fam),
        "",
        "## Before / after the corrected strong-concern logic",
        "",
        table(ba),
        "",
        "## Sensitivity (experimental; no thresholds selected)",
        "",
        "AOI area (km2) by state:",
        "",
        table(s_aoi),
        "",
        "Strong-concern share of each province (%):",
        "",
        table(s_prov),
        "",
        "Strong-concern share of each reporting stratum (%):",
        "",
        table(s_low),
        "",
        "Strong-concern area by hydrogeomorphic status (km2):",
        "",
        table(h_tab),
        "",
        "## Active-fault context (descriptive)",
        "",
        table(reg),
        "",
        "Share of province area by distance to the nearest mapped trace (%):",
        "",
        table(band_tab),
        "",
        img("active-fault-context.png"),
        "",
        "## DMR hazard zones (probabilistic PGA 10% in 50 years, shown as MMI)",
        "",
        "Share of province area by class (%):",
        "",
        table(cls_tab),
        "",
        img("earthquake-intensity-context.png"),
        "",
        "## Historical seismicity (sources kept separate)",
        "",
        table(cat.fillna("")),
        "",
        img("historical-seismicity.png"),
        "",
        "## Hydrogeomorphic x seismic (diagnostic cross-tab, km2; no combined score)",
        "",
        table(cross),
        "",
        table(dis_tab),
        "",
        img("hydrogeomorphic-vs-seismic.png"),
        "",
        "## Residential-lowland context (slope strata for reporting only, %)",
        "",
        table(low_tab),
        "",
        img("seismic-lowland-context.png"),
        "",
        "## Confidence dimensions (kept separate)",
        "",
        table(conf),
        "",
        "## Human QA",
        "",
        table(gates),
        "",
        "No review of the M1C, M1C.1, M1C.2, M1C.3 or M1D map packs has been reported; none is inferred.",
        "",
        "## Files",
        "",
        "| File | Bytes |",
        "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in files.items()],
    ]
    del st
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (REVIEW / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1d-review/").replace(
            TITLE,
            TITLE
            + "\n\n> Committed copy of `outputs/m1d-review/README.md`; images and tables live "
            "in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
