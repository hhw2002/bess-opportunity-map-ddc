"""Helpers shared by integration tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from bess_catalonia.demo import FILES, generate


def enable_real_grid(project: Path) -> None:
    """Configure a 'real' grid dataset in a throw-away project, using a copy of the synthetic
    grid file. Only for testing pipeline mechanics - never done in the repository itself."""
    tmp_sample = project / "_test_sample"
    generate(tmp_sample)
    target = project / "data" / "raw" / "grid" / "grid_nodes.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((tmp_sample / FILES["grid"]).read_bytes())
    path = project / "config" / "datasets.yaml"
    data = yaml.safe_load(path.read_text())
    data["real"]["grid_nodes"].update(path="grid/grid_nodes.csv", source_crs="EPSG:4326",
                                      columns=data["demo"]["grid_nodes"]["columns"])
    path.write_text(yaml.safe_dump(data, allow_unicode=True))
