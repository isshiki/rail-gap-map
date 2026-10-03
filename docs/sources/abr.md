# アドレス・ベース・レジストリ 町字マスター (東京都)

| 項目 | 内容 |
|---|---|
| データセット | アドレス・ベース・レジストリ (デジタル庁)。町字マスター、町字マスター位置参照拡張 |
| 配布 | ポータル https://dataset.address-br.digital.go.jp/ 。ファイルは https://data.address-br.digital.go.jp/ に置かれている (データ一覧 feed: https://dataset.address-br.digital.go.jp/api/feed/dcat-us/1.1.json) |
| 利用条件 | CC BY 4.0 (feed のメタデータの `license`。確認日 2026-10-03) |
| 出典表記 | 「アドレス・ベース・レジストリ」（デジタル庁）（https://dataset.address-br.digital.go.jp/）を加工して作成 |
| 再配布 | `web/data/<region>/places.json` (町丁目名・よみ・代表点) を CC BY 4.0 で提供する |
| ファイル | `mt_town_pref13.csv.zip` 83,827 bytes (Last-Modified 2026-10-02) / `mt_town_pos_pref13.csv.zip` 84,132 bytes (Last-Modified 2025-10-27) |
| 取得 | `mt_town_pref13.csv.zip` 83,827 bytes、SHA-256 `58f62944afa4d641880ea255838c8c0be2cf5f363eb97e27e3173e3eecc493b3`、取得 2026-10-03T09:28:24Z<br>`mt_town_pos_pref13.csv.zip` 84,132 bytes、SHA-256 `06c42c5a1beb3f2606c1816893fe7bc8efa7d5edf1a8c7a366e8a04bef87c0a8`、取得 2026-10-03T09:28:24Z |
| 結合の結果 | 町字 5,942 件のうち 5,319 件に代表点が付いた。付かなかった 623 件は主に島しょの小字 (大島町 319 件など) と、丁目を持つ町の親の項目 (例「港区虎ノ門」) |
| 使い方 | 町丁目の名前と代表点 (`rep_lon`, `rep_lat`) を `lg_code` + `machiaza_id` + `rsdt_addr_flg` で結び付け、ブラウザ内の検索に使う |
| 取得 (大阪) | `mt_town_pref27.csv.zip` 144,643 bytes、SHA-256 `b2db60d2cb6c77b895f8218dc4643e63387279e8396a1d09353e2194221daaae`、取得 2026-10-03T14:17:26Z<br>`mt_town_pos_pref27.csv.zip` 126,681 bytes、SHA-256 `793fb8e279db493ed1bff8f5119d14bfcfd01d41efed6f42e95c37e8d69ea3a3`、取得 2026-10-03T14:17:26Z |
