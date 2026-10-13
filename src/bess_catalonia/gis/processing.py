"""GIS stage (owner: Yuki): land feasibility, constraints and accessibility around nodes.

For every grid node and every buffer radius in spatial.yaml:

* ``suitable_land_ha_<r>km`` - area of suitable land-cover classes MINUS all available hard
  constraint layers, inside the buffer (layers dissolved first: no double counting)
* ``<constraint>_share_<r>km`` - share of the buffer covered by each constraint layer

plus ``protected_area_conflict`` (protected area within the configured distance),
``flood_risk_at_node`` (node inside a flood zone) and ``distance_to_major_road_km``.

A metric whose source layer is unavailable stays null (unknown) - never 0. If suitable land
is computed while a hard-constraint layer is missing, the report says so.
"""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd

from bess_catalonia.gis import spatial
from bess_catalonia.io import read_vector, write_csv, write_gpkg
from bess_catalonia.pipeline import STAGES, RunContext, StageResult
from bess_catalonia.quality import QualityReport
from bess_catalonia.schemas import order_columns
from bess_catalonia.units import m2_to_ha, m_to_km


@dataclass
class GisInputs:
    layers: dict[str, gpd.GeoDataFrame]
    report: QualityReport


def load(ctx: RunContext) -> GisInputs:
    report = QualityReport(dataset="gis_layers", stage="gis")
    layers = {}
    for key in STAGES["gis"].optional_datasets:
        if ctx.available(key):
            layers[key] = read_vector(ctx.dataset(key), ctx.config.analysis_crs, report)
            report.metrics[f"{key}_features"] = len(layers[key])
        else:
            report.info("layer_availability", f"{key} not available - its metrics stay null")
    return GisInputs(layers, report)


def _select(gdf: gpd.GeoDataFrame, class_column: str | None, classes, report, key: str):
    if not class_column:
        return gdf
    if class_column not in gdf:
        report.error("class_column", f"{key}: column {class_column!r} not found "
                                     f"(available: {list(gdf.columns)})")
        return gdf.iloc[0:0]
    unknown = set(classes) - set(gdf[class_column].astype(str))
    if unknown:
        report.warning("classes", f"{key}: configured classes not present: {sorted(unknown)}")
    return gdf[gdf[class_column].astype(str).isin([str(c) for c in classes])]


def validate(inputs: GisInputs, ctx: RunContext) -> list[QualityReport]:
    sp, report = ctx.config.spatial, inputs.report
    lc = sp["land_cover"]
    if lc["dataset"] in inputs.layers:
        _select(inputs.layers[lc["dataset"]], lc["class_column"], lc["suitable_classes"],
                report, lc["dataset"])
    for name, c in sp["constraints"].items():
        if c["dataset"] in inputs.layers:
            _select(inputs.layers[c["dataset"]], c.get("class_column"), c.get("classes", []),
                    report, name)
            if c.get("role") not in ("hard", "soft"):
                report.error("constraint_role", f"{name}: role must be hard or soft")
    for key, gdf in inputs.layers.items():
        kinds = sorted(set(gdf.geom_type))
        report.metrics[f"{key}_geometry_types"] = ",".join(kinds)
    return [report]


