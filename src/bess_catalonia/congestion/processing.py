"""Congestion stage (owner: Hsiang Wei): ERNI records, node matching, 12-month totals.

Outputs in ``<processed>/congestion/``:
* ``congestion_records.csv``      - standardised source records + source key + matched node
* ``node_matching.csv``           - one row per source node: method, status, candidates
* ``congestion_node_summary.csv`` - per canonical node: ERNI in the 12-month window (GWh)

ERNI quantifies renewable energy that could not be integrated; it is evidence of
constraints, not a direct measure of BESS revenue (docs/assumptions.md).
"""

from __future__ import annotations

import pandas as pd

from bess_catalonia.congestion.matching import match_nodes, source_key
from bess_catalonia.io import (
    Loaded,
    apply_column_mapping,
    load_standardized,
    read_table,
    write_csv,
)
from bess_catalonia.pipeline import RunContext, StageResult
from bess_catalonia.quality import QualityReport
from bess_catalonia.schemas import order_columns
from bess_catalonia.units import mwh_to_gwh

DATASET = "congestion_erni"
CROSSWALK = "congestion_crosswalk"


def load(ctx: RunContext) -> Loaded:
    loaded = load_standardized(ctx.dataset(DATASET), "congestion", "congestion_input")
    df = loaded.data
    if not loaded.report.has_errors:
        ids = df["source_node_id"] if "source_node_id" in df else [None] * len(df)
        df["congestion_source_key"] = [source_key(i, n) for i, n in
                                       zip(ids, df["source_node_name"], strict=True)]
        df["period_month"] = df["period_start"].dt.to_period("M")
    return loaded


def load_crosswalk(ctx: RunContext, report: QualityReport) -> pd.DataFrame | None:
    if not ctx.available(CROSSWALK):
        report.info("crosswalk", "No crosswalk configured - only id/name rules used")
        return None
    spec = ctx.dataset(CROSSWALK)
    xw = apply_column_mapping(read_table(spec), spec, report)
    need = {"congestion_source_node_id", "grid_source_node_id"}
    if not need <= set(xw.columns):
        report.error("crosswalk", f"Crosswalk needs columns {sorted(need)}")
        return None
    dup = xw["congestion_source_node_id"].astype(str).duplicated(keep=False)
    if dup.any():
        report.error("crosswalk", "Crosswalk maps a source node more than once",
                     int(dup.sum()), xw.loc[dup, "congestion_source_node_id"].tolist())
    report.metrics["crosswalk_entries"] = len(xw)
    return xw


def validate(loaded: Loaded, ctx: RunContext) -> list[QualityReport]:
    df, report = loaded.data, loaded.report
    if report.has_errors:
        return [report]
    bad_period = df["period_start"].isna()
    if bad_period.any():
        report.error("period", "Records without a valid period_start", int(bad_period.sum()))
    key = ["congestion_source_key", "period_month"] + (
        ["network_level"] if "network_level" in df else [])
    dup = df.duplicated(subset=key, keep=False)
    if dup.any():
        report.error("duplicate_records", f"Duplicate {key} records", int(dup.sum()),
                     df.loc[dup, "congestion_source_key"].unique().tolist())
    if (df["erni_mwh"] < 0).any():
        report.error("negative_erni", "Negative ERNI values", int((df["erni_mwh"] < 0).sum()))
    n_null = int(df["erni_mwh"].isna().sum())
    if n_null:
        report.warning("missing_values", "ERNI values missing (kept null, not zero)", n_null)
    report.metrics["records"] = len(df)
    report.metrics["source_nodes"] = int(df["congestion_source_key"].nunique())
    if not bad_period.all():
        report.metrics["observation_period"] = (
            f"{df['period_month'].min()} to {df['period_month'].max()}")
    report.add_completeness(df, ["source_node_id", "source_node_name", "erni_mwh"])
    return [report]


