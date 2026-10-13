"""Data-quality reports.

Every stage produces a QualityReport (JSON + Markdown). Issues have a level:
``info`` (recorded fact), ``warning`` (data accepted, but needs attention) and ``error``
(stage must not produce output).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

LEVELS = ("info", "warning", "error")


class DataValidationError(RuntimeError):
    """Raised when a dataset has error-level quality issues."""

    def __init__(self, report: QualityReport):
        self.report = report
        errors = "; ".join(i.message for i in report.issues if i.level == "error")
        super().__init__(f"{report.dataset}: validation failed: {errors}")


@dataclass
class Issue:
    level: str
    check: str
    message: str
    count: int | None = None
    examples: list[Any] = field(default_factory=list)


@dataclass
class QualityReport:
    dataset: str
    stage: str
    mode: str = ""
    issues: list[Issue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    completeness: dict[str, float] = field(default_factory=dict)

    def add(self, level: str, check: str, message: str, count=None, examples=None) -> None:
        if level not in LEVELS:
            raise ValueError(level)
        ex = [str(e) for e in list(examples or [])[:10]]
        self.issues.append(Issue(level, check, message, count, ex))

    def info(self, check, message, count=None, examples=None):
        self.add("info", check, message, count, examples)

    def warning(self, check, message, count=None, examples=None):
        self.add("warning", check, message, count, examples)

    def error(self, check, message, count=None, examples=None):
        self.add("error", check, message, count, examples)

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)

    @property
    def warnings(self) -> list[str]:
        return [f"{self.dataset}: {i.message}" for i in self.issues if i.level == "warning"]

    def add_completeness(self, df: pd.DataFrame, columns: list[str] | None = None) -> None:
        cols = [c for c in (columns or list(df.columns)) if c in df.columns and c != "geometry"]
        n = len(df)
        for c in cols:
            self.completeness[c] = round(float(df[c].notna().mean()) if n else 0.0, 4)

    def raise_if_errors(self) -> None:
        if self.has_errors:
            raise DataValidationError(self)

    # -- output -------------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [f"# Quality report: {self.dataset}", "",
                 f"- Stage: `{self.stage}`", f"- Mode: `{self.mode}`"]
        if self.mode == "demo":
            lines.append("- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**")
        counts = {lvl: sum(i.level == lvl for i in self.issues) for lvl in LEVELS}
        lines += [f"- Issues: {counts['error']} error(s), {counts['warning']} warning(s), "
                  f"{counts['info']} info", ""]
        if self.metrics:
            lines += ["## Metrics", "", "| metric | value |", "|---|---|"]
            lines += [f"| {k} | {v} |" for k, v in self.metrics.items()]
            lines.append("")
        lines += ["## Checks", "", "| level | check | message | count | examples |",
                  "|---|---|---|---|---|"]
        for i in self.issues:
            ex = ", ".join(i.examples)
            lines.append(f"| {i.level} | {i.check} | {i.message} | {i.count or ''} | {ex} |")
        if self.completeness:
            lines += ["", "## Completeness (share non-null)", "", "| column | share |",
                      "|---|---|"]
            lines += [f"| {k} | {v:.2%} |" for k, v in self.completeness.items()]
        return "\n".join(lines) + "\n"

    def write(self, directory: Path) -> list[Path]:
        from bess_catalonia.io import write_text

        stem = f"quality_{self.dataset}"
        json_path = directory / f"{stem}.json"
        md_path = directory / f"{stem}.md"
        write_text(json_path, json.dumps(self.to_dict(), indent=2, default=str))
        write_text(md_path, self.to_markdown())
        return [json_path, md_path]
