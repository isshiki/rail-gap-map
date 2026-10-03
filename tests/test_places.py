from ekiwalk.places import station_rows, town_rows


def test_town_rows_joins_names_and_points():
    towns = [{"lg_code": "131202", "machiaza_id": "0045006", "rsdt_addr_flg": "1", "city": "練馬区", "ward": "",
              "oaza_cho": "大泉学園町", "chome": "６丁目", "koaza": "", "city_kana": "ネリマク", "ward_kana": "",
              "oaza_cho_kana": "オオイズミガクエンチョウ", "chome_kana": "６チョウメ", "koaza_kana": ""}]
    pos = [{"lg_code": "131202", "machiaza_id": "0045006", "rsdt_addr_flg": "0", "rep_lon": "139.0", "rep_lat": "35.0"},
           {"lg_code": "131202", "machiaza_id": "0045006", "rsdt_addr_flg": "1", "rep_lon": "139.58012345", "rep_lat": "35.77123456"}]
    rows = town_rows(towns, pos)
    assert rows == [["練馬区大泉学園町６丁目", "ネリマクオオイズミガクエンチョウ６チョウメ", 139.58012, 35.77123, "t"]]


def test_town_rows_falls_back_to_other_flag_and_skips_missing():
    towns = [{"lg_code": "1", "machiaza_id": "a", "rsdt_addr_flg": "1", "city": "X区", "oaza_cho": "Y町"},
             {"lg_code": "1", "machiaza_id": "b", "rsdt_addr_flg": "1", "city": "X区", "oaza_cho": "Z町"}]
    pos = [{"lg_code": "1", "machiaza_id": "a", "rsdt_addr_flg": "0", "rep_lon": "139.1", "rep_lat": "35.1"}]
    assert [r[0] for r in town_rows(towns, pos)] == ["X区Y町"]


def test_station_rows_dedupes_groups_and_skips_planned():
    st = [{"group": "G1", "name": "光が丘", "lon": 139.62861, "lat": 35.75811, "planned": False},
          {"group": "G1", "name": "光が丘", "lon": 139.62862, "lat": 35.75812, "planned": False},
          {"group": "plan:大泉学園町（仮称）", "name": "大泉学園町（仮称）", "lon": 139.58, "lat": 35.77, "planned": True}]
    assert station_rows(st) == [["光が丘駅", "", 139.62861, 35.75811, "s"]]
