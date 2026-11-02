# 🔮 AI五賢者の中間選挙予測

GPT-6.1 Sol / Claude Sonnet 5.5 / Gemini 4 Argon / DeepSeek V4.1 Flash / Qwen3.8 Max の5モデルが、
毎朝（日本時間7時ごろ）直近24時間のニュースをWeb検索し、2026年米中間選挙の上院・下院議席数を予測します。

- 各モデルは独立した会話で実行され、自分自身の過去の考察（`data/history/<model>.json`）だけを読み返します。他モデルの予測は見ません。
- API: [OpenRouter](https://openrouter.ai/)（`openrouter:web_search` サーバーツールで検索）
- サイト: GitHub Pages（`index.html` + `data/predictions.json`）

## ローカル実行

```powershell
py -3.13 scripts\predict.py                 # 全モデル
py -3.13 scripts\predict.py --only qwen3.8-max
powershell -File scripts\run_daily.ps1      # 予測 → commit → push
```

APIキーはリポジトリ直下の `key.txt`（gitignore済み）に置きます。


## 選挙当日の最終予測・振り返り（2026年）

米国の投票日は11月3日です。日本時間では次のスケジュールです。

| 開始日時（JST） | 処理 |
| --- | --- |
| 11月4日 06:00 | 全5モデルの最終予測を生成し、`data/final_predictions.json` に固定 |
| 11月5日 06:00 | 保存した自分の予測と実際の報道結果を比較し、`data/retrospective.json` に振り返りを追記 |

処理開始から検索・生成・push・Pages反映まで時間がかかります。6時ちょうどの掲載ではありません。
上部の予測・考察・グラフはスナップショットを維持し、下部に各モデルの振り返り、結果の基準時刻、出典を表示します。
議席は民主・共和・その他・未確定に分け、未確定の段階では最終確定結果と扱いません。
振り返りの再試行も11月5日6時までに報じられた結果を使います。

### Windowsの実行設定（既存の実行PCで一度実行）

```powershell
git pull
powershell -ExecutionPolicy Bypass -File scripts\install_election_tasks.ps1
```

この登録は既存の7時タスクを削除せず、6時の単発タスク2件を追加します。同じPC・アカウントの既存APIキーとgit認証を使います。
そのアカウントにサインインした状態でPCを稼働させてください。登録スクリプトをGitHubに置くだけではWindowsの予約は変更されません。
`run_daily.ps1` のロックで重複実行を防止します。APIキーは従来の `key.txt` または `OPENROUTER_API_KEY` 環境変数で指定できます。

最終予測が保存されると、通常実行・`--only`・`--site-only` でも上書きしません。
最終予測に失敗したモデルは前回値を保持し、その旨を表示します。6:30以降に初めて起動した場合も、結果を見た予測の混入を避けて前回値を固定します。
振り返りは成功分を逐次保存し、再実行時は未取得モデルのみ再試行します。履歴には振り返りを混ぜません。

検証: `python -m unittest discover -s tests -v`（API通信なし）
