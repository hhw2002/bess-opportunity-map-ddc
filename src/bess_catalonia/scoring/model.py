"""Transparent multi-criteria scoring (pure functions, no I/O).

score = Σ w_i · n_i / Σ w_i over the indicators available for the node, where n_i is the
normalised indicator (0 worst, 1 best). The functions take the weights explicitly so a
future sensitivity analysis can call ``score_scenario`` repeatedly with perturbed weights
or alternative normalisations without touching the pipeline (docs/future_features.md).

All weights in config/scoring.yaml are ILLUSTRATIVE until justified by exploratory analysis.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def normalise(values: pd.Series, method: str, direction: str) -> pd.Series:
    """Map an indicator to [0, 1] where 1 = most favourable. Nulls stay null.

    minmax: (x - min) / (max - min); a constant column maps to 0.5 (no information).
    percentile: average rank / count of non-null values.
    """
    v = pd.to_numeric(values, errors="coerce").astype(float)
    if method == "minmax":
        lo, hi = v.min(), v.max()
        if pd.isna(lo) or hi == lo:
            out = pd.Series(np.where(v.notna(), 0.5, np.nan), index=v.index)
        else:
            out = (v - lo) / (hi - lo)
    elif method == "percentile":
        out = v.rank(method="average", pct=True)
    else:
        raise ValueError(f"Unknown normalisation {method!r}")
    if direction == "lower_better":
        out = 1.0 - out
    elif direction != "higher_better":
        raise ValueError(f"Unknown direction {direction!r}")
    return out


def score_scenario(
    df: pd.DataFrame,
    weights: dict[str, float],
    indicators: dict[str, dict],
    min_weight_coverage: float = 0.5,
    exclude_if_true: list[str] | tuple[str, ...] = (),
    scenario: str = "",
) -> pd.DataFrame:
    """Score and rank nodes for one scenario. Deterministic: ties broken by node_id."""
    res = pd.DataFrame({"node_id": df["node_id"].to_numpy(), "scenario": scenario})
    total_w = sum(weights.values())
    num = np.zeros(len(df))
    covered = np.zeros(len(df))
    missing = [[] for _ in range(len(df))]
    excluded = [[] for _ in range(len(df))]
    for name, w in weights.items():
        spec = indicators[name]
        if name not in df:
            col = pd.Series(np.nan, index=df.index)
        else:
            col = normalise(df[name], spec["normalization"], spec["direction"])
        isna = col.isna().to_numpy()
        policy = spec["missing"]
        filled = col.to_numpy(dtype=float)
        if policy == "worst":
            filled = np.where(isna, 0.0, filled)
            covered += w
        elif policy == "reweight":
            covered += np.where(isna, 0.0, w)
        elif policy == "exclude":
            covered += w
            for i in np.flatnonzero(isna):
                excluded[i].append(f"missing {name}")
        num += w * np.nan_to_num(filled, nan=0.0)
        for i in np.flatnonzero(isna):
            missing[i].append(name)
    for flag in exclude_if_true:
        if flag in df:
            hit = df[flag].fillna(False).astype(bool).to_numpy()
            for i in np.flatnonzero(hit):
                excluded[i].append(f"{flag} = true")
    coverage = covered / total_w if total_w else np.zeros(len(df))
    with np.errstate(invalid="ignore", divide="ignore"):
        score = np.where(covered > 0, num / covered, np.nan)
    for i in np.flatnonzero(coverage < min_weight_coverage):
        excluded[i].append(f"weight coverage {coverage[i]:.0%} < {min_weight_coverage:.0%}")
    res["score"] = np.round(score, 6)
    res["weight_coverage"] = np.round(coverage, 4)
    res["missing_indicators"] = [";".join(m) or None for m in missing]
    res["excluded_reason"] = [";".join(e) or None for e in excluded]
    rankable = res["excluded_reason"].isna() & res["score"].notna()
    order = res[rankable].sort_values(["score", "node_id"], ascending=[False, True]).index
    res["rank"] = pd.Series(pd.NA, index=res.index, dtype="Int64")
    res.loc[order, "rank"] = np.arange(1, len(order) + 1)
    return res


def score_all(df: pd.DataFrame, scoring_cfg: dict) -> pd.DataFrame:
    frames = [
        score_scenario(df, s["weights"], scoring_cfg["indicators"],
                       scoring_cfg.get("min_weight_coverage", 0.5),
                       scoring_cfg.get("exclude_if_true", []), name)
        for name, s in scoring_cfg["scenarios"].items()
    ]
    return pd.concat(frames, ignore_index=True)