def summarise(records: pd.DataFrame, reference_end: str | None) -> tuple[pd.DataFrame, str, str]:
    """ERNI per matched node in the 12 months ending at ``reference_end`` (YYYY-MM)."""
    end = pd.Period(reference_end, "M") if reference_end else records["period_month"].max()
    start = end - 11
    matched = records[records["node_id"].notna()]
    window = matched[(matched["period_month"] >= start) & (matched["period_month"] <= end)]
    g = window.groupby("node_id")
    summary = pd.DataFrame({
        "erni_12m_gwh": mwh_to_gwh(g["erni_mwh"].sum(min_count=1)),
        "erni_months_observed": window[window["erni_mwh"].notna()]
        .groupby("node_id")["period_month"].nunique(),
    })
    total = mwh_to_gwh(matched.groupby("node_id")["erni_mwh"].sum(min_count=1))
    summary = summary.reindex(total.index)
    summary["erni_total_gwh"] = total
    summary["erni_months_observed"] = summary["erni_months_observed"].fillna(0).astype(int)
    summary["erni_window_start"], summary["erni_window_end"] = str(start), str(end)
    meta = matched.groupby("node_id").agg(
        erni_match_method=("match_method", lambda s: ";".join(sorted(set(s)))),
        erni_source_keys=("congestion_source_key", lambda s: ";".join(sorted(set(s)))),
    )
    summary = summary.join(meta).reset_index()
    return order_columns(summary, "congestion_node_summary"), str(start), str(end)


def process(loaded: Loaded, ctx: RunContext, crosswalk, match_report: QualityReport):
    params = ctx.config.project["congestion"]
    nodes = pd.read_csv(ctx.upstream_file("grid", "grid_nodes.csv"), dtype={"source_node_id": str})
    records = loaded.data
    sources = records[[c for c in ("source_node_id", "source_node_name") if c in records]]
    matching = match_nodes(sources, nodes, crosswalk, params["allow_id_match"],
                           params["allow_name_match"], params["name_strip_tokens"])
    records = records.merge(
        matching[["congestion_source_key", "node_id", "match_method", "match_status"]],
        on="congestion_source_key", how="left")
    counts = matching["match_status"].value_counts().to_dict()
    for status in ("matched", "ambiguous", "unmatched"):
        match_report.metrics[f"source_nodes_{status}"] = int(counts.get(status, 0))
    for method, n in matching.loc[matching.match_status == "matched",
                                  "match_method"].value_counts().items():
        match_report.metrics[f"matched_by_{method}"] = int(n)
    amb = matching[matching.match_status == "ambiguous"]
    if len(amb):
        match_report.warning("ambiguous", "Ambiguous source nodes NOT merged - add crosswalk "
                             "entries", len(amb), (amb.source_node_name + " -> " +
                                                   amb.candidates).tolist())
    unm = matching[matching.match_status == "unmatched"]
    if len(unm):
        match_report.warning("unmatched", "Source nodes without a grid node", len(unm),
                             unm.source_node_name.tolist())
    if matching["crosswalk_target_missing"].any():
        match_report.warning("crosswalk", "Crosswalk points to grid ids that do not exist",
                             int(matching["crosswalk_target_missing"].sum()))
    shared = matching[matching.node_id.notna()].node_id.duplicated(keep=False)
    if shared.any():
        match_report.info("many_to_one", "Several source nodes map to one grid node; summed",
                          int(shared.sum()))
    summary, start, end = summarise(records, params.get("reference_period_end"))
    match_report.metrics["erni_window"] = f"{start} to {end}"
    short = summary[summary["erni_months_observed"] < 12]
    if len(short):
        match_report.warning("coverage", "Nodes with < 12 observed months in the window",
                             len(short), short.node_id.tolist())
    records = records.assign(period_month=records["period_month"].astype(str))
    return records, matching.drop(columns="crosswalk_target_missing"), summary


def run(ctx: RunContext) -> StageResult:
    loaded = load(ctx)
    match_report = QualityReport(dataset="congestion_node_matching", stage="congestion")
    crosswalk = load_crosswalk(ctx, match_report)
    reports = validate(loaded, ctx)
    outputs = [p for r in reports for p in ctx.write_report(r)]
    for r in reports + [match_report]:
        r.raise_if_errors()
    records, matching, summary = process(loaded, ctx, crosswalk, match_report)
    outputs += ctx.write_report(match_report)
    out = ctx.stage_dir("congestion")
    outputs += [write_csv(records, out / "congestion_records.csv"),
                write_csv(order_columns(matching, "node_matching"), out / "node_matching.csv"),
                write_csv(summary, out / "congestion_node_summary.csv")]
    return StageResult(
        outputs=outputs,
        record_counts={"records": len(records), "source_nodes": len(matching),
                       "matched": int((matching.match_status == "matched").sum()),
                       "nodes_with_erni": len(summary)},
        warnings=loaded.report.warnings + match_report.warnings,
    )
