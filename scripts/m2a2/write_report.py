# ruff: noqa: E501
"""M2A.2 completion report from generated artifacts (numbers are read, not typed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

R = Path("outputs/m2a2-review")
MANUAL = Path("data/manual")


def tbl(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in r) + " |")
    return "\n".join(out)


def main() -> int:
    h = json.loads((R / "health-refresh-summary.json").read_text("utf-8"))
    chg = pd.read_csv(R / "accessibility-change-summary.csv")
    aoi = chg[
        (chg.stratum == "AOI")
        & chg.category.isin(["primary_health_unit", "hospital", "higher_level_hospital"])
    ][
        [
            "category",
            "resolved_both_km2",
            "newly_resolved_km2",
            "nearest_changed_pct",
            "median_old_min",
            "median_new_min",
            "median_change_min",
            "p95_change_min",
        ]
    ]
    low = chg[
        (chg.stratum == "ROAD_WITHIN_500M_AND_LOW_SLOPE_LE_5")
        & chg.category.isin(["primary_health_unit", "hospital"])
    ][["category", "nearest_changed_pct", "median_old_min", "median_new_min", "median_change_min"]]
    prov = chg[
        chg.stratum.isin(["TH50", "TH56", "TH57"])
        & chg.category.isin(["hospital", "higher_level_hospital"])
    ][
        [
            "category",
            "stratum",
            "median_old_min",
            "median_new_min",
            "median_change_min",
            "newly_resolved_km2",
        ]
    ]
    edu = chg[
        (chg.stratum == "AOI")
        & chg.category.isin(["kindergarten", "primary_school", "secondary_school"])
    ][["category", "nearest_changed_pct"]]
    supplied = (
        sorted(
            p.parent.name + "/" + p.name
            for p in MANUAL.glob("*/*")
            if p.is_file() and p.name != "MANIFEST.yaml"
        )
        if MANUAL.exists()
        else []
    )
    qa = {p.stem: json.loads(p.read_text("utf-8")) for p in R.glob("manual-import-*.json")}
    freeze = json.loads((R / "routing-freeze-evidence.json").read_text("utf-8"))
    lines = [
        "# HearthMap M2A.2 - Manual-Assisted Facility Refresh: completion report",
        "",
        "Evidence only. No scalar family/infrastructure score, no ranking. Natural Hazard scope statement carried: hazard outputs are regional screening, not parcel/site safety.",
        "",
        "## 1. Manual sources received",
        "",
        f"Files supplied by the project user in `data/manual/`: **{'; '.join(supplied) if supplied else 'none'}**."
        + (" Import QA reports: " + ", ".join(qa) + "." if qa else ""),
        "No MOE workbook and no HCODE export were available, so nothing was imported manually; the import path, manifest contract and validators are in place and tested on synthetic workbooks.",
        "",
        "Source states (registry `source_state`):",
        "",
        "| Source | State | Acquisition path |",
        "|---|---|---|",
        "| MOE current school register | SOURCE_EXISTS_AGENT_BLOCKED | manual import: `data/manual/moe-register-current/` |",
        "| MoPH HCODE | SOURCE_EXISTS_AGENT_BLOCKED (browser challenge, not bypassed) | manual import: `data/manual/moph-hcode-export/` |",
        "| MoPH public hospital point layer (update68, update69) | SOURCE_EXISTS_AGENT_ACCESSIBLE | automated public ArcGIS query, acquired |",
        "",
        "## 2. Education",
        "",
        "Unchanged from M2A.1: primary layer = DOPA 2021 (stale fallback), OBEC 2020 = authoritative classification for matched schools, OSM = cross-check. The MOE register is **not** treated as unavailable; it is awaiting a manual file. When supplied it is imported with `scripts/m2a2/import_manual.py`, which checks schema, duplicate official ids, missing/invalid coordinates, province mismatch, stale internal dates and AOI coverage before anything is used.",
        "",
        tbl(edu.assign(note="no change: education layer unchanged in M2A.2")),
        "",
        "## 3. Healthcare: current location vs classification freshness",
        "",
        f"Primary = MoPH public hospital point layer `Hospital_update68` (service last edited {h['location_vintage']['max_source_last_edited']}; record dates by year {json.dumps(h['location_vintage']['record_dates_by_year'])}). {h['primary_layer']['records']} AOI records, {h['primary_layer']['service_points']} service points, {h['primary_layer']['non_service_points']} administrative offices (kept, not routed), {h['primary_layer']['inactive']} inactive.",
        f"Classes from the source typecode/level (not names): {json.dumps(h['classes'], ensure_ascii=False)}. Basis: {json.dumps(h['class_basis'])}. Classification freshness: {json.dumps(h['classification_freshness'])}; hybrid fallbacks to the 2020 class: {h['hybrid_fallback_records']}.",
        f"Higher-level (source typecode 'โรงพยาบาลศูนย์'): {', '.join(h['higher_level_hospitals'])}. Large general hospitals are not promoted. **No emergency, trauma, ICU or specialist capability is stated or assigned.**",
        f"Cross-checks: vs MoPH update69 {json.dumps(h['update68_vs_update69'])}; vs CITIZENinfo 2020 match rate {h['vs_citizeninfo']['match_rate_pct']}% (matched {h['vs_citizeninfo']['current_side_matched']}, possible {h['vs_citizeninfo']['current_side_possible_match']}, conflict {h['vs_citizeninfo']['current_side_conflict']}, MoPH-only {h['vs_citizeninfo']['current_side_current_only']}, CITIZENinfo-only {h['vs_citizeninfo']['legacy_side_only']}, class changes {h['class_changes_vs_citizeninfo_matched']}); vs OSM match rate {h['vs_osm']['match_rate_pct']}%.",
        f"Coordinate QA {json.dumps(h['coordinate_qa'])}. **The layer's point geometry and its lat/lon attributes disagree by more than 100 m for {h['geometry_vs_attribute_conflicts_over_threshold']} records**; the geometry is used (it agrees better with an independent source) and the conflict is flagged, never silently resolved.",
        "",
        "## 4. Accessibility changes (routing frozen; previous = M2A.1 artifact)",
        "",
        f"Routing fingerprint `{freeze['routing_config_fingerprint']}` on every cell; road columns identical; `BASELINE_DRIVE_TIME`.",
        "",
        tbl(aoi),
        "",
        "Residential-lowland stratum (connected road within 500 m, median slope <= 5 deg; reporting only):",
        "",
        tbl(low),
        "",
        "Province (descriptive, not a ranking):",
        "",
        tbl(prov),
        "",
        "Higher-level-hospital access is new (it was deferred): cells beyond the 120-minute search limit or without road access stay unresolved.",
        "",
        "## 5. Remaining limitations",
        "",
        "* Education stays on stale 2021/2020 sources until the MOE register is imported; about half of schools and all non-school institutions have derived levels.",
        "* MoPH layer is a public GIS layer, not HCODE: no capability fields, no licence statement, most records dated 2023.",
        "* Hospital service level is available only as the source's type/level code; capability is not assessed.",
        "* Government facilities only (no private hospitals/clinics).",
        "* Electricity NOT_ASSESSED; water NON_PWA_OR_UNKNOWN_SERVICE; telecom DEFERRED (parcel verification concerns).",
        "",
        "## 6. Readiness",
        "",
        "Healthcare: current MoPH location and source classification acquired and cross-checked (criterion B met; higher-level hospital resolved from the source's own type field). Education: **no current MOE register was supplied or validated**, so the education criterion is not met.",
        "",
        "FACILITY_REFRESH_REQUIRES_MANUAL_SOURCE",
        "",
    ]
    (R / "m2a2-report.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("report written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
