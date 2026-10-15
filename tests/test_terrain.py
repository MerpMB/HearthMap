"""Slope derivation and support-aware zonal statistics on SYNTHETIC surfaces."""

from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from hearthmap.terrain import (
    clip_weights,
    horn_slope_degrees,
    pixel_cell_weights,
    weighted_cell_stats,
)

# ======================================================== slope


def test_flat_plane_has_zero_slope_and_nan_edges():
    s = horn_slope_degrees(np.full((6, 7), 450.0), 30.0, 30.0)
    assert np.allclose(s[1:-1, 1:-1], 0.0)
    assert np.isnan(s[0]).all() and np.isnan(s[-1]).all()
    assert np.isnan(s[:, 0]).all() and np.isnan(s[:, -1]).all()


@pytest.mark.parametrize("gradient", [0.05, 0.1, 0.5, 1.0, 3.0])
def test_constant_incline_east_matches_analytic_slope(gradient):
    dx = 29.3
    cols = np.arange(12)
    z = np.tile(gradient * cols * dx, (8, 1))
    s = horn_slope_degrees(z, dx, 30.9)
    assert np.allclose(s[1:-1, 1:-1], np.degrees(np.arctan(gradient)))


def test_incline_in_both_directions():
    dx, dy = 25.0, 31.0
    r, c = np.mgrid[0:9, 0:9]
    # row 0 is north; heights rise southward by 0.2 per metre and eastward by 0.1
    z = 0.1 * c * dx + 0.2 * r * dy
    s = horn_slope_degrees(z, dx, dy)
    assert np.allclose(s[1:-1, 1:-1], np.degrees(np.arctan(np.hypot(0.1, 0.2))))


def test_row_varying_geodesic_spacing_is_respected():
    rows, cols = 10, 10
    dx_rows = np.linspace(29.0, 30.0, rows)  # E-W spacing shrinks toward the pole
    z = 0.3 * np.arange(cols)[None, :] * dx_rows[:, None]
    # A huge N-S spacing makes the (artificial) between-row differences negligible,
    # isolating the per-row E-W spacing.
    s = horn_slope_degrees(z, dx_rows, 1e9)
    assert np.allclose(s[1:-1, 1:-1], np.degrees(np.arctan(0.3)))
    # Using a single wrong spacing would change the answer measurably
    wrong = horn_slope_degrees(z, 30.0, 1e9)
    assert not np.allclose(wrong[1:-1, 1:-1], s[1:-1, 1:-1])


def test_nodata_propagates_only_to_its_neighbourhood_without_infill():
    z = np.tile(0.2 * np.arange(10) * 30.0, (10, 1))
    z[5, 5] = np.nan
    s = horn_slope_degrees(z, 30.0, 30.0)
    assert np.isnan(s[4:7, 4:7]).all()
    assert np.isfinite(s[1:4, 1:-1]).all() and np.isfinite(s[7:-1, 1:-1]).all()


def test_slope_requires_ground_spacing():
    with pytest.raises(ValueError, match="ground distance"):
        horn_slope_degrees(np.zeros((3, 3)), 0.0, 30.0)


# ======================================================== zonal


def _pixels(x0, y0, n, size):
    xs, ys = np.meshgrid(x0 + size * (np.arange(n) + 0.5), y0 + size * (np.arange(n) + 0.5))
    return xs.ravel(), ys.ravel()


def test_aligned_pixels_give_exact_support():
    x, y = _pixels(0, 0, 10, 100.0)  # 1 km x 1 km of 100 m pixels over 500 m cells
    pi, c, r, w = pixel_cell_weights(x, y, 50.0, 50.0, 500.0)
    assert np.allclose(np.bincount(pi, weights=w), 1.0)
    cell = r * 2 + c
    st = weighted_cell_stats(cell, w, np.ones(len(pi)), n_cells=4, prefix="z")
    assert np.allclose(st["z_support_px"], 25.0)


def test_offset_pixels_split_weights_and_conserve_mass():
    x, y = _pixels(-50, -50, 11, 100.0)  # pixel edges no longer on cell edges
    pi, c, r, w = pixel_cell_weights(x, y, 50.0, 50.0, 500.0)
    assert np.allclose(np.bincount(pi, weights=w), 1.0)
    inside = (c >= 0) & (c <= 1) & (r >= 0) & (r <= 1)
    cell = r[inside] * 2 + c[inside]
    st = weighted_cell_stats(cell, w[inside], np.ones(inside.sum()), n_cells=4, prefix="z")
    assert np.allclose(st["z_support_px"], 25.0)  # 500x500 m / (100x100 m)


def test_weighted_quantiles_and_threshold_fractions():
    cell = np.zeros(4, int)
    w = np.array([0.1, 0.2, 0.3, 0.4])
    v = np.array([10.0, 20.0, 30.0, 40.0])
    st = weighted_cell_stats(
        cell, w, v, n_cells=1, quantiles=(0.5, 0.9), thresholds=(25,), prefix="s"
    )
    assert st.loc[0, "s_min"] == 10 and st.loc[0, "s_max"] == 40
    assert st.loc[0, "s_p50"] == 30.0  # cumulative 0.1,0.3,0.6 -> first >= 0.5
    assert st.loc[0, "s_p90"] == 40.0
    assert st.loc[0, "s_gt25_fraction"] == pytest.approx(0.7)


def test_nan_values_do_not_count_as_support():
    st = weighted_cell_stats(
        np.zeros(3, int), np.ones(3), np.array([1.0, np.nan, 3.0]), n_cells=1, prefix="z"
    )
    assert st.loc[0, "z_support_px"] == 2.0


def test_very_small_partial_cell_gets_weighted_support_not_centre_lookup():
    # A 500 m cell of which only a 12 m sliver is inside the AOI; 30 m pixels.
    x, y = _pixels(0, 0, 17, 30.0)
    pi, c, r, w = pixel_cell_weights(x, y, 15.0, 15.0, 500.0)
    sel = (c == 0) & (r == 0)
    pi, c, r, w = pi[sel], c[sel], r[sel], w[sel]
    piece = box(470, 0, 490, 500)  # 20 m wide sliver between pixel centres 465 and 495
    centres_inside = ((x > 470) & (x < 490)).sum()
    assert centres_inside == 0
    hw = np.full(len(x), 15.0)
    w2 = clip_weights(pi, np.zeros(len(pi), int), w, x, y, hw, hw, {0: piece})
    support = w2.sum()
    assert support == pytest.approx(20 * 500 / 900, rel=1e-6)  # 11.1 pixel-equivalents
    st = weighted_cell_stats(
        np.zeros(len(pi), int), w2, np.full(len(pi), 7.0), n_cells=1, prefix="z", min_support=1.0
    )
    assert st.loc[0, "z_p50"] == 7.0
    tiny = box(480, 0, 490, 1)  # 10 m2: support far below one pixel -> UNKNOWN
    w3 = clip_weights(pi, np.zeros(len(pi), int), w, x, y, hw, hw, {0: tiny})
    st3 = weighted_cell_stats(
        np.zeros(len(pi), int), w3, np.full(len(pi), 7.0), n_cells=1, prefix="z", min_support=1.0
    )
    assert st3.loc[0, "z_support_px"] < 1
    assert np.isnan(st3.loc[0, "z_p50"])


def test_pixels_larger_than_cells_rejected():
    with pytest.raises(ValueError):
        pixel_cell_weights(np.array([0.0]), np.array([0.0]), 300.0, 300.0, 500.0)
