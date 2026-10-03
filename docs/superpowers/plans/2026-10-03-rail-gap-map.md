# rail-gap-map 実装計画

> この文書は初期実装時の計画の記録です。コード例・チェック欄は当時の内容で、現在の実装状況を示すものではありません。現在の実行手順は [README.md](../../../README.md)、作業上の決まりは [AGENTS.md](../../../AGENTS.md) を参照してください。特定のAI製品やプラグインは必要ありません。

**Goal:** 東京 (島しょを除く) の「最寄り駅まで徒歩何分か」を等距離線で描く静的 Web アプリと、それを作る Python のデータ作成パイプラインを作る。大江戸線延伸の前後比較と、自分の場所の検索を含む。

**Architecture:** OSM の歩ける道を DuckDB で読んでグラフにし、国土数値情報の駅から多始点ダイクストラで道のりを求める。道のりを 25 m 格子へ補間して contourpy で等値線と帯にし、GeoJSON で `web/data/` に書き出す。画面はビルド無しの HTML + MapLibre GL JS で、検索と地点判定はブラウザ内だけで行う。

**Tech Stack:** Python 3.13 / uv、duckdb (spatial)、numpy、scipy、shapely、pyproj、contourpy、pyarrow、pytest。Web は MapLibre GL JS 6.11.2 (unpkg)、テストは `node --test` (Node 25)。

**設計書:** `docs/superpowers/specs/2026-10-03-rail-gap-map-design.md`

**全体の約束 (どのタスクでも守る):**
- データのダウンロード前に、ファイル名・取得元 URL・大きさを利用者に示して確認を取る。確認が取れるまで取得しない。
- `git add` の前に `git status --short --untracked-files=all` を見る。1 MiB を超えるファイルは理由を調べる。`data/` の中は絶対に追加しない。
- `git push` は利用者の確認後だけ行う。
- 依存は `uv add` で足す。
- 特定のAIエージェント名義のコミット署名は指定しない。
- テストは `uv run --offline --frozen pytest -q`、Web のテストは `node --test web/test/lookup.test.js web/test/search.test.js` で実行する。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `pyproject.toml` | パッケージ `ekiwalk` と依存 |
| `configs/regions/tokyo.toml` | 東京の範囲・座標系・段階など |
| `configs/regions/oizumi-test.toml` | 試運転用の小さな範囲 (大泉学園町付近 約 4 km 四方) |
| `configs/scenarios/oedo-ext.toml` | 大江戸線延伸の予定駅 |
| `configs/sources.toml` | ダウンロードするファイルの URL・ファイル名・期待サイズ |
| `src/ekiwalk/config.py` | 設定ファイルの読み込み (`Region`, `Scenario`) |
| `src/ekiwalk/fetch.py` | 確認済みファイルの取得と SHA-256 の記録 |
| `src/ekiwalk/geo.py` | 座標変換 (WGS84 ⇔ 平面直角) の小さな関数 |
| `src/ekiwalk/osmtags.py` | 歩ける道の判定 (タグだけを見る純粋関数) |
| `src/ekiwalk/network.py` | PBF → 節点表・辺表 (Parquet) |
| `src/ekiwalk/water.py` | PBF → 水域ポリゴン |
| `src/ekiwalk/admin.py` | N03 → 陸地・表示範囲・区市町村界 |
| `src/ekiwalk/stations.py` | N02 → 駅表 (Parquet) + シナリオの予定駅 |
| `src/ekiwalk/shortest.py` | 多始点ダイクストラ |
| `src/ekiwalk/surface.py` | 辺の点打ち・格子への補間・空白の指定・ぼかし |
| `src/ekiwalk/contours.py` | 格子 → 帯・線・差分・最寄り駅範囲の GeoJSON |
| `src/ekiwalk/places.py` | 町丁目 (ABR) と駅名 → 検索用 JSON |
| `src/ekiwalk/cli.py` | `uv run ekiwalk <段階>` |
| `web/index.html` `web/style.css` | 画面 |
| `web/js/main.js` | 地図・レイヤー・切り替え・地点表示 |
| `web/js/lookup.js` | 点がどの帯・どの駅範囲に入るか (純粋関数) |
| `web/js/search.js` | 検索の正規化と照合 (純粋関数) |
| `web/test/*.test.js` | `node --test` 用テスト |
| `docs/data-policy.md` `docs/sources/*.md` `docs/limitations.md` | 記録 |
| `.github/workflows/pages.yml` | `web/` を GitHub Pages へ |

中間成果物は `data/build/<region>/` に置く。

| ファイル | 中身 |
|---|---|
| `nodes.parquet` | `node_id, x, y` |
| `edges.parquet` | `u, v, length_m` |
| `water.wkb` | 水域ポリゴン |
| `admin.npz` | 陸地・表示範囲 |
| `stations.parquet` | 駅表 |
| `solve-<scenario>.parquet` | `node_id, dist_m, station_idx` |
| `grid-<scenario>.npz` | `dist`, `station`, `x0, y0, cell` |

`<scenario>` は延伸前が `base`、延伸後が `oedo-ext`。

---

### Task 1: プロジェクトの土台

**Files:**
- Create: `pyproject.toml`, `src/ekiwalk/__init__.py`, `README.md`, `docs/data-policy.md`, `tests/__init__.py`

- [ ] **Step 1: pyproject.toml を書く**

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "rail-gap-map"
version = "0.1.0"
description = "Walking-distance isolines to the nearest railway station, built from public data."
readme = "README.md"
requires-python = ">=3.11"
license = "Apache-2.0"
license-files = ["LICENSE"]
dependencies = []

[project.scripts]
ekiwalk = "ekiwalk.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/ekiwalk"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`src/ekiwalk/__init__.py` は `"""Shared pipeline: walking network, stations, shortest paths, isolines."""` の 1 行にする。`tests/__init__.py` は空にする。

- [ ] **Step 2: 依存を足す**

```bash
uv add "duckdb>=1.5,<2" "numpy>=2" "scipy>=1.14" "shapely>=2.1" "pyproj>=3.7" "contourpy>=1.3" "pyarrow>=20"
uv add --dev "pytest>=8"
```

- [ ] **Step 3: DuckDB spatial が使えるか確認する**

```bash
uv run python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL spatial; LOAD spatial'); print(c.execute(\"SELECT MAP(['highway'],['footway'])['highway']\").fetchone())"
```

期待される出力: `('footway',)` (DuckDB 1.5 では map の添字が値を返す)

- [ ] **Step 4: README.md を書く**

```markdown
# rail-gap-map

**This repository uses only publicly obtainable data. No proprietary company data is included.**

最寄り駅まで歩いて何分かを等距離線 (徒歩 5・10・15・20・25・30・45・60 分) で描き、駅から遠い「鉄道の空白地帯」を見せる地図です。都営大江戸線の延伸 (光が丘〜大泉学園町) の前後も比べられます。

- 地図: (公開後に GitHub Pages の URL を書く)
- 設計: [docs/superpowers/specs/2026-10-03-rail-gap-map-design.md](docs/superpowers/specs/2026-10-03-rail-gap-map-design.md)
- 地図の限界: [docs/limitations.md](docs/limitations.md)
- データと出典: [docs/data-policy.md](docs/data-policy.md)

## 作り方 (再現手順)

Python 3.11 以上と uv を使います。

    uv sync --locked
    uv run ekiwalk fetch --all          # 取得するファイルを表示し、確認後にダウンロード
    uv run ekiwalk build --region tokyo --scenario base --scenario oedo-ext

生成物は `web/data/tokyo/` に書かれます。`web/` を静的サーバーで配信すると地図が開きます。

    uv run python -m http.server -d web 8000

## ライセンス

コードとオリジナルの文書は [Apache License 2.0](LICENSE) です。`web/data/` の地図データは外部データの派生物で、各データのライセンスに従います (詳細は [docs/data-policy.md](docs/data-policy.md))。
```

- [ ] **Step 5: docs/data-policy.md を書く**

```markdown
# データポリシー

このリポジトリは個人ブログと連動する公開プロジェクトです。公開されていて取得できるデータだけを使います。会社のコード・データ・文書は一切入れません ([AGENTS.md](../AGENTS.md))。

## Git に入れるもの・入れないもの

- 入れるもの: コード、設定、手順、データ源の記録 (`docs/sources/`)、`web/data/` の生成物
- 入れないもの: ダウンロードした生データ (`data/raw/`)、中間成果物 (`data/build/`)、キャッシュ、認証情報

## web/data/ のライセンス

`web/data/` の GeoJSON / JSON は次のデータから作った派生物です。

| ファイル | 元データ | ライセンス |
|---|---|---|
| `bands-*.geojson` `lines-*.geojson` `diff-*.geojson` `catchments-*.geojson` | OpenStreetMap (道路・水域)、国土数値情報 N02・N03 | **ODbL 1.0** (OSM の派生データベース)。出典: © OpenStreetMap contributors、「国土数値情報（鉄道データ・行政区域データ）」（国土交通省）をもとに作成 |
| `stations.geojson` | 国土数値情報 N02 | CC BY 4.0 |
| `boundaries.geojson` | 国土数値情報 N03 | CC BY 4.0 |
| `places.json` | アドレス・ベース・レジストリ (デジタル庁)、国土数値情報 N02 | CC BY 4.0 |

国が作成したように見える使い方はしません。データ源ごとの版・取得日・SHA-256 は `docs/sources/` に記録します。

## データ源

| データ | 記録 |
|---|---|
| OpenStreetMap 関東抽出 (Geofabrik) | [sources/osm.md](sources/osm.md) |
| 国土数値情報 鉄道データ N02-25 | [sources/n02.md](sources/n02.md) |
| 国土数値情報 行政区域 N03 | [sources/n03.md](sources/n03.md) |
| アドレス・ベース・レジストリ 町字マスター | [sources/abr.md](sources/abr.md) |
| 地理院タイル | [sources/gsi-tiles.md](sources/gsi-tiles.md) |
| 大江戸線延伸の資料 (東京都・練馬区) | [sources/oedo-extension.md](sources/oedo-extension.md) |
```

- [ ] **Step 6: 確認してコミットする**

```bash
uv run pytest -q   # "no tests ran" で終了コード 5 になるのは想定どおり
git status --short --untracked-files=all
git add pyproject.toml uv.lock src/ekiwalk/__init__.py tests/__init__.py README.md docs/data-policy.md
git commit -m "Scaffold ekiwalk package, README and data policy"
```

---

### Task 2: 設定ファイルと読み込み

**Files:**
- Create: `configs/regions/tokyo.toml`, `configs/regions/oizumi-test.toml`, `configs/scenarios/oedo-ext.toml`, `src/ekiwalk/config.py`, `src/ekiwalk/geo.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: 設定ファイルを書く**

`configs/regions/tokyo.toml`:

```toml
name = "tokyo"
label = "東京都 (島しょを除く)"
crs = "EPSG:6677"              # 平面直角座標系 IX 系 (JGD2011)
# 表示範囲: N03 の行政区域コードの先頭が一致するもの。島しょ (13360〜13421) は exclude で除く
display_prefixes = ["13"]
display_exclude_codes = ["13361", "13362", "13363", "13364", "13381", "13382", "13401", "13402", "13421"]
compute_buffer_m = 3000
# 計算用の外枠 (WGS84)。PBF から切り出す範囲。表示範囲 + 3 km を十分に含む
bbox = [138.90, 35.47, 140.00, 35.93]
n03_prefectures = ["11", "12", "13", "14"]
osm_source = "osm-kanto"
cell_m = 25
walk_m_per_min = 80
levels_min = [5, 10, 15, 20, 25, 30, 45, 60]
access_radius_m = 100
max_offroad_m = 300
smooth_sigma_cells = 1.0
simplify_m = 5
home_view = { center = [139.60, 35.69], zoom = 10 }
```

`configs/regions/oizumi-test.toml`:

```toml
name = "oizumi-test"
label = "試運転: 大泉学園町付近"
crs = "EPSG:6677"
display_prefixes = ["13"]
display_exclude_codes = []
compute_buffer_m = 1500
bbox = [139.555, 35.735, 139.640, 35.785]
n03_prefectures = ["11", "13"]
osm_source = "osm-kanto"
cell_m = 25
walk_m_per_min = 80
levels_min = [5, 10, 15, 20, 25, 30, 45, 60]
access_radius_m = 100
max_offroad_m = 300
smooth_sigma_cells = 1.0
simplify_m = 5
home_view = { center = [139.597, 35.760], zoom = 13 }
```

`configs/scenarios/oedo-ext.toml` (座標は Task 11 で推定して書き換える。それまでは駅を空にしておく):

```toml
name = "oedo-ext"
label = "大江戸線延伸後"
note = "東京都の検討資料 (2025-10-15) の概略図から筆者が位置を推定した。座標は公表されていない。開業は2040年頃の想定 (未確定)。"
stations = []
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_config.py`:

```python
from pathlib import Path

import pytest

from ekiwalk.config import load_region, load_scenario
from ekiwalk.geo import Projector

ROOT = Path(__file__).resolve().parents[1]


def test_load_tokyo_region():
    r = load_region("tokyo", root=ROOT)
    assert r.name == "tokyo"
    assert r.crs == "EPSG:6677"
    assert r.levels_m == [400, 800, 1200, 1600, 2000, 2400, 3600, 4800]
    assert r.bbox == (138.90, 35.47, 140.00, 35.93)
    assert r.build_dir == ROOT / "data" / "build" / "tokyo"


def test_load_scenario_base_is_empty():
    s = load_scenario("base", root=ROOT)
    assert s.name == "base"
    assert s.stations == []


def test_unknown_region_raises():
    with pytest.raises(FileNotFoundError):
        load_region("nowhere", root=ROOT)


