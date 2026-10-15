# ruff: noqa: E501
"""Write outputs/m1e-review/README.md and docs/research/m1e-natural-hazard-integration-report.md."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hearthmap.hazard import load_integration_config
from hearthmap.hazard.defaults import load_regional_defaults
from hearthmap.qa import load_human_qa

OUT = Path("outputs/m1e")
REVIEW = Path("outputs/m1e-review")
DOC = Path("docs/research/m1e-natural-hazard-integration-report.md")
FINDINGS = Path("docs/research/m1e-findings.md")
TITLE = "# HearthMap M1E - Natural Hazard policy integration"
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
    cfg = load_integration_config()
    d = load_regional_defaults()
    qa = load_human_qa()
    pa = pd.read_csv(REVIEW / "province-action-areas.csv")
    st = pd.read_csv(REVIEW / "integrated-state-distribution.csv")
    pc = pd.read_csv(REVIEW / "integration-policy-comparison.csv")
    pdiff = pd.read_csv(REVIEW / "integration-policy-differences.csv")
    combos = pd.read_csv(REVIEW / "cross-family-combinations.csv")
    comp = pd.read_csv(REVIEW / "cross-family-component-summary.csv")
    reg = pd.read_csv(REVIEW / "cross-family-largest-regions.csv")
    axis = pd.read_csv(REVIEW / "action-axis-distribution.csv")
    fam = pd.read_csv(REVIEW / "family-action-distribution.csv")
    unres = pd.read_csv(REVIEW / "unresolved-evidence.csv")
    burden = pd.read_csv(REVIEW / "verification-burden-distribution.csv")
    prof = pd.read_csv(REVIEW / "parcel-handoff-profiles.csv")
    stats = json.loads((REVIEW / "integration-statistics.json").read_text("utf-8"))

    def img(n: str) -> str:
        return f"![{n}]({prefix}{n})"

    pa_t = pa.assign(
        v=lambda x: (
            x["area_km2"].map("{:,.0f}".format)
            + " km2 ("
            + (100 * x["share_of_scope_area"]).round(1).astype(str)
            + "%)"
        )
    )
    pa_t = (
        pa_t.pivot_table(index="measure", columns="scope", values="v", aggfunc="first", sort=False)[
            list(NAMES)
        ]
        .rename(columns=NAMES)
        .reset_index()
    )
    st_t = st[st["stratum"] == "ALL"].assign(
        v=lambda x: (
            x["area_km2"].map("{:,.0f}".format)
            + " km2 ("
            + (100 * x["share_of_scope_area"]).round(1).astype(str)
            + "%)"
        )
    )
    st_t = (
        st_t.pivot_table(index="state", columns="scope", values="v", aggfunc="first", sort=False)[
            list(NAMES)
        ]
        .rename(columns=NAMES)
        .reset_index()
    )
    pc_t = pc.assign(
        v=lambda x: (
            x["area_km2"].map("{:,.0f}".format)
            + " km2 ("
            + (100 * x["share_of_scope_area"]).round(1).astype(str)
            + "%)"
        )
    )
    pc_t = pc_t.pivot_table(
        index=["scope", "search_action"],
        columns="integration_policy",
        values="v",
        aggfunc="first",
        sort=False,
    ).reset_index()
    pc_t["scope"] = pc_t["scope"].map(NAMES)
    ax_t = axis[axis["scope"] == "AOI"].assign(
        v=lambda x: (100 * x["share_of_scope_area"]).round(1)
    )
    ax_t = ax_t.pivot_table(
        index=["axis", "value"], columns="stratum", values="v", aggfunc="first", sort=False
    ).reset_index()
    fam_t = (
        fam[fam["scope"] == "AOI"]
        .assign(v=lambda x: (100 * x["share_of_scope_area"]).round(1))
        .pivot_table(index="family", columns="action", values="v", sort=False)
        .fillna(0)
        .reset_index()
    )
    un_t = (
        unres.assign(v=lambda x: (100 * x["share_of_scope_area"]).round(1))
        .pivot_table(index="unresolved", columns="scope", values="v", sort=False)[list(NAMES)]
        .rename(columns=NAMES)
        .reset_index()
    )
    bu = (
        burden.assign(v=lambda x: (100 * x["share_of_scope_area"]).round(1))
        .pivot_table(index="verification_triggers", columns="scope", values="v", sort=False)[
            list(NAMES)
        ]
        .rename(columns=NAMES)
        .reset_index()
    )
    gates = pd.DataFrame([{"gate": g.upper(), "status": r.status} for g, r in qa.gates.items()])
    files = {
        p.name: p.stat().st_size
        for p in sorted(REVIEW.iterdir())
        if p.is_file() and p.name not in ("README.md", "file-sizes.json")
    }
    files |= {f"m1e/{p.name}": p.stat().st_size for p in sorted(OUT.iterdir()) if p.is_file()}
    lines = [
        TITLE,
        "",
        f"**Hazard integration {cfg.integration_version} - {cfg.status}; regional screening only; no scalar hazard score; no integration policy selected.** "
        f"Inputs: `hydrogeomorphic_profile = {d.hydrogeomorphic_profile}`, `flood_fusion_policy = {d.flood_fusion_policy}` "
        f"(`selected_for_provisional_screening = true`, `production_truth = false`) and the experimental M1D seismic evidence. "
        "Parcel/site hazard assessment is NOT complete and ground response is not assessed anywhere. "
        "Semantics: `docs/product/natural-hazard-integration.md`.",
        "",
        FINDINGS.read_text("utf-8"),
        "",
        "## Action areas by province (cells in the artifact; area / share of scope)",
        "",
        table(pa_t),
        "",
        "## Integrated action state",
        "",
        table(st_t),
        "",
        img("multiple-hazard-actions.png"),
        "",
        "## Regional search action under three integration policies",
        "",
        table(pc_t),
        "",
        "Cells whose search action differs between policies:",
        "",
        table(pdiff),
        "",
        img("natural-hazard-search-action.png"),
        "",
        "## Decision axes (AOI, % of stratum area; strata are reporting only)",
        "",
        table(ax_t),
        "",
        "Per-family recommended actions (AOI, % of area):",
        "",
        table(fam_t),
        "",
        "Verification triggers per cell (% of scope area; triggers >= 1 equals the area flagged VERIFY_SITE_REQUIRED):",
        "",
        table(bu),
        "",
        img("verification-burden.png"),
        "",
        img("engineering-mitigation.png"),
        "",
        "## Cross-family combinations",
        "",
        table(combos),
        "",
        table(comp),
        "",
        "Largest regions per combination:",
        "",
        table(reg),
        "",
        img("hydro-vs-seismic.png"),
        "",
        "## Unresolved evidence (% of scope area)",
        "",
        table(un_t),
        "",
        img("unresolved-hazard-evidence.png"),
        "",
        "## Parcel handoff profiles (cell action profile -> checklist; nothing is checked in M1E)",
        "",
        table(prof.head(12)),
        "",
        "Characterisation of hydrogeomorphic favourable + seismic strong: see `outputs/m1e-review/integration-statistics.json` "
        f"(area {stats['hydro_favourable_seismic_strong']['area_km2']:,.0f} km2).",
        "",
        "## Human QA",
        "",
        table(gates),
        "",
        "No review of the M1C-M1E map packs has been reported; none is inferred.",
        "",
        "## Files",
        "",
        "| File | Bytes |",
        "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in files.items()],
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    (REVIEW / "README.md").write_text(build(""), "utf-8")
    DOC.write_text(
        build("../../outputs/m1e-review/").replace(
            TITLE,
            TITLE
            + "\n\n> Committed copy of `outputs/m1e-review/README.md`; images and tables live in the untracked review folder.",
        ),
        "utf-8",
    )
    print("written")
