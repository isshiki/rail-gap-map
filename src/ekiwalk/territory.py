"""Station territories (the area whose nearest station by walking is that station): shapes and colours."""

from __future__ import annotations

import random
from collections import defaultdict

import numpy as np
import shapely
from shapely.geometry import box


def station_groups(stations: list[dict]):
    """station idx -> group number (stations of one interchange share a group), and group -> first row."""
    groups: dict[str, int] = {}
    gid = np.array([groups.setdefault(s["group"], len(groups)) for s in stations])
    first = {}
    for s, k in zip(stations, gid):
        first.setdefault(int(k), s)
    return gid, first


def adjacency(sg: np.ndarray) -> dict[int, set[int]]:
    """Territories that share an edge or a corner on the grid (-1 = no territory)."""
    adj: dict[int, set[int]] = defaultdict(set)
    for a, b in [(sg[:, :-1], sg[:, 1:]), (sg[:-1, :], sg[1:, :]), (sg[:-1, :-1], sg[1:, 1:]), (sg[:-1, 1:], sg[1:, :-1])]:
        m = (a != b) & (a >= 0) & (b >= 0)
        for x, y in set(zip(a[m].tolist(), b[m].tolist())):
            adj[x].add(y)
            adj[y].add(x)
    return dict(adj)


def color_territories(adj: dict[int, set[int]], k: int, similar: dict[int, set[int]],
                      initial: dict[int, int] | None = None, seed: int = 0, max_steps: int = 200000) -> dict[int, int]:
    """Colour so that neighbours never share a colour nor a pair listed in `similar` (e.g. orange/yellow).

    DSatur for an initial colouring (or start from `initial`), then min-conflicts repair. Colours in
    `initial` are kept unless a conflict forces a change.
    """
    nodes = sorted(adj)
    rnd = random.Random(seed)

    def clash(c, d):
        return c == d or d in similar.get(c, ())

    colors: dict[int, int] = {}
    if initial:
        colors.update({n: c for n, c in initial.items() if n in adj})
    todo = [n for n in nodes if n not in colors]
    while todo:
        def sat(n):
            return len({colors[m] for m in adj[n] if m in colors})
        v = max(todo, key=lambda n: (sat(n), len(adj[n])))
        counts = np.bincount(list(colors.values()) or [0], minlength=k)
        options = sorted(range(k), key=lambda c: (sum(clash(c, colors[m]) for m in adj[v] if m in colors), counts[c]))
        colors[v] = options[0]
        todo.remove(v)

    def conflicts(n, c):
        return sum(clash(c, colors[m]) for m in adj[n])

    bad = [n for n in nodes if conflicts(n, colors[n])]
    steps = 0
    while bad and steps < max_steps:
        steps += 1
        v = rnd.choice(bad)
        if rnd.random() < 0.1:  # a little noise to step off plateaus
            colors[v] = rnd.randrange(k)
        else:
            scores = [(conflicts(v, c), rnd.random(), c) for c in range(k)]
            colors[v] = min(scores)[2]
        bad = [n for n in set(bad) | adj[v] | {v} if conflicts(n, colors[n])]
    return colors


def _row_runs(sg: np.ndarray):
    """(label, row, col_start, col_end) for each horizontal run of one label."""
    for r in range(sg.shape[0]):
        row = sg[r]
        cuts = np.flatnonzero(np.diff(row)) + 1
        starts = np.concatenate([[0], cuts])
        ends = np.concatenate([cuts, [len(row)]])
        for s, e in zip(starts, ends):
            if row[s] >= 0:
                yield int(row[s]), r, int(s), int(e)


def territory_polygons(sg: np.ndarray, g, simplify_m: float) -> dict[int, object]:
    """Exact cell-union polygon per territory, then a coverage-preserving simplification.

    Built from cell squares, neighbouring territories share their edges exactly; simplifying them as one
    coverage keeps it that way (no gaps or overlaps), and removes the 25 m staircase.
    """
    boxes: dict[int, list] = defaultdict(list)
    for lab, r, c0, c1 in _row_runs(sg):
        boxes[lab].append(box(g.x0 + c0 * g.cell, g.y0 + r * g.cell, g.x0 + c1 * g.cell, g.y0 + (r + 1) * g.cell))
    labels = sorted(boxes)
    geoms = [shapely.make_valid(shapely.union_all(boxes[lab], grid_size=g.cell / 100)) for lab in labels]
    if simplify_m > 0:
        geoms = list(shapely.coverage_simplify(np.array(geoms, dtype=object), simplify_m))
    return dict(zip(labels, geoms))
