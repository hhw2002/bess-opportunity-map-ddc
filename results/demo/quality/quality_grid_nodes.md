# Quality report: grid_nodes

- Stage: `grid`
- Mode: `demo`
- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**
- Issues: 0 error(s), 3 warning(s), 3 info

## Metrics

| metric | value |
|---|---|
| source_file | grid_nodes_synthetic.csv |
| source_rows | 25 |
| generation_available_mw_missing | 3 |
| demand_available_mw_missing | 2 |
| nodes_in_source | 25 |

## Checks

| level | check | message | count | examples |
|---|---|---|---|---|
| info | required_columns | All required columns present |  |  |
| info | units | generation_available_mw: converted from MW to canonical unit |  |  |
| info | units | demand_available_mw: converted from MW to canonical unit |  |  |
| warning | duplicate_rows | Exact duplicate rows will be dropped | 1 | REE-SYN_T03 |
| warning | duplicate_names | Several nodes share a name; names must not be used as identifiers | 2 | DEMO CEDAR |
| warning | negative_capacity | demand_available_mw: negative values set to null | 1 | EDIS-SYN_D113 |
