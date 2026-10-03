import numpy as np
from shapely.geometry import box

from ekiwalk.surface import densify_edges, grid_from_points, mask_geometry, smooth_nan


def test_densify_interpolates_along_edge():
    xy = np.array([[0, 0], [100, 0]], float)
    pts, d, st = densify_edges(xy, np.array([0]), np.array([1]), np.array([100.0]),
                               dist=np.array([0.0, 300.0]), station=np.array([0, 1]), step=20)
    # 端 A は 0、端 B は 300 (節点の値はそのまま)。辺上の 4 点は min(0 + s, 300 + 100 - s) = s
    assert np.allclose(sorted(d), [0, 20, 40, 60, 80, 300])
    assert st[2:].tolist() == [0, 0, 0, 0]
    assert np.allclose(pts[2:, 0], [20, 40, 60, 80])


def test_densify_picks_cheaper_end():
    xy = np.array([[0, 0], [100, 0]], float)
    _, d, st = densify_edges(xy, np.array([0]), np.array([1]), np.array([100.0]),
                             dist=np.array([0.0, 0.0]), station=np.array([0, 1]), step=20)
    assert np.allclose(d[2:], [20, 40, 40, 20])
    assert st[2:].tolist() == [0, 0, 1, 1]


def test_grid_adds_offroad_distance_and_blanks_far_cells():
    pts = np.array([[0.0, 0.0]])
    grid = grid_from_points(pts, np.array([100.0]), np.array([7]), x0=0, y0=-12.5, nx=20, ny=1, cell=25, max_offroad=300, k=1)
    # セル中心 x = 12.5, 37.5, ...、y = 0
    assert abs(grid.dist[0, 0] - (100 + 12.5)) < 1e-6
    assert np.isnan(grid.dist[0, 12])  # 312.5 m 離れている
    assert grid.station[0, 0] == 7 and grid.station[0, 12] == -1


def test_grid_takes_minimum_over_neighbours():
    pts = np.array([[0.0, 0.0], [100.0, 0.0]])
    grid = grid_from_points(pts, np.array([1000.0, 0.0]), np.array([1, 2]), x0=0, y0=-12.5, nx=4, ny=1, cell=25, max_offroad=300, k=2)
    # セル 0 (x=12.5) は点 0 経由 1012.5、点 1 経由 87.5 → 87.5
    assert abs(grid.dist[0, 0] - 87.5) < 1e-6
    assert grid.station[0, 0] == 2


def test_mask_geometry_blanks_inside():
    dist = np.zeros((4, 4))
    out = mask_geometry(dist, box(0, 0, 50, 50), x0=0, y0=0, cell=25, inside=True)
    assert np.isnan(out[0, 0]) and np.isnan(out[1, 1]) and not np.isnan(out[3, 3])


def test_smooth_nan_does_not_spread_blanks():
    a = np.ones((5, 5)) * 10
    a[2, 2] = np.nan
    s = smooth_nan(a, sigma=1.0)
    assert np.isnan(s[2, 2])
    assert np.allclose(s[0, 0], 10)
