from ekiwalk.ridership import parse_s12, ridership_for_groups


def _f(name, group, year_fields, lon=139.6, lat=35.7):
    p = {"S12_001": name, "S12_001g": group, "S12_002": "A", "S12_003": "L"}
    p.update(year_fields)
    return {"type": "Feature", "properties": p,
            "geometry": {"type": "LineString", "coordinates": [[lon, lat], [lon + 0.001, lat]]}}


def test_parse_s12_keeps_latest_year_non_duplicate_rows_with_data():
    feats = [
        _f("X", "001", {"S12_058": 1, "S12_059": 1, "S12_061": 1000}),
        _f("X", "001", {"S12_058": 1, "S12_059": 1, "S12_061": 500}),    # another operator: added
        _f("X", "001", {"S12_058": 2, "S12_059": 1, "S12_061": 999}),    # duplicate: skipped
        _f("Y", "002", {"S12_058": 1, "S12_059": 2, "S12_061": 0}),      # no data: skipped
    ]
    rows, year = parse_s12(feats)
    assert year == 2024
    assert [(r["name"], r["group"], r["value"]) for r in rows] == [("X", "001", 1000), ("X", "001", 500)]


def test_ridership_for_groups_matches_code_then_name_nearby():
    rows = [
        {"name": "X", "group": "001", "value": 1500, "lon": 139.6, "lat": 35.7},
        {"name": "Z", "group": "999", "value": 700, "lon": 139.7, "lat": 35.6},     # code differs from N02
        {"name": "Z", "group": "998", "value": 50, "lon": 140.5, "lat": 36.5},      # same name, far away
    ]
    groups = {0: {"code": "001", "name": "X", "lon": 139.6, "lat": 35.7},
              1: {"code": "123", "name": "Z", "lon": 139.701, "lat": 35.601},
              2: {"code": "555", "name": "W", "lon": 139.0, "lat": 35.0}}
    assert ridership_for_groups(rows, groups) == {0: 1500, 1: 700, 2: None}
