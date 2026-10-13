"""Demand stage (owner: Fernando): municipal electricity consumption by sector.

The source resolution is kept: the long table (municipality x year x sector) is written
unchanged in content, plus a per-municipality summary for the latest year. Municipal annual
consumption is NOT nodal load - it becomes a spatial context indicator only in integration.

Suppressed values (statistical secrecy) stay null, never zero; affected municipal totals are
flagged ``total_is_lower_bound``.
"""

from __future__ import annotations

import pandas as pd

from bess_catalonia.io import Loaded, load_standardized, write_csv, write_parquet
from bess_catalonia.pipeline import RunContext, StageResult
from bess_catalonia.quality import QualityReport
from bess_catalonia.schemas import order_columns

DATASET = "demand_municipal"


def load(ctx: RunContext) -> Loaded:
    loaded = load_standardized(ctx.dataset(DATASET), "demand", "demand_input")
    df = loaded.data
    if "municipality_code" in df:
        # INE codes are 5 digits; spreadsheets often strip the leading zero.
        df["municipality_code"] = df["municipality_code"].astype("string").str.zfill(5)
    return loaded


def _suppressed(df: pd.DataFrame, marker: str | None) -> pd.Series:
    if marker and "source_note" in df:
        return df["source_note"].astype("string").str.contains(marker, case=False).fillna(False)
    return pd.Series(False, index=df.index)


def validate(loaded: Loaded, ctx: RunContext) -> list[QualityReport]:
    df, report = loaded.data, loaded.report
    if report.has_errors:
        return [report]
    opts = loaded.spec.options
    key = ["municipality_code", "year"] + (["sector_code"] if "sector_code" in df else [])
    dupes = df.duplicated(subset=key, keep=False)
    if dupes.any():
        report.error("duplicate_records", f"Duplicate {key} combinations", int(dupes.sum()),
                     df.loc[dupes, key].astype(str).agg("/".join, axis=1).head(10).tolist())
    supp = _suppressed(df, opts.get("suppressed_note_contains"))
    missing = df["consumption_mwh"].isna()
    report.metrics["records"] = len(df)
    report.metrics["municipalities"] = int(df["municipality_code"].nunique())
    report.metrics["years"] = f"{int(df['year'].min())}-{int(df['year'].max())}"
    report.metrics["suppressed_values"] = int((missing & supp).sum())
    if (missing & ~supp).any():
        report.warning("missing_values", "Consumption missing without a suppression note",
                       int((missing & ~supp).sum()))
    neg = df["consumption_mwh"] < 0
    if neg.any():
        report.error("negative_consumption", "Negative consumption values", int(neg.sum()))
    report.info("resolution", "Annual municipal totals - not nodal / hourly load")
    report.add_completeness(df)
    return [report]


def summarise(df: pd.DataFrame, industrial_codes: list[str], marker: str | None):
    """Per municipality, latest year: published total, industrial part, suppression flag."""
    df = df.copy()
    df["_suppressed"] = _suppressed(df, marker) & df["consumption_mwh"].isna()
    latest = df.groupby("municipality_code")["year"].transform("max")
    cur = df[df["year"] == latest]
    sector = cur.get("sector_code", pd.Series(pd.NA, index=cur.index)).astype("string")
    cur = cur.assign(_industrial=cur["consumption_mwh"].where(sector.isin(industrial_codes)))
    if "municipality_name" not in cur:
        cur["municipality_name"] = pd.NA
    agg = cur.groupby("municipality_code").agg(
        municipality_name=("municipality_name", "first"),
        year=("year", "first"),
        total_mwh=("consumption_mwh", lambda s: s.sum(min_count=1)),
        industrial_mwh=("_industrial", lambda s: s.sum(min_count=1)),
        n_suppressed_sectors=("_suppressed", "sum"),
    ).reset_index()
    agg[["total_mwh", "industrial_mwh"]] = agg[["total_mwh", "industrial_mwh"]].round(3)
    agg["n_suppressed_sectors"] = agg["n_suppressed_sectors"].astype(int)
    agg["total_is_lower_bound"] = agg["n_suppressed_sectors"] > 0
    return order_columns(agg, "demand_municipal_summary")


def process(loaded: Loaded, ctx: RunContext) -> tuple[pd.DataFrame, pd.DataFrame]:
    opts = loaded.spec.options
    long = loaded.data.sort_values(
        [c for c in ("municipality_code", "year", "sector_code") if c in loaded.data]
    ).reset_index(drop=True)
    summary = summarise(long, [str(c) for c in opts.get("industrial_sector_codes", [])],
                        opts.get("suppressed_note_contains"))
    return long, summary


def run(ctx: RunContext) -> StageResult:
    loaded = load(ctx)
    reports = validate(loaded, ctx)
    outputs = [p for r in reports for p in ctx.write_report(r)]
    for r in reports:
        r.raise_if_errors()
    long, summary = process(loaded, ctx)
    out = ctx.stage_dir("demand")
    outputs += [write_parquet(long, out / "demand_municipal_long.parquet"),
                write_csv(long, out / "demand_municipal_long.csv"),
                write_csv(summary, out / "demand_municipal_summary.csv")]
    return StageResult(outputs=outputs,
                       record_counts={"records": len(long), "municipalities": len(summary)},
                       warnings=loaded.report.warnings)
