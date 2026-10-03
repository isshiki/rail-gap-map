"""OSM PBF -> water polygons (projected CRS), saved as WKB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union

from .config import Region
from .geo import Projector


def is_water(tags: dict) -> bool:
    return (
        tags.get("natural") == "water"
        or tags.get("waterway") == "riverbank"
        or tags.get("landuse") == "reservoir"
        or ("water" in tags and tags.get("natural") in (None, "water"))
    )


WATER_SQL = """(tags['natural'] = 'water' OR tags['waterway'] = 'riverbank' OR tags['landuse'] = 'reservoir'
                OR (tags['water'] IS NOT NULL AND coalesce(tags['natural'], 'water') = 'water'))"""


def assemble_relation(outer: list[LineString], inner: list[LineString]):
    outer_polys = list(polygonize(linemerge(outer))) if outer else []
    if not outer_polys:
        return None
    shape = unary_union(outer_polys)
    inner_polys = list(polygonize(linemerge(inner))) if inner else []
    if inner_polys:
        shape = shape.difference(unary_union(inner_polys))
    return shape


def run(region: Region, pbf: Path) -> None:
    w, s, e, n = region.bbox
    p = Projector(region.crs)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    src = f"ST_ReadOSM('{pbf.as_posix()}')"
    con.execute(f"""CREATE TEMP TABLE osm_rel AS SELECT id, refs, ref_roles, ref_types FROM {src}
                    WHERE kind = 'relation' AND tags['type'] = 'multipolygon' AND {WATER_SQL}""")
    con.execute("CREATE TEMP TABLE rel_ways AS SELECT DISTINCT unnest(refs) AS id FROM osm_rel")
    con.execute(f"""CREATE TEMP TABLE w AS
                    SELECT id, refs, coalesce({WATER_SQL}, false) AS is_water_way FROM {src}
                    WHERE kind = 'way' AND (coalesce({WATER_SQL}, false) OR id IN (SELECT id FROM rel_ways))""")
    con.execute("CREATE TEMP TABLE w_nodes AS SELECT DISTINCT unnest(refs) AS id FROM w")
    con.execute(f"""CREATE TEMP TABLE nd AS SELECT id, lon, lat FROM {src}
                    WHERE kind = 'node' AND lon BETWEEN {w} AND {e} AND lat BETWEEN {s} AND {n}
                      AND id IN (SELECT id FROM w_nodes)""")
    nodes = con.execute("SELECT id, lon, lat FROM nd ORDER BY id").fetchnumpy()
    ids = nodes["id"]
    if len(ids) == 0:
        region.build_dir.mkdir(parents=True, exist_ok=True)
        (region.build_dir / "water.wkb").write_bytes(shapely.to_wkb(shapely.GeometryCollection()))
        return
    x, y = p.to_xy(nodes["lon"], nodes["lat"])

    def line(refs):
        r = np.asarray(refs, np.int64)
        pos = np.searchsorted(ids, r)
        pos[pos >= len(ids)] = 0
        ok = ids[pos] == r
        if not ok.all():  # crosses the bbox edge: cannot close reliably
            return None
        return LineString(np.column_stack([x[pos], y[pos]]))

    way_lines, polys = {}, []
    for wid, refs, is_ww in con.execute("SELECT id, refs, is_water_way FROM w").fetchall():
        ln = line(refs)
        if ln is None:
            continue
        way_lines[wid] = ln
        if is_ww and refs[0] == refs[-1] and len(ln.coords) >= 4:
            polys.append(Polygon(ln.coords))
    for _, refs, roles, types in con.execute("SELECT * FROM osm_rel").fetchall():
        members = [(r, role) for r, role, t in zip(refs, roles, types) if t == "way"]
        outer = [way_lines[r] for r, role in members if role != "inner" and r in way_lines]
        inner = [way_lines[r] for r, role in members if role == "inner" and r in way_lines]
        shape = assemble_relation(outer, inner)
        if shape is not None and not shape.is_empty:
            polys.append(shape)
    polys = [shapely.make_valid(g) for g in polys]
    water = unary_union(polys) if polys else shapely.GeometryCollection()
    region.build_dir.mkdir(parents=True, exist_ok=True)
    (region.build_dir / "water.wkb").write_bytes(shapely.to_wkb(water))
