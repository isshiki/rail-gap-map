from shapely.geometry import LineString

from ekiwalk.config import PlannedStation
from ekiwalk.stations import add_planned, parse_station_features


def _feat(name, group, coords):
    return {
        "type": "Feature",
        "properties": {"N02_001": "12", "N02_003": "大江戸線", "N02_004": "東京都", "N02_005": name, "N02_005c": "1", "N02_005g": group},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def test_parse_keeps_stations_in_bbox():
    feats = [
        _feat("光が丘", "G1", [[139.628, 35.758], [139.630, 35.758]]),
        _feat("遠い駅", "G2", [[141.0, 38.0], [141.001, 38.0]]),
    ]
    rows = parse_station_features(feats, bbox=(139.5, 35.6, 139.7, 35.9))
    assert [r["name"] for r in rows] == ["光が丘"]
    assert rows[0]["group"] == "G1"
    assert rows[0]["planned"] is False
    assert abs(rows[0]["lon"] - 139.629) < 1e-9


def test_add_planned_appends_points():
    rows = [{"group": "G1", "name": "光が丘", "line": "大江戸線", "operator": "東京都", "planned": False,
             "geom_ll": LineString([(0, 0), (1, 0)]), "lon": 0.5, "lat": 0.0}]
    out = add_planned(rows, [PlannedStation(name="大泉学園町（仮称）", lon=139.58, lat=35.77, basis="概略図")])
    assert out[-1]["planned"] is True
    assert out[-1]["group"] == "plan:大泉学園町（仮称）"
    assert out[-1]["geom_ll"].geom_type == "Point"
