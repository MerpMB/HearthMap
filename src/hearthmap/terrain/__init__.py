"""Terrain derivation and support-aware zonal statistics (M1B)."""

from hearthmap.terrain.slope import horn_slope_degrees
from hearthmap.terrain.zonal import clip_weights, pixel_cell_weights, weighted_cell_stats

__all__ = ["clip_weights", "horn_slope_degrees", "pixel_cell_weights", "weighted_cell_stats"]
