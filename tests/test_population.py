import numpy as np

from ekiwalk.population import mesh250_bounds, mesh250_code, parse_mesh_csv


def test_code_of_known_mesh_and_roundtrip():
    # KEY_CODE 5339000541: 1st 5339, 2nd 00, 3rd 05, 4th 4 (NE), 5th 1 (SW)
    w, s, e, n = mesh250_bounds(5339000541)
    assert mesh250_code(np.array([(w + e) / 2]), np.array([(s + n) / 2]))[0] == 5339000541
    assert abs((n - s) - 7.5 / 3600) < 1e-12 and abs((e - w) - 11.25 / 3600) < 1e-12


def test_codes_for_grid_points():
    lon = np.array([139.6, 139.0001, 138.9999])
    lat = np.array([35.7, 35.3334, 35.6667])
    codes = mesh250_code(lon, lat)
    for c, x, y in zip(codes, lon, lat):
        w, s, e, n = mesh250_bounds(int(c))
        assert w <= x < e and s <= y < n


def test_parse_mesh_csv_reads_total_population():
    text = (
        "KEY_CODE,HTKSYORI,HTKSAKI,GASSAN,T001142001,T001142002\n"
        ",,,,　人口（総数）,　人口（総数）　男\n"
        "5339000541,2,5339000544,,3,2\n"
        "5339000542,0,,,120,60\n"
        "5339000543,0,,,*,*\n"
    )
    pop = parse_mesh_csv(text)
    assert pop == {5339000541: 3, 5339000542: 120, 5339000543: 0}
