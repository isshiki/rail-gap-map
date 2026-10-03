from pathlib import Path

import pytest

from ekiwalk.config import load_region, load_scenario
from ekiwalk.geo import Projector

ROOT = Path(__file__).resolve().parents[1]


def test_load_tokyo_region():
    r = load_region("tokyo", root=ROOT)
    assert r.name == "tokyo"
    assert r.crs == "EPSG:6677"
    assert r.blank_min == 20 and r.bus_km == 5 and r.pop_threshold == 40
    assert r.bbox == (138.90, 35.47, 140.00, 35.93)
    assert r.build_dir == ROOT / "data" / "build" / "tokyo"


def test_load_scenario_base_is_empty():
    s = load_scenario("base", root=ROOT)
    assert s.name == "base"
    assert s.stations == []


def test_load_scenario_with_page_text_and_sources():
    s = load_scenario("oedo-ext", root=ROOT)
    assert s.verb == "延伸" and s.opening == "2040年頃" and s.title.endswith("？")
    assert len(s.stations) == 3 and all(src["url"].startswith("https://") for src in s.sources)


def test_unknown_region_raises():
    with pytest.raises(FileNotFoundError):
        load_region("nowhere", root=ROOT)


def test_projector_roundtrip():
    p = Projector("EPSG:6677")
    x, y = p.to_xy([139.6], [35.7])
    lon, lat = p.to_lonlat(x, y)
    assert abs(lon[0] - 139.6) < 1e-9
    assert abs(lat[0] - 35.7) < 1e-9


def test_load_osaka_region():
    r = load_region("osaka", root=ROOT)
    assert r.pref_code == "27" and r.place_name == "大阪" and r.crs == "EPSG:6674"
    assert r.n03_prefectures == ["26", "27", "28", "29", "30"]
