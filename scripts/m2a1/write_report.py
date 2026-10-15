# ruff: noqa: E501
"""M2A.1: completion report from the generated artifacts (numbers are read, not typed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

R = Path("outputs/m2a1-review")


def tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(out)


def main() -> int:
    s = json.loads((R / "facility-refresh-summary.json").read_text("utf-8"))
    c = s["classification"]
    chg = pd.read_csv(R / "accessibility-change-summary.csv")
    aoi = chg[chg.stratum == "AOI"][["category", "nearest_changed_pct", "median_old_min", "median_new_min", "median_change_min", "p05_change_min", "p95_change_min", "newly_resolved_km2"]]
    low = chg[chg.stratum == "ROAD_WITHIN_500M_AND_LOW_SLOPE_LE_5"][["category", "resolved_both_km2", "nearest_changed_pct", "median_old_min", "median_new_min", "median_change_min"]]
    prov = chg[chg.stratum.isin(["TH50", "TH56", "TH57"]) & chg.category.isin(["kindergarten", "secondary_school"])][["category", "stratum", "nearest_changed_pct", "median_old_min", "median_new_min", "median_change_min"]]
    sens = pd.read_csv(R / "obec-only-union-sensitivity.csv")
    qa = pd.read_csv(R / "facility-coordinate-qa-counts.csv")
    big = pd.read_csv(R / "accessibility-largest-changes.csv").sort_values("change_min").head(6)[["category", "province", "old_min", "new_min", "change_min"]]
    freeze = json.loads((R / "routing-freeze-evidence.json").read_text("utf-8"))
    log = json.loads((R / "source-access-log.json").read_text("utf-8"))
    lines = [
        "# HearthMap M2A.1 - Education & Healthcare Source Refresh: completion report",
        "",
        "Evidence only. No scalar family/infrastructure score, no ranking. Natural Hazard scope statement carried: hazard outputs are regional screening, not parcel/site safety.",
        "",
        "## Headline",
        "",
        "The current MOE register and the MoPH HCODE data could **not** be acquired lawfully from this environment, so the primary layers remain the stale DOPA 2021 (education) and CITIZENinfo 2020 (health) fallbacks. A different official source (OBEC school list, academic year 2563) supplies authoritative levels for half the schools and OSM (2026) validates staleness.",
        "",
        "## 1. Education refresh",
        "",
        "Source access attempts (no authentication or bot challenge bypassed):",
        "",
        tbl(pd.DataFrame(log)[["name", "http_status", "error", "note"]].fillna("").assign(error=lambda d: d["error"].str[:60])),
        "",
        f"* MOE register: **not acquired** (https refused / unresolved; plain http serves an empty CKAN instance). Role if acquired: PRIMARY; DOPA would become HISTORICAL/VALIDATION. The role and reconciliation machinery (`compose_primary`, `reconcile`) is in place; a loader for the register is still to be written.",
        f"* OBEC_SCHOOL_007 (academic year 2563, 2020): MOE code, class min/max, school type, 4-decimal coordinates; {s['obec_records_in_aoi']} schools in the AOI; QA {json.dumps(s['obec_qa'])}. Role AUTHORITATIVE_CLASSIFICATION (stale).",
        f"* Classification, schools: authoritative **{c['schools_authoritative']}**, derived **{c['schools_derived']}** (of which {c['schools_derived_default_primary_low']} default to PRIMARY at LOW confidence), unknown {c['schools_unknown']}; in M2A all {c['m2a_baseline_schools_derived']} school levels were derived. {c['level_sets_changed_vs_m2a']} institutions changed level set.",
        f"* All institutions (incl. early-childhood centres, colleges, learning resources): authoritative {c['all_authoritative']}, derived/unknown {c['all_derived_or_unknown']} of {c['all_institutions']}. Early-childhood, vocational and university levels remain name-derived (OBEC covers schools only).",
        "",
        "## 2. Healthcare refresh",
        "",
        "* HCODE (`hcode.moph.go.th`): HTTP 403 and a Cloudflare bot-challenge page; **not bypassed**; whether hospital_level is public or permission-gated could not be inspected. `opendata.moph.go.th` is the HDC statistics service, not a facility register.",
        "* The 2026 'GIS HEALTH' coordinate dataset on data.go.th is a **provincial** (Amnat Charoen) publication, outside the AOI: rejected as national truth.",
        "* Primary remains CITIZENinfo (2020-03-14, stale, government only). Facility classes unchanged: primary health unit / hospital of unspecified level / specialised. **Hospital level: PARTIALLY_ASSESSED**; higher-level hospital stays deferred; no emergency, trauma, ICU or specialist capability is assigned.",
        "",
        "## 3. Source reconciliation (statuses with retained evidence in the CSVs)",
        "",
        tbl(pd.DataFrame([{"comparison": k, **{kk: vv for kk, vv in s[k].items() if kk != 'current_side_legacy_only'}} for k in ("education_obec", "education_osm", "health_osm")])),
        "",
        f"DOPA vs OBEC: schools matched {s['education_obec']['current_side_matched']} ({s['education_obec']['match_rate_pct']}%), possible {s['education_obec']['current_side_possible_match']}, coordinate conflicts {s['obec_coordinate_conflicts']}, OBEC-only {s['obec_only_schools']}. OSM comparisons: current-only means a current OSM object with no stale-register counterpart (it may be an unregistered, private or new facility); stale-only means no OSM counterpart (it is not evidence of closure). {s['osm_other_clinics_out_of_scope']} OSM clinics/doctors are outside the government-register scope.",
        "",
        "Coordinate QA by source (flags only; nothing corrected; FAILED points are excluded from routing):",
        "",
        tbl(qa),
        "",
        "## 4. Accessibility impact (routing frozen)",
        "",
        f"Routing assumptions are unchanged: config fingerprint `{freeze['routing_config_fingerprint']}` on every cell, road-derived columns identical to M2A, `BASELINE_DRIVE_TIME`.",
        "",
        "AOI, cells resolved in both runs (area-weighted):",
        "",
        tbl(aoi),
        "",
        "Residential-lowland stratum (connected road within 500 m and median slope <= 5 deg; reporting stratum only):",
        "",
        tbl(low),
        "",
        "Province (descriptive, not a ranking):",
        "",
        tbl(prov),
        "",
        "Largest reductions:",
        "",
        tbl(big),
        "",
        "Primary-school and healthcare access are essentially unchanged; kindergarten and secondary-school access changed substantially because authoritative class ranges show many OBEC schools serve kindergarten and lower-secondary grades that name inference had assigned to PRIMARY only. Shorter time is not higher quality.",
        "",
        "Sensitivity - adding the OBEC-only schools (2020, not unioned into the layer):",
        "",
        tbl(sens),
        "",
        "## 5. Remaining uncertainty",
        "",
        "* Primary education and health layers are STALE (2021 / 2020); no current-only register records can be added until MOE/MoPH data is obtained.",
        "* About half of schools and all non-school institutions still have derived levels; private, local-authority and vocational schools are not in OBEC.",
        "* Hospital service level and emergency capability are not assessed.",
        "",
        "## 6. Utilities (unchanged)",
        "",
        "Electricity = NOT_ASSESSED / parcel verification required; water outside verified evidence = NON_PWA_OR_UNKNOWN_SERVICE; telecom = DEFERRED.",
        "",
        "## 7. M2B readiness",
        "",
        "Criteria asked for a current-enough primary source for education and healthcare. Neither was acquirable here, so the readiness criteria are **not met**; the refresh produced authoritative classification and a quantified staleness picture, and put the source-role and reconciliation machinery in place for the official registers.",
        "",
        "FACILITY_REFRESH_REQUIRES_CORRECTION",
        "",
    ]
    (R / "m2a1-report.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("report written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