def compute_node_metrics(nodes: gpd.GeoDataFrame, inputs: GisInputs, ctx: RunContext):
    """Return (metrics table, layers for export)."""
    sp, report, layers = ctx.config.spatial, inputs.report, inputs.layers
    spatial.require_projected(nodes, ctx.config.analysis_crs)
    radii = [float(r) for r in sp["buffers_km"]]
    aoi = spatial.make_buffers(nodes, max(radii)).geometry.union_all()

    def dissolved(gdf):
        return spatial.dissolve(gdf[gdf.intersects(aoi)])

    constraint_geoms, hard = {}, []
    for name, c in sp["constraints"].items():
        if c["dataset"] not in layers:
            if c.get("role") == "hard":
                report.warning("missing_constraint", f"Hard constraint '{name}' unavailable - "
                               "suitable land is overestimated where it would apply")
            continue
        sel = _select(layers[c["dataset"]], c.get("class_column"), c.get("classes", []),
                      report, name)
        constraint_geoms[name] = dissolved(sel)
        if c.get("role") == "hard" and constraint_geoms[name] is not None:
            hard.append(constraint_geoms[name])
    hard_union = gpd.GeoSeries(hard, crs=nodes.crs).union_all() if hard else None

    lc = sp["land_cover"]
    net = None
    if lc["dataset"] in layers:
        suitable = dissolved(_select(layers[lc["dataset"]], lc["class_column"],
                                     lc["suitable_classes"], report, lc["dataset"]))
        net = suitable
        if suitable is not None and hard_union is not None:
            net = suitable.difference(hard_union)
        if net is None:
            report.warning("suitable_land", "No suitable land-cover polygons near any node")

    out = pd.DataFrame({"node_id": nodes["node_id"].to_numpy()}, index=nodes.index)
    buffer_layers = []
    for r in radii:
        tag = f"{int(r) if r.is_integer() else r}km"
        buf = spatial.make_buffers(nodes, r)
        buf["radius_km"] = r
        buffer_layers.append(buf)
        area = buf.geometry.area
        if lc["dataset"] in layers:
            out[f"suitable_land_ha_{tag}"] = m2_to_ha(spatial.area_in_buffers_m2(buf, net))
        for name, geom in constraint_geoms.items():
            out[f"{name}_share_{tag}"] = (spatial.area_in_buffers_m2(buf, geom) / area).round(4)

    if "protected_area" in constraint_geoms:
        out["protected_area_conflict"] = spatial.within_distance(
            nodes, constraint_geoms["protected_area"], float(sp["protected_conflict_distance_m"]))
    if "flood_zone" in constraint_geoms:
        out["flood_risk_at_node"] = spatial.within_distance(nodes, constraint_geoms["flood_zone"],
                                                            0.0)
    acc = sp["accessibility"]
    if acc["dataset"] in layers:
        roads = layers[acc["dataset"]]
        if acc.get("class_column"):
            roads = _select(roads, acc["class_column"], acc["major_classes"], report, "roads")
        dist_m = spatial.nearest_distance_m(nodes, roads)
        out["distance_to_major_road_km"] = m_to_km(dist_m).round(3)

    export_layers = {"node_buffers": pd.concat(buffer_layers, ignore_index=True)}
    if net is not None:
        export_layers["suitable_land_net"] = gpd.GeoDataFrame(
            {"description": ["suitable land cover minus hard constraints"]}, geometry=[net],
            crs=nodes.crs)
    if hard_union is not None:
        export_layers["hard_constraints"] = gpd.GeoDataFrame(
            {"description": ["union of hard constraint layers"]}, geometry=[hard_union],
            crs=nodes.crs)
    report.metrics["nodes"] = len(out)
    report.metrics["buffers_km"] = ",".join(str(r) for r in radii)
    report.metrics["hard_constraints_used"] = ",".join(
        n for n, c in sp["constraints"].items()
        if c.get("role") == "hard" and n in constraint_geoms)
    return order_columns(out.reset_index(drop=True), "gis_node_metrics"), export_layers


def run(ctx: RunContext) -> StageResult:
    inputs = load(ctx)
    reports = validate(inputs, ctx)
    for r in reports:
        r.raise_if_errors()
    nodes = gpd.read_file(ctx.upstream_file("grid", "grid_nodes.gpkg"), layer="grid_nodes")
    metrics, layers = compute_node_metrics(nodes, inputs, ctx)
    outputs = [p for r in reports for p in ctx.write_report(r)]
    out = ctx.stage_dir("gis")
    outputs += [write_csv(metrics, out / "gis_node_metrics.csv"),
                write_gpkg(layers, out / "gis_layers.gpkg")]
    return StageResult(outputs=outputs,
                       record_counts={"nodes": len(metrics), "layers_used": len(inputs.layers)},
                       warnings=inputs.report.warnings)
