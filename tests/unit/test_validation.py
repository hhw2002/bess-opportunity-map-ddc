"""Schema checks, type coercion, missing values, duplicates, quality reports."""

import pandas as pd

from bess_catalonia.grid import processing as grid
from bess_catalonia.io import Loaded
from bess_catalonia.quality import QualityReport
from bess_catalonia.schemas import check_required, coerce_types, parse_numbers


def test_parse_catalan_numbers():
    s = pd.Series(["2.555.460", "237.755", "", None, "1.234,5"])
    out = parse_numbers(s, thousands=".", decimal=",")
    assert out.iloc[0] == 2_555_460 and out.iloc[1] == 237_755 and out.iloc[4] == 1234.5
    assert out.iloc[2:4].isna().all()  # blanks are null, never zero


def test_coercion_reports_bad_values_as_null():
    rep = QualityReport("t", "grid")
    df = pd.DataFrame({"source_node_id": ["a"], "node_name": ["n"], "x": ["2.1"], "y": ["41"],
                       "voltage_kv": ["n/a"]})
    out = coerce_types(df, "grid_input", rep)
    assert pd.isna(out.loc[0, "voltage_kv"])
    assert any(i.check == "type_coercion" and i.level == "warning" for i in rep.issues)


def test_missing_required_column_is_an_error():
    rep = QualityReport("t", "grid")
    assert not check_required(pd.DataFrame({"node_name": ["x"]}), "grid_input", rep)
    assert rep.has_errors
    assert "Quality report" in rep.to_markdown()


def _grid_loaded(cfg, rows):
    df = pd.DataFrame(rows)
    rep = QualityReport("grid_nodes", "grid")
    df = coerce_types(df, "grid_input", rep)
    return Loaded(cfg.dataset("demo", "grid_nodes"), df, rep)


BASE = {"source_node_id": "N1", "node_name": "A", "operator": "REE", "x": 2.0, "y": 41.5,
        "generation_available_mw": 10.0, "demand_available_mw": 20.0}


def test_conflicting_duplicate_node_id_is_error(cfg, demo_ctx):
    loaded = _grid_loaded(cfg, [BASE, {**BASE, "generation_available_mw": 99.0}])
    [rep] = grid.validate(loaded, demo_ctx)
    assert rep.has_errors and any(i.check == "duplicate_node_id" for i in rep.issues)


def test_exact_duplicates_dropped_and_names_flagged(cfg, demo_ctx):
    other = {**BASE, "source_node_id": "N2", "y": 41.6}  # same name, different node
    loaded = _grid_loaded(cfg, [BASE, BASE, other])
    [rep] = grid.validate(loaded, demo_ctx)
    assert not rep.has_errors
    checks = {i.check for i in rep.issues if i.level == "warning"}
    assert {"duplicate_rows", "duplicate_names"} <= checks
    nodes = grid.process(loaded, demo_ctx)
    assert list(nodes["node_id"]) == ["REE-N1", "REE-N2"]


def test_negative_and_missing_capacity_handling(cfg, demo_ctx):
    rows = [{**BASE, "demand_available_mw": -5.0},
            {**BASE, "source_node_id": "N2", "generation_available_mw": None}]
    nodes = grid.process(_grid_loaded(cfg, rows), demo_ctx)
    assert nodes["demand_available_mw"].isna().iloc[0]  # negative -> null, not zero
    assert nodes["bess_headroom_proxy_mw"].isna().all()
    assert nodes["headroom_note"].notna().all()


def test_coordinates_outside_region_flagged(cfg, demo_ctx):
    rows = [BASE, {**BASE, "source_node_id": "N2", "x": -3.7, "y": 40.4}]  # Madrid
    loaded = _grid_loaded(cfg, rows)
    [rep] = grid.validate(loaded, demo_ctx)
    assert any(i.check == "coordinates_region" for i in rep.issues)
    assert len(grid.process(loaded, demo_ctx)) == 1


def test_wrong_crs_mostly_outside_is_error(cfg, demo_ctx):
    rows = [{**BASE, "x": 430_000.0, "y": 4_580_000.0}]  # UTM values declared as EPSG:4326
    [rep] = grid.validate(_grid_loaded(cfg, rows), demo_ctx)
    assert rep.has_errors
