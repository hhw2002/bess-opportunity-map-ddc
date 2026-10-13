"""Deterministic SYNTHETIC demonstration data (seed 42) written to data/sample/.

Everything here is fictional: node names start with "DEMO", municipality codes are 99xxx,
locations are random points inside a box within Catalonia's UTM extent. The data
deliberately contains problems the pipeline must detect: missing values, a duplicate row,
duplicate node names, an ambiguous and an unmatched congestion node, a broken crosswalk
entry, invalid coordinates, unknown statuses, suppressed demand values and municipalities
without data. It exists only to exercise the software.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import affinity
from shapely.geometry import LineString, Point, box

from bess_catalonia.io import write_csv, write_gpkg, write_text

SEED = 42
CRS = "EPSG:25831"
X0, X1, Y0, Y1 = 300_000, 460_000, 4_560_000, 4_700_000
FILES = {
    "grid": "grid/grid_nodes_synthetic.csv",
    "demand": "demand/municipal_consumption_synthetic.csv",
    "erni": "congestion/erni_monthly_synthetic.csv",
    "crosswalk": "congestion/node_crosswalk_synthetic.csv",
    "renewables": "renewables/installations_synthetic.csv",
    "gis": "gis/gis_layers_synthetic.gpkg",
}
TREES = ["Alder", "Birch", "Cedar", "Dogwood", "Elm", "Fir", "Ginkgo", "Hazel", "Cedar",
         "Juniper", "Larch", "Maple", "Oak", "Pine", "Rowan", "Spruce", "Tamarack", "Willow",
         "Yew", "Aspen", "Beech", "Cypress", "Holly", "Linden"]
SECTORS = {"1": "PRIMARI", "3": "INDUSTRIAL", "4": "CONSTRUCCIO I OBRES PUBLIQUES",
           "5": "TRANSPORT", "6": "SERVEIS", "7": "USOS DOMESTICS"}
SECRECY = "Dada subjecta a secret estadístic"


def sample_data_present(raw_root: Path) -> bool:
    return all((raw_root / f).exists() for f in FILES.values())


def ensure_sample_data(raw_root: Path, force: bool = False) -> bool:
    """Generate the sample data if any file is missing. Returns True if generated."""
    if sample_data_present(raw_root) and not force:
        return False
    generate(raw_root)
    return True


def _catalan_number(v: float) -> str:
    return f"{int(round(v)):,}".replace(",", ".")


def _nodes(rng) -> pd.DataFrame:
    n = len(TREES)
    xs = rng.uniform(X0 + 15_000, X1 - 15_000, n)
    ys = rng.uniform(Y0 + 15_000, Y1 - 15_000, n)
    trans = np.arange(n) < 6
    df = pd.DataFrame({
        "node_code": [f"SYN-T{i + 1:02d}" if t else f"SYN-D{101 + i}" for i, t in
                      enumerate(trans)],
        "name": [f"DEMO {t}" for t in TREES],
        "operator": np.where(trans, "REE", "EDIS"),
        "level": np.where(trans, "transmission", "distribution"),
        "kv": np.where(trans, rng.choice([220, 400], n), rng.choice([25, 66, 110], n)),
        "gen_access_mw": np.round(np.where(trans, rng.uniform(0, 300, n),
                                           rng.uniform(0, 60, n)), 1),
        "dem_access_mw": np.round(np.where(trans, rng.uniform(0, 250, n),
                                           rng.uniform(0, 50, n)), 1),
        "gen_capacity_date": "2026-08-01",
        "dem_capacity_date": "2026-08-01",
    })
    df.loc[[7, 15, 20], "gen_access_mw"] = np.nan
    df.loc[[10, 21], "dem_access_mw"] = np.nan
    df.loc[12, "dem_access_mw"] = -5.0  # invalid negative value
    df.loc[16, "dem_capacity_date"] = "2026-05-01"  # not comparable with generation date
    pts = gpd.GeoSeries(gpd.points_from_xy(xs, ys), crs=CRS).to_crs("EPSG:4326")
    df["lon"], df["lat"] = pts.x.round(6), pts.y.round(6)
    df["_x"], df["_y"] = xs, ys
    return pd.concat([df, df.iloc[[2]]], ignore_index=True)  # exact duplicate row


def _erni(rng, nodes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = pd.period_range("2025-01", "2026-06", freq="M")
    season = 1 + 0.6 * np.sin((months.month.to_numpy() - 2) / 12 * 2 * np.pi)
    sources = [  # (erni id, published name, crosswalk target, scale MWh)
        *[(f"ERNI-{i + 1:04d}", f"SET DEMO {TREES[i].upper()} 400", f"SYN-T{i + 1:02d}", 900)
          for i in range(6)],
        ("ERNI-0007", "DEMO GINKGO", "SYN-D107", 120),
        ("ERNI-0008", "DEMO LINDEN DISTRIBUCIO", "SYN-D999", 80),  # broken crosswalk entry
        ("ERNI-0101", "SE DEMO HAZEL", None, 150),  # name rule (strip token SE)
        ("ERNI-0102", "demo juniper", None, 100),
        ("ERNI-0103", "DEMO MÀPLE", None, 60),  # accent removed by normalisation
        ("SYN-D113", "DEMO OAK (EDIS)", None, 90),  # identical source id rule
        ("ERNI-0201", "DEMO CEDAR", None, 110),  # ambiguous: two grid nodes named Cedar
        ("ERNI-0301", "DEMO NOWHERE", None, 70),  # unmatched
    ]
    rows = []
    for sid, name, _, scale in sources:
        for m, s in zip(months, season, strict=True):
            if sid == "ERNI-0004" and m < pd.Period("2026-01", "M"):
                continue  # short history -> coverage warning
            rows.append({"erni_node_id": sid, "erni_node_name": name, "month": str(m),
                         "erni_mwh": round(float(rng.gamma(2.0, scale * s / 2.0)), 1),
                         "level": "transmission" if sid <= "ERNI-0006" else "distribution"})
    erni = pd.DataFrame(rows)
    erni.loc[rng.choice(len(erni), 6, replace=False), "erni_mwh"] = np.nan
    xwalk = pd.DataFrame([{"congestion_source_node_id": s, "grid_source_node_id": g,
                           "note": "SYNTHETIC crosswalk entry"} for s, _, g, _ in sources if g])
    return erni, xwalk


def _renewables(rng, nodes: pd.DataFrame) -> pd.DataFrame:
    n = 200
    anchor = rng.integers(0, len(TREES), n)
    x = nodes["_x"].to_numpy()[anchor] + rng.normal(0, 6_000, n)
    y = nodes["_y"].to_numpy()[anchor] + rng.normal(0, 6_000, n)
    tech = rng.choice(["solar_pv", "wind", "hydro", "biomass"], n, p=[0.6, 0.3, 0.06, 0.04])
    cap_mw = np.where(tech == "solar_pv", rng.uniform(0.5, 50, n),
                      np.where(tech == "wind", rng.uniform(10, 60, n), rng.uniform(1, 15, n)))
    df = pd.DataFrame({
        "id": [f"SYN-RE-{i:04d}" for i in range(n)],
        "nom": [f"DEMO plant {i}" for i in range(n)],
        "tecnologia": tech,
        "potencia_kw": np.round(cap_mw * 1000),
        "estat": rng.choice(["En servei", "Autoritzat", "En tramitació"], n,
                            p=[0.6, 0.25, 0.15]),
        "utm_x": np.round(x, 1),
        "utm_y": np.round(y, 1),
    })
    df.loc[[5, 77, 140], ["utm_x", "utm_y"]] = 0.0  # invalid coordinates
    df.loc[[9, 31, 66, 150], "potencia_kw"] = np.nan
    df.loc[[42, 43], "estat"] = "Desconegut"  # not in status_map
    df.loc[199, "id"] = df.loc[198, "id"]  # duplicate id
    return df


def _municipalities(rng) -> gpd.GeoDataFrame:
    cells, codes = [], []
    size = 20_000
    k = 1
    for j in range(7):
        for i in range(8):
            cells.append(box(X0 + i * size, Y0 + j * size, X0 + (i + 1) * size,
                             Y0 + (j + 1) * size))
            codes.append(f"99{k:03d}")
            k += 1
    return gpd.GeoDataFrame({"municipality_code": codes,
                             "municipality_name": [f"DEMO MUNICIPI {c[-2:]}" for c in codes]},
                            geometry=cells, crs=CRS)


def _demand(rng, mun: gpd.GeoDataFrame) -> pd.DataFrame:
    rows = []
    codes = list(mun["municipality_code"])
    with_data = [c for c in codes if c not in ("99017", "99044")] + ["99099"]  # gaps, orphan
    scale = {c: rng.lognormal(0, 1) for c in with_data}
    base = {"1": 2e6, "3": 40e6, "4": 3e6, "5": 1e6, "6": 30e6, "7": 25e6}
    for year in (2023, 2024):
        for c in with_data:
            for code, name in SECTORS.items():
                v = base[code] * scale[c] * rng.uniform(0.8, 1.2) * (1.02 if year == 2024 else 1)
                secret = rng.random() < 0.1
                rows.append({"Any": str(year), "Provincia": "DEMO", "Comarca": "DEMO",
                             "CDMUN": c, "Municipi": f"DEMO MUNICIPI {c[-2:]}",
                             "Codi_Sector": code, "Descripcio_Sector": name,
                             "Consum [kWh]": "" if secret else _catalan_number(v),
                             "Observacions": SECRECY if secret else ""})
    return pd.DataFrame(rows)


def _gis_layers(rng, nodes: pd.DataFrame) -> dict[str, gpd.GeoDataFrame]:
    size = 4_000
    classes = ["agricultural_dryland", "grassland_scrub", "forest", "urban", "bare_industrial",
               "water", "irrigated_agriculture"]
    cells = [box(x, y, x + size, y + size) for x in range(X0, X1, size)
             for y in range(Y0, Y1, size)]
    land = gpd.GeoDataFrame({"land_class": rng.choice(
        classes, len(cells), p=[0.35, 0.15, 0.3, 0.08, 0.04, 0.03, 0.05])},
        geometry=cells, crs=CRS)
    centres = [(340_000, 4_640_000, 9_000, 5_000), (420_000, 4_600_000, 7_000, 7_000),
               (380_000, 4_680_000, 12_000, 4_000), (440_000, 4_670_000, 5_000, 8_000),
               (320_000, 4_580_000, 6_000, 6_000)]
    # one protected area right next to node DEMO Elm -> exercises the exclusion filter
    centres.append((nodes.loc[4, "_x"] + 2_500, nodes.loc[4, "_y"], 2_000, 2_000))
    ellipses = [affinity.scale(Point(x, y).buffer(1.0), sx, sy) for x, y, sx, sy in centres]
    protected = gpd.GeoDataFrame({"site_name": [f"DEMO Natura site {i + 1}" for i in
                                                range(len(ellipses))]},
                                 geometry=ellipses, crs=CRS).to_crs("EPSG:4326")
    rivers = [LineString([(X0, 4_620_000), (360_000, 4_610_000), (400_000, 4_630_000),
                          (X1, 4_615_000)]),
              LineString([(390_000, Y1), (395_000, 4_660_000), (385_000, 4_620_000)])]
    flood = gpd.GeoDataFrame({"return_period_yr": [100, 100]},
                             geometry=[r.buffer(1_500) for r in rivers], crs=CRS)
    towns = [(350_000, 4_600_000), (410_000, 4_650_000), (440_000, 4_590_000),
             (330_000, 4_680_000)]
    zoning = gpd.GeoDataFrame(
        {"zone_class": ["urban_residential", "urban_core", "urban_residential",
                        "industrial_estate"]},
        geometry=[Point(t).buffer(3_000) for t in towns], crs=CRS)
    roads = gpd.GeoDataFrame(
        {"road_class": ["motorway", "primary", "secondary"]},
        geometry=[LineString([(X0, 4_580_000), (380_000, 4_600_000), (X1, 4_690_000)]),
                  LineString([(330_000, Y0), (340_000, 4_650_000), (360_000, Y1)]),
                  LineString([(400_000, Y0), (430_000, 4_640_000)])], crs=CRS)
    return {"land_cover": land, "protected_areas": protected, "flood_zones": flood,
            "zoning": zoning, "roads": roads, "municipalities": _municipalities(rng)}


def generate(raw_root: Path) -> None:
    rng = np.random.default_rng(SEED)
    nodes = _nodes(rng)
    write_csv(nodes.drop(columns=["_x", "_y"]), raw_root / FILES["grid"])
    erni, xwalk = _erni(rng, nodes)
    write_csv(erni, raw_root / FILES["erni"])
    write_csv(xwalk, raw_root / FILES["crosswalk"])
    write_csv(_renewables(rng, nodes), raw_root / FILES["renewables"])
    layers = _gis_layers(rng, nodes)
    write_gpkg(layers, raw_root / FILES["gis"])
    write_csv(_demand(rng, layers["municipalities"]), raw_root / FILES["demand"])
    write_text(raw_root / "README.md", (
        "# SYNTHETIC sample data\n\nGenerated by `bess_catalonia.demo` (seed 42). All values "
        "are fictional and exist only to test the software. Never use them as evidence of a "
        "real BESS opportunity. Regenerate by deleting this folder and running "
        "`./start.sh --mode demo --all`.\n"))
