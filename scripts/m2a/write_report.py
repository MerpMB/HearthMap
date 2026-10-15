# ruff: noqa: E501
"""M2A: write the completion report from the generated statistics (numbers are read, not typed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

R = Path("outputs/m2a-review")


def tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(out)


def main() -> int:
    fs = json.loads((R / "facility-summary.json").read_text("utf-8"))
    ns = json.loads((R / "network-stats.json").read_text("utf-8"))
    val = json.loads((R / "osm-vs-drr-validation.json").read_text("utf-8"))
    td = pd.read_csv(R / "travel-time-distribution.csv")
    sens = pd.read_csv(R / "speed-sensitivity.csv")
    ctx = pd.read_csv(R / "infrastructure-context-statistics.csv")
    cnt = pd.read_csv(R / "facility-counts-by-province.csv")
    art = pd.read_parquet("outputs/m2a/family-infrastructure-evidence.parquet")
    snap = pd.read_csv(R / "facility-routing-snap.csv")
    aoi = td[td.scope == "AOI"][
        ["category", "resolved_share_pct", "p10_min", "median_min", "p90_min"]
    ]
    prov = td[
        (td.scope != "AOI") & td.category.isin(["primary_school", "secondary_school", "hospital"])
    ][["scope", "category", "resolved_share_pct", "median_min", "p90_min"]]
    unrouted = snap[~snap.routed].groupby("category").size().to_dict()
    ed, hl = fs["education"], fs["health"]
    lines = [
        "# HearthMap M2A - Family & Infrastructure Evidence Foundation: completion report",
        "",
        "Evidence only. No suitability score, no ranking of provinces or places, no 'best place for a family'.",
        "Natural Hazard scope statement carried: hazard outputs elsewhere are regional screening, not parcel/site safety.",
        "",
        "## 1. M1E accounting correction",
        "",
        "Done in M1E.1 (commits `aaee452`, `cc2e440`): the 86.1% flag (34,377 km2) and the 0/1/2/3 distribution described different",
        "populations. The seismic screening state alone also triggers verification (8,502 cells, 2,072 km2, 5.2%), which the",
        "old count omitted. Counts are now 'verification triggers' with flag == (triggers >= 1); policy and all action areas are",
        "unchanged; an invariant test guards it.",
        "",
        "## 2. Sources",
        "",
        "| Source | Status | Notes |",
        "|---|---|---|",
        "| DOPA gis-02 places (education) | VERIFIED, acquired | budget year 2564 (~2021) STALE; no authoritative level field; types derived |",
        "| DGA CITIZENinfo health facilities | VERIFIED, acquired | file dated 2020-03-14 STALE; government only; CC BY 4.0 |",
        "| DRR rural-highway FeatureServer | VERIFIED, acquired (validation only) | 390 links in envelope; not a routable network; not merged |",
        "| OSM Overpass extract (M1A) | used for routing | current (2026-10-15) |",
        "| MOE register (catalog.moe.go.th) | UNREACHABLE | connection refused; not verified |",
        "| MOPH hospital service levels | NOT FOUND | higher-level hospital DEFERRED |",
        "| PEA Power Map | NOT VERIFIED | no public machine-readable endpoint; no scraping attempted |",
        "| PWA service-area polygons | NOT FOUND | only province-level user/capacity tables |",
        "| NBTC coverage | REJECTED for grid | population-share aggregates, not spatial |",
        "| Ookla open data | DEFERRED | crowd-sourced, global files exceed the 250 MB guard, NC licence |",
        "",
        "## 3. Education",
        "",
        f"{ed['source_records_gov_office_2']:,} DOPA education-office records -> {ed['institutions_after_dedup']:,} institutions after deterministic de-duplication ({ed['merged_groups']} merge groups). Kinds: {json.dumps(ed['by_kind'])}.",
        f"Coordinate QA: {json.dumps(ed['qa_status'])} (flags only; coordinates never corrected; FAILED points are not routed). Freshness: {ed['freshness']['freshness_status']} ({ed['freshness']['age_years']} years).",
        "Levels are DERIVED from names and source sub-codes with basis/confidence; an unstated basic school defaults to PRIMARY at LOW confidence. No quality field exists.",
        "",
        "## 4. Healthcare",
        "",
        f"{hl['source_records_in_three_provinces']} government facilities in the three provinces; classes {json.dumps(hl['by_class'])}; QA {json.dumps(hl['qa_status'])}. Freshness {hl['freshness']['freshness_status']} ({hl['freshness']['age_years']} years).",
        "No emergency, trauma, specialty or service-level capability is assigned. `higher_level_hospital` is DEFERRED (empty reference list in `config/healthcare-reference-levels.yaml`).",
        "",
        "## 5. Routing",
        "",
        f"Own directed-graph prototype (decision in `docs/research/m2a-routing-decision.md`): {ns['nodes']:,} nodes, {ns['directed_edges']:,} directed edges, {ns['largest_component_share_of_nodes'] * 100:.1f}% of nodes in one connected component, {ns['oneway_ways']:,} one-way ways. No turn restrictions, traffic, weather or surface effects.",
        f"OSM vs official DRR: {val['within_50m_pct']}% of sampled DRR rural-highway points inside the AOI lie within 50 m of an OSM road ({val['drr_length_in_aoi_km']} km of DRR links).",
        "",
        "## 6. Accessibility (BASELINE_DRIVE_TIME, minutes; area-weighted over resolved cells)",
        "",
        tbl(aoi),
        "",
        "Per-province (descriptive, not a ranking):",
        "",
        tbl(prov),
        "",
        "Speed sensitivity (SLOW x0.75, BASE, FAST x1.25):",
        "",
        tbl(sens),
        "",
        f"Facilities not routed (snap > 1 km): {json.dumps(unrouted)}.",
        f"Unresolved cells stay NaN with a reason; {int((art['road_access_context'] == 'NO_ROAD_WITHIN_1KM').sum()):,} cells have no road within 1 km (mostly upland forest) - this is *unresolved*, not 'no access'.",
        "",
        "## 7. Electricity",
        "",
        "`electricity_service_potential = NOT_ASSESSED` everywhere; parcel verification always required. Classified as review/context evidence, never `PARCEL_ELECTRICITY_AVAILABLE`.",
        "",
        "## 8. Water",
        "",
        "`water_service_context = NON_PWA_OR_UNKNOWN_SERVICE` everywhere (no PWA polygons published); `water_service_verification_required` always true. This is not 'no water'; non-PWA areas are not penalised.",
        "",
        "## 9. Telecom",
        "",
        "DEFERRED: NBTC publishes population-share aggregates, not spatial coverage; province-level counts are not grid coverage.",
        "",
        "## 10. Data completeness",
        "",
        tbl(ctx.round(2)),
        "",
        "## 11. Artifacts",
        "",
        "`outputs/m2a/family-infrastructure-evidence.parquet` (+provenance), `data/processed/m2a/facilities.gpkg`, `data/processed/m2a/network.npz`, review maps and CSVs in `outputs/m2a-review/`.",
        "",
        "## 12-14. Tests, human QA, repository state",
        "",
        "Tests: see the commit message of the final build; `config/human-qa.yaml` keeps every existing gate unchanged and adds `m2a_human_visual_signoff: PENDING` (nothing reviewed, nothing inferred). Hazard actions are untouched and independent (tested).",
        "",
        "## 15. Requirements for M2B",
        "",
        "See `docs/product/m2b-requirements-sheet.md` (unfilled). Blocking evidence gaps: authoritative education levels (MOE register), hospital service levels/emergency capability, PEA/PWA/telecom spatial evidence, current (post-2021) facility data.",
        "",
    ]
    (R / "m2a-report.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("written", len(lines), "lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
