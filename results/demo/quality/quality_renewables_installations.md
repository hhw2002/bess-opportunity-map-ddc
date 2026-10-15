# Quality report: renewables_installations

- Stage: `renewables`
- Mode: `demo`
- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**
- Issues: 0 error(s), 4 warning(s), 2 info

## Metrics

| metric | value |
|---|---|
| source_file | installations_synthetic.csv |
| source_rows | 200 |
| installations | 200 |
| operating_mw | 3561.84 |
| pipeline_mw | 1888.86 |

## Checks

| level | check | message | count | examples |
|---|---|---|---|---|
| info | required_columns | All required columns present |  |  |
| info | units | capacity_mw: converted from kW to canonical unit |  |  |
| warning | coordinates | Installations with missing/out-of-region coordinates (kept, flagged, excluded from aggregation) | 3 | SYN-RE-0005, SYN-RE-0077, SYN-RE-0140 |
| warning | duplicate_source_id | Duplicate installation ids (first kept for aggregation) | 2 | SYN-RE-0198 |
| warning | status_map | Statuses not in options.status_map -> 'unknown' | 2 | Desconegut |
| warning | missing_values | Installations without capacity (kept null) | 4 |  |

## Completeness (share non-null)

| column | share |
|---|---|
| source_installation_id | 100.00% |
| installation_name | 100.00% |
| technology | 100.00% |
| capacity_mw | 98.00% |
| status | 100.00% |
| x | 100.00% |
| y | 100.00% |
