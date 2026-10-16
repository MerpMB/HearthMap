# ruff: noqa: E501
"""Descriptive statistics that always carry their denominator. Nothing here derives a threshold, class or score."""

from __future__ import annotations

import numpy as np
import pandas as pd

QUANTILES = (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)


def stat_with_denominator(
    values: np.ndarray,
    resolved: np.ndarray,
    area_w: np.ndarray,
    label: str,
    scope: str,
    column: str,
) -> dict[str, object]:
    """Median/quantiles over RESOLVED cells only, stating how many cells and how much area that is.

    ``values`` is NaN where a cell is unresolved; ``resolved`` marks cells the statistic covers; ``area_w`` is each cell's covered area
    (coverage_fraction x cell area). The row is explicit that the median is NOT an AOI-wide median.
    """
    ok = resolved & np.isfinite(values)
    n_total = len(values)
    v = values[ok]
    row: dict[str, object] = {
        "scope": scope,
        "column": column,
        "statistic_population": label,
        "cells_total": n_total,
        "cells_resolved": int(ok.sum()),
        "cells_unresolved": int(n_total - ok.sum()),
        "resolved_cell_share": round(float(ok.mean()), 4) if n_total else float("nan"),
        "area_total_km2": round(float(area_w.sum()), 1),
        "area_resolved_km2": round(float(area_w[ok].sum()), 1),
        "resolved_area_share": round(float(area_w[ok].sum() / area_w.sum()), 4)
        if area_w.sum()
        else float("nan"),
        "unresolved_area_share": round(float(1 - area_w[ok].sum() / area_w.sum()), 4)
        if area_w.sum()
        else float("nan"),
    }
    for q in QUANTILES:
        row[f"p{int(q * 100)}"] = round(float(np.quantile(v, q)), 3) if len(v) else float("nan")
    row["mean"] = round(float(v.mean()), 3) if len(v) else float("nan")
    row["max"] = round(float(v.max()), 3) if len(v) else float("nan")
    return row


def routable_median_label(column: str) -> str:
    """Name of the statistic population for a service-time column: it is never the AOI-wide median."""
    return (
        "MEDIAN_AMONG_ROUTABLE_CELLS_ONLY"
        if column.startswith("drive_time_to_nearest_service_")
        else "ALL_CELLS"
    )


def distribution_table(
    frame: pd.DataFrame,
    columns: list[str],
    scopes: dict[str, pd.Series],
    signal_only: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Quantile distributions per variable and scope for urban-core CALIBRATION REVIEW. No quantile is a threshold."""
    rows = []
    for scope, mask in scopes.items():
        for col in columns:
            for pop_label, m in (
                ("ALL_CELLS", mask),
                ("CELLS_WITH_NONZERO_VALUE", mask & (frame[col] > 0)),
            ):
                v = frame.loc[m, col].dropna()
                row = {"scope": scope, "column": col, "population": pop_label, "n_cells": len(v)}
                for q in QUANTILES:
                    row[f"p{int(q * 100)}"] = (
                        round(float(v.quantile(q)), 4) if len(v) else float("nan")
                    )
                row["max"] = round(float(v.max()), 4) if len(v) else float("nan")
                rows.append(row)
    return pd.DataFrame(rows)


def weighted_coverage(quantity: np.ndarray, routable: np.ndarray) -> dict[str, float]:
    """Share of a quantity (modelled people, built-up m2, area) in routable vs unresolved cells.

    Unresolved cells keep their quantity: it is never treated as zero. Cell-count, area, population and built-up coverage are
    different weightings and must not be conflated; this only ever weights by the quantity it is given.
    """
    q = np.nan_to_num(np.asarray(quantity, dtype=float), nan=0.0)
    total = float(q.sum())
    routed = float(q[routable].sum())
    unresolved = total - routed
    share = (unresolved / total) if total else float("nan")
    return {"total": total, "routable": routed, "unresolved": unresolved, "unresolved_share": share}
