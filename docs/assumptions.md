# Assumptions

Each assumption names where it is implemented, so it can be challenged and changed.

| # | Assumption | Why | Where | Consequence if wrong |
|---|---|---|---|---|
| A1 | `min(generation, demand)` access capacity is a usable *screening* proxy for BESS headroom | A battery needs both directions | `grid/processing.py` | Over/under-estimates real connectable size; never use as a connection offer |
| A2 | Capacities are comparable only if published on the same date | Capacity maps change over time | `grid.require_same_capacity_date` | Mixing dates could pair unrelated values |
| A3 | Node names alone do not identify electrical assets | Duplicate / similar names are common | `congestion/matching.py` | Name matching is *medium* reliability and must be unique |
| A4 | ERNI indicates network constraints near a node, not storage revenue | ERNI measures non-integrated energy | scoring weights | Ranking may favour congested but uneconomic nodes |
| A5 | Renewable capacity within 10 km describes local generation context | No public connection data per node | `integration.aggregation_radius_km` | Plants connected elsewhere are counted |
| A6 | Municipal demand is uniform within each municipality | Only municipal totals are public | `spatial.area_weighted_sum` | Misallocates demand in large, uneven municipalities |
| A7 | Suppressed demand values are unknown, not zero | Statistical secrecy | `demand/processing.py` | Totals are lower bounds (`total_is_lower_bound`) |
| A8 | Protected areas, flood zones and excluded urban zoning are *hard* exclusions | Permitting practice (to be verified) | `config/spatial.yaml` | Too strict or too lenient land estimates |
| A9 | Suitable land classes = dryland agriculture, scrub/grassland, bare/industrial | Typical BESS siting (to be verified per land-cover legend) | `land_cover.suitable_classes` | Land estimates depend directly on this list |
| A10 | Planar distances in EPSG:25831 are accurate enough at ≤ 20 km | UTM distortion is small within Catalonia | `gis/spatial.py` | Negligible |
| A11 | Scenario weights are illustrative | Not yet justified by data | `config/scoring.yaml` | Rankings carry no scientific weight until revised |
