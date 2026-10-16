"""AI五賢者 中間選挙議席予測 — daily runner.

Each model is called in its own, fully separate conversation. A model only ever
sees its OWN past analyses (data/history/<slug>.json), never another model's.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = ROOT / "data" / "history"
SITE_DATA = ROOT / "data" / "predictions.json"
KEY_FILE = ROOT / "key.txt"

API_URL = "https://openrouter.ai/api/v1/chat/completions"
JST = ZoneInfo("Asia/Tokyo")
ET = ZoneInfo("America/New_York")
ELECTION_DAY = dt.date(2026, 11, 3)
SENATE_SEATS, HOUSE_SEATS = 100, 435
CONTEXT_DAYS = 7  # how many of the model's own past days to feed back

MODELS = [
    {"slug": "gpt-6.1-sol", "id": "openai/gpt-6.1-sol", "name": "GPT-6.1 Sol", "maker": "OpenAI"},
    {"slug": "claude-opus-5.5", "id": "anthropic/claude-opus-5.5", "name": "Claude Opus 5.5", "maker": "Anthropic"},
    {"slug": "gemini-4-argon", "id": "google/gemini-4-argon", "name": "Gemini 4 Argon", "maker": "Google"},
    {"slug": "deepseek-v4.1-flash", "id": "deepseek/deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash", "maker": "DeepSeek"},
    {"slug": "qwen3.8-max", "id": "qwen/qwen3.8-max-0902", "name": "Qwen3.8 Max", "maker": "Alibaba Qwen"},
]

SYSTEM_PROMPT = """You are an independent, nonpartisan U.S. election analyst producing a daily seat forecast for the {year} U.S. midterm elections (Election Day: {election_day}, {days_left} days from now).

Current time: {now_et} (US Eastern) / {now_jst} (Japan).

You keep a running forecast. Below you will receive YOUR OWN analyses from previous days (and only yours). Treat them as your notes: build on them, but revise whenever new evidence warrants it.

## Today's procedure
1. Use the web search tool to gather news and data from roughly the last 24 hours (since about {since_et} ET). Run several distinct searches (aim for 6+), for example: new Senate/House polls, race-rating changes (Cook, Sabato, Inside Elections), polling averages and forecast models, prediction-market odds, fundraising/ad spending, candidate news, scandals, debates, economic and approval data, early-vote / turnout data.
2. Avoid one-sided sourcing. Deliberately draw on left-leaning, right-leaning, and centrist/wire outlets (e.g. AP, Reuters, NYT, WaPo, WSJ, Fox News, Politico, The Hill, NBC, CNN, National Review, Washington Examiner), plus nonpartisan data sources. Weigh hard data (polls, early vote, ratings) above opinion. Note when a poll is partisan-sponsored.
3. If there is little genuinely new information, it is fine to keep your numbers unchanged — do not create artificial movement. If this is your first day, establish a careful baseline from the overall state of the races.
4. Produce your updated seat forecast for the NEW Congress (most likely outcome / median expectation):
   - Senate: "dem" + "rep" must equal {senate}. Count independents who caucus with Democrats as "dem".
   - House: "dem" + "rep" must equal {house}.

## Output
Respond with ONE JSON object inside a ```json code block and nothing after it. All prose fields in natural Japanese.
```json
{{
  "senate": {{"dem": <int>, "rep": <int>}},
  "house": {{"dem": <int>, "rep": <int>}},
  "senate_control_prob_dem": <int 0-100, your probability Democrats control the Senate>,
  "house_control_prob_dem": <int 0-100, your probability Democrats control the House>,
  "comment": "<一言コメント: 40字以内。ウィットがあって読んで楽しいが、中身のある一言>",
  "change_reason": "<前日から数字を変えた/変えなかった理由を1〜2文>",
  "analysis": "<今日時点の考察。注目州・接戦区、世論調査の傾向、両党それぞれの強み・リスクを含めて400〜700字。明日のあなた自身への引き継ぎメモになる>",
  "key_news": [
    {{"title": "<ニュースの要約(日本語)>", "source": "<媒体名>", "url": "<URL>", "impact": "D+ | R+ | neutral"}}
  ]
}}
```
key_news: 3-6 items from the last ~24 hours, from a balanced mix of outlets."""

FIX_PROMPT = (
    "Your previous reply could not be used: {error}. "
    "Reply again with ONLY the corrected JSON object in a ```json code block, following the required schema exactly."
)