def test_projector_roundtrip():
    p = Projector("EPSG:6677")
    x, y = p.to_xy([139.6], [35.7])
    lon, lat = p.to_lonlat(x, y)
    assert abs(lon[0] - 139.6) < 1e-9
    assert abs(lat[0] - 35.7) < 1e-9
```

- [ ] **Step 3: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_config.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'ekiwalk.config'`)

- [ ] **Step 4: config.py と geo.py を書く**

`src/ekiwalk/config.py`:

```python
"""Load region and scenario settings from configs/."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PlannedStation:
    name: str
    lon: float
    lat: float
    basis: str


@dataclass(frozen=True)
class Scenario:
    name: str
    label: str
    note: str = ""
    stations: list[PlannedStation] = field(default_factory=list)


@dataclass(frozen=True)
class Region:
    name: str
    label: str
    crs: str
    display_prefixes: list[str]
    display_exclude_codes: list[str]
    compute_buffer_m: float
    bbox: tuple[float, float, float, float]
    n03_prefectures: list[str]
    osm_source: str
    cell_m: float
    walk_m_per_min: float
    levels_min: list[int]
    access_radius_m: float
    max_offroad_m: float
    smooth_sigma_cells: float
    simplify_m: float
    home_view: dict
    root: Path

    @property
    def levels_m(self) -> list[float]:
        return [m * self.walk_m_per_min for m in self.levels_min]

    @property
    def build_dir(self) -> Path:
        return self.root / "data" / "build" / self.name

    @property
    def web_dir(self) -> Path:
        return self.root / "web" / "data" / self.name


def _read(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"設定ファイルがありません: {path}")
    with path.open("rb") as f:
        return tomllib.load(f)


def load_region(name: str, root: Path = ROOT) -> Region:
    d = _read(root / "configs" / "regions" / f"{name}.toml")
    d["bbox"] = tuple(d["bbox"])
    return Region(**d, root=root)


def load_scenario(name: str, root: Path = ROOT) -> Scenario:
    if name == "base":
        return Scenario(name="base", label="現在")
    d = _read(root / "configs" / "scenarios" / f"{name}.toml")
    stations = [PlannedStation(**s) for s in d.pop("stations", [])]
    return Scenario(**d, stations=stations)
```

`src/ekiwalk/geo.py`:

```python
"""Coordinate transforms between WGS84 and a projected metric CRS."""

from __future__ import annotations

import numpy as np
from pyproj import Transformer


class Projector:
    def __init__(self, crs: str):
        self.crs = crs
        self._fwd = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        self._inv = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def to_xy(self, lon, lat):
        x, y = self._fwd.transform(np.asarray(lon, float), np.asarray(lat, float))
        return np.asarray(x), np.asarray(y)

    def to_lonlat(self, x, y):
        lon, lat = self._inv.transform(np.asarray(x, float), np.asarray(y, float))
        return np.asarray(lon), np.asarray(lat)
```

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run pytest tests/test_config.py -q`
Expected: `4 passed`

- [ ] **Step 6: コミットする**

```bash
git add configs src/ekiwalk/config.py src/ekiwalk/geo.py tests/test_config.py
git commit -m "Add region/scenario configs and loaders"
```

---

### Task 3: ダウンロードの仕組みとデータ源の記録

**Files:**
- Create: `configs/sources.toml`, `src/ekiwalk/fetch.py`, `docs/sources/osm.md`, `docs/sources/n02.md`, `docs/sources/n03.md`, `docs/sources/abr.md`, `docs/sources/gsi-tiles.md`, `docs/sources/oedo-extension.md`
- Test: `tests/test_fetch.py`

- [ ] **Step 1: 各配布ページで URL とファイル名を確かめ、configs/sources.toml を書く**

次の値はこの計画を書いた時点 (2026-10-03) で確かめたもの。N03 と ABR はファイル名を配布ページで確かめてから書く。

- 確認済み: `osm-kanto` (HEAD 応答、ETag から 515,684,430 bytes)、`n02` (配布ページに 14.2 MB とある)
- 未確認: N03 は国土数値情報の N03 配布ページ (`https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2025.html` か、それより新しい年の版) で、県別の zip 名と大きさを読む。ABR はデジタル庁のデータセットサイトで「東京都 町字マスター」と「東京都 町字マスター位置参照拡張」の CSV の URL・大きさ・ライセンスを読む。

```toml
# 取得するファイル。size_hint は確認時に利用者へ示す目安
[osm-kanto]
url = "https://download.geofabrik.de/asia/japan/kanto-261001.osm.pbf"
file = "kanto-261001.osm.pbf"
size_hint = "約 492 MB (515,684,430 bytes)"
license = "ODbL 1.0"

[n02]
url = "https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-25/N02-25_GML.zip"
file = "N02-25_GML.zip"
size_hint = "14.2 MB"
license = "CC BY 4.0"

# N03・ABR は配布ページで確かめた URL・大きさを同じ形で書く:
# [n03-11] [n03-12] [n03-13] [n03-14] [abr-town-13] [abr-town-pos-13]
```

- [ ] **Step 2: 失敗するテストを書く**

`tests/test_fetch.py`:

```python
import hashlib
import json

from ekiwalk.fetch import load_sources, record_file


def test_load_sources(tmp_path):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "sources.toml").write_text(
        '[a]\nurl = "https://example.org/a.zip"\nfile = "a.zip"\nsize_hint = "1 MB"\nlicense = "CC BY 4.0"\n',
        encoding="utf-8",
    )
    s = load_sources(tmp_path)
    assert s["a"]["file"] == "a.zip"


