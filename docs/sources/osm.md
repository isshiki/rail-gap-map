# OpenStreetMap 関東抽出 (Geofabrik)

| 項目 | 内容 |
|---|---|
| データセット | OpenStreetMap。Geofabrik による関東地方の抽出 (`.osm.pbf`) |
| 配布 | https://download.geofabrik.de/asia/japan/kanto.html |
| 利用条件 | Open Database License (ODbL) 1.0 — https://www.openstreetmap.org/copyright (確認日 2026-10-03) |
| 出典表記 | © OpenStreetMap contributors (地図の右下と「出典」に掲載) |
| 再配布 | `web/data/` の等値線・帯・差分・最寄り駅範囲は OSM の派生データベースとして ODbL 1.0 で提供する |
| 版 | `kanto-261001.osm.pbf` (2026-10-01 の日付付きファイル。Geofabrik は月次・年次の日付付きファイルを残している) |
| 期待サイズ | 515,684,430 bytes (2026-10-03 の HEAD 応答の ETag から) |
| 取得 | `kanto-261001.osm.pbf` 515,684,430 bytes、SHA-256 `5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83`、取得 2026-10-03T09:29:33Z |
| 使い方 | 計算範囲 (configs/regions/*.toml の bbox) 内の歩ける道 (`highway=*`。自動車専用道路・`foot=no`・立入禁止を除く) と水域ポリゴン |
| 取得 (大阪) | `kansai-261001.osm.pbf` 352,390,316 bytes、SHA-256 `4af8888a116ccce0902f4b2ba3aa6352121a7384d35ff53d3da718df56615fd1`、取得 2026-10-03T14:25:59Z。Geofabrik の関西抽出 (`kansai-261001.osm.pbf`、2026-10-01) |
