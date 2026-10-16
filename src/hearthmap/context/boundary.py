# ruff: noqa: E501
"""Boundary context for accessibility: distance to the AOI boundary, exit times, and destination-catalogue completeness.

Four extents are different things and must never be used interchangeably:

ORIGIN_EXTENT               where analytical origins are (AOI analysis points)
NETWORK_EXTENT              where the routing graph reaches (it extends beyond the AOI, so routes can cross borders)
DESTINATION_CATALOG_EXTENT  where the facility/POI catalogue has records (currently the three provinces / the AOI)
FEATURE_CONTEXT_EXTENT      where context features (factories, quarries, nightlife) were extracted (currently the three provinces)

The completeness state below is parameter-free: an outside-catalogue destination must be reached by first leaving the AOI, so it can only beat
the catalogued nearest destination when leaving the AOI is faster than reaching that destination. Nothing is invented and no value is corrected.
"""

from __future__ import annotations

import numpy as np
import shapely

COMPLETE_WITHIN_AVAILABLE_CATALOG = "COMPLETE_WITHIN_AVAILABLE_CATALOG"
BOUNDARY_LIMITED = "BOUNDARY_LIMITED"
SOURCE_COMPLETENESS_UNKNOWN = "SOURCE_COMPLETENESS_UNKNOWN"
COMPLETENESS_STATES = (
    COMPLETE_WITHIN_AVAILABLE_CATALOG,
    BOUNDARY_LIMITED,
    SOURCE_COMPLETENESS_UNKNOWN,
)

EXTENT_CONCEPTS = (
    "ORIGIN_EXTENT",
    "NETWORK_EXTENT",
    "DESTINATION_CATALOG_EXTENT",
    "FEATURE_CONTEXT_EXTENT",
)


def aoi_boundary_distance_m(
    points_xy: np.ndarray, aoi: shapely.Geometry, step_m: float = 100.0
) -> np.ndarray:
    """Euclidean distance from each point to the AOI boundary, via a densified boundary vertex tree (error about half of ``step_m``)."""
    b = shapely.segmentize(shapely.boundary(aoi), step_m)
    verts = shapely.points(shapely.get_coordinates(b))
    tree = shapely.STRtree(verts)
    idx = tree.query_nearest(shapely.points(points_xy), return_distance=True, all_matches=False)
    out = np.empty(len(points_xy))
    out[idx[0][0]] = idx[1]
    return out


def exit_node_masks(
    node_xy: np.ndarray, aoi: shapely.Geometry, thailand: shapely.Geometry
) -> tuple[np.ndarray, np.ndarray]:
    """(domestic_exit, international_exit): network nodes outside the AOI that are inside / outside Thailand.

    Cross-province movement inside Thailand is ordinary; movement into Myanmar or Laos involves crossings, legal limits and hours and is not
    ordinary accessibility. The two are kept apart.
    """
    in_aoi = shapely.contains_xy(aoi, node_xy[:, 0], node_xy[:, 1])
    in_th = shapely.contains_xy(thailand, node_xy[:, 0], node_xy[:, 1])
    return ~in_aoi & in_th, ~in_aoi & ~in_th


def completeness_state(
    time_to_catalog_destination_min: np.ndarray,
    time_to_domestic_exit_min: np.ndarray,
    origin_routable: np.ndarray,
) -> np.ndarray:
    """Destination-catalogue completeness per cell for one destination category.

    * origin not routable -> SOURCE_COMPLETENESS_UNKNOWN (no route is evaluated at all)
    * a domestic exit from the AOI is reachable faster than the nearest catalogued destination, or no catalogued destination is reachable while a
      domestic exit is -> BOUNDARY_LIMITED (an outside destination could be nearer; the catalogue cannot see it)
    * otherwise -> COMPLETE_WITHIN_AVAILABLE_CATALOG (no outside destination can be nearer than the catalogued one; this is relative to the
      catalogue, never an absolute completeness claim about OSM or the registers)
    * no catalogued destination and no domestic exit reachable -> SOURCE_COMPLETENESS_UNKNOWN
    """
    t_cat = np.asarray(time_to_catalog_destination_min, dtype=float)
    t_exit = np.asarray(time_to_domestic_exit_min, dtype=float)
    cat_ok, exit_ok = np.isfinite(t_cat), np.isfinite(t_exit)
    out = np.full(len(t_cat), SOURCE_COMPLETENESS_UNKNOWN, dtype=object)
    out[origin_routable & cat_ok & ~(exit_ok & (t_exit < t_cat))] = (
        COMPLETE_WITHIN_AVAILABLE_CATALOG
    )
    out[origin_routable & exit_ok & (~cat_ok | (t_exit < t_cat))] = BOUNDARY_LIMITED
    return out
