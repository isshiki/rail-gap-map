"""Which OSM ways a pedestrian can use. Python rule and the equivalent SQL."""

from __future__ import annotations

EXCLUDED_HIGHWAY = {"motorway", "motorway_link", "construction", "proposed", "abandoned", "razed", "raceway", "bus_guideway", "escape"}
NO_ACCESS = {"no", "private"}
FOOT_ALLOWED = {"yes", "designated", "permissive"}


def is_walkable(tags: dict) -> bool:
    hw = tags.get("highway")
    if not hw or hw in EXCLUDED_HIGHWAY:
        return False
    if tags.get("area") == "yes":
        return False
    foot = tags.get("foot")
    if foot == "no":
        return False
    if tags.get("motorroad") == "yes" and foot not in FOOT_ALLOWED:
        return False
    if tags.get("access") in NO_ACCESS and foot not in FOOT_ALLOWED:
        return False
    return True


def _in(values: set[str]) -> str:
    return "(" + ", ".join(f"'{v}'" for v in sorted(values)) + ")"


WALKABLE_SQL = f"""
    tags['highway'] IS NOT NULL
    AND tags['highway'] NOT IN {_in(EXCLUDED_HIGHWAY)}
    AND coalesce(tags['area'], '') <> 'yes'
    AND coalesce(tags['foot'], '') <> 'no'
    AND NOT (coalesce(tags['motorroad'], '') = 'yes' AND coalesce(tags['foot'], '') NOT IN {_in(FOOT_ALLOWED)})
    AND NOT (coalesce(tags['access'], '') IN {_in(NO_ACCESS)} AND coalesce(tags['foot'], '') NOT IN {_in(FOOT_ALLOWED)})
"""
