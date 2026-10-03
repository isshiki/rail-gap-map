import duckdb
import pytest

from ekiwalk.osmtags import WALKABLE_SQL, is_walkable


@pytest.mark.parametrize(
    "tags,expected",
    [
        ({"highway": "residential"}, True),
        ({"highway": "footway"}, True),
        ({"highway": "steps"}, True),
        ({"highway": "primary"}, True),
        ({"highway": "trunk"}, True),
        ({"highway": "motorway"}, False),
        ({"highway": "motorway_link"}, False),
        ({"highway": "trunk", "motorroad": "yes"}, False),
        ({"highway": "service", "access": "private"}, False),
        ({"highway": "service", "access": "private", "foot": "yes"}, True),
        ({"highway": "footway", "foot": "no"}, False),
        ({"highway": "construction"}, False),
        ({"highway": "proposed"}, False),
        ({"highway": "platform"}, True),
        ({"highway": "residential", "area": "yes"}, False),
        ({}, False),
    ],
)
def test_is_walkable(tags, expected):
    assert is_walkable(tags) is expected


CASES = [
    {"highway": "residential"}, {"highway": "motorway"}, {"highway": "trunk", "motorroad": "yes"},
    {"highway": "service", "access": "private"}, {"highway": "service", "access": "private", "foot": "yes"},
    {"highway": "footway", "foot": "no"}, {"highway": "residential", "area": "yes"}, {"building": "yes"},
]


def test_sql_matches_python():
    con = duckdb.connect()
    for tags in CASES:
        keys, vals = list(tags), list(tags.values())
        got = con.execute(
            f"SELECT coalesce(({WALKABLE_SQL}), false) FROM (SELECT MAP($k::VARCHAR[], $v::VARCHAR[]) AS tags)",
            {"k": keys, "v": vals},
        ).fetchone()[0]
        assert got is is_walkable(tags), tags
