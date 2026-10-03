"""Multi-source Dijkstra from all stations at once."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from .config import Region, Scenario

EPS = 1e-3  # scipy ignores zero-weight edges, so every access edge gets this tiny extra cost


def solve(xy: np.ndarray, u, v, length, stations: list, access_radius_m: float):
    """Return (dist_m per node, nearest station index per node).

    Each station becomes a virtual node linked to every graph node within access_radius_m
    of its geometry (platform line or point), weighted by the straight-line distance.
    """
    n, k = len(xy), len(stations)
    tree = cKDTree(xy)
    su, sv, sw = [], [], []
    for i, geom in enumerate(stations):
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        reach = np.hypot(maxx - minx, maxy - miny) / 2 + access_radius_m
        cand = np.asarray(tree.query_ball_point([cx, cy], reach), dtype=np.int64)
        d = np.empty(0)
        if len(cand):
            d = shapely.distance(shapely.points(xy[cand]), geom)
            cand, d = cand[d <= access_radius_m], d[d <= access_radius_m]
        if len(cand) == 0:
            pt = geom.interpolate(0.5, normalized=True) if geom.geom_type == "LineString" else geom
            _, j = tree.query([pt.x, pt.y])
            cand, d = np.array([j]), np.array([shapely.distance(shapely.points(xy[j]), geom)])
        su.append(np.full(len(cand), n + i))
        sv.append(cand)
        sw.append(d + EPS)
    uu = np.concatenate([np.asarray(u)] + su)
    vv = np.concatenate([np.asarray(v)] + sv)
    ww = np.concatenate([np.asarray(length, float)] + sw)
    g = coo_matrix((ww, (uu, vv)), shape=(n + k, n + k)).tocsr()
    dist, _, src = dijkstra(g, directed=False, indices=np.arange(n, n + k), min_only=True, return_predecessors=True)
    dist = dist[:n] - EPS
    nearest = np.where(src[:n] >= n, src[:n] - n, -1)
    return dist, nearest


def run(region: Region, scenario: Scenario) -> None:
    b = region.build_dir
    nodes = pq.read_table(b / "nodes.parquet")
    edges = pq.read_table(b / "edges.parquet")
    st = pq.read_table(b / f"stations-{scenario.name}.parquet")
    xy = np.column_stack([nodes["x"].to_numpy(), nodes["y"].to_numpy()])
    geoms = list(shapely.from_wkb(st["wkb"].to_numpy(zero_copy_only=False)))
    dist, nearest = solve(xy, edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy(),
                          geoms, region.access_radius_m)
    unreached = int(np.isinf(dist).sum())
    if unreached:
        raise RuntimeError(f"{unreached} 個の節点に届きません (グラフが分かれています)")
    pq.write_table(pa.table({"node_id": nodes["node_id"], "dist_m": dist, "station_idx": nearest}),
                   b / f"solve-{scenario.name}.parquet")
