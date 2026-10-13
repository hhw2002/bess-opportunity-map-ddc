"""Notebooks execute, environment files are consistent, docs match the implementation."""

import re
import shlex
import tomllib
from pathlib import Path

import pytest

import bess_catalonia
from bess_catalonia.cli import build_parser
from bess_catalonia.pipeline import STAGE_ORDER
from bess_catalonia.schemas import SCHEMAS

REPO = Path(__file__).resolve().parents[2]


# ----------------------------------------------------------------------------- environment
def test_environment_files():
    py = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert py["project"]["requires-python"].startswith(">=3.12")
    assert py["project"]["version"] == bess_catalonia.__version__
    assert (REPO / ".python-version").read_text().strip() == "3.12"
    assert 'name = "bess-opportunity-map-ddc"' in (REPO / "uv.lock").read_text()
    for script in ("start.sh", "start.ps1"):
        text = (REPO / script).read_text()
        assert "sync" in text and "--locked" in text and "bess_catalonia" in text
    assert (REPO / "start.sh").stat().st_mode & 0o111, "start.sh must be executable"


# ----------------------------------------------------------------------------- notebooks
@pytest.mark.slow
@pytest.mark.parametrize("name", ["01_data_exploration", "02_spatial_exploration",
                                  "03_model_exploration"])
def test_notebook_executes(name, demo_project, monkeypatch):
    import nbformat
    from nbclient import NotebookClient

    monkeypatch.setenv("BESS_PROJECT_ROOT", str(demo_project))
    monkeypatch.setenv("PYTHONPATH", str(REPO / "src"))
    monkeypatch.setenv("MPLBACKEND", "Agg")
    nb = nbformat.read(REPO / "notebooks" / f"{name}.ipynb", as_version=4)
    assert all(not c.get("outputs") for c in nb.cells if c.cell_type == "code"), \
        "commit notebooks with outputs cleared"
    NotebookClient(nb, timeout=300, kernel_name="python3",
                   resources={"metadata": {"path": str(REPO / "notebooks")}}).execute()


# ----------------------------------------------------------------------------- documentation
def _readme_commands() -> list[str]:
    text = (REPO / "README.md").read_text()
    return re.findall(r"^\s*\.\\?/start\.(?:sh|ps1)\s+(.*)$", text, flags=re.M)


def test_readme_commands_are_valid_cli_invocations():
    commands = _readme_commands()
    assert len(commands) >= 10
    parser = build_parser()
    for cmd in commands:
        args = shlex.split(cmd.split("#")[0])
        if args in (["--help"], ["--version"]):
            continue
        ns, extra = parser.parse_known_args(args)
        assert not extra or ns.test, f"README command not understood by the CLI: {cmd}"
        if ns.steps:
            assert set(ns.steps.split(",")) <= set(STAGE_ORDER), cmd


def test_readme_covers_required_sections_and_stages():
    text = (REPO / "README.md").read_text()
    for heading in ("Project overview", "Research methodology", "System architecture",
                    "Team and responsibilities", "Project plan", "Data sources",
                    "Getting started", "Repository structure", "Data contracts",
                    "Limitations", "Project status", "Documentation and changelog"):
        assert heading.lower() in text.lower(), heading
    for stage in STAGE_ORDER:
        assert f"`{stage}`" in text, stage


def test_data_contract_documents_every_schema_column():
    doc = (REPO / "docs" / "data_contract.md").read_text()
    missing = [f"{s}.{f.name}" for s, fields in SCHEMAS.items() for f in fields
               if f"`{f.name}`" not in doc]
    assert not missing, f"undocumented columns: {missing}"


def test_changelog_structure():
    text = (REPO / "CHANGELOG.md").read_text()
    assert "## [Unreleased]" in text and re.search(r"## \[0\.1\.0\] - \d{4}-\d{2}-\d{2}", text)