def test_record_file_writes_sha256(tmp_path):
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True)
    f = raw / "a.zip"
    f.write_bytes(b"hello")
    record_file(tmp_path, "a", {"url": "https://example.org/a.zip", "file": "a.zip"})
    manifest = json.loads((raw / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["a"]["sha256"] == hashlib.sha256(b"hello").hexdigest()
    assert manifest["a"]["bytes"] == 5
    assert manifest["a"]["retrieved_utc"].endswith("Z")
```

- [ ] **Step 3: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_fetch.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: fetch.py を書く**

ダウンロード本体は `urllib.request` で行う。CLI は取得前に一覧を表示して `y` を待つ。ただし**この計画を実行するエージェントは、CLI を使う前に必ずチャットで利用者の確認を取る**。

```python
"""Download confirmed source files into data/raw/ and record SHA-256."""

from __future__ import annotations

import hashlib
import json
import tomllib
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def load_sources(root: Path) -> dict:
    with (root / "configs" / "sources.toml").open("rb") as f:
        return tomllib.load(f)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_file(root: Path, key: str, src: dict) -> dict:
    raw = root / "data" / "raw"
    path = raw / src["file"]
    manifest_path = raw / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    entry = {
        "url": src["url"],
        "file": src["file"],
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    manifest[key] = entry
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def download(root: Path, key: str, src: dict) -> dict:
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    path = raw / src["file"]
    if not path.exists():
        tmp = path.with_suffix(path.suffix + ".part")
        req = urllib.request.Request(src["url"], headers={"User-Agent": "rail-gap-map (personal research)"})
        with urllib.request.urlopen(req) as r, tmp.open("wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        tmp.replace(path)
    return record_file(root, key, src)


def raw_path(root: Path, key: str) -> Path:
    src = load_sources(root)[key]
    path = root / "data" / "raw" / src["file"]
    if not path.exists():
        raise FileNotFoundError(f"{key} がありません: {path}  先に `uv run ekiwalk fetch {key}` を実行してください")
    return path
```

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run pytest tests/test_fetch.py -q`
Expected: `2 passed`

- [ ] **Step 6: データ源の記録を書く**

各 `docs/sources/*.md` に、次の表を埋めて書く (取得前に書けるところまで)。

| 項目 | 内容 |
|---|---|
| データセット | 正式名称・提供者・配布 URL |
| 利用条件 | ライセンス名・版・規約 URL・確認日 (2026-10-03) |
| 出典表記 | 画面とブログに載せる文 |
| 再配布 | `web/data/` に含める派生物の扱い |
| 版 | release / 基準日 |
| 取得 | 取得日時 (UTC)・バイト数・SHA-256 (取得後に manifest から転記) |
| 使い方 | 計算範囲・使う属性 |

書く内容 (確認済みの事実):

- `osm.md`: Geofabrik `kanto-261001.osm.pbf`、ODbL 1.0、「© OpenStreetMap contributors」、https://www.openstreetmap.org/copyright 。日付付きファイルは月次・年次で残る (https://download.geofabrik.de/asia/japan/kanto.html)。
- `n02.md`: N02-25、基準日 2025-12-31、CC BY 4.0、出典例「『国土数値情報（鉄道データ）』（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html）をもとに作成」。駅は線データ。属性 N02_001 鉄道区分、N02_003 路線名、N02_004 運営会社、N02_005 駅名、N02_005c 駅コード、N02_005g グループコード (同じ駅名で 300 m 以内の駅をまとめる)。規約 https://nlftp.mlit.go.jp/ksj/other/agreement.html 。
- `n03.md`: 行政区域、CC BY 4.0、版は取得時に書く。
- `abr.md`: アドレス・ベース・レジストリ (デジタル庁)、https://dataset.address-br.digital.go.jp/ 、CC BY 4.0 (取得時に再確認する)。
- `gsi-tiles.md`: 淡色地図 `https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png`。リアルタイム読み込みなので申請不要。出典「地理院タイル」+ https://maps.gsi.go.jp/development/ichiran.html 。
- `oedo-extension.md`: 東京都 都市整備局 PDF (2025-10-15) https://www.toshiseibi.metro.tokyo.lg.jp/documents/d/toshiseibi/2025-10-15-111344-482 、練馬区 https://www.city.nerima.tokyo.jp/kusei/machi/kunai_tetsudo/ooedoenshin.html 。約 4 km、3 駅 (仮称 土支田・大泉町・大泉学園町)、開業は 2040 年頃の想定。座標は公表されていない。

- [ ] **Step 7: コミットする**

```bash
git add configs/sources.toml src/ekiwalk/fetch.py tests/test_fetch.py docs/sources
git commit -m "Add source registry, download recorder and source docs"
```

- [ ] **Step 8: 利用者の確認を取ってから取得する**

チャットで、次を 1 件ずつ (または一覧で) 示して確認を取る。

- `n02`: `N02-25_GML.zip`、nlftp.mlit.go.jp、14.2 MB
- `n03-*`: 県別の zip のファイル名と大きさ
- `abr-*`: CSV のファイル名と大きさ
- `osm-kanto`: `kanto-261001.osm.pbf`、download.geofabrik.de、約 492 MB

確認が取れたものだけ、Task 13 の CLI ができる前は次で取得する。

```bash
uv run python -c "from ekiwalk.fetch import load_sources, download; from ekiwalk.config import ROOT; s=load_sources(ROOT); print(download(ROOT, 'n02', s['n02']))"
```

取得後、`data/raw/manifest.json` の bytes・sha256・retrieved_utc を `docs/sources/*.md` に転記してコミットする。

---

### Task 4: 歩ける道の判定 (タグ)

**Files:**
- Create: `src/ekiwalk/osmtags.py`
- Test: `tests/test_osmtags.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
import pytest

from ekiwalk.osmtags import is_walkable


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
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_osmtags.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: osmtags.py を書く**

Python の関数をテストの基準にし、同じ規則を DuckDB の SQL 文字列 `WALKABLE_SQL` にも書く。Task 5 で両者が一致することを確かめる。

```python
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
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_osmtags.py -q`
Expected: `16 passed`

- [ ] **Step 5: SQL も同じ判定になるかのテストを足す**

`tests/test_osmtags.py` に追記する。

```python
import duckdb

from ekiwalk.osmtags import WALKABLE_SQL

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
```

Run: `uv run pytest tests/test_osmtags.py -q`
Expected: `17 passed`

- [ ] **Step 6: コミットする**

```bash
git add src/ekiwalk/osmtags.py tests/test_osmtags.py
git commit -m "Add pedestrian way filter (Python and SQL)"
```

---

### Task 5: 道路網 (PBF → 節点・辺)

**Files:**
- Create: `src/ekiwalk/network.py`
- Test: `tests/test_network.py`

方針: OSM の節点をそのままグラフの節点にし、way の隣り合う節点の組を辺にする。交差点での分割は要らない (同じ OSM 節点を共有する way は自然につながる)。長さは平面直角座標で測る。最大の連結成分だけを残す。

- [ ] **Step 1: 失敗するテストを書く (PBF を読まない部分)**

```python
import numpy as np

from ekiwalk.network import build_edges, largest_component


def test_build_edges_from_way_refs():
    ways = [[1, 2, 3], [3, 4]]
    node_ids = np.array([1, 2, 3, 4])
    xy = np.array([[0, 0], [3, 4], [3, 10], [6, 10]], float)
    u, v, length = build_edges(ways, node_ids, xy)
    assert list(zip(u.tolist(), v.tolist())) == [(0, 1), (1, 2), (2, 3)]
    assert np.allclose(length, [5.0, 6.0, 3.0])


def test_build_edges_skips_missing_nodes_and_duplicates():
    ways = [[1, 2, 99, 3], [2, 1]]
    node_ids = np.array([1, 2, 3])
    xy = np.array([[0, 0], [1, 0], [2, 0]], float)
    u, v, length = build_edges(ways, node_ids, xy)
    # 99 は範囲外なので 2-99, 99-3 は捨てる。2-1 は 1-2 と重複なので捨てる
    assert list(zip(u.tolist(), v.tolist())) == [(0, 1)]


def test_largest_component_keeps_biggest():
    u = np.array([0, 1, 3])
    v = np.array([1, 2, 4])
    keep = largest_component(5, u, v)
    assert keep.tolist() == [True, True, True, False, False]
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_network.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: network.py を書く**

```python
"""OSM PBF -> walking graph (nodes.parquet, edges.parquet)."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .config import Region
from .geo import Projector
from .osmtags import WALKABLE_SQL

log = logging.getLogger(__name__)


def build_edges(ways, node_ids: np.ndarray, xy: np.ndarray):
    """ways: list of OSM node-id lists. node_ids sorted. Returns (u, v, length) as index arrays."""
    order = np.argsort(node_ids)
    sorted_ids = node_ids[order]
    us, vs = [], []
    for refs in ways:
        r = np.asarray(refs, dtype=np.int64)
        pos = np.searchsorted(sorted_ids, r)
        pos[pos >= len(sorted_ids)] = 0
        ok = sorted_ids[pos] == r
        idx = np.where(ok, order[pos], -1)
        a, b = idx[:-1], idx[1:]
        m = (a >= 0) & (b >= 0) & (a != b)
        us.append(a[m])
        vs.append(b[m])
    u = np.concatenate(us) if us else np.empty(0, np.int64)
    v = np.concatenate(vs) if vs else np.empty(0, np.int64)
    lo, hi = np.minimum(u, v), np.maximum(u, v)
    # drop duplicate edges, keeping first-seen order
    first = {}
    for i, (a, b) in enumerate(zip(lo.tolist(), hi.tolist())):
        first.setdefault((a, b), i)
    pairs = sorted(first, key=first.get)
    u = np.array([p[0] for p in pairs], dtype=np.int64)
    v = np.array([p[1] for p in pairs], dtype=np.int64)
    length = np.hypot(*(xy[u] - xy[v]).T)
    return u, v, length


def largest_component(n: int, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    g = coo_matrix((np.ones(len(u)), (u, v)), shape=(n, n))
    _, labels = connected_components(g, directed=False)
    counts = np.bincount(labels)
    return labels == np.argmax(counts)


def read_walk_ways(pbf: Path, bbox) -> tuple[list[list[int]], np.ndarray, np.ndarray, np.ndarray]:
    """Return (ways, node_ids, lon, lat) for walkable ways touching bbox."""
    w, s, e, n = bbox
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(
        f"""CREATE TEMP TABLE nodes AS
            SELECT id, lon, lat FROM ST_ReadOSM('{pbf.as_posix()}')
            WHERE kind = 'node' AND lon BETWEEN {w} AND {e} AND lat BETWEEN {s} AND {n}"""
    )
    con.execute(
        f"""CREATE TEMP TABLE ways AS
            SELECT id, refs FROM ST_ReadOSM('{pbf.as_posix()}')
            WHERE kind = 'way' AND ({WALKABLE_SQL})"""
    )
    con.execute(
        """CREATE TEMP TABLE used AS
           SELECT DISTINCT r AS id FROM (SELECT unnest(refs) AS r FROM ways) JOIN nodes ON nodes.id = r"""
    )
    nodes = con.execute("SELECT n.id, n.lon, n.lat FROM nodes n JOIN used USING (id) ORDER BY n.id").fetchnumpy()
    ways = [r[0] for r in con.execute(
        "SELECT refs FROM ways WHERE list_has_any(refs, (SELECT list(id) FROM used))"
    ).fetchall()]
    return ways, nodes["id"].astype(np.int64), nodes["lon"], nodes["lat"]


def run(region: Region, pbf: Path) -> None:
    out = region.build_dir
    out.mkdir(parents=True, exist_ok=True)
    ways, ids, lon, lat = read_walk_ways(pbf, region.bbox)
    if len(ids) < 100:
        raise RuntimeError(f"歩ける道の節点が {len(ids)} 個しかありません。bbox か PBF を確かめてください")
    x, y = Projector(region.crs).to_xy(lon, lat)
    xy = np.column_stack([x, y])
    u, v, length = build_edges(ways, ids, xy)
    keep = largest_component(len(ids), u, v)
    log.info("nodes=%d edges=%d dropped_nodes=%d", len(ids), len(u), int((~keep).sum()))
    new_index = np.cumsum(keep) - 1
    m = keep[u] & keep[v]
    pq.write_table(pa.table({"node_id": ids[keep], "x": x[keep], "y": y[keep]}), out / "nodes.parquet")
    pq.write_table(pa.table({"u": new_index[u[m]], "v": new_index[v[m]], "length_m": length[m]}), out / "edges.parquet")
```

注: `read_walk_ways` の `list_has_any(... (SELECT list(id) FROM used))` は東京規模では重い。Step 5 の試運転で遅ければ、`ways` を unnest して `used` と結合する次の形に置き換える。

```sql
SELECT id, list(r ORDER BY ord) AS refs
FROM (SELECT id, unnest(refs) AS r, generate_subscripts(refs, 1) AS ord FROM ways)
GROUP BY id
HAVING bool_or(r IN (SELECT id FROM used))
```

`build_edges` は範囲外の節点を -1 にして辺を捨てるので、どちらの形でも結果は同じになる。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_network.py -q`
Expected: `3 passed`

- [ ] **Step 5: 実データで試運転する (osm-kanto の取得後)**

```bash
uv run python -c "import logging; logging.basicConfig(level=logging.INFO); from ekiwalk.config import load_region, ROOT; from ekiwalk.fetch import raw_path; from ekiwalk import network; network.run(load_region('oizumi-test'), raw_path(ROOT, 'osm-kanto'))"
```

Expected: `nodes=... edges=...` がログに出て、`data/build/oizumi-test/nodes.parquet` と `edges.parquet` ができる。節点は数万程度、捨てた節点は全体の数 % 以下になるはず。かかった時間を記録する。

- [ ] **Step 6: コミットする**

```bash
git add src/ekiwalk/network.py tests/test_network.py
git commit -m "Build walking graph from OSM PBF via DuckDB"
```

---

### Task 6: 水域 (PBF → ポリゴン)

**Files:**
- Create: `src/ekiwalk/water.py`
- Test: `tests/test_water.py`

方針: 閉じた way (`natural=water`、`waterway=riverbank`、`landuse=reservoir`、`water=*`) はそのまま多角形にする。マルチポリゴンの relation は、outer の way の線を `shapely.ops.linemerge` → `polygonize` で輪にし、inner を引く。

- [ ] **Step 1: 失敗するテストを書く**

```python
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
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_water.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: water.py を書く**

```python
"""OSM PBF -> water polygons (projected CRS), saved as WKB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union

from .config import Region
from .geo import Projector


def is_water(tags: dict) -> bool:
    return (
        tags.get("natural") == "water"
        or tags.get("waterway") == "riverbank"
        or tags.get("landuse") == "reservoir"
        or ("water" in tags and tags.get("natural") in (None, "water"))
    )


WATER_SQL = """(tags['natural'] = 'water' OR tags['waterway'] = 'riverbank' OR tags['landuse'] = 'reservoir'
                OR (tags['water'] IS NOT NULL AND coalesce(tags['natural'], 'water') = 'water'))"""


def assemble_relation(outer: list[LineString], inner: list[LineString]):
    outer_polys = list(polygonize(linemerge(outer))) if outer else []
    if not outer_polys:
        return None
    shape = unary_union(outer_polys)
    inner_polys = list(polygonize(linemerge(inner))) if inner else []
    if inner_polys:
        shape = shape.difference(unary_union(inner_polys))
    return shape


def run(region: Region, pbf: Path) -> None:
    w, s, e, n = region.bbox
    p = Projector(region.crs)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    src = f"ST_ReadOSM('{pbf.as_posix()}')"
    con.execute(f"CREATE TEMP TABLE osm_rel AS SELECT id, tags, refs, ref_roles, ref_types FROM {src} WHERE kind='relation' AND tags['type']='multipolygon' AND {WATER_SQL}")
    con.execute(f"""CREATE TEMP TABLE w AS
        SELECT id, refs, ({WATER_SQL}) AS is_water_way FROM {src}
        WHERE kind='way' AND (({WATER_SQL}) OR id IN (SELECT unnest(refs) FROM osm_rel))""")
    con.execute(f"""CREATE TEMP TABLE nd AS SELECT id, lon, lat FROM {src}
        WHERE kind='node' AND lon BETWEEN {w} AND {e} AND lat BETWEEN {s} AND {n}
          AND id IN (SELECT unnest(refs) FROM w)""")
    nodes = con.execute("SELECT id, lon, lat FROM nd ORDER BY id").fetchnumpy()
    ids = nodes["id"]
    x, y = p.to_xy(nodes["lon"], nodes["lat"])

    def line(refs):
        r = np.asarray(refs, np.int64)
        pos = np.searchsorted(ids, r)
        pos[pos >= len(ids)] = 0
        ok = ids[pos] == r
        if ok.sum() < 2:
            return None
        return LineString(np.column_stack([x[pos[ok]], y[pos[ok]]]))

    way_lines = {}
    polys = []
    for wid, refs, is_ww in con.execute("SELECT id, refs, is_water_way FROM w").fetchall():
        ln = line(refs)
        if ln is None:
            continue
        way_lines[wid] = ln
        if is_ww and refs[0] == refs[-1] and len(ln.coords) >= 4:
            polys.append(Polygon(ln.coords))
    for _, _, refs, roles, types in con.execute("SELECT * FROM osm_rel").fetchall():
        outer = [way_lines[r] for r, role, t in zip(refs, roles, types) if t == "way" and role != "inner" and r in way_lines]
        inner = [way_lines[r] for r, role, t in zip(refs, roles, types) if t == "way" and role == "inner" and r in way_lines]
        shape = assemble_relation(outer, inner)
        if shape is not None and not shape.is_empty:
            polys.append(shape)
    water = shapely.make_valid(unary_union(polys)) if polys else shapely.GeometryCollection()
    region.build_dir.mkdir(parents=True, exist_ok=True)
    (region.build_dir / "water.wkb").write_bytes(shapely.to_wkb(water))
```

注: bbox の境界で切れた relation は輪にならず、捨てられる。計算範囲の外側 3 km の中で起きるので、表示範囲には影響しない。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_water.py -q`
Expected: `2 passed`

- [ ] **Step 5: 試運転して面積で確かめる**

```bash
uv run python -c "import shapely; from ekiwalk.config import load_region, ROOT; from ekiwalk.fetch import raw_path; from ekiwalk import water; r=load_region('oizumi-test'); water.run(r, raw_path(ROOT,'osm-kanto')); g=shapely.from_wkb((r.build_dir/'water.wkb').read_bytes()); print(g.geom_type, round(g.area/1e6,3), 'km2')"
```

Expected: 面積は小さい (白子川や池の分。0.01〜0.5 km² 程度)。0 なら SQL の条件を確かめる。

- [ ] **Step 6: コミットする**

```bash
git add src/ekiwalk/water.py tests/test_water.py
git commit -m "Extract OSM water polygons for masking"
```

---

### Task 7: 行政区域 (N03 → 陸地・表示範囲・区市町村界)

**Files:**
- Create: `src/ekiwalk/admin.py`
- Test: `tests/test_admin.py`

N03 の zip には GeoJSON が入っている (取得後にファイル名を確かめる)。属性は `N03_001` 都道府県名、`N03_004` 区市町村名、`N03_007` 行政区域コード。版によってコードが `N03_007` でない場合は、取得後に属性名を確かめて定数 `CODE_KEY` を直す。

- [ ] **Step 1: 失敗するテストを書く**

```python
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
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_admin.py -q`
Expected: FAIL

- [ ] **Step 3: admin.py を書く**

```python
"""N03 administrative areas -> land mask, display area, municipal boundaries."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import shapely
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from .config import Region
from .geo import Projector

CODE_KEY = "N03_007"
NAME_KEYS = ("N03_003", "N03_004")


def read_n03(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".geojson"))
        data = json.loads(z.read(name).decode("utf-8"))
    feats = []
    for f in data["features"]:
        props = f["properties"]
        code = props.get(CODE_KEY)
        if not code:
            continue
        label = "".join(props.get(k) or "" for k in NAME_KEYS)
        feats.append({"code": code, "name": label, "geom": shape(f["geometry"])})
    return feats


def select_display(feats: list[dict], prefixes: list[str], exclude: list[str]):
    return unary_union([f["geom"] for f in feats if f["code"][:2] in prefixes and f["code"] not in exclude])


def project(geom, projector: Projector):
    return transform(lambda x, y, z=None: projector.to_xy(x, y), geom)


def run(region: Region, zips: list[Path]) -> dict:
    p = Projector(region.crs)
    feats = [f for z in zips for f in read_n03(z)]
    if not feats:
        raise RuntimeError("N03 の地物が読めませんでした")
    land = project(unary_union([f["geom"] for f in feats]), p)
    display = project(select_display(feats, region.display_prefixes, region.display_exclude_codes), p)
    by_code: dict[str, list] = {}
    names = {}
    for f in feats:
        if f["code"][:2] in region.display_prefixes and f["code"] not in region.display_exclude_codes:
            by_code.setdefault(f["code"], []).append(f["geom"])
            names[f["code"]] = f["name"]
    boundaries = [{"code": c, "name": names[c], "geom": unary_union(g)} for c, g in by_code.items()]
    region.build_dir.mkdir(parents=True, exist_ok=True)
    (region.build_dir / "land.wkb").write_bytes(shapely.to_wkb(shapely.make_valid(land)))
    (region.build_dir / "display.wkb").write_bytes(shapely.to_wkb(shapely.make_valid(display)))
    return {"boundaries": boundaries}
```

`boundaries` (WGS84 のまま) は Task 13 の export で `boundaries.geojson` に書く。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_admin.py -q`
Expected: `1 passed`

- [ ] **Step 5: 実データで東京の面積を確かめる (N03 の取得後)**

島しょを除いた東京都の面積は約 1,780 km² (都の総面積約 2,194 km² から島しょ約 406 km² を引いた値)。±5% 以内なら良しとする。外れたら除外コードを確かめる。

```bash
uv run python -c "import shapely; from ekiwalk.config import load_region, ROOT; from ekiwalk.fetch import raw_path; from ekiwalk import admin; r=load_region('tokyo'); admin.run(r, [raw_path(ROOT,f'n03-{c}') for c in r.n03_prefectures]); print(round(shapely.from_wkb((r.build_dir/'display.wkb').read_bytes()).area/1e6), 'km2')"
```

- [ ] **Step 6: コミットする**

```bash
git add src/ekiwalk/admin.py tests/test_admin.py
git commit -m "Read N03 for land mask, display area and boundaries"
```

---

### Task 8: 駅 (N02 → 駅表、予定駅)

**Files:**
- Create: `src/ekiwalk/stations.py`
- Test: `tests/test_stations.py`

駅表の列: `idx`(0 始まり)、`group`(N02_005g。予定駅は `plan:<名前>`)、`name`、`line`、`operator`、`planned`(bool)、`wkb`(平面直角の線または点)、`lon`、`lat`(代表点 = 線の中点)。

- [ ] **Step 1: 失敗するテストを書く**

```python
from shapely.geometry import LineString, box

from ekiwalk.config import PlannedStation
from ekiwalk.stations import parse_station_features, add_planned


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
    rows = [{"group": "G1", "name": "光が丘", "line": "大江戸線", "operator": "東京都", "planned": False, "geom_ll": LineString([(0, 0), (1, 0)]), "lon": 0.5, "lat": 0.0}]
    out = add_planned(rows, [PlannedStation(name="大泉学園町（仮称）", lon=139.58, lat=35.77, basis="概略図")])
    assert out[-1]["planned"] is True
    assert out[-1]["group"] == "plan:大泉学園町（仮称）"
    assert out[-1]["geom_ll"].geom_type == "Point"
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_stations.py -q`
Expected: FAIL

- [ ] **Step 3: stations.py を書く**

```python
"""N02 stations (platform line segments) + planned stations -> stations.parquet."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from shapely.geometry import Point, box, shape
from shapely.ops import transform

from .config import PlannedStation, Region, Scenario
from .geo import Projector


def read_n02_station_features(zip_path: Path) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        cands = [n for n in z.namelist() if n.lower().endswith(".geojson") and "station" in n.lower()]
        if not cands:
            raise RuntimeError(f"Station の GeoJSON が見つかりません: {z.namelist()[:20]}")
        data = json.loads(z.read(cands[0]).decode("utf-8"))
    return data["features"]


def parse_station_features(features: list[dict], bbox) -> list[dict]:
    area = box(*bbox)
    rows = []
    for f in features:
        g = shape(f["geometry"])
        if not g.intersects(area):
            continue
        p = f["properties"]
        mid = g.interpolate(0.5, normalized=True) if g.geom_type == "LineString" else g.centroid
        rows.append({
            "group": p.get("N02_005g") or p.get("N02_005c") or p["N02_005"],
            "name": p["N02_005"],
            "line": p.get("N02_003", ""),
            "operator": p.get("N02_004", ""),
            "planned": False,
            "geom_ll": g,
            "lon": mid.x,
            "lat": mid.y,
        })
    return rows


def add_planned(rows: list[dict], planned: list[PlannedStation]) -> list[dict]:
    out = list(rows)
    for s in planned:
        out.append({
            "group": f"plan:{s.name}", "name": s.name, "line": "", "operator": "", "planned": True,
            "geom_ll": Point(s.lon, s.lat), "lon": s.lon, "lat": s.lat,
        })
    return out


def run(region: Region, scenario: Scenario, zip_path: Path) -> Path:
    p = Projector(region.crs)
    rows = add_planned(parse_station_features(read_n02_station_features(zip_path), region.bbox), scenario.stations)
    if sum(not r["planned"] for r in rows) < 3:
        raise RuntimeError("範囲内の駅が 3 未満です。bbox を確かめてください")
    geoms = [transform(lambda x, y, z=None: p.to_xy(x, y), r["geom_ll"]) for r in rows]
    table = pa.table({
        "idx": list(range(len(rows))),
        "group": [r["group"] for r in rows],
        "name": [r["name"] for r in rows],
        "line": [r["line"] for r in rows],
        "operator": [r["operator"] for r in rows],
        "planned": [r["planned"] for r in rows],
        "lon": [r["lon"] for r in rows],
        "lat": [r["lat"] for r in rows],
        "wkb": [shapely.to_wkb(g) for g in geoms],
    })
    region.build_dir.mkdir(parents=True, exist_ok=True)
    out = region.build_dir / f"stations-{scenario.name}.parquet"
    pq.write_table(table, out)
    return out
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_stations.py -q`
Expected: `2 passed`

- [ ] **Step 5: 実データで確かめる (N02 の取得後)**

```bash
uv run python -c "from ekiwalk.config import load_region, load_scenario, ROOT; from ekiwalk.fetch import raw_path; from ekiwalk import stations; import pyarrow.parquet as pq; r=load_region('oizumi-test'); t=pq.read_table(stations.run(r, load_scenario('base'), raw_path(ROOT,'n02'))); print(t.num_rows, sorted(set(t.column('name').to_pylist())))"
```

Expected: 光が丘・大泉学園・保谷・和光市・地下鉄成増・成増 などが入る。zip の中の GeoJSON 名と属性名を `docs/sources/n02.md` に書く。

- [ ] **Step 6: コミットする**

```bash
git add src/ekiwalk/stations.py tests/test_stations.py
git commit -m "Parse N02 stations and add planned stations"
```

---

### Task 9: 多始点ダイクストラ

**Files:**
- Create: `src/ekiwalk/shortest.py`
- Test: `tests/test_shortest.py`

方針: 駅ごとに仮の節点を 1 つ足す。その駅の線から `access_radius_m` 以内のグラフ節点へ「直線距離 + 0.001」の辺を張る (scipy は重み 0 の辺を無視するため)。半径内に節点が無い駅は、最も近い 1 節点につなぐ。仮の節点をすべて出発点にし、`min_only=True` で 1 回解く。`sources` が仮の節点の番号を返すので、それを駅番号に戻す。

- [ ] **Step 1: 失敗するテストを書く**

```python
import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve


def test_two_stations_on_a_line():
    # 0 --100-- 1 --100-- 2 --100-- 3 --100-- 4
    xy = np.array([[0, 0], [100, 0], [200, 0], [300, 0], [400, 0]], float)
    u = np.array([0, 1, 2, 3])
    v = np.array([1, 2, 3, 4])
    length = np.full(4, 100.0)
    stations = [Point(0, 10), Point(400, 0)]
    dist, nearest = solve(xy, u, v, length, stations, access_radius_m=50)
    assert np.allclose(dist, [10, 110, 200, 100, 0], atol=0.01)
    # 節点 2 は駅 0 から 210 m、駅 1 から 200 m なので駅 1
    assert nearest.tolist() == [0, 0, 1, 1, 1]


def test_platform_line_reaches_several_nodes():
    xy = np.array([[0, 0], [100, 0], [200, 0]], float)
    u, v, length = np.array([0, 1]), np.array([1, 2]), np.array([100.0, 100.0])
    platform = LineString([(0, 20), (200, 20)])
    dist, nearest = solve(xy, u, v, length, [platform], access_radius_m=50)
    assert np.allclose(dist, [20, 20, 20], atol=0.01)


def test_station_without_nodes_in_radius_uses_nearest_node():
    xy = np.array([[0, 0], [100, 0]], float)
    u, v, length = np.array([0]), np.array([1]), np.array([100.0])
    dist, nearest = solve(xy, u, v, length, [Point(-500, 0)], access_radius_m=100)
    assert np.allclose(dist, [500, 600], atol=0.01)
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_shortest.py -q`
Expected: FAIL

- [ ] **Step 3: shortest.py を書く**

```python
"""Multi-source Dijkstra from all stations at once."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from .config import Region, Scenario

EPS = 1e-3


def solve(xy: np.ndarray, u, v, length, stations: list, access_radius_m: float):
    """Return (dist_m per node, nearest station index per node)."""
    n, k = len(xy), len(stations)
    tree = cKDTree(xy)
    su, sv, sw = [], [], []
    for i, geom in enumerate(stations):
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        reach = np.hypot(maxx - minx, maxy - miny) / 2 + access_radius_m
        cand = np.asarray(tree.query_ball_point([cx, cy], reach), dtype=np.int64)
        if len(cand):
            d = shapely.distance(shapely.points(xy[cand]), geom)
            cand, d = cand[d <= access_radius_m], d[d <= access_radius_m]
        if len(cand) == 0:
            pt = geom.interpolate(0.5, normalized=True) if geom.geom_type == "LineString" else geom
            dd, j = tree.query([pt.x, pt.y])
            cand, d = np.array([j]), np.array([shapely.distance(shapely.points(xy[j]), geom)])
        su.append(np.full(len(cand), n + i))
        sv.append(cand)
        sw.append(d + EPS)
    uu = np.concatenate([u] + su)
    vv = np.concatenate([v] + sv)
    ww = np.concatenate([np.asarray(length, float)] + sw)
    g = coo_matrix((ww, (uu, vv)), shape=(n + k, n + k)).tocsr()
    dist, _, src = dijkstra(g, directed=False, indices=np.arange(n, n + k), min_only=True, return_predecessors=True)
    dist = dist[:n] - EPS
    nearest = np.where(src[:n] >= n, src[:n] - n, -1)
    return dist, nearest


def run(region: Region, scenario: Scenario) -> None:
    b = region.build_dir
    nodes = pq.read_table(b / "nodes.parquet")
    edges = pq.read_table(b / "edges.parquet")
    st = pq.read_table(b / f"stations-{scenario.name}.parquet")
    xy = np.column_stack([nodes["x"].to_numpy(), nodes["y"].to_numpy()])
    geoms = list(shapely.from_wkb(st["wkb"].to_numpy(zero_copy_only=False)))
    dist, nearest = solve(xy, edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy(), geoms, region.access_radius_m)
    unreached = int(np.isinf(dist).sum())
    if unreached:
        raise RuntimeError(f"{unreached} 個の節点に届きません (グラフが分かれています)")
    pq.write_table(pa.table({"node_id": nodes["node_id"], "dist_m": dist, "station_idx": nearest}), b / f"solve-{scenario.name}.parquet")
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_shortest.py -q`
Expected: `3 passed`

- [ ] **Step 5: コミットする**

```bash
git add src/ekiwalk/shortest.py tests/test_shortest.py
git commit -m "Add multi-source Dijkstra with platform-line access"
```

---

### Task 10: 格子への補間と空白

**Files:**
- Create: `src/ekiwalk/surface.py`
- Test: `tests/test_surface.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
import numpy as np
from shapely.geometry import box

from ekiwalk.surface import densify_edges, grid_from_points, mask_geometry, smooth_nan


def test_densify_interpolates_along_edge():
    xy = np.array([[0, 0], [100, 0]], float)
    pts, d, st = densify_edges(xy, np.array([0]), np.array([1]), np.array([100.0]),
                               dist=np.array([0.0, 300.0]), station=np.array([0, 1]), step=20)
    # 端 A は 0、端 B は 300 (節点の値はそのまま)。辺上の 4 点は min(0 + s, 300 + 100 - s) = s
    assert np.allclose(sorted(d), [0, 20, 40, 60, 80, 300])
    assert st[2:].tolist() == [0, 0, 0, 0]


def test_grid_adds_offroad_distance_and_blanks_far_cells():
    pts = np.array([[0.0, 0.0]])
    grid = grid_from_points(pts, np.array([100.0]), np.array([7]), x0=0, y0=0, nx=20, ny=1, cell=25, max_offroad=300, k=1)
    # セル中心 x = 12.5, 37.5, ...
    assert abs(grid.dist[0, 0] - (100 + 12.5)) < 1e-6
    assert np.isnan(grid.dist[0, 12])  # 312.5 m 離れている
    assert grid.station[0, 0] == 7 and grid.station[0, 12] == -1


def test_mask_geometry_blanks_inside():
    dist = np.zeros((4, 4))
    out = mask_geometry(dist, box(0, 0, 50, 50), x0=0, y0=0, cell=25, inside=True)
    assert np.isnan(out[0, 0]) and np.isnan(out[1, 1]) and not np.isnan(out[3, 3])


def test_smooth_nan_does_not_spread_blanks():
    a = np.ones((5, 5)) * 10
    a[2, 2] = np.nan
    s = smooth_nan(a, sigma=1.0)
    assert np.isnan(s[2, 2])
    assert np.allclose(s[0, 0], 10)
```

格子の向き: `dist[row, col]`、行 `r` のセル中心は `y0 + (r + 0.5) * cell`、列 `c` は `x0 + (c + 0.5) * cell`。y は下から上へ増える。

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_surface.py -q`
Expected: FAIL

- [ ] **Step 3: surface.py を書く**

```python
"""Node distances -> 25 m grid with blanks (water, sea, far from roads)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyarrow.parquet as pq
import shapely
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from .config import Region, Scenario


@dataclass
class Grid:
    dist: np.ndarray
    station: np.ndarray
    x0: float
    y0: float
    cell: float

    def save(self, path):
        np.savez_compressed(path, dist=self.dist.astype(np.float32), station=self.station.astype(np.int32),
                            x0=self.x0, y0=self.y0, cell=self.cell)

    @staticmethod
    def load(path) -> "Grid":
        z = np.load(path)
        return Grid(z["dist"].astype(float), z["station"], float(z["x0"]), float(z["y0"]), float(z["cell"]))


def densify_edges(xy, u, v, length, dist, station, step: float):
    pts, ds, sts = [xy], [dist], [station]
    for a, b, L in zip(u, v, length):
        n = int(np.ceil(L / step)) - 1  # interior points, spacing <= step
        if n < 1:
            continue
        s = np.arange(1, n + 1) * (L / (n + 1))
        t = (s / L)[:, None]
        p = xy[a] * (1 - t) + xy[b] * t
        da, db = dist[a] + s, dist[b] + (L - s)
        pts.append(p)
        ds.append(np.minimum(da, db))
        sts.append(np.where(da <= db, station[a], station[b]))
    return np.vstack(pts), np.concatenate(ds), np.concatenate(sts)


def grid_from_points(pts, d, st, x0, y0, nx, ny, cell, max_offroad, k=8, chunk_rows=200) -> Grid:
    tree = cKDTree(pts)
    dist = np.full((ny, nx), np.nan)
    station = np.full((ny, nx), -1, dtype=np.int32)
    xs = x0 + (np.arange(nx) + 0.5) * cell
    for r0 in range(0, ny, chunk_rows):
        r1 = min(ny, r0 + chunk_rows)
        ys = y0 + (np.arange(r0, r1) + 0.5) * cell
        gx, gy = np.meshgrid(xs, ys)
        q = np.column_stack([gx.ravel(), gy.ravel()])
        kk = min(k, len(pts))
        dd, ii = tree.query(q, k=kk, distance_upper_bound=max_offroad, workers=-1)
        if kk == 1:
            dd, ii = dd[:, None], ii[:, None]
        valid = np.isfinite(dd)
        ii_safe = np.where(valid, ii, 0)
        total = np.where(valid, d[ii_safe] + dd, np.inf)
        best = np.argmin(total, axis=1)
        val = total[np.arange(len(q)), best]
        ok = np.isfinite(val)
        dist[r0:r1] = np.where(ok, val, np.nan).reshape(r1 - r0, nx)
        station[r0:r1] = np.where(ok, st[ii_safe[np.arange(len(q)), best]], -1).reshape(r1 - r0, nx)
    return Grid(dist, station, x0, y0, cell)


def cell_centers_mask(geom, x0, y0, cell, shape_):
    ny, nx = shape_
    xs = x0 + (np.arange(nx) + 0.5) * cell
    ys = y0 + (np.arange(ny) + 0.5) * cell
    gx, gy = np.meshgrid(xs, ys)
    shapely.prepare(geom)
    return shapely.contains_xy(geom, gx, gy)


def mask_geometry(dist, geom, x0, y0, cell, inside: bool):
    m = cell_centers_mask(geom, x0, y0, cell, dist.shape)
    out = dist.copy()
    out[m if inside else ~m] = np.nan
    return out


def smooth_nan(a, sigma: float):
    if sigma <= 0:
        return a
    valid = np.isfinite(a)
    num = gaussian_filter(np.where(valid, a, 0.0), sigma)
    den = gaussian_filter(valid.astype(float), sigma)
    out = num / np.where(den > 0, den, 1)
    out[~valid] = np.nan
    return out


def run(region: Region, scenario: Scenario) -> Grid:
    b = region.build_dir
    nodes = pq.read_table(b / "nodes.parquet")
    edges = pq.read_table(b / "edges.parquet")
    sol = pq.read_table(b / f"solve-{scenario.name}.parquet")
    xy = np.column_stack([nodes["x"].to_numpy(), nodes["y"].to_numpy()])
    pts, d, st = densify_edges(xy, edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy(),
                               sol["dist_m"].to_numpy(), sol["station_idx"].to_numpy(), step=20)
    land = shapely.from_wkb((b / "land.wkb").read_bytes())
    display = shapely.from_wkb((b / "display.wkb").read_bytes())
    minx, miny, maxx, maxy = display.buffer(region.cell_m * 4).bounds
    cell = region.cell_m
    x0, y0 = np.floor(minx / cell) * cell, np.floor(miny / cell) * cell
    nx, ny = int(np.ceil((maxx - x0) / cell)), int(np.ceil((maxy - y0) / cell))
    g = grid_from_points(pts, d, st, x0, y0, nx, ny, cell, region.max_offroad_m)
    g.dist = mask_geometry(g.dist, land, x0, y0, cell, inside=False)
    water = shapely.from_wkb((b / "water.wkb").read_bytes())
    if not water.is_empty:
        g.dist = mask_geometry(g.dist, water, x0, y0, cell, inside=True)
    g.station[np.isnan(g.dist)] = -1
    g.save(b / f"grid-{scenario.name}.npz")
    return g
```

注: グリッドの外枠は表示範囲 + 100 m にする。計算範囲 (外側 3 km) の道路と駅はダイクストラで使い終わっているので、格子は表示範囲だけで足りる。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_surface.py -q`
Expected: `4 passed`

- [ ] **Step 5: コミットする**

```bash
git add src/ekiwalk/surface.py tests/test_surface.py
git commit -m "Interpolate distances to grid with water/sea/off-road blanks"
```

---

### Task 11: 等値線・帯・差分・最寄り駅範囲

**Files:**
- Create: `src/ekiwalk/contours.py`
- Test: `tests/test_contours.py`

出力の形:

| ファイル | 地物の属性 |
|---|---|
| `bands-<s>.geojson` | 帯 1 つにつき MultiPolygon 1 つ。`{"lo": 0, "hi": 5}`。最後の帯は `{"lo": 60, "hi": null}` |
| `lines-<s>.geojson` | 段階 1 つにつき MultiLineString 1 つ。`{"min": 10}` |
| `diff-<s>.geojson` | 1 地物。`{"improved_min": 5}` |
| `catchments-<s>.geojson` | 駅のまとまり (group) 1 つにつき 1 地物。`{"name": "光が丘", "planned": false}` |

- [ ] **Step 1: 失敗するテストを書く**

```python
import math

import numpy as np
from shapely.geometry import shape

from ekiwalk.contours import band_polygons, level_lines, threshold_polygons
from ekiwalk.surface import Grid


def radial_grid(n=201, cell=10.0):
    c = (n * cell) / 2
    xs = (np.arange(n) + 0.5) * cell
    gx, gy = np.meshgrid(xs, xs)
    return Grid(np.hypot(gx - c, gy - c), np.zeros((n, n), np.int32), 0.0, 0.0, cell), c


def test_level_line_is_circle_of_right_radius():
    g, c = radial_grid()
    lines = level_lines(g, [400.0])
    geom = lines[400.0]
    r = np.array([math.hypot(x - c, y - c) for x, y in geom.geoms[0].coords])
    assert np.all(np.abs(r - 400) < 5)


def test_band_area_matches_annulus():
    g, c = radial_grid()
    bands = band_polygons(g, [400.0, 800.0])
    a = bands[(400.0, 800.0)].area
    assert abs(a - math.pi * (800**2 - 400**2)) / a < 0.02


def test_nan_cells_are_not_in_bands():
    g, c = radial_grid()
    g.dist[:, :50] = np.nan
    bands = band_polygons(g, [400.0, 800.0])
    assert bands[(400.0, 800.0)].bounds[0] >= 50 * g.cell - g.cell


def test_threshold_polygons_excludes_inner_disc():
    # threshold_polygons(values, grid, t) は「値 >= t の範囲」を返す
    g, c = radial_grid()
    poly = threshold_polygons(g.dist, g, 300.0)
    from shapely.geometry import Point
    assert not poly.contains(Point(c, c))
    assert abs(poly.area - (g.dist.size * g.cell**2 - math.pi * 300**2)) / poly.area < 0.02
    assert poly.contains(Point(c + 600, c))


def test_catchment_polygons_split_by_group():
    from ekiwalk.contours import catchment_polygons
    st = np.zeros((10, 20), np.int32)
    st[:, 10:] = 1
    st[0, 0] = -1  # blank cell
    g = Grid(np.ones((10, 20)), st, 0.0, 0.0, 10.0)
    cps = catchment_polygons(g, groups=np.array([0, 1]))
    assert set(cps) == {0, 1}
    assert abs(cps[1].area - 100 * 100) / (100 * 100) < 0.1
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_contours.py -q`
Expected: FAIL

- [ ] **Step 3: contours.py を書く**

```python
"""Grid -> isoline bands, lines, improvement area, nearest-station areas (GeoJSON)."""

from __future__ import annotations

import json
from pathlib import Path

import contourpy
import numpy as np
import pyarrow.parquet as pq
import shapely
from scipy.ndimage import find_objects
from shapely.geometry import LineString, MultiLineString, Polygon, mapping
from shapely.ops import transform, unary_union

from .config import Region, Scenario
from .geo import Projector
from .surface import Grid, smooth_nan


def _axes(g: Grid):
    ny, nx = g.dist.shape
    return g.x0 + (np.arange(nx) + 0.5) * g.cell, g.y0 + (np.arange(ny) + 0.5) * g.cell


def _gen(g: Grid, z: np.ndarray):
    x, y = _axes(g)
    return contourpy.contour_generator(
        x, y, np.ma.masked_invalid(z),
        line_type=contourpy.LineType.Separate,
        fill_type=contourpy.FillType.OuterOffset,
    )


def _polys_from_filled(filled) -> list[Polygon]:
    points_list, offsets_list = filled
    polys = []
    for pts, offs in zip(points_list, offsets_list):
        rings = [pts[offs[i]:offs[i + 1]] for i in range(len(offs) - 1)]
        rings = [r for r in rings if len(r) >= 4]
        if rings:
            polys.append(Polygon(rings[0], rings[1:]))
    return polys


def band_polygons(g: Grid, levels: list[float]) -> dict:
    gen = _gen(g, g.dist)
    out = {}
    for lo, hi in zip(levels[:-1], levels[1:]):
        out[(lo, hi)] = shapely.make_valid(unary_union(_polys_from_filled(gen.filled(lo, hi))))
    return out


def level_lines(g: Grid, levels: list[float]) -> dict:
    gen = _gen(g, g.dist)
    return {lv: MultiLineString([LineString(a) for a in gen.lines(lv) if len(a) >= 2]) for lv in levels}


def threshold_polygons(values: np.ndarray, g: Grid, t: float):
    gen = _gen(g, values)
    hi = float(np.nanmax(values)) + 1.0
    return shapely.make_valid(unary_union(_polys_from_filled(gen.filled(t, hi))))


def _to_ll(geom, p: Projector, simplify_m: float, clip):
    geom = geom.intersection(clip).simplify(simplify_m, preserve_topology=True)
    return transform(lambda x, y, z=None: p.to_lonlat(x, y), geom)


def _round(obj, nd=5):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, (list, tuple)):
        return [_round(o, nd) for o in obj]
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    return obj


def write_fc(path: Path, features: list[dict]) -> None:
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": props, "geometry": _round(mapping(geom))}
        for props, geom in features if not geom.is_empty
    ]}
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def catchment_polygons(g: Grid, groups: np.ndarray) -> dict:
    """groups: station_idx -> group number. Returns {group_number: polygon}."""
    gid = np.where(g.station >= 0, groups[np.clip(g.station, 0, None)], -1)
    out = {}
    for k, sl in enumerate(find_objects(gid + 1)):
        if sl is None:
            continue
        # index k <-> label k+1 in gid+1 <-> group k (blank -1 becomes 0, which find_objects ignores)
        r0, r1 = max(sl[0].start - 1, 0), min(sl[0].stop + 1, gid.shape[0])
        c0, c1 = max(sl[1].start - 1, 0), min(sl[1].stop + 1, gid.shape[1])
        sub = Grid((gid[r0:r1, c0:c1] == k).astype(float), g.station[r0:r1, c0:c1],
                   g.x0 + c0 * g.cell, g.y0 + r0 * g.cell, g.cell)
        out[int(k)] = threshold_polygons(sub.dist, sub, 0.5)
    return out


def run(region: Region, scenario: Scenario, compare_to: str | None = None) -> None:
    b, w = region.build_dir, region.web_dir
    w.mkdir(parents=True, exist_ok=True)
    p = Projector(region.crs)
    clip = shapely.from_wkb((b / "display.wkb").read_bytes())
    g = Grid.load(b / f"grid-{scenario.name}.npz")
    g.dist = smooth_nan(g.dist, region.smooth_sigma_cells)
    levels = region.levels_m
    edges = [0.0] + levels + [float(np.nanmax(g.dist)) + 1.0]
    bands = band_polygons(g, edges)
    mpm = region.walk_m_per_min
    write_fc(w / f"bands-{scenario.name}.geojson", [
        ({"lo": round(lo / mpm), "hi": (round(hi / mpm) if hi in levels else None)}, _to_ll(geom, p, region.simplify_m, clip))
        for (lo, hi), geom in bands.items()
    ])
    lines = level_lines(g, levels)
    write_fc(w / f"lines-{scenario.name}.geojson", [
        ({"min": round(lv / mpm)}, _to_ll(geom, p, region.simplify_m, clip)) for lv, geom in lines.items()
    ])
    st = pq.read_table(b / f"stations-{scenario.name}.parquet")
    group_names = st["group"].to_pylist()
    uniq = {gname: i for i, gname in enumerate(dict.fromkeys(group_names))}
    groups = np.array([uniq[x] for x in group_names])
    first_row = {uniq[x]: i for i, x in reversed(list(enumerate(group_names)))}
    cps = catchment_polygons(g, groups)
    write_fc(w / f"catchments-{scenario.name}.geojson", [
        ({"name": st["name"][first_row[k]].as_py(), "planned": bool(st["planned"][first_row[k]].as_py())},
         _to_ll(geom, p, region.simplify_m, clip)) for k, geom in cps.items()
    ])
    if compare_to:
        before = Grid.load(b / f"grid-{compare_to}.npz")
        before.dist = smooth_nan(before.dist, region.smooth_sigma_cells)
        gain = before.dist - g.dist
        poly = threshold_polygons(gain, g, 5 * mpm)
        write_fc(w / f"diff-{scenario.name}.geojson", [({"improved_min": 5}, _to_ll(poly, p, region.simplify_m, clip))])
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_contours.py -q`
Expected: `5 passed`

- [ ] **Step 5: コミットする**

```bash
git add src/ekiwalk/contours.py tests/test_contours.py
git commit -m "Generate isoline bands, lines, diff and catchments"
```

---

### Task 12: 検索用の索引 (町丁目・駅名)

**Files:**
- Create: `src/ekiwalk/places.py`
- Test: `tests/test_places.py`

`places.json` の形: `[["練馬区大泉学園町六丁目", "ねりまくおおいずみがくえんちょう6ちょうめ", 139.5801, 35.7712, "t"], ["光が丘駅", "ひかりがおか", 139.6286, 35.7581, "s"], ...]`。最後の列は種類 (`t` 町丁目、`s` 駅)。大きさを抑えるため配列にする。

ABR の列名は 2024 年以降の CSV で英語になっている (`lg_code, machiaza_id, city, ward, oaza_cho, chome, ... rep_lon, rep_lat`)。取得後に 1 行目を見て、`COLS` を直す。

- [ ] **Step 1: 失敗するテストを書く**

```python
from ekiwalk.places import town_rows, station_rows


def test_town_rows_joins_names_and_points():
    towns = [{"lg_code": "131202", "machiaza_id": "0012006", "city": "練馬区", "ward": "", "oaza_cho": "大泉学園町",
              "chome": "六丁目", "city_kana": "ねりまく", "oaza_cho_kana": "おおいずみがくえんちょう", "chome_kana": "6ちょうめ"}]
    pos = [{"lg_code": "131202", "machiaza_id": "0012006", "rep_lon": "139.58012345", "rep_lat": "35.77123456"}]
    rows = town_rows(towns, pos)
    assert rows == [["練馬区大泉学園町六丁目", "ねりまくおおいずみがくえんちょう6ちょうめ", 139.58012, 35.77123, "t"]]


def test_station_rows_dedupes_groups():
    st = [{"group": "G1", "name": "光が丘", "lon": 139.62861, "lat": 35.75811, "planned": False},
          {"group": "G1", "name": "光が丘", "lon": 139.62862, "lat": 35.75812, "planned": False},
          {"group": "plan:大泉学園町（仮称）", "name": "大泉学園町（仮称）", "lon": 139.58, "lat": 35.77, "planned": True}]
    rows = station_rows(st)
    assert rows == [["光が丘駅", "", 139.62861, 35.75811, "s"]]
```

予定駅は検索に入れない (現在の駅だけ)。駅のよみは N02 に無いので空にする。

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_places.py -q`
Expected: FAIL

- [ ] **Step 3: places.py を書く**

```python
"""Search index: town/chome representative points (ABR) and station names (N02)."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pyarrow.parquet as pq

COLS = {
    "key": ("lg_code", "machiaza_id"),
    "name": ("city", "ward", "oaza_cho", "chome"),
    "kana": ("city_kana", "ward_kana", "oaza_cho_kana", "chome_kana"),
    "lon": "rep_lon",
    "lat": "rep_lat",
}


def town_rows(towns: list[dict], pos: list[dict]) -> list[list]:
    pts = {(p[COLS["key"][0]], p[COLS["key"][1]]): p for p in pos if p.get(COLS["lon"])}
    rows = []
    for t in towns:
        p = pts.get((t[COLS["key"][0]], t[COLS["key"][1]]))
        if not p:
            continue
        name = "".join(t.get(k) or "" for k in COLS["name"])
        kana = "".join(t.get(k) or "" for k in COLS["kana"])
        rows.append([name, kana, round(float(p[COLS["lon"]]), 5), round(float(p[COLS["lat"]]), 5), "t"])
    return rows


def station_rows(stations: list[dict]) -> list[list]:
    seen, rows = set(), []
    for s in stations:
        if s["planned"] or s["group"] in seen:
            continue
        seen.add(s["group"])
        rows.append([f"{s['name']}駅", "", round(s["lon"], 5), round(s["lat"], 5), "s"])
    return rows


def read_csv_any(path: Path) -> list[dict]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            text = z.read(name).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def run(region, town_csv: Path, pos_csv: Path) -> Path:
    st = pq.read_table(region.build_dir / "stations-base.parquet").to_pylist()
    rows = town_rows(read_csv_any(town_csv), read_csv_any(pos_csv)) + station_rows(st)
    if len(rows) < 100:
        raise RuntimeError(f"検索の索引が {len(rows)} 件しかありません。ABR の列名 (COLS) を確かめてください")
    region.web_dir.mkdir(parents=True, exist_ok=True)
    out = region.web_dir / "places.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run pytest tests/test_places.py -q`
Expected: `2 passed`

- [ ] **Step 5: コミットする**

```bash
git add src/ekiwalk/places.py tests/test_places.py
git commit -m "Build client-side search index from ABR and N02"
```

---

### Task 13: CLI と書き出し (stations / boundaries / meta)

**Files:**
- Create: `src/ekiwalk/cli.py`, `src/ekiwalk/export.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: 失敗するテストを書く**

```python
from ekiwalk.cli import build_parser


def test_parser_build():
    a = build_parser().parse_args(["build", "--region", "tokyo", "--scenario", "base", "--scenario", "oedo-ext"])
    assert a.command == "build" and a.region == "tokyo" and a.scenario == ["base", "oedo-ext"]


def test_parser_fetch():
    a = build_parser().parse_args(["fetch", "n02"])
    assert a.command == "fetch" and a.keys == ["n02"]
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL

- [ ] **Step 3: export.py を書く**

```python
"""Write stations.geojson, boundaries.geojson, meta.json for the web app."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pyarrow.parquet as pq
import shapely
from shapely.geometry import Point, mapping

from .config import Region, Scenario
from .contours import write_fc


def run(region: Region, scenarios: list[Scenario], boundaries: list[dict], root) -> None:
    w = region.web_dir
    w.mkdir(parents=True, exist_ok=True)
    last = scenarios[-1]
    st = pq.read_table(region.build_dir / f"stations-{last.name}.parquet").to_pylist()
    seen, feats = set(), []
    for s in st:
        if s["group"] in seen:
            continue
        seen.add(s["group"])
        feats.append(({"name": s["name"], "planned": s["planned"]}, Point(s["lon"], s["lat"])))
    write_fc(w / "stations.geojson", feats)
    write_fc(w / "boundaries.geojson", [({"name": b["name"]}, b["geom"].boundary) for b in boundaries])
    manifest_path = root / "data" / "raw" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    meta = {
        "region": region.name,
        "label": region.label,
        "home_view": region.home_view,
        "walk_m_per_min": region.walk_m_per_min,
        "levels_min": region.levels_min,
        "scenarios": [{"name": s.name, "label": s.label, "note": s.note,
                       "planned": [{"name": p.name, "lon": p.lon, "lat": p.lat, "basis": p.basis} for p in s.stations]}
                      for s in scenarios],
        "sources": {k: {"file": v["file"], "retrieved_utc": v["retrieved_utc"], "sha256": v["sha256"]} for k, v in manifest.items()},
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (w / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
```

- [ ] **Step 4: cli.py を書く**

```python
"""Command line: uv run ekiwalk <fetch|build> ..."""

from __future__ import annotations

import argparse
import logging
import time

from . import admin, contours, export, network, places, shortest, stations, surface, water
from .config import ROOT, load_region, load_scenario
from .fetch import download, load_sources, raw_path

log = logging.getLogger("ekiwalk")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="ekiwalk")
    sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="確認後に生データを data/raw/ へ取得する")
    f.add_argument("keys", nargs="*")
    f.add_argument("--all", action="store_true")
    b = sub.add_parser("build", help="データを作って web/data/<region>/ に書き出す")
    b.add_argument("--region", required=True)
    b.add_argument("--scenario", action="append", default=None)
    b.add_argument("--from", dest="start", default="network",
                   choices=["network", "water", "admin", "stations", "solve", "surface", "contours", "places", "export"])
    return ap


STEPS = ["network", "water", "admin", "stations", "solve", "surface", "contours", "places", "export"]


def cmd_fetch(args) -> None:
    srcs = load_sources(ROOT)
    keys = list(srcs) if args.all else args.keys
    for k in keys:
        print(f"  {k}: {srcs[k]['file']}  {srcs[k]['url']}  ({srcs[k]['size_hint']}, {srcs[k]['license']})")
    if input("これらを取得しますか? [y/N] ").strip().lower() != "y":
        print("取得しませんでした")
        return
    for k in keys:
        print(k, download(ROOT, k, srcs[k]))


def cmd_build(args) -> None:
    region = load_region(args.region)
    names = args.scenario or ["base"]
    if names[0] != "base":
        names = ["base"] + names
    scenarios = [load_scenario(n) for n in names]
    todo = STEPS[STEPS.index(args.start):]

    def step(name, fn):
        if name in todo:
            t = time.time()
            r = fn()
            log.info("%s done in %.1fs", name, time.time() - t)
            return r
        return None

    pbf = raw_path(ROOT, region.osm_source)
    step("network", lambda: network.run(region, pbf))
    step("water", lambda: water.run(region, pbf))
    adm = admin.run(region, [raw_path(ROOT, f"n03-{c}") for c in region.n03_prefectures])
    for s in scenarios:
        step("stations", lambda s=s: stations.run(region, s, raw_path(ROOT, "n02")))
        step("solve", lambda s=s: shortest.run(region, s))
        step("surface", lambda s=s: surface.run(region, s))
        step("contours", lambda s=s: contours.run(region, s, compare_to=None if s.name == "base" else "base"))
    step("places", lambda: places.run(region, raw_path(ROOT, "abr-town-13"), raw_path(ROOT, "abr-town-pos-13")))
    step("export", lambda: export.run(region, scenarios, adm["boundaries"], ROOT))


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    {"fetch": cmd_fetch, "build": cmd_build}[args.command](args)
```

`admin.run` は区市町村界を返すので毎回実行する (数秒)。

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run pytest -q`
Expected: すべて pass

- [ ] **Step 6: 試運転の範囲で全段階を通す**

```bash
uv run ekiwalk build --region oizumi-test --scenario base
```

Expected: `web/data/oizumi-test/` に `bands-base.geojson`、`lines-base.geojson`、`catchments-base.geojson`、`stations.geojson`、`boundaries.geojson`、`places.json`、`meta.json` ができる。各段階の時間がログに出る。

数値で確かめる:

```bash
uv run python -c "import pyarrow.parquet as pq, numpy as np; s=pq.read_table('data/build/oizumi-test/solve-base.parquet'); d=s['dist_m'].to_numpy(); print('max', d.max().round(), 'p50', np.median(d).round())"
```

`data/build/oizumi-test/` の格子で、光が丘駅の代表点のマスが 0〜200 m、大泉学園町六丁目付近が 1,600 m (20 分) 以上になっているかを確かめる (`Grid.load` と `Projector.to_xy` で行・列を求める)。

- [ ] **Step 7: コミットする (試運転の生成物は入れない)**

`web/data/oizumi-test/` はコミットしない。`.gitignore` に `/web/data/oizumi-test/` を足す。

```bash
git add src/ekiwalk/cli.py src/ekiwalk/export.py tests/test_cli.py .gitignore
git commit -m "Add CLI and web export; ignore test-region output"
```

---

### Task 14: 大江戸線延伸の予定駅を推定する

**Files:**
- Modify: `configs/scenarios/oedo-ext.toml`
- Modify: `docs/sources/oedo-extension.md`

- [ ] **Step 1: 資料の PDF を取得する許可を取る**

東京都の資料 PDF の大きさを HEAD で確かめ、ファイル名・取得元・大きさを示して利用者の確認を取る。PDF は `data/raw/` に置き、コミットしない。

```bash
curl -sI https://www.toshiseibi.metro.tokyo.lg.jp/documents/d/toshiseibi/2025-10-15-111344-482 | grep -i -E "content-length|content-type"
```

- [ ] **Step 2: 概略図と説明から位置を推定する**

資料の説明は「土支田通りの東側」「外環道との交差部西側」「大泉学園通りとの交差部東側」。延伸ルートは都市計画道路 補助 230 号線に沿う。次の手順で推定する。

1. OSM (`kanto-261001.osm.pbf`) から、補助 230 号線に当たる道路と、土支田通り・外環道 (東京外かく環状道路)・大泉学園通りの交点を DuckDB で求める。名前のタグは `name`、`ref`、`official_name` を見る。
2. 説明の東西の向きに合わせて、各交点から道路に沿って約 100 m ずらした点を予定駅とする。
3. 概略図 (PDF) と重ねて見比べ、明らかなずれが無いかを確かめる。

推定した座標と方法を toml に書く。駅名と位置の対応は北東から順に土支田・大泉町・大泉学園町と推定した旨も書く。

```toml
name = "oedo-ext"
label = "大江戸線延伸後"
note = "東京都の検討資料 (2025-10-15) の説明と概略図から筆者が位置を推定した。座標は公表されていない。開業は2040年頃の想定 (未確定)。"

[[stations]]
name = "土支田（仮称）"
lon = 0.0   # Step 2 の結果で置き換える
lat = 0.0
basis = "資料の説明「土支田通りの東側」。補助230号線と土支田通りの交点から東へ約100mと推定"
```

(3 駅分を同じ形で書く。`lon`/`lat` は Step 2 で求めた値。0.0 のままコミットしない。)

- [ ] **Step 3: 延伸後を作って確かめる**

```bash
uv run ekiwalk build --region oizumi-test --scenario oedo-ext --from stations
```

Expected: `diff-oedo-ext.geojson` ができ、大泉学園町付近に「5 分以上近くなった所」がある。

- [ ] **Step 4: 記録とコミット**

`docs/sources/oedo-extension.md` に推定方法と座標を書く。

```bash
git add configs/scenarios/oedo-ext.toml docs/sources/oedo-extension.md
git commit -m "Add estimated planned stations for Oedo Line extension"
```

---

### Task 15: Web の純粋関数 (地点判定と検索)

**Files:**
- Create: `web/js/lookup.js`, `web/js/search.js`, `web/test/lookup.test.js`, `web/test/search.test.js`, `web/package.json`

`web/package.json` は `{"type": "module", "private": true}` だけにする (Node で ES モジュールとして読むため)。

- [ ] **Step 1: 失敗するテストを書く**

`web/test/lookup.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { pointInFeature, findFeature } from "../js/lookup.js";

const square = (x0, y0, x1, y1, props) => ({
  type: "Feature", properties: props,
  geometry: { type: "Polygon", coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] },
});

test("point in polygon with hole", () => {
  const f = { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
    [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
  ] } };
  assert.equal(pointInFeature([1, 1], f), true);
  assert.equal(pointInFeature([5, 5], f), false);
});

test("findFeature returns first containing feature", () => {
  const fc = { type: "FeatureCollection", features: [square(0, 0, 1, 1, { lo: 0, hi: 5 }), square(1, 0, 2, 1, { lo: 5, hi: 10 })] };
  assert.deepEqual(findFeature(fc, [1.5, 0.5]).properties, { lo: 5, hi: 10 });
  assert.equal(findFeature(fc, [5, 5]), null);
});
```

`web/test/search.test.js`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { normalize, search } from "../js/search.js";

test("normalize converts digits to kanji numerals and strips spaces", () => {
  assert.equal(normalize("大泉学園町6丁目"), "大泉学園町六丁目");
  assert.equal(normalize("大泉学園町６丁目"), "大泉学園町六丁目");
  assert.equal(normalize(" 光が丘 "), "光が丘");
  assert.equal(normalize("12丁目"), "十二丁目");
});

const PLACES = [
  ["練馬区大泉学園町六丁目", "", 139.58, 35.77, "t"],
  ["練馬区大泉学園町七丁目", "", 139.57, 35.78, "t"],
  ["光が丘駅", "", 139.63, 35.76, "s"],
];

test("search matches substrings, stations first on tie", () => {
  assert.deepEqual(search(PLACES, "大泉学園町6").map((r) => r[0]), ["練馬区大泉学園町六丁目"]);
  assert.deepEqual(search(PLACES, "光が丘").map((r) => r[0]), ["光が丘駅"]);
  assert.deepEqual(search(PLACES, ""), []);
});
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `node --test web/test/`
Expected: FAIL (`Cannot find module`)

- [ ] **Step 3: lookup.js と search.js を書く**

`web/js/lookup.js`:

```js
// Which polygon feature contains a [lon, lat] point (ray casting, bbox prefilter).

function ringContains(ring, [x, y]) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygonContains(rings, pt) {
  if (!ringContains(rings[0], pt)) return false;
  for (let k = 1; k < rings.length; k++) if (ringContains(rings[k], pt)) return false;
  return true;
}

function bbox(geom) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  for (const p of polys) for (const [x, y] of p[0]) {
    if (x < minX) minX = x; if (y < minY) minY = y; if (x > maxX) maxX = x; if (y > maxY) maxY = y;
  }
  return [minX, minY, maxX, maxY];
}

export function pointInFeature(pt, feature) {
  const g = feature.geometry;
  if (!g) return false;
  if (!feature._bbox) feature._bbox = bbox(g);
  const [a, b, c, d] = feature._bbox;
  if (pt[0] < a || pt[0] > c || pt[1] < b || pt[1] > d) return false;
  if (g.type === "Polygon") return polygonContains(g.coordinates, pt);
  if (g.type === "MultiPolygon") return g.coordinates.some((rings) => polygonContains(rings, pt));
  return false;
}

export function findFeature(fc, pt) {
  return fc.features.find((f) => pointInFeature(pt, f)) ?? null;
}
```

`web/js/search.js`:

```js
// Client-side search over places.json rows: [name, kana, lon, lat, kind].

const KANJI = ["〇", "一", "二", "三", "四", "五", "六", "七", "八", "九"];

function toKanji(n) {
  if (n < 10) return KANJI[n];
  if (n < 20) return "十" + (n % 10 ? KANJI[n % 10] : "");
  if (n < 100) return KANJI[Math.floor(n / 10)] + "十" + (n % 10 ? KANJI[n % 10] : "");
  return String(n);
}

export function normalize(s) {
  return s
    .normalize("NFKC")
    .replace(/\s+/g, "")
    .replace(/(\d+)(?=丁目|$)/g, (m) => toKanji(Number(m)));
}

export function search(places, query, limit = 10) {
  const q = normalize(query);
  if (!q) return [];
  const hits = [];
  for (const row of places) {
    const name = row[0];
    const i = name.indexOf(q);
    const j = i < 0 && row[1] ? row[1].indexOf(query.trim()) : -1;
    if (i >= 0 || j >= 0) hits.push({ row, score: (i >= 0 ? i : 50) + (row[4] === "s" ? 0 : 1) + name.length / 100 });
  }
  hits.sort((a, b) => a.score - b.score);
  return hits.slice(0, limit).map((h) => h.row);
}
```

注: 「大泉学園町6」は末尾の 6 が `$` に当たるので「六」になり、「大泉学園町六」で前方一致する。

- [ ] **Step 4: テストが通ることを確かめる**

Run: `node --test web/test/`
Expected: すべて pass

- [ ] **Step 5: コミットする**

```bash
git add web/package.json web/js/lookup.js web/js/search.js web/test
git commit -m "Add client-side point lookup and place search"
```

---

### Task 16: 画面 (HTML / CSS / main.js)

**Files:**
- Create: `web/index.html`, `web/style.css`, `web/js/main.js`

- [ ] **Step 1: index.html を書く**

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>鉄道空白地帯マップ</title>
  <meta name="description" content="最寄り駅まで歩いて何分かを等距離線で描いた地図。東京。">
  <link rel="stylesheet" href="https://unpkg.com/maplibre-gl@6.11.2/dist/maplibre-gl.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="map" aria-label="地図"></div>

  <section class="panel panel-top-left">
    <h1>鉄道空白地帯マップ</h1>
    <p class="lead">最寄り駅まで歩いて何分か (80 m/分) を線で描きました。色が濃い所ほど駅から遠い所です。</p>
    <form id="search-form" role="search" autocomplete="off">
      <input id="search" type="search" placeholder="町丁目・駅名 (例: 大泉学園町6丁目)" aria-label="町丁目・駅名で探す">
      <ul id="search-results" role="listbox"></ul>
    </form>
    <div class="buttons">
      <button id="locate" type="button">現在地</button>
      <button id="go-oizumi" type="button">大泉学園町へ</button>
    </div>
    <p class="privacy">検索と現在地はブラウザの中だけで使い、どこにも送りません。</p>
  </section>

  <section class="panel panel-top-right">
    <div class="toggle" role="group" aria-label="比較">
      <button type="button" data-scenario="base" aria-pressed="true">延伸前</button>
      <button type="button" data-scenario="oedo-ext" aria-pressed="false">延伸後</button>
    </div>
    <div id="legend"></div>
  </section>

  <section id="info" class="panel panel-info" hidden aria-live="polite"></section>

  <details class="panel panel-bottom">
    <summary>この地図の限界と出典</summary>
    <div id="notes"></div>
  </details>

  <div id="error" class="error" hidden></div>

  <script src="https://unpkg.com/maplibre-gl@6.11.2/dist/maplibre-gl.js"></script>
  <script type="module" src="js/main.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css を書く**

```css
:root {
  --bg: #ffffff;
  --fg: #1d2330;
  --muted: #5b6475;
  --panel: rgba(255, 255, 255, 0.94);
  --border: #d6dbe4;
  --accent: #2456c9;
  --band-0: #fff7ec; --band-1: #fee8c8; --band-2: #fdd49e; --band-3: #fdbb84;
  --band-4: #fc8d59; --band-5: #ef6548; --band-6: #d7301f; --band-7: #b30000; --band-8: #7f0000;
  --line: #4a3a2a;
  --diff: #1a7f5a;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #12151b; --fg: #e8ebf1; --muted: #a3abba; --panel: rgba(24, 28, 36, 0.94); --border: #343b48; --accent: #7ea3ff;
  }
}
:root[data-theme="dark"] {
  --bg: #12151b; --fg: #e8ebf1; --muted: #a3abba; --panel: rgba(24, 28, 36, 0.94); --border: #343b48; --accent: #7ea3ff;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: var(--bg); color: var(--fg);
  font: 14px/1.5 system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif; }
#map { position: fixed; inset: 0; }
.panel { position: absolute; background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; box-shadow: 0 2px 8px rgba(0,0,0,.12); max-width: calc(100vw - 32px); }
.panel-top-left { top: 16px; left: 16px; width: 340px; }
.panel-top-right { top: 16px; right: 16px; }
.panel-info { left: 16px; bottom: 64px; width: 340px; }
.panel-bottom { left: 16px; bottom: 16px; width: 340px; max-height: 50vh; overflow: auto; }
h1 { font-size: 17px; margin: 0 0 4px; }
.lead, .privacy { margin: 0 0 8px; color: var(--muted); }
.privacy { font-size: 12px; margin: 6px 0 0; }
#search { width: 100%; padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--fg); font-size: 15px; }
#search-results { list-style: none; margin: 4px 0 0; padding: 0; max-height: 220px; overflow: auto; }
#search-results li { padding: 6px 8px; cursor: pointer; border-radius: 4px; }
#search-results li[aria-selected="true"], #search-results li:hover { background: color-mix(in srgb, var(--accent) 14%, transparent); }
.buttons { display: flex; gap: 6px; margin-top: 8px; }
button { font: inherit; padding: 5px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--fg); cursor: pointer; }
.toggle button[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: #fff; }
#legend { margin-top: 8px; font-size: 12px; }
#legend .row { display: flex; align-items: center; gap: 6px; }
#legend .sw { width: 18px; height: 12px; border: 1px solid var(--border); }
.error { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: #b00020; color: #fff; padding: 10px 14px; border-radius: 6px; }
@media (max-width: 640px) {
  .panel-top-left, .panel-info, .panel-bottom { left: 16px; right: 16px; width: auto; }
  .panel-top-right { top: auto; bottom: 120px; right: 16px; }
  .lead { display: none; }
}
```

- [ ] **Step 3: main.js を書く**

```js
import { findFeature } from "./lookup.js";
import { search } from "./search.js";

const REGION = "tokyo";
const BASE = `data/${REGION}`;
const OIZUMI = { center: [139.585, 35.765], zoom: 13.2 };
const BAND_VARS = ["--band-0", "--band-1", "--band-2", "--band-3", "--band-4", "--band-5", "--band-6", "--band-7", "--band-8"];

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const data = {};
let scenario = "base";
let marker = null;

async function getJSON(path) {
  const r = await fetch(`${BASE}/${path}`);
  if (!r.ok) throw new Error(`${path} を読めませんでした (${r.status})`);
  return r.json();
}

function showError(msg) {
  const el = document.getElementById("error");
  el.textContent = msg;
  el.hidden = false;
}

function bandLabel(p) {
  return p.hi == null ? `${p.lo}分以上` : `${p.lo}〜${p.hi}分`;
}

function bandColorExpr(levels) {
  const expr = ["step", ["get", "lo"], css(BAND_VARS[0])];
  levels.forEach((lv, i) => expr.push(lv, css(BAND_VARS[Math.min(i + 1, BAND_VARS.length - 1)])));
  return expr;
}

function buildLegend(meta) {
  const el = document.getElementById("legend");
  const lv = [0, ...meta.levels_min];
  el.innerHTML = lv.map((lo, i) => {
    const hi = meta.levels_min[i];
    const label = hi == null ? `${lo}分以上` : `${lo}〜${hi}分`;
    return `<div class="row"><span class="sw" style="background:${css(BAND_VARS[Math.min(i, BAND_VARS.length - 1)])}"></span>${label}</div>`;
  }).join("") + `<div class="row diff-row" hidden><span class="sw" style="border:2.5px solid ${css("--diff")}"></span>延伸で5分以上近くなった所 (緑の線の内側)</div>`;
}

function buildNotes(meta) {
  const planned = meta.scenarios.find((s) => s.name === "oedo-ext");
  document.getElementById("notes").innerHTML = `
    <h2>この地図の限界</h2>
    <ul>
      <li>駅の位置はホームの中心線 (国土数値情報の駅区間) で、出口ではありません。</li>
      <li>道のりは 80 m/分で一定と仮定しました。信号・坂・階段・混雑は入れていません。</li>
      <li>バスは考えていません。</li>
      <li>OpenStreetMap に載っていない道は通れない扱いです。私道や建物の中の通路はデータ次第です。</li>
      <li>道から離れた所は、近くの道まで直線で歩くと仮定しました。道から 300 m 以上離れた所と水面は塗っていません。</li>
      <li>延伸後の予定駅 (仮称) は、${planned ? planned.note : ""}</li>
    </ul>
    <h2>出典</h2>
    <ul>
      <li>道路・水域: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)</li>
      <li>駅: 「国土数値情報（鉄道データ）」（国土交通省）をもとに作成</li>
      <li>行政区域: 「国土数値情報（行政区域データ）」（国土交通省）をもとに作成</li>
      <li>町丁目の位置: アドレス・ベース・レジストリ (デジタル庁) をもとに作成</li>
      <li>背景地図: <a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a> (表示範囲のタイルは国土地理院のサーバーから読み込みます)</li>
      <li>大江戸線延伸: <a href="https://www.toshiseibi.metro.tokyo.lg.jp/documents/d/toshiseibi/2025-10-15-111344-482">東京都 都市整備局 (2025-10-15)</a>、<a href="https://www.city.nerima.tokyo.jp/kusei/machi/kunai_tetsudo/ooedoenshin.html">練馬区</a></li>
    </ul>
    <p>データ作成: ${meta.built_utc} / <a href="https://github.com/isshiki/rail-gap-map">ソースコード</a></p>`;
}

function setScenario(map, name) {
  scenario = name;
  for (const b of document.querySelectorAll(".toggle button")) b.setAttribute("aria-pressed", String(b.dataset.scenario === name));
  map.getSource("bands").setData(data[`bands-${name}`]);
  map.getSource("lines").setData(data[`lines-${name}`]);
  const after = name !== "base";
  map.setLayoutProperty("diff", "visibility", after ? "visible" : "none");
  map.setLayoutProperty("planned", "visibility", after ? "visible" : "none");
  map.setLayoutProperty("planned-label", "visibility", after ? "visible" : "none");
  document.querySelector(".diff-row").hidden = !after;
  if (marker) showInfo(marker.getLngLat().toArray());
}

function showInfo(pt, title) {
  const el = document.getElementById("info");
  const now = findFeature(data[`bands-${scenario}`], pt);
  const st = findFeature(data[`catchments-${scenario}`], pt);
  let text = now ? `徒歩 ${bandLabel(now.properties)} の帯` : "この地点は計算していません (水面・道から遠い所・範囲外)";
  if (scenario !== "base") {
    const before = findFeature(data["bands-base"], pt);
    if (before && now) text = `延伸前 ${bandLabel(before.properties)} → 延伸後 ${bandLabel(now.properties)}`;
  }
  const stName = st ? `${st.properties.name}${st.properties.planned ? "（予定駅・概略位置）" : "駅"}` : "—";
  el.innerHTML = `${title ? `<strong>${title}</strong><br>` : ""}最寄り駅: ${stName}<br>${text}`;
  el.hidden = false;
}

function placeMarker(map, lngLat, title) {
  if (!marker) marker = new maplibregl.Marker({ color: css("--accent") });
  marker.setLngLat(lngLat).addTo(map);
  showInfo(lngLat, title);
}

function setupSearch(map) {
  const input = document.getElementById("search");
  const list = document.getElementById("search-results");
  let rows = [];
  const render = () => {
    rows = search(data.places, input.value);
    list.innerHTML = rows.map((r, i) => `<li role="option" data-i="${i}">${r[0]}</li>`).join("");
  };
  const choose = (r) => {
    list.innerHTML = "";
    input.value = r[0];
    map.flyTo({ center: [r[2], r[3]], zoom: 15 });
    placeMarker(map, [r[2], r[3]], r[0]);
  };
  input.addEventListener("input", render);
  list.addEventListener("click", (e) => { const li = e.target.closest("li"); if (li) choose(rows[Number(li.dataset.i)]); });
  document.getElementById("search-form").addEventListener("submit", (e) => { e.preventDefault(); if (rows[0]) choose(rows[0]); });
}

function setupLocate(map) {
  document.getElementById("locate").addEventListener("click", () => {
    if (!navigator.geolocation) return showInfoText("このブラウザでは現在地を使えません。検索で探してください。");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const ll = [pos.coords.longitude, pos.coords.latitude];
        map.flyTo({ center: ll, zoom: 15 });
        placeMarker(map, ll, "現在地");
      },
      () => showInfoText("現在地を取得できませんでした。検索で探してください。"),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  });
}

function showInfoText(msg) {
  const el = document.getElementById("info");
  el.textContent = msg;
  el.hidden = false;
}

async function main() {
  const meta = await getJSON("meta.json");
  const names = meta.scenarios.map((s) => s.name);
  const files = ["stations.geojson", "boundaries.geojson", "places.json",
    ...names.flatMap((n) => [`bands-${n}.geojson`, `lines-${n}.geojson`, `catchments-${n}.geojson`]),
    ...names.filter((n) => n !== "base").map((n) => `diff-${n}.geojson`)];
  const loaded = await Promise.all(files.map(getJSON));
  files.forEach((f, i) => { data[f.replace(/\.(geo)?json$/, "")] = loaded[i]; });

  const map = new maplibregl.Map({
    container: "map",
    hash: false,
    center: meta.home_view.center,
    zoom: meta.home_view.zoom,
    minZoom: 8,
    maxZoom: 17,
    style: {
      version: 8,
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
      sources: {
        gsi: { type: "raster", tiles: ["https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"], tileSize: 256, maxzoom: 18,
          attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a>' },
      },
      layers: [{ id: "gsi", type: "raster", source: "gsi" }],
    },
    attributionControl: { compact: true, customAttribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> / 国土数値情報 / アドレス・ベース・レジストリ' },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

  map.on("load", () => {
    map.addSource("bands", { type: "geojson", data: data["bands-base"] });
    map.addSource("lines", { type: "geojson", data: data["lines-base"] });
    map.addSource("boundaries", { type: "geojson", data: data.boundaries });
    map.addSource("stations", { type: "geojson", data: data.stations });
    const diffName = names.find((n) => n !== "base");
    if (diffName) map.addSource("diff", { type: "geojson", data: data[`diff-${diffName}`] });

    map.addLayer({ id: "bands", type: "fill", source: "bands", paint: { "fill-color": bandColorExpr(meta.levels_min), "fill-opacity": 0.45 } });
    map.addLayer({ id: "boundaries", type: "line", source: "boundaries", paint: { "line-color": css("--muted"), "line-width": 0.8, "line-dasharray": [3, 2] } });
    map.addLayer({ id: "lines", type: "line", source: "lines", paint: { "line-color": css("--line"), "line-width": ["interpolate", ["linear"], ["zoom"], 9, 0.4, 14, 1.2] } });
    map.addLayer({ id: "line-labels", type: "symbol", source: "lines", minzoom: 12,
      layout: { "symbol-placement": "line", "text-field": ["concat", ["to-string", ["get", "min"]], "分"], "text-size": 11, "text-font": ["Open Sans Regular"] },
      paint: { "text-color": css("--line"), "text-halo-color": "#fff", "text-halo-width": 1.2 } });
    if (diffName) {
      map.addLayer({ id: "diff", type: "line", source: "diff", layout: { visibility: "none" }, paint: { "line-color": css("--diff"), "line-width": 2.5 } });
    }
    map.addLayer({ id: "stations", type: "circle", source: "stations", filter: ["!", ["get", "planned"]],
      paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 14, 4], "circle-color": "#222", "circle-stroke-color": "#fff", "circle-stroke-width": 1 } });
    map.addLayer({ id: "station-labels", type: "symbol", source: "stations", minzoom: 13, filter: ["!", ["get", "planned"]],
      layout: { "text-field": ["get", "name"], "text-size": 12, "text-offset": [0, 1.1], "text-anchor": "top", "text-font": ["Open Sans Regular"] },
      paint: { "text-color": "#222", "text-halo-color": "#fff", "text-halo-width": 1.4 } });
    map.addLayer({ id: "planned", type: "circle", source: "stations", filter: ["get", "planned"], layout: { visibility: "none" },
      paint: { "circle-radius": 9, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": css("--diff"), "circle-stroke-width": 2 } });
    map.addLayer({ id: "planned-label", type: "symbol", source: "stations", filter: ["get", "planned"], layout: { visibility: "none",
      "text-field": ["concat", ["get", "name"], "\n概略位置"], "text-size": 11, "text-offset": [0, 1.6], "text-font": ["Open Sans Regular"] },
      paint: { "text-color": css("--diff"), "text-halo-color": "#fff", "text-halo-width": 1.2 } });

    map.on("click", (e) => placeMarker(map, e.lngLat.toArray()));
  });

  buildLegend(meta);
  buildNotes(meta);
  setupSearch(map);
  setupLocate(map);
  document.getElementById("go-oizumi").addEventListener("click", () => map.flyTo(OIZUMI));
  for (const b of document.querySelectorAll(".toggle button")) b.addEventListener("click", () => setScenario(map, b.dataset.scenario));
}

main().catch((e) => showError(e.message));
```

注:
- 日本語の文字 (「分」・駅名) は、MapLibre の `localIdeographFontFamily` (既定は `sans-serif`) により端末のフォントで描かれる。グリフの PBF は英数字だけに使う。Step 4 で日本語ラベルが出ることを確かめる。
- 差分の強調は緑の太線 (範囲の輪郭) で出す。斜線の塗りは `fill-pattern` 用の画像が要るので、見た目を確かめてから決める。凡例も線の見本にしてある。

- [ ] **Step 4: ブラウザで確かめる (試運転の範囲で)**

共通の起動スクリプトで静的サーバーを起動し、任意のブラウザで開く。試運転のデータがある場合は `http://127.0.0.1:8000/?region=oizumi-test` を使う。`main.js` の変更は不要。

```powershell
powershell -NoProfile -File scripts/serve.ps1
```

確かめること:
- 帯・線・駅・区市町村界が出る
- クリックで「最寄り駅・帯」が出る
- 検索「大泉学園町6」で候補が出て、移動して印が付く
- 現在地ボタンで、拒否したときに案内が出る
- 延伸前 / 延伸後の切り替えで帯と差分が変わる
- 375 px 幅で横スクロールが無い
- コンソールにエラーが無い

現在の公開地域については、東京・大阪をパソコン幅と 375 px 幅の両方で確かめる。

- [ ] **Step 5: コミットする**

```bash
git add web/index.html web/style.css web/js/main.js scripts/serve.ps1
git commit -m "Add static map page with search, locate and scenario toggle"
```

---

### Task 17: 東京全体で作り、確かめる

**Files:**
- Create: `web/data/tokyo/*` (生成物)、`docs/limitations.md`
- Modify: `docs/sources/*.md` (取得記録)、`README.md`

- [ ] **Step 1: 東京全体で作る**

```bash
uv run ekiwalk build --region tokyo --scenario base --scenario oedo-ext
```

各段階の時間と、節点数・辺数・捨てた節点数をログから記録する。メモリ不足や長すぎる段階があれば、その段階だけ直す。たとえば `grid_from_points` の `chunk_rows` を減らす、`read_walk_ways` を Task 5 の注の SQL にする。

- [ ] **Step 2: 数値で確かめる**

- 駅の代表点のマスがすべて 0〜250 m である (N02 の線の中点からの直線距離ぶんの誤差を許す)。外れた駅を一覧にして理由を見る。
- 大泉学園町六丁目の代表点が、延伸前 ≥ 20 分、延伸後 ≤ 10 分である。
- 帯の面積の合計が、表示範囲の面積から水面・空白を引いたものとおおむね一致する (±3%)。
- `web/data/tokyo/` の各ファイルの大きさを一覧にする。1 ファイル 10 MB を超えたら、`simplify_m` を 8 → 10 m に上げるか、PMTiles を検討する。

- [ ] **Step 3: ブラウザで確かめる**

Task 16 Step 4 と同じ項目を東京全体で確かめる。加えて、荒川・多摩川を挟んだ所で、橋まで回る分だけ線が曲がっているかを見る。

- [ ] **Step 4: docs/limitations.md を書く**

画面の「この地図の限界」と同じ内容に、次を足す。

- 計算の手順 (多始点ダイクストラ、25 m 格子、ぼかし σ = 25 m、単純化 5 m)
- 段階の値
- 道から 300 m 以上離れた所を空白にしたこと
- 都境の外 3 km の駅を含めたこと

- [ ] **Step 5: 取得記録と README を更新する**

`data/raw/manifest.json` から、各 `docs/sources/*.md` に bytes・sha256・retrieved_utc を転記する。

- [ ] **Step 6: 生成物を確かめてコミットする**

```bash
git status --short --untracked-files=all
uv run python -c "import pathlib; [print(f'{p.stat().st_size/1e6:7.2f} MB  {p}') for p in sorted(pathlib.Path('web/data/tokyo').iterdir())]"
git add web/data/tokyo docs README.md
git diff --cached --stat
git commit -m "Build Tokyo isolines and document limitations"
```

1 MiB を超えるファイルは、`web/data/` の生成物であることと、ライセンスを `docs/data-policy.md` に書いてあることを確かめてから追加する。

---

### Task 18: GitHub Pages と公開

**Files:**
- Create: `.github/workflows/pages.yml`

- [ ] **Step 1: ワークフローを書く**

```yaml
name: Deploy web to GitHub Pages
on:
  push:
    branches: [main]
    paths: ["web/**", ".github/workflows/pages.yml"]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22" }
      - run: node --test web/test/
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with: { path: web }
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: コミットする**

```bash
git add .github/workflows/pages.yml
git commit -m "Deploy web/ to GitHub Pages"
```

- [ ] **Step 3: 利用者の確認を取ってから GitHub に公開する**

チャットで、次の内容を示して確認を取る。

- リポジトリ `isshiki/rail-gap-map` を **public** で作ること
- push する commit の一覧 (`git log --oneline`)
- `web/data/tokyo/` の大きさの合計

確認が取れたら次を実行する。

```bash
gh repo create isshiki/rail-gap-map --public --source . --remote origin --description "鉄道空白地帯マップ: 最寄り駅までの徒歩距離を等距離線で描く (公開データのみ)"
git push -u origin main
gh api -X POST repos/isshiki/rail-gap-map/pages -f build_type=workflow
```

- [ ] **Step 4: 公開ページを確かめる**

Actions の結果を確かめ、`https://isshiki.github.io/rail-gap-map/` をアプリ内ブラウザで開く。Task 16 Step 4 と同じ項目を確かめ、README の「地図」に URL を書いてコミットする (push は再び確認を取る)。
