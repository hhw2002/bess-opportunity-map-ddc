"""Static maps (matplotlib). Every demo map carries a SYNTHETIC watermark."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

SYNTHETIC_NOTE = "SYNTHETIC DEMO DATA - fictional, not a real Catalan BESS opportunity"


def _base(ax, context: dict[str, gpd.GeoDataFrame]) -> list:
    handles = []
    if (m := context.get("municipalities")) is not None:
        m.boundary.plot(ax=ax, color="#bbbbbb", linewidth=0.4, zorder=1)
    if (s := context.get("suitable_land_net")) is not None:
        s.plot(ax=ax, color="#9bd17f", alpha=0.6, zorder=2)
        handles.append(Patch(color="#9bd17f", alpha=0.6, label="Suitable land (net)"))
    if (h := context.get("hard_constraints")) is not None:
        h.plot(ax=ax, facecolor="none", edgecolor="#c0392b", hatch="///", linewidth=0.3,
               zorder=3)
        handles.append(Patch(facecolor="none", edgecolor="#c0392b", hatch="///",
                             label="Hard constraints"))
    if (r := context.get("roads")) is not None:
        r.plot(ax=ax, color="#555555", linewidth=0.8, zorder=4)
        handles.append(Line2D([], [], color="#555555", label="Major roads"))
    return handles


def _finish(fig, ax, title: str, mode: str, path: Path, handles: list) -> Path:
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("Easting (m, EPSG:25831)")
    ax.set_ylabel("Northing (m, EPSG:25831)")
    ax.ticklabel_format(style="plain")
    ax.tick_params(labelsize=7)
    if handles:
        ax.legend(handles=handles, loc="lower left", fontsize=7, framealpha=0.9)
    if mode == "demo":
        ax.text(0.5, 0.5, "SYNTHETIC", transform=ax.transAxes, fontsize=60, color="red",
                alpha=0.12, ha="center", va="center", rotation=30, zorder=10)
        note, color = SYNTHETIC_NOTE, "red"
    else:
        note, color = "Opportunity screening only - not an engineering feasibility study", "k"
    ax.annotate(note, xy=(0.5, -0.14), xycoords="axes fraction", ha="center", fontsize=8,
                color=color)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}")
    fig.savefig(tmp, dpi=150, bbox_inches="tight", format="png")
    plt.close(fig)
    tmp.replace(path)
    return path


def node_overview_map(nodes, context, mode: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 8))
    handles = _base(ax, context)
    styles = {"transmission": ("#1f3b73", "^", 70), "distribution": ("#e67e22", "o", 35)}
    level = nodes.get("network_level")
    for lvl, (color, marker, size) in styles.items():
        sub = nodes[level == lvl] if level is not None else nodes.iloc[0:0]
        if len(sub):
            sub.plot(ax=ax, color=color, marker=marker, markersize=size, edgecolor="black",
                     linewidth=0.4, zorder=5)
            handles.append(Line2D([], [], color=color, marker=marker, linestyle="",
                                  label=f"{lvl.capitalize()} node"))
    other = nodes[~level.isin(list(styles))] if level is not None else nodes
    if len(other):
        other.plot(ax=ax, color="grey", markersize=25, zorder=5)
        handles.append(Line2D([], [], color="grey", marker="o", linestyle="", label="Other node"))
    return _finish(fig, ax, "Grid nodes and land feasibility", mode, path, handles)


def score_map(nodes, scores, scenario: str, context, mode: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 8))
    handles = _base(ax, context)
    s = scores[scores["scenario"] == scenario][["node_id", "score", "rank"]]
    g = nodes.merge(s, on="node_id", how="left")
    ranked = g[g["rank"].notna()]
    unranked = g[g["rank"].isna()]
    if len(unranked):
        unranked.plot(ax=ax, facecolor="none", edgecolor="grey", markersize=40, zorder=5)
        handles.append(Line2D([], [], marker="o", color="grey", markerfacecolor="none",
                              linestyle="", label="Unranked (excluded / insufficient data)"))
    if len(ranked):
        ranked.plot(ax=ax, column="score", cmap="RdYlGn", vmin=0, vmax=1, markersize=70,
                    edgecolor="black", linewidth=0.4, zorder=6, legend=True,
                    legend_kwds={"label": "Score (0-1, illustrative weights)", "shrink": 0.6})
        for _, r in ranked.nsmallest(5, "rank").iterrows():
            ax.annotate(f"#{int(r['rank'])}", (r.geometry.x, r.geometry.y), xytext=(4, 4),
                        textcoords="offset points", fontsize=7, zorder=7)
    title = f"Opportunity score - {scenario.replace('_', ' ')} (illustrative)"
    return _finish(fig, ax, title, mode, path, handles)
