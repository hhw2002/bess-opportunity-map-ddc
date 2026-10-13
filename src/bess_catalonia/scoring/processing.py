"""Score stage: apply scoring.yaml scenarios to the integrated node dataset."""

from __future__ import annotations

import pandas as pd

from bess_catalonia.io import write_csv
from bess_catalonia.pipeline import RunContext, StageResult
from bess_catalonia.quality import QualityReport
from bess_catalonia.schemas import order_columns
from bess_catalonia.scoring.model import score_all


def run(ctx: RunContext) -> StageResult:
    cfg = ctx.config.scoring
    nodes = pd.read_csv(ctx.upstream_file("integrate", "nodes_integrated.csv"))
    report = QualityReport(dataset="scores", stage="score")
    report.warning("illustrative", f"Scoring status '{cfg.get('status')}': weights are "
                   "placeholders, not validated - do not interpret rankings as findings")
    scores = order_columns(score_all(nodes, cfg), "scores")
    for scen, g in scores.groupby("scenario"):
        report.metrics[f"{scen}_ranked"] = int(g["rank"].notna().sum())
        report.metrics[f"{scen}_unranked"] = int(g["rank"].isna().sum())
    absent = sorted({i for s in cfg["scenarios"].values() for i in s["weights"]}
                    - set(nodes.columns))
    if absent:
        report.warning("indicators_absent", "Indicators not in the integrated data (treated "
                       "as missing for every node)", len(absent), absent)
    outputs = ctx.write_report(report)
    out = ctx.stage_dir("score")
    wide = scores.pivot(index="node_id", columns="scenario", values=["score", "rank"])
    wide.columns = [f"{scen}_{v}" for v, scen in wide.columns]
    outputs += [write_csv(scores, out / "scores_long.csv"),
                write_csv(wide.reset_index(), out / "scores_wide.csv")]
    return StageResult(outputs=outputs,
                       record_counts={"scenarios": scores["scenario"].nunique(),
                                      "rows": len(scores)},
                       warnings=report.warnings)
