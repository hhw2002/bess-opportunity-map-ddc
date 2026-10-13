# Team workflow

## Branches

```
main                          always runs: ./start.sh --mode demo --all and ./start.sh --test pass
feature/grid-polo
feature/demand-fernando
feature/congestion-hsiang
feature/renewables-isabella
feature/gis-yuki
```

Short-lived topic branches (`fix/…`, `docs/…`) are fine. Merge `main` into your branch often.

## Pull requests

All changes to `main` go through a pull request using the
[PR template](../.github/pull_request_template.md). **Review by at least one other member is
required** for changes to:

* canonical schemas (`schemas.py`, `docs/data_contract.md`)
* integration logic (`integration/`)
* coordinate / CRS standards and spatial methods (`gis/spatial.py`, `spatial.yaml`)
* scoring methodology (`scoring/`, `scoring.yaml`)
* shared configuration (`project.yaml`) and the pipeline core (`pipeline.py`, `io.py`, …)

Changes inside your own domain module and your own `datasets.yaml` entry can be reviewed by
the integration coordinator.

## Working independently without inconsistent data

1. **Raw data is immutable.** Never edit a downloaded file; fix problems through the column
   mapping, options or code, so the correction is reproducible.
2. **Raw data is not committed** (`data/raw/` is git-ignored). Share files through the team
   drive with the exact file name used in `datasets.yaml`.
3. **One owner per dataset**; coordinates of nodes (Polo) and installations (Isabella) are
   collected once.
4. **Record provenance** in `datasets.yaml` (`publication_date`, `retrieval_date`, `source_url`,
   `observation_period`, `version`, `verification_status`, `known_limitations`).
5. After adding or updating a raw file run `./start.sh --mode real --record-manifest` and
   commit `data/manifests/real_datasets.json`, so everyone can check they hold the same version
   (`--validate` reports differences).
6. Refreshing a dataset is a deliberate act: download, record dates, update the manifest,
   open a PR. Pipeline runs never download data.

## Contributing a new dataset (checklist)

1. Save the official file in `data/raw/<domain>/` (keep the original name or add a date).
2. Edit `config/datasets.yaml → real:` entry: `path`, `format`, `read_options`, `source_crs`,
   `columns` (source → canonical, see [data_contract.md](data_contract.md)), `units`,
   `options`, `metadata`.
3. `./start.sh --mode real --validate` — fix errors, read the warnings in
   `results/real/quality/`.
4. `./start.sh --mode real --steps <domain>` and inspect the outputs (notebook 01 helps).
5. `./start.sh --mode real --record-manifest`.
6. Update [dataset_inventory.md](dataset_inventory.md) and, if relevant, the README progress
   table. Open a PR.

## Before every pull request

```bash
./start.sh --test
./start.sh --mode demo --all
uv run ruff check src tests
```

## Notebooks

Exploration only. Import from `bess_catalonia`; no absolute paths; clear outputs before
committing. If a notebook cell becomes essential, move it into the package with a test.
