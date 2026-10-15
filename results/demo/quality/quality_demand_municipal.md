# Quality report: demand_municipal

- Stage: `demand`
- Mode: `demo`
- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**
- Issues: 0 error(s), 0 warning(s), 3 info

## Metrics

| metric | value |
|---|---|
| source_file | municipal_consumption_synthetic.csv |
| source_rows | 660 |
| records | 660 |
| municipalities | 55 |
| years | 2023-2024 |
| suppressed_values | 62 |

## Checks

| level | check | message | count | examples |
|---|---|---|---|---|
| info | required_columns | All required columns present |  |  |
| info | units | consumption_mwh: converted from kWh to canonical unit |  |  |
| info | resolution | Annual municipal totals - not nodal / hourly load |  |  |

## Completeness (share non-null)

| column | share |
|---|---|
| year | 100.00% |
| province | 100.00% |
| comarca | 100.00% |
| municipality_code | 100.00% |
| municipality_name | 100.00% |
| sector_code | 100.00% |
| sector_name | 100.00% |
| consumption_mwh | 90.61% |
| source_note | 9.39% |
