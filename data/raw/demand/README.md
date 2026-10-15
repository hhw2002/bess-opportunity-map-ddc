# Demand-side data, reference year 2023

Generated 2026-10-08. Reference year 2023 = latest year with generation-side installed capacity data.

| File | Content | Source |
|---|---|---|
| municipal_electricity_consumption_by_sector_2023.csv | 947 municipalities x up to 6 sectors, annual kWh (4,676 rows; 920 rows have no value, mostly statistical secrecy) | Generalitat de Catalunya open data, dataset 8idm-becu (ICAEN) |
| icaen_municipal_electricity_consumption.csv | Full 2013-2024 series of the same dataset, raw portal format (Catalan headers, European number format). Its 2023 rows match the file above exactly | Generalitat de Catalunya open data, dataset 8idm-becu (ICAEN) |
| catalonia_hourly_demand_2023_long.csv | Catalonia-wide hourly demand, one row per hour: date, hour_slot, demand_mwh (8,760 rows) | Generalitat open data, dataset hx6q-ykhb (portal publishes it wide: one row per day, columns h01..h25) |
| ree_monthly_demand_by_ccaa_2023.csv | Monthly demand (MWh) for Spain, peninsular system and CCAAs | REE REData API (apidatos.ree.es) |
| edistribucion_demand_capacity_catalonia_2026-10.csv | Demand-side access capacity per e-distribucion substation, Oct 2026 snapshot (357 rows): kV, coordinates, available / occupied / admitted MW | e-distribucion capacity map |

## Notes
- Clean numerics: the original portal CSVs use European formats (dot thousands, comma decimals, dd/mm/yyyy). These extracts are plain numbers and ISO dates.
- Hourly files: hour_slot 1..24, plus slot 25 only on 2023-10-29 (25-hour day); 2023-03-26 has 23 hours. Demand is measured at power-station busbars (EBC).
- REE region labels: ids 5 (Aragon), 7 (Castilla-La Mancha), 9 (Catalonia), 8741 (peninsula) and the national series are documented or verified; the other region labels are inferred from annual magnitude. The regional sum reconciles with the national total (peninsula + Balearics + Canaries + Ceuta + Melilla).
- Catalonia 2023 cross-check: municipal 38.81 TWh (end use) < hourly EBC 42.34 TWh (+9.1%) < REE 44.41 TWh (+4.9% over hourly).
- REE REData API (tested 2026-10-08): at CCAA level it only returns monthly values. A daily request for Catalonia returns HTTP 200 with a single value equal to the whole month (silently ignores the daily setting); hourly requests return HTTP 400, even at national level for the window tested. Daily works for national and peninsular. The REData web interface (checked manually by Fernando, 2026-10-08) also offers only monthly and yearly data per autonomous community. Not verified: ESIOS (a web search found no sign of hourly regional demand, but that is not conclusive).
- Node-level capacity (e-distribucion) has no 2023 version: the archive starts in Sep 2025.
