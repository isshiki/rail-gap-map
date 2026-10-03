"""Census 2020 250 m mesh population (e-Stat) -> per-cell population and a residential mask."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

import numpy as np
from scipy import ndimage

from .geo import Projector

# JIS X 0410: 1st mesh 40' x 1 deg, 2nd 5' x 7'30", 3rd 30" x 45", 250 m mesh = 3rd / 4 (7.5" x 11.25")


def mesh250_code(lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """10-digit 250 m mesh code for each point (int64)."""
    lat_s = np.asarray(lat, float) * 3600.0
    lon_s = (np.asarray(lon, float) - 100.0) * 3600.0
    p, lat_r = np.divmod(lat_s, 2400.0)
    u, lon_r = np.divmod(lon_s, 3600.0)
    q, lat_r = np.divmod(lat_r, 300.0)
    v, lon_r = np.divmod(lon_r, 450.0)
    r, lat_r = np.divmod(lat_r, 30.0)
    w, lon_r = np.divmod(lon_r, 45.0)
    yi = np.floor(lat_r / 7.5).astype(np.int64)  # 0..3 within the 3rd mesh
    xi = np.floor(lon_r / 11.25).astype(np.int64)
    q4 = 1 + xi // 2 + 2 * (yi // 2)
    q5 = 1 + xi % 2 + 2 * (yi % 2)
    p, u, q, v, r, w = (a.astype(np.int64) for a in (p, u, q, v, r, w))
    return ((((((p * 100 + u) * 10 + q) * 10 + v) * 10 + r) * 10 + w) * 10 + q4) * 10 + q5


def mesh250_bounds(code: int) -> tuple[float, float, float, float]:
    """(west, south, east, north) in degrees."""
    s = f"{code:010d}"
    p, u, q, v, r, w, q4, q5 = int(s[0:2]), int(s[2:4]), int(s[4]), int(s[5]), int(s[6]), int(s[7]), int(s[8]), int(s[9])
    yi = 2 * ((q4 - 1) // 2) + (q5 - 1) // 2
    xi = 2 * ((q4 - 1) % 2) + (q5 - 1) % 2
    south = (p * 2400 + q * 300 + r * 30 + yi * 7.5) / 3600
    west = 100 + (u * 3600 + v * 450 + w * 45 + xi * 11.25) / 3600
    return west, south, west + 11.25 / 3600, south + 7.5 / 3600


def parse_mesh_csv(text: str) -> dict[int, int]:
    """KEY_CODE -> total population (T001142001). Hidden values ('*', '-') count as 0."""
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    col = next(i for i, h in enumerate(header) if h.endswith("001") and h.startswith("T"))
    out = {}
    for row in rows[1:]:
        if not row or not row[0].strip().isdigit():
            continue  # the second header row (Japanese names) has an empty KEY_CODE
        val = row[col].strip()
        out[int(row[0])] = int(val) if val.isdigit() else 0
    return out


def read_mesh_zip(path: Path) -> dict[int, int]:
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".txt", ".csv")))
        return parse_mesh_csv(z.read(name).decode("cp932"))


def cell_population(pop: dict[int, int], projector: Projector, x0: float, y0: float, cell: float, shape) -> tuple[np.ndarray, np.ndarray]:
    """Per grid cell: (mesh code, population of that mesh). Meshes missing from the census have 0 people."""
    ny, nx = shape
    codes = np.empty(shape, np.int64)
    xs = x0 + (np.arange(nx) + 0.5) * cell
    for r0 in range(0, ny, 256):
        r1 = min(ny, r0 + 256)
        gx, gy = np.meshgrid(xs, y0 + (np.arange(r0, r1) + 0.5) * cell)
        lon, lat = projector.to_lonlat(gx.ravel(), gy.ravel())
        codes[r0:r1] = mesh250_code(lon, lat).reshape(r1 - r0, nx)
    keys = np.fromiter(pop.keys(), np.int64, len(pop))
    vals = np.fromiter(pop.values(), np.int64, len(pop))
    order = np.argsort(keys)
    keys, vals = keys[order], vals[order]
    pos = np.clip(np.searchsorted(keys, codes), 0, len(keys) - 1)
    people = np.where(keys[pos] == codes, vals[pos], 0)
    return codes, people


def residential_mask(people: np.ndarray, threshold: int, smooth_cells: float) -> np.ndarray:
    """Cells in meshes with >= threshold people, with the 250 m steps smoothed out."""
    m = (people >= threshold).astype(float)
    if smooth_cells > 0:
        m = ndimage.gaussian_filter(m, smooth_cells)
    return m >= 0.5
