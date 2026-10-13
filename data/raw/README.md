# Raw data (real mode)

Official source files, one sub-folder per domain (`grid/`, `demand/`, `congestion/`, `renewables/`, `gis/`).

* **Immutable** — never edit; fix problems via `config/datasets.yaml` or code.
* **Not committed** to git; share through the team drive using the exact file names in `config/datasets.yaml`.
* Record provenance in `datasets.yaml` and run `./start.sh --mode real --record-manifest` after adding a file.
