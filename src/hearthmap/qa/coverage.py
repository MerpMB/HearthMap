"""Grid area accounting with unambiguous terminology.

For a grid clipped against a boundary:

* ``raw_cell_footprint_area``  = n_cells * cell_area (includes overhang outside the boundary)
* ``clipped_coverage_area``    = sum(cell_area * coverage_fraction)
* ``boundary_area``            = area of the boundary polygon(s)
* ``edge_overhang_area``       = raw_cell_footprint_area - clipped_coverage_area
* ``coverage_difference``      = clipped_coverage_area - boundary_area   (should be ~0)

Invariant: ``|coverage_difference| <= abs_tol + rel_tol * boundary_area``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

DEFAULT_REL_TOL = 1e-9
DEFAULT_ABS_TOL_M2 = 1.0


@dataclass(frozen=True)
class CoverageAccounting:
    n_cells: int
    full_cells: int
    partial_cells: int
    cell_area_m2: float
    raw_cell_footprint_area_m2: float
    clipped_coverage_area_m2: float
    boundary_area_m2: float
    edge_overhang_area_m2: float
    coverage_difference_m2: float
    tolerance_m2: float
    invariant_ok: bool

    def as_km2(self) -> dict:
        out = {}
        for k, v in asdict(self).items():
            if k.endswith("_m2") and k != "cell_area_m2":
                out[k[:-3] + "_km2"] = round(v / 1e6, 6)
            else:
                out[k] = v
        return out


def coverage_accounting(
    coverage_fraction: np.ndarray,
    cell_size_m: float,
    boundary_area_m2: float,
    *,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol_m2: float = DEFAULT_ABS_TOL_M2,
    full_threshold: float = 1 - 1e-9,
) -> CoverageAccounting:
    frac = np.asarray(coverage_fraction, dtype=float)
    if np.any((frac < 0) | (frac > 1)) or np.any(~np.isfinite(frac)):
        raise ValueError("coverage_fraction must be finite and within [0, 1]")
    cell_area = float(cell_size_m) ** 2
    raw = len(frac) * cell_area
    clipped = float(frac.sum()) * cell_area
    tol = abs_tol_m2 + rel_tol * boundary_area_m2
    diff = clipped - boundary_area_m2
    return CoverageAccounting(
        n_cells=len(frac),
        full_cells=int((frac >= full_threshold).sum()),
        partial_cells=int(((frac > 0) & (frac < full_threshold)).sum()),
        cell_area_m2=cell_area,
        raw_cell_footprint_area_m2=raw,
        clipped_coverage_area_m2=clipped,
        boundary_area_m2=float(boundary_area_m2),
        edge_overhang_area_m2=raw - clipped,
        coverage_difference_m2=diff,
        tolerance_m2=tol,
        invariant_ok=abs(diff) <= tol,
    )
