"""OSM PBF -> walking graph (nodes.parquet, edges.parquet)."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .config import Region
from .geo import Projector
from .osmtags import WALKABLE_SQL

log = logging.getLogger(__name__)


def build_edges(ways, node_ids: np.ndarray, xy: np.ndarray):
    """ways: list of OSM node-id lists. Returns (u, v, length) as index arrays into node_ids."""
    order = np.argsort(node_ids)
    sorted_ids = node_ids[order]
    us, vs = [], []
    for refs in ways:
        r = np.asarray(refs, dtype=np.int64)
        pos = np.searchsorted(sorted_ids, r)
        pos[pos >= len(sorted_ids)] = 0
        idx = np.where(sorted_ids[pos] == r, order[pos], -1)
        a, b = idx[:-1], idx[1:]
        m = (a >= 0) & (b >= 0) & (a != b)
        us.append(a[m])
        vs.append(b[m])
    u = np.concatenate(us) if us else np.empty(0, np.int64)
    v = np.concatenate(vs) if vs else np.empty(0, np.int64)
    pairs = np.stack([np.minimum(u, v), np.maximum(u, v)], axis=1)
    # drop duplicate edges, keeping first-seen order
    _, first = np.unique(pairs, axis=0, return_index=True)
    pairs = pairs[np.sort(first)]
    u, v = pairs[:, 0], pairs[:, 1]
    length = np.hypot(*(xy[u] - xy[v]).T)
    return u, v, length


def largest_component(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    g = coo_matrix((np.ones(len(u)), (u, v)), shape=(n, n))
    _, labels = connected_components(g, directed=False)
    return labels == np.argmax(np.bincount(labels))


def read_walk_ways(pbf: Path, bbox):
    """Return (ways, node_ids, lon, lat) for walkable ways with at least one node inside bbox."""
    w, s, e, n = bbox
    src = f"ST_ReadOSM('{pbf.as_posix()}')"
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"""CREATE TEMP TABLE nodes AS SELECT id AS node_id, lon, lat FROM {src}
                    WHERE kind = 'node' AND lon BETWEEN {w} AND {e} AND lat BETWEEN {s} AND {n}""")
    con.execute(f"""CREATE TEMP TABLE way_refs AS
                    SELECT id AS way_id, unnest(refs) AS node_id, generate_subscripts(refs, 1) AS ord
                    FROM {src} WHERE kind = 'way' AND ({WALKABLE_SQL})""")
    con.execute("""CREATE TEMP TABLE used AS
                   SELECT DISTINCT node_id FROM way_refs JOIN nodes USING (node_id)""")
    nodes = con.execute("SELECT node_id, lon, lat FROM nodes JOIN used USING (node_id) ORDER BY node_id").fetchnumpy()
    ways = [r[0] for r in con.execute(
        """SELECT list(node_id ORDER BY ord) FROM way_refs
           WHERE way_id IN (SELECT DISTINCT way_id FROM way_refs JOIN used USING (node_id))
           GROUP BY way_id"""
    ).fetchall()]
    return ways, nodes["node_id"].astype(np.int64), nodes["lon"], nodes["lat"]


def run(region: Region, pbf: Path) -> None:
    out = region.build_dir
    out.mkdir(parents=True, exist_ok=True)
    ways, ids, lon, lat = read_walk_ways(pbf, region.bbox)
    if len(ids) < 100:
        raise RuntimeError(f"歩ける道の節点が {len(ids)} 個しかありません。bbox か PBF を確かめてください")
    x, y = Projector(region.crs).to_xy(lon, lat)
    xy = np.column_stack([x, y])
    u, v, length = build_edges(ways, ids, xy)
    keep = largest_component(len(ids), u, v)
    log.info("ways=%d nodes=%d edges=%d dropped_nodes=%d", len(ways), len(ids), len(u), int((~keep).sum()))
    new_index = np.cumsum(keep) - 1
    m = keep[u] & keep[v]
    pq.write_table(pa.table({"node_id": ids[keep], "x": x[keep], "y": y[keep]}), out / "nodes.parquet")
    pq.write_table(pa.table({"u": new_index[u[m]], "v": new_index[v[m]], "length_m": length[m]}), out / "edges.parquet")
