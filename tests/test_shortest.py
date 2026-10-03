import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve


def test_two_stations_on_a_line():
    # 0 --100-- 1 --100-- 2 --100-- 3 --100-- 4
    xy = np.array([[0, 0], [100, 0], [200, 0], [300, 0], [400, 0]], float)
    u = np.array([0, 1, 2, 3])
    v = np.array([1, 2, 3, 4])
    length = np.full(4, 100.0)
    stations = [Point(0, 10), Point(400, 0)]
    dist, nearest = solve(xy, u, v, length, stations, access_radius_m=50)
    assert np.allclose(dist, [10, 110, 200, 100, 0], atol=0.01)
    # 節点 2 は駅 0 から 210 m、駅 1 から 200 m なので駅 1
    assert nearest.tolist() == [0, 0, 1, 1, 1]


def test_platform_line_reaches_several_nodes():
    xy = np.array([[0, 0], [100, 0], [200, 0]], float)
    u, v, length = np.array([0, 1]), np.array([1, 2]), np.array([100.0, 100.0])
    platform = LineString([(0, 20), (200, 20)])
    dist, nearest = solve(xy, u, v, length, [platform], access_radius_m=50)
    assert np.allclose(dist, [20, 20, 20], atol=0.01)


def test_station_without_nodes_in_radius_uses_nearest_node():
    xy = np.array([[0, 0], [100, 0]], float)
    u, v, length = np.array([0]), np.array([1]), np.array([100.0])
    dist, nearest = solve(xy, u, v, length, [Point(-500, 0)], access_radius_m=100)
    assert np.allclose(dist, [500, 600], atol=0.01)
