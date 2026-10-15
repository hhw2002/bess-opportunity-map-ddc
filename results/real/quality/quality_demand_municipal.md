# Quality report: demand_municipal

- Stage: `demand`
- Mode: `real`
- Issues: 0 error(s), 0 warning(s), 3 info

## Metrics

| metric | value |
|---|---|
| source_file | icaen_municipal_electricity_consumption.csv |
| source_rows | 54611 |
| records | 54611 |
| municipalities | 947 |
| years | 2013-2024 |
| suppressed_values | 10099 |

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
| consumption_mwh | 81.51% |
| source_note | 19.80% |
