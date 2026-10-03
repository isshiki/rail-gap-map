import math

import numpy as np
from shapely.geometry import Point

from ekiwalk.contours import threshold_polygons
from ekiwalk.surface import Grid


def radial_grid(n=201, cell=10.0):
    c = (n * cell) / 2
    xs = (np.arange(n) + 0.5) * cell
    gx, gy = np.meshgrid(xs, xs)
    return Grid(np.hypot(gx - c, gy - c), np.zeros((n, n), np.int32), 0.0, 0.0, cell), c


def test_threshold_polygons_excludes_inner_disc():
    # threshold_polygons(values, grid, t) は「値 >= t の範囲」を返す
    g, c = radial_grid()
    poly = threshold_polygons(g.dist, g, 300.0)
    assert not poly.contains(Point(c, c))
    assert poly.contains(Point(c + 600, c))


def test_smooth_outline_keeps_area_and_rounds_corners():
    from ekiwalk.contours import smooth_outline
    m = np.zeros((40, 40), bool)
    m[10:30, 10:30] = True
    g = Grid(None, None, 0.0, 0.0, 10.0)
    poly = smooth_outline(m, g, 3.0)
    # rounding the corners costs a little area; the straight edges stay at the cell boundary (100 and 300)
    assert abs(poly.area - 200 * 200) / (200 * 200) < 0.1
    assert all(abs(a - b) < 3 for a, b in zip(poly.bounds, (100, 100, 300, 300)))
    assert len(poly.exterior.coords) > 20  # corners are rounded, not 4 right angles
