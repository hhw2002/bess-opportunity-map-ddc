"""Auditable matching of congestion (ERNI) source nodes to canonical grid nodes.

Rules, applied in order - the first that yields exactly one node wins:

1. ``crosswalk`` (reliability high): a reviewed manual table maps the congestion source id
   (or name) to a grid ``source_node_id``.
2. ``source_id`` (high): the congestion source id equals exactly one grid ``source_node_id``.
3. ``name`` (medium): the normalised names are identical and unique among grid nodes.

If a rule finds several candidate nodes the record is ``ambiguous`` and NOT merged - it must
be resolved by adding a crosswalk entry. Records that match nothing are ``unmatched``.
Identical names never imply identical electrical assets unless unique and reviewed.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd


def normalise_name(name, strip_tokens: list[str] | tuple[str, ...] = ()) -> str:
    if name is None or pd.isna(name):
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    tokens = re.sub(r"[^A-Z0-9]+", " ", text).split()
    strip = {t.upper() for t in strip_tokens}
    return " ".join(t for t in tokens if t not in strip)


def source_key(source_id, source_name) -> str:
    if source_id is not None and not pd.isna(source_id) and str(source_id).strip():
        return str(source_id).strip()
    return "name:" + str(source_name).strip()


def match_nodes(
    sources: pd.DataFrame,
    nodes: pd.DataFrame,
    crosswalk: pd.DataFrame | None = None,
    allow_id_match: bool = True,
    allow_name_match: bool = True,
    strip_tokens: list[str] | tuple[str, ...] = (),
) -> pd.DataFrame:
    """Return one matching row per distinct congestion source node (schema: node_matching).

    ``sources`` needs source_node_name (+ optional source_node_id); ``nodes`` needs node_id,
    source_node_id, node_name; ``crosswalk`` needs congestion_source_node_id,
    grid_source_node_id.
    """
    src = sources.copy()
    if "source_node_id" not in src:
        src["source_node_id"] = pd.NA
    src["congestion_source_key"] = [source_key(i, n) for i, n in
                                    zip(src["source_node_id"], src["source_node_name"],
                                        strict=True)]
    src = src.drop_duplicates("congestion_source_key")

    by_grid_id = nodes.groupby(nodes["source_node_id"].astype(str))["node_id"].apply(list)
    norm = nodes["node_name"].map(lambda n: normalise_name(n, strip_tokens))
    by_name = nodes.groupby(norm)["node_id"].apply(list)
    xwalk: dict[str, str] = {}
    if crosswalk is not None and not crosswalk.empty:
        xwalk = dict(zip(crosswalk["congestion_source_node_id"].astype(str).str.strip(),
                         crosswalk["grid_source_node_id"].astype(str).str.strip(), strict=True))

    rows = []
    for _, r in src.iterrows():
        sid = None if pd.isna(r["source_node_id"]) else str(r["source_node_id"]).strip()
        name = r["source_node_name"]
        candidates: list[str] = []
        method = "none"
        grid_sid = xwalk.get(sid or "") or xwalk.get(str(name).strip())
        if grid_sid is not None:
            candidates, method = by_grid_id.get(grid_sid, []), "crosswalk"
        if not candidates and allow_id_match and sid:
            candidates, method = by_grid_id.get(sid, []), "source_id"
        if not candidates and allow_name_match:
            key = normalise_name(name, strip_tokens)
            candidates, method = (by_name.get(key, []) if key else []), "name"
        if len(candidates) == 1:
            status = "matched"
            reliability = "medium" if method == "name" else "high"
        elif len(candidates) > 1:
            status, reliability = "ambiguous", "none"
        else:
            status, reliability, method = "unmatched", "none", "none"
        rows.append({
            "congestion_source_key": r["congestion_source_key"],
            "source_node_id": sid,
            "source_node_name": name,
            "node_id": candidates[0] if status == "matched" else None,
            "match_method": method,
            "match_status": status,
            "match_reliability": reliability,
            "candidates": ";".join(sorted(candidates)) if status == "ambiguous" else None,
            "crosswalk_target_missing": grid_sid is not None and grid_sid not in by_grid_id,
        })
    return pd.DataFrame(rows).sort_values("congestion_source_key").reset_index(drop=True)
