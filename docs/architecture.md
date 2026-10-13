# Architecture

## Principles

* **Grid nodes are the analytical unit.** Every indicator is attached to a canonical `node_id`.
* **One module per data owner.** Teammates change their own module and their own
  `datasets.yaml` entry without touching others.
* **Shared contracts, not shared code paths.** Domains meet only through the canonical
  schemas (`schemas.py`, [data_contract.md](data_contract.md)) and processed files.
* **Configuration over code** for anything source-specific (paths, column names, units,
  status values) or methodological (buffers, constraints, weights).
* **Thin shell scripts, logic in Python.** `start.sh` / `start.ps1` only bootstrap the
  environment and forward arguments.
* **No premature infrastructure:** files on disk (CSV, GeoPackage, Parquet), no database,
  no Docker, no web services.

## Stages

| Stage | Module | Reads | Writes (`<processed_root>/<stage>/`) | Requires |
|---|---|---|---|---|
| `grid` | `grid/processing.py` | `grid_nodes` | `grid_nodes.gpkg/.csv` | — |
| `demand` | `demand/processing.py` | `demand_municipal` | `demand_municipal_long.*`, `demand_municipal_summary.csv` | — |
| `congestion` | `congestion/processing.py`, `matching.py` | `congestion_erni`, `congestion_crosswalk` (opt.) | records, `node_matching.csv`, `congestion_node_summary.csv` | grid output |
| `renewables` | `renewables/processing.py` | `renewables_installations` | `renewable_installations.gpkg/.csv`, summary | — |
| `gis` | `gis/processing.py`, `spatial.py` | land cover, protected, flood, zoning, roads (≥1) | `gis_node_metrics.csv`, `gis_layers.gpkg` | grid output |
| `integrate` | `integration/processing.py` | processed outputs + `gis_municipalities` | `nodes_integrated.gpkg/.csv/.parquet` | grid output |
| `score` | `scoring/model.py`, `processing.py` | integrated nodes | `scores_long.csv`, `scores_wide.csv` | integrate output |
| `export` | `export/processing.py`, `maps.py` | integrated, scores, GIS layers | `results/<mode>/bess_master.gpkg`, `tables/`, `maps/`, `summary.md` | integrate output |

Stage definitions (datasets, upstream stages, relevant configuration keys) live in one table:
`STAGES` in `pipeline.py`.

### Domain module interface

Every domain module exposes the same functions:

```python
load(ctx) -> Loaded            # read + map columns + coerce types + convert units
validate(loaded, ctx) -> [QualityReport]
process(loaded, ctx) -> data   # pure transformation into the canonical schema
run(ctx) -> StageResult        # load -> validate -> (stop on errors) -> process -> write
```

`--validate` calls only `load` + `validate`. `ctx` (`RunContext`) gives access to the
configuration, the mode's paths, dataset specs and upstream outputs.

## Execution model

1. `cli.py` parses arguments → `pipeline.run_pipeline`.
2. **Plan**: for each requested stage (fixed order) decide *run*, *up to date*, *skip*
   (optional stage, data missing, `--all` only) or *blocked* (required data or upstream output
   missing). `--dry-run` prints this and stops.
3. **Execute**: run stages; a failure blocks only stages that depend on it.
4. **Record**: every stage writes `_stage.json` (fingerprint, run id, outputs, counts); every
   run writes `logs/runs/<run_id>.json` and `logs/<run_id>.log`.

### Up-to-date detection (fingerprints)

A stage's fingerprint hashes: input file checksums (SHA-256), the stage's dataset
configuration, the relevant configuration sections, the fingerprints of upstream outputs and a
hash of the package source code. Identical fingerprint + existing outputs ⇒ "up to date".
Changing a raw file, a mapping, a weight or the code therefore re-runs exactly the affected
stages and everything downstream.

### Safe writes

Outputs are written to a temporary file in the same folder and atomically renamed, so a failed
run never leaves a half-written file in place of a previous good one. A stage's `_stage.json` is
deleted before it runs and rewritten only on success, so a failed stage is never reported as up
to date.

### Modes

| | demo | real |
|---|---|---|
| inputs | `data/sample/` (generated, synthetic) | `data/raw/` (official sources) |
| processed | `results/demo/processed/` | `data/processed/` |
| results | `results/demo/` | `results/real/` |
| datasets | `datasets.yaml → demo:` | `datasets.yaml → real:` |

Real mode never reads `data/sample/`; a missing real dataset is reported, never substituted.

## Provenance layers

| Record | Location | Written by |
|---|---|---|
| Dataset metadata (source, dates, limitations) | `config/datasets.yaml` | data owner |
| Data-version manifest (checksums of inputs) | `data/manifests/<mode>_datasets.json` | `--record-manifest` |
| Stage lineage (fingerprint, upstream run ids) | `<processed>/<stage>/_stage.json` | pipeline |
| Run record | `logs/runs/<run_id>.json` | pipeline |
| Software history | `CHANGELOG.md` | developers |
