# Viewing results in QGIS

QGIS is a separate desktop application (<https://qgis.org>); it is not part of the Python
environment.

1. Run the pipeline, e.g. `./start.sh --mode demo --all`.
2. In QGIS: *Layer → Add Layer → Add Vector Layer…* → choose
   `results/demo/bess_master.gpkg` (or `results/real/bess_master.gpkg`) → select all layers.
3. Layers (all EPSG:25831):
   * `nodes_integrated` — every node with all indicators (attribute table = master dataset)
   * `scores_<scenario>` — score and rank per node; style by `score` (graduated) and label `rank`
   * `suitable_land_net`, `hard_constraints`, `node_buffers` (filter `"radius_km" = 5`)
   * `renewable_installations` — style by `status_category`
4. Unranked nodes have a null `rank` and an `excluded_reason`.

Demo layers are SYNTHETIC. Project (`.qgz`) and style (`.qml`) files can be added here once real
layers exist.
