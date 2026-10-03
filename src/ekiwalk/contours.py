"""Grid -> isoline bands, lines, improvement area, nearest-station areas (GeoJSON)."""

from __future__ import annotations

import json
from pathlib import Path

import contourpy
import numpy as np
import pyarrow.parquet as pq
import shapely
from scipy import ndimage
from scipy.ndimage import find_objects
from shapely.geometry import Polygon, mapping
from shapely.ops import transform, unary_union

from .config import Region, Scenario
from .geo import Projector
from .surface import Grid


def _axes(g: Grid):
    ny, nx = g.dist.shape
    return g.x0 + (np.arange(nx) + 0.5) * g.cell, g.y0 + (np.arange(ny) + 0.5) * g.cell


def _gen(g: Grid, z: np.ndarray):
    x, y = _axes(g)
    return contourpy.contour_generator(
        x, y, np.ma.masked_invalid(z),
        line_type=contourpy.LineType.Separate,
        fill_type=contourpy.FillType.OuterOffset,
    )


def _polys_from_filled(filled) -> list[Polygon]:
    points_list, offsets_list = filled
    polys = []
    for pts, offs in zip(points_list, offsets_list):
        rings = [pts[offs[i]:offs[i + 1]] for i in range(len(offs) - 1)]
        rings = [r for r in rings if len(r) >= 4]
        if rings:
            polys.append(Polygon(rings[0], rings[1:]))
    return polys


def _union(polys):
    return shapely.make_valid(unary_union(polys)) if polys else shapely.MultiPolygon()


def threshold_polygons(values: np.ndarray, g: Grid, t: float):
    """Area where values >= t."""
    if not np.any(values >= t):
        return shapely.MultiPolygon()
    gen = _gen(g, values)
    return _union(_polys_from_filled(gen.filled(t, float(np.nanmax(values)) + 1.0)))


def _round(obj, nd=5):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, (list, tuple)):
        return [_round(o, nd) for o in obj]
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    return obj


def write_fc(path: Path, features: list[tuple[dict, object]]) -> None:
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": _round(mapping(geom))}
        for props, geom in features if not geom.is_empty
    ]}
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def smooth_outline(mask: np.ndarray, g: Grid, sigma: float):
    """Outline of a boolean area with the cell steps blurred away."""
    sm = ndimage.gaussian_filter(mask.astype(float), sigma)
    return threshold_polygons(sm, Grid(sm, None, g.x0, g.y0, g.cell), 0.5)


def run(region: Region, scenario: Scenario) -> None:
    """walk-, tiers-, blanks-<scenario>.geojson over the whole compute area (outside Tokyo is veiled in the app)."""
    import json

    from .territory import station_groups, territory_polygons

    b, w = region.build_dir, region.web_dir
    w.mkdir(parents=True, exist_ok=True)
    p = Projector(region.crs)
    g = Grid.load(b / f"grid-{scenario.name}.npz")
    tiers = np.load(b / f"tiers-{scenario.name}.npz")
    to_ll = lambda geom, tol=region.simplify_m: transform(
        lambda x, y, z=None: p.to_lonlat(x, y), geom.simplify(tol, preserve_topology=True) if tol else geom)

    # station walking areas: each station's territory cut at blank_min, coloured; shared edges stay shared
    st = pq.read_table(b / f"stations-{scenario.name}.parquet").to_pylist()
    gid, first = station_groups(st)
    sg = np.where(g.station >= 0, gid[np.clip(g.station, 0, None)], -1)
    colors = {int(k): v for k, v in json.loads((b / f"colors-{scenario.name}.json").read_text(encoding="utf-8")).items()}
    polys = territory_polygons(np.where(tiers["walk"], sg, -1), g, region.territory_simplify_m)
    write_fc(w / f"walk-{scenario.name}.geojson", [
        ({"group": k, "name": first[k]["name"], "planned": bool(first[k]["planned"]), "color": colors.get(k, 0)}, to_ll(geom, 0))
        for k, geom in polys.items()
    ])

    # blank tiers: bus (about 30 min by bus) and deep (beyond, or no road), smoothed
    feats = []
    for tier in ("bus", "deep"):
        sm = ndimage.gaussian_filter(tiers[tier].astype(float), 1.5)
        feats.append(({"tier": tier}, to_ll(threshold_polygons(sm, Grid(sm, None, g.x0, g.y0, g.cell), 0.5), 15)))
    write_fc(w / f"tiers-{scenario.name}.geojson", feats)

    # blank areas (per municipality): outlines for the numbers and selection
    lab = np.load(b / f"blanks-{scenario.name}.npy")
    outlines = []
    for no, sl in enumerate(find_objects(lab), start=1):
        if sl is None:
            continue
        r0, r1 = max(sl[0].start - 8, 0), min(sl[0].stop + 8, lab.shape[0])
        c0, c1 = max(sl[1].start - 8, 0), min(sl[1].stop + 8, lab.shape[1])
        sub = Grid(None, None, g.x0 + c0 * g.cell, g.y0 + r0 * g.cell, g.cell)
        outlines.append(({"no": no}, to_ll(smooth_outline(lab[r0:r1, c0:c1] == no, sub, 1.5))))
    write_fc(w / f"blanks-{scenario.name}.geojson", [f for f in outlines if not f[1].is_empty])
