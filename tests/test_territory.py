import numpy as np
import shapely

from ekiwalk.surface import Grid
from ekiwalk.territory import adjacency, color_territories, territory_polygons


def test_adjacency_from_grid():
    sg = np.array([[0, 0, 1, 1],
                   [0, 0, 1, 1],
                   [2, 2, 2, -1]])
    adj = adjacency(sg)
    assert adj == {0: {1, 2}, 1: {0, 2}, 2: {0, 1}}


def _conflicts(adj, colors, similar):
    bad = 0
    for a, ns in adj.items():
        for b in ns:
            if a < b and (colors[a] == colors[b] or colors[b] in similar.get(colors[a], set())):
                bad += 1
    return bad


def test_color_territories_avoids_same_and_similar_neighbours():
    # a wheel: hub 0 touching a ring of 7 (needs more than 3 colours)
    adj = {0: set(range(1, 8))}
    for i in range(1, 8):
        j = i % 7 + 1
        adj.setdefault(i, set()).update({0, j})
        adj.setdefault(j, set()).add(i)
    similar = {1: {4}, 4: {1}}
    colors = color_territories(adj, k=5, similar=similar)
    assert set(colors) == set(range(8))
    assert _conflicts(adj, colors, similar) == 0


def test_color_territories_keeps_given_colours_where_possible():
    adj = {0: {1}, 1: {0, 2}, 2: {1}}
    colors = color_territories(adj, k=5, similar={}, initial={0: 3, 1: 2, 2: 3})
    assert colors == {0: 3, 1: 2, 2: 3}


def test_territory_polygons_cover_cells_without_gaps_or_overlaps():
    sg = np.array([[0, 0, 0, 1, 1],
                   [0, 0, 1, 1, 1],
                   [0, 2, 2, 1, -1],
                   [2, 2, 2, 2, -1]])
    g = Grid(np.zeros(sg.shape), sg, 0.0, 0.0, 10.0)
    polys = territory_polygons(sg, g, simplify_m=0)
    assert set(polys) == {0, 1, 2}
    total = sum(p.area for p in polys.values())
    assert abs(total - (sg >= 0).sum() * 100) < 1e-6
    union = shapely.union_all(list(polys.values()))
    assert abs(union.area - total) < 1e-6   # no overlaps


def test_territory_polygons_simplified_still_share_edges():
    rng = np.random.default_rng(0)
    sg = (np.add.outer(np.arange(60), np.arange(60)) // 20 + (rng.random((60, 60)) < 0.05)).astype(int)
    g = Grid(np.zeros(sg.shape), sg, 0.0, 0.0, 25.0)
    polys = territory_polygons(sg, g, simplify_m=40)
    union = shapely.union_all(list(polys.values()))
    total = sum(p.area for p in polys.values())
    assert abs(union.area - total) / total < 1e-6   # simplification keeps the coverage (no overlaps)
