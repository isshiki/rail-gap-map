"""Node distances -> grid with blanks (water, sea, far from roads)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow.parquet as pq
import shapely
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from .config import Region, Scenario


@dataclass
class Grid:
    """dist[row, col]; cell centre of row r is y0 + (r + 0.5) * cell (y grows upward)."""

    dist: np.ndarray
    station: np.ndarray
    x0: float
    y0: float
    cell: float

    def save(self, path):
        np.savez_compressed(path, dist=self.dist.astype(np.float32), station=self.station.astype(np.int32),
                            x0=self.x0, y0=self.y0, cell=self.cell)

    @staticmethod
    def load(path) -> "Grid":
        z = np.load(path)
        return Grid(z["dist"].astype(float), z["station"], float(z["x0"]), float(z["y0"]), float(z["cell"]))

    def index(self, x: float, y: float) -> tuple[int, int]:
        return int((y - self.y0) // self.cell), int((x - self.x0) // self.cell)


def densify_edges(xy, u, v, length, dist, station, step: float):
    """Nodes plus interior points every <= step metres along each edge, with interpolated distances."""
    u, v, length = np.asarray(u), np.asarray(v), np.asarray(length, float)
    n = np.maximum(np.ceil(length / step).astype(np.int64) - 1, 0)  # interior points per edge
    e = np.repeat(np.arange(len(u)), n)
    j = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 1  # 1..n within each edge
    L = length[e]
    s = j * L / (n[e] + 1)
    t = (s / L)[:, None]
    a, b = u[e], v[e]
    p = xy[a] * (1 - t) + xy[b] * t
    da, db = dist[a] + s, dist[b] + (L - s)
    return (np.vstack([xy, p]), np.concatenate([dist, np.minimum(da, db)]),
            np.concatenate([station, np.where(da <= db, station[a], station[b])]))


def grid_from_points(pts, d, st, x0, y0, nx, ny, cell, max_offroad, k=8, chunk_rows=200) -> Grid:
    """Each cell gets min over its k nearest points (within max_offroad) of point distance + straight-line offset."""
    tree = cKDTree(pts)
    dist = np.full((ny, nx), np.nan)
    station = np.full((ny, nx), -1, dtype=np.int32)
    xs = x0 + (np.arange(nx) + 0.5) * cell
    kk = min(k, len(pts))
    for r0 in range(0, ny, chunk_rows):
        r1 = min(ny, r0 + chunk_rows)
        ys = y0 + (np.arange(r0, r1) + 0.5) * cell
        gx, gy = np.meshgrid(xs, ys)
        q = np.column_stack([gx.ravel(), gy.ravel()])
        dd, ii = tree.query(q, k=kk, distance_upper_bound=max_offroad, workers=-1)
        if kk == 1:
            dd, ii = dd[:, None], ii[:, None]
        valid = np.isfinite(dd)
        ii_safe = np.where(valid, ii, 0)
        total = np.where(valid, d[ii_safe] + dd, np.inf)
        best = np.argmin(total, axis=1)
        rows = np.arange(len(q))
        val = total[rows, best]
        ok = np.isfinite(val)
        dist[r0:r1] = np.where(ok, val, np.nan).reshape(r1 - r0, nx)
        station[r0:r1] = np.where(ok, st[ii_safe[rows, best]], -1).reshape(r1 - r0, nx)
    return Grid(dist, station, x0, y0, cell)


def cell_centers_mask(geom, x0, y0, cell, shape_):
    ny, nx = shape_
    xs = x0 + (np.arange(nx) + 0.5) * cell
    ys = y0 + (np.arange(ny) + 0.5) * cell
    gx, gy = np.meshgrid(xs, ys)
    shapely.prepare(geom)
    return shapely.contains_xy(geom, gx, gy)


def mask_geometry(dist, geom, x0, y0, cell, inside: bool):
    m = cell_centers_mask(geom, x0, y0, cell, dist.shape)
    out = dist.copy()
    out[m if inside else ~m] = np.nan
    return out


def smooth_nan(a, sigma: float):
    """Gaussian blur that ignores NaN cells and keeps them NaN (normalized convolution)."""
    if sigma <= 0:
        return a
    valid = np.isfinite(a)
    num = gaussian_filter(np.where(valid, a, 0.0), sigma)
    den = gaussian_filter(valid.astype(float), sigma)
    out = num / np.where(den > 0, den, 1)
    out[~valid] = np.nan
    return out


def run(region: Region, scenario: Scenario) -> Grid:
    b = region.build_dir
    nodes = pq.read_table(b / "nodes.parquet")
    edges = pq.read_table(b / "edges.parquet")
    sol = pq.read_table(b / f"solve-{scenario.name}.parquet")
    xy = np.column_stack([nodes["x"].to_numpy(), nodes["y"].to_numpy()])
    pts, d, st = densify_edges(xy, edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy(),
                               sol["dist_m"].to_numpy(), sol["station_idx"].to_numpy(), step=20)
    land = shapely.from_wkb((b / "land.wkb").read_bytes())
    cell = region.cell_m
    # the grid covers the whole compute area (not just Tokyo) so colours continue across the border
    x0, y0 = np.floor(xy[:, 0].min() / cell) * cell, np.floor(xy[:, 1].min() / cell) * cell
    nx, ny = int(np.ceil((xy[:, 0].max() - x0) / cell)), int(np.ceil((xy[:, 1].max() - y0) / cell))
    g = grid_from_points(pts, d, st, x0, y0, nx, ny, cell, region.max_offroad_m)
    g.dist = mask_geometry(g.dist, land, x0, y0, cell, inside=False)
    water = shapely.from_wkb((b / "water.wkb").read_bytes())
    if not water.is_empty:
        g.dist = mask_geometry(g.dist, water, x0, y0, cell, inside=True)
    g.station[np.isnan(g.dist)] = -1
    g.save(b / f"grid-{scenario.name}.npz")
    return g
