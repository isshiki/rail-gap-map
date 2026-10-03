"""N03 administrative areas -> land mask, display area, municipal boundaries."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from .config import Region
from .geo import Projector

CODE_KEY = "N03_007"
NAME_KEYS = ("N03_003", "N03_004", "N03_005")  # 郡, 市区町村, 政令市の区


def read_n03(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".geojson"))
        data = json.loads(z.read(name).decode("utf-8"))
    feats = []
    for f in data["features"]:
        props = f["properties"]
        code = props.get(CODE_KEY)
        if not code:
            continue
        label = "".join(props.get(k) or "" for k in NAME_KEYS)
        feats.append({"code": code, "name": label, "geom": shape(f["geometry"])})
    return feats


def _in_display(code: str, prefixes: list[str], exclude: list[str]) -> bool:
    return code[:2] in prefixes and code not in exclude


def select_display(feats: list[dict], prefixes: list[str], exclude: list[str]):
    return unary_union([f["geom"] for f in feats if _in_display(f["code"], prefixes, exclude)])


def project(geom, projector: Projector):
    return transform(lambda x, y, z=None: projector.to_xy(x, y), geom)


def run(region: Region, zips: list[Path]) -> dict:
    p = Projector(region.crs)
    feats = [f for z in zips for f in read_n03(z)]
    if not feats:
        raise RuntimeError("N03 の地物が読めませんでした")
    land = project(unary_union([f["geom"] for f in feats]), p)
    display = project(select_display(feats, region.display_prefixes, region.display_exclude_codes), p)
    by_code: dict[str, list] = {}
    names = {}
    for f in feats:
        # "xx000" is 所属未定地 (unassigned land): part of the display area, but not a municipality
        if _in_display(f["code"], region.display_prefixes, region.display_exclude_codes) and not f["code"].endswith("000"):
            by_code.setdefault(f["code"], []).append(f["geom"])
            names[f["code"]] = f["name"]
    boundaries = [{"code": c, "name": names[c], "geom": unary_union(g)} for c, g in by_code.items()]
    region.build_dir.mkdir(parents=True, exist_ok=True)
    (region.build_dir / "land.wkb").write_bytes(shapely.to_wkb(shapely.make_valid(land)))
    (region.build_dir / "display.wkb").write_bytes(shapely.to_wkb(shapely.make_valid(display)))
    return {"boundaries": boundaries}


def municipality_grid(region: Region, zip_path: Path, g, projector: Projector):
    """Index of the listed municipality containing each grid cell (-1 elsewhere), and their display names."""
    import numpy as np

    from .surface import cell_centers_mask

    by_code: dict[str, list] = {}
    names = {}
    for f in read_n03(zip_path):
        # "xx000" is 所属未定地 (unassigned land), not a municipality
        if _in_display(f["code"], region.display_prefixes, region.display_exclude_codes) and not f["code"].endswith("000"):
            by_code.setdefault(f["code"], []).append(f["geom"])
            names[f["code"]] = f["name"].split("郡")[-1]  # 西多摩郡瑞穂町 -> 瑞穂町
    ny, nx = g.dist.shape
    muni = np.full((ny, nx), -1, np.int32)
    order = sorted(by_code)
    for i, code in enumerate(order):
        geom = project(unary_union(by_code[code]), projector)
        minx, miny, maxx, maxy = geom.bounds
        c0, c1 = max(int((minx - g.x0) // g.cell), 0), min(int((maxx - g.x0) // g.cell) + 1, nx)
        r0, r1 = max(int((miny - g.y0) // g.cell), 0), min(int((maxy - g.y0) // g.cell) + 1, ny)
        if c1 <= c0 or r1 <= r0:
            continue
        sub = cell_centers_mask(geom, g.x0 + c0 * g.cell, g.y0 + r0 * g.cell, g.cell, (r1 - r0, c1 - c0))
        view = muni[r0:r1, c0:c1]
        view[sub & (view < 0)] = i
    return muni, [names[c] for c in order]
