import numpy as np

from ekiwalk.blanks import (blank_name, classify, excess_person_minutes, match_scenarios, municipality_blanks,
                            nearest_station_shares)


def test_classify_walk_bus_and_deep_including_roadless_land():
    dist = np.array([[100.0, 1700.0, 6000.0, np.nan, np.nan]])
    roadless = np.array([[False, False, False, True, False]])  # last cell: water / sea, not roadless land
    walk, bus, deep = classify(dist, roadless, walk_m=1600, bus_m=5000)
    assert walk.tolist() == [[True, False, False, False, False]]
    assert bus.tolist() == [[False, True, False, False, False]]
    assert deep.tolist() == [[False, False, True, True, False]]


def test_municipality_blanks_split_at_municipal_borders_not_stations():
    blank = np.zeros((6, 20), bool)
    blank[:, 2:18] = True
    muni = np.zeros((6, 20), int)
    muni[:, 12:] = 1
    inside = np.ones((6, 20), bool)
    lab, owner = municipality_blanks(blank, muni, inside, min_cells=10, closing=0)
    assert sorted(owner.values()) == [0, 1]
    assert len(np.unique(lab[:, 2:12])) == 1 and len(np.unique(lab[:, 12:18])) == 1


def test_municipality_blanks_drop_small_and_outside_parts():
    blank = np.ones((6, 10), bool)
    muni = np.zeros((6, 10), int)
    inside = np.zeros((6, 10), bool)
    inside[:, :4] = True
    lab, owner = municipality_blanks(blank, muni, inside, min_cells=5, closing=0)
    assert (lab > 0).sum() == 24 and not (lab[:, 4:] > 0).any()
    assert municipality_blanks(blank, muni, inside, min_cells=30, closing=0)[1] == {}


def test_nearest_station_shares_by_people_then_area():
    stations = np.array([3, 3, 7, 7, 7, -1])
    people = np.array([10.0, 10.0, 5.0, 0.0, 0.0, 99.0])
    assert nearest_station_shares(stations, people, min_share=0.05) == [(3, 0.8), (7, 0.2)]
    # nobody lives there (mountains): fall back to area
    assert nearest_station_shares(stations, np.zeros(6), min_share=0.05) == [(7, 0.6), (3, 0.4)]


def test_blank_name_strips_chome_and_joins_two():
    names = ["練馬区大泉学園町６丁目"] * 5 + ["練馬区大泉学園町一丁目"] * 2 + ["練馬区大泉町２丁目"] * 3 + ["練馬区東大泉三丁目"]
    assert blank_name(names) == "練馬区大泉学園町・大泉町ほか"
    assert blank_name(["調布市深大寺東町６丁目"] * 9 + ["三鷹市大沢２丁目"]) == "調布市深大寺東町"
    assert blank_name(["武蔵村山市中原一丁目"] * 6 + ["武蔵村山市三ツ木二丁目"] * 4) == "武蔵村山市中原・三ツ木"
    assert blank_name(["瑞穂町大字高根"] * 6 + ["瑞穂町大字二本木"] * 4) == "瑞穂町大字高根・大字二本木"


def test_excess_person_minutes():
    people = np.array([10.0, 10.0, 5.0])
    minutes = np.array([25.0, 15.0, 40.0])
    # 10 * 5 + 10 * 0 + 5 * 20
    assert excess_person_minutes(people, minutes, 20) == 150


def test_match_scenarios_marks_resolved_and_reuses_numbers():
    base = np.zeros((4, 12), int)
    base[:, 0:4] = 1   # will disappear
    base[:, 6:10] = 2  # will stay
    after = np.zeros((4, 12), int)
    after[:, 6:10] = 5
    status, mapping = match_scenarios(base, after)
    assert status == {1: ("解消", 0.0), 2: ("", 1.0)}
    assert mapping == {5: 2}
