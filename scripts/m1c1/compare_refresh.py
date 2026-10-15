"""M1C.1: old (2005-2016) vs refreshed (2011-2023) flood evidence and policy outcomes.

Baseline = the M1B evidence and M1C v0.1.0 policy results snapshotted from commit
1d9a15c (data/interim/m1c1/baseline-m1c-1d9a15c). Refreshed = outputs/m1c1/evidence
and outputs/m1c1/policy. Differences are described, not judged: newer data is not
assumed to be more correct.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "m1a"))
from common import PROCESSED, PROVINCE_NAMES

from hearthmap.hazard import connected_components

BASE = Path("data/interim/m1c1/baseline-m1c-1d9a15c")
NEW_EV = Path("outputs/m1c1/evidence")
NEW_POL = Path("outputs/m1c1/policy")
OUT = Path("outputs/m1c1")
STATUSES = [
    "NO_MAJOR_CONCERN_DETECTED",
    "REQUIRES_VERIFICATION",
    "STRONG_REGIONAL_CONCERN",
    "REGIONAL_DEPRIORITIZE",
    "UNRESOLVED",
]
PROFILES = ["CONSERVATIVE", "BALANCED", "PERMISSIVE"]
TIER_RANK = {"NONE_DETECTED": 0, "CAUTION": 1, "HIGH": 2}
FLOOD_CHANGE = [
    "CONSISTENT_NO_MAJOR_SIGNAL",
    "CONSISTENT_CONCERN",
    "NEWER_DATA_INCREASES_CONCERN",
    "NEWER_DATA_DECREASES_CONCERN",
    "NOT_DIRECTLY_COMPARABLE",
]
STATUS_RANK = {s: i for i, s in enumerate(STATUSES[:4])}


def flood_change(old_tier: pd.Series, new_tier: pd.Series) -> np.ndarray:
    """Categorical comparison of the two records' own provisional flood tiers.

    Both tiers mean the same thing relative to their record ('>= 10% of the cell
    observed flooded in >= 3 of the record's years', any observed flooding, or
    observed flooding within 250 m), so they are comparable as concern levels;
    the records differ in length (12 vs 13 years), period, sensor and scale.
    A cell is NOT_DIRECTLY_COMPARABLE when either record did not evaluate it.
    """
    o = old_tier.map(TIER_RANK)
    n = new_tier.map(TIER_RANK)
    out = np.select(
        [
            o.isna() | n.isna(),
            (o == 0) & (n == 0),
            o == n,
            n > o,
            n < o,
        ],
        FLOOD_CHANGE[4:5] + FLOOD_CHANGE[:4],
        "NOT_DIRECTLY_COMPARABLE",
    )
    return out


def scope_masks(df: pd.DataFrame) -> dict[str, pd.Series]:
    return {"AOI": pd.Series(True, index=df.index)} | {
        p: df["majority_pcode"] == p for p in ("TH50", "TH56", "TH57")
    }


def largest_regions(grid, mask: np.ndarray, area: np.ndarray, label: str, n: int = 10):
    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return [], {"set": label, "cells": 0, "components": 0}
    lab = connected_components(grid["col"].to_numpy()[idx], grid["row"].to_numpy()[idx])
    comp_area = np.bincount(lab, weights=area[idx])
    sizes = np.bincount(lab)
    cent = grid.geometry.centroid.to_crs("EPSG:4326")
    rows = []
    for rank, k in enumerate(np.argsort(comp_area)[::-1][:n], 1):
        m = idx[lab == k]
        rows.append(
            {
                "set": label,
                "rank": rank,
                "area_km2": round(float(comp_area[k]), 2),
                "cells": int(sizes[k]),
                "lon": round(float(cent.x.iloc[m].mean()), 3),
                "lat": round(float(cent.y.iloc[m].mean()), 3),
                "majority_province": PROVINCE_NAMES.get(
                    grid["majority_pcode"].iloc[m].mode().iloc[0], "?"
                ),
            }
        )
    summary = {
        "set": label,
        "cells": len(idx),
        "area_km2": round(float(area[idx].sum()), 2),
        "components": len(comp_area),
        "isolated_single_cells": int((sizes == 1).sum()),
        "largest_component_km2": round(float(comp_area.max()), 2),
    }
    return rows, summary


def main() -> int:
    grid = gpd.read_file(PROCESSED / "grid.gpkg", layer="analysis_grid_500m")
    old = pd.read_parquet(BASE / "hazard-evidence.parquet").set_index("cell_id")
    new = pd.read_parquet(NEW_EV / "hazard-evidence.parquet").set_index("cell_id")
    old, new = old.loc[grid["cell_id"]], new.loc[grid["cell_id"]]
    area = new["clipped_area_km2"].to_numpy()
    masks = scope_masks(new.reset_index())
    stats: dict = {}

    # ------------------------------------------------ source footprints (area)
    def fp(frac):
        return round(float((frac.fillna(0).to_numpy() * area).sum()), 1)

    stats["flooded_area_km2"] = {
        "legacy_2005_2016_any": fp(old["flood_area_fraction"]),
        "legacy_2005_2016_ge3_of_12_years": fp(old["flood_freq_ge3_area_fraction"]),
        "refreshed_2011_2023_any": fp(new["flood_area_fraction"]),
        **{
            f"refreshed_2011_2023_ge{k}_of_13_years": fp(new[f"flood_years_ge{k}_area_fraction"])
            for k in (2, 3, 4, 5)
        },
        "legacy_recomputed_in_refresh_any": fp(new["legacy_flood_2005_2016_area_fraction"]),
    }
    # the legacy columns in the refreshed table must reproduce the baseline exactly
    stats["legacy_reproduced_max_abs_diff"] = float(
        (
            new["legacy_flood_2005_2016_years_ge3_area_fraction"]
            - old["flood_freq_ge3_area_fraction"]
        )
        .abs()
        .max()
    )
    o_any = old["flood_area_fraction"] > 0
    n_any = new["flood_area_fraction"] > 0
    stats["cells_with_any_observed_flood"] = {
        "legacy_only": int((o_any & ~n_any).sum()),
        "refreshed_only": int((~o_any & n_any).sum()),
        "both": int((o_any & n_any).sum()),
        "neither": int((~o_any & ~n_any).sum()),
    }

    # ------------------------------------------------ flood change classes
    cls = flood_change(old["flood_tier"], new["flood_tier"])
    fc = pd.DataFrame(
        {
            "cell_id": grid["cell_id"],
            "majority_pcode": grid["majority_pcode"],
            "clipped_area_km2": area,
            "flood_tier_2005_2016": old["flood_tier"].to_numpy(),
            "flood_tier_2011_2023": new["flood_tier"].to_numpy(),
            "flood_ge3_fraction_2005_2016": old["flood_freq_ge3_area_fraction"].to_numpy(),
            "flood_ge3_fraction_2011_2023": new["flood_years_ge3_area_fraction"].to_numpy(),
            "flood_change_class": cls,
        }
    )
    fc.to_parquet(OUT / "flood-change-cells.parquet", index=False)
    rows = []
    for scope, m in masks.items():
        for c in FLOOD_CHANGE:
            sel = m.to_numpy() & (cls == c)
            rows.append(
                {
                    "scope": scope,
                    "province": PROVINCE_NAMES.get(scope, "AOI"),
                    "flood_change_class": c,
                    "cells": int(sel.sum()),
                    "area_km2": round(float(area[sel].sum()), 2),
                    "share_of_area": round(float(area[sel].sum() / area[m.to_numpy()].sum()), 4),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "flood-change-summary.csv", index=False)
    tt = pd.crosstab(fc["flood_tier_2005_2016"], fc["flood_tier_2011_2023"])
    stats["flood_tier_transition_cells"] = {
        a: {b: int(tt.loc[a, b]) for b in tt.columns} for a in tt.index
    }
    reg_rows, reg_sum = [], []
    for c in ("NEWER_DATA_INCREASES_CONCERN", "NEWER_DATA_DECREASES_CONCERN"):
        r, s = largest_regions(grid, cls == c, area, c)
        reg_rows += r
        reg_sum.append(s)
    pd.DataFrame(reg_rows).to_csv(OUT / "flood-change-largest-regions.csv", index=False)
    stats["flood_change_regions"] = reg_sum

    # ------------------------------------------------ M1B evidence refresh
    for h in ("landslide", "terrain"):
        same = (old[f"{h}_tier"] == new[f"{h}_tier"]).all()
        stats[f"{h}_tiers_unchanged"] = bool(same)
    ev = []
    for col in ("flood_state", "overall_state"):
        t = pd.crosstab(old[col], new[col], values=area, aggfunc="sum").fillna(0)
        c = pd.crosstab(old[col], new[col])
        for a in c.index:
            for b in c.columns:
                if c.loc[a, b]:
                    ev.append(
                        {
                            "field": col,
                            "before": a,
                            "after": b,
                            "cells": int(c.loc[a, b]),
                            "area_km2": round(float(t.loc[a, b]), 2),
                        }
                    )
    pd.DataFrame(ev).to_csv(OUT / "evidence-refresh-transitions.csv", index=False)
    stats["evidence_overall_changed"] = {
        "cells": int((old["overall_state"] != new["overall_state"]).sum()),
        "area_km2": round(
            float(area[(old["overall_state"] != new["overall_state"]).to_numpy()].sum()), 2
        ),
    }
    stats["evidence_completeness_mean"] = {
        "before": float(old["evidence_completeness"].mean()),
        "after": float(new["evidence_completeness"].mean()),
    }

    # ------------------------------------------------ policy refresh
    po = pd.read_parquet(BASE / "policy-results.parquet")
    pn = pd.read_parquet(NEW_POL / "policy-results.parquet")
    dist_rows, trans_rows, chg_sum, chg_regions = [], [], {}, []
    for prof in PROFILES:
        a = po[po["policy_profile"] == prof].set_index("cell_id").loc[grid["cell_id"]]
        b = pn[pn["policy_profile"] == prof].set_index("cell_id").loc[grid["cell_id"]]
        sa, sb = a["regional_search_status"].to_numpy(), b["regional_search_status"].to_numpy()
        for scope, m in masks.items():
            mm = m.to_numpy()
            for st in STATUSES:
                oa, nb = mm & (sa == st), mm & (sb == st)
                dist_rows.append(
                    {
                        "profile": prof,
                        "scope": scope,
                        "province": PROVINCE_NAMES.get(scope, "AOI"),
                        "status": st,
                        "cells_before": int(oa.sum()),
                        "cells_after": int(nb.sum()),
                        "cells_delta": int(nb.sum() - oa.sum()),
                        "area_km2_before": round(float(area[oa].sum()), 2),
                        "area_km2_after": round(float(area[nb].sum()), 2),
                        "area_km2_delta": round(float(area[nb].sum() - area[oa].sum()), 2),
                    }
                )
        for x in STATUSES:
            for y in STATUSES:
                sel = (sa == x) & (sb == y)
                if sel.any():
                    trans_rows.append(
                        {
                            "profile": prof,
                            "before": x,
                            "after": y,
                            "cells": int(sel.sum()),
                            "area_km2": round(float(area[sel].sum()), 2),
                        }
                    )
        changed = sa != sb
        ra = pd.Series(sa).map(STATUS_RANK).to_numpy()
        rb = pd.Series(sb).map(STATUS_RANK).to_numpy()
        up = changed & (rb > ra)
        down = changed & (rb < ra)
        chg_sum[prof] = {
            "cells_changed": int(changed.sum()),
            "area_changed_km2": round(float(area[changed].sum()), 2),
            "share_of_aoi_area": round(float(area[changed].sum() / area.sum()), 4),
            "more_concern_cells": int(up.sum()),
            "more_concern_km2": round(float(area[up].sum()), 2),
            "less_concern_cells": int(down.sum()),
            "less_concern_km2": round(float(area[down].sum()), 2),
            "to_or_from_unresolved_cells": int((changed & ~up & ~down).sum()),
            "changed_cells_with_flood_level_change": int(
                (
                    changed
                    & (a["flood_policy_level"].to_numpy() != b["flood_policy_level"].to_numpy())
                ).sum()
            ),
            "by_province_km2": {
                PROVINCE_NAMES[p]: round(
                    float(area[changed & (grid["majority_pcode"] == p).to_numpy()].sum()), 2
                )
                for p in ("TH50", "TH56", "TH57")
            },
        }
        for label, mk in (("MORE_CONCERN", up), ("LESS_CONCERN", down)):
            r, s = largest_regions(grid, mk, area, f"{prof}:{label}", n=5)
            chg_regions += r
            chg_sum[prof][f"{label.lower()}_regions"] = s
    pd.DataFrame(dist_rows).to_csv(OUT / "policy-refresh-distribution.csv", index=False)
    pd.DataFrame(trans_rows).to_csv(OUT / "policy-refresh-transitions.csv", index=False)
    pd.DataFrame(chg_regions).to_csv(OUT / "policy-refresh-largest-changes.csv", index=False)
    stats["policy_change"] = chg_sum
    stats["policy_versions"] = {
        "before": str(po["policy_version"].iloc[0]),
        "after": str(pn["policy_version"].iloc[0]),
    }
    (OUT / "refresh-statistics.json").write_text(json.dumps(stats, indent=2) + "\n", "utf-8")
    print(
        json.dumps(
            {k: v for k, v in stats.items() if k != "flood_tier_transition_cells"}, indent=1
        )[:6000]
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
