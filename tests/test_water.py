from shapely.geometry import LineString

from ekiwalk.water import assemble_relation, is_water


def test_is_water():
    assert is_water({"natural": "water"})
    assert is_water({"waterway": "riverbank"})
    assert is_water({"landuse": "reservoir"})
    assert not is_water({"natural": "wood"})


def test_assemble_relation_from_split_outer_and_inner():
    outer = [LineString([(0, 0), (10, 0), (10, 10)]), LineString([(10, 10), (0, 10), (0, 0)])]
    inner = [LineString([(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)])]
    poly = assemble_relation(outer, inner)
    assert abs(poly.area - (100 - 4)) < 1e-9
