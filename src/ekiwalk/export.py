"""Write stations.geojson, boundaries.geojson, meta.json for the web app."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pyarrow.parquet as pq
import shapely
from shapely.geometry import Point, box
from shapely.ops import transform

from .config import Region, Scenario
from .contours import write_fc
from .geo import Projector


def run(region: Region, scenarios: list[Scenario], root) -> None:
    w = region.web_dir
    w.mkdir(parents=True, exist_ok=True)
    st = pq.read_table(region.build_dir / f"stations-{scenarios[-1].name}.parquet").to_pylist()
    seen, feats = set(), []
    for s in st:
        if s["group"] in seen:
            continue
        seen.add(s["group"])
        feats.append(({"name": s["name"], "planned": s["planned"]}, Point(s["lon"], s["lat"])))
    write_fc(w / "stations.geojson", feats)
    # Tokyo outline and a veil over everything outside it (the fill continues underneath)
    p = Projector(region.crs)
    tokyo = transform(lambda x, y, z=None: p.to_lonlat(x, y),
                      shapely.from_wkb((region.build_dir / "display.wkb").read_bytes()).simplify(30))
    write_fc(w / "outline.geojson", [({}, tokyo.boundary)])
    write_fc(w / "veil.geojson", [({}, box(*region.bbox).difference(tokyo))])
    manifest_path = root / "data" / "raw" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    meta = {
        "region": region.name,
        "label": region.label,
        "place_name": region.place_name,
        "home_view": region.home_view,
        "walk_m_per_min": region.walk_m_per_min,
        "blank_min": region.blank_min,
        "bus_km": region.bus_km,
        "osm_source": region.osm_source,
        "scenarios": [{"name": s.name, "label": s.label, "note": s.note, "title": s.title, "verb": s.verb,
                       "opening": s.opening, "sources": s.sources,
                       "planned": [{"name": p.name, "lon": p.lon, "lat": p.lat, "basis": p.basis} for p in s.stations]}
                      for s in scenarios],
        "sources": {k: {"file": v["file"], "retrieved_utc": v["retrieved_utc"], "sha256": v["sha256"]}
                    for k, v in manifest.items()},
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (w / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
