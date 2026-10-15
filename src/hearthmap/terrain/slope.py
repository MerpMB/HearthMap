"""Slope derivation (documented in docs/architecture/terrain-methods.md).

Algorithm: Horn (1981) 3x3 finite differences.

    dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * dx)
    dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * dy)
    slope = degrees(arctan(sqrt(dz/dx^2 + dz/dy^2)))

with the 3x3 window   a b c / d e f / g h i   (row 0 = north).

* Units: input heights in metres, pixel spacing in metres, output in degrees.
* Pixel spacing: ``dx`` may vary per row (geodesic east-west spacing of a
  geographic grid shrinks with latitude); ``dy`` is the north-south spacing.
  Callers pass ground distances - slope is never computed in degree units.
* Nodata: if any of the 9 window cells is NaN the result is NaN (no infilling).
* Edges: the outermost rows/columns are NaN (no one-sided differences); callers
  read a halo so interior results are complete.
* No smoothing is applied.
"""

from __future__ import annotations

import numpy as np


def horn_slope_degrees(z: np.ndarray, dx: float | np.ndarray, dy: float) -> np.ndarray:
    z = np.asarray(z, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError("z must be 2-D")
    rows, cols = z.shape
    dx_arr = np.broadcast_to(np.asarray(dx, dtype=np.float64), (rows,)).reshape(rows, 1)
    if np.any(dx_arr <= 0) or dy <= 0:
        raise ValueError("pixel spacing must be positive ground distance in metres")
    out = np.full(z.shape, np.nan)
    if rows < 3 or cols < 3:
        return out
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx_arr[1:-1])
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * dy)
    with np.errstate(invalid="ignore"):
        out[1:-1, 1:-1] = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    centre_nan = np.isnan(z[1:-1, 1:-1])
    out[1:-1, 1:-1][centre_nan] = np.nan
    return out
