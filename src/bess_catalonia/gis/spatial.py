"""Reusable spatial operations. All metric operations require a projected CRS (EPSG:25831).

Methods (documented in docs/methodology.md):
* buffers           - Euclidean buffers around node points in the analysis CRS
* area in buffer    - planar area of (buffer ∩ layer union), m² -> ha
* points in buffer  - sum of a point attribute for points within ``radius`` of each node
* area-weighted sum - polygon attribute x share of the polygon's area inside each buffer
* nearest distance  - planar distance from each node to the nearest feature
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from shapely.geometry.base import BaseGeometry


class CRSError(ValueError):
    pass


def require_projected(gdf: gpd.GeoDataFrame, expected: str | None = None) -> None:
    if gdf.crs is None or not gdf.crs.is_projected:
        raise CRSError(f"Metric operation needs a projected CRS, got {gdf.crs}")
    if expected and gdf.crs != gpd.GeoSeries(crs=expected).crs:
        raise CRSError(f"Expected CRS {expected}, got {gdf.crs.to_string()}")


def add_lonlat(gdf: gpd.GeoDataFrame, geographic_crs: str = "EPSG:4326") -> gpd.GeoDataFrame:
    ll = gdf.geometry.to_crs(geographic_crs)
    gdf = gdf.copy()
    gdf["lon"] = ll.x.round(6)
    gdf["lat"] = ll.y.round(6)
    return gdf


def in_bbox(lon: pd.Series, lat: pd.Series, bbox: list[float]) -> pd.Series:
    min_lon, min_lat, max_lon, max_lat = bbox
    return lon.between(min_lon, max_lon) & lat.between(min_lat, max_lat)


def make_buffers(nodes: gpd.GeoDataFrame, radius_km: float, id_col: str = "node_id"):
    require_projected(nodes)
    # 64 segments per quarter circle: polygon area within 0.01% of the true circle
    # (shapely's default of 16 under-estimates by ~0.16%).
    geom = nodes.geometry.buffer(radius_km * 1000.0, quad_segs=64)
    return gpd.GeoDataFrame(nodes[[id_col]].copy(), geometry=geom, crs=nodes.crs)


def dissolve(layer: gpd.GeoDataFrame) -> BaseGeometry | None:
    if layer is None or layer.empty:
        return None
    return layer.geometry.union_all()


def area_in_buffers_m2(buffers: gpd.GeoDataFrame, geom: BaseGeometry | None) -> pd.Series:
    """Area (m²) of ``geom`` inside each buffer. ``geom`` should be pre-dissolved so
    overlapping source polygons are not double counted."""
    require_projected(buffers)
    if geom is None or geom.is_empty:
        return pd.Series(0.0, index=buffers.index)
    return buffers.geometry.intersection(geom).area


def sum_points_within(
    nodes: gpd.GeoDataFrame, points: gpd.GeoDataFrame, value_col: str, radius_km: float
) -> pd.Series:
    """Sum of ``value_col`` over points within ``radius_km`` of each node.

    Points may count towards several nodes (catchments overlap) - this is a context
    indicator, not an allocation. Null values are ignored; nodes with no points get 0.
    """
    require_projected(nodes)
    require_projected(points)
    if points.empty:
        return pd.Series(0.0, index=nodes.index)
    tree = STRtree(points.geometry.values)
    node_idx, pt_idx = tree.query(nodes.geometry.values, predicate="dwithin",
                                  distance=radius_km * 1000.0)
    values = points[value_col].to_numpy(dtype=float)
    sums = np.zeros(len(nodes))
    np.add.at(sums, node_idx, np.nan_to_num(values[pt_idx], nan=0.0))
    return pd.Series(sums, index=nodes.index)


def area_weighted_sum(
    buffers: gpd.GeoDataFrame, polygons: gpd.GeoDataFrame, value_col: str
) -> pd.Series:
    """Σ value · area(buffer ∩ polygon) / area(polygon) for each buffer.

    Assumes the attribute is spread uniformly over each polygon (e.g. municipal demand).
    Null values contribute nothing, so results are lower bounds where data is missing.
    """
    require_projected(buffers)
    require_projected(polygons)
    sums = np.zeros(len(buffers))
    if polygons.empty:
        return pd.Series(sums, index=buffers.index)
    polys = polygons.geometry.values
    tree = STRtree(polys)
    b_idx, p_idx = tree.query(buffers.geometry.values, predicate="intersects")
    inter = shapely.area(shapely.intersection(buffers.geometry.values[b_idx], polys[p_idx]))
    share = inter / shapely.area(polys[p_idx])
    values = np.nan_to_num(polygons[value_col].to_numpy(dtype=float)[p_idx], nan=0.0)
    np.add.at(sums, b_idx, values * share)
    return pd.Series(sums, index=buffers.index)


def nearest_distance_m(nodes: gpd.GeoDataFrame, features: gpd.GeoDataFrame) -> pd.Series:
    require_projected(nodes)
    if features is None or features.empty:
        return pd.Series(np.nan, index=nodes.index)
    tree = STRtree(features.geometry.values)
    idx = tree.nearest(nodes.geometry.values)
    nearest = features.geometry.values[idx]
    return pd.Series(nodes.geometry.distance(gpd.GeoSeries(nearest, index=nodes.index,
                                                           crs=nodes.crs)), index=nodes.index)


def within_distance(nodes: gpd.GeoDataFrame, geom: BaseGeometry | None, distance_m: float):
    if geom is None or geom.is_empty:
        return pd.Series(False, index=nodes.index)
    return nodes.geometry.distance(geom) <= distance_m
