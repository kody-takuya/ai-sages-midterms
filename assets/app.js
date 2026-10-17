(() => {
  "use strict";

  const SAGES = {
    "gpt-6.1-sol":     { color: "--m1", title: "陽の賢者", glyph: "陽", short: "Sol",   emblem: sun },
    "claude-sonnet-5.5": { color: "--m2", title: "詩の賢者", glyph: "詩", short: "Sonnet", emblem: quill },
    "gemini-4-argon":  { color: "--m3", title: "光の賢者", glyph: "光", short: "Argon", emblem: crystal },
    "deepseek-v4.1-flash": { color: "--m4", title: "深淵の賢者", glyph: "深", short: "DeepSeek", emblem: abyss, flag: "東方より" },
    "qwen3.8-max":     { color: "--m5", title: "千問の賢者", glyph: "問", short: "Qwen", emblem: question, flag: "東方より" },
  };
  // D needs 51 in the Senate (the VP breaks 50-50 ties for the GOP); 218 in the House.
  const MAJORITY = { senate: 51, house: 218 };
  const CHAMBER_JA = { senate: "上院", house: "下院" };
  const STATUS_JA = { new: "新説", kept: "継続", refined: "修正", discarded_and_replaced: "撤回→新説" };

  const $ = (s, r = document) => r.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
  const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const md = (iso) => { const [, m, d] = iso.split("-"); return `${+m}/${+d}`; };

  function sun() {
    return `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="20" cy="20" r="7"/>${
      [0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const r = (a * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r);
        return `<line x1="${20 + 11 * c}" y1="${20 + 11 * s}" x2="${20 + 16 * c}" y2="${20 + 16 * s}"/>`;
      }).join("")}</svg>`;
  }
  function quill() {
    return `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M31 6C19 8 12 17 10 30c8-2 17-8 21-24z"/><path d="M10 30l13-14"/><path d="M8 34h10"/></svg>`;
  }
  function crystal() {
    return `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linejoin="round"><path d="M20 4l10 10-10 22L10 14z"/><path d="M10 14h20M20 4v32"/><circle cx="33" cy="7" r="1.6" fill="currentColor" stroke="none"/><circle cx="7" cy="30" r="1.2" fill="currentColor" stroke="none"/></svg>`;
  }

  function abyss() {
    return `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M4 14c4-4 8-4 12 0s8 4 12 0 6-3 8-1"/><path d="M4 22c4-4 8-4 12 0s8 4 12 0 6-3 8-1"/><path d="M4 30c4-4 8-4 12 0s8 4 12 0 6-3 8-1"/></svg>`;
  }
  function question() {
    return `<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="20" cy="20" r="15"/><path d="M15 16a5 5 0 1 1 7 4.6c-1.4.7-2 1.6-2 3.2"/><circle cx="20" cy="29" r="1.6" fill="currentColor" stroke="none"/></svg>`;
  }

  let DATA = null;

  fetch("data/predictions.json", { cache: "no-store" })
    .then((r) => r.json())
    .then((d) => { DATA = d; render(); })
    .catch(() => { $("#sages").innerHTML = `<p>データを読み込めませんでした。</p>`; });

  function render() {
    renderHeader();
    renderVerdict("senate", $("#verdict-senate"));
    renderVerdict("house", $("#verdict-house"));
    renderSages();
    renderLegends();
    renderNotes();
    const charts = [["senate", $("#chart-senate")], ["house", $("#chart-house")]];
    const draw = () => charts.forEach(([c, el]) => drawChart(el, c));
    draw();
    let w = 0;
    new ResizeObserver(() => { const nw = $("#chart-senate").clientWidth; if (nw !== w) { w = nw; draw(); } }).observe($("#chart-senate"));
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  }

  function renderHeader() {
    const now = new Date();
    const jst = new Date(now.getTime() + (now.getTimezoneOffset() + 540) * 60000);
    const today = Date.UTC(jst.getFullYear(), jst.getMonth(), jst.getDate());
    const [y, m, d] = DATA.election_day.split("-").map(Number);
    const days = Math.round((Date.UTC(y, m - 1, d) - today) / 864e5);
    $("#countdown").innerHTML = days > 0 ? `投票日まで あと<b>${days}</b>日`
      : days >= -1 ? `🗳️ 投票日！ 開票を待て` : `投票日（11/3）は終了しました`;
    const u = new Date(DATA.updated_at);
    if (!isNaN(u)) {
      $("#updated").textContent = `最終更新 ${u.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })} JST`;
    }
  }

  function renderVerdict(ch, el) {
    const votes = DATA.models.map((m) => {
      const s = SAGES[m.slug], l = m.latest;
      if (!l) return { cls: "x", glyph: s.glyph, name: m.name };
      return { cls: l[ch].dem >= MAJORITY[ch] ? "d" : "r", glyph: s.glyph, name: m.name };
    });
    const d = votes.filter((v) => v.cls === "d").length, r = votes.filter((v) => v.cls === "r").length;
    const pending = votes.length - d - r;
    let result;
    if (d + r === 0) result = "審議中…";
    else if (d === r) result = `真っ二つ ${d} : ${r}`;
    else if ((d === 0 || r === 0) && !pending) result = `<span style="color:var(${d ? "--dem" : "--rep"})">全会一致で${d ? "民主党" : "共和党"}</span>`;
    else result = `<span style="color:var(${d > r ? "--dem" : "--rep"})">${d > r ? "民主党" : "共和党"}</span> ${Math.max(d, r)} : ${Math.min(d, r)}`;
    if (pending && d + r) result += ` <small style="color:var(--muted);font-weight:500">（${pending}名瞑想中）</small>`;
    el.innerHTML = `<span class="label">${CHAMBER_JA[ch]}の多数派は？</span>
      <span class="votes">${votes.map((v) => `<span class="vote ${v.cls}" title="${esc(v.name)}">${v.glyph}</span>`).join("")}</span>
      <span class="result">${result}</span>`;
  }

  function seatBar(ch, seats) {
    const total = DATA.seats[ch];
    const majPct = (MAJORITY[ch] / total) * 100;
    return `<div class="seatbar" role="img" aria-label="${CHAMBER_JA[ch]} 民主党${seats.dem} 共和党${seats.rep}">
      <div class="seg d" style="flex:${seats.dem}">D ${seats.dem}</div>
      <div class="seg r" style="flex:${seats.rep}">${seats.rep} R</div>
      <div class="maj" style="left:calc(${majPct}% - 1px)" title="過半数ライン ${MAJORITY[ch]}"></div>
    </div>`;
  }

  function deltaText(m, ch) {
    const s = m.series;
    if (s.length < 2) return "初回予測";
    const diff = s[s.length - 1][ch].dem - s[s.length - 2][ch].dem;
    if (diff === 0) return "前日から変化なし";
    return `前日比 ${diff > 0 ? "D" : "R"}+${Math.abs(diff)}`;
  }

  function renderSages() {
    $("#sages").innerHTML = DATA.models.map((m) => {
      const s = SAGES[m.slug], l = m.latest;
      const body = l ? `
        <div class="bubble">${esc(l.comment)}</div>
        ${l.hypothesis_title ? `<div class="thesis"><span>仮説</span>${esc(l.hypothesis_title)}</div>` : ""}
        <div>
          <div class="seatrow"><span class="ch">上院</span>${seatBar("senate", l.senate)}</div>
          <div class="seatmeta"><span class="delta">${deltaText(m, "senate")}</span><span>D支配確率 ${l.senate_control_prob_dem ?? "–"}%</span></div>
        </div>
        <div>
          <div class="seatrow"><span class="ch">下院</span>${seatBar("house", l.house)}</div>
          <div class="seatmeta"><span class="delta">${deltaText(m, "house")}</span><span>D支配確率 ${l.house_control_prob_dem ?? "–"}%</span></div>
        </div>`
        : `<div class="bubble quiet">まだ瞑想中…</div>`;
      return `<article class="sage" style="--c:var(${s.color})">${s.flag ? `<span class="flag">${s.flag}</span>` : ""}
        <div class="sage-top">
          <div class="emblem" style="color:var(${s.color})">${s.emblem()}</div>
          <div><div class="sage-title">${s.title}</div><div class="sage-name">${esc(m.name)}</div><div class="sage-maker">${esc(m.maker)}${l ? ` · ${md(l.date)}の予測` : ""}</div></div>
        </div>${body}
      </article>`;
    }).join("");
  }

  function renderLegends() {
    const html = DATA.models.map((m) => `<span><i style="background:var(${SAGES[m.slug].color})"></i>${esc(m.name)}</span>`).join("");
    document.querySelectorAll("[data-legend]").forEach((el) => (el.innerHTML = html));
  }

  function renderNotes() {
    $("#notes").innerHTML = DATA.models.map((m, i) => {
      const s = SAGES[m.slug], l = m.latest;
      if (!l) return "";
      const news = (l.key_news || []).map((n) => {
        const imp = String(n.impact || "").toUpperCase();
        const cls = imp.startsWith("D") ? "D" : imp.startsWith("R") ? "R" : "N";
        const label = cls === "N" ? "中立" : `${cls}+`;
        const url = safeUrl(n.url);
        const title = url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title);
        return `<li><span class="impact ${cls}">${label}</span>${title} <span class="src">${esc(n.source)}</span></li>`;
      }).join("");
      return `<details class="note" style="--c:var(${s.color})">
        <summary><span class="dot"></span>${esc(m.name)} の考察ノート</summary>
        ${l.hypothesis ? `<h3>仮説 ${STATUS_JA[l.hypothesis_status] ? `<span class="hstatus">${STATUS_JA[l.hypothesis_status]}</span>` : ""}</h3><p class="hyp"><b>${esc(l.hypothesis_title)}</b>
${esc(l.hypothesis)}</p>` : ""}
        ${(l.hidden_dynamics || []).length ? `<h3>水面下の動き</h3><ul>${l.hidden_dynamics.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        ${l.change_reason ? `<h3>仮説から議席数へ</h3><p>${esc(l.change_reason)}</p>` : ""}
        <h3>今日の考察</h3><p>${esc(l.analysis)}</p>
        ${news ? `<h3>注目ニュース</h3><ul>${news}</ul>` : ""}
        <p class="src">参照ソース ${(l.citations || []).length}件 · ${esc(l.model_id || m.id)} · ${md(l.date)}</p>
      </details>`;
    }).join("");
  }

  // ---------- chart ----------
  function niceStep(span) {
    const raw = span / 5, p = Math.pow(10, Math.floor(Math.log10(raw)));
    return [1, 2, 5, 10].map((k) => k * p).find((s) => raw <= s) || 10 * p;
  }

  function drawChart(el, ch) {
    const models = DATA.models.filter((m) => m.series.length);
    const dates = [...new Set(models.flatMap((m) => m.series.map((p) => p.date)))].sort();
    if (!dates.length) { el.innerHTML = `<p class="chart-sub">予測データ待ち</p>`; return; }

    const W = Math.max(280, el.clientWidth), narrow = W < 420;
    const H = narrow ? 240 : 280;
    const M = { t: 14, r: narrow ? 70 : 92, b: 26, l: 36 };
    const pw = W - M.l - M.r, ph = H - M.t - M.b;
    const maj = MAJORITY[ch];
    const vals = models.flatMap((m) => m.series.map((p) => p[ch].dem)).concat([maj]);
    const pad = ch === "senate" ? 3 : 10;
    let lo = Math.min(...vals) - pad, hi = Math.max(...vals) + pad;
    const step = niceStep(hi - lo);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;

    const x = (i) => (dates.length === 1 ? M.l + pw / 2 : M.l + (i / (dates.length - 1)) * pw);
    const y = (v) => M.t + ((hi - v) / (hi - lo)) * ph;
    const yMaj = y(maj - 0.5);

    const parts = [];
    parts.push(`<rect x="${M.l}" y="${M.t}" width="${pw}" height="${yMaj - M.t}" fill="var(--dem-wash)"/>`);
    parts.push(`<rect x="${M.l}" y="${yMaj}" width="${pw}" height="${M.t + ph - yMaj}" fill="var(--rep-wash)"/>`);
    for (let v = lo; v <= hi + 1e-9; v += step) {
      parts.push(`<line class="gridline" x1="${M.l}" x2="${M.l + pw}" y1="${y(v)}" y2="${y(v)}"/>`);
      parts.push(`<text class="tick" x="${M.l - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text>`);
    }
    parts.push(`<line class="majline" x1="${M.l}" x2="${M.l + pw}" y1="${yMaj}" y2="${yMaj}"/>`);
    parts.push(`<text class="zone-label" x="${M.l + 6}" y="${M.t + 14}" fill="var(--dem)">▲ 民主党多数</text>`);
    parts.push(`<text class="zone-label" x="${M.l + 6}" y="${M.t + ph - 6}" fill="var(--rep)">▼ 共和党多数</text>`);
    parts.push(`<text class="tick" x="${M.l + pw - 4}" y="${yMaj - 5}" text-anchor="end">過半数 ${maj}〜</text>`);

    const maxTicks = narrow ? 4 : 7, every = Math.max(1, Math.ceil(dates.length / maxTicks));
    dates.forEach((d, i) => {
      if (i % every === 0 || i === dates.length - 1) {
        parts.push(`<text class="tick" x="${x(i)}" y="${H - 6}" text-anchor="middle">${md(d)}</text>`);
      }
    });

    const ends = [];
    const showAllMarkers = dates.length <= 10;
    models.forEach((m) => {
      const col = `var(${SAGES[m.slug].color})`;
      const pts = m.series.map((p) => [x(dates.indexOf(p.date)), y(p[ch].dem)]);
      if (pts.length > 1) {
        parts.push(`<path d="${pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join("")}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`);
      }
      pts.forEach((p, i) => {
        if (showAllMarkers || i === pts.length - 1) {
          parts.push(`<circle cx="${p[0]}" cy="${p[1]}" r="4.5" fill="${col}" stroke="var(--surface)" stroke-width="2"/>`);
        }
      });
      const last = pts[pts.length - 1];
      ends.push({ y: last[1], x: last[0], col, label: `${SAGES[m.slug].short} ${m.series[m.series.length - 1][ch].dem}` });
    });
    // direct labels at the right edge, nudged apart
    ends.sort((a, b) => a.y - b.y);
    for (let i = 1; i < ends.length; i++) if (ends[i].y - ends[i - 1].y < 14) ends[i].y = ends[i - 1].y + 14;
    ends.forEach((e) => {
      parts.push(`<text x="${M.l + pw + 8}" y="${e.y + 4}" font-size="11" font-weight="700" fill="var(--ink-2)"><tspan fill="${e.col}">●</tspan> ${esc(e.label)}</text>`);
    });

    parts.push(`<line class="xhair" x1="0" x2="0" y1="${M.t}" y2="${M.t + ph}" stroke="var(--ink-2)" stroke-width="1" visibility="hidden"/>`);
    parts.push(`<rect class="hit" x="${M.l - 10}" y="${M.t}" width="${pw + 20}" height="${ph}" fill="transparent"/>`);

    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${CHAMBER_JA[ch]}の民主党予測議席の推移">${parts.join("")}</svg>`;

    const svg = el.querySelector("svg"), hit = svg.querySelector(".hit"), xh = svg.querySelector(".xhair"), tt = $("#tooltip");
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      let idx = 0, best = Infinity;
      dates.forEach((_, i) => { const dd = Math.abs(x(i) - px); if (dd < best) { best = dd; idx = i; } });
      xh.setAttribute("x1", x(idx)); xh.setAttribute("x2", x(idx)); xh.setAttribute("visibility", "visible");
      const rows = DATA.models.map((m) => {
        const p = m.series.find((q) => q.date === dates[idx]);
        if (!p) return "";
        return `<div class="tt-row"><i style="background:var(${SAGES[m.slug].color})"></i><span>${esc(m.name)}</span><b>D ${p[ch].dem} – R ${p[ch].rep}</b></div>`;
      }).join("");
      tt.innerHTML = `<div class="tt-date">${md(dates[idx])} · ${CHAMBER_JA[ch]}</div>${rows}`;
      tt.hidden = false;
      const tw = tt.offsetWidth, th = tt.offsetHeight;
      let left = ev.clientX + 14; if (left + tw > innerWidth - 8) left = ev.clientX - tw - 14;
      tt.style.left = Math.max(8, left) + "px";
      tt.style.top = Math.max(8, ev.clientY - th - 12) + "px";
    };
    const leave = () => { tt.hidden = true; xh.setAttribute("visibility", "hidden"); };
    hit.addEventListener("pointermove", move);
    hit.addEventListener("pointerdown", move);
    hit.addEventListener("pointerleave", leave);
  }
})();