def load_key() -> str:
    return KEY_FILE.read_text(encoding="utf-8").strip()


def history_path(slug: str) -> Path:
    return HISTORY_DIR / f"{slug}.json"


def load_history(slug: str) -> list[dict]:
    p = history_path(slug)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def save_history(slug: str, entries: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    entries.sort(key=lambda e: e["date"])
    history_path(slug).write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_messages(history: list[dict], today: str, now: dt.datetime) -> list[dict]:
    now_et = now.astimezone(ET)
    since_et = now_et - dt.timedelta(hours=24)
    days_left = (ELECTION_DAY - now_et.date()).days
    system = SYSTEM_PROMPT.format(
        year=ELECTION_DAY.year,
        election_day=ELECTION_DAY.isoformat(),
        days_left=days_left,
        now_et=now_et.strftime("%Y-%m-%d %H:%M"),
        now_jst=now.astimezone(JST).strftime("%Y-%m-%d %H:%M"),
        since_et=since_et.strftime("%Y-%m-%d %H:%M"),
        senate=SENATE_SEATS,
        house=HOUSE_SEATS,
    )

    past = [e for e in history if e["date"] < today][-CONTEXT_DAYS:]
    if past:
        lines = ["Your own forecasts from previous days (oldest first):"]
        for e in past:
            lines.append(
                f"\n### {e['date']}\n"
                f"Senate D{e['senate']['dem']}-R{e['senate']['rep']} / House D{e['house']['dem']}-R{e['house']['rep']}"
                f" (P(D Senate)={e.get('senate_control_prob_dem', '?')}%, P(D House)={e.get('house_control_prob_dem', '?')}%)\n"
                f"Comment: {e.get('comment', '')}\n"
                f"Analysis: {e.get('analysis', '')}"
            )
        lines.append("\nNow search today's news and produce today's updated forecast.")
        user = "\n".join(lines)
    else:
        user = "You have no previous forecasts — this is your first day. Research the current state of the midterm races and today's news, then produce your baseline forecast."

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_openrouter(key: str, payload: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/kody-takuya/ai-sages-midterms",
            "X-Title": "AI Sages Midterm Forecast",
        },
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
            if "error" in body:
                raise RuntimeError(f"API error: {body['error']}")
            return body
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            last_err = RuntimeError(f"HTTP {e.code}: {detail}")
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # network / timeout
            last_err = e
        time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"OpenRouter call failed: {last_err}")


def extract_json(text: str) -> dict:
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidates = blocks[::-1] or [text[text.find("{"): text.rfind("}") + 1]]
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError("no parseable JSON object found")


def validate(d: dict) -> None:
    for chamber, total in (("senate", SENATE_SEATS), ("house", HOUSE_SEATS)):
        seats = d.get(chamber) or {}
        dem, rep = seats.get("dem"), seats.get("rep")
        if not isinstance(dem, int) or not isinstance(rep, int):
            raise ValueError(f"{chamber}.dem/rep must be integers")
        if dem + rep != total:
            raise ValueError(f"{chamber}: dem + rep = {dem + rep}, must equal {total}")
    if not str(d.get("comment", "")).strip() or not str(d.get("analysis", "")).strip():
        raise ValueError("comment and analysis must be non-empty")


def collect_citations(message: dict) -> list[dict]:
    seen, out = set(), []
    for a in message.get("annotations") or []:
        c = a.get("url_citation") or {}
        url = c.get("url")
        if url and url not in seen:
            seen.add(url)
            out.append({"url": url, "title": c.get("title", "")})
    return out


