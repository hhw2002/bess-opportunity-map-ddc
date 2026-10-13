"""Reading configured datasets and writing outputs safely.

Writes go to a temporary file in the target directory which is then atomically renamed, so
a failed run never leaves a half-written file in place of a previous good output.
Raw input files are only ever opened for reading.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd

from bess_catalonia.config import DatasetSpec
from bess_catalonia.quality import QualityReport

TABULAR_FORMATS = ("csv", "xlsx", "xls", "parquet", "json")
VECTOR_FORMATS = ("gpkg", "shp", "geojson", "json-geo", "fgb")


class MissingDataError(FileNotFoundError):
    """A required dataset or upstream output is not available."""


# ------------------------------------------------------------------------------- reading
def require_available(spec: DatasetSpec) -> Path:
    if spec.path is None:
        raise MissingDataError(
            f"Dataset '{spec.key}' ({spec.mode}) is not configured: set its path in "
            f"config/datasets.yaml under '{spec.mode}:'"
        )
    if not spec.path.exists():
        raise MissingDataError(f"Dataset '{spec.key}' expected at {spec.path} but not found")
    return spec.path


def read_table(spec: DatasetSpec) -> pd.DataFrame:
    path = require_available(spec)
    opts = dict(spec.read_options)
    fmt = spec.format
    if fmt == "csv":
        return pd.read_csv(path, **opts)
    if fmt in ("xlsx", "xls"):
        return pd.read_excel(path, **opts)
    if fmt == "parquet":
        return pd.read_parquet(path, **opts)
    if fmt == "json":
        return pd.read_json(path, **opts)
    raise ValueError(f"{spec.key}: unsupported tabular format {fmt!r}")


def read_vector(spec: DatasetSpec, target_crs: str, report: QualityReport) -> gpd.GeoDataFrame:
    """Read a vector layer and reproject it to ``target_crs``.

    CRS rules: the CRS stored in the file wins; ``source_crs`` in the config is used only if
    the file has none. A disagreement between the two is reported as a warning.
    """
    path = require_available(spec)
    kwargs = {"layer": spec.layer} if spec.layer else {}
    gdf = gpd.read_file(path, **kwargs)
    if gdf.crs is None:
        if not spec.source_crs:
            report.error("crs", f"{spec.key}: file has no CRS and no source_crs is configured")
            return gdf
        gdf = gdf.set_crs(spec.source_crs)
        report.info("crs", f"CRS taken from config: {spec.source_crs}")
    elif spec.source_crs and gpd.GeoSeries(crs=spec.source_crs).crs != gdf.crs:
        report.warning("crs", f"File CRS {gdf.crs.to_string()} differs from configured "
                              f"source_crs {spec.source_crs}; using the file CRS")
    report.metrics[f"{spec.key}_source_crs"] = gdf.crs.to_string()
    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        report.warning("geometry", f"{spec.key}: {int(invalid.sum())} invalid geometries "
                                   "repaired with make_valid", count=int(invalid.sum()))
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].make_valid()
    empty = gdf.geometry.is_empty | gdf.geometry.isna()
    if empty.any():
        report.warning("geometry", f"{spec.key}: {int(empty.sum())} empty geometries dropped")
        gdf = gdf[~empty]
    return gdf.to_crs(target_crs)


def apply_column_mapping(df: pd.DataFrame, spec: DatasetSpec, report: QualityReport):
    """Rename source columns to canonical names. An empty mapping keeps columns as-is."""
    if not spec.columns:
        return df
    absent = [src for src in spec.columns if src not in df.columns]
    if absent:
        report.warning("column_mapping", f"Mapped source columns not found in file: {absent}")
    return df.rename(columns={s: c for s, c in spec.columns.items() if s in df.columns})


def points_from_xy(
    df: pd.DataFrame, x: str, y: str, crs: str | None, report: QualityReport
) -> gpd.GeoDataFrame:
    if not crs:
        report.error("crs", "Coordinates present but no source_crs configured for this dataset")
        crs = "EPSG:4326"
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[x], df[y]), crs=crs)


# ------------------------------------------------------------------------------- writing
def _atomic(path: Path, writer: Callable[[Path], None]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        tmp_path.unlink()  # some writers (GPKG) refuse to write into an existing file
        writer(tmp_path)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
    return path


def write_text(path: Path, text: str) -> Path:
    return _atomic(path, lambda p: p.write_text(text, encoding="utf-8"))


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    out = pd.DataFrame(df.drop(columns="geometry", errors="ignore"))
    return _atomic(path, lambda p: out.to_csv(p, index=False))


def write_parquet(df: pd.DataFrame, path: Path) -> Path:
    """GeoDataFrames are written as GeoParquet, plain DataFrames as Parquet."""
    return _atomic(path, lambda p: df.to_parquet(p, index=False))


def write_gpkg(layers: dict[str, gpd.GeoDataFrame], path: Path) -> Path:
    """Write one or more layers into a single GeoPackage atomically."""

    def _write(p: Path) -> None:
        for name, gdf in layers.items():
            out = gdf.copy()
            for col in out.columns:  # GPKG has no nullable bool/Int64 extension types
                if str(out[col].dtype) == "boolean":
                    out[col] = out[col].astype(object)
            out.to_file(p, layer=name, driver="GPKG")

    return _atomic(path, _write)


# ------------------------------------------------------------------------ standardisation
@dataclass
class Loaded:
    """A dataset after reading, column mapping, type coercion and unit conversion."""

    spec: DatasetSpec
    data: pd.DataFrame
    report: QualityReport


def load_standardized(spec: DatasetSpec, stage: str, schema: str) -> Loaded:
    """Read a tabular dataset and bring it onto the canonical ``schema``.

    Order: read -> map columns -> check required columns -> coerce types -> convert units.
    Problems are recorded in the returned report; nothing is silently filled in.
    """
    from bess_catalonia.schemas import check_required, coerce_types
    from bess_catalonia.units import convert_column

    report = QualityReport(dataset=spec.key, stage=stage)
    raw = read_table(spec)
    report.metrics["source_file"] = spec.path.name
    report.metrics["source_rows"] = len(raw)
    df = apply_column_mapping(raw, spec, report)
    if check_required(df, schema, report):
        df = coerce_types(df, schema, report, spec.number_format)
        for column, unit in spec.units.items():
            if column in df:
                convert_column(df, column, unit)
                report.info("units", f"{column}: converted from {unit} to canonical unit")
    return Loaded(spec, df, report)
