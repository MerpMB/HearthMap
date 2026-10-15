"""Facility coordinate QA. Flags only: coordinates are NEVER corrected or moved."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def coordinate_flags(
    lon: pd.Series, lat: pd.Series, names: pd.Series, cfg: dict[str, Any],
    inside_aoi: pd.Series | None = None, inside_stated_province: pd.Series | None = None,
) -> pd.DataFrame:  # fmt: skip
    """Boolean flags per facility plus ``coordinate_qa_status`` (PASS / FLAGGED / FAILED)."""
    q = cfg["coordinate_qa"]
    x0, y0, x1, y1 = q["thailand_bbox"]
    lo, la = pd.to_numeric(lon, errors="coerce"), pd.to_numeric(lat, errors="coerce")
    f = pd.DataFrame(index=lon.index)
    f["MISSING_COORDINATE"] = lo.isna() | la.isna()
    f["ZERO_COORDINATE"] = (lo.fillna(1) == 0) | (la.fillna(1) == 0)
    outside = ~((lo >= x0) & (lo <= x1) & (la >= y0) & (la <= y1))
    swapped = (la >= x0) & (la <= x1) & (lo >= y0) & (lo <= y1) & outside
    f["SWAPPED_LAT_LON"] = swapped
    f["OUTSIDE_THAILAND"] = outside & ~f["MISSING_COORDINATE"] & ~f["ZERO_COORDINATE"]
    f["OUTSIDE_AOI"] = (
        (~inside_aoi.fillna(False)) & ~f["MISSING_COORDINATE"] if inside_aoi is not None else False
    )
    f["OUTSIDE_STATED_PROVINCE"] = (
        (~inside_stated_province.fillna(False)) & ~f["MISSING_COORDINATE"]
        if inside_stated_province is not None
        else False
    )
    key = lo.round(6).astype(str) + "|" + la.round(6).astype(str)
    valid = ~f["MISSING_COORDINATE"]
    distinct = (
        pd.DataFrame({"k": key[valid], "n": names[valid].astype(str)}).groupby("k")["n"].nunique()
    )
    f["DUPLICATE_COORDINATE_MULTI_INSTITUTION"] = (
        key.map(distinct).fillna(0) >= q["duplicate_coordinate_min_distinct_names"]
    )

    def dec(s: pd.Series) -> pd.Series:
        return s.dropna().map(
            lambda v: len(repr(float(v)).split(".")[1].rstrip("0")) if "." in repr(float(v)) else 0
        )

    d_lo, d_la = dec(lo).reindex(lo.index).fillna(99), dec(la).reindex(la.index).fillna(99)
    f["COARSE_PRECISION"] = (
        valid & (d_lo <= q["coarse_decimals_max"]) & (d_la <= q["coarse_decimals_max"])
    )
    hard = [
        "MISSING_COORDINATE",
        "ZERO_COORDINATE",
        "OUTSIDE_THAILAND",
        "SWAPPED_LAT_LON",
        "OUTSIDE_STATED_PROVINCE",
    ]
    soft = ["OUTSIDE_AOI", "DUPLICATE_COORDINATE_MULTI_INSTITUTION", "COARSE_PRECISION"]
    f["coordinate_qa_status"] = np.where(
        f[hard].any(axis=1), "FAILED", np.where(f[soft].any(axis=1), "FLAGGED", "PASS")
    )
    f["coordinate_qa_flags"] = [",".join(c for c in hard + soft if r[c]) for _, r in f.iterrows()]
    return f
