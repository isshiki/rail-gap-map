# データポリシー

このリポジトリは個人ブログと連動する公開プロジェクトです。公開されていて取得できるデータだけを使います。会社のコード・データ・文書は一切入れません ([AGENTS.md](../AGENTS.md))。

## Git に入れるもの・入れないもの

- 入れるもの: コード、設定、手順、データ源の記録 (`docs/sources/`)、`web/data/` の生成物
- 入れないもの: ダウンロードした生データ (`data/raw/`)、中間成果物 (`data/build/`)、キャッシュ、認証情報

## web/data/ のライセンス

`web/data/` の GeoJSON / JSON は次のデータから作った派生物です。

| ファイル | 元データ | ライセンス |
|---|---|---|
| `walk-*.geojson` `tiers-*.geojson` `blanks-*.geojson` | OpenStreetMap (道路・水域)、国土数値情報 N02・N03、国勢調査 250 m メッシュ人口 | **ODbL 1.0** (OSM の派生データベース)。出典: © OpenStreetMap contributors、「国土数値情報（鉄道データ・行政区域データ）」（国土交通省）（データページの URL は `docs/sources/`）、「令和2年国勢調査に関する地域メッシュ統計」（総務省統計局）を加工して作成 |
| `summary.json` (空白地帯の一覧) | 上と同じ + アドレス・ベース・レジストリ (名前)、国土数値情報 S12 (乗降客数) | ODbL 1.0 (上と同じ出典 + 「国土数値情報（駅別乗降客数データ）」（国土交通省）) |
| `stations.geojson` | 国土数値情報 N02 | CC BY 4.0 |
| `outline.geojson` `veil.geojson` | 国土数値情報 N03 | CC BY 4.0 |
| `meta.json` | 設定と取得記録 (データそのものは含まない) | Apache 2.0 |
| `places.json` | アドレス・ベース・レジストリ (デジタル庁)、国土数値情報 N02 | CC BY 4.0 |

これらは `web/data/tokyo/` と `web/data/osaka/` の両方に当てはまります。国土数値情報・e-Stat・アドレス・ベース・レジストリはいずれも CC BY 4.0 (または互換の政府標準利用規約) なので、出典を書けば ODbL のデータベースに組み込めます。

国が作成したように見える使い方はしません。データ源ごとの版・取得日・SHA-256 は `docs/sources/` に記録します。地図の画面の「出典」には、国土数値情報の利用規約に従ってデータページの URL を載せています。

`docs/superpowers/screens/` の画面写真には、背景の地理院タイルと上の派生データが写っています。出典は「地理院タイル」(国土地理院) と上の表のとおりです。

## データ源

| データ | 記録 |
|---|---|
| OpenStreetMap 関東・関西抽出 (Geofabrik) | [sources/osm.md](sources/osm.md) |
| 国土数値情報 鉄道データ N02-25 | [sources/n02.md](sources/n02.md) |
| 国土数値情報 行政区域 N03 | [sources/n03.md](sources/n03.md) |
| アドレス・ベース・レジストリ 町字マスター | [sources/abr.md](sources/abr.md) |
| 地理院タイル | [sources/gsi-tiles.md](sources/gsi-tiles.md) |
| 国勢調査 250 m メッシュ人口 (e-Stat) | [sources/estat.md](sources/estat.md) |
| 国土数値情報 駅別乗降客数 S12-25 | [sources/s12.md](sources/s12.md) |
| 大江戸線延伸の資料 (東京都・練馬区) | [sources/oedo-extension.md](sources/oedo-extension.md) |
| 大阪府の開業予定路線 (大阪府・市・事業者) | [sources/osaka-plan.md](sources/osaka-plan.md) |
| 地図の文字 (Noto Sans、SIL OFL 1.1。`web/fonts/`) | [sources/fonts.md](sources/fonts.md) |
