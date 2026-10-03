"""Search index: town/chome representative points (ABR) and station names (N02).

Rows are [name, kana, lon, lat, kind] with kind "t" (town) or "s" (station). Names are kept
as published (chome may be 一丁目 or １丁目); the web app normalizes both query and names.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

NAME_COLS = ("city", "ward", "oaza_cho", "chome", "koaza")
KANA_COLS = ("city_kana", "ward_kana", "oaza_cho_kana", "chome_kana", "koaza_kana")


def town_rows(towns: list[dict], pos: list[dict]) -> list[list]:
    pts = {}
    for p in pos:
        if p.get("rep_lon") and p.get("rep_lat"):
            pts[(p["lg_code"], p["machiaza_id"], p.get("rsdt_addr_flg"))] = p
            pts.setdefault((p["lg_code"], p["machiaza_id"], None), p)
    rows = []
    for t in towns:
        key = (t["lg_code"], t["machiaza_id"])
        p = pts.get(key + (t.get("rsdt_addr_flg"),)) or pts.get(key + (None,))
        if not p:
            continue
        name = "".join(t.get(k) or "" for k in NAME_COLS)
        kana = "".join(t.get(k) or "" for k in KANA_COLS)
        rows.append([name, kana, round(float(p["rep_lon"]), 5), round(float(p["rep_lat"]), 5), "t"])
    return rows


def station_rows(stations: list[dict]) -> list[list]:
    seen, rows = set(), []
    for s in stations:
        if s["planned"] or s["group"] in seen:
            continue
        seen.add(s["group"])
        rows.append([f"{s['name']}駅", "", round(s["lon"], 5), round(s["lat"], 5), "s"])
    return rows


def read_csv_any(path: Path) -> list[dict]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            text = z.read(name).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def run(region, town_csv: Path, pos_csv: Path) -> Path:
    st = pq.read_table(region.build_dir / "stations-base.parquet").to_pylist()
    rows = town_rows(read_csv_any(town_csv), read_csv_any(pos_csv)) + station_rows(st)
    if len(rows) < 100:
        raise RuntimeError(f"検索の索引が {len(rows)} 件しかありません。ABR の列名を確かめてください")
    region.web_dir.mkdir(parents=True, exist_ok=True)
    out = region.web_dir / "places.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out
