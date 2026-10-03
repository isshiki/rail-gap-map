# 大阪府の開業予定路線 (シナリオ osaka-plan)

公開されている HTML ページだけを読み、PDF は取得していない。予定駅の座標は公表されていないので、資料にある位置の説明から筆者が推定した。設定は `configs/scenarios/osaka-plan.toml` (確認日 2026-10-04)。

| 路線 | 状況 | 新駅 | 主な資料 |
|---|---|---|---|
| 大阪モノレール本線延伸 (門真市 - 瓜生堂、約 8.9 km) | 事業中。開業目標 2033 年 (瓜生堂付近の軟弱地盤で当初の 2029 年度から延期) | 松生町・門真南・鴻池新田・荒本・瓜生堂 (いずれも仮称)。瓜生堂には近鉄奈良線の新駅も設けて乗り換え | 大阪府 https://www.pref.osaka.lg.jp/o130090/toshikotsu/osakamonorail-enshin/index.html 、大阪府 松生町駅 https://www.pref.osaka.lg.jp/o130090/tetsudosuishin/sinekisettizigyou/index.html 、大阪モノレール https://www.osaka-monorail.co.jp/know/stretching/ 、門真市 https://www.city.kadoma.osaka.jp/soshiki/machizukuri/5/koutuuseisaku/2/2/13950.html 、東大阪市 https://www.city.higashiosaka.lg.jp/0000041414.html |
| なにわ筋線 (大阪(うめきた) - JR難波 / 新今宮、約 7.2 km) | 事業中。開業目標 2031 年春 | 中之島・西本町・南海新難波 (いずれも仮称) | 関西高速鉄道 https://www.kr-railway.co.jp/naniwa/ 、大阪府 https://www.pref.osaka.lg.jp/o130080/toshikotsu/naniwasuzisen/index.html 、大阪市 https://www.city.osaka.lg.jp/toshikeikaku/page/0000481324.html |
| Osaka Metro 中央線 森ノ宮 - 森之宮新駅 (約 1.1 km) | 軌道事業特許取得 (2024-06-28)。開業予定 2028 年春 | 森之宮新駅 (仮称) | Osaka Metro https://subway.osakametro.co.jp/news/news_release/20240628_morinomiya_kidoujigyou_tokkyo.php |

検討・調査の段階のもの (京阪中之島線延伸、JR 桜島線延伸、北港テクノポート線延伸、阪急なにわ筋連絡線・新大阪連絡線、大阪モノレールの瓜生堂以南) は入れていない。

## 位置の推定

- 資料の説明 (どの道路のどちら側か、どの駅と乗り換えか、町丁目) から点を置いた。町丁目の代表点は国土地理院の住所検索、既存駅・施設の位置は Wikipedia の座標を参考にした。
- モノレール延伸となにわ筋線は、手元の OpenStreetMap 関西抽出 (2026-10-01) にある工事中の線 (`railway=construction`、名前「大阪モノレール本線」「なにわ筋線」) の上の、最も近い点に移した。移した距離は 1〜40 m。門真南は地下鉄門真南駅に最も近い線上の点、瓜生堂は工事中の線と近鉄奈良線の交点。
- 森之宮新駅は検車場の北端の大学寄りに置いた。確度は低め。
- 駅ごとの根拠は設定ファイルの `basis` に書いた。

## 結果

新駅 9 か所は、どれも今の駅から道のりで 1.6 km (歩いて 20 分) 以内にある。最も遠いのは森之宮新駅で約 1.0 km。開業後の計算でも、空白地帯の番号や広さはほとんど変わらない (空白に住む人で約 80 人分)。大阪の空白地帯は、計画中の路線でも埋まらない。
