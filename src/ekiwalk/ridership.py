"""Station ridership (国土数値情報 S12, passengers per day) per station group, for reference only."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from shapely.geometry import shape

NEAR_DEG = (0.009, 0.0075)  # about 800 m in lon / lat around Tokyo


def _latest_year_fields(props: dict):
    """S12 repeats (duplicate code, data code, note, count) per year from 2011; return the last set."""
    nums = sorted(int(m.group(1)) for k in props if (m := re.fullmatch(r"S12_0*(\d+)", k)))
    last = nums[-1]  # the count of the latest year
    year = 2011 + (last - 9) // 4
    return f"S12_{last - 3:03d}", f"S12_{last - 2:03d}", f"S12_{last:03d}", year


def parse_s12(features: list[dict]):
    """Rows with data for the latest year, skipping duplicates (counted in another row)."""
    dup_key, data_key, count_key, year = _latest_year_fields(features[0]["properties"])
    rows = []
    for f in features:
        p = f["properties"]
        if p.get(dup_key) == 1 and p.get(data_key) == 1 and p.get(count_key):
            c = shape(f["geometry"]).centroid
            rows.append({"name": p["S12_001"], "group": p["S12_001g"], "value": int(p[count_key]), "lon": c.x, "lat": c.y})
    return rows, year


def read_s12(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".geojson") and "utf-8" in n.lower())
        return parse_s12(json.loads(z.read(name).decode("utf-8"))["features"])


def ridership_for_groups(rows: list[dict], groups: dict[int, dict]) -> dict[int, int | None]:
    """Sum per station group by group code; if the code is missing, use rows of the same name nearby.

    groups: {group number: {"code", "name", "lon", "lat"}}. None = not published.
    """
    by_code = defaultdict(int)
    for r in rows:
        by_code[r["group"]] += r["value"]
    out = {}
    for k, gi in groups.items():
        v = by_code.get(gi["code"])
        if not v:
            v = sum(r["value"] for r in rows if r["name"] == gi["name"]
                    and abs(r["lon"] - gi["lon"]) < NEAR_DEG[0] and abs(r["lat"] - gi["lat"]) < NEAR_DEG[1]) or None
        out[k] = v
    return out
