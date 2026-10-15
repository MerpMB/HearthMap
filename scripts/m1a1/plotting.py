"""Small matplotlib helpers for the M1A.1 review figures (EPSG:32647, metres)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

CRS_NOTE = "Map units: EPSG:32647 (WGS 84 / UTM 47N), metres."
NICE = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000]


def scalebar(ax, *, frac: float = 0.25, loc: tuple[float, float] = (0.04, 0.04)) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    target = (x1 - x0) * frac
    length = max(n for n in NICE if n <= target) if target >= NICE[0] else NICE[0]
    bx = x0 + (x1 - x0) * loc[0]
    by = y0 + (y1 - y0) * loc[1]
    h = (y1 - y0) * 0.012
    half = length / 2
    ax.add_patch(Rectangle((bx, by), half, h, facecolor="black", edgecolor="black", zorder=20))
    ax.add_patch(
        Rectangle((bx + half, by), half, h, facecolor="white", edgecolor="black", zorder=20)
    )
    label = f"{length / 1000:g} km" if length >= 1000 else f"{length:g} m"
    ax.text(bx, by + h * 1.6, "0", fontsize=7, zorder=21)
    ax.text(
        bx + length,
        by + h * 1.6,
        label,
        fontsize=7,
        ha="right",
        zorder=21,
        bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1},
    )


def clean_axes(ax, title: str | None = None) -> None:
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    if title:
        ax.set_title(title, fontsize=9)


def window(ax, cx: float, cy: float, half_m: float) -> None:
    ax.set_xlim(cx - half_m, cx + half_m)
    ax.set_ylim(cy - half_m, cy + half_m)


def grid_image(grid, values: np.ndarray, cell: float = 500.0):
    """Rasterise per-cell values of an aligned grid into (array, extent) for imshow."""
    cols = grid["col"].to_numpy()
    rows = grid["row"].to_numpy()
    c0, r0 = cols.min(), rows.min()
    arr = np.full((rows.max() - r0 + 1, cols.max() - c0 + 1), np.nan)
    arr[rows - r0, cols - c0] = values
    extent = (c0 * cell, (cols.max() + 1) * cell, r0 * cell, (rows.max() + 1) * cell)
    return arr, extent


def save(
    fig,
    path: Path,
    source: str,
    tag: str = "HearthMap M1A.1 review - descriptive QA, not a suitability map.",
) -> None:
    # Wrap to the figure width so a long caption never widens the saved canvas.
    width_chars = max(int(fig.get_figwidth() * 19), 80)
    caption = textwrap.fill(f"Source: {source}  |  {CRS_NOTE}  |  {tag}", width=width_chars)
    fig.text(0.005, 0.003, caption, fontsize=6.5, color="#333333", va="top")
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
