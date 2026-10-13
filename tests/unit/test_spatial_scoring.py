"""CRS transformations, buffers, intersections, areas, aggregation and scoring."""

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, box

from bess_catalonia.gis import spatial
from bess_catalonia.scoring.model import normalise, score_scenario

CRS = "EPSG:25831"


def nodes_at(*xy):
    return gpd.GeoDataFrame({"node_id": [f"N{i}" for i in range(len(xy))]},
                            geometry=[Point(x, y) for x, y in xy], crs=CRS)


def test_crs_transformation_barcelona():
    # Plaça de Catalunya, Barcelona - approx. ETRS89 / UTM 31N coordinates
    p = gpd.GeoSeries([Point(2.1700, 41.3870)], crs="EPSG:4326").to_crs(CRS).iloc[0]
    assert p.x == pytest.approx(430_550, abs=300) and p.y == pytest.approx(4_582_200, abs=300)
    back = spatial.add_lonlat(gpd.GeoDataFrame(geometry=[p], crs=CRS))
    assert back["lon"].iloc[0] == pytest.approx(2.17, abs=1e-6)


def test_metric_operations_require_projected_crs():
    with pytest.raises(spatial.CRSError):
        spatial.make_buffers(nodes_at((2.0, 41.0)).set_crs("EPSG:4326", allow_override=True), 5)


def test_buffer_area():
    buf = spatial.make_buffers(nodes_at((400_000, 4_600_000)), 5)
    assert buf.area.iloc[0] == pytest.approx(math.pi * 5000**2, rel=1e-3)


def test_area_in_buffer_and_shares():
    nodes = nodes_at((0, 0), (100_000, 0))
    buf = spatial.make_buffers(nodes, 1)
    half_plane = box(0, -2000, 2000, 2000)  # covers exactly half the first buffer
    area = spatial.area_in_buffers_m2(buf, half_plane)
    assert area.iloc[0] == pytest.approx(math.pi * 1e6 / 2, rel=1e-3)
    assert area.iloc[1] == 0
    assert spatial.area_in_buffers_m2(buf, None).eq(0).all()


def test_dissolve_prevents_double_counting():
    layer = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10), box(5, 0, 15, 10)], crs=CRS)
    assert spatial.dissolve(layer).area == 150


def test_points_within_and_area_weighted_sum():
    nodes = nodes_at((0, 0))
    pts = gpd.GeoDataFrame({"mw": [5.0, np.nan, 7.0]},
                           geometry=[Point(500, 0), Point(800, 0), Point(5000, 0)], crs=CRS)
    assert spatial.sum_points_within(nodes, pts, "mw", 1).iloc[0] == 5.0
    polys = gpd.GeoDataFrame({"mwh": [100.0]}, geometry=[box(0, -5000, 10_000, 5000)], crs=CRS)
    buf = spatial.make_buffers(nodes, 1)
    share = (math.pi * 1e6 / 2) / 1e8
    assert spatial.area_weighted_sum(buf, polys, "mwh").iloc[0] == pytest.approx(
        100 * share, rel=1e-3)


def test_nearest_distance_and_within():
    nodes = nodes_at((0, 0), (0, 3000))
    roads = gpd.GeoDataFrame(geometry=[LineString([(-10, 1000), (10, 1000)])], crs=CRS)
    d = spatial.nearest_distance_m(nodes, roads)
    assert d.tolist() == pytest.approx([1000, 2000])
    assert spatial.within_distance(nodes, roads.geometry.iloc[0], 1500).tolist() == [True, False]


INDICATORS = {
    "a": {"direction": "higher_better", "normalization": "minmax", "missing": "reweight"},
    "b": {"direction": "lower_better", "normalization": "minmax", "missing": "worst"},
    "c": {"direction": "higher_better", "normalization": "minmax", "missing": "exclude"},
}


def test_normalise():
    s = pd.Series([0.0, 5.0, 10.0, np.nan])
    assert normalise(s, "minmax", "higher_better").tolist()[:3] == [0, 0.5, 1]
    assert normalise(s, "minmax", "lower_better").tolist()[:3] == [1, 0.5, 0]
    assert pd.isna(normalise(s, "minmax", "higher_better").iloc[3])
    assert normalise(pd.Series([3.0, 3.0]), "minmax", "higher_better").tolist() == [0.5, 0.5]
    assert normalise(s, "percentile", "higher_better").iloc[2] == 1.0


def test_missing_policies_and_ranking():
    df = pd.DataFrame({"node_id": ["n1", "n2", "n3"], "a": [10.0, np.nan, 0.0],
                       "b": [0.0, 10.0, np.nan]})
    res = score_scenario(df, {"a": 0.5, "b": 0.5}, INDICATORS).set_index("node_id")
    assert res.loc["n1", "score"] == 1.0 and res.loc["n1", "rank"] == 1
    assert res.loc["n2", "weight_coverage"] == 0.5  # 'a' reweighted away
    assert res.loc["n2", "score"] == 0.0  # only b, which is worst
    assert res.loc["n3", "score"] == 0.0 and res.loc["n3", "missing_indicators"] == "b"


def test_exclusion_rules():
    df = pd.DataFrame({"node_id": ["n1", "n2", "n3"], "a": [1.0, 2.0, np.nan],
                       "c": [1.0, np.nan, 1.0], "flag": [True, False, False]})
    res = score_scenario(df, {"a": 0.5, "c": 0.5}, INDICATORS, min_weight_coverage=0.6,
                         exclude_if_true=["flag"]).set_index("node_id")
    assert "flag = true" in res.loc["n1", "excluded_reason"]
    assert "missing c" in res.loc["n2", "excluded_reason"]
    assert "coverage" in res.loc["n3", "excluded_reason"]
    assert res["rank"].isna().all()


def test_ties_are_deterministic():
    df = pd.DataFrame({"node_id": ["z", "a", "m"], "a": [1.0, 1.0, 1.0]})
    res = score_scenario(df, {"a": 1.0}, INDICATORS)
    assert res.sort_values("rank")["node_id"].tolist() == ["a", "m", "z"]
