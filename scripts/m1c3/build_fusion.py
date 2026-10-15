"""M1C.3: source-aware flood ledger, flood-fusion candidates and the flood x profile matrix.

Inputs (all existing, nothing re-acquired):
  outputs/m1c2-review/common-period-cell-comparison.parquet   per-cell annual fractions
  outputs/m1c1/evidence/hazard-evidence.parquet                M1B evidence (landslide, terrain)

Outputs: outputs/m1c3/ (long ledger, diagnostics) and outputs/m1c3-review/ (tables).
No flood candidate and no hydrogeomorphic profile is selected.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import CANONICAL, PROCESSED, PROVINCE_NAMES, source_ref

from hearthmap.enums import Confidence
from hearthmap.hazard import apply_policy, connected_components, load_policy_config
from hearthmap.hazard.flood_fusion import (
    OBSERVED_YEAR_COUNT_DEFINITION,
    YEARS,
    build_ledger,
    evaluate_candidate,
    ledger_long,
    ledger_summary,
    load_fusion_config,
    slope_stratum,
    tabulate,
    to_policy_override,
)
from hearthmap.provenance import ProvenanceRecord, current_code_version

OUT = Path("outputs/m1c3")
REVIEW = Path("outputs/m1c3-review")
M1C2 = Path("outputs/m1c2-review/common-period-cell-comparison.parquet")
EVIDENCE = Path("outputs/m1c1/evidence/hazard-evidence.parquet")
BASELINE = "V021_CURRENT_ONLY_REFERENCE"  # the profile's own flood rule (policy 0.2.1)
PROFILES = ["CONSERVATIVE", "BALANCED", "PERMISSIVE"]
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
LADDER = [
    "NO_MAJOR_OBSERVED_SIGNAL",
    "HISTORICAL_SIGNAL",
    "REQUIRES_FLOOD_VERIFICATION",
    "STRONG_FLOOD_SCREENING_CONCERN",
    "UNRESOLVED",
]
STRATA = {
    "ALL": None,
    "LOW_SLOPE_LE_5": ["LOW_SLOPE_LE_5"],
    "GENTLE_5_15": ["GENTLE_5_15"],
    "LOW_OR_GENTLE_LE_15": ["LOW_SLOPE_LE_5", "GENTLE_5_15"],
    "STEEP_GT_15": ["STEEP_GT_15"],
    "UNKNOWN": ["UNKNOWN"],
}
CHUNK = 20000


def log(m: str) -> None:
    print(m, flush=True)


def scope_masks(pcode: np.ndarray) -> dict[str, np.ndarray]:
    return {"AOI": np.ones(len(pcode), bool)} | {p: pcode == p for p in ("TH50", "TH56", "TH57")}


def pair_matrix(a: np.ndarray, b: np.ndarray, area: np.ndarray, order: list[str], **keys):
    rows = []
    for x in order:
        for y in order:
            sel = (a == x) & (b == y)
            if sel.any():
                rows.append(
                    {
                        **keys,
                        "from": x,
                        "to": y,
                        "cells": int(sel.sum()),
                        "area_km2": round(float(area[sel].sum()), 2),
                    }
                )
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    fcfg, pcfg = load_fusion_config(), load_policy_config()
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    tab = pd.read_parquet(M1C2)
    ev = pd.read_parquet(EVIDENCE)
    if (
        not (tab["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all()
        or not (ev["cell_id"].to_numpy() == grid["cell_id"].to_numpy()).all()
    ):
        raise ValueError("cell order differs between grid, M1C.2 table and M1B evidence")
    n = len(grid)
    area = ev["clipped_area_km2"].to_numpy()
    pcode = grid["majority_pcode"].to_numpy()
    masks = scope_masks(pcode)
    strat = slope_stratum(
        ev["slope_p90_deg"].to_numpy(),
        ev["terrain_support_px"].to_numpy(),
        tuple(fcfg.stratification.slope_p90_bands_deg),
    )

    # ------------------------------------------------ ledger
    led = build_ledger(tab, fcfg.presence_min_fraction)
    log("ledger built")
    summ = ledger_summary(led, fcfg.reference_year)
    summ.insert(0, "clipped_area_km2", area)
    summ.insert(0, "majority_pcode", pcode)
    summ.insert(0, "cell_id", grid["cell_id"].to_numpy())
    summ["slope_stratum_reporting_only"] = strat
    summ.to_parquet(REVIEW / "flood-ledger-summary.parquet", index=False)
    writer = None
    for a in range(0, n, CHUNK):
        sl = slice(a, min(a + CHUNK, n))
        part = ledger_long(
            type(led)(
                led.years,
                led.presence_min,
                led.legacy[sl],
                led.current[sl],
                led.intersection[sl],
                led.legacy_only[sl],
                led.current_only[sl],
                led.observed[sl],
                led.state[sl],
                led.sources_positive[sl],
            ),
            grid["cell_id"].iloc[sl],
        )
        t = pa.Table.from_pandas(part, preserve_index=False)
        writer = writer or pq.ParquetWriter(OUT / "flood-ledger-long.parquet", t.schema)
        writer.write_table(t)
    writer.close()
    log("ledger long written")

    # per-year state areas (map + report table)
    ys = []
    for j, y in enumerate(YEARS):
        s = led.state[:, j]
        for st in sorted(set(s)):
            m = s == st
            ys.append(
                {
                    "year": y,
                    "state": st,
                    "cells": int(m.sum()),
                    "area_km2": round(float(area[m].sum()), 2),
                    "observed_fraction_area_km2": round(
                        float((led.observed[m, j] * area[m]).sum()), 2
                    ),
                }
            )
    pd.DataFrame(ys).to_csv(OUT / "ledger-by-year.csv", index=False)

    # ------------------------------------------------ flood candidates
    cands = list(fcfg.candidates)
    results = {c: evaluate_candidate(led, fcfg, c) for c in cands}
    ladder = {c: results[c].state for c in cands}
    comp_rows = []
    for c in cands:
        t = tabulate(ladder[c], area, masks, LADDER)
        t.insert(0, "flood_policy", c)
        comp_rows.append(t)
    comp = pd.concat(comp_rows, ignore_index=True)
    comp["province"] = comp["scope"].map(PROVINCE_NAMES).fillna("AOI")
    comp.to_csv(REVIEW / "flood-policy-comparison.csv", index=False)
    # lowland / slope strata of the flood ladder (reporting only)
    srows = []
    for sname, vals in STRATA.items():
        sm = np.ones(n, bool) if vals is None else np.isin(strat, vals)
        for c in cands:
            t = tabulate(ladder[c], area, {sname: sm}, LADDER)
            t.insert(0, "flood_policy", c)
            srows.append(t)
    pd.concat(srows).rename(columns={"scope": "stratum"}).to_csv(
        OUT / "flood-ladder-by-stratum.csv", index=False
    )
    # transitions between flood candidates
    tr = []
    for a, b in itertools.combinations(cands, 2):
        tr += pair_matrix(ladder[a], ladder[b], area, LADDER, from_policy=a, to_policy=b)
    pd.DataFrame(tr).to_csv(OUT / "flood-policy-transitions.csv", index=False)
    # reason-code frequency per candidate
    rc = []
    for c in cands:
        s = pd.Series(["|".join(r) for r in results[c].reason_codes]).str.split("|").explode()
        s = s[s != ""]
        for code, k in s.value_counts().items():
            rc.append({"flood_policy": c, "reason_code": code, "cells": int(k)})
    pd.DataFrame(rc).to_csv(OUT / "flood-reason-code-counts.csv", index=False)
    log("candidates evaluated")

    # ------------------------------------------------ rule-family sensitivity (A-D)
    fam = []

    def add(family, rule, metric, years, k, f, hit):
        for scope, m in masks.items():
            sel = hit & m
            fam.append(
                {
                    "family": family,
                    "rule": rule,
                    "metric": metric,
                    "years": f"{years[0]}-{years[1]}",
                    "min_years": k,
                    "min_cell_fraction": f,
                    "scope": scope,
                    "province": PROVINCE_NAMES.get(scope, "AOI"),
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 2),
                    "share_of_area": round(float(area[sel].sum() / area[m].sum()), 4),
                }
            )

    def hits(metric, a, b, k, f):
        mat = led.metric(metric)[:, led.window(a, b)]
        with np.errstate(invalid="ignore"):
            return ((mat >= f - 1e-12).sum(axis=1)) >= k

    for k in (1, 2, 3):
        for f in (0.05, 0.10, 0.25, 0.50):
            add(
                "A_RECENT_RECURRENCE",
                f">= {k} yrs @ {f}",
                "observed_fraction",
                (2017, 2023),
                k,
                f,
                hits("observed_fraction", 2017, 2023, k, f),
            )
            add(
                "B_COMMON_PERIOD_CONSENSUS",
                f">= {k} yrs @ {f}",
                "intersection_fraction",
                (2011, 2016),
                k,
                f,
                hits("intersection_fraction", 2011, 2016, k, f),
            )
    for k in (1, 2):
        for f in (0.01, 0.05, 0.10, 0.25, 0.50):
            add(
                "C_LEGACY_HISTORICAL_SIGNAL",
                f">= {k} yrs @ {f}",
                "observed_fraction",
                (2005, 2010),
                k,
                f,
                hits("observed_fraction", 2005, 2010, k, f),
            )
    for f in (0.01, 0.05, 0.10, 0.25, 0.50):
        add(
            "D_PRODUCT_DISAGREEMENT",
            f"mismatch >= {f} in any year",
            "mismatch_fraction",
            (2011, 2016),
            1,
            f,
            hits("mismatch_fraction", 2011, 2016, 1, f),
        )
    pd.DataFrame(fam).to_csv(OUT / "rule-family-sensitivity.csv", index=False)

    # ------------------------------------------------ hydrogeomorphic matrix
    policies = [BASELINE, *cands]
    status: dict[tuple[str, str], np.ndarray] = {}
    interp: dict[tuple[str, str], np.ndarray] = {}
    for fp in policies:
        ov = None if fp == BASELINE else to_policy_override(results[fp])
        for prof in PROFILES:
            r = apply_policy(ev, pcfg, prof, ov)
            status[(fp, prof)] = r["regional_search_status"].to_numpy()
            interp[(fp, prof)] = r["flood_policy_level"].to_numpy()
            log(f"policy {fp} x {prof}")
    mrows = []
    for (fp, prof), st in status.items():
        t = tabulate(st, area, masks, STATUSES)
        t.insert(0, "profile", prof)
        t.insert(0, "flood_policy", fp)
        mrows.append(t)
    matrix = pd.concat(mrows, ignore_index=True)
    matrix["province"] = matrix["scope"].map(PROVINCE_NAMES).fillna("AOI")
    matrix.to_csv(REVIEW / "policy-matrix.csv", index=False)
    long_rows = pd.DataFrame(
        {
            "cell_id": np.tile(grid["cell_id"].to_numpy(), len(status)),
            "flood_policy": np.repeat([k[0] for k in status], n),
            "profile": np.repeat([k[1] for k in status], n),
            "regional_search_status": np.concatenate(list(status.values())),
            "flood_policy_level": np.concatenate(list(interp.values())),
        }
    )
    long_rows.to_parquet(OUT / "policy-results-long.parquet", index=False)
    # transitions of overall status between flood policies (per profile)
    ptr = []
    pairs = [(BASELINE, c) for c in cands] + list(itertools.combinations(cands, 2))
    for prof in PROFILES:
        for a, b in pairs:
            ptr += pair_matrix(
                status[(a, prof)],
                status[(b, prof)],
                area,
                STATUSES,
                profile=prof,
                from_policy=a,
                to_policy=b,
            )
    pd.DataFrame(ptr).to_csv(OUT / "policy-transitions.csv", index=False)

    # ------------------------------------------------ stability: flood choice vs profile choice
    def differs(stats: list[np.ndarray]) -> np.ndarray:
        stack = np.vstack(stats)
        return (stack != stack[0]).any(axis=0)

    stab = {
        "aoi_area_km2": float(area.sum()),
        "by_profile_flood_choice": {},
        "by_flood_policy_profile_choice": {},
    }
    pair_rows = []
    for prof in PROFILES:
        d3 = differs([status[(c, prof)] for c in cands])
        d4 = differs([status[(c, prof)] for c in policies])
        stab["by_profile_flood_choice"][prof] = {
            "area_differs_across_3_candidates_km2": round(float(area[d3].sum()), 1),
            "share": round(float(area[d3].sum() / area.sum()), 4),
            "area_differs_incl_reference_km2": round(float(area[d4].sum()), 1),
        }
    for c in policies:
        d = differs([status[(c, p)] for p in PROFILES])
        stab["by_flood_policy_profile_choice"][c] = {
            "area_differs_across_3_profiles_km2": round(float(area[d].sum()), 1),
            "share": round(float(area[d].sum() / area.sum()), 4),
        }
    for prof in PROFILES:
        for a, b in itertools.combinations(cands, 2):
            ch = status[(a, prof)] != status[(b, prof)]
            pair_rows.append(
                {
                    "axis": "flood_choice",
                    "held_fixed": prof,
                    "a": a,
                    "b": b,
                    "area_km2": round(float(area[ch].sum()), 1),
                }
            )
    for c in cands:
        for a, b in itertools.combinations(PROFILES, 2):
            ch = status[(c, a)] != status[(c, b)]
            pair_rows.append(
                {
                    "axis": "profile_choice",
                    "held_fixed": c,
                    "a": a,
                    "b": b,
                    "area_km2": round(float(area[ch].sum()), 1),
                }
            )
    pairs_df = pd.DataFrame(pair_rows)
    pairs_df.to_csv(OUT / "stability-pairwise-area.csv", index=False)
    stab["mean_pairwise_changed_area_km2"] = {
        ax: round(float(g["area_km2"].mean()), 1) for ax, g in pairs_df.groupby("axis")
    }
    stab["max_pairwise_changed_area_km2"] = {
        ax: round(float(g["area_km2"].max()), 1) for ax, g in pairs_df.groupby("axis")
    }
    all9 = [status[(c, p)] for c in cands for p in PROFILES]
    d9 = differs(all9)
    stab["share_of_area_identical_across_all_9_combinations"] = round(
        float(1 - area[d9].sum() / area.sum()), 4
    )
    stab["reference_vs_candidates_changed_km2"] = {
        f"{prof}:{c}": round(float(area[status[(BASELINE, prof)] != status[(c, prof)]].sum()), 1)
        for prof in PROFILES
        for c in cands
    }

    # ------------------------------------------------ lowland sensitivity (reporting only)
    flood_sens = {prof: differs([status[(c, prof)] for c in cands]) for prof in PROFILES}
    flood_sens_any = np.logical_or.reduce(list(flood_sens.values()))
    ladder_diff = differs([ladder[c] for c in cands])
    lrows = []
    totals = {}

    def measure(name, mask_changed):
        totals[name] = float(area[mask_changed].sum())

    measures = {"flood_ladder_differs_across_candidates": ladder_diff}
    for prof in PROFILES:
        measures[f"overall_status_differs_across_flood_candidates:{prof}"] = flood_sens[prof]
    measures["overall_status_differs_across_flood_candidates:any_profile"] = flood_sens_any
    for c in cands:
        measures[f"overall_status_differs_across_profiles:{c}"] = differs(
            [status[(c, p)] for p in PROFILES]
        )
    for name, ch in measures.items():
        measure(name, ch)
    for sname, vals in STRATA.items():
        sm = np.ones(n, bool) if vals is None else np.isin(strat, vals)
        s_area = float(area[sm].sum())
        for name, ch in measures.items():
            a = float(area[sm & ch].sum())
            lrows.append(
                {
                    "stratum": sname,
                    "measure": name,
                    "stratum_area_km2": round(s_area, 1),
                    "stratum_share_of_aoi": round(s_area / area.sum(), 4),
                    "changed_area_km2": round(a, 1),
                    "changed_cells": int((sm & ch).sum()),
                    "share_of_stratum_changed": round(a / s_area, 4) if s_area else None,
                    "share_of_all_changed_in_stratum": round(a / totals[name], 4)
                    if totals[name]
                    else None,
                    "disproportion_ratio": round((a / totals[name]) / (s_area / area.sum()), 3)
                    if totals[name] and s_area
                    else None,
                }
            )
    pd.DataFrame(lrows).to_csv(REVIEW / "lowland-policy-sensitivity.csv", index=False)

    # ------------------------------------------------ sensitive regions
    idx = np.flatnonzero(flood_sens_any)
    lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
    comp_area = np.bincount(lab, weights=area[idx])
    sizes = np.bincount(lab)
    cent = grid.geometry.centroid.to_crs("EPSG:4326")
    rows = []
    for rank, k in enumerate(np.argsort(comp_area)[::-1][:25], 1):
        m = idx[lab == k]
        trip = pd.Series(
            [
                "/".join(
                    s[:3] for s in (ladder[cands[0]][i], ladder[cands[1]][i], ladder[cands[2]][i])
                )
                for i in m
            ]
        )
        rows.append(
            {
                "rank": rank,
                "area_km2": round(float(comp_area[k]), 2),
                "cells": int(sizes[k]),
                "lon": round(float(cent.x.iloc[m].mean()), 3),
                "lat": round(float(cent.y.iloc[m].mean()), 3),
                "majority_province": PROVINCE_NAMES.get(pd.Series(pcode[m]).mode().iloc[0], "?"),
                "share_low_slope_le_5": round(float((strat[m] == "LOW_SLOPE_LE_5").mean()), 3),
                "share_low_or_gentle_le_15": round(
                    float(np.isin(strat[m], ["LOW_SLOPE_LE_5", "GENTLE_5_15"]).mean()), 3
                ),
                "median_elev_m_dsm": round(float(np.median(ev["elev_median_m"].to_numpy()[m])), 1),
                "share_product_disagreement": round(
                    float(summ["has_overlap_product_disagreement"].to_numpy()[m].mean()), 3
                ),
                "share_older_only_evidence": round(
                    float(
                        (
                            (summ["legacy_era_observed_years"].to_numpy()[m] > 0)
                            & (summ["overlap_consensus_observed_years"].to_numpy()[m] == 0)
                            & (summ["current_era_observed_years"].to_numpy()[m] == 0)
                        ).mean()
                    ),
                    3,
                ),
                "share_recent_evidence": round(
                    float((summ["current_era_observed_years"].to_numpy()[m] > 0).mean()), 3
                ),
                "median_observed_years": float(
                    np.median(summ["observed_year_count_total"].to_numpy()[m])
                ),
                "most_common_ladder_triple_CP_AS_UC": trip.mode().iloc[0],
                "balanced_status_by_candidate": " / ".join(
                    pd.Series(status[(c, "BALANCED")][m]).mode().iloc[0] for c in cands
                ),
            }
        )
    pd.DataFrame(rows).to_csv(REVIEW / "policy-sensitive-regions.csv", index=False)
    cnt = {
        "cells_flood_sensitive_any_profile": int(flood_sens_any.sum()),
        "area_km2": round(float(area[flood_sens_any].sum()), 1),
        "components": len(comp_area),
        "isolated_single_cells": int((sizes == 1).sum()),
        "largest_component_km2": round(float(comp_area.max()), 1),
        "share_area_in_largest_10": round(
            float(np.sort(comp_area)[::-1][:10].sum() / comp_area.sum()), 4
        ),
    }
    stab["sensitive_regions"] = cnt
    stab["flood_ladder_differs_km2"] = round(float(area[ladder_diff].sum()), 1)

    # ------------------------------------------------ statistics, provenance
    stats = {
        "fusion_version": fcfg.fusion_version,
        "presence_min_fraction": fcfg.presence_min_fraction,
        "reference_year": fcfg.reference_year,
        "observed_year_count_definition": OBSERVED_YEAR_COUNT_DEFINITION,
        "observed_year_count_distribution_cells": {
            str(k): int(v)
            for k, v in summ["observed_year_count_total"].value_counts().sort_index().items()
        },
        "cells_with_any_observation": int((summ["observed_year_count_total"] > 0).sum()),
        "cells_with_overlap_disagreement": int(summ["has_overlap_product_disagreement"].sum()),
        "most_recent_band_cells": summ["most_recent_observed_band"].value_counts().to_dict(),
        "strata_area_km2": {
            s: round(float(area[strat == s].sum()), 1)
            for s in ("LOW_SLOPE_LE_5", "GENTLE_5_15", "STEEP_GT_15", "UNKNOWN")
        },
        "stability": stab,
    }
    (OUT / "fusion-statistics.json").write_text(json.dumps(stats, indent=2) + "\n", "utf-8")
    rec = ProvenanceRecord(
        artifact_id="m1c3-flood-fusion",
        artifact_path=(REVIEW / "flood-ledger-summary.parquet").as_posix(),
        code_version=current_code_version(),
        sources=[
            source_ref("flood-gistda-repeated-2005-2016", original_crs="EPSG:3857"),
            source_ref("flood-gistda-history", original_crs="EPSG:4326"),
        ],
        normalized_crs=CANONICAL,
        method="Per-cell annual source-native flooded fractions of two GISTDA products "
        "(2005-2010 legacy only, 2011-2016 both, 2017-2023 current only) from the M1C.2 exact "
        "vector overlays; source-aware agreement states; positive-only candidate flood "
        f"ladders per config/flood-fusion.yaml {fcfg.fusion_version} ({fcfg.status}).",
        spatial_resolution="500 m cells; legacy 1:50k; current 20 m",
        confidence=Confidence.LOW,
        limitations=[
            "Raw observational ledger, NOT a homogeneous 19-year series: the publisher documents "
            "no imagery, classification, cloud handling, minimum mapping unit or generalisation.",
            "observed_year_count_total is a count of mapped years, not a probability.",
            "Absence of a polygon is not evidence of no flood risk; no candidate is selected.",
            "Slope strata are for reporting only and never a suitability criterion.",
        ],
    )
    rec.write_sidecar(REVIEW / "flood-ledger-summary.parquet")
    log(json.dumps({"stability": stab}, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
