"""Shared fixtures. Every test that runs the pipeline uses a throw-away project root in a
temporary directory (copy of config/), so the real repository outputs are never touched."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from bess_catalonia.config import load_config
from bess_catalonia.pipeline import _make_context

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def make_project(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    shutil.copytree(REPO / "config", base / "config", dirs_exist_ok=True)
    (base / "pyproject.toml").write_text("[project]\nname = 'tmp'\n")
    return base


@pytest.fixture
def project(tmp_path) -> Path:
    return make_project(tmp_path / "proj")


@pytest.fixture
def cfg(project):
    return load_config(project)


@pytest.fixture
def demo_ctx(cfg):
    return _make_context(cfg, "demo", [], force=False, dry_run=False)


@pytest.fixture(scope="session")
def demo_project(tmp_path_factory) -> Path:
    """A project root on which the full demo pipeline has run once (shared, read-only)."""
    from bess_catalonia.pipeline import run_pipeline

    root = make_project(tmp_path_factory.mktemp("demo") / "proj")
    assert run_pipeline("demo", run_all=True, root=root, log_level="WARNING") == 0
    return root
