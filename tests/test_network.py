import numpy as np

from ekiwalk.network import build_edges, largest_component


def test_build_edges_from_way_refs():
    ways = [[1, 2, 3], [3, 4]]
    node_ids = np.array([1, 2, 3, 4])
    xy = np.array([[0, 0], [3, 4], [3, 10], [6, 10]], float)
    u, v, length = build_edges(ways, node_ids, xy)
    assert list(zip(u.tolist(), v.tolist())) == [(0, 1), (1, 2), (2, 3)]
    assert np.allclose(length, [5.0, 6.0, 3.0])


def test_build_edges_skips_missing_nodes_and_duplicates():
    ways = [[1, 2, 99, 3], [2, 1]]
    node_ids = np.array([1, 2, 3])
    xy = np.array([[0, 0], [1, 0], [2, 0]], float)
    u, v, length = build_edges(ways, node_ids, xy)
    # 99 は範囲外なので 2-99, 99-3 は捨てる。2-1 は 1-2 と重複なので捨てる
    assert list(zip(u.tolist(), v.tolist())) == [(0, 1)]


def test_largest_component_keeps_biggest():
    u = np.array([0, 1, 3])
    v = np.array([1, 2, 4])
    keep = largest_component(5, u, v)
    assert keep.tolist() == [True, True, True, False, False]
