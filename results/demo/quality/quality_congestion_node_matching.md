# Quality report: congestion_node_matching

- Stage: `congestion`
- Mode: `demo`
- **SYNTHETIC DEMONSTRATION DATA - not a real measurement**
- Issues: 0 error(s), 4 warning(s), 0 info

## Metrics

| metric | value |
|---|---|
| crosswalk_entries | 8 |
| source_nodes_matched | 11 |
| source_nodes_ambiguous | 1 |
| source_nodes_unmatched | 2 |
| matched_by_crosswalk | 7 |
| matched_by_name | 3 |
| matched_by_source_id | 1 |
| erni_window | 2025-07 to 2026-06 |

## Checks

| level | check | message | count | examples |
|---|---|---|---|---|
| warning | ambiguous | Ambiguous source nodes NOT merged - add crosswalk entries | 1 | DEMO CEDAR -> EDIS-SYN_D109;REE-SYN_T03 |
| warning | unmatched | Source nodes without a grid node | 2 | DEMO LINDEN DISTRIBUCIO, DEMO NOWHERE |
| warning | crosswalk | Crosswalk points to grid ids that do not exist | 1 |  |
| warning | coverage | Nodes with < 12 observed months in the window | 3 | EDIS-SYN_D107, EDIS-SYN_D110, REE-SYN_T04 |
