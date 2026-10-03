# rail-gap-map

**This repository uses only publicly obtainable data. No proprietary company data is included.**

東京・大阪の「鉄道空白地帯」の地図です。どの駅からも歩いて 20 分 (1.6 km) を超える所を鉄道空白地帯とし、駅まで 5 km まで (バスで 30 分ほど) の「バス圏」と、それより遠い・道のない「奥地」に分けて示します。空白地帯は区市町村ごとに区切り、面積・住む人の数 (2020 年国勢調査)・住む人の最寄り駅とその乗降客数 (参考) を一覧にします。東京は都営大江戸線の延伸 (光が丘〜大泉学園町)、大阪は大阪モノレール延伸・なにわ筋線・森之宮新駅の開業前後を比べられます。

- 地図: https://isshiki.github.io/rail-gap-map/ (東京) / https://isshiki.github.io/rail-gap-map/?region=osaka (大阪)
- 設計: [空白地帯を主役にする設計 (v2)](docs/superpowers/specs/2026-10-03-gap-first-redesign.md) / [最初の設計 (v1)](docs/superpowers/specs/2026-10-03-rail-gap-map-design.md)
- 考え方・限界・計算方法: [docs/limitations.md](docs/limitations.md)
- データと出典: [docs/data-policy.md](docs/data-policy.md)

## 手元で地図を開く

特定のAIエージェントやエディターの設定は不要です。作業時の決まりは [AGENTS.md](AGENTS.md) にまとめています。`docs/superpowers/` は設計・初期計画の記録で、特定のプラグインの実行は必要ありません。

コミット済みの `web/data/tokyo/` と `web/data/osaka/` があるので、地図を見るだけなら生データの取得や再ビルドは不要です。Python 3.11 以上だけでも起動できます。

```powershell
python -m http.server --bind 127.0.0.1 --directory web 8000
```

uv の環境を準備済みの場合は、次の共通スクリプトでも起動できます。依存の自動ダウンロードを避けるため、オフラインで実行します。

```powershell
powershell -NoProfile -File scripts/serve.ps1
# ポートを変える場合: powershell -NoProfile -File scripts/serve.ps1 -Port 8001
```

- 東京: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- 大阪: [http://127.0.0.1:8000/?region=osaka](http://127.0.0.1:8000/?region=osaka)
- 終了: サーバーを起動したターミナルで Ctrl+C

MapLibre の JavaScript・CSS (unpkg) と地理院の背景タイルをブラウザから読み込むため、地図表示にはインターネット接続が必要です。検索と地点判定はブラウザ内で行い、現在地を外部へ送信しません。再生成後に古いデータが出る場合は強制再読み込みしてください。

## 作り方 (再現手順)

Python 3.11 以上と uv を使います (手元の確認環境は Python 3.13)。新規環境の `uv sync` は依存をダウンロードする場合があります。AIエージェントが実行するときは、データ・資料の取得前にファイル名・取得元・サイズを示して利用者の確認を取ります。新しい依存は `uv add` で追加し、`uv.lock` を更新します。

    uv sync --locked
    uv run ekiwalk fetch --all          # 取得するファイルを表示し、確認後にダウンロード
    uv run ekiwalk build --region tokyo --scenario base --scenario oedo-ext
    uv run ekiwalk build --region osaka --scenario base --scenario osaka-plan

既存環境・データだけで再現するときは `uv run --offline --frozen ekiwalk build ...` を使えます。生データは `data/raw/`、中間生成物は `data/build/<region>/`、公開用生成物は `web/data/<region>/` に書かれます。OSM の読み込みには DuckDB の spatial 拡張が必要です。初回ビルド時に拡張を取得する可能性があるので、事前に取得済みか確認してください。

`meta.json` の出力が Windows で CRLF になった場合は、コミット前に LF に揃えてください。`--from export` だけでも生成日時が変わります。

## 検証と作業の流れ

```powershell
uv run --offline --frozen pytest -q
node --test web/test/lookup.test.js web/test/search.test.js
uv run --offline --frozen ekiwalk --help
```

Web テストには Node.js を使います (CI は Node 24)。Windows でも実行できるようファイル名を明示します。表示・操作を変えたら、東京・大阪をパソコン幅とスマホ幅 (375 px) で開き、一覧・検索・現在/延伸後の切り替え・スマホの引き出しを確認します。

作業は `main` から切ったブランチで行います。コミット前に対象ファイル・サイズ・内容とステージ済み差分を確認し、1 MiB を超えるファイルは理由を調べます。利用者の確認後に fast-forward でマージし、push は毎回確認を取ります。push 後は GitHub Pages のデプロイ成功まで確認します。

## ライセンス

コードとオリジナルの文書は [Apache License 2.0](LICENSE) です。`web/data/` の地図データは外部データの派生物で、各データのライセンスに従います (詳細は [docs/data-policy.md](docs/data-policy.md))。
