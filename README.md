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
