"""Explicit unit conversion. Every converted column states its source unit in datasets.yaml."""

from __future__ import annotations

import pandas as pd

# Factors to the canonical unit of each quantity.
_POWER_TO_MW = {"W": 1e-6, "kW": 1e-3, "MW": 1.0, "GW": 1e3}
_ENERGY_TO_MWH = {"Wh": 1e-6, "kWh": 1e-3, "MWh": 1.0, "GWh": 1e3, "TWh": 1e6}


class UnitError(ValueError):
    pass


def to_mw(values: pd.Series, unit: str) -> pd.Series:
    if unit not in _POWER_TO_MW:
        raise UnitError(f"Unsupported power unit {unit!r}; expected one of {list(_POWER_TO_MW)}")
    return values * _POWER_TO_MW[unit]


def to_mwh(values: pd.Series, unit: str) -> pd.Series:
    if unit not in _ENERGY_TO_MWH:
        raise UnitError(
            f"Unsupported energy unit {unit!r}; expected one of {list(_ENERGY_TO_MWH)}"
        )
    return values * _ENERGY_TO_MWH[unit]


def mwh_to_gwh(values: pd.Series) -> pd.Series:
    return values / 1e3


def m_to_km(values: pd.Series) -> pd.Series:
    return values / 1e3


def m2_to_ha(values: pd.Series) -> pd.Series:
    return values / 1e4


def convert_column(df: pd.DataFrame, column: str, unit: str | None) -> pd.DataFrame:
    """Convert ``column`` to its canonical unit, inferred from the column suffix."""
    if unit is None or column not in df:
        return df
    if column.endswith("_mw"):
        df[column] = to_mw(df[column], unit)
    elif column.endswith("_mwh"):
        df[column] = to_mwh(df[column], unit)
    else:
        raise UnitError(f"Don't know the canonical unit of column {column!r}")
    return df
