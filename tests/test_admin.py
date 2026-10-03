from shapely.geometry import box

from ekiwalk.admin import select_display


def test_select_display_excludes_islands():
    feats = [
        {"code": "13120", "name": "練馬区", "geom": box(0, 0, 1, 1)},
        {"code": "13361", "name": "大島町", "geom": box(5, 5, 6, 6)},
        {"code": "11230", "name": "新座市", "geom": box(1, 0, 2, 1)},
    ]
    shape = select_display(feats, prefixes=["13"], exclude=["13361"])
    assert abs(shape.area - 1.0) < 1e-9
