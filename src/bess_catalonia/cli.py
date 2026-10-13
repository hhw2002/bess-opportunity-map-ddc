"""Command-line interface. Teammates normally call it through ./start.sh or .\\start.ps1."""

from __future__ import annotations

import argparse
import importlib
import platform
import subprocess
import sys

from bess_catalonia import __version__
from bess_catalonia.config import ConfigError, load_config

EPILOG = """\
stages (dependency order): grid, demand, congestion, renewables, gis, integrate, score, export

examples:
  ./start.sh --setup                              check / initialise the environment
  ./start.sh --mode demo --all                    full synthetic demonstration
  ./start.sh --mode real --steps grid             one stage on real data
  ./start.sh --mode real --steps grid,congestion  several stages
  ./start.sh --mode real --all                    all stages (optional ones skipped if no data)
  ./start.sh --mode real --validate               validate available real inputs only
  ./start.sh --mode real --all --dry-run          show the plan, change nothing
  ./start.sh --mode real --steps grid --force     regenerate even if up to date
  ./start.sh --mode real --record-manifest        record checksums of current input files
  ./start.sh --lab                                open JupyterLab (notebooks/)
  ./start.sh --test                               run the test suite
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="start.sh | start.ps1",
        description="Catalonia Grid-Scale BESS Opportunity Map - pipeline runner",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--mode", choices=["demo", "real"],
                   help="demo = synthetic data (results/demo), real = data/raw (results/real)")
    sel = p.add_mutually_exclusive_group()
    sel.add_argument("--steps", metavar="STAGES", help="comma-separated stage names")
    sel.add_argument("--all", action="store_true", help="run all stages in dependency order")
    sel.add_argument("--validate", action="store_true",
                     help="load and validate available inputs; write quality reports only")
    sel.add_argument("--record-manifest", action="store_true",
                     help="write data/manifests/<mode>_datasets.json with input checksums")
    sel.add_argument("--setup", action="store_true", help="check the environment and folders")
    sel.add_argument("--lab", action="store_true",
                     help="start JupyterLab in notebooks/ (extra args forwarded)")
    sel.add_argument("--test", action="store_true", help="run pytest (extra args forwarded)")
    p.add_argument("--dry-run", action="store_true",
                   help="print the execution plan without running or writing anything")
    p.add_argument("--force", action="store_true", help="re-run stages even if up to date")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument("--version", action="version", version=f"bess-opportunity-map-ddc {__version__}")
    return p


def cmd_setup() -> int:
    cfg = load_config()
    print(f"bess-opportunity-map-ddc {__version__} | Python {platform.python_version()} | {sys.prefix}")
    missing = []
    for mod in ("pandas", "numpy", "geopandas", "shapely", "pyproj", "pyogrio", "matplotlib",
                "yaml", "pyarrow"):
        try:
            m = importlib.import_module(mod)
            print(f"  ok  {mod:<11} {getattr(m, '__version__', '')}")
        except ImportError:
            missing.append(mod)
            print(f"  !!  {mod:<11} NOT INSTALLED")
    for mode in ("demo", "real"):
        mp = cfg.mode_paths(mode)
        for d in (mp.raw_root, mp.processed_root, mp.results_root):
            d.mkdir(parents=True, exist_ok=True)
    for domain in ("grid", "demand", "congestion", "renewables", "gis"):
        (cfg.mode_paths("real").raw_root / domain).mkdir(exist_ok=True)
    cfg.logs_dir.mkdir(exist_ok=True)
    print(f"  ok  configuration ({cfg.root / 'config'})")
    if missing:
        print("Missing packages - run: uv sync")
        return 1
    print("Environment ready. Next: ./start.sh --mode demo --all")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra and not (args.test or args.lab):
        parser.error(f"unrecognised arguments: {' '.join(extra)}")
    try:
        if args.setup:
            return cmd_setup()
        if args.lab:
            root = load_config().root
            return subprocess.call([sys.executable, "-m", "jupyter", "lab",
                                    f"--notebook-dir={root / 'notebooks'}", *extra])
        if args.test:
            return subprocess.call([sys.executable, "-m", "pytest", *extra],
                                   cwd=load_config().root)
        if not (args.steps or args.all or args.validate or args.record_manifest):
            parser.print_help()
            return 0
        if not args.mode:
            parser.error("--mode demo|real is required (synthetic and real data are kept apart)")
        if args.validate:
            from bess_catalonia.pipeline import validate_inputs

            return validate_inputs(args.mode, log_level=args.log_level)
        if args.record_manifest:
            from bess_catalonia.provenance import write_manifest

            cfg = load_config()
            if args.mode == "demo":
                from bess_catalonia.demo import ensure_sample_data

                ensure_sample_data(cfg.mode_paths("demo").raw_root)
            print("Data manifest written:", write_manifest(cfg, args.mode))
            return 0
        from bess_catalonia.pipeline import run_pipeline

        return run_pipeline(args.mode, steps=args.steps, run_all=args.all, dry_run=args.dry_run,
                            force=args.force, log_level=args.log_level)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
