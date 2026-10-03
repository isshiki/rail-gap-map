"""Rail blank areas: land outside every station's walking area (more than blank_min minutes' walk).

A blank is not owned by a station. It is cut at municipal borders, and described by the stations its
residents would walk to (the nearest one by road) and how far they are.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import numpy as np
from scipy import ndimage


def classify(dist: np.ndarray, roadless: np.ndarray, walk_m: float, bus_m: float):
    """(walk, bus, deep) masks.

    walk: within walk_m of a station by road. bus: walk_m..bus_m (a station is about 30 minutes away by bus).
    deep: beyond bus_m, plus land without any road nearby (not computed, e.g. forest). Water/sea is in none.
    """
    d = np.nan_to_num(dist, nan=-1.0)
    walk = (d >= 0) & (d < walk_m)
    bus = (d >= walk_m) & (d < bus_m)
    deep = (d >= bus_m) | roadless
    return walk, bus, deep


def municipality_blanks(blank: np.ndarray, muni: np.ndarray, inside: np.ndarray, min_cells: int, closing: int = 2):
    """Label connected blank areas within each municipality (muni >= 0) inside the listed area.

    Returns (labels 1..n, {label: municipality index}).
    """
    lab = np.zeros(blank.shape, np.int32)
    owner: dict[int, int] = {}
    n = 0
    for i, sl in enumerate(ndimage.find_objects(muni + 1)):
        if sl is None:
            continue
        here = muni[sl] == i
        m = blank[sl] & here
        if not m.any():
            continue
        if closing:
            m = ndimage.binary_closing(np.pad(m, closing), iterations=closing)[closing:-closing, closing:-closing]
            m &= blank[sl] & here
        m &= inside[sl]
        l, c = ndimage.label(m, structure=np.ones((3, 3)))
        sizes = np.bincount(l.ravel(), minlength=c + 1)
        view = lab[sl]
        for j in range(1, c + 1):
            if sizes[j] >= min_cells:
                n += 1
                view[l == j] = n
                owner[n] = i
    return lab, owner


def nearest_station_shares(stations: np.ndarray, people: np.ndarray, min_share: float = 0.05) -> list[tuple[int, float]]:
    """[(station group, share)] of the residents by their nearest station; by area where nobody lives."""
    ok = stations >= 0
    st, w = stations[ok], people[ok]
    if w.sum() <= 0:
        w = np.ones(len(st))
    totals = Counter()
    for s, v in zip(st.tolist(), w.tolist()):
        totals[s] += v
    total = sum(totals.values())
    return [(int(s), round(v / total, 2)) for s, v in totals.most_common() if total and v / total >= min_share]


def excess_person_minutes(people: np.ndarray, minutes: np.ndarray, base_min: float) -> float:
    """Sum over residents of the minutes they walk beyond base_min (people x minutes)."""
    return float((people * np.clip(minutes - base_min, 0, None)).sum())


_CHOME = re.compile(r"[０-９0-9〇一二三四五六七八九十]+丁目$")
# 市/区 first (so 武蔵村山市 and 東村山市 are not cut at 村), then 町/村 for towns and villages
_CITY = re.compile(r"^(.{1,6}?[市区]|.{1,5}?[町村])")


def blank_name(cell_towns: list[str]) -> str:
    """Name from the towns covering the area: the largest, plus the second if it covers >= 20 %."""
    towns = Counter(_CHOME.sub("", t) for t in cell_towns)
    total = sum(towns.values())
    top = towns.most_common()
    name = top[0][0]
    if len(top) > 1 and top[1][1] / total >= 0.2:
        second = top[1][0]
        city = _CITY.match(name)
        if city and second.startswith(city.group(1)):
            second = second[len(city.group(1)):]
        name = f"{name}・{second}"
        if (total - top[0][1] - top[1][1]) / total >= 0.05:
            name += "ほか"
    return name


def match_scenarios(base_lab: np.ndarray, after_lab: np.ndarray):
    """Compare blank areas before/after a scenario.

    Returns ({base key: (status, share still blank)}, {after key: base key it continues}).
    status: "解消" if < 20 % remains blank, "縮小" if < 80 %, else "".
    """
    status = {}
    for k, sl in enumerate(ndimage.find_objects(base_lab), start=1):
        if sl is None:
            continue
        m = base_lab[sl] == k
        left = float((after_lab[sl][m] > 0).mean())
        status[k] = ("解消" if left < 0.2 else "縮小" if left < 0.8 else "", round(left, 2))
    mapping = {}
    for k, sl in enumerate(ndimage.find_objects(after_lab), start=1):
        if sl is None:
            continue
        m = after_lab[sl] == k
        over = base_lab[sl][m]
        over = over[over > 0]
        if len(over) and len(over) / m.sum() >= 0.3:
            mapping[k] = int(Counter(over.tolist()).most_common(1)[0][0])
    return status, mapping


PALETTE_SIZE = 5
SIMILAR_COLORS = {1: {4}, 4: {1}}  # orange and yellow are too alike to sit side by side


def run(region, scenarios, town_csv, pos_csv, s12_zip) -> dict:
    """Blank areas, tiers, station colours and summary.json for every scenario."""
    import pyarrow.parquet as pq
    import shapely
    from scipy.spatial import cKDTree

    from .admin import municipality_grid
    from .fetch import raw_path
    from .geo import Projector
    from .places import read_csv_any, town_rows
    from .population import cell_population, read_mesh_zip, residential_mask
    from .ridership import read_s12, ridership_for_groups
    from .surface import Grid, cell_centers_mask
    from .territory import adjacency, color_territories, station_groups

    b = region.build_dir
    p = Projector(region.crs)
    grids = {s.name: Grid.load(b / f"grid-{s.name}.npz") for s in scenarios}
    g0 = grids[scenarios[0].name]
    shape = g0.dist.shape
    cells = lambda wkb: cell_centers_mask(shapely.from_wkb((b / wkb).read_bytes()), g0.x0, g0.y0, g0.cell, shape)
    land, water, inside = cells("land.wkb"), cells("water.wkb"), cells("display.wkb")
    pop = {}
    for key in region.population_sources:
        pop.update(read_mesh_zip(raw_path(region.root, key)))
    codes, people = cell_population(pop, p, g0.x0, g0.y0, g0.cell, shape)
    resid = residential_mask(people, region.pop_threshold, region.res_smooth_cells) & land & ~water
    _, inv, cnt = np.unique(codes, return_inverse=True, return_counts=True)
    per_cell = people / cnt[inv].reshape(shape)  # residents of each cell (mesh population spread evenly)
    muni, muni_names = municipality_grid(region, raw_path(region.root, f"n03-{region.pref_code}"), g0, p)

    stations = pq.read_table(b / f"stations-{scenarios[-1].name}.parquet").to_pylist()
    gid, first = station_groups(stations)
    s12_rows, s12_year = read_s12(s12_zip)
    rides = ridership_for_groups(s12_rows, {k: {"code": s["group"], "name": s["name"], "lon": s["lon"], "lat": s["lat"]}
                                            for k, s in first.items() if not s["planned"]})
    towns = town_rows(read_csv_any(town_csv), read_csv_any(pos_csv))
    tx, ty = p.to_xy([t[2] for t in towns], [t[3] for t in towns])
    cell_km2 = (g0.cell / 1000) ** 2
    mpm = region.walk_m_per_min
    walk_m, bus_m = region.blank_min * mpm, region.bus_km * 1000

    def namer(muni_name):
        """Name blanks from town points of the same municipality (the ABR names start with it)."""
        own = [i for i, t in enumerate(towns) if t[0].startswith(muni_name)]
        if not own:
            return lambda xs, ys: muni_name  # e.g. 檜原村 has no town points
        tree = cKDTree(np.column_stack([tx[own], ty[own]]))
        return lambda xs, ys: blank_name([towns[own[i]][0] for i in tree.query(np.column_stack([xs, ys]))[1]])
    namers = {i: namer(n) for i, n in enumerate(muni_names)}

    labels, items, colors = {}, {}, {}
    for s in scenarios:
        g = grids[s.name]
        sg = np.where(g.station >= 0, gid[np.clip(g.station, 0, None)], -1)
        # station colours: later scenarios keep the base colours wherever they can
        colors[s.name] = color_territories(adjacency(sg), PALETTE_SIZE, SIMILAR_COLORS,
                                           initial=colors.get(scenarios[0].name))
        (b / f"colors-{s.name}.json").write_text(json.dumps(colors[s.name]), encoding="utf-8")
        roadless = land & ~water & np.isnan(g.dist)
        walk, bus, deep = classify(g.dist, roadless, walk_m, bus_m)
        np.savez_compressed(b / f"tiers-{s.name}.npz", walk=walk, bus=bus, deep=deep)
        lab, owner = municipality_blanks(bus | deep, muni, inside, int(region.min_blank_km2 / cell_km2))
        found = []
        for k, sl in enumerate(ndimage.find_objects(lab), start=1):
            if sl is None:
                continue
            rr, cc = np.nonzero(lab[sl] == k)
            rr, cc = rr + sl[0].start, cc + sl[1].start
            xs, ys = g.x0 + (cc + 0.5) * g.cell, g.y0 + (rr + 0.5) * g.cell
            dist_here = g.dist[rr, cc]
            mins = np.nan_to_num(dist_here, nan=0.0) / mpm
            pc = per_cell[rr, cc]
            j = int(np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2))  # label at the cell nearest the centroid
            lon, lat = p.to_lonlat([xs[j]], [ys[j]])
            mname = muni_names[owner[k]]
            found.append({
                "key": k,
                "muni": mname,
                "name": namers[owner[k]](xs, ys).removeprefix(mname) or mname,
                "area_km2": round(len(rr) * cell_km2, 2),
                "bus_km2": round(float(bus[rr, cc].sum()) * cell_km2, 2),
                "deep_km2": round(float(deep[rr, cc].sum()) * cell_km2, 2),
                "roadless_km2": round(float(roadless[rr, cc].sum()) * cell_km2, 2),
                "population": int(round(float(pc.sum()))),
                "density": int(round(float(pc.sum()) / (len(rr) * cell_km2))),
                "lived_share": round(float(resid[rr, cc].mean()), 2),
                "max_km": round(float(np.nanmax(dist_here)) / 1000, 1) if np.isfinite(dist_here).any() else None,
                "excess_pm": int(round(excess_person_minutes(pc, mins, region.blank_min))),
                "stations": [{"group": st, "name": first[st]["name"], "planned": bool(first[st]["planned"]),
                              "share": sh, "ridership": rides.get(st), "lon": round(first[st]["lon"], 5),
                              "lat": round(first[st]["lat"], 5)}
                             for st, sh in nearest_station_shares(sg[rr, cc], pc)[:4]],
                "label": [round(float(lon[0]), 5), round(float(lat[0]), 5)],
            })
        labels[s.name], items[s.name] = lab, found

    # numbers follow population density (people per km2 of the blank) in the base scenario, so dense urban gaps
    # come first; later scenarios reuse the numbers for areas they continue
    score = lambda it: (-it["density"], -it["population"])
    base = scenarios[0].name
    for no, it in enumerate(sorted(items[base], key=score), 1):
        it["no"] = no
    base_no = {it["key"]: it["no"] for it in items[base]}
    for s in scenarios[1:]:
        status, mapping = match_scenarios(labels[base], labels[s.name])
        resolved = {k for k, (st, _) in status.items() if st == "解消"}
        nxt, used = len(items[base]) + 1, set()
        for it in sorted(items[s.name], key=score):
            src = mapping.get(it["key"])
            # leftovers of a resolved area, and the smaller piece of a split one, get new numbers
            no = None if src in resolved else base_no.get(src)
            if no is None or no in used:
                no, nxt = nxt, nxt + 1
            it["no"] = no
            used.add(no)
        for it in items[base]:
            st, left = status[it["key"]]
            it.setdefault("after", {})[s.name] = {"status": st, "left": left}
    out = {"blank_min": region.blank_min, "bus_km": region.bus_km, "pop_threshold": region.pop_threshold,
           "ridership_year": s12_year, "blanks": {}, "planned": {}}
    # how far each planned station is from today's stations (a station inside today's walking areas fills no blank)
    for s in scenarios[1:]:
        xs, ys = p.to_xy([st.lon for st in s.stations], [st.lat for st in s.stations])
        cols = ((np.asarray(xs) - g0.x0) // g0.cell).astype(int)
        rows_ = ((np.asarray(ys) - g0.y0) // g0.cell).astype(int)
        out["planned"][s.name] = [{"name": st.name, "lon": st.lon, "lat": st.lat,
                                   "walk_m": None if np.isnan(d := float(g0.dist[r, c])) else int(round(d))}
                                  for st, r, c in zip(s.stations, rows_, cols)]
    for s in scenarios:
        lab = labels[s.name]
        renum = np.zeros(lab.max() + 1, np.int32)
        for it in items[s.name]:
            renum[it["key"]] = it["no"]
        np.save(b / f"blanks-{s.name}.npy", renum[lab])
        rows = sorted(items[s.name], key=lambda it: it["no"])
        for it in rows:
            it.pop("key")
        out["blanks"][s.name] = rows
    region.web_dir.mkdir(parents=True, exist_ok=True)
    (region.web_dir / "summary.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out
