# Quality report: congestion_erni

- Stage: `congestion`
- Mode: `demo`
- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**
- Issues: 0 error(s), 1 warning(s), 2 info

## Metrics

| metric | value |
|---|---|
| source_file | erni_monthly_synthetic.csv |
| source_rows | 240 |
| records | 240 |
| source_nodes | 14 |
| observation_period | 2025-01 to 2026-06 |

## Checks

| level | check | message | count | examples |
|---|---|---|---|---|
| info | required_columns | All required columns present |  |  |
| info | units | erni_mwh: converted from MWh to canonical unit |  |  |
| warning | missing_values | ERNI values missing (kept null, not zero) | 6 |  |

## Completeness (share non-null)

| column | share |
|---|---|
| source_node_id | 100.00% |
| source_node_name | 100.00% |
| erni_mwh | 97.50% |