def run_model(model: dict, key: str, today: str, now: dt.datetime, effort: str) -> dict:
    history = load_history(model["slug"])
    messages = build_messages(history, today, now)
    base = {
        "model": model["id"],
        "max_tokens": 32000,
        "reasoning": {"effort": effort},
    }
    resp = call_openrouter(key, {
        **base,
        "messages": messages,
        "tools": [{"type": "openrouter:web_search", "parameters": {"max_results": 8, "max_uses": 10}}],
        "max_tool_calls": 15,
    })
    msg = resp["choices"][0]["message"]
    text = msg.get("content") or ""
    citations = collect_citations(msg)
    usage = resp.get("usage", {})
    cost = float(usage.get("cost") or 0)
    searches = (usage.get("server_tool_use") or {}).get("web_search_requests")

    data, err = None, None
    for _ in range(3):
        try:
            data = extract_json(text)
            validate(data)
            err = None
            break
        except (ValueError, TypeError) as e:
            err = str(e)
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": FIX_PROMPT.format(error=err)}]
            fix = call_openrouter(key, {**base, "messages": messages})
            text = fix["choices"][0]["message"].get("content") or ""
            cost += float((fix.get("usage") or {}).get("cost") or 0)
    if err:
        raise RuntimeError(f"{model['name']}: invalid output after retries: {err}")

    entry = {
        "date": today,
        "generated_at": now.astimezone(JST).isoformat(timespec="seconds"),
        "model_id": resp.get("model", model["id"]),
        "senate": {"dem": data["senate"]["dem"], "rep": data["senate"]["rep"]},
        "house": {"dem": data["house"]["dem"], "rep": data["house"]["rep"]},
        "senate_control_prob_dem": data.get("senate_control_prob_dem"),
        "house_control_prob_dem": data.get("house_control_prob_dem"),
        "comment": str(data["comment"]).strip(),
        "change_reason": str(data.get("change_reason", "")).strip(),
        "analysis": str(data["analysis"]).strip(),
        "key_news": data.get("key_news") or [],
        "citations": citations,
        "searches": searches,
        "cost_usd": round(cost, 4),
    }
    history = [e for e in history if e["date"] != today] + [entry]
    save_history(model["slug"], history)
    return entry


def build_site_data(now: dt.datetime) -> None:
    out = {"updated_at": now.astimezone(JST).isoformat(timespec="seconds"),
           "election_day": ELECTION_DAY.isoformat(),
           "seats": {"senate": SENATE_SEATS, "house": HOUSE_SEATS},
           "models": []}
    for m in MODELS:
        hist = load_history(m["slug"])
        out["models"].append({
            **{k: m[k] for k in ("slug", "name", "maker", "id")},
            "series": [{"date": e["date"], "senate": e["senate"], "house": e["house"],
                        "senate_control_prob_dem": e.get("senate_control_prob_dem"),
                        "house_control_prob_dem": e.get("house_control_prob_dem"),
                        "comment": e["comment"]} for e in hist],
            "latest": {k: v for k, v in hist[-1].items() if k not in ("cost_usd",)} if hist else None,
        })
    SITE_DATA.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="model slugs to run (default: all)")
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high"])
    ap.add_argument("--site-only", action="store_true", help="just rebuild data/predictions.json")
    args = ap.parse_args()

    now = dt.datetime.now(tz=JST)
    today = now.date().isoformat()  # forecasts are keyed by the JST date
    if args.site_only:
        build_site_data(now)
        return 0

    key = load_key()
    targets = [m for m in MODELS if not args.only or m["slug"] in args.only]
    failures = 0
    # Separate threads, separate conversations, separate history files: nothing is shared between models.
    with cf.ThreadPoolExecutor(max_workers=len(targets)) as ex:
        futs = {ex.submit(run_model, m, key, today, now, args.effort): m for m in targets}
        for f in cf.as_completed(futs):
            m = futs[f]
            try:
                e = f.result()
                print(f"[OK] {m['name']}: Senate D{e['senate']['dem']}-R{e['senate']['rep']} "
                      f"House D{e['house']['dem']}-R{e['house']['rep']} "
                      f"searches={e['searches']} cost=${e['cost_usd']} | {e['comment']}", flush=True)
            except Exception as ex_:
                failures += 1
                print(f"[FAIL] {m['name']}: {ex_}", file=sys.stderr, flush=True)

    build_site_data(now)
    return 1 if failures == len(targets) else 0


if __name__ == "__main__":
    sys.exit(main())
