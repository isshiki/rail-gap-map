"""N02 stations (platform line segments) + planned stations -> stations-<scenario>.parquet."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from shapely.geometry import Point, box, shape
from shapely.ops import transform

from .config import PlannedStation, Region, Scenario
from .geo import Projector


def read_n02_station_features(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        cands = [n for n in z.namelist() if n.lower().endswith(".geojson") and "station" in n.lower()]
        if not cands:
            raise RuntimeError(f"Station の GeoJSON が見つかりません: {z.namelist()[:20]}")
        data = json.loads(z.read(cands[0]).decode("utf-8"))
    return data["features"]


def parse_station_features(features: list[dict], bbox) -> list[dict]:
    area = box(*bbox)
    rows = []
    for f in features:
        g = shape(f["geometry"])
        if not g.intersects(area):
            continue
        p = f["properties"]
        mid = g.interpolate(0.5, normalized=True) if g.geom_type == "LineString" else g.centroid
        rows.append({
            "group": p.get("N02_005g") or p.get("N02_005c") or p["N02_005"],
            "name": p["N02_005"],
            "line": p.get("N02_003") or "",
            "operator": p.get("N02_004") or "",
            "planned": False,
            "geom_ll": g,
            "lon": mid.x,
            "lat": mid.y,
        })
    return rows


def add_planned(rows: list[dict], planned: list[PlannedStation]) -> list[dict]:
    out = list(rows)
    for s in planned:
        out.append({
            "group": f"plan:{s.name}", "name": s.name, "line": "", "operator": "", "planned": True,
            "geom_ll": Point(s.lon, s.lat), "lon": s.lon, "lat": s.lat,
        })
    return out


def run(region: Region, scenario: Scenario, zip_path: Path) -> Path:
    p = Projector(region.crs)
    rows = add_planned(parse_station_features(read_n02_station_features(zip_path), region.bbox), scenario.stations)
    if sum(not r["planned"] for r in rows) < 3:
        raise RuntimeError("範囲内の駅が 3 未満です。bbox を確かめてください")
    geoms = [transform(lambda x, y, z=None: p.to_xy(x, y), r["geom_ll"]) for r in rows]
    table = pa.table({
        "idx": list(range(len(rows))),
        "group": [r["group"] for r in rows],
        "name": [r["name"] for r in rows],
        "line": [r["line"] for r in rows],
        "operator": [r["operator"] for r in rows],
        "planned": [r["planned"] for r in rows],
        "lon": [r["lon"] for r in rows],
        "lat": [r["lat"] for r in rows],
        "wkb": [shapely.to_wkb(g) for g in geoms],
    })
    region.build_dir.mkdir(parents=True, exist_ok=True)
    out = region.build_dir / f"stations-{scenario.name}.parquet"
    pq.write_table(table, out)
    return out
